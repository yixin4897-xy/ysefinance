# E04 Candidate V2 methodology governance

Status: **CANDIDATE_ONLY_PENDING_VALIDATION**. AEHI, AESI and ASFI composite
scores remain **HOLD**. Method B is the primary research candidate; Method A is
retained for sensitivity. Neither method is approved for publication.

## V2 research decisions

E04 is **consumption-price-adjusted real household gross disposable income per
capita growth**, using non-annualised quarter-on-quarter percentage change.
Average adjacent quarter-end ERP (B) approximates average population for a quarterly
income flow under linear within-quarter change; concentrated migration can violate
that assumption. Quarter-end ERP (A) remains the sensitivity comparison. This is
an analytical choice, not a verified ABS prescription for this E04 derivation.

Use the HFCE implicit price deflator for aggregate consumption purchasing power.
The [ABS June 2026 National Accounts release](https://www.abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product/jun-2026)
states a **2023–24** chain-volume reference year. Matching the supplied workbook
snapshot to that release vintage remains pending. Do not assign an unconditional
constant-dollar label yet. [RBA household-finances analysis](https://www.rba.gov.au/speeches/2008/sp-dg-301008.html)
uses the household consumption deflator for real disposable income; that supports
the price concept without establishing exact equivalence to every RBA income
series. The deflator reflects composition as well as prices and is not a
household-specific cost-of-living index or interchangeable with CPI.

Historical results are **latest-revised-data research**, not real-time backtesting.
Later source revisions, benchmarking and seasonal re-estimation can incorporate
information unavailable historically. Lagging revised observations does not remove
this problem. [ABS revisions guidance](https://www.abs.gov.au/statistics/detailed-methodology-information/concepts-sources-methods/australian-system-national-accounts-concepts-sources-and-methods/edition-8/chapter-24-quality-national-accounts/revisions)
and [RBA revision analysis](https://www.rba.gov.au/publications/bulletin/2013/mar/2.html)
establish the general risk, not E04-specific revision magnitudes.

`methodology.research_decisions` records primary/sensitivity methods, the price
concept, growth convention, historical classification, conditional reference-year
status and false publication/backtest eligibility flags. The candidate writer
rejects changes to the method selection, research-only status, publication
restrictions and composite HOLD gates. V2 changes governance metadata only;
all V1 calculations and source provenance remain unchanged.

## Proposed append-only source-vintage framework

Proposal only: no archive, database or storage service is implemented.

1. Retain immutable raw snapshots outside Git in approved durable storage, identified
   by SHA-256 and archive reference. New releases never replace earlier snapshots.
2. Append manifests containing source URLs, series IDs/dimensions, units, seasonal
   adjustment, price reference year, observation coverage, official publication
   timestamp/timezone, UTC retrieval timestamp, revision status and file hashes.
   Unknown dates remain unknown.
3. Key observations by series, observation quarter and vintage. Append revised
   values under new vintages rather than overwriting old values.
4. Record each derived run's input hashes/vintages, code commit, methodology version,
   method selection, generation timestamp and output hash. Preserve separate
   income/consumption and ERP release schedules.
5. For future as-of simulations, use only vintages available by each decision
   timestamp. Distinguish official publication availability from actual operational
   retrieval. Document conservative assumptions where availability is unverified;
   never fabricate missing historical vintages.
6. Compare initial-to-later growth revisions and signal sign changes. Report
   revised-history research separately from genuine real-time tests.

Storage selection, retention, historical archive coverage and availability-date
policy require approval before implementation. Current hashes establish byte
identity, not original-release vintage or past availability.

## Run offline

From the repository root:

```powershell
python -B -m unittest discover -s tests -p "test_aehi_e04_import.py" -v
python -B -m unittest discover -s tests -p "test_aehi_abs_api_import.py" -v
python -B scripts/aehi_e04_import.py
```

Default output: `data-candidates/aehi-e04-local-review.json`. Existing files are
never overwritten. For another review, pass `--output data-candidates/<new-name>.json`.
Outputs are restricted to new JSON files directly in that directory. The module
uses only Python's standard library, reads OOXML without opening Excel, and has
no network or publication path. It does not edit the registry, pinned series,
verified observations, existing candidate files, original workbooks or website.

## Verified source contracts

All files are under `research-inputs/e04/`. Metadata is read from `Data1` rows
1–10. The importer locates columns by exact series ID, resolves worksheet names
through OOXML relationships, and checks the Index table title and metadata labels.

| Role | Workbook | ID / original column | Exact description | Unit / adjustment / type |
|---|---|---|---|---|
| Nominal income | `5206020_Household_Income (1).xlsx` | A2302939L / BW | GROSS DISPOSABLE INCOME ; | $ Millions / Seasonally Adjusted / DERIVED |
| Nominal consumption | `5206008_Household_Final_Consumption_Expenditure (1).xlsx` | A2302236T / GA | FINAL CONSUMPTION EXPENDITURE: Current prices ; | $ Millions / Seasonally Adjusted / DERIVED |
| Consumption volume | Same Table 8 workbook | A2303280V / BC | FINAL CONSUMPTION EXPENDITURE: Chain volume measures ; | $ Millions / Seasonally Adjusted / DERIVED |
| Closing population | `310101 (1).xlsx` | A2133251W / L | Estimated Resident Population (ERP) ;  Australia ; | 000 / Original / STOCK_CLOSE |

The three monetary series span 1959 Q3–2026 Q2 (268 observations each). ERP spans
1981 Q2–2026 Q1 (180). The output records actual coverage, source paths, exact
metadata locations and SHA-256 for each input role. The consumption roles share
one file hash. File hashes identify the supplied bytes, not publication dates.
No release date or download vintage is inferred from filenames or file timestamps.

Source paths are repository-relative with forward slashes, for example
`research-inputs/e04/310101 (1).xlsx`. Input directories and resolved workbook
paths must remain inside the repository; external paths are rejected. Moving the
checkout does not change provenance paths or numerical output. The generation
timestamp intentionally changes between runs, so reproducibility comparisons
exclude only `generated_at_utc`.

`research-inputs/e04/` is ignored by Git. Supply the original workbooks separately
to reproduce the local integration check; they are not part of Candidate V1's
commit. Without the ERP workbook, the optional local integration test skips.
The synthetic tests run without the source workbooks.

The fourth supplied workbook, `5206024_Selected_Analytical_Series (1).xlsx`, was
inspected in the preceding source review. No directly published real household
disposable income per capita series was found within the four supplied workbooks.
Table 24 is not a calculation input and is not required at runtime. This is not
a claim about all ABS products.

## Calculation

For quarter t, let Y be household gross disposable income in current-price
millions, C be current-price HFCE millions, V be chain-volume HFCE millions,
and N be closing ERP in thousands:

```text
consumption implicit price deflator D[t] = 100 * C[t] / V[t]
real gross disposable income R[t]       = Y[t] * V[t] / C[t]  (millions)
A[t] = 1000 * R[t] / N[t]                                   (dollars/person)
N_average[t] = (N[t-1] + N[t]) / 2                           (thousands)
B[t] = 1000 * R[t] / N_average[t]                           (dollars/person)
growth_A[t] = 100 * (A[t] / A[t-1] - 1)
growth_B[t] = 100 * (B[t] / B[t-1] - 1)
```

Growth is non-annualised quarter-on-quarter percent. No intermediate rounding is
applied. The 1000 factor converts millions of dollars divided by thousands of
people to dollars per person. D is an implicit price index based on the supplied
chain-volume series; applying the official 2023–24 reference year remains pending
the supplied workbook vintage match.
These derived real income levels are not themselves ABS-published chain volumes.

Method A uses the closing stock. Method B approximates quarterly average
population using adjacent closing stocks; it is not an observed quarterly mean.
The prior ERP must exist even when it lies outside monetary input coverage.
No interpolation, population carry-forward, extrapolation or projections are used.

## Alignment and comparison

Compute levels only over the intersection of the four validated input histories.
With the current snapshots this is 1981 Q2–2026 Q1: 180 A levels and 179 B levels.
A growth begins 1981 Q3 (179 observations). B growth begins 1981 Q4 (178).
Compare growth over 1981 Q4–2026 Q1 only, with 178 matched observations.

Differences are **B minus A in percentage points**. The candidate includes every
paired difference, maximum absolute difference and its quarter(s), unweighted
arithmetic mean absolute difference, latest signed difference and latest absolute
difference. Growth-percent differences are already percentage points; do not
multiply them by 100 again. All source periods outside the level intersection are
listed explicitly, including unavailable June 2026 E04 due to missing June ERP.

## Validation and limitations

The importer rejects missing/duplicate IDs, mismatched descriptions, units,
adjustment, frequency, collection month, data type and table context. It rejects
blank, nonnumeric, nonfinite or nonpositive observations, duplicate dates,
unordered quarters, internal gaps, dates outside ABS quarter-label conventions,
and coverage/count disagreement with workbook headers. Formula cells and Excel's
1904 date system are unsupported and rejected rather than interpreted silently.
ABS quarter labels use the first day of the quarter's final month; that stored
date is not the population measurement date. `STOCK_CLOSE` supplies the timing.

Remaining review decisions:

- B is selected for primary research and A for sensitivity. Differences quantify
  sensitivity, not statistical error. An observed quarterly-average population
  source would require a separate review and methodology decision.
- Match the workbook vintage before applying the verified 2023–24 reference year
  to levels. HFCE price adjustment and gross income are selected for research,
  not publication. These aggregates are not median or equivalised income.
- Income and consumption are seasonally adjusted; ERP is original. The derived
  per-capita series is not independently seasonally adjusted.
- Source snapshots may have different revision vintages. Input metadata checks
  and hashes do not establish common original-release vintages or authenticity
  beyond the supplied workbooks. Full-history revisions can change both methods.
- Non-annualised quarterly growth is selected for research. Preserve the common
  observed cutoff; no June 2026 result is available from these four inputs.
- Validate calculated history and sensitivity results independently before any
  pinning, dashboard display or promotion to verified observations.

Synthetic automated tests check formulas, comparison statistics, alignment,
metadata failures, missingness, continuity, output protection and OOXML handling.
An additional local integration test checks the supplied snapshot endpoints and
counts. That snapshot test is intentionally specific to this review vintage.

## Initial candidate results (21 October 2026)

The generated `data-candidates/aehi-e04-local-review.json` contains 180 quarterly
rows, with unavailable initial B levels/growth represented by null rather than
zero. The paired growth comparison contains 178 observations:

| Comparison statistic | Percentage points |
|---|---:|
| Maximum absolute B minus A growth difference (2020 Q2) | 0.1741083964 |
| Mean absolute growth difference | 0.0437069999 |
| Latest signed B minus A difference (2026 Q1) | +0.0932231384 |

Latest common quarter, 2026 Q1:

| Quantity | Value |
|---|---:|
| Consumption implicit price deflator | 107.1023760371 |
| Closing ERP, thousands | 27,921.2 |
| Average adjacent closing ERP, thousands | 27,855.75 |
| Method A real quarterly income per person, price base unlabelled | 15,282.09921589 |
| Method B real quarterly income per person, price base unlabelled | 15,318.00610742 |
| Method A non-annualised quarterly growth, percent | -0.7560388119 |
| Method B non-annualised quarterly growth, percent | -0.6628156735 |

Validation: all 20 E04 and existing AEHI API-import tests passed (14 E04, 6 existing).
An independent 40-digit Decimal recomputation of all 178 paired growth differences
agreed within 1e-10 percentage points. SHA-256 comparison of all 75 pre-existing
workspace files found no changed or missing files, including all original ABS
workbooks, verified observations, existing candidates and website files. These
checks validate this implementation and supplied snapshot, not publication approval.
