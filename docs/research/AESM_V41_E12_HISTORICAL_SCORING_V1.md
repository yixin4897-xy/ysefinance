# E12 Historical Scoring Research Experiment V1

**CANDIDATE_ONLY_PENDING_VALIDATION. Latest-revised historical data research,
not point-in-time information or a historical forecast.** No E12 weight or
parameter is approved. AEHI/AESI/ASFI composite scores remain HOLD; PR #8 remains
Draft. No production or composite score is created.

## Reproduce offline

From the checkout root, with the validated quarterly workbook supplied locally:

```powershell
python -B scripts/aehi_e12_scoring_research.py
python -B -m unittest discover -s tests -v
```

Default output:
`data-candidates/research/aehi-e12-quarterly-scoring-v1.json`.
The writer exclusively creates a new JSON and refuses to overwrite existing
results. To rerun after initial generation:

```powershell
python -B scripts/aehi_e12_scoring_research.py --output data-candidates/research/aehi-e12-quarterly-scoring-v1-rerun.json
```

These are deliberately new research paths. The original candidate importer,
tests, candidate JSON, source registry, pinned configuration, production data and
website files are unchanged. Python standard library only; no network, Excel,
third-party packages or installation needed. Tests use temporary fixture outputs.

## Source and isolation

Input: `research-inputs/e12/64010Appendix1a.xlsx`, ABS Track A **A3604511X**,
seasonally adjusted annual percentage change from corresponding quarter of the
previous year. The script reuses the existing E12 importer's OOXML reader,
exact metadata and coverage validation functions. It independently verifies the
validated source SHA-256 before extraction:

`71f8b078d9fc59b011ad1bf3ae77ce23c6dee7eb667fc276acf6821e9bc11f02`

The source is the previously validated [August 2026 ABS CPI release](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/aug-2026),
published 30 September 2026. Full provenance and excluded boundary blanks are
copied from the importer into the experiment. No fresh source verification is
implied by the offline run. Original download timestamp remains unknown.

Coverage: **174 valid quarters, 1983-Q1 through 2026-Q2**. The experiment never
opens `640106.xlsx`, never calls the two-track candidate builder, and never uses
monthly Track B observations. A local test asserts exactly one workbook read.
No interpolation, filling, averaging, annualisation or recomputation of published
annual inflation rates occurs. Internal gaps and invalid quarterly labels fail
closed. The 42 leading and four trailing blank source cells remain excluded.

## Scoring model and reproducibility

Inflation is in percent, so 3.6 means 3.6%, not 0.036.

```text
distance_pp = max(2 - inflation, 0, inflation - 3)
signed_deviation_pp = inflation - 2.5
score_k = max(0, 100 - k * distance_pp)
k = 10, 20, 30
```

The row-level `score` is the **provisional research benchmark k=20**. The `scores`
object stores all three slopes; neither field is a production score. Each row
also retains period, source date/cell, raw published inflation, midpoint deviation,
band distance and methodological flags. Decimal arithmetic avoids artificial
binary rounding at score-bin boundaries; raw published values remain unchanged.

Every result carries candidate status, false publication/weight/parameter and
real-time-backtest approval flags, null composite score, all three composite HOLD
statuses and source/implementation hashes. Generation timestamps differ between
runs; tests compare all other output fields exactly. The script hash identifies
the scoring implementation; existing importer code is versioned in Git.

Summaries use equal weight per observed quarter, population standard deviation
and linearly interpolated quantiles at (n-1)*p (type 7). Score-distribution bins
are [0,20), [20,40), [40,60), [60,80), [80,100), and exactly 100. Zero-score counts
are separately reported. All tied highest and lowest quarters are listed in JSON.
No statistical confidence intervals or independence claims are implied.

## Full-history findings

Annual inflation: mean **3.608%**, median **2.75%**, minimum **1.1% (2021-Q1)**,
maximum **10.6% (1983-Q1)**. Of 174 quarters, 29 are below 2%, 77 are within the
inclusive 2-3% band, and 68 exceed 3%.

| Statistic | k=10 | k=20 benchmark | k=30 |
|---|---:|---:|---:|
| Mean score | 88.76 | 78.71 | 73.08 |
| Median | 98.00 | 96.00 | 94.00 |
| 25th percentile | 87.25 | 74.50 | 61.75 |
| 75th percentile | 100.00 | 100.00 | 100.00 |
| Population standard deviation | 17.98 | 32.72 | 38.68 |
| Minimum | 24.00 | 0.00 | 0.00 |
| Maximum | 100.00 | 100.00 | 100.00 |
| Zero-score quarters | 0 | 11 | 28 |
| Score-100 quarters | 77 | 77 | 77 |

Score distribution (quarter counts; exact percentages also stored in JSON):

| Bin | k=10 | k=20 | k=30 |
|---|---:|---:|---:|
| [0,20) | 0 | 18 | 36 |
| [20,40) | 3 | 14 | 3 |
| [40,60) | 15 | 7 | 4 |
| [60,80) | 21 | 8 | 12 |
| [80,100) | 58 | 50 | 42 |
| Exactly 100 | 77 | 77 | 77 |

The 77 highest-score quarters are identical for all slopes: each is inside the
reference band. The first is 1992-Q2; the latest are 2025-Q1, Q2 and Q3. The JSON
lists all ties explicitly rather than choosing an arbitrary single best quarter.

Lowest quarters:

- k=10: **1983-Q1**, score 24 (10.6% inflation).
- k=20: score zero in **1983-Q1-Q3 and 1985-Q4 through 1987-Q3** (11 quarters).
- k=30: score zero in **1983-Q1 through 1984-Q2; 1985-Q2 through 1989-Q1;
  1990-Q1-Q4; 2022-Q4; 2023-Q1** (28 quarters).

Latest 2026-Q2: inflation **3.6%**, midpoint deviation **+1.1 pp**, band distance
**0.6 pp**, scores **94 / 88 / 82** for k=10/20/30.

## Subperiod and episode comparison

These windows are fixed in the script, overlap and are descriptive calendar
comparisons. They are not official episode dates, causal attribution, independent
samples or a partition whose counts should be summed. Inflation is annual, so
observations reflect price changes extending beyond window boundaries.

| Window | Quarters | Mean annual inflation % | Mean k=10 | Mean k=20 | Mean k=30 |
|---|---:|---:|---:|---:|---:|
| Pre-September 2001: 1983-Q1 to 2001-Q2 | 74 | 4.699 | 79.24 | 61.30 | 53.47 |
| September 2001 onward: 2001-Q3 to 2026-Q2 | 100 | 2.801 | 95.80 | 91.60 | 87.59 |
| Post-2011 change: 2011-Q3 to 2026-Q2 | 60 | 2.640 | 94.50 | 89.00 | 83.82 |
| Early high inflation: 1983-1990 | 32 | 7.494 | 55.06 | 16.63 | 1.59 |
| Disinflation: 1991-1993 | 12 | 3.192 | 93.50 | 87.00 | 80.50 |
| GFC window: 2007-2009 | 12 | 3.642 | 93.08 | 86.17 | 79.25 |
| Low inflation: 2016-2019 | 16 | 1.631 | 96.31 | 92.63 | 88.94 |
| Pandemic: 2020-2021 | 8 | 1.613 | 95.25 | 90.50 | 85.75 |
| Inflation surge: 2022-2023 | 8 | 5.388 | 76.13 | 52.25 | 30.75 |
| Recent: 2024-Q1 to 2026-Q2 | 10 | 3.370 | 95.80 | 91.60 | 87.40 |

The modern-history benchmark mean of 91.60 versus 61.30 before September 2001
mainly describes different inflation outcomes and regimes; it does not establish
that the model is better calibrated in either period. The September 2001 split
is motivated by the earlier ABS/RBA comparison, not an asserted ABS method break.

The GFC-window score cannot be interpreted as a rating of financial health.
Likewise, relatively high scores during 2016-2021 indicate closeness to the band,
not an absence of weak demand, unemployment or pandemic damage.

## Slope sensitivity and economic meaning

Outside the band and before clipping, an extra 0.1 pp of distance reduces the
score by 1, 2 or 3 points. Higher k expands dispersion while preserving ordering
by distance except where clipping creates ties. The 100-point plateau is
unchanged; it contains 44.25% of history under every slope.

Zero-score thresholds are distance >=10, >=5 and >=3.333... pp. On the high side,
these correspond to inflation >=13%, >=8% and >=6.333...%; on the low side,
<=-8%, <=-3% and <=-1.333...%. The sample has no low-side zero scores.

k=10 preserves differentiation across all observed inflation rates but imposes
only a small penalty for modest persistent undershoots. k=30 strongly penalises
the 2022-2023 surge but compresses severe episodes at zero. k=20 is an intermediate
research reference, not empirically optimal or approved. None measures persistence,
expectations, welfare costs or recession probability.

## Methodological limits and validation

- The official RBA target is headline CPI; applying its band to trimmed mean is
  a research assumption. Giving the whole band 100 is not a central-bank rating.
- Earlier source validation found 34 ABS/RBA annual differences through June
  2001, maximum 0.2 pp. Only ABS data are used here. Before clipping, a 0.2 pp
  difference can imply up to 2/4/6 score points for k=10/20/30; actual effects
  depend on distance and clipping. No historical RBA substitution is attempted.
- Historical precision changes, the 2011 seasonal-adjustment change and the
  treatment/backcasting of early history remain unresolved. ABS says December
  2025 source changes preserve quarterly continuity. See the existing E12
  candidate documentation for official methodology links and lineage caveats.
- Applying a modern target before inflation targeting is counterfactual; the
  earliest high-inflation years dominate full-history means and zero counts.
- Seasonal revisions may change past values, scores and band membership.
  This one August 2026 vintage cannot quantify revision sensitivity or historical
  operational performance. Release-date lags do not turn revised history into
  point-in-time data. Post-2011 is a sensitivity window, not proof of uniform methods.
- Annual rates overlap; quarterly observations and overlapping windows are
  serially dependent. No inferential significance, calibration fit, causal
  attribution or predictive validity is claimed.
- A price-stability score cannot summarise purchasing power, GDP, employment,
  housing stress or overall sustainability. Composite overlap/weight decisions
  remain out of scope. No alert thresholds or qualitative risk labels are assigned.

Verification: **38 tests passed with no skips**: seven scoring-research tests,
nine existing E12 tests, sixteen E04 tests and six existing API tests. Checks
cover exact formula values, clipping, signs, raw-value preservation, chronology,
frequency rejection, missingness, hash failures, one-workbook isolation, output
restrictions and exclusive creation. All 174 observations x three slopes agree
with an independent piecewise Decimal calculation; the saved experiment is
reproducible excluding its generation timestamp. No source/importer changes,
production configuration changes or composite updates were made.

## Completed robustness review

Retain k=10 and k=20 as parallel research candidates, without an approved preferred
slope. k=20 remains the provisional output-field convention; k=10 remains a
research sensitivity candidate, and k=30 remains an additional sensitivity case.
The independent review matched all 522 scores directly against workbook values.

All slopes put 77/174 quarters (44.25%) at 100. Floor shares are 0%, 6.32% and
16.09% for k=10/20/30. Distinct band distances number 44; distinct scores number
44/38/26. Larger slopes widen numerical dispersion but create additional tail
ties. k=20 has no zero scores from September 2001 onward, including 2022-2023.

Exploratory review criteria flag a floor share above 5% over all history or above
25% in a declared window of at least eight quarters. k=20 flags full history
(6.32%) and 1983-1990 (34.38%); k=10 flags neither. These are retrospective
information-retention conventions, not economic or policy thresholds. They do
not establish that k=20 is excessively punitive in economic terms.

A smooth positive distance transformation could remove finite floor clipping,
but would retain the flat-band ceiling and require new parameter choices. No
replacement is implemented or approved. Scores add a reference-scale presentation,
not new statistical information beyond inflation and signed deviations. Next
research steps are vintage sensitivity and comparison of one transparently
anchored non-clipped model. This review supports preservation in Draft PR #8,
not production use, parameter selection or composite integration.
