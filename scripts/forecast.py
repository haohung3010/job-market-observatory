"""forecast.py -- forecast BC health-occupation job vacancies four quarters ahead, after testing each model on the past.

PURPOSE
  A planner reading the 2026 Q2 comparison will ask what comes next. This answers with the simplest models that can
  be checked: each is scored on quarters it did not see (rolling origin), the best is chosen by that score, and its
  range comes from its own past errors, not from a formula it was never tested against. Whether the series has a
  trend is measured separately, by a least-squares slope, because a flat model winning cannot show it.

CONFIG
  input   data/raw/14100444-eng.zip   (Statistics Canada 14-10-0444-01, quarterly, 2015 Q1 to 2026 Q2)
  output  data/forecast_backtest.csv  (every model's error at every origin and horizon)
          data/forecast.csv           (the chosen model's four quarters ahead, with the range that held for 4 in 5
                                       of its past forecasts)
          data/forecast_trend.csv     (least-squares slope per quarter over the window, with its standard error)
          data/vacancy_series.csv     (each series as read, every quarter from 2015, with its grade)
  series  GEO British Columbia, "Job vacancies", the NOC codes in SERIES below
  window  from 2020 Q4: the survey was not collected in 2020 Q2 and Q3, and the level after the gap is about twice
          the level before it, so the earlier quarters describe a different market

WORKFLOW
  1. read the series; refuse if any quarter in the window is suppressed (F, x, ..), graded E, or missing
  2. for each origin in the last BACKTEST quarters, fit every model on the quarters before it, forecast 1 to 4 ahead,
     and record the error against what Statistics Canada later published
  3. choose the model with the lowest mean absolute error over all horizons; print each horizon's winner too
  4. refit it on the whole window and forecast four quarters. The range at each horizon is the 80th percentile of
     its own absolute backtest errors, widened so it never narrows as the horizon grows
  5. fit a least-squares line to the window and to its last eight quarters, and report both slopes with their
     standard errors: a whole-window slope can come from a step early in the window that has since stopped

MODELS
  naive            the last quarter, carried forward
  seasonal naive   the same quarter one year earlier
  mean of 4        the mean of the last four quarters
  exp. smoothing   simple exponential smoothing; alpha chosen on the training quarters only, by grid
  drift            the last quarter plus the average quarterly change so far: the one model here that can carry a
                   trend, so a flat model beating it is evidence the backtest could have rejected

Q&A
  Q: why not ARIMA or Holt-Winters?   A: 23 quarters after the gap. A model with a seasonal term spends 4 of them on
     the season alone. The backtest is the test: a richer model belongs here only once it beats these on it.
  Q: why is the range not called an 80% interval?   A: at four quarters ahead it rests on five errors, from the model
     chosen for having small errors. It says how wide past misses were, not a probability (second read, 2026-10-06).
  Q: why widen the range by horizon?   A: with five to eight errors per horizon, the raw percentiles came out
     narrower at four quarters than at three in all three series, which no forecast can honestly claim.

PITFALLS
  * exit 0 ok . 3 a raw file is missing, a quarter in the window is suppressed, graded E or absent, or a control fails
  * REF_DATE 2026-04 is 2026 Q2 (the first month of the quarter)

NOTES
  [BOUND] the range rests on at most BACKTEST errors per horizon, fewer at longer horizons; it is not a probability
  statement about the world. [BOUND] the slope is ordinary least squares with no correction for autocorrelation,
  which would only widen its standard error: evidence of no measurable trend, not proof of none. [BOUND] Statistics
  Canada revises; a forecast is a statement about the vintage downloaded (data/MANIFEST.csv). [SEMANTICS] a vacancy is
  a job vacant on the first day of a month in the quarter: a stock, not a count of postings.
"""
import csv
import io
import math
import os
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ZIP = os.path.join(ROOT, "data", "raw", "14100444-eng.zip")
OUT_BT = os.path.join(ROOT, "data", "forecast_backtest.csv")
OUT_FC = os.path.join(ROOT, "data", "forecast.csv")
OUT_TR = os.path.join(ROOT, "data", "forecast_trend.csv")
OUT_SER = os.path.join(ROOT, "data", "vacancy_series.csv")
SERIES = ["3", "3130", "3310"]          # health occupations; nursing and allied professionals; assisting occupations
WINDOW_FROM = "2020-10"
BACKTEST = 8
HORIZON = 4


def quarter(ref):
    y, m = ref.split("-")
    return "%s Q%d" % (y, (int(m) - 1) // 3 + 1)


def next_ref(ref):
    y, m = int(ref[:4]), int(ref[5:7]) + 3
    if m > 12:
        y, m = y + 1, m - 12
    return "%d-%02d" % (y, m)


def read_series(code):
    tag = "[%s]" % code
    rows = {}
    with zipfile.ZipFile(ZIP) as z:
        f = io.TextIOWrapper(z.open("14100444.csv"), encoding="utf-8-sig")
        for r in csv.DictReader(f):
            if (r["GEO"] == "British Columbia" and r["Statistics"] == "Job vacancies"
                    and r["National Occupational Classification"].endswith(tag)):
                rows[r["REF_DATE"]] = (r["VALUE"], r["STATUS"])
    return rows


def ses(y, alpha):
    level = y[0]
    for v in y[1:]:
        level = alpha * v + (1 - alpha) * level
    return level


def ses_alpha(y):
    best = None
    for a in [i / 20 for i in range(1, 20)]:
        level, sse = y[0], 0.0
        for v in y[1:]:
            sse += (v - level) ** 2
            level = a * v + (1 - a) * level
        if best is None or sse < best[0]:
            best = (sse, a)
    return best[1]


def predict(model, y, h):
    if model == "naive":
        return y[-1]
    if model == "seasonal naive":
        return y[-4 + ((h - 1) % 4)] if len(y) >= 4 else None
    if model == "mean of 4":
        return sum(y[-4:]) / 4
    if model == "exp. smoothing":
        return ses(y, ses_alpha(y))
    if model == "drift":
        return y[-1] + h * (y[-1] - y[0]) / (len(y) - 1)
    raise ValueError(model)


MODELS = ["naive", "seasonal naive", "mean of 4", "exp. smoothing", "drift"]


def pct80(xs):
    xs = sorted(xs)
    if not xs:
        return None
    k = 0.8 * (len(xs) - 1)
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def ols_slope(y):
    n = len(y)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(y) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (v - my) for x, v in zip(xs, y)) / sxx
    a = my - b * mx
    resid = [v - (a + b * x) for x, v in zip(xs, y)]
    se = math.sqrt(sum(r * r for r in resid) / (n - 2) / sxx)
    return b, se


def main():
    if not os.path.exists(ZIP):
        print("CANNOT-MEASURE: %s missing; run scripts/fetch_sources.py" % ZIP)
        return 3
    # [CONTROL] the slope function must recover a known slope exactly, and read a flat series as zero
    b_known, _ = ols_slope([10 + 3 * i + (1 if i % 2 else -1) for i in range(12)])
    b_flat, _ = ols_slope([5, 7, 5, 7, 5, 7, 5, 7])
    print("[CONTROL] slope of a known +3 line with alternating noise %.3f (close to 3); of a flat series %.3f" % (
        b_known, b_flat))
    if abs(b_known - 3) > 0.2 or abs(b_flat) > 0.2:
        return 3
    bt_rows, fc_rows, tr_rows, ser_rows = [], [], [], []
    for code in SERIES:
        raw = read_series(code)
        ser_rows += [[code, quarter(k), k, raw[k][0], raw[k][1]] for k in sorted(raw)]
        refs = sorted(k for k in raw if k >= WINDOW_FROM)
        expect, r = [], WINDOW_FROM
        while r <= refs[-1]:
            expect.append(r)
            r = next_ref(r)
        bad = [(q, raw.get(q)) for q in expect if q not in raw or raw[q][0] == "" or raw[q][1] in ("E", "F", "x", "..")]
        if bad:
            print("CANNOT-MEASURE [%s]: suppressed, caution-graded or absent quarters in the window: %s" % (code, bad))
            return 3
        y = [float(raw[q][0]) for q in expect]
        n = len(y)
        errs = {m: {h: [] for h in range(1, HORIZON + 1)} for m in MODELS}
        for o in range(n - BACKTEST, n):
            train = y[:o]
            for m in MODELS:
                for h in range(1, HORIZON + 1):
                    if o + h - 1 >= n:
                        continue
                    p = predict(m, train, h)
                    actual = y[o + h - 1]
                    errs[m][h].append(abs(actual - p))
                    bt_rows.append([code, m, quarter(expect[o - 1]), h, quarter(expect[o + h - 1]),
                                    round(p), round(actual), round(p - actual)])
        mae = {m: sum(sum(v) for v in errs[m].values()) / sum(len(v) for v in errs[m].values()) for m in MODELS}
        best = min(MODELS, key=lambda m: mae[m])
        label = "BC, NOC [%s]" % code
        print("\n%s . window %s to %s (%d quarters) . backtest origins %d" % (label, quarter(expect[0]),
                                                                               quarter(expect[-1]), n, BACKTEST))
        for m in MODELS:
            print("  %-15s MAE %6.0f   (%.1f%% of the last quarter)%s" % (m, mae[m], 100 * mae[m] / y[-1],
                                                                          "   <- chosen" if m == best else ""))
        for h in range(1, HORIZON + 1):
            hm = {m: sum(errs[m][h]) / len(errs[m][h]) for m in MODELS}
            print("  horizon %d best: %s (MAE %.0f)" % (h, min(hm, key=hm.get), min(hm.values())))
        b, se = ols_slope(y)
        b8, se8 = ols_slope(y[-8:])
        tr_rows.append([code, quarter(expect[0]), quarter(expect[-1]), n, round(b, 1), round(se, 1),
                        round(b / se, 2), round(sum(y[-4:]) / 4), round(min(y)), round(max(y)),
                        round(sum(y[:4]) / 4), round(b8, 1), round(se8, 1), round(b8 / se8, 2)])
        print("  trend: least-squares slope %+.0f a quarter (standard error %.0f, t %.2f); range %.0f to %.0f" % (
            b, se, b / se, min(y), max(y)))
        print("         last 8 quarters %+.0f (standard error %.0f, t %.2f); mean of first 4 %.0f, of last 4 %.0f" % (
            b8, se8, b8 / se8, sum(y[:4]) / 4, sum(y[-4:]) / 4))
        ref, width = expect[-1], 0.0
        for h in range(1, HORIZON + 1):
            ref = next_ref(ref)
            p = predict(best, y, h)
            width = max(width, pct80(errs[best][h]))
            fc_rows.append([code, best, quarter(ref), h, round(p), round(max(p - width, 0)), round(p + width),
                            len(errs[best][h])])
            print("  %s  %6.0f   range that held for 4 in 5 past forecasts %6.0f to %6.0f   (%d errors)" % (
                quarter(ref), p, max(p - width, 0), p + width, len(errs[best][h])))
        # [CONTROL] the naive model's 1-step error at the last origin must equal the last quarter-on-quarter change
        ctl = abs(y[-1] - y[-2])
        got = errs["naive"][1][-1]
        print("  [CONTROL] naive 1-step error at the last origin %.0f == last quarter's change %.0f: %s" % (
            got, ctl, "PASS" if abs(got - ctl) < 1e-9 else "FAIL"))
        if abs(got - ctl) >= 1e-9:
            return 3
        widths = [r[6] - r[4] for r in fc_rows if r[0] == code]
        if any(b2 < a2 for a2, b2 in zip(widths, widths[1:])):
            print("  [CONTROL] FAIL: the range narrows with horizon")
            return 3
    with io.open(OUT_BT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["noc", "model", "origin", "horizon", "target", "predicted", "actual", "error"])
        w.writerows(bt_rows)
    with io.open(OUT_FC, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["noc", "model", "quarter", "horizon", "forecast", "low_4in5", "high_4in5", "errors_behind_range"])
        w.writerows(fc_rows)
    with io.open(OUT_TR, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["noc", "from", "to", "quarters", "slope_per_quarter", "standard_error", "t", "mean_last_4",
                    "min", "max", "mean_first_4", "slope_last_8", "standard_error_last_8", "t_last_8"])
        w.writerows(tr_rows)
    with io.open(OUT_SER, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["noc", "quarter", "ref_date", "vacancies", "grade"])
        w.writerows(ser_rows)
    print("\nWROTE %s (%d rows), %s (%d rows), %s (%d rows) and %s (%d rows)" % (
        OUT_BT, len(bt_rows), OUT_FC, len(fc_rows), OUT_TR, len(tr_rows), OUT_SER, len(ser_rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
