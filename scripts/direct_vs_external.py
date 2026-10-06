"""direct_vs_external.py -- test whether a group's direct postings are a fair sample of the group, on the one field both kinds carry.

PURPOSE
  Requirements (education, experience) exist only on direct employer postings. A requirement share is a property of
  the group only if its direct postings resemble the rest of it. The feed shares one field across direct and external
  postings: economic region. This measures how far apart the two region mixes are, and how often random splits of the
  same sizes are that far apart.

CONFIG
  input   data/observatory.sqlite, view bc_health (build_db.py)
  output  data/direct_vs_external.csv
  groups  minor groups with at least 20 direct and 20 external postings
  test    total-variation distance between the two region mixes; 2,000 random splits at the group's own sizes, seed 211

WORKFLOW
  1. for each group, count direct and external postings by economic region
  2. distance = half the sum of absolute differences in region shares
  3. permute the direct/external labels 2,000 times; count splits at least as far; report the 95th percentile
  4. [CONTROL] the same test on a random relabelling must not look extreme

Q&A
  Q: why region?   A: it is the only field both kinds of posting carry; employer and source are not in the feed.
  Q: what does a large distance prove?   A: that direct postings are not a random half of the group. It does not prove
     that their requirements differ, which no test can show because external postings carry no requirements.

PITFALLS
  * exit 0 ok . 3 the database is missing or the control fails

NOTES
  [BOUND] region only. [SEMANTICS] "fair sample" here means "indistinguishable by region from the rest of the group".
  Reproduces the reviewer's second-read test (2026-10-06); its figures are now generated here, not quoted.
"""
import csv
import io
import os
import random
import sqlite3
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB = os.path.join(ROOT, "data", "observatory.sqlite")
OUT = os.path.join(ROOT, "data", "direct_vs_external.csv")
PERMS = 2000
SEED = 211


def tvd(a, b):
    ca, cb = Counter(a), Counter(b)
    keys = set(ca) | set(cb)
    return 0.5 * sum(abs(ca[k] / len(a) - cb[k] / len(b)) for k in keys)


def test(direct, external, rnd):
    obs = tvd(direct, external)
    pool = direct + external
    nd = len(direct)
    dist = []
    for _ in range(PERMS):
        rnd.shuffle(pool)
        dist.append(tvd(pool[:nd], pool[nd:]))
    dist.sort()
    return obs, dist[int(0.95 * PERMS)], sum(1 for d in dist if d >= obs - 1e-12)


def main():
    if not os.path.exists(DB):
        print("CANNOT-MEASURE: %s missing; run scripts/build_db.py" % DB)
        return 3
    con = sqlite3.connect(DB)
    rows = con.execute("select substr(noc21, 1, 4), external, economic_region from bc_health").fetchall()
    groups = sorted({r[0] for r in rows})
    rnd = random.Random(SEED)
    out = []
    print("%-6s %8s %8s %9s %9s %12s" % ("group", "direct", "external", "distance", "random 95%", "as far"))
    for g in groups:
        d = [r[2] for r in rows if r[0] == g and r[1] == "0"]
        e = [r[2] for r in rows if r[0] == g and r[1] == "1"]
        if len(d) < 20 or len(e) < 20:
            continue
        obs, p95, far = test(d, e, rnd)
        out.append([g, len(d), len(e), round(obs, 2), round(p95, 2), far, PERMS])
        print("%-6s %8d %8d %9.2f %9.2f %7d of %d" % (g, len(d), len(e), obs, p95, far, PERMS))
    # [CONTROL] relabel one group at random and test again: it must not come out as far as almost every split
    g = out[0][0]
    pool = [r[2] for r in rows if r[0] == g]
    rnd.shuffle(pool)
    obs, p95, far = test(pool[:out[0][1]], pool[out[0][1]:], rnd)
    ok = far > PERMS * 0.05
    print("[CONTROL] group %s, labels shuffled: distance %.2f, %d of %d random splits as far (must be over 5%%): %s" % (
        g, obs, far, PERMS, "PASS" if ok else "FAIL"))
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["minor_group", "direct", "external", "distance", "random_95th", "random_as_far", "random_splits"])
        w.writerows(out)
    print("WROTE %s (%d rows)" % (OUT, len(out)))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
