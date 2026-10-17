# ASFI V3.7 — Official quarterly indicator feed (research draft)

## Status
V3.7 adds two **raw** RBA series and a historical trend display to the ASFI dashboard. **Initial records were loaded from RBA files provided for review on 17 October 2026 and checked against their file headers and SHA-256 hashes.** The reviewed development-branch JSON includes 70 S01 quarterly observations (2009 Q1–2026 Q2) and 69 S02 observations (2009 Q1–2026 Q1). It does **not** publish ASFI index scores, dimensional scores or economic risk labels. All composite scoring stays `HOLD`.

| Code | Definition | Source | RBA series |
| --- | --- | --- | --- |
| S01 | Household debt / household disposable income | RBA E2 | `BHFDDIT` |
| S02 | Housing interest charged / household disposable income | RBA E13 | `LPHTICRI` |

RBA replaced the older E2 housing-interest-payments ratio with an E13 interest-*charged*-to-income series beginning with the February 2023 statistical-table release. Do not splice the old and new definitions without a documented bridge. See [RBA table changes](https://www.rba.gov.au/statistics/tables/changes-to-tables.html).

## Fetch and generate candidate JSON

From the repository root with Python 3.9+:

```powershell
python scripts/import_asfi_rba.py --download
```

If the RBA blocks automated downloads, manually download the official CSVs in your browser:

- [E2 (CSV)](https://www.rba.gov.au/statistics/tables/csv/e2-data.csv)
- [E13 (CSV)](https://www.rba.gov.au/statistics/tables/csv/e13-data.csv)

Then run:

```powershell
python scripts/import_asfi_rba.py --e2 "$HOME\Downloads\e2-data.csv" --e13 "$HOME\Downloads\e13-data.csv"
```

The script extracts by exact RBA series ID, checks labels and percent units, validates chronological quarterly observations, rejects duplicate/future periods, and records the raw CSV SHA-256 and publisher. It **does not** calculate ASFI scores.

## Editorial review before publication

The importer-generated `asfi-indicators.json` has `data_status: "DATA_IMPORT_REVIEW_REQUIRED"`. This status intentionally **prevents the Dashboard from displaying numeric values** until an editor reviews the file. The current **development branch** uses `VERIFIED_FOR_PUBLIC_DISPLAY` following source-file, SHA-256, series-ID, unit, date and selected numeric cross-checks, so the site owner can preview actual observations locally. **This does not mean production deployment or index-score approval.**

For **each** series, verify:
1. Exact RBA table and series ID, percentage units, denominator definition and any breaks/notes.
2. Several recent quarters **against the original RBA files**, including release dates and missing observations.
3. Whether all published values are revised current-vintage observations, rather than claimed point-in-time historical snapshots.
4. That the JSON `source_retrieved_utc` and SHA-256 hashes correspond to the downloaded files.
5. Chart and cards render correctly on desktop and mobile.

After those checks **only**, edit `data_status` from `DATA_IMPORT_REVIEW_REQUIRED` to `VERIFIED_FOR_PUBLIC_DISPLAY` in a reviewed PR and merge it. If regenerating the current reviewed file, do not overwrite its `source_file_reviewed_utc` with a guessed source-download time; record the actual source-file review timestamp, source publication dates and SHA-256 hashes. Do **not** change `composite_release_status` from `HOLD`; `asfi-public-status.json` stays HOLD.

## Display behavior

- The dashboard loads `/asfi-indicators.json` as an ordinary same-origin JSON asset. The current source vintage is RBA E2 dated 25 Sep 2026 and E13 dated 13 Aug 2026; **E13 has a blank S02 value for 2026 Q2**, so it correctly reports S02 as of 2026 Q1.
- It shows S01/S02 latest values, observation periods, change in percentage points, and a **24-quarter** interactive SVG series.
- Missing, stale, malformed or unapproved JSON -> show `—` and clear verification status, never guessed values.
- Each official series shows its original RBA table and ID and links to the public statistical tables directory.
- A successful data import alone **does not** mean the data are live: they must be committed, reviewed and deployed.
- Future updates should be processed in a review PR with the same checks.

## Phase boundary

S03–S08 require separate official APRA/ABS import specifications and comparability checks. AEHI/AESI composite calculations are outside this phase.
