# AESM V4.1 Phase 2B: manually triggered prospective capture

**Research only. No scheduling, publication, commit, push or deployment.
PR #8 stays Draft; E04/E12 stay candidate-only; AEHI/AESI/ASFI scores stay HOLD.**

## Files and relationship to Phase 2A

- `scripts/aesm_capture.py`: manual capture, archive inspection and interruption
  recovery, using Python standard library only.
- `docs/aesm-capture-config-schema-v0.1.json`: strict operator request schema.
- `docs/aesm-capture-record-schema-v0.2.json`: strict prospective audit/manifest
  schema. This is a separate record family, not an overwrite of the V0.1 schema.
- `docs/examples/aesm-capture-e12-quarterly.json` and
  `docs/examples/aesm-capture-rba-household.json`: unapproved configuration
  templates using existing source identities. Release claims are null.
- `tests/test_aesm_capture.py`: local fixtures, mocked HTTPS and failure scenarios;
  no automated test depends on live ABS/RBA availability.

The capture tool reuses Phase 2A canonical JSON, safe paths and strict JSON
reading, plus the existing read-only ABS workbook reader/date parser. A separate
schema checker supports nullable result objects without changing the frozen
Phase 2A implementation. No Phase 2A schema, manifest, importer, candidate,
Master Indicator Contract, source registry, pin or dashboard is modified.

Existing dictionary/contract definitions remain primary methodology references.
Capture requests select an indicator, variant and source role but confer no
membership, definition or scoring approval. E04/E12 require an explicit A/B
variant. One capture describes one source file/series, not a newly calculated
E04 income series or a combined E12 history.

## Local configuration

Choose an absolute archive directory **outside this checkout and every other
Git worktree**. The tool rejects paths inside Git, symlink/alias paths and relative
archive roots. It does not default to a personal directory or create files in
the repository. Keep real local configuration outside Git too.

```powershell
$env:AESM_VINTAGE_ARCHIVE = Read-Host 'Absolute archive directory outside Git'
$captureRequest = Read-Host 'Path to reviewed local capture-request JSON'

# Preview only: no download, local-file read, timestamp assignment or writes.
python -B scripts/aesm_capture.py capture --config $captureRequest --dry-run

# Explicit manual HTTPS download and capture.
python -B scripts/aesm_capture.py capture --config $captureRequest

# Import an already downloaded file, without inventing its original retrieval time.
$downloadedFile = Read-Host 'Path to existing downloaded source file'
python -B scripts/aesm_capture.py capture --config $captureRequest --local-file $downloadedFile

# Read-only archive integrity and pending-capture report.
python -B scripts/aesm_capture.py inspect
```

`--archive-dir` overrides `AESM_VINTAGE_ARCHIVE`. No scheduler or workflow file is
added. `--dry-run` applies only to capture; it is rejected on recovery so it cannot
silently perform writes. A dry run previews the request, relative archive layout
and intended steps, not whether an unavailable future file will validate.

Copy a template to a reviewed local request and inspect the exact series,
description, units, adjustment, native frequency, data type, workbook table or
SDMX dimensions before each new series/release. Minimum observations and size
limits are capture-quality checks, not model thresholds. Never guess missing
IDs. The E12 template URL is the known August 2026 historical workbook; it is
not represented as a current/future release. Update its official URL deliberately
for the intended release, and review structural/methodological changes first.

Supported adapters:

| Adapter | Checks | Limits |
|---|---|---|
| ABS_XLSX | Exact table, ID and metadata, workbook declared counts/endpoints, finite values, chronological monthly/quarterly grid, missingness | Narrow Data1/Index ABS layout; formulas and unsupported Excel structures rejected; future coverage is not locked to Phase 2A endpoints |
| RBA_CSV | Exact ID, title/description, units, frequency, requested adjustment, dates, finite values and continuity | Narrow RBA statistical-table CSV layout; unfamiliar footers/dates fail closed |
| ABS_SDMX_CSV | Exact configured dimensions, dates, finite values and continuity | Description/units/adjustment remain operator-specified; independent DSD review still required and explicitly noted in validation metadata |

All adapters reject internal missing periods. Boundary blanks are retained as
excluded labels/counts, not zeros. Failure is quarantined for review rather than
silently accepted or filled. No growth normalization or score is calculated.

## Time, release and identity semantics

- `started_at_utc`: actual local UTC time before transfer.
- `retrieved_at_utc`: actual UTC time after a complete HTTPS transfer, never a CLI
  input. It remains null for local imports and incomplete transfers.
- `completed_at_utc`: after validation and snapshot publication, before terminal
  manifest publication. It is distinct from retrieval time and observation period.
- Observation coverage: parsed native periods and missingness, not release dates.
- Release date/period: null unless the operator supplies an official evidence URL
  and verification note. Any supplied claim is labelled
  OPERATOR_ATTESTATION_NOT_AUTOMATED_VERIFICATION. No dates are inferred from
  filenames, filesystem modification times, URL fragments or current time.

The host clock must be accurate. No time-of-day is invented for date-only releases.
HTTPS redirects are checked before following and must stay on the configured
provider's official HTTPS allowlist: www.abs.gov.au, data.api.abs.gov.au or
www.rba.gov.au. Credentials, credential-like query keys and unsafe filenames are
rejected. Filename basis is recorded as Content-Disposition, URL basename or
local basename; storage never uses an untrusted original name as a path.

Every complete source has `snapshot_id = sha256-<exact byte SHA-256>`. A new
capture receives a random UUID capture ID and a canonical content-hashed record
ID. Repeating identical bytes reuses immutable blob storage but creates a new
capture event/manifest with its own actual timing. Reusing a capture ID fails.
Different bytes at an existing content address fail rather than being replaced.

This does not alter Phase 2A's historical identity or metadata-amendment rules:
new retrieval events belong to the prospective record family. Nothing backfills
old retrieval timestamps. All histories are conservatively classified
LATEST_REVISED_DATA_CAPTURE_NOT_HISTORICAL_FIRST_RELEASE, with point-in-time
eligibility false. Prospective byte capture alone does not prove first-release
history, publication-time availability, source authenticity or model fitness.

## Atomic publication and append-only audit

```text
archive/
  events/<capture_id>.json          immutable STARTED record
  .staging/<capture_id>.part        incomplete/unpublished transfer
  snapshots/sha256/<hash>           complete capture-validation-passing bytes
  quarantine/sha256/<hash>          complete validation-failing bytes
  manifests/<capture_id>.json       immutable terminal result
```

The STARTED event is published before any transfer. Bytes stream into an exclusive
staging file, with bounded size, declared HTTP length and encoding checks. Each
file is flushed/fsynced before same-filesystem hard-link publication; `replace`
and overwrite fallbacks are never used. ABS expanded ZIP size is also bounded.
The source hash is rechecked after validation. The complete snapshot/quarantine
object is published **before** the terminal manifest. JSON records are likewise
written to temporary files then atomically linked into their final names.

Terminal states distinguish VALIDATED, VALIDATION_FAILED, TRANSFER_FAILED and
INTERRUPTED. VALIDATED means the configured capture checks passed, **not** verified
indicator/publication status. Complete rejected files are retained in quarantine
with their hashes; they have no validated coverage or approval. Transfer failures
have no completed snapshot reference. Raw exception messages/absolute local paths
are not copied into records; error classes and scoped notes are retained.

All approval flags remain false, composite scores null and statuses HOLD. No
command changes production pins, verified datasets, methodology approvals or PR
state. Runtime records and snapshots are outside Git; there is no automatic
export or Git mutation path.

## Interruption recovery

Use a local filesystem supporting atomic hard links (for example NTFS); network,
FAT-like or cloud-synchronised filesystems are not certified. Unsupported hard
links fail closed. File fsync/atomic visibility is not a guarantee against all
power-loss/filesystem failure modes, nor filesystem-enforced WORM retention.

1. Run `inspect`. A STARTED event without a terminal manifest is pending, never
   a successful capture. Staging `.part` files and unreferenced complete blobs
   are not eligible input sources merely because they exist.
2. Confirm the corresponding capture process has stopped. Do not recover a live
   process; recovery does not independently prove process liveness.
3. Append an interruption result, preserving the original event and all bytes:

```powershell
python -B scripts/aesm_capture.py recover --capture-id '<pending capture ID>' --confirm-stopped
```

4. Recovery does not promote, retry, delete or adopt any partial/orphan snapshot.
   Investigate it, retain it under controlled storage and perform a new capture
   with a new ID if appropriate. Never reuse the interrupted ID or overwrite its
   result. Corrupted existing records stop inspection; restore from trusted backup
   and investigate instead of recalculating hashes to hide the conflict.

Concurrent distinct captures deduplicate blobs atomically. A capture racing with
recovery cannot overwrite the first terminal record; operators must still stop
the process first. Pre-existing staging files are never deleted by an operation
that did not create them. Filesystem failure may leave a durable STARTED record
and partial/orphan files; that audit intent remains visible. Preflight-invalid
configuration/unsafe paths are rejected before capture begins and create no audit
event. If the disk cannot publish the STARTED event, no transfer is attempted.

## Retention, backup, restore and quarterly procedure

Keep every referenced source, quarantine item, event and terminal manifest while
research depends on it; no automatic expiry/deletion is authorized. Restrict
write/delete access and use storage-level immutability where available. Retain
the matching code, schemas and request versions. SHA-256/record IDs detect damage
and accidental identity reuse, not malicious rewriting of all records or deletion
of a complete event/manifest pair. Independent backups/audit anchors are required
for stronger tamper/deletion guarantees.

For backup, pause captures/recovery or take a consistent filesystem snapshot.
Copy the entire archive including events, manifests, snapshots and quarantine;
preserve pending evidence too. Maintain a second independently controlled copy.
Restore into a new archive directory outside Git, run `inspect`, compare expected
capture inventory with the independent backup inventory, and investigate pending
or missing records. Never restore over a running archive or merge conflicting
identities by overwriting. The inspector rehashes referenced objects; it does not
automatically repeat all source parsing or certify operator release attestations.

Each quarterly review:

1. Review the intended official release, dictionary/master-contract identity,
   source scope and methodological breaks. Update a local request explicitly;
   unknown release fields stay null.
2. Check clock, disk space, backup health, archive permissions and pending captures.
3. Run dry-run and review the request. Trigger the capture manually once ready.
4. Inspect its terminal record, coverage/missingness, filename and hash. Review
   quarantined/failed outcomes independently; do not call them approved data.
5. Compare with prior captures for revisions under a separate research task.
   Back up the archive and record the quarterly operator review externally.
6. Any indicator/data-publication promotion remains a separate explicit approval
   process. No quarterly procedure lifts HOLD or enables composite scoring.

## Verification and operational limits

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/aesm_provenance.py validate --verify-sources
python -B scripts/validate_aesm_master_contract.py
```

Automated tests use local synthetic ABS/RBA fixtures and mocked HTTPS, including
future releases, interrupted streams/publication, content conflicts, deduplication,
dry runs, quarantine, recovery and approval guards. They do not certify live
provider accessibility. This implementation performs no real network capture as
part of its setup/testing. An operator-selected archive, a reviewed request and a
controlled manual smoke capture are still needed before operational use.

Next research work: independent configuration/source review, durable archive and
backup ownership, a controlled first live capture, revision comparison and a
separately governed prospective as-of availability policy. Historical source
origins/unknown retrieval times and E11/S08 overlap remain unresolved.
