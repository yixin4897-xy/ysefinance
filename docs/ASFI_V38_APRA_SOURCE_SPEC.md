# AESM V3.8 — APRA mortgage risk source specification

**Status:** Source workbook examined; 30 quarterly values from 2019 Q1 through 2026 Q2 extracted and verified. V3.8 remains in a draft development branch pending user visual review.

## S03 — High DTI residential mortgage lending share

- Proposed definition: the share of **new housing loans funded during the quarter** where debt-to-income ratio is **at least 6 times**. Unit: per cent of new loans funded, following APRA's own denominator/explanatory notes.
- Use **total new loans** as the model series rather than owner-occupied or investor-only series; the other two should be displayed separately as supplemental context if desired.
- Primary source: APRA **Quarterly authorised deposit-taking institution property exposures statistics** (QPEX), specifically **Tab 1c, row 35** (numerator, DTI ≥6x) divided by **Tab 1c, rows 9 + 10** (owner-occupied and investment new term loans funded). The broad row 7 total includes non-housing and revolving loans and must **not** be used as the S03 denominator.
- APRA's June 2026 highlights report **5.6% for June 2026** (vs 5.5% June 2025).
- Do not confuse this with APRA's supervisory **20% DTI limit**, which is applied separately to new investor and owner-occupier lending. The 20% limit is not the measured industry average.
- Do not mix loan **funding** with applications, approvals, borrower counts or outstanding stock.

## S04 — Residential mortgage NPL share

- Proposed definition: APRA's **non-performing residential mortgage loans as a share of ADIs' outstanding residential property exposures**, consistent with the QPEX property-exposure release. Avoid substituting the separate 30–89-days-past-due statistic, and confirm the denominator in workbook explanatory notes.
- Primary source: APRA **Quarterly authorised deposit-taking institution property exposures statistics** (QPEX); **Tab 1b, row 69**, non-performing loans numerator; **Tab 1b, row 16**, total residential credit outstanding denominator. This computes the NPL ratio rather than using 30–89 days past due.
- APRA's June 2026 highlights report **1.01%** for June 2026, vs 1.04% June 2025.

## Publication metadata

APRA published the June 2026 quarterly release on **17 September 2026**. The reviewed workbook SHA-256 is `be570149ec853fdae93be1f405724af697c7a1a33ed383894c0a6014dc112cb6`. Quarter-end dates are in APRA Excel serial dates on Tab 1b and Tab 1c row 4. Cite the source workbook, worksheet, original fields, explanatory notes and source SHA-256 for every imported series. Archive the as-received workbook separately from any transformed JSON. Preserve observation quarter independently from publication date.

## Primary official references

- [APRA Quarterly ADI statistics page, including the QPEX workbook](https://www.apra.gov.au/news-and-publications/quarterly-authorised-deposit-taking-institution-statistics)
- [June 2026 property exposures highlights](https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-property-exposure-statistics-june-2026-highlights)
- [June 2026 media release](https://www.apra.gov.au/news-and-publications/apra-releases-quarterly-authorised-deposit-taking-institution-statistics-27)
- [March 2026 announcement of separate DTI series](https://www.apra.gov.au/news-and-publications/apra-releases-quarterly-authorised-deposit-taking-institution-statistics-26)

## Next implementation checkpoint

1. **Completed:** Received the original June 2026 **QPEX statistical Excel workbook** from the site owner and inspected the original cells and metadata.
2. **Completed:** Identified exact numerator and denominator rows, 30 quarter-end dates, relevant population and calculated percentages. June 2026: 10825.3 / (123607.6 + 71066.5) × 100 = **5.5607%** (S03); 25868.5 / 2558542.4 × 100 = **1.0111%** (S04). Both match APRA-highlight rounded values.
3. **Completed for latest quarter:** S03 rounds to **5.6%**, S04 to **1.01%**; past values from 2019 Q1 through 2026 Q2 were extracted without imputing any gaps.
4. **Next:** Formalise a repeatable XLSX-to-JSON importer that fails closed on missing/changed headers; the initial extracted history and provenance have been committed to `asfi-apra-indicators.json`.
5. **Completed in development:** Added a separate APRA Mortgage Credit Risk area with S03/S04 cards, calculated ratios and quarterly trend switching. No scores.
6. Verify on desktop/mobile, then review PR before merge.

**Publication controls:** vetted development-branch observations only; no production deployment yet. `asfi-public-status.json` remains `HOLD`, and a partially checked workbook must not be displayed as approved.

## Research interpretation

S03 is a **new-loan flow** (risk in recent mortgage origination), while S04 is a **stock-based loan quality ratio**. They have different populations and denominators; similar chart scales must never suggest they measure the same risk. Do not derive one from the other.
