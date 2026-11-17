# Input and aggregate output contract

## Input: manually supplied minimised CSV or JSONL

A row contains only:

| Field | Type | Meaning |
|---|---|---|
| `platform` | string | permitted source platform category, e.g. `youtube`; must match approved scope |
| `timestamp` | ISO 8601 date-time with timezone | date/time of the observation, converted to UTC for weekly buckets |
| `text` | UTF-8 string (1–2000 characters) | pre-redacted permitted discussion text; transient in-memory only |
| `language` | `en` or `zh` | language supplied by reviewer; not inferred |
| `synthetic` | boolean (fixtures) | required `true` for every bundled synthetic fixture |
| `source_type` | optional string | provenance category; ignored by current classifier |

Do **not** include usernames, IDs, profile URLs, emails, phone numbers, geolocation, or cross-platform keys. The script rejects unexpected columns but **does not fully detect identities embedded in free text**; required manual pre-redaction and permission checks precede input.

Input file limit: 10,000 records. Exact normalized duplicate text in the same platform, language and UTC week is counted once. Invalid rows are counted; unexpected schema fields are a hard failure.

## Real-data attestation gate

`--approval PRIVATE.json` is mandatory for non-synthetic input; it must include documented human review, matching platform list, rights confirmation, data-minimisation acknowledgment, reviewer and expiry. A locally fabricated `true` value is not authorization. Never check in real approvals or third-party content.

Synthetic mode is limited to the bundled fixture directory and requires each row to be `synthetic: true`. The sample contains explicitly made-up rows and intentionally one duplicate.

## Aggregate output

Output JSON fields:

- `research_status = CANDIDATE_ONLY_UNVALIDATED`;
- `provenance = SYNTHETIC_TEST_ONLY` or `MANUAL_APPROVED_INPUT_UNVALIDATED`;
- counts for input, relevant rows, deduplicated, invalid and unclassified;
- language counts, source-platform categories, UTC-week summary, themes, directional labels;
- suppression of cells smaller than five; no raw text or personal identifiers;
- limitations and explicit no-composite/no-representativeness statements.

Output markdown is a readability-focused **test report**. Neither format is a sentiment index, published economic metric or evidence of causality. Outputs must not be placed under public website paths or committed without separate authorization.
