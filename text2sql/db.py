"""Builds a small synthetic job-marketplace database (SQLite) to query in plain language.

All data is randomly generated with a fixed seed: no real companies or people.
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "jobs.db"

SCHEMA = """
CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT NOT NULL,
    city TEXT NOT NULL,
    employee_count INTEGER NOT NULL
);
CREATE TABLE job_posts (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    title TEXT NOT NULL,
    category TEXT NOT NULL,          -- Engineering, Data, Sales, Marketing, Design, Operations
    seniority TEXT NOT NULL,         -- Intern, Junior, Mid, Senior, Lead
    work_mode TEXT NOT NULL,         -- Onsite, Hybrid, Remote
    salary_min INTEGER,              -- monthly, TRY
    salary_max INTEGER,
    posted_on DATE NOT NULL,
    is_open INTEGER NOT NULL         -- 1 = still accepting applications
);
CREATE TABLE candidates (
    id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    city TEXT NOT NULL,
    years_experience INTEGER NOT NULL,
    top_skill TEXT NOT NULL
);
CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    job_post_id INTEGER NOT NULL REFERENCES job_posts(id),
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    applied_on DATE NOT NULL,
    status TEXT NOT NULL             -- Applied, Screening, Interview, Offer, Hired, Rejected
);
"""

CITIES = ["Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Kocaeli", "Eskisehir"]
INDUSTRIES = ["Software", "E-commerce", "Fintech", "Gaming", "Retail", "Logistics", "Health", "Energy"]
CATEGORIES = {
    "Engineering": ["Backend Developer", "Frontend Developer", "Mobile Developer", "DevOps Engineer", "QA Engineer"],
    "Data": ["Data Analyst", "Data Engineer", "Data Scientist", "ML Engineer", "BI Specialist"],
    "Sales": ["Account Executive", "Sales Representative", "Business Development"],
    "Marketing": ["Growth Marketer", "Content Specialist", "Performance Marketer"],
    "Design": ["Product Designer", "UX Researcher", "Graphic Designer"],
    "Operations": ["Operations Specialist", "Customer Success", "HR Specialist"],
}
SENIORITY = [("Intern", 0.6), ("Junior", 1.0), ("Mid", 1.5), ("Senior", 2.2), ("Lead", 3.0)]
SKILLS = ["Python", "SQL", "React", "Flutter", "Excel", "Figma", "Sales", "Java", "Go", "Power BI", "Kotlin", "Swift"]
FIRST = ["Ali", "Ayse", "Mehmet", "Zeynep", "Can", "Elif", "Emre", "Selin", "Burak", "Deniz", "Mert", "Ece", "Kerem", "Irem"]
LAST = ["Yilmaz", "Kaya", "Demir", "Sahin", "Celik", "Arslan", "Dogan", "Kilic", "Aydin", "Ozturk", "Koc", "Polat"]
SYLLABLES = ["nova", "tek", "lab", "soft", "net", "ver", "mint", "loop", "flow", "bit", "core", "sun", "pix", "data"]
STATUS = [("Applied", 40), ("Screening", 20), ("Interview", 15), ("Offer", 5), ("Hired", 4), ("Rejected", 30)]


def _weighted(rng, pairs):
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs])[0]


def build(path=DEFAULT_DB, seed=42, companies=60, posts=600, candidates=1500, applications=6000):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rng = random.Random(seed)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    names = set()
    while len(names) < companies:
        names.add((rng.choice(SYLLABLES) + rng.choice(SYLLABLES)).capitalize())
    for i, name in enumerate(sorted(names), 1):
        con.execute("INSERT INTO companies VALUES (?,?,?,?,?)",
                    (i, name, rng.choice(INDUSTRIES), rng.choice(CITIES), rng.choice([12, 40, 85, 150, 400, 1200, 5000])))
    today = date(2026, 11, 1)
    for i in range(1, posts + 1):
        cat = rng.choice(list(CATEGORIES))
        sen, mult = rng.choice(SENIORITY)
        base = rng.randint(32, 55) * 1000
        smin = int(base * mult / 1000) * 1000
        has_salary = rng.random() < 0.7
        posted = today - timedelta(days=rng.randint(0, 364))
        con.execute("INSERT INTO job_posts VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (i, rng.randint(1, companies), "%s %s" % (sen, rng.choice(CATEGORIES[cat])) if sen != "Mid" else rng.choice(CATEGORIES[cat]),
                     cat, sen, rng.choice(["Onsite", "Hybrid", "Hybrid", "Remote"]),
                     smin if has_salary else None, int(smin * 1.35) if has_salary else None,
                     posted.isoformat(), 1 if (today - posted).days < 60 and rng.random() < 0.8 else 0))
    for i in range(1, candidates + 1):
        con.execute("INSERT INTO candidates VALUES (?,?,?,?,?)",
                    (i, "%s %s" % (rng.choice(FIRST), rng.choice(LAST)), rng.choice(CITIES), rng.randint(0, 15), rng.choice(SKILLS)))
    posted_on = dict(con.execute("SELECT id, posted_on FROM job_posts"))
    for i in range(1, applications + 1):
        jp = rng.randint(1, posts)
        applied = date.fromisoformat(posted_on[jp]) + timedelta(days=rng.randint(0, 45))
        con.execute("INSERT INTO applications VALUES (?,?,?,?,?)",
                    (i, jp, rng.randint(1, candidates), min(applied, today).isoformat(), _weighted(rng, STATUS)))
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print("built", build())
