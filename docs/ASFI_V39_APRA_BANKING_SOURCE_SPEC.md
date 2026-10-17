# AESM V3.9 — APRA Banking Resilience source specification

**Status:** Official source identified; underlying statistical XLSX not yet inspected, no series imported, scores remain HOLD.

## Indicator S05 — Banking CET1 capital ratio
- Model definition: APRA industry-level **Common Equity Tier 1 (CET1) capital ratio**, subject to the official statistical series definition, capital population, numerator, and risk-weighted-assets denominator in the source workbook.
- Primary source: APRA **Quarterly Authorised Deposit-taking Institution Performance Statistics**, June 2026 (historical workbook September 2004–June 2026), under **Capital Adequacy**; individual institution CET1 figures from the **ADI Centralised Publication** are supplemental and must not be improperly averaged to reproduce the industry figure.
- Important structural break: APRA's **2023 capital framework reform** can create a break in comparability. Record relevant footnotes and avoid splicing different bases without documenting and validating them.
- Do **not** mistake APRA's **Total Capital Ratio** (20.5% for June 2026) for the **CET1 Ratio**; they are different measures. The precise June 2026 S05 level must be extracted from the original APRA XLSX and validated, not guessed from highlights charts.

## Indicator S06 — Net Stable Funding Ratio
- Model definition: APRA published **Net Stable Funding Ratio (NSFR)** at industry level for the relevant NSFR-reporting ADI population, in per cent.
- Primary source: same **Quarterly ADI Performance Statistics** XLSX, under **Liquidity / Net Stable Funding Ratio**.
- The June 2026 APRA highlights report **114.5%** (June 2025: **116.2%**), with a year-on-year decline of approximately 1.67 percentage points on the original unrounded data.
- NSFR coverage is not necessarily the same as the total ADI population for CET1. The population, aggregation method and break footnotes must be confirmed in the workbook. Avoid comparing this to the **LCR** or **minimum liquid holdings** ratios as if they were NSFR.

## Source and processing controls

Official main source: https://www.apra.gov.au/news-and-publications/quarterly-authorised-deposit-taking-institution-statistics

June 2026 highlights: https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-performance-statistics-june-2026-highlights

Publication date: **17 September 2026**, observation through **June 2026**.

Before any numbers are shown on the dashboard:
1. Download/upload the exact official **Quarterly ADI Performance Statistics XLSX — September 2004 to June 2026** from APRA, not the QPEX property-exposures workbook previously used for S03/S04.
2. Inspect worksheet and series metadata. Identify industry aggregate **CET1 ratio**, **NSFR**, units and exact cells for each quarter.
3. Note CET1 reform-related break, NSFR coverage and any missing observation quarters. Do not invent values or infer figures from APRA chart images.
4. Extract chronological historical observations and verify June 2026 NSFR rounds to **114.5%** and its original-source year-earlier figure matches highlights.
5. Archive source workbook SHA-256, observation date, original release date, population and series denominator/definitions.
6. Integrate a **Banking Resilience** section with S05/S06 data cards and trend switch in a development PR. Keep independently gated raw data and composite ASFI HOLD.
7. Review on desktop/mobile before a separate merge request.

This stage concerns raw official banking data, not final AESI/ASFI numerical scores.
