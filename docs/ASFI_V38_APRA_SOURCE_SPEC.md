# AESM V3.8 — APRA mortgage risk source specification

**Status:** SOURCE IDENTIFICATION ONLY / no extracted observations. Draft for validation before any production release.

## S03 — High DTI residential mortgage lending share

- Proposed definition: the share of **new housing loans funded during the quarter** where debt-to-income ratio is **at least 6 times**. Unit: per cent of new loans funded, following APRA's own denominator/explanatory notes.
- Use **total new loans** as the model series rather than owner-occupied or investor-only series; the other two should be displayed separately as supplemental context if desired.
- Primary source: APRA **Quarterly authorised deposit-taking institution property exposures statistics** (QPEX), specifically **table 1c** (exact row/column subject to workbook review).
- APRA's June 2026 highlights report **5.6% for June 2026** (vs 5.5% June 2025).
- Do not confuse this with APRA's supervisory **20% DTI limit**, which is applied separately to new investor and owner-occupier lending. The 20% limit is not the measured industry average.
- Do not mix loan **funding** with applications, approvals, borrower counts or outstanding stock.

## S04 — Residential mortgage NPL share

- Proposed definition: APRA's **non-performing residential mortgage loans as a share of ADIs' outstanding residential property exposures**, consistent with the QPEX property-exposure release. Avoid substituting the separate 30–89-days-past-due statistic, and confirm the denominator in workbook explanatory notes.
- Primary source: APRA **Quarterly authorised deposit-taking institution property exposures statistics** (QPEX); actual column and exact non-performing loan terminology to be locked only after examining the XLSX.
- APRA's June 2026 highlights report **1.01%** for June 2026, vs 1.04% June 2025.

## Publication metadata

APRA published the June 2026 quarterly release on **17 September 2026**. Cite the source workbook, worksheet, original fields, explanatory notes and source SHA-256 for every imported series. Archive the as-received workbook separately from any transformed JSON. Preserve observation quarter independently from publication date.

## Primary official references

- [APRA Quarterly ADI statistics page, including the QPEX workbook](https://www.apra.gov.au/news-and-publications/quarterly-authorised-deposit-taking-institution-statistics)
- [June 2026 property exposures highlights](https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-property-exposure-statistics-june-2026-highlights)
- [June 2026 media release](https://www.apra.gov.au/news-and-publications/apra-releases-quarterly-authorised-deposit-taking-institution-statistics-27)
- [March 2026 announcement of separate DTI series](https://www.apra.gov.au/news-and-publications/apra-releases-quarterly-authorised-deposit-taking-institution-statistics-26)

## Next implementation checkpoint

1. Obtain the official June 2026 **QPEX statistical Excel workbook** via APRA. Prefer the exact file linked from the official quarterly publication.
2. Inspect workbook table/worksheet definitions, historical time series, breaks and industry scope; lock matching series identifiers.
3. Cross-check June 2026 S03=5.6% and S04=1.01% and year-ago comparisons against APRA's highlights.
4. Implement an XLSX-to-JSON importer that fails closed on missing/changed headers and records original workbook hash, publication date, numerical series, and definition.
5. Extend the Dashboard's **Official Indicator Data** from S01/S02 to S03/S04 with trend selection and transparent per-indicator provenance. No scores.
6. Verify on desktop/mobile, then review PR before merge.

**Publication controls:** no production observation series yet. `asfi-public-status.json` remains `HOLD`, and a partially checked workbook must not be displayed as approved.

## Research interpretation

S03 is a **new-loan flow** (risk in recent mortgage origination), while S04 is a **stock-based loan quality ratio**. They have different populations and denominators; similar chart scales must never suggest they measure the same risk. Do not derive one from the other.
