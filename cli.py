"""Ask the demo database a question from the terminal.
python3 cli.py "Which 5 companies got the most applications for Data roles this year?" """
import sys

from text2sql.agent import TextToSQL
from text2sql.db import DEFAULT_DB, build

if __name__ == "__main__":
    if not DEFAULT_DB.exists():
        build()
    ans = TextToSQL(DEFAULT_DB).ask(" ".join(sys.argv[1:]) or "How many open job posts are there per city?")
    print("SQL:\n" + (ans.sql or "-"))
    print("\n" + ans.explanation)
    if ans.error:
        print("\nError:", ans.error)
    else:
        print("\n" + " | ".join(ans.columns))
        for r in ans.rows[:30]:
            print(" | ".join(map(str, r)))
    print("\n(attempts: %d)" % ans.attempts)
