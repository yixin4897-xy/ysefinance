# AESM V4.1 — AEHI source integration and automation in parallel

## Why this stage exists
AEHI currently defines twelve indicators but has **no published official observations**. V4.1 establishes a reusable **five-indicator source registry and automated source-change review** before public data display. The development strategy is to implement each indicator's official-data ingestion, validation, history and automation as one unit.

## First five (data not yet imported)
| Code | Measure | Source | Publication cadence / caveat |
|---|---|---|---|
| E01 | Real GDP per Capita Growth | ABS National Accounts | quarterly; confirm growth horizon and exact table |
| E04 | Real Household Disposable Income per Capita Growth | ABS National Accounts | quarterly; approve population and real-deflator specification |
| E05 | Real Household Consumption Growth | ABS National Accounts | quarterly; confirm volume, seasonality and quarter-over-quarter vs year-over-year convention |
| E06 | Unemployment Rate | ABS Labour Force | **monthly**, not naturally quarterly; seasonally adjusted national series. A dashboard must label the month unless a separate quarterly aggregation policy is approved |
| E12 | Trimmed Mean Inflation | ABS Consumer Price Index | now published in a monthly CPI series; ensure comparable quarterly meaning before blending historical releases |

Primary official URLs are declared in `aehi-source-registry.json`.

## Combined workflow
1. **Detect** new official publication pages or file versions via a scheduled GitHub Actions job.
2. **Stage** candidate release metadata and source file links; never silently pick a number from scraped page text.
3. **Parse** the exact ABS CSV/XLSX time-series with series IDs, definitions, reference period, unit, release date and source hash. Reject changed source structure.
4. **Validate** at least two quarters and historical corrections against original ABS files and consistent units.
5. **Review** a draft PR. Only after human approval may the verified raw data be copied to a public AEHI JSON file.
6. **Display** the observation period, official release date, true original metric, latest value and history. Keep AEHI/ASFI/AESI scores on HOLD pending separate validation.

## What should not happen
- Automated page-change monitoring is **not** equivalent to a verified economic indicator. Monitoring cannot authorize publication of extracted numerical data.
- Do **not** present a monthly rate as a quarterly number without a documented rule.
- Do **not** pretend to have 12 populated indicators or produce a composite AEHI/AESI score.
- Do not add hardcoded numerical examples that could be mistaken for official current releases.
- AESI must address duplicate E11 (government interest burden) and S08 before weighting.

## Implementation gate
Before merging this branch, test the scheduled workflow with real ABS pages, pin extracted file URLs and series IDs, establish the correct update frequency, and verify the review PR is created only when new source content actually appears. Do not put unreviewed candidates on the website.

Current status: **Architecture and source monitoring pilot only. No AEHI numerical observations have yet been imported or published.**
