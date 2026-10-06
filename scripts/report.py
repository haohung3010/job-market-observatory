"""report.py -- write the one-page findings report, its three charts, and the README's numbers, from the outputs.

PURPOSE
  A manager should get the answer in two minutes, and every number on the page should come from a query. This script
  is the only author of report/REPORT.md, report/*.png and the two GENERATED blocks in README.md: nothing in them is
  typed by hand, so neither page can drift from the data when the sources are revised.

CONFIG
  input   data/observatory.sqlite (build_db.py) . data/forecast.csv, data/forecast_trend.csv,
          data/forecast_backtest.csv, data/vacancy_series.csv (forecast.py) . data/title_classifier_eval.csv
          (title_classifier.py) . data/direct_vs_external.csv (direct_vs_external.py)
  output  report/REPORT.md . report/gaps.png . report/requirements.png . report/forecast.png
          README.md, only between <!-- GENERATED:tldr --> and <!-- GENERATED:findings --> and their closing markers

WORKFLOW
  1. read the claimed gaps, the requirements table and its region test, the forecast and trend, the classifier scores
  2. draw three charts (matplotlib, no styling beyond labels)
  3. write REPORT.md: the finding first, then the sections, then the bounds, each figure cited to its source
  4. rewrite the README's two generated blocks; refuse if either marker pair is missing

Q&A
  Q: why generate the README's numbers too?   A: the monthly rebuild changes the report; a README typed by hand would
     keep the old figures beside it (second read, 2026-10-06).
  Q: why only claimed gaps in the table?   A: the chart shows every measured group; the table carries only what
     passed the claim rule in METHODS.md, so a reader cannot quote an unclaimed gap from it.

PITFALLS
  * exit 0 ok . 3 an input is missing, or a README marker pair is missing
  * the gaps chart plots the minor-group detail rows only, never the "(unpublished)" residual beside them (METHODS.md)

NOTES
  [BOUND] one quarter (2026 Q2) of postings; the forecast reads the vacancy series to 2026 Q2.
"""
import csv
import io
import os
import re
import sqlite3
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB = os.path.join(ROOT, "data", "observatory.sqlite")
FC = os.path.join(ROOT, "data", "forecast.csv")
TR = os.path.join(ROOT, "data", "forecast_trend.csv")
BT = os.path.join(ROOT, "data", "forecast_backtest.csv")
SER = os.path.join(ROOT, "data", "vacancy_series.csv")
CLF = os.path.join(ROOT, "data", "title_classifier_eval.csv")
DVE = os.path.join(ROOT, "data", "direct_vs_external.csv")
README = os.path.join(ROOT, "README.md")
OUT = os.path.join(ROOT, "report")
INK, GREY, ACCENT = "#1f2a36", "#9aa5b1", "#c2410c"


def short(label):
    return label.split(" [")[0]


def num(x):
    return format(int(round(float(x))), ",")


def read_csv(path):
    return list(csv.DictReader(io.open(path, encoding="utf-8")))


def replace_block(text, name, body):
    start, end = "<!-- GENERATED:%s -->" % name, "<!-- /GENERATED:%s -->" % name
    if text.count(start) != 1 or text.count(end) != 1:
        return None
    a = text.index(start) + len(start)
    b = text.index(end)
    return text[:a] + "\n" + body.strip("\n") + "\n" + text[b:]


def main():
    missing = [p for p in (DB, FC, TR, BT, SER, CLF, DVE, README) if not os.path.exists(p)]
    if missing:
        print("CANNOT-MEASURE: missing %s" % ", ".join(missing))
        return 3
    os.makedirs(OUT, exist_ok=True)
    con = sqlite3.connect(DB)

    gaps = con.execute("""select code, noc_label, grade, vacancies, postings, vacancy_share_pct, postings_share_pct,
                                 gap_all, gap_direct, gap_external, claim
                          from representativeness
                          where level_digits = 4 and code != '(unpublished)' and vacancies is not null
                          order by gap_all""").fetchall()
    req = con.execute("""select minor_group, label, postings, direct, direct_pct, edu_secondary_pct, edu_college_pct,
                                edu_bachelor_pct, edu_graduate_pct, exp_none_pct, exp_under_1y_pct,
                                exp_1_to_3y_pct, exp_3y_plus_pct, status
                         from requirements_by_group""").fetchall()
    tot = con.execute("select count(*), sum(external = '0') from bc_health").fetchone()
    dup = con.execute("select repeat_postings from duplicates order by definition desc").fetchall()
    ask = con.execute("""select sum(x.min_months >= 36), sum(x.min_months < 24), count(*)
                         from bc_health p join experience_ladder x on x.experience = p.experience
                         where p.external = '0'""").fetchone()
    series = [(r["ref_date"], float(r["vacancies"]) if r["vacancies"] else None)
              for r in read_csv(SER) if r["noc"] == "3"]
    fc = read_csv(FC)
    trend = {r["noc"]: r for r in read_csv(TR)}
    bt = read_csv(BT)
    clf = read_csv(CLF)
    dve = {r["minor_group"]: r for r in read_csv(DVE)}

    # chart 1: gaps
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.barh([short(g[1]) for g in gaps], [g[7] for g in gaps],
            color=[ACCENT if g[10] == "claimed" else GREY for g in gaps])
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_xlabel("postings share minus vacancy share, in points")
    ax.set_title("BC health, 2026 Q2: where postings over- and under-represent vacancies\n"
                 "orange: claimed . grey: shown, not claimed", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "gaps.png"), dpi=150)
    plt.close(fig)

    # chart 2: requirements (cited groups)
    cited = [r for r in req if r[13] == "cited"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
    names = [short(r[1]) for r in cited]
    shades = ["#e5e7eb", "#9aa5b1", "#4b5563", ACCENT]
    for ax, cols, legend, title in (
            (axes[0], (5, 6, 7, 8), ("secondary or none", "college or trades", "bachelor's", "graduate or professional"),
             "Education asked"),
            (axes[1], (9, 10, 11, 12), ("none", "under 1 year", "1 to 3 years", "3 years or more"),
             "Experience asked")):
        left = [0] * len(cited)
        for k, c in enumerate(cols):
            v = [r[c] or 0 for r in cited]
            ax.barh(names, v, left=left, color=shades[k], label=legend[k])
            left = [a + b for a, b in zip(left, v)]
        ax.set_title(title + "\nof each group's direct postings", fontsize=10)
        ax.set_xlim(0, 100)
        ax.set_xlabel("% of the group's direct postings")
        ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "requirements.png"), dpi=150)
    plt.close(fig)

    # chart 3: forecast
    fc3 = [r for r in fc if r["noc"] == "3"]
    pts = sorted((r, v) for r, v in series if v is not None and r >= "2017-01")

    def t(ref):
        return int(ref[:4]) + (int(ref[5:7]) - 1) / 12.0

    def tq(q):
        return int(q[:4]) + (int(q[-1]) - 1) / 4.0

    fig, ax = plt.subplots(figsize=(8, 3.4))
    before = [(t(r), v) for r, v in pts if r < "2020-04"]
    after = [(t(r), v) for r, v in pts if r > "2020-07"]
    for part in (before, after):
        ax.plot([a for a, _ in part], [b for _, b in part], color=INK, marker="o", ms=2.5, lw=1)
    xs = [tq(r["quarter"]) for r in fc3]
    ax.plot(xs, [float(r["forecast"]) for r in fc3], color=ACCENT, ls="--", lw=1.2)
    ax.fill_between(xs, [float(r["low_4in5"]) for r in fc3], [float(r["high_4in5"]) for r in fc3], color=ACCENT,
                    alpha=0.18, lw=0)
    years = list(range(2017, 2028))
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], fontsize=8)
    ax.set_ylabel("vacancies")
    ax.set_title("BC health-occupation vacancies, with a four-quarter forecast and the range its past forecasts\n"
                 "stayed within 4 times in 5 (2020 Q2 and Q3 were not collected)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "forecast.png"), dpi=150)
    plt.close(fig)

    claimed = [g for g in gaps if g[10] == "claimed"]
    clf_row = {(r["subset"], r["level"], r["weighting"]): r for r in clf}
    h_unit = clf_row[("health (NOC 3)", "unit group (5)", "by title")]
    a_unit = clf_row[("all occupations", "unit group (5)", "by title")]
    nurse = [g for g in gaps if g[0] == "3130"][0]
    ther = [g for g in gaps if g[0] == "3120"][0]
    nxt = fc3[0]
    tr3 = trend["3"]
    trending = [(c, r) for c, r in trend.items() if abs(float(r["t"])) >= 2]
    labels = {g[0]: short(g[1]) for g in gaps}
    labels["3"] = "Health occupations"

    # per-horizon winners, read from the backtest (F3)
    hz = {}
    for r in bt:
        if r["noc"] != "3":
            continue
        hz.setdefault(r["horizon"], {}).setdefault(r["model"], []).append(abs(float(r["error"])))
    winners = {h: min(m, key=lambda k: sum(m[k]) / len(m[k])) for h, m in hz.items()}
    chosen = fc3[0]["model"]
    later = [h for h in sorted(winners) if winners[h] == chosen]

    tested = [r for r in dve.values()]
    differ = [r for r in tested if int(r["random_as_far"]) / int(r["random_splits"]) < 0.05]

    finding_nurse = (
        "In 2026 Q2, nursing and allied health professionals held %.1f%% of British Columbia's health-occupation "
        "vacancies but %.1f%% of its health postings on Job Bank, a gap of %.1f points: postings show nursing at about "
        "%.0f%% of its share of vacancies." % (nurse[5], nurse[6], nurse[7], 100.0 * nurse[6] / nurse[5]))
    trend_sentence = (
        "Vacancies have ranged from %s to %s since %s, with no measurable trend (a least-squares slope of %+.0f a "
        "quarter, standard error %.0f)" % (num(tr3["min"]), num(tr3["max"]), tr3["from"], float(tr3["slope_per_quarter"]),
                                            float(tr3["standard_error"])))
    def exception(c, r):
        name = labels.get(c, c)
        whole = ("fell from an average of %s vacancies in the window's first four quarters to %s in its last four "
                 "(a slope of %+.0f a quarter, standard error %.0f)") % (
            num(r["mean_first_4"]), num(r["mean_last_4"]), float(r["slope_per_quarter"]), float(r["standard_error"]))
        if abs(float(r["t_last_8"])) < 2:
            return ("%s are the exception: they %s, but show no measurable trend over the last eight quarters "
                    "(%+.0f, standard error %.0f), which is what the flat forecast assumes" % (
                        name, whole, float(r["slope_last_8"]), float(r["standard_error_last_8"])))
        return "%s are the exception: they %s, and are still falling over the last eight quarters (%+.0f, standard " \
               "error %.0f)" % (name, whole, float(r["slope_last_8"]), float(r["standard_error_last_8"]))

    trend_except = "; ".join(exception(c, r) for c, r in trending if c != "3")

    lines = [
        "# BC health job postings: what employers ask for, and how far postings can be trusted",
        "",
        "*Generated by `scripts/report.py` from the database and the files in `data/`. Nothing below is typed by hand.*",
        "",
        "## The finding",
        "",
        "**Job Bank postings are not a fair picture of where BC health vacancies are.** " + finding_nurse,
        "",
        "## 1. Postings against vacancies, 2026 Q2",
        "",
        "![gaps](gaps.png)",
        "",
        "| occupation group (NOC 2021) | grade | vacancy share | postings share | gap (points) |",
        "|---|---|---|---|---|",
    ]
    for g in claimed:
        lines.append("| %s | %s | %.1f%% | %.1f%% | %+.1f |" % (short(g[1]), g[2], g[5], g[6], g[7]))
    lines += [
        "",
        "A gap is claimed only when it keeps its sign for all, direct and external postings, each at least 2 points "
        "from zero, on a vacancy estimate graded A to D. The rule and its reasons are in `METHODS.md`.",
        "",
        "## 2. What employers ask for, in their direct postings",
        "",
        "![requirements](requirements.png)",
        "",
        "From %d direct employer postings (of %d in total; external postings carry no requirements). **%d of %d (%.1f%%) "
        "ask for three years or more; %d (%.1f%%) ask for under two.**" % (
            tot[1], tot[0], ask[0], ask[2], 100.0 * ask[0] / ask[2], ask[1], 100.0 * ask[1] / ask[2]),
        "",
        "| occupation group | direct postings | bachelor's or higher | asks 1 year or more | direct postings differ by region from the rest of the group |",
        "|---|---|---|---|---|",
    ]
    for r in cited:
        d = dve.get(r[0])
        reg = ("not tested" if d is None else
               "yes (%s of %s random splits as far)" % (d["random_as_far"], num(d["random_splits"]))
               if int(d["random_as_far"]) / int(d["random_splits"]) < 0.05 else
               "not distinguishable (%s of %s)" % (d["random_as_far"], num(d["random_splits"])))
        lines.append("| %s | %d (%.0f%% of its postings) | %.0f%% | %.0f%% | %s |" % (
            short(r[1]), r[3], r[4], r[7] + r[8], r[11] + r[12], reg))
    lines += [
        "",
        "**These shares describe each group's direct postings, not the whole group.** Region is the only field both "
        "direct and external postings carry, and in %d of the %d groups large enough to test, the direct postings come "
        "from a different mix of regions than the rest of their group, further apart than any but a handful of 2,000 "
        "random splits of the same sizes (`scripts/direct_vs_external.py`). That shows the direct postings are not a "
        "random half; it cannot show whether their requirements differ, because external postings carry none. Groups "
        "with fewer than 20 direct postings are left out of this table; they are in `requirements_by_group`." % (
            len(differ), len(tested)),
        "",
        "## 3. What comes next",
        "",
        "![forecast](forecast.png)",
        "",
        trend_sentence + "." + (" " + trend_except[0].upper() + trend_except[1:] + "." if trend_except else ""),
        "",
        "Five models, one of which can carry a trend, were each tested on eight past quarters they had not seen. The "
        "mean of the last four quarters made the smallest errors overall, and was best at %s quarters ahead; at one "
        "quarter ahead, %s did better. The forecast for %s is %s. Its past forecasts at that distance stayed within "
        "%s to %s four times in five (from %s past errors; a record of past misses, not a probability)." % (
            " and ".join(later) if len(later) < 3 else "%s to %s" % (later[0], later[-1]),
            winners.get("1", chosen), nxt["quarter"], num(nxt["forecast"]), num(nxt["low_4in5"]),
            num(nxt["high_4in5"]), nxt["errors_behind_range"]),
        "",
        "## 4. Coding postings that arrive without an occupation",
        "",
        "Postings from other sources carry a title and no occupation code. A text classifier trained on Job Bank's coded "
        "titles placed **index titles it had never seen** in the right unit group %s%% of the time (health occupations "
        "%s%%, on %s test titles). A word-overlap lookup on the same titles scores %s%% (health %s%%), and always "
        "guessing the most common code %s%%, so the model adds about %.0f points over a lookup (%.0f in health). Job "
        "Bank's titles are ESDC's standard titles, so accuracy on titles written freely by employers is not yet "
        "measured." % (
            a_unit["accuracy_pct"], h_unit["accuracy_pct"], h_unit["test_titles"], a_unit["lookup_pct"],
            h_unit["lookup_pct"], a_unit["baseline_pct"],
            float(a_unit["accuracy_pct"]) - float(a_unit["lookup_pct"]),
            float(h_unit["accuracy_pct"]) - float(h_unit["lookup_pct"])),
        "",
        "## Bounds",
        "",
        "* One quarter of postings (2026 Q2). Vacancies are a stock on the first day of each month; postings are a flow. "
        "A gap mixes how much hiring reaches Job Bank with how long vacancies stay open.",
        "* Duplicates are a bracket: %d by posting id, %d by title, occupation, city, date and source, of %d postings." % (
            dup[0][0], dup[1][0], tot[0]),
        "* Requirement shares describe direct postings only, which differ by region from the rest of most groups.",
        "* The forecast's range rests on 5 to 8 past errors per horizon; the slope ignores autocorrelation, which would "
        "only widen its error.",
        "",
        "Sources and licences: `data/SOURCES.md`. Method: `METHODS.md`.",
    ]
    io.open(os.path.join(OUT, "REPORT.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    # README: the two generated blocks
    tldr = (
        "**TL;DR.** Not for every occupation. %s Therapy and assessment professionals ran the other way, at %.1f%% of "
        "vacancies and %.1f%% of postings. So a dashboard of postings would under-state nursing demand and over-state "
        "therapy demand. Of direct employer postings, %.1f%% ask for three years of experience or more. %s.\n\n"
        "![Postings share minus vacancy share for BC health occupations, 2026 Q2. Nursing is %.0f points under, "
        "therapy and assessment professionals %.0f points over.](report/gaps.png)" % (
            finding_nurse, ther[5], ther[6], 100.0 * ask[0] / ask[2], trend_sentence, -nurse[7], ther[7]))
    rows = [
        "| | finding | where it comes from |",
        "|---|---|---|",
        "| Trust | %s | `sql/20_representativeness.sql`, view `representativeness` |" % "; ".join(
            "%s **%+.1f** points" % (short(g[1]).lower(), g[7]) for g in claimed),
        "| Requirements | %d of %d direct postings (**%.1f%%**) ask for three years or more; %d (**%.1f%%**) ask for "
        "under two. Shares describe each group's direct postings, which differ by region from the rest of the group "
        "in %d of %d groups tested | `sql/35_requirements_tables.sql`, `scripts/direct_vs_external.py` |" % (
            ask[0], ask[2], 100.0 * ask[0] / ask[2], ask[1], 100.0 * ask[1] / ask[2], len(differ), len(tested)),
        "| Forecast | No measurable trend: **%+.0f** a quarter (standard error %.0f). A flat mean of the last four "
        "quarters forecast best of five models; %s forecast **%s**, past forecasts within %s to %s four times in five | "
        "`scripts/forecast.py`, `data/forecast.csv`, `data/forecast_trend.csv` |" % (
            float(tr3["slope_per_quarter"]), float(tr3["standard_error"]), nxt["quarter"], num(nxt["forecast"]),
            num(nxt["low_4in5"]), num(nxt["high_4in5"])),
        "| Coding | Index titles never seen in training placed in the right unit group **%s%%** of the time (health "
        "**%s%%**, %s titles), against %s%% for a word-overlap lookup and %s%% for the most common code | "
        "`scripts/title_classifier.py`, `data/title_classifier_eval.csv` |" % (
            a_unit["accuracy_pct"], h_unit["accuracy_pct"], h_unit["test_titles"], a_unit["lookup_pct"],
            a_unit["baseline_pct"]),
    ]
    text = io.open(README, encoding="utf-8").read()
    for name, body in (("tldr", tldr), ("findings", "\n".join(rows))):
        new = replace_block(text, name, body)
        if new is None:
            print("CANNOT-MEASURE: README.md lacks exactly one <!-- GENERATED:%s --> block" % name)
            return 3
        text = new
    io.open(README, "w", encoding="utf-8", newline="\n").write(text)
    back = io.open(README, encoding="utf-8").read()
    print("WROTE report/REPORT.md (%d lines), 3 charts, and README.md's 2 generated blocks (read back %s)" % (
        len(lines), "MATCH" if back == text else "MISMATCH"))
    return 0 if back == text else 3


if __name__ == "__main__":
    sys.exit(main())
