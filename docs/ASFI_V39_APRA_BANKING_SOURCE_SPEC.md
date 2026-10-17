# AESM V3.9 — APRA Banking Resilience source specification

**Status:** Official original Excel workbook received and inspected 17 Oct 2026. Raw S05/S06 indicators loaded into development branch for review; composite scoring remains HOLD. Not yet released to production.

## Indicator S05 — Banking CET1 capital ratio
- Model definition: APRA industry-level **Common Equity Tier 1 (CET1) capital ratio**, subject to the official statistical series definition, capital population, numerator, and risk-weighted-assets denominator in the source workbook.
- Primary source: APRA **Quarterly Authorised Deposit-taking Institution Performance Statistics**, June 2026 (historical workbook September 2004–June 2026), under **Capital Adequacy**; individual institution CET1 figures from the **ADI Centralised Publication** are supplemental and must not be improperly averaged to reproduce the industry figure.
- Important structural break: APRA's **2023 capital framework reform** can create a break in comparability. Record relevant footnotes and avoid splicing different bases without documenting and validating them.
- Do **not** mistake APRA's **Total Capital Ratio** (20.5% for June 2026) for the **CET1 Ratio**; they are different measures. **Verified June 2026 S05 CET1 = 12.5%**, extracted from **Tab 1c, row 64, column CK** (ratio stored as 0.125). Historical coverage: **2013 Q1–2026 Q2, 54 quarterly observations**. Prior 2026 Q1 = 12.3%. Series pre-2023 and post-2023 requires reform-break caution.

## Indicator S06 — Net Stable Funding Ratio
- Model definition: APRA published **Net Stable Funding Ratio (NSFR)** at industry level for the relevant NSFR-reporting ADI population, in per cent.
- Primary source: same **Quarterly ADI Performance Statistics** XLSX, under **Liquidity / Net Stable Funding Ratio**.
- The June 2026 APRA highlights report **114.5%** (June 2025: **116.2%**). Verified original Excel: **Tab 1e row 83, column AU**, ratio stored as 1.145; previous quarter **115.7%**. Historical coverage: **2018 Q1–2026 Q2, 34 quarters**. Tab 1e row 89 notes NSFR introduced January 2018; row 87 indicates 12 LCR-regulated entities for June 2026 (not all ADIs).
- NSFR coverage is not necessarily the same as the total ADI population for CET1. The population, aggregation method and break footnotes must be confirmed in the workbook. Avoid comparing this to the **LCR** or **minimum liquid holdings** ratios as if they were NSFR.

## Source and processing controls

Official main source: https://www.apra.gov.au/news-and-publications/quarterly-authorised-deposit-taking-institution-statistics

June 2026 highlights: https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-performance-statistics-june-2026-highlights

Publication date: **17 September 2026**, observation through **June 2026**.

Original Excel file SHA-256: `cb60ee011bb1cd6db7dfc1b537e73fa44d5234f7a8063f23272df0eeb2aab52e`. Both ratios are stored as decimals in the workbook and multiplied by 100 for display. CET1 is from all ADIs excluding 'other ADIs' and foreign branches in Level 2 capital adequacy; NSFR is from the LCR-regulated ADI group. 

Completed in **development branch**: extracted source observations, created `asfi-banking-indicators.json`, the two banking cards and trend switch, and a fail-closed standard-library import script (`scripts/import_asfi_banking.py`). Script output is always `DATA_IMPORT_REVIEW_REQUIRED` until editorial review. 

Remaining release checks:
1. **Done:** Original APRA performance workbook received; correct source as distinct from QPEX confirmed.
2. **Done:** CET1 Tab 1c row 64 and NSFR Tab 1e row 83 confirmed, ratio-to-percentage conversion checked.
3. **Done:** Retained 2023 comparability warning, 2018 NSFR inception date, distinct entity populations and original observation years.
4. **Done:** Exact latest values confirmed: CET1 12.5%, NSFR 114.5%.
5. **Done:** Hash and source metadata recorded in data contract.
6. **Done in draft:** Banking Resilience data cards and historical trend toggle, independently gated from ASFI index score.
7. Review on desktop/mobile before a separate merge request.

This stage concerns raw official banking data, not final AESI/ASFI numerical scores.
