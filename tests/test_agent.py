"""Offline tests: a fake model client stands in for Claude. python3 -m unittest"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from text2sql.agent import TextToSQL, UnsafeQuery, check_safe, extract_sql
from text2sql.db import build


class FakeClient:
    """Returns scripted replies in order and records the messages it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.replies.pop(0))])


class GuardTests(unittest.TestCase):
    def test_extract(self):
        self.assertEqual(extract_sql("x\n```sql\nSELECT 1;\n```\nok"), "SELECT 1")
        self.assertIsNone(extract_sql("no query here"))

    def test_rejects_writes_and_multi(self):
        for bad in ["DELETE FROM companies", "SELECT 1; DROP TABLE companies", "PRAGMA table_info(x)",
                    "WITH a AS (SELECT 1) DELETE FROM companies", "ATTACH 'x.db' AS y"]:
            with self.assertRaises(UnsafeQuery, msg=bad):
                check_safe(bad)

    def test_allows_keywords_inside_strings(self):
        check_safe("SELECT * FROM job_posts WHERE title = 'Update; delete me'")


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = build(Path(cls.tmp.name) / "t.db", posts=80, candidates=100, applications=300)

    def test_happy_path(self):
        fc = FakeClient(["```sql\nSELECT city, COUNT(*) AS n FROM companies GROUP BY city\n```\nCounts per city."])
        ans = TextToSQL(self.db, fc).ask("companies per city")
        self.assertIsNone(ans.error)
        self.assertEqual(ans.columns, ["city", "n"])
        self.assertEqual(sum(r[1] for r in ans.rows), 60)
        self.assertIn("CREATE TABLE companies", fc.calls[0]["system"])

    def test_self_corrects_after_error(self):
        fc = FakeClient(["```sql\nSELECT nme FROM companies\n```", "```sql\nSELECT name FROM companies LIMIT 3\n```"])
        ans = TextToSQL(self.db, fc).ask("company names")
        self.assertEqual(ans.attempts, 2)
        self.assertEqual(len(ans.rows), 3)
        self.assertIn("no such column", fc.calls[1]["messages"][-1]["content"])

    def test_unsafe_never_runs(self):
        fc = FakeClient(["```sql\nDELETE FROM companies\n```"] * 3)
        ans = TextToSQL(self.db, fc).ask("delete everything")
        self.assertIsNotNone(ans.error)
        self.assertEqual(ans.attempts, 3)

    def test_unanswerable(self):
        ans = TextToSQL(self.db, FakeClient(["The schema has no weather data."])).ask("weather?")
        self.assertIsNone(ans.sql)
        self.assertIsNotNone(ans.error)


if __name__ == "__main__":
    unittest.main()
