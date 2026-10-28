# AESM V4.1 Master Indicator Contract V0.1

Status: **DRAFT_DOCUMENTATION_ONLY**. Machine-readable record:
[`aesm-master-indicator-contract-v0.1.json`](aesm-master-indicator-contract-v0.1.json).
Contract version `0.1.0-draft.1`; schema version `0.1.0`.

## Authority and scope

The maintained Indicator Dictionary in `aesm-research.html` is the primary
definition reference: ASFI section `indicators`, AEHI section `aehi`.
The user's Phase 1 documentation-governance decisions authorize this inventory;
they do not approve any economic model, score, weight or publication.

Exactly 20 indicators are represented: E01-E12 and S01-S08. E04 A/B and E12
quarterly/monthly tracks are variants within their indicators. Registered names
are retained verbatim. Operational definitions, registry records, pinned-series
records and implementation evidence remain separate. No old records are edited.

## Reading the contract

- `null` means unsupported or unknown, never zero. `UNKNOWN` is a specification
  state, not a missing observation, rejection or approval.
- `registered_definition` records dictionary wording; `operational_definition`
  records existing source/data implementation where available.
- `sources` holds provider, verified identifier or typed workbook locator and
  scoped evidence. A workbook row is not an invented Series ID.
- `coverage` describes committed snapshot coverage, not maximum agency history.
  E04 growth coverage is variant-specific; E12 has no combined observation count.
- `capability_evidence` preserves raw-display designations only. No new deployment
  verification is performed. Production definition approvals are not inferred.
- `scoring.direction`, `normalization`, `score` and all weights remain null.
  E12's existing formulas/slopes are isolated in `research_experiment`, with all
  parameter, weight, publication and real-time-backtest flags false.
- `evidence_catalog` records repository-relative paths, audited Git commit and
  SHA-256 of Git blob bytes at that commit, independent of checkout line endings.
  Working text must also match, allowing CRLF/LF conversion only. No untracked
  candidate file is used. Embedded official source-file hashes remain unchanged. Evidence
  hashes identify bytes; they do not authenticate official releases or vintages.
- `contradictions` remains unresolved with no silent overrides. `overlaps` are
  scoped research relationships, not measured correlation or approved deduplication.

## E11/S08 and release restrictions

Both dictionary entries remain. O01 records the same name/intended fiscal signal,
but exact numerical equivalence is unknown because E11 lacks accounting, source
and transformation detail. Any composite containing both is blocked pending
independent equivalence/overlap review and explicit approval. Neither dropping an
indicator nor declaring equivalence is authorized by this draft.

AEHI, AESI and ASFI scores remain **HOLD**, with null composite scores. All
unapproved model definitions remain candidate-only; no contribution is enabled.
E04/E12 variants remain unpublished. PR #8 is required to remain Draft; this work
does not call GitHub mutation tools. Existing importers, public datasets and
dashboards do not consume this documentation contract.

## Gates and versioning

G0 inventory, G1 source identity, G2 data/derivation, G3 raw display, G4 scoring
research, G5 composite methodology and G6 production release are separate gates.
All are `NOT_GRANTED_BY_THIS_CONTRACT`; existing scoped capability evidence is
preserved without promotion. Passing the validator is documentation QA only.

Schema compatibility, contract evidence snapshot and per-indicator definition
versions are independent. Population, concept, denominator, frequency, formula or
scoring changes require a new definition version and dependent reapproval.
Source/evidence changes require explicit review and a versioned contract update;
do not refresh hashes merely to silence a failure. No approval is auto-inherited.

Before later publication, missing source/measurement specifications, E11/S08,
normalization, weights, missingness, alignment/staleness, vintage controls and
independent release approval remain unresolved. They do not need invented
defaults to make this draft structurally complete.

## Read-only validation

From the repository root, standard library only:

```powershell
python -B scripts/validate_aesm_master_contract.py
python -B -m unittest discover -s tests -v
```

The validator reads evidence through local Git and checks the frozen V0.1 draft's inventory,
references/hashes, variants and publication safeguards. Negative tests ensure
missing indicators, altered evidence, unblocking E11/S08 and enabling scores or
weights fail. It performs no network access, data ingestion, writes or deployment.
It does not verify economic validity, source freshness or actual remote PR state.
