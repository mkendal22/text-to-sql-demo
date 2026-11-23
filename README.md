# text-to-sql-demo

**Ask a database questions in plain language and get validated, read-only SQL and results, powered by Claude.**

At work I built an internal text-to-SQL assistant that lets BI, data platform and sales teams get the data tables they need without writing SQL. This repo is a small, independent version of the same idea. It uses a synthetic job-marketplace database and contains no company code or data.

```
$ python3 cli.py "Application-to-hire conversion rate by job category"

SQL:
SELECT jp.category,
       COUNT(*) AS applications,
       SUM(a.status = 'Hired') AS hires,
       ROUND(100.0 * SUM(a.status = 'Hired') / COUNT(*), 1) AS hire_rate_pct
FROM applications a
JOIN job_posts jp ON jp.id = a.job_post_id
GROUP BY jp.category
ORDER BY hire_rate_pct DESC
```

## How it works

1. **Schema grounding.** The prompt includes the `CREATE TABLE` statements, plus the real values of short text columns (statuses, cities, seniority) so filters match the data.
2. **Generation.** Claude returns exactly one SQLite query and a one-line explanation. It says so when the question can't be answered from the schema.
3. **Guardrails.** The query must be a single `SELECT` or `WITH` statement. Write and admin keywords are rejected, and the database is opened in read-only mode as a second layer.
4. **Validation.** `EXPLAIN` runs before execution. Results are capped at 200 rows.
5. **Self-correction.** If the query fails (wrong column, syntax error, unsafe statement), the error goes back to the model, which gets up to 3 attempts in total.

| File | Purpose |
|---|---|
| `text2sql/agent.py` | Prompting, guardrails, validation and the retry loop |
| `text2sql/db.py` | Generates the synthetic database (companies, job posts, candidates, applications) |
| `app.py` | Streamlit UI with example questions |
| `cli.py` | Terminal version |
| `tests/` | Offline tests with a fake model client: guardrails, retries and unanswerable questions |

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # your key
streamlit run app.py                # or: python3 cli.py "your question"
python3 -m unittest discover -s tests -t .   # tests need no API key
```

The default model is `claude-opus-5-5`. You can change it with the `CLAUDE_MODEL` environment variable.

---
Melik Yusuf Kendal · Data Scientist & AI Engineer
