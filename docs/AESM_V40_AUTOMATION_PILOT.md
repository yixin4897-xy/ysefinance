# AESM V4.0 — automated source monitoring (initial pilot)

**Draft only. Do not merge to production before a real GitHub Actions test.**

This first automation checks official RBA E2 and E13 CSVs once each Monday, parses the S01 and S02 series using the existing import script and compares the source hashes and observations with the last published data. It **never writes** to the public `asfi-indicators.json` or `asfi-public-status.json` files.

If either series changes, it writes a review-only `data-candidates/rba-source-review.json` in a bot-owned branch and opens a **draft pull request**. If nothing changed, it does nothing. If downloads fail, data cannot be validated, permissions are missing or a source changes format, the workflow **fails visibly without publishing any new value**.

## Human review and release
- Verify original series IDs, data dates and notes, historical revisions, source hashes, and units.
- Verify recent observation periods separately for S01 and S02; APRA and ABS release calendars differ.
- A future human-reviewed PR must copy the verified observations into `asfi-indicators.json`, record the actual review date and publication metadata, and leave composite score and all score approvals on `HOLD`.
- **Never merge the draft bot PR merely because it exists**: the staging JSON is not production data.
- A scheduled job depends on GitHub Actions permissions and service availability, as well as RBA public CSV download accessibility.
- The current RBA import parser has not yet been executed end-to-end against a live downloaded file in this branch. Validate and adjust for RBA's real file layout before enabling regular runs.

## Planned expansion
- **APRA S03–S04**: discover the latest QPEX release workbook URL, download to a temporary directory, verify schema, and run the QPEX importer. Source metadata must be checked before a staged PR.
- **APRA S05–S06**: download the current ADI performance XLSX and run the CET1/NSFR importer; explicitly flag the 2023 capital framework break.
- **ABS S07–S08**: define source tables and frequency before automating; fiscal GFS may be annual and must not be silently treated as quarterly.
- A composite ASFI/AESI score release would need a separate model-validation and governance procedure; it is **not** part of source monitoring.

## How to manually test (after enabling GitHub workflow permissions)
GitHub > Actions > AESM RBA source watch > Run workflow. Review logs, generated candidate branch, and any draft PR. Verify a run with no source changes does not create a PR or modify files.

**No external scheduler, paid hosting or secrets are needed for the basic GitHub Actions mechanism**, assuming repository permissions allow Actions and branch pushes. The GitHub-hosted workflow is not guaranteed to run exactly on schedule.
