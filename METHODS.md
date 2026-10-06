# Methods and bounds

## The comparison

Each BC health occupation's share of Job Bank postings is set beside its share of Statistics Canada's job vacancies,
for 2026 Q2 (`sql/20_representativeness.sql`). The shares are within health occupations, NOC 2021 broad category 3.

* **Two levels:** major groups (two digits) and minor groups (four digits).
* **The unpublished row:** at each level, the vacancies Statistics Canada does not publish are shown as one
  "(unpublished)" row, with the postings in those same codes on the other side. At the minor level that row holds 425
  vacancies (4.1%) and 204 postings (12.9%). Physicians and veterinarians alone account for 124 of those postings.
* **Renormalised gaps:** each gap is also shown renormalised to published codes only.

## When a gap is claimed

The vacancy grade combines the coefficient of variation, non-response, imputation and expert judgement (the table's
note 1), so **no error bar can be derived from it.** The rule is therefore a gate on claims, not on rows:

| grade | shown | claimed |
|---|---|---|
| A to D | yes, with its grade | only if the gap has the same sign for all postings, direct postings and external postings, **and** every one of the three is at least 2 points from zero |
| E | yes | never; marked "caution, not cited" |
| F, `..`, `x` | as unmeasured | never; never read as zero |

* **The 2-point floor is a judgement, not a measurement.** It is set above the size of a group's own loose duplicates,
  which are worth about 1.6 points of share for the assisting occupations. A gap that keeps its sign but falls under
  the floor on any arm reads "consistent but small".
* **The floor is applied to unrounded values.** Medical technologists and technicians (3212) is the case on the line:
  its direct arm is -1.99, so it is not claimed.
* **Claimed at 2026 Q2:**
  * nursing and allied health professionals (3130), -26.2;
  * therapy and assessment professionals (3120), +12.0;
  * technical occupations in therapy and assessment (3210), -8.0.
* **For charts:** the unmeasured detail rows repeat the postings already counted in the "(unpublished)" row. Plot
  either the detail rows or the residual, never both, or posting shares sum past 100.

## What this comparison cannot carry

* **Stock against flow.** The survey counts the jobs vacant on the first day of each month (note 4): a stock.
  Postings are counted when first posted: a flow. The feed has no expiry date, so a posting's duration cannot be
  measured. **A gap therefore mixes two things:** how much of an occupation's hiring reaches Job Bank, and how long
  its vacancies stay open. A long-open vacancy counts in every month's stock but posts once. *[INFERRED from the two
  definitions, not measured.]*
* **The nursing gap is almost all registered nurses.**
  * NOC 31301: 3,490 vacancies (grade C) against 86 postings.
  * Whether nurses are under-posted on Job Bank or their vacancies stay open longer cannot be separated here.
* **Two coders.** Statistics Canada codes the vacancy survey; ESDC codes Job Bank postings. The table's note 9 warns
  that detailed levels are less reliable. Coding differences between the two are not measured.
* **External postings' `Vacancy Count` is always 1,** so positions are not comparable across the two channels.
  Shares here count postings, not positions.
* **Duplicates are a bracket, not a number:**
  * 0 by posting id;
  * 73 of 1,576 by same title, occupation, city, date and source.
* **One quarter,** 2026 Q2. Nothing here describes a trend.

## Requirements (`sql/35_requirements_tables.sql`)

* **Direct employer postings only.** External postings carry `NA` for education and experience, so the shares rest on
  543 of 1,576 postings. Each group's direct share is printed beside it, and it ranges from 27% to 82%.
* **The shares describe each group's direct postings, not the whole group.** Region is the one field both kinds of
  posting carry. `scripts/direct_vs_external.py` measures the distance between the two region mixes in every group with
  at least 20 of each, against 2,000 random splits of the same sizes: in most groups the direct postings come from a
  different mix of regions than any but a handful of random splits. That shows they are not a random half of the
  group; it cannot show whether their requirements differ, because external postings carry none.
* **Two ladders.** The publisher's eleven education values sit on one ladder in four bands; its seven experience
  values sit on another, by minimum months. A value no band names stays unbanded rather than falling into the highest
  band. **[CONTROL]** `ladder_check` counts values off the ladders and `requirements_check` counts direct postings left
  unbanded; `run_all.py` stops if either is above 0.
* **Groups with fewer than 20 direct postings are shown and marked "not cited".**

## Forecast (`scripts/forecast.py`)

* **The window starts at 2020 Q4.** The survey was not collected in 2020 Q2 and Q3, and the level after the gap is
  about twice the level before it.
* **Five models, each scored on quarters it had not seen:** naive, seasonal naive, the mean of the last four quarters,
  simple exponential smoothing, and drift, the one model that can carry a trend. Eight rolling origins, horizons 1 to
  4. The model with the lowest mean absolute error over all horizons is chosen; each horizon's winner is printed too.
* **Whether there is a trend is measured, not inferred from which model won.** A flat model winning cannot show that a
  series has no trend, so `forecast.py` fits a least-squares line to the window and reports its slope and standard
  error (`data/forecast_trend.csv`). The slope ignores autocorrelation, which would only widen its error: it is
  evidence of no measurable trend, not proof of none. One series tested does trend, and the report says so.
* **The range is the 80th percentile of the chosen model's own past errors** at each horizon, so it rests on 8, 7, 6
  and 5 errors, from the model picked for having small errors. It is widened so it never narrows as the horizon grows,
  and it is called what it is: the range past forecasts stayed within four times in five, not a probability.
* **The forecast refuses** if any quarter in the window is suppressed or graded E.

## Title classifier (`scripts/title_classifier.py`)

* **The task:** predict a posting's NOC 2021 unit group from its title alone, so postings from sources without a code
  can be set beside the vacancy survey.
* **The split is by distinct title** (80/20, seed 211): no title in the test set was seen in training. A split by
  posting would have tested memory, because 158,668 postings hold only 10,541 distinct titles.
* **Two baselines are printed beside every score.** The most frequent code is near zero by construction with about 500
  codes, so it shows little. The honest comparison is a **word-overlap lookup**: each test title takes the code most
  common among the training titles that share the most words with it. Of the lookups tried, the strongest is used,
  because a stronger baseline can only narrow the model's margin.
* **[SEMANTICS] Job Bank's titles are ESDC's standard titles,** not employers' own wording: only one title in 10,541
  carries more than one code. So the score says how well the model places index titles it has never seen. Accuracy
  on free-text titles needs a hand-coded sample, which is not built.

## Who checked it

The work was reviewed by a second AI agent, working independently of the one that built it. Every finding of the
review was reproduced before it was applied. The reviewer read the comparison method before it was published. It reproduced the view, and tested the nursing gap
across four posting variants: all postings, direct only, direct weighted by positions, and external only. It held at
26 to 27 points in every one. The unpublished row, the gate on claims, the 2-point floor and the bounds above all came
from that read, and the reviewer verified each revision after it was made.

The same reviewer then read the requirements tables, the forecast and the title classifier, rebuilt everything, and
reproduced every result. Its tests are now part of the code: the region test, the trend slope and the word-overlap
lookup. Its read also renamed the forecast's range, widened it by horizon, and made the monthly rebuild commit only
when every step passes.
