"""fetch_sources.py -- download the open data this project is built from, into data/raw/, with a manifest.

PURPOSE
  Every number in this project regenerates from files anyone can download. This script fetches them and records
  each file's size and sha256 in data/MANIFEST.csv, so a reader can confirm they have the same inputs.

CONFIG
  --check     list what would be fetched; download nothing
  quarter     2026 Q2 (April to June 2026): the latest quarter of Statistics Canada table 14-10-0444-01 at build time
  sources     Job Bank job postings, monthly CSV (English), for the quarter's three months
              Statistics Canada table 14-10-0444-01, job vacancies by occupation (unit group), quarterly
              (licences in data/SOURCES.md)

WORKFLOW
  1. ask the open.canada.ca CKAN API for the Job Bank dataset and match each month's English file by its file name
  2. refuse (exit 3) if any month is not found, rather than fetch the wrong one
  3. download each file, read it back, refuse if the bytes differ
  4. write MANIFEST.csv: source, file, bytes, sha256, url

Q&A
  Q: why look the files up instead of hard-coding the URLs?   A: each month is its own resource with its own id; a
     typed URL silently fetches whatever sits there, a lookup by name fails loudly when a file is renamed.
  Q: why English only?   A: the French files carry the same postings; one language avoids counting them twice.

PITFALLS
  * the Job Bank files are UTF-16 and tab-separated, despite the .csv extension
  * the June file's name is "june2026", not "jun2026"; the month tokens below are the publisher's spelling
  * exit 0 ok . 2 usage . 3 a source could not be resolved or fetched

NOTES
  [BOUND] the CKAN resource list is read at run time; if the publisher retires a month, this refuses rather than
  substitutes. data/raw/ is git-ignored: the manifest, not the data, is what the repository carries.
"""
import csv
import hashlib
import io
import json
import os
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(ROOT, "data", "raw")
JOBBANK = "ea639e28-c0fc-48bf-b5dd-b8899bd43072"
CKAN = "https://open.canada.ca/data/api/action/package_show?id=" + JOBBANK
VACANCIES = "https://www150.statcan.gc.ca/n1/tbl/csv/14100444-eng.zip"
QUARTER_MONTHS = {"2026Q2": ["apr2026", "may2026", "june2026"]}
UA = {"User-Agent": "job-market-observatory (open-data portfolio project)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


def month_urls(months):
    """{month token: url} for the English monthly files, matched on the resource's file name."""
    pkg = json.loads(get(CKAN))["result"]
    found = {}
    for res in pkg["resources"]:
        url = res.get("url", "")
        name = url.rsplit("/", 1)[-1].lower()
        if not name.startswith("job-bank-open-data-all-job-postings-en-"):
            continue
        for m in months:
            if name.endswith("-" + m + ".csv"):
                found[m] = url
    return found


def main(argv):
    if any(a != "--check" for a in argv):
        print("usage: fetch_sources.py [--check]")
        return 2
    months = QUARTER_MONTHS["2026Q2"]
    urls = month_urls(months)
    missing = [m for m in months if m not in urls]
    for m in months:
        print("%-10s %s" % (m, urls.get(m, "NOT FOUND")))
    print("%-10s %s" % ("vacancies", VACANCIES))
    if missing:
        print("CANNOT-MEASURE: no English Job Bank file found for %s" % ", ".join(missing))
        return 3
    if "--check" in argv:
        return 0
    os.makedirs(RAW, exist_ok=True)
    rows = []
    for label, url in [(m, urls[m]) for m in months] + [("vacancies", VACANCIES)]:
        path = os.path.join(RAW, url.rsplit("/", 1)[-1])
        data = get(url)
        open(path, "wb").write(data)
        back = open(path, "rb").read()
        if back != data:
            print("REFUSED: %s did not read back identical" % path)
            return 3
        rows.append({"source": label, "file": os.path.basename(path), "bytes": len(back),
                     "sha256": hashlib.sha256(back).hexdigest(), "url": url})
        print("fetched %-10s %10d bytes  sha256 %s" % (label, len(back), rows[-1]["sha256"][:16]))
    with io.open(os.path.join(ROOT, "data", "MANIFEST.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source", "file", "bytes", "sha256", "url"])
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
