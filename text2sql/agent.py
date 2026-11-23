"""Natural language -> SQL with Claude, with guardrails and self-correction.

Flow: read schema + sample values -> ask Claude for one SQLite query -> safety check (read-only, single
SELECT/WITH) -> validate with EXPLAIN -> run with a row limit -> on error, send the error back and retry.
"""
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
MAX_ROWS = 200
MAX_ATTEMPTS = 3

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b", re.I)

SYSTEM = """You translate business questions into a single SQLite query.
Rules:
- Return exactly one query inside a ```sql code block, then one short sentence explaining it.
- Read-only: only SELECT or WITH ... SELECT.
- Use only the tables and columns in the schema. Prefer explicit JOINs and readable column aliases.
- Dates are ISO strings (YYYY-MM-DD); use SQLite date functions.
- If the question cannot be answered from the schema, return no SQL and say why."""


class UnsafeQuery(ValueError):
    pass


@dataclass
class Answer:
    question: str
    sql: str | None = None
    explanation: str = ""
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    attempts: int = 0
    error: str | None = None


def schema_text(con: sqlite3.Connection, samples: int = 3) -> str:
    """CREATE statements plus a few distinct values for short text columns (helps the model pick filters)."""
    out = []
    for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        out.append(sql.strip() + ";")
        for col in con.execute("PRAGMA table_info(%s)" % name).fetchall():
            cname, ctype = col[1], (col[2] or "").upper()
            if ctype == "TEXT":
                vals = [r[0] for r in con.execute(
                    "SELECT DISTINCT %s FROM %s WHERE %s IS NOT NULL LIMIT 12" % (cname, name, cname))]
                if 0 < len(vals) <= 10:
                    out.append("-- %s.%s values: %s" % (name, cname, ", ".join(map(str, vals[:samples * 3]))))
    return "\n".join(out)


def extract_sql(text: str) -> str | None:
    m = re.search(r"```(?:sql)?\s*(.+?)```", text, re.S | re.I)
    return m.group(1).strip().rstrip(";").strip() if m else None


def check_safe(sql: str) -> None:
    body = re.sub(r"'(?:[^']|'')*'", "''", sql)          # ignore string literals
    body = re.sub(r"--[^\n]*|/\*.*?\*/", " ", body, flags=re.S)
    if ";" in body:
        raise UnsafeQuery("only one statement is allowed")
    if not re.match(r"\s*(select|with)\b", body, re.I):
        raise UnsafeQuery("only SELECT queries are allowed")
    if FORBIDDEN.search(body):
        raise UnsafeQuery("query contains a write or admin keyword")


def connect_readonly(path) -> sqlite3.Connection:
    return sqlite3.connect("file:%s?mode=ro" % Path(path).resolve(), uri=True)


class TextToSQL:
    def __init__(self, db_path, client=None):
        self.db_path = db_path
        self.con = connect_readonly(db_path)
        self.schema = schema_text(self.con)
        if client is None:
            import anthropic  # imported here so tests can run without the SDK
            client = anthropic.Anthropic()
        self.client = client

    def _ask_model(self, messages):
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            system=SYSTEM + "\n\nSchema:\n" + self.schema,
            messages=messages,
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    def ask(self, question: str) -> Answer:
        ans = Answer(question)
        messages = [{"role": "user", "content": question}]
        for attempt in range(1, MAX_ATTEMPTS + 1):
            ans.attempts = attempt
            reply = self._ask_model(messages)
            sql = extract_sql(reply)
            ans.explanation = re.sub(r"```.*?```", "", reply, flags=re.S).strip()
            if sql is None:
                ans.error = "The question can't be answered from this database."
                return ans
            ans.sql = sql
            try:
                check_safe(sql)
                self.con.execute("EXPLAIN " + sql)
                cur = self.con.execute(sql)
                ans.columns = [d[0] for d in cur.description]
                ans.rows = cur.fetchmany(MAX_ROWS)
                ans.error = None
                return ans
            except (UnsafeQuery, sqlite3.Error) as e:
                ans.error = str(e)
                messages += [{"role": "assistant", "content": reply},
                             {"role": "user", "content": "That query failed: %s\nFix it and return one corrected query." % e}]
        return ans
