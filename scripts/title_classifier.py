"""title_classifier.py -- predict a posting's occupation (NOC 2021) from its job title, tested on titles it never saw.

PURPOSE
  Job Bank postings arrive coded to NOC 2021 by ESDC. Most other postings, including any board crawled directly,
  carry a title and no code, so they cannot be set beside the vacancy survey at all. This trains a text classifier on
  ESDC's coded titles and measures how far a title alone can carry the code, so an uncoded source can be placed on the
  same occupations, with a known error.

CONFIG
  input   data/observatory.sqlite, table postings (all of Canada, 2026 Q2; build_db.py)
  output  data/title_classifier_eval.csv  (accuracy by NOC level, weighting and subset)
  model   character n-grams (2 to 5, word-bounded) with TF-IDF, then a linear classifier (logistic regression)
  split   80/20 over DISTINCT normalised titles, seed 211: no title in the test set was seen in training

WORKFLOW
  1. normalise titles (lower case, collapse spaces); each distinct title gets its most frequent NOC as its label
  2. CEILING: the share of postings whose code equals their title's most frequent code. No title-only method can
     beat it, because the same title is coded differently in different postings
  3. split distinct titles 80/20; fit on train; predict test
  4. score at three levels (unit group 5 digits, minor group 4, major group 2), weighted by title and by posting,
     for all occupations and for health (NOC broad category 3); report top-3 accuracy at the unit group
  5. TWO BASELINES beside every score: the most frequent code in training, for every title; and a word-overlap
     lookup, where each test title takes the code most common among the training titles with the highest word
     overlap (Jaccard), ties to the lower code. The lookup is the honest comparison: index titles are often close
     variants of one another, so the model's gain is its margin over the lookup (second read, 2026-10-06). Of the
     lookups tried, this was the strongest, and it is the one used because a stronger baseline can only narrow the
     margin

Q&A
  Q: why split by distinct title?   A: the 158,668 postings hold about 10,500 distinct titles. A random split of
     postings would put "registered nurse" in train and test, and the score would measure memory, not the model.
  Q: why characters, not words?   A: titles are short and full of abbreviations and spelling variants (RN, R.N.,
     "aide"/"aid"); character n-grams survive those.

PITFALLS
  * exit 0 ok . 3 the database is missing, or a control fails
  * the posting-weighted score is dominated by a few very common titles; read both weightings

NOTES
  [SEMANTICS] MEASURED 2026-10-05: Job Bank's "Job Title" is ESDC's standardised title from the NOC index, not the
  employer's own wording. Of 10,541 distinct normalised titles, ONE carries more than one code, which is why the
  ceiling reads 100%. So this measures how well the model places index titles it has never seen; it does NOT measure
  free-text titles as employers write them. That needs a hand-coded sample of free-text titles, not built yet.
  [BOUND] one quarter of one feed, coded by one coder (ESDC); agreement with ESDC is the measure, not truth about the
  job. [BOUND] a title from another source may be written differently from Job Bank's; accuracy on a crawl is not
  measured here. [SEMANTICS] "accuracy" is the share of test items whose predicted code equals ESDC's code.
"""
import csv
import io
import os
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB = os.path.join(ROOT, "data", "observatory.sqlite")
OUT = os.path.join(ROOT, "data", "title_classifier_eval.csv")
SEED = 211


def norm(t):
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def main():
    if not os.path.exists(DB):
        print("CANNOT-MEASURE: %s missing; run scripts/build_db.py" % DB)
        return 3
    con = sqlite3.connect(DB)
    by_title = defaultdict(Counter)
    for title, noc in con.execute("select title, noc21 from postings where noc21 is not null and noc21 != ''"):
        t = norm(title)
        if t:
            by_title[t][noc] += 1
    titles = sorted(by_title)
    label = {t: by_title[t].most_common(1)[0][0] for t in titles}
    weight = {t: sum(by_title[t].values()) for t in titles}
    n_post = sum(weight.values())
    ceiling = sum(by_title[t][label[t]] for t in titles) / n_post
    print("POPULATION  %d postings . %d distinct titles . %d unit groups" % (
        n_post, len(titles), len(set(label.values()))))
    multi = sum(1 for t in titles if len(by_title[t]) > 1)
    print("CEILING     %.1f%% of postings carry their title's most frequent code (no title-only method can beat it)"
          % (100 * ceiling))
    print("            titles carrying more than one code: %d of %d. Near 0 means the titles are a coded index "
          "(ESDC's standard titles), not free text" % (multi, len(titles)))

    rnd = random.Random(SEED)
    shuffled = titles[:]
    rnd.shuffle(shuffled)
    cut = int(0.8 * len(shuffled))
    train, test = shuffled[:cut], shuffled[cut:]
    overlap = len(set(train) & set(test))
    print("SPLIT       %d train titles . %d test titles . [CONTROL] titles in both: %d (must be 0)" % (
        len(train), len(test), overlap))
    if overlap:
        return 3

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True)
    xtr = vec.fit_transform(train)
    ytr = [label[t] for t in train]
    clf = LogisticRegression(max_iter=2000, C=10.0)
    clf.fit(xtr, ytr)
    xte = vec.transform(test)
    proba = clf.predict_proba(xte)
    classes = clf.classes_
    top3 = [[classes[j] for j in row.argsort()[::-1][:3]] for row in proba]
    pred = [r[0] for r in top3]
    base = Counter(ytr).most_common(1)[0][0]

    def words(t):
        return set(re.findall(r"[a-z0-9]+", t))

    index = defaultdict(set)
    for j, t in enumerate(train):
        for w in words(t):
            index[w].add(j)
    train_words = [words(t) for t in train]
    nn = []
    for t in test:
        ws = words(t)
        overlap = Counter()
        for w in ws:
            for j in index.get(w, ()):
                overlap[j] += 1
        if not overlap:
            nn.append(base)
            continue
        sim = {j: overlap[j] / len(ws | train_words[j]) for j in overlap}
        top = max(sim.values())
        votes = Counter(label[train[j]] for j in sim if sim[j] == top)
        most = max(votes.values())
        nn.append(min(c for c in votes if votes[c] == most))

    rows = []

    def score(subset_name, keep):
        idx = [i for i, t in enumerate(test) if keep(t)]
        if not idx:
            return
        for level, k in (("unit group (5)", 5), ("minor group (4)", 4), ("major group (2)", 2)):
            for wname, wf in (("by title", lambda t: 1), ("by posting", lambda t: weight[t])):
                tot = sum(wf(test[i]) for i in idx)
                hit = sum(wf(test[i]) for i in idx if pred[i][:k] == label[test[i]][:k])
                bhit = sum(wf(test[i]) for i in idx if base[:k] == label[test[i]][:k])
                nhit = sum(wf(test[i]) for i in idx if nn[i][:k] == label[test[i]][:k])
                rows.append([subset_name, level, wname, len(idx), round(100 * hit / tot, 1),
                             round(100 * bhit / tot, 1), round(100 * nhit / tot, 1)])
        tot = len(idx)
        hit3 = sum(1 for i in idx if label[test[i]] in top3[i])
        rows.append([subset_name, "unit group (5), top 3", "by title", len(idx), round(100 * hit3 / tot, 1), "", ""])

    score("all occupations", lambda t: True)
    score("health (NOC 3)", lambda t: label[t].startswith("3"))

    print("\n%-16s %-22s %-11s %6s %9s %9s %9s" % ("subset", "level", "weighting", "titles", "accuracy",
                                                    "commonest", "lookup"))
    for r in rows:
        print("%-16s %-22s %-11s %6d %8s%% %8s%s %8s%s" % (r[0], r[1], r[2], r[3], r[4], r[5],
                                                        "%" if r[5] != "" else "", r[6], "%" if r[6] != "" else ""))

    # [CONTROL] the model must beat the baseline on the subset it is scored on; equal scores mean it learned nothing
    main_row = [r for r in rows if r[0] == "all occupations" and r[1] == "unit group (5)" and r[2] == "by title"][0]
    ok = main_row[4] > main_row[5] + 10
    print("\n[CONTROL] unit-group accuracy %.1f%% vs baseline %.1f%%: %s" % (main_row[4], main_row[5],
                                                                          "PASS" if ok else "FAIL"))
    print("[MARGIN] over the word-overlap lookup: %+.1f points (all), %+.1f (health)" % (
        main_row[4] - main_row[6],
        [r for r in rows if r[0] == "health (NOC 3)" and r[1] == "unit group (5)" and r[2] == "by title"][0][4]
        - [r for r in rows if r[0] == "health (NOC 3)" and r[1] == "unit group (5)" and r[2] == "by title"][0][6]))
    # [CONTROL] a title that cannot exist must not be predicted with high confidence
    p = clf.predict_proba(vec.transform(["qzxv jjkw"]))[0].max()
    print("[CONTROL] top probability for a nonsense title %.2f (expected low)" % p)

    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["subset", "level", "weighting", "test_titles", "accuracy_pct", "baseline_pct", "lookup_pct"])
        w.writerows(rows)
        w.writerow(["all occupations", "ceiling (title-only)", "by posting", len(titles), round(100 * ceiling, 1), "",
                    ""])
    print("WROTE %s (%d rows)" % (OUT, len(rows) + 1))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
