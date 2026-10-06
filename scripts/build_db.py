"""build_db.py -- load the quarter's Job Bank postings and Statistics Canada vacancies into one SQLite file.

PURPOSE
  The analysis is SQL. This script does the one thing SQL cannot: read the publishers' files (UTF-16 tab-separated
  postings, a zipped vacancy CSV) into two tables, untouched apart from column names. Every result after this point
  is a query in sql/ that anyone can read and re-run.

CONFIG
  input   data/raw/job-bank-open-data-all-job-postings-en-{apr,may,june}2026.csv   (fetch_sources.py)
          data/raw/14100444-eng.zip
  output  data/observatory.sqlite (git-ignored; rebuilt from the raw files)
  quarter REF_DATE 2026-04 in table 14-10-0444-01 is 2026 Q2

WORKFLOW
  1. create table postings: one row per Job Bank posting, the columns the analysis uses
  2. create table vacancies: the quarter's rows for Canada and every province, both statistics, with STATUS kept
  3. run every sql/*.sql file in name order; each may create views
  4. print row counts, with a control: the loaded postings must equal the file's data rows

Q&A
  Q: why keep STATUS?   A: Statistics Canada grades each estimate A to F and suppresses unreliable ones; a blank
     VALUE is "not published", never zero. The comparison must see that difference.
  Q: why not load every column?   A: the analysis uses 18 of 65; the rest stay in the raw files.

PITFALLS
  * the postings files are UTF-16 with a byte-order mark, tab-separated, despite the .csv extension
  * the column "Economic  Region" has two spaces in the publisher's header
  * exit 0 ok . 3 a raw file is missing or a count control fails

NOTES
  [BOUND] one quarter, 2026 Q2. [SEMANTICS] a Job Bank posting's month is its first posting date.
"""
import csv
import glob
import io
import os
import sqlite3
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(ROOT, "data", "raw")
DB = os.path.join(ROOT, "data", "observatory.sqlite")
MONTHS = ["apr2026", "may2026", "june2026"]
QUARTER_REF = "2026-04"
COLS = [("id", "WIC Job Location Snapshot ID"), ("title", "Job Title"), ("noc21", "NOC21 Code"),
        ("noc21_name", "NOC21 Code Name"), ("external", "External Indicator"),
        ("first_posting_date", "First Posting Date"), ("vacancy_count", "Vacancy Count"),
        ("education", "Education LOS"), ("experience", "Experience Level"), ("naics", "NAICS"),
        ("province", "Province/Territory"), ("city", "City"), ("economic_region", "Economic  Region"),
        ("employment_type", "Employment Type"), ("employment_term", "Employment Term"),
        ("salary_per", "Salary Per"), ("salary_min", "Salary Minimum"), ("salary_max", "Salary Maximum")]


def main():
    files = [os.path.join(RAW, "job-bank-open-data-all-job-postings-en-%s.csv" % m) for m in MONTHS]
    zpath = os.path.join(RAW, "14100444-eng.zip")
    missing = [p for p in files + [zpath] if not os.path.exists(p)]
    if missing:
        print("CANNOT-MEASURE: missing %s; run scripts/fetch_sources.py" % ", ".join(missing))
        return 3
    if os.path.exists(DB):
        os.replace(DB, DB + ".previous")
    con = sqlite3.connect(DB)
    con.execute("create table postings (%s, source_month text)" % ", ".join(c for c, _ in COLS))
    expected = 0
    for m, path in zip(MONTHS, files):
        with io.open(path, encoding="utf-16", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        expected += len(rows)
        con.executemany("insert into postings values (%s)" % ",".join("?" * (len(COLS) + 1)),
                        [[r[src] for _, src in COLS] + [m] for r in rows])
    con.execute("create table vacancies (ref_date text, geo text, noc text, statistic text, value real, status text)")
    with zipfile.ZipFile(zpath) as z:
        r = csv.DictReader(io.TextIOWrapper(z.open("14100444.csv"), encoding="utf-8-sig"))
        keep = [(x["REF_DATE"], x["GEO"], x["National Occupational Classification"], x["Statistics"],
                 float(x["VALUE"]) if x["VALUE"] else None, x["STATUS"])
                for x in r if x["REF_DATE"] == QUARTER_REF]
    con.executemany("insert into vacancies values (?,?,?,?,?,?)", keep)
    con.commit()
    for sql in sorted(glob.glob(os.path.join(ROOT, "sql", "*.sql"))):
        con.executescript(io.open(sql, encoding="utf-8").read())
        print("ran", os.path.relpath(sql, ROOT))
    got = con.execute("select count(*) from postings").fetchone()[0]
    print("postings loaded %d of %d data rows" % (got, expected))
    print("vacancy rows for %s: %d" % (QUARTER_REF, len(keep)))
    if got != expected or not keep:
        print("REFUSED: a load count control failed")
        return 3
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
