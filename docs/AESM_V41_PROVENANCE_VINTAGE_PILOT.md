# AESM V4.1 Phase 2A: provenance and vintage control pilot V0.1

**Research only. E04/E12 candidate-only. AEHI/AESI/ASFI composite scores HOLD.
PR #8 remains Draft. No publication, commit, push or deployment is authorized.**

## Artifacts and scope

- Schema: `docs/aesm-provenance-manifest-schema-v0.1.json`, JSON Schema Draft
  2020-12, version 0.1.0. Its restricted pilot contract permits only E04/E12,
  latest-revised classification, false approvals and null composite scores.
- Builder/validator: `scripts/aesm_provenance.py`, Python standard library only.
  It implements the schema keywords used in this schema and rejects unsupported
  keywords. The schema can also be used with a full Draft 2020-12 validator.
- Store: `data-candidates/provenance/manifests/<manifest_id>.json`. Four manifests
  describe E04 A/B and E12 A/B; variants are not additional indicators.
- Tests: `tests/test_aesm_provenance.py`; synthetic metadata tests need no source
  workbooks. An optional local integration test uses the original workbooks.

The Master Indicator Contract V0.1 at commit
`6dc970f614f5199f9baa929b5c5c7d1bcf05106a` remains unchanged and is linked as
evidence, not treated as new approval. The Phase 2A code/schema are uncommitted
working artifacts identified by their own LF-normalized SHA-256 evidence fields;
the evidence commit anchors the preceding research, not a false claim that the
new code already exists in that commit. Source XLSX hashes always cover exact
binary bytes and are never line-ending-normalized.

Existing E04/E12 importers are reused read-only to validate actual local workbook
metadata, units, adjustment, IDs, dates, coverage and hash contracts. Fresh
in-memory candidate output must match the saved candidate except its generation
timestamp. Existing candidates, source workbooks, registry, production pins,
master contract and dashboard files are not rewritten. No raw observations or
scores are copied into provenance manifests; only safe metadata is stored.

## Dates and historical meaning

These are three different concepts:

1. **Observation period/date:** the period the measurement describes. ABS workbook
   dates label the first day of the reference month (quarter labels use its final
   month). This is not a publication date; ERP measurement timing is STOCK_CLOSE.
2. **Release period/date:** publication identity and calendar date recorded from
   prior source review. E12 belongs to the August 2026 release, published
   2026-09-30; its quarterly history ends 2026-Q2, while its monthly history ends
   2026-08. Release date has no invented time-of-day or historical availability
   timestamp. E04 workbook release identity/date are unknown.
3. **Retrieval timestamp:** when the exact source bytes were downloaded. Unknown
   for all supplied files and therefore null. Generation time, current access,
   file modification time and Git dates must never substitute for retrieval.

All manifests are `latest_revised_data_research` with `point_in_time_eligible`
false. A content ID or known release date does not prove first-release values or
historical operational availability. V0.1 cannot certify point-in-time data; that
requires a separately reviewed schema/policy with archived vintages and evidence.

E04 direct workbook URLs remain null. National Accounts landing pages are only
reference links, not verified file URLs; the population reference URL is unknown.
E12 file URLs and the release date are retained as prior-review evidence, not
fresh network verification. Source authenticity for E04 remains UNKNOWN; E12's
prior official byte-identity review is recorded without claiming a fresh download.

## Pilot sources and coverage

Input roots are existing ignored `research-inputs/e04/` and `research-inputs/e12/`.
Filenames below are the supplied local basenames; E04 names containing `(1)` do
not establish original publication filenames or vintages.

| Source file | Roles / exact IDs | Coverage | Exact SHA-256 |
|---|---|---|---|
| `e04/5206020_Household_Income (1).xlsx` | Income / A2302939L | 268 Q, 1959-Q3 to 2026-Q2 | `98c1561f5640195b962b56e86898ae61dd017df56f3fefff937c571b2cb60ba5` |
| `e04/5206008_Household_Final_Consumption_Expenditure (1).xlsx` | Current HFCE / A2302236T; volume HFCE / A2303280V | 268 Q each, 1959-Q3 to 2026-Q2 | `889dcad19a45827d68a0343bf26ca3f9da506dd887a0f18f88de1e9ec4afd8cc` |
| `e04/310101 (1).xlsx` | Closing ERP / A2133251W | 180 Q, 1981-Q2 to 2026-Q1 | `79eb16006d54bb0f0dbb1e71bdcb2fcb0e098ecb3ae2f29d6e9418a3e5a48a74` |
| `e12/64010Appendix1a.xlsx` | Quarterly track A / A3604511X | 174 Q, 1983-Q1 to 2026-Q2 | `71f8b078d9fc59b011ad1bf3ae77ce23c6dee7eb667fc276acf6821e9bc11f02` |
| `e12/640106.xlsx` | Monthly track B / A130400382R | 17 M, 2025-04 to 2026-08 | `1df9e8b27beb31c8ab3ed36ee8f9d309fb0e0e61706d48df17fcf766ce44f01a` |

E04 A produces 179 growth quarters (1981-Q3 to 2026-Q1); B produces 178
(1981-Q4 to 2026-Q1). Both use the same four input series, with no internal input
gaps. The prior unavailable B values are not zero. The shared common level grid
ends at 2026-Q1 because June ERP is absent; the source histories retain their own
coverage rather than being relabelled as one common publication vintage.

E12 A excludes 42 leading blank cells and four trailing placeholders; B excludes
12 leading blanks. Neither has internal gaps. All excluded period labels are
retained. Future grid dates are not forecasts. The two tracks are never spliced,
filled or averaged. E04 reference-year application remains UNKNOWN: the official
release reference year 2023-24 does not yet establish the supplied workbook base.
E12 annual-rate inputs have no applicable index reference-year assignment.

`5206024_Selected_Analytical_Series (1).xlsx` is not an E04 calculation input and
is deliberately excluded from source-vintage manifests.

## Identity and append-only behaviour

`source_vintage_id = abs-sha256-<exact workbook SHA-256>`. It identifies bytes,
not a calendar publication vintage. The two HFCE series share one workbook ID;
series IDs and roles distinguish them. Source identity conflicts are checked by
provider + series ID + source-vintage ID; changing immutable metadata under the
same identity is rejected across stored manifests.

`manifest_id = <indicator>-<variant>-<SHA-256(canonical payload)>`, excluding only
the manifest ID itself. Canonical JSON sorts keys, uses ASCII escapes and compact
separators, with no nonfinite values. No variable generation timestamp is added,
so the same source/evidence/code/schema bytes reproduce identical manifests.

`pilot --append` can write only the fixed research metadata store. It validates
all prior manifests before appending, serializes writes with an exclusive lock,
and uses exclusive file creation. Identical reruns return UNCHANGED without
touching old files. Changed content with a reused manifest ID, conflicting source
metadata, malformed existing files, unexpected fields or unsafe/symlink paths
fail closed. Changed metadata under the same source identity requires a future
reviewed amendment/supersession design, not an overwrite or renamed workaround.

This is append-only **through the provided writer**, not filesystem WORM storage
or a signed audit log. Manual deletion/rewrite, an administrator bypass, interrupted
partial writes and Git history changes are not prevented. Partial/malformed files
block later appends; no automatic repair/delete is attempted. The transient
`.append.lock` is removed after successful/failed writes by its owner; an existing
lock blocks concurrent writers. Crash recovery must inspect ownership before any
manual stale-lock cleanup. Batch creation is per manifest, not a four-file atomic
transaction; a valid partial batch can be rerun idempotently.

## Snapshot storage and retention

No workbook is committed, moved, copied or archived by this pilot. Existing
ignored originals remain untouched. Each manifest names the retention target
`research-inputs/vintage-archive/sha256/<hash>.xlsx`, also ignored by Git. Archive
status explicitly remains NOT_ARCHIVED_BY_PILOT; a locator is not a backup.

Before operational use, retain verified bytes in approved durable storage outside
Git with content-addressed keys, restricted write/delete permissions and a second
backup. Keep every referenced snapshot while any manifest/research result depends
on it; no automated expiry is authorized. Verify hashes on ingest and restore,
never replace old bytes with a later release, and retain manifests and code/schema
versions needed to reproduce each run. Provider redistribution/retention terms and
storage ownership require review. Do not put credentials, signed URLs, personal
absolute paths or binary/base64 file contents in Git metadata.

## Commands and validation limits

```powershell
# Read and verify source workbooks; write nothing.
python -B scripts/aesm_provenance.py pilot
# Exclusively create metadata manifests; identical reruns do not overwrite.
python -B scripts/aesm_provenance.py pilot --append
# Validate stored schema, identities and cross-manifest conflicts without XLSX.
python -B scripts/aesm_provenance.py validate
# Also reproduce the entire frozen pilot from current local source/evidence files.
python -B scripts/aesm_provenance.py validate --verify-sources
python -B scripts/validate_aesm_master_contract.py
python -B -m unittest discover -s tests -v
```

Schema/identity validation alone does not authenticate source bytes or claims in
handwritten metadata. `--verify-sources` is required for this pilot's source-check
claim. It compares the entire stored set to reproducible current pilot output;
future releases/implementations require new reviewed contracts and historical
code/schema retention. Older manifests must be validated against their recorded
implementation, not silently rewritten to match new code.

No command approves an indicator, edits pins, writes a public dataset, calculates
scores, changes PR state or deploys. Future work: verify E04 official file origins,
release vintages and price base; establish real retrieval evidence prospectively;
populate durable archives; design metadata amendments and historical as-of joins;
measure revisions before making any real-time backtesting claim.
