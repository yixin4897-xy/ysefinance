# E12 Trimmed Mean Inflation Candidate V1

Status: **CANDIDATE_ONLY_PENDING_VALIDATION**. AEHI, AESI and ASFI composite
scores remain **HOLD**. Neither track is production pinned or publication approved.
PR #8 remains Draft; this implementation does not change PR state.

## Independent source contracts

| Track | ABS Series ID | Frequency | Workbook / original column | Annual observation coverage |
|---|---|---|---|---|
| A | A3604511X | Quarterly | 64010Appendix1a.xlsx / I | 1983-Q1 to 2026-Q2: 174 |
| B | A130400382R | Monthly | 640106.xlsx / AH | 2025-04 to 2026-08: 17 |

Both are Australia trimmed mean, seasonally adjusted, units `Percent`, data type
`PERCENT`. A is percentage change from corresponding quarter of previous year;
B is percentage change from corresponding month of previous year. Both latest
published annual values are 3.6%, for different reference periods.

All sheets are `Index`, `Data1`, `Enquiries`. Metadata is in Data1 rows 1-10;
series selection uses exact row-10 IDs rather than fixed column positions.
The Index table titles and metadata labels are checked. Dates are Excel 1900
serials displayed as `mmm\-yyyy`, on the first day of the reference month.
Quarterly labels use March, June, September and December; canonical output
periods are `YYYY-Qn` and `YYYY-MM`, respectively. Output retains the raw reference
date and source cell. Values are copied as published percentages, without
annualisation, rounding, index recomputation or division by 100.

A valid cells: I53:I226, with 42 leading blanks and four trailing placeholders
(2026-Q3 through 2027-Q2). B valid cells: AH23:AH39, with 12 leading blanks
(April 2024 through March 2025). Neither has internal gaps. The monthly index
starts April 2024; annual changes require a year of history. Future quarterly
grid dates are not forecasts. Blank observations never become zero. Zero and
negative finite annual inflation values are valid numerical observations.

## Provenance and vintage

Original files stay outside Git under `research-inputs/e12/`; provenance in JSON
uses repository-relative forward-slash paths. Both files were independently
verified byte-for-byte against the [ABS August 2026 release](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/aug-2026),
published 30 September 2026, during the preceding local validation.
Original download timestamps are unknown and remain null; generation time is
not represented as source download time.

| File | SHA-256 |
|---|---|
| 64010Appendix1a.xlsx | 71f8b078d9fc59b011ad1bf3ae77ce23c6dee7eb667fc276acf6821e9bc11f02 |
| 640106.xlsx | 1df9e8b27beb31c8ab3ed36ee8f9d309fb0e0e61706d48df17fcf766ce44f01a |

V1 deliberately pins these validated **research snapshot hashes**, not production
series. Changed bytes or a later release fail closed and require a new source
review and contract update. The importer is offline and does not reverify URLs.

## Methodology and unresolved historical questions

A and B are separate methodologies, not primary and fallback versions of one
series. There is no splicing, forward fill, substitution, averaging, alignment
intersection or shared observation array. A quarterly measure derived from
monthly indexes would require a separately reviewed third contract.

[ABS methodology history](https://www.abs.gov.au/statistics/research/underlying-inflation-measures-explaining-trimmed-mean-and-weighted-median)
records ABS responsibility from 2007 and improved seasonal adjustment in 2011.
The entire 1983 onward history must not be labelled methodologically unchanged.
Historical [RBA documentation, Appendix A](https://www.rba.gov.au/publications/confs/2009/pdf/conf-vol-2009.pdf)
records a September 2002 precision-related break. How these changes and any
backcasting affect the current extended ABS series remains unresolved.

The [ABS quarterly explanatory note](https://www.abs.gov.au/statistics/detailed-methodology-information/information-papers/quarterly-trimmed-mean-pre-october-2025-compilation-basis-explanatory-note)
confirms pre-October 2025 collection patterns continue through at least June
quarter 2027. New childcare, long day care and insurance sources enter from
December quarter 2025; ABS says their treatment preserves quarterly continuity.
This transition does not establish unchanged methods across all earlier decades.
Monthly collection, trimming and evolving seasonal factors differ from quarterly
methods. The monthly annual history is short and needs revision-sensitivity review.

Both tracks contain latest-revised history, not real-time historical vintages.
Seasonal re-estimation can revise earlier values. Genuine as-of backtests require
archived vintages and availability dates; eligibility remains false.

## RBA comparison from preceding local validation

The [official RBA G1 CSV](https://www.rba.gov.au/statistics/tables/csv/g1-data.csv)
uses **GCPIOCPMTMYP** for year-ended trimmed mean inflation excluding interest
charges and tax changes; **GCPIOCPMTMQP** is quarterly change, not annual change.
These are RBA IDs, distinct from ABS A3604511X and A130400382R.

The preceding independent validation compared 174 annual quarterly observations:
140 matched and 34 differed, all from March 1983 through June 2001. Maximum
absolute difference was 0.2 percentage points; all September 2001-June 2026
observations matched. Examples: March 1983 ABS 10.6 versus RBA 10.7; June 1983
9.8 versus 10.0; June 2001 2.9 versus 3.0. These are historical comparison findings,
not an RBA input or a fresh automated comparison in this offline importer.
The exact contribution of exclusions, precision and revisions remains unresolved.
Do not substitute RBA history for ABS history or infer equivalence from recent matches.

## Execution and safeguards

```powershell
python -B scripts/aehi_e12_import.py
python -B -m unittest discover -s tests -v
```

Default output: `data-candidates/aehi-e12-local-review.json`. Output creation is
exclusive: existing files are never overwritten. For another run use
`--output data-candidates/<new-name>.json`. No output outside that directory is
allowed. Sources must resolve within the checkout. The narrow standard-library
OOXML reader is reused from E04 unchanged; formulas, error/boolean cells and the
1904 date system are rejected. No dependencies or Excel installation are needed.

Contract checks reject wrong IDs, descriptions, units, adjustment, frequency,
interval, table context, dates, count/endpoint disagreement, internal gaps,
unexpected boundary blanks and nonfinite/nonnumeric observations. The writer
enforces candidate status, null score, publication/backtest/production restrictions,
independent track identity, immutable source hashes and all three HOLD gates.

Synthetic tests exercise contracts without source files. An optional local
integration test checks hashes, exact counts, endpoints, latest values and saved
candidate reproducibility excluding generation time. E04/API regressions retain
their original implementations and tests. The general E12 production importer
blocks remain unchanged. No registry, verified indicator, website or dashboard
changes are authorised by this candidate implementation.

Outstanding decisions: reconcile historical methods and RBA differences; approve
scoring frequency and historical window; assess monthly seasonal revisions;
establish historical vintage coverage before any real-time backtesting. Neither
successful parsing nor local tests authorise production promotion or composite scoring.

## Implementation verification (22 October 2026)

`python -B -m unittest discover -s tests -v`: **31 tests passed**, no skips
(9 E12, 16 E04, 6 existing API checks). Candidate generation produced 174 A
observations and 17 B observations, with latest values of 3.6% for 2026-Q2 and
2026-08 respectively. Git confirms both source workbooks are ignored, untracked
and unstaged. `git diff --check` passed. No production importer blocks, existing
indicator functionality, website/dashboard files or PR state were changed.
