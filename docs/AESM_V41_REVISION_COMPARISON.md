# AESM V4.1 Phase 2C: synthetic vintage revision comparison

Research only. E04/E12 remain candidate-only. AEHI/AESI/ASFI composite scores
remain HOLD and null. PR #8 remains Draft. No capture, network, scheduling,
publication, production pinning or approval is implemented.

## Scope and inputs

`scripts/aesm_revision_compare.py` compares explicitly synthetic bundles containing
an unchanged Phase 2B-format STARTED record, its terminal VALIDATED record, exact
UTF-8 source text, and a separate methodology declaration. The checked-in old/new
fixtures in `tests/fixtures/aesm_revision/` are fabricated observations, identifiers
and timestamps, not official source data or real capture evidence. Their URLs are
synthetic labels on the permitted ABS host and must never be fetched.

The source payload adapter is deliberately limited to synthetic SDMX-shaped CSV.
It rechecks dimensions, source byte hash/count, canonical period order, continuity,
boundary missingness and recorded coverage. It does not accept actual archives,
XLSX, RBA CSV, derived E04 histories or Phase 2A manifests as observation inputs.
This isolates arithmetic research from live ingestion and avoids interpreting
Phase 2A's unknown retrieval times or retention targets as captured vintages.
Phase 2A manifests, capture code/schema, master contract, snapshots and E04/E12
research implementations are unchanged.

Capture records undergo Phase 2B schema, identity, timing and restriction checks.
Only VALIDATED terminal records with matching STARTED linkage are eligible;
interrupted, failed, pending, corrupted, promoted or incomplete inputs fail.
Filename provenance must agree with local-import versus HTTPS transport, and
successful records cannot retain a validation error type. These checks supplement
the frozen Phase 2B validator without changing it.
Distinct capture IDs and strictly ordered, non-overlapping capture times are
required. Local-import retrieval timestamps remain null; completion times order
those events and do not establish original retrieval or publication availability.

Provider, source series ID, indicator, native frequency, unit, adjustment,
methodological variant, source role, adapter and dimensions must match exactly.
No unit conversion, quarterly/monthly splice or E04 A/B substitution is allowed.
These checks establish consistency with supplied identities, not official
authenticity or automatic membership in the draft master contract.

An explicit declaration supplies definition version, methodology, reference year,
price basis and percentage-point applicability. Use `NOT_APPLICABLE` where
appropriate; unknown declarations must be reviewed before input preparation.
Explicit UNKNOWN, UNVERIFIED, UNSPECIFIED, PENDING or TBD placeholders require
manual review even if both vintages use the same placeholder. Empty/non-string
declarations fail validation.
Any change in these fields or capture description/table/data type yields
`MANUAL_REVIEW_REQUIRED`, with reasons and no numerical rows or statistics.
No override flag exists. Identity mismatches are rejected rather than compared.
Material changes absent from metadata cannot be discovered from values alone.
Declarations are hash-bound to the reported bundle, not retroactively claimed as
fields authenticated by the original Phase 2B capture.

## Reproduce offline

```powershell
python -B scripts/aesm_revision_compare.py --old tests/fixtures/aesm_revision/old.json --new tests/fixtures/aesm_revision/new.json
python -B -m unittest discover -s tests -v
```

The CLI emits JSON to stdout only; it has no file writer. Exit code 0 means a
research comparison completed, 2 means manual review, and invalid inputs fail
without a comparison report. No generation timestamp or random ID is introduced.
Identical bundles and implementation produce identical reports. Duplicate JSON
keys, nonfinite JSON constants, duplicate CSV columns and malformed rows fail.
CSV quoting is parsed strictly. Synthetic SERIES and UNIT_MEASURE dimensions are
required; SERIES must equal the declared ID, and PCT must agree with percentage
units. Non-percentage unit codes remain operator declarations rather than a full
SDMX DSD validation.

## Classification and arithmetic

Monthly keys are ASCII `YYYY-MM`; quarterly keys are ASCII `YYYY-Qn`, with calendar
years 0001-9999. Unicode digits and year zero are rejected. Periods are compared
over their sorted union. An absent row differs from an explicit missing value:

| Condition | Classification |
|---|---|
| Present only in new | NEW_OBSERVATION |
| Present only in old | REMOVED_OBSERVATION |
| Present in both, one null | MISSINGNESS_CHANGED |
| Present in both, numerically equal or both null | UNCHANGED |
| Present in both, unequal numeric values | REVISED |

Existing Phase 2B rejects internal gaps; explicit missing observations therefore
occur only at coverage boundaries. There is no filling or zero substitution.
Values are ASCII plain decimal strings, at most 100 characters; floats, exponents,
thousands separators and nonfinite values are rejected. Decimal precision is
fixed at 256 independently of caller context. Subtractions are exact for accepted
values; non-terminating means use that fixed precision. Output numbers are decimal
strings, with canonical zero and no redundant fractional zeros.

For numeric pairs, signed change is new minus old; absolute change is its
magnitude. Percentage-point change equals signed change only when explicitly
applicable and units are percentages. No relative-percent division is performed,
so zero/negative old values need no special denominator rule. Unpaired or missing
values have null changes. Summaries include all numeric pairs, including unchanged
pairs, and expose class counts, union/overlap counts, mean signed/absolute changes
and maximum absolute change. Empty numeric intersections have null statistics.

Reports retain old/new source identities, byte hashes, record IDs, timestamps,
release attestations, coverage, bundle hashes, methodology declarations and tool
hash. They do not establish first-release history, source authenticity, historical
availability, significance thresholds or real-time backtest eligibility.

Before extending this prototype to real archives: independently review source and
methodology declarations, implement byte-bound Decimal extractors for each actual
format, retain matching historical schema/code, and validate archive/backup and
as-of availability policies. E04 derived revision attribution across income,
deflator and population sources remains separate research work.

The comparison suite also covers independently resealed failed captures, local
imports, disjoint coverage, missing-to-value transitions, malformed CSV, unknown
reference bases, extreme decimals and non-terminating means. CLI subprocess tests
check byte-identical output across hash seeds, manual-review exit code 2 and empty
stdout on invalid JSON. Tests create and clean temporary synthetic files only;
the command itself emits reports to stdout and never writes input files.
