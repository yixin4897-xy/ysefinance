# AESM Social Sentiment Research — Phase 1 (offline candidate)

**State: CANDIDATE_ONLY_UNVALIDATED · Not for publication · No live collection · No index score.**

This project explores **discussion patterns** about Australian economic conditions across five topics: living costs, housing, employment, consumer spending, and small-business conditions. It does **not** infer population-wide consumer sentiment or individual financial status. Reddit/YouTube/Chinese-language communities have selection biases. AESM E04, ASFI, and official ABS/RBA/APRA series remain separate and unchanged.

## Current deliverable

- Python 3.10+ **standard-library-only** offline analysis script in `sentiment.py`; no HTTP requests, API keys, browser automation, scheduler, or network scraping.
- Synthetic, invented English and Chinese discussions in `fixtures/synthetic_comments.jsonl`, marked `synthetic: true` on every row. They are **not real Australian observations**.
- Reproducible tests in `tests/test_sentiment.py`.
- `FEASIBILITY.md`, `METHODOLOGY.md`, and `SCHEMA.md` explain permissions, sampling, aggregation, model limitations, and validation gates.

## Run safely (from repository root)

```powershell
python -m unittest discover -s research/social-sentiment/tests -v
python research/social-sentiment/sentiment.py --input research/social-sentiment/fixtures/synthetic_comments.jsonl --synthetic-fixture --json-out social-sentiment-local.json --markdown-out social-sentiment-local.md
```

The two `social-sentiment-local.*` outputs are local-only **synthetic demonstration results**. Do not commit or publish them as observations. Sample sizes and platform labels in the fixture are invented. This repository deliberately contains no live-data collector. Never use an unapproved URL, scraper, authentication cookie, browser extension, or platform API to populate the input.

## External data approval gate

Real discussion data may be processed **only after** an actual human governance review and applicable platform authorization. Record an **out-of-repository** permission attestation:

```json
{
  "governance_approved": true,
  "rights_confirmed": true,
  "data_minimised": true,
  "approval_reference": "EXTERNAL-AUTHORIZATION-ID",
  "approved_by": "REVIEWER-NAME",
  "allowed_platforms": ["youtube"],
  "valid_until": "2026-12-31"
}
```

This JSON is only an **attestation, not proof of platform permission**. It must not be manufactured just to make the script run. Without documented valid permission, stay on the synthetic fixture. Consult each provider's terms, retention, attribution and permitted processing scope before use. Manual input must remove usernames, IDs, profile links, contact details, exact location, direct quotes with identifying details and any unnecessary personal information before analysis. Data must not be used to infer people's sensitive traits. The pilot does not verify that personal data has been fully removed from arbitrary `text` fields; this remains a required manual review.

Example *only after real approval* (do **not** execute now):

```powershell
python research/social-sentiment/sentiment.py --input approved_minimised.csv --approval PRIVATE_PERMISSION_FILE.json --json-out private_aggregate.json --markdown-out private_summary.md
```

Keep inputs and approval credentials outside the Git repository; verify all lawful retention/deletion requirements. No profiling, surveillance, ML training on platform content, or automatic posting.

## Next gates (explicit separate approval)

1. Confirm platform-specific commercial data rights (Reddit approval is **not** inferred from public visibility); assess a compliant YouTube Data API implementation and Google Trends Alpha status.
2. Establish a defensible sampling frame, topic relevance review, language-specific annotation quality and exclusion/bot criteria. Avoid claiming representative sentiment.
3. Pilot four weeks with approved inputs **only after owner authorization**; record provenance, sampling dates, source mix, precision/recall against hand-labelled sample, and data-retention constraints.
4. Compare observed **discussion rates** with ABS CPI, labour data, AESM E04, ASFI and RBA on their respective dates; compare co-movement descriptively without causal claims or composite scores.

**No changes to PR #8, E04/ASFI datasets, AESM model governance, production site, or scheduled workflows are authorized by this draft.**
