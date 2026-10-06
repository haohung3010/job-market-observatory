"""run_all.py -- rebuild every table, model, chart and the report from the raw files, in order, and log the run.

PURPOSE
  The done-test says one command rebuilds everything. This is that command. It runs each step, stops at the first
  that fails, and appends one line per run to data/runs.jsonl: when it ran, the input digests it ran on, each step's
  exit code and time, and the headline numbers it produced. A reader can see every run and what changed between them.

CONFIG
  --fetch     run scripts/fetch_sources.py first (downloads about 290 MB); without it, the files in data/raw/ are used
  output      data/runs.jsonl (appended, never rewritten) . every file the steps write

WORKFLOW
  1. (--fetch) fetch_sources.py
  2. build_db.py -> forecast.py -> title_classifier.py -> direct_vs_external.py -> report.py; stop at the first
     non-zero exit. After build_db, stop if any education or experience value is off its ladder or any direct posting
     is unbanded (views ladder_check and requirements_check)
  3. read data/MANIFEST.csv for the input digests, and the headline numbers from the outputs
  4. append the run record; print it

Q&A
  Q: why a log in the repository?   A: a scheduled run that leaves no record cannot be audited. The log is small and
     shows that the pipeline ran, on which inputs, and whether the numbers moved.
  Q: why stop at the first failure?   A: a report built on a failed step would look current and be wrong.

PITFALLS
  * exit 0 every step passed . 3 a step failed (named in the log line and on screen)
  * the log records the MANIFEST digests, which describe the last fetch; without --fetch a run reuses those inputs

NOTES
  [BOUND] the log says the steps ran and passed their own controls; it does not re-check the controls itself.
"""
import csv
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG = os.path.join(ROOT, "data", "runs.jsonl")
STEPS = ["build_db.py", "forecast.py", "title_classifier.py", "direct_vs_external.py", "report.py"]


def requirements_controls():
    import sqlite3
    con = sqlite3.connect(os.path.join(ROOT, "data", "observatory.sqlite"))
    off = con.execute("select coalesce(sum(off_ladder), 0) from ladder_check").fetchone()[0]
    unb = con.execute("select coalesce(sum(education_unbanded + experience_unbanded), 0) from requirements_check"
                      ).fetchone()[0]
    print("[CONTROL] values off the ladders %d . direct postings unbanded %d (both must be 0)" % (off, unb))
    return off == 0 and unb == 0


def headline():
    out = {}
    try:
        import sqlite3
        con = sqlite3.connect(os.path.join(ROOT, "data", "observatory.sqlite"))
        out["bc_health_postings"] = con.execute("select count(*) from bc_health").fetchone()[0]
        out["claimed_gaps"] = {r[0]: r[1] for r in con.execute(
            "select code, gap_all from representativeness where claim = 'claimed' and level_digits = 4")}
    except Exception as e:  # recorded, never hidden
        out["db_error"] = str(e)
    try:
        fc = [r for r in csv.DictReader(io.open(os.path.join(ROOT, "data", "forecast.csv"), encoding="utf-8"))
              if r["noc"] == "3" and r["horizon"] == "1"][0]
        out["forecast_next"] = {"quarter": fc["quarter"], "forecast": int(fc["forecast"]),
                                "low_4in5": int(fc["low_4in5"]), "high_4in5": int(fc["high_4in5"])}
    except Exception as e:
        out["forecast_error"] = str(e)
    try:
        ev = [r for r in csv.DictReader(io.open(os.path.join(ROOT, "data", "title_classifier_eval.csv"),
                                                encoding="utf-8"))
              if r["subset"] == "all occupations" and r["level"] == "unit group (5)" and r["weighting"] == "by title"]
        out["classifier_unit_accuracy"] = float(ev[0]["accuracy_pct"])
        out["classifier_lookup_accuracy"] = float(ev[0]["lookup_pct"])
    except Exception as e:
        out["classifier_error"] = str(e)
    return out


def main():
    steps = (["fetch_sources.py"] if "--fetch" in sys.argv else []) + STEPS
    record = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "steps": []}
    rc_all = 0
    for step in steps:
        t0 = time.time()
        print("== %s" % step, flush=True)
        rc = subprocess.call([sys.executable, os.path.join(ROOT, "scripts", step)], cwd=ROOT)
        record["steps"].append({"step": step, "rc": rc, "seconds": round(time.time() - t0, 1)})
        if rc == 0 and step == "build_db.py" and not requirements_controls():
            rc = 3
            record["steps"][-1]["rc"] = rc
        if rc != 0:
            print("STOPPED: %s exited %d" % (step, rc))
            rc_all = 3
            break
    try:
        record["inputs"] = {r["file"]: r["sha256"][:12] for r in
                            csv.DictReader(io.open(os.path.join(ROOT, "data", "MANIFEST.csv"), encoding="utf-8"))}
    except OSError:
        record["inputs"] = "MANIFEST.csv missing"
    record["result"] = "passed" if rc_all == 0 else "failed"
    if rc_all == 0:
        record["headline"] = headline()
    line = json.dumps(record, ensure_ascii=False)
    with io.open(LOG, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    with io.open(LOG, encoding="utf-8") as f:
        last = f.read().rstrip("\n").split("\n")[-1]
    print("\nLOGGED (read back %s): %s" % ("MATCH" if last == line else "MISMATCH", line))
    return rc_all if last == line else 3


if __name__ == "__main__":
    sys.exit(main())
