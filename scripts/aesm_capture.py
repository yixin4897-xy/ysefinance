"""Manual research captures only. No scheduler, production writes or approvals.

All runtime bytes/audit records live in a configured archive OUTSIDE Git.
Phase 2A stores are read-only and never used as capture output destinations.
"""
import argparse
import copy
from contextlib import ExitStack
import csv
import datetime as dt
from email.message import Message
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import uuid
import zipfile
from urllib.parse import parse_qsl, unquote, urlsplit
import urllib.request

import aesm_provenance as provenance
import aehi_e04_import as e04
import aehi_e12_import as e12

ROOT = Path(__file__).resolve().parents[1]
CONFIG_SCHEMA = ROOT / "docs/aesm-capture-config-schema-v0.1.json"
RECORD_SCHEMA = ROOT / "docs/aesm-capture-record-schema-v0.2.json"
MAXIMUM_BYTES = 100_000_000
HOSTS = {"ABS": {"www.abs.gov.au", "data.api.abs.gov.au"}, "RBA": {"www.rba.gov.au"}}


def schema_check(value, schema):
    """Strict local schema subset, including nullable objects in capture results.

    Kept separate so the frozen Phase 2A validator/implementation is unchanged.
    """
    supported = {"$schema", "$id", "title", "type", "properties", "required", "additionalProperties",
                 "items", "minimum", "minLength", "pattern", "enum", "const", "anyOf"}
    if set(schema) - supported:
        raise ValueError("Unsupported capture schema keyword")
    if "anyOf" in schema:
        if set(schema) != {"anyOf"}:
            raise ValueError("Unsupported combined anyOf schema")
        for choice in schema["anyOf"]:
            try:
                schema_check(value, choice)
                return
            except ValueError:
                pass
        raise ValueError("No matching nullable schema branch")
    types = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
             "string": lambda v: isinstance(v, str), "integer": lambda v: type(v) is int,
             "boolean": lambda v: type(v) is bool, "null": lambda v: v is None}
    if "type" in schema and (schema["type"] not in types or not types[schema["type"]](value)):
        raise ValueError("Capture schema type mismatch")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError("Capture restricted constant changed")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Unknown capture schema enum")
    if isinstance(value, str) and (len(value) < schema.get("minLength", 0) or ("pattern" in schema and not re.search(schema["pattern"], value))):
        raise ValueError("Capture schema string mismatch")
    if type(value) is int and value < schema.get("minimum", value):
        raise ValueError("Capture schema minimum failed")
    if isinstance(value, list):
        for child in value:
            schema_check(child, schema["items"])
    if isinstance(value, dict):
        if set(schema.get("required", [])) - set(value):
            raise ValueError("Capture required field missing")
        for key, child in value.items():
            child_schema = schema.get("properties", {}).get(key, schema.get("additionalProperties"))
            if child_schema is False or child_schema is None:
                raise ValueError("Unexpected capture record field")
            schema_check(child, child_schema)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text_digest(path):
    return digest(Path(path).read_bytes().replace(b"\r\n", b"\n"))


def utc(value):
    timestamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.utcoffset() != dt.timedelta(0):
        raise ValueError("Explicit UTC timestamp required")
    return timestamp


def official_url(url, provider):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in HOSTS[provider]
            or parsed.username or parsed.password or parsed.port or parsed.fragment):
        raise ValueError("Only official provider HTTPS URLs are allowed")
    if any(re.search(r"token|password|secret|signature|api.?key", key, re.I) for key, _ in parse_qsl(parsed.query)):
        raise ValueError("Credential-bearing URLs must not be stored")
    return url


def validate_request(request):
    schema_check(request, provenance.read_json(CONFIG_SCHEMA))
    official_url(request["official_source_url"], request["provider"])
    if request["maximum_bytes"] > MAXIMUM_BYTES:
        raise ValueError("Capture exceeds maximum configured size")
    if request["indicator"] in ("E04", "E12") and request["methodological_variant"] not in ("A", "B"):
        raise ValueError("E04/E12 require an explicit variant")
    contract = request["validation_contract"]
    if (contract["adapter"] == "RBA_CSV") != (request["provider"] == "RBA"):
        raise ValueError("Adapter/provider mismatch")
    if contract["adapter"] == "ABS_XLSX" and any(contract[k] is None for k in ("seasonal_adjustment", "data_type", "table")):
        raise ValueError("Exact ABS workbook metadata required")
    if contract["adapter"] == "ABS_SDMX_CSV" and not contract["dimensions"]:
        raise ValueError("Exact SDMX dimensions required")
    release = request["release"]
    if any(v is not None for v in release.values()):
        if not release["evidence_url"] or not release["verification_note"] or not (release["date"] or release["period"]):
            raise ValueError("Release claims need explicit operator evidence and verification note")
        official_url(release["evidence_url"], request["provider"])
        if release["date"]:
            dt.date.fromisoformat(release["date"])
    return request


def archive_root(path):
    root = Path(path).expanduser()
    if not root.is_absolute():
        raise ValueError("Archive directory must be explicitly absolute")
    root = Path(os.path.abspath(root))
    if root.resolve() != root:
        raise ValueError("Archive path aliases/symlinks are forbidden")
    if root.is_relative_to(ROOT.resolve()):
        raise ValueError("Archive must be outside the project checkout")
    for parent in (root, *root.parents):
        if parent.is_symlink() or (parent / ".git").exists():
            raise ValueError("Archive cannot be in a Git worktree or symlink")
    return root


def inside(root, relative):
    return provenance.safe_path(relative, root)


def filename(value):
    if (not value or value in (".", "..") or len(value) > 240
            or any(ch in value for ch in ("/", "\\", ":", "\x00"))
            or any(ord(ch) < 32 for ch in value)):
        raise ValueError("Unsafe original filename")
    return value


def record_seal(record):
    record = copy.deepcopy(record)
    record.pop("record_id", None)
    record["record_id"] = "sha256-" + digest(provenance.canonical(record))
    return record


def validate_record(record):
    schema_check(record, provenance.read_json(RECORD_SCHEMA))
    validate_request(record["request"])
    if record != record_seal(record) or record["request_sha256"] != digest(provenance.canonical(record["request"])):
        raise ValueError("Capture record identity conflict")
    start = utc(record["started_at_utc"])
    outcome, source = record["outcome"], record["source"]
    if record["transport"] == "LOCAL_IMPORT" and record["retrieved_at_utc"] is not None:
        raise ValueError("Local import cannot establish original retrieval time")
    if record["retrieved_at_utc"]:
        retrieved = utc(record["retrieved_at_utc"])
        if retrieved < start:
            raise ValueError("Retrieval precedes capture")
        if record["request"]["release"]["date"] and retrieved.date() < dt.date.fromisoformat(record["request"]["release"]["date"]):
            raise ValueError("Retrieval precedes claimed release date")
    if outcome == "STARTED":
        if (record["completed_at_utc"] is not None or record["start_record_id"] is not None
                or record["retrieved_at_utc"] is not None or any(v is not None for v in source.values())):
            raise ValueError("Invalid start event")
    else:
        if not record["completed_at_utc"] or not record["start_record_id"]:
            raise ValueError("Final record needs completion and start identity")
        completed = utc(record["completed_at_utc"])
        if completed < start or (record["retrieved_at_utc"] and completed < utc(record["retrieved_at_utc"])):
            raise ValueError("Invalid capture chronology")
    if source["original_filename"] is not None:
        filename(source["original_filename"])
    expected_basis = "UNKNOWN" if all(v is None for v in record["request"]["release"].values()) else "OPERATOR_ATTESTATION_NOT_AUTOMATED_VERIFICATION"
    if record["release_verification_basis"] != expected_basis:
        raise ValueError("Release verification must retain its actual evidence scope")
    complete = outcome in ("VALIDATED", "VALIDATION_FAILED")
    if complete:
        prefix = "snapshots" if outcome == "VALIDATED" else "quarantine"
        if (source["sha256"] is None or source["byte_count"] is None
                or source["snapshot_id"] != "sha256-" + source["sha256"]
                or source["snapshot_path"] != f"{prefix}/sha256/{source['sha256']}"
                or source["original_filename"] is None or source["filename_basis"] is None):
            raise ValueError("Snapshot identity/path conflict")
        if record["transport"] == "HTTPS_DOWNLOAD" and record["retrieved_at_utc"] is None:
            raise ValueError("Completed download requires actual retrieval time")
        if record["validation"]["state"] != ("PASSED" if outcome == "VALIDATED" else "FAILED"):
            raise ValueError("Validation/outcome disagreement")
        if (record["validation"]["coverage"] is not None) != (outcome == "VALIDATED"):
            raise ValueError("Failed files cannot claim validated coverage")
        if outcome == "VALIDATED":
            c = record["validation"]["coverage"]
            freq = record["request"]["validation_contract"]["frequency"]
            first, last = (provenance.period_index(c[k], freq) for k in ("first_period", "last_period"))
            blanks = [provenance.period_index(p, freq) for p in c["excluded_blank_periods"]]
            if (last - first + 1 != c["observation_count"] or c["internal_missing_count"] != 0
                    or c["grid_count"] != c["observation_count"] + len(blanks)
                    or len(set(blanks)) != len(blanks)
                    or sum(i < first for i in blanks) != c["leading_missing_count"]
                    or sum(i > last for i in blanks) != c["trailing_missing_count"]
                    or any(first <= i <= last for i in blanks)):
                raise ValueError("Capture coverage/missingness disagreement")
    elif any(source[k] is not None for k in ("sha256", "byte_count", "snapshot_id", "snapshot_path")) or record["validation"]["state"] != "NOT_RUN":
        raise ValueError("Incomplete transfers must not reference a completed snapshot")
    return record


def atomic_publish(temp, target, allow_identical=False):
    """Same-filesystem no-clobber atomic publication; never use replace/rename."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(temp, target)
    except FileExistsError:
        if not allow_identical or target.is_symlink() or target.stat().st_size != temp.stat().st_size or target.read_bytes() != temp.read_bytes():
            raise ValueError("Conflicting existing immutable identifier")
    return target


def write_record(root, record, final=False):
    validate_record(record)
    relative = ("manifests" if final else "events") + "/" + record["capture_id"] + ".json"
    target = inside(root, relative)
    temp = inside(root, ".staging/record-" + uuid.uuid4().hex + ".part")
    temp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temp.open("xb") as stream:
            stream.write((json.dumps(record, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        return atomic_publish(temp, target)
    finally:
        if temp.exists():
            temp.unlink()


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official_url(newurl, self.provider)  # Check BEFORE contacting redirect host.
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_official(url, provider):
    official_url(url, provider)
    request = urllib.request.Request(url, headers={"User-Agent": "YSEFinance-AESM-research-capture/0.1", "Accept-Encoding": "identity"})
    return urllib.request.build_opener(OfficialRedirect(provider)).open(request, timeout=45)


def coverage(rows, frequency, minimum):
    """Rows are (canonical period, value or None); retain all missing labels."""
    if not rows:
        raise ValueError("No source observations")
    indices = [provenance.period_index(period, frequency) for period, _ in rows]
    if any(b != a + 1 for a, b in zip(indices, indices[1:])):
        raise ValueError("Duplicate, unordered or missing grid period")
    valid = [(period, index) for (period, value), index in zip(rows, indices) if value is not None]
    if len(valid) < minimum:
        raise ValueError("Insufficient observations")
    low, high = valid[0][1], valid[-1][1]
    blanks = [(period, index) for (period, value), index in zip(rows, indices) if value is None]
    if any(low <= index <= high for _, index in blanks):
        raise ValueError("Internal missing observation")
    return {"first_period": valid[0][0], "last_period": valid[-1][0], "observation_count": len(valid),
            "grid_count": len(rows), "leading_missing_count": sum(i < low for _, i in blanks),
            "trailing_missing_count": sum(i > high for _, i in blanks), "internal_missing_count": 0,
            "excluded_blank_periods": [p for p, _ in blanks]}


def numeric(text):
    if text.strip() in ("", "..", "NA", "na", "n.a.", "-", "*"):
        return None
    number = float(text.replace(",", ""))
    if not math.isfinite(number):
        raise ValueError("Nonfinite source observation")
    return number


def validate_abs_xlsx(path, contract):
    # Generic future coverage; deliberately does not reuse frozen E12 endpoints.
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 10000 or sum(m.file_size for m in members) > MAXIMUM_BYTES:
            raise ValueError("Workbook expanded size exceeds safety limit")
    book = e04.read_workbook(path)
    cells = book["sheets"].get("Data1", {})
    if book["sheets"].get("Index", {}).get("B6") != contract["table"]:
        raise ValueError("Wrong source table")
    if any(cells.get("A" + str(row)) != label for row, label in e12.LABELS.items()):
        raise ValueError("Changed ABS metadata layout")
    columns = [a[:-2] for a, value in cells.items() if re.fullmatch(r"[A-Z]+10", a) and value == contract["series_id"]]
    if len(columns) != 1:
        raise ValueError("Exact source Series ID missing or duplicated")
    col = columns[0]
    expected = {1: contract["description"], 2: contract["unit"], 3: contract["seasonal_adjustment"],
                4: contract["data_type"], 5: "Quarter" if contract["frequency"] == "quarterly" else "Month",
                6: "3" if contract["frequency"] == "quarterly" else "1"}
    if any(cells.get(col + str(row)) != value for row, value in expected.items()):
        raise ValueError("Source metadata contract changed")
    row_numbers = sorted({int(re.search(r"\d+$", address).group()) for address, value in cells.items()
                          if value and re.fullmatch(r"(?:A|" + col + r")\d+", address)
                          and int(re.search(r"\d+$", address).group()) > 10})
    date_contract = {"frequency": expected[5]}
    rows = [(e12.parse_date(cells.get("A" + str(row)), date_contract)[2], numeric(cells.get(col + str(row), ""))) for row in row_numbers]
    result = coverage(rows, contract["frequency"], contract["minimum_observations"])
    declared = (e12.parse_date(cells.get(col + "7"), date_contract)[2],
                e12.parse_date(cells.get(col + "8"), date_contract)[2], int(cells.get(col + "9", "")))
    if declared != (result["first_period"], result["last_period"], result["observation_count"]):
        raise ValueError("Workbook header/observed coverage disagreement")
    return result


def validate_rba_csv(path, contract):
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    headers = [i for i, row in enumerate(rows[:40]) if row and row[0].strip().lower() == "series id"]
    if len(headers) != 1:
        raise ValueError("Missing/ambiguous RBA Series ID row")
    header = headers[0]
    columns = [i for i, value in enumerate(rows[header]) if value.strip() == contract["series_id"]]
    if len(columns) != 1:
        raise ValueError("Missing/duplicated RBA Series ID")
    column = columns[0]
    metadata = {row[0].strip().lower().replace(" ", "_"): row[column].strip() for row in rows[:header] if row and len(row) > column}
    if contract["description"] not in (metadata.get("title"), metadata.get("description")) or metadata.get("units") != contract["unit"]:
        raise ValueError("Wrong RBA description/units")
    if metadata.get("frequency", "").lower() != contract["frequency"]:
        raise ValueError("Wrong RBA frequency")
    if contract["seasonal_adjustment"] is not None and metadata.get("type") != contract["seasonal_adjustment"]:
        raise ValueError("Wrong RBA adjustment")
    observations = []
    for row in rows[header + 1:]:
        if not row or not row[0].strip():
            continue
        date = None
        for fmt in ("%d-%b-%Y", "%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%b %Y", "%Y-%m"):
            try:
                date = dt.datetime.strptime(row[0].strip(), fmt)
                break
            except ValueError:
                pass
        if date is None or (contract["frequency"] == "quarterly" and date.month not in (3, 6, 9, 12)) or len(row) <= column:
            raise ValueError("Unrecognized RBA date/row; no silent skipping")
        period = f"{date.year}-Q{date.month // 3}" if contract["frequency"] == "quarterly" else f"{date.year}-{date.month:02}"
        observations.append((period, numeric(row[column])))
    return coverage(observations, contract["frequency"], contract["minimum_observations"])


def validate_sdmx_csv(path, contract):
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    observations = []
    for row in rows:
        if any(row.get(k) != v for k, v in contract["dimensions"].items()):
            raise ValueError("Wrong SDMX source dimensions")
        # CSV lacks full DSD metadata: dimensions/units are operator contracts,
        # not a claim that this parser independently reverified the DSD.
        observations.append((row["TIME_PERIOD"], numeric(row["OBS_VALUE"])))
    return coverage(observations, contract["frequency"], contract["minimum_observations"])


def validate_source(path, request):
    contract = request["validation_contract"]
    adapters = {"ABS_XLSX": validate_abs_xlsx, "RBA_CSV": validate_rba_csv, "ABS_SDMX_CSV": validate_sdmx_csv}
    return adapters[contract["adapter"]](path, contract)


def start_record(request, capture_id, transport):
    return record_seal({
        "schema_version": "0.2.0", "capture_id": capture_id, "outcome": "STARTED",
        "started_at_utc": now(), "completed_at_utc": None, "retrieved_at_utc": None,
        "transport": transport, "request": copy.deepcopy(request), "request_sha256": digest(provenance.canonical(request)),
        "start_record_id": None,
        "source": dict.fromkeys(("original_filename", "filename_basis", "sha256", "byte_count", "snapshot_id", "snapshot_path")),
        "validation": {"state": "NOT_RUN", "coverage": None, "error_type": None, "note": None},
        "release_verification_basis": "UNKNOWN" if all(v is None for v in request["release"].values()) else "OPERATOR_ATTESTATION_NOT_AUTOMATED_VERIFICATION",
        "historical_classification": "LATEST_REVISED_DATA_CAPTURE_NOT_HISTORICAL_FIRST_RELEASE", "point_in_time_eligible": False,
        "approval": dict.fromkeys(("indicator_approved", "publication_approved", "production_pinned", "scoring_approved", "weights_approved"), False),
        "composite_release_statuses": dict(provenance.HOLD), "composite_scores": dict.fromkeys(provenance.HOLD),
        "implementation_sha256": text_digest(__file__), "record_schema_sha256": text_digest(RECORD_SCHEMA)})


def capture(request, archive_dir, local_file=None, dry_run=False, capture_id=None):
    validate_request(request)
    root = archive_root(archive_dir)
    if dry_run:
        return {"dry_run": True, "transport": "LOCAL_IMPORT" if local_file else "HTTPS_DOWNLOAD",
                "provider": request["provider"], "official_source_url": request["official_source_url"],
                "request": copy.deepcopy(request),
                "archive_layout": ["events/<capture_id>.json", "snapshots/sha256/<source_hash>",
                                   "quarantine/sha256/<source_hash>", "manifests/<capture_id>.json"],
                "actions": ["Append STARTED event", "Stream bounded source to .staging", "Validate source contract",
                            "Atomically publish content-addressed snapshot or quarantine", "Append terminal manifest"],
                "retrieved_at_utc": None, "snapshot_sha256": None, "writes_performed": False}
    capture_id = capture_id or uuid.uuid4().hex
    if not re.fullmatch(r"[a-f0-9]{32}", capture_id):
        raise ValueError("Invalid capture ID")
    if any(inside(root, kind + "/" + capture_id + ".json").exists() for kind in ("events", "manifests")):
        raise ValueError("Capture ID already used; never overwrite")
    start = start_record(request, capture_id, "LOCAL_IMPORT" if local_file else "HTTPS_DOWNLOAD")
    write_record(root, start)  # Durable audit intent before transfer/validation.
    stage = inside(root, ".staging/" + capture_id + ".part")
    stage.parent.mkdir(parents=True, exist_ok=True)
    record = copy.deepcopy(start)
    record["start_record_id"] = start["record_id"]
    stage_owned = False
    try:
        if local_file is not None:
            original = filename(Path(local_file).name)
            record["source"].update(original_filename=original, filename_basis="LOCAL_BASENAME")
            response = Path(local_file).open("rb")
        else:
            response = open_official(request["official_source_url"], request["provider"])
        with ExitStack() as stack:
            incoming = stack.enter_context(response)
            outgoing = stack.enter_context(stage.open("xb"))
            stage_owned = True
            expected_length = None
            if local_file is None:
                official_url(incoming.geturl(), request["provider"])
                if incoming.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
                    raise ValueError("Unexpected encoded response")
                if incoming.headers.get("Content-Length") is not None:
                    expected_length = int(incoming.headers["Content-Length"])
                    if not 0 <= expected_length <= request["maximum_bytes"]:
                        raise ValueError("Invalid response length")
                message = Message()
                message["Content-Disposition"] = incoming.headers.get("Content-Disposition", "")
                original = message.get_filename()
                basis = "CONTENT_DISPOSITION" if original else "URL_PATH"
                original = original or unquote(urlsplit(incoming.geturl()).path.rsplit("/", 1)[-1])
                record["source"].update(original_filename=filename(original), filename_basis=basis)
            count = 0
            hasher = hashlib.sha256()
            while True:
                chunk = incoming.read(min(65536, request["maximum_bytes"] - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > request["maximum_bytes"]:
                    raise ValueError("Response size limit exceeded")
                outgoing.write(chunk)
                hasher.update(chunk)
            if expected_length is not None and count != expected_length:
                raise ValueError("Incomplete response length")
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if local_file is None:
            record["retrieved_at_utc"] = now()  # Never CLI/user-supplied or inferred.
    except Exception as error:
        record["outcome"] = "TRANSFER_FAILED"
        record["validation"].update(error_type=type(error).__name__, note="Transfer failed; partial bytes are not a valid snapshot.")
        record["completed_at_utc"] = now()
        record = record_seal(record)
        write_record(root, record, final=True)
        if stage_owned and stage.exists():
            stage.unlink()
        return record
    try:
        result = validate_source(stage, request)
        record["outcome"] = "VALIDATED"
        record["validation"].update(state="PASSED", coverage=result,
            note="Research capture validation only; metadata contract does not approve indicator or first-release history.")
        if request["validation_contract"]["adapter"] == "ABS_SDMX_CSV":
            record["validation"]["note"] += " SDMX dimensions/observations checked; description, unit and adjustment are operator-specified, pending independent DSD review."
    except Exception as error:
        record["outcome"] = "VALIDATION_FAILED"
        record["validation"].update(state="FAILED", error_type=type(error).__name__,
            note="Source contract rejected received bytes. Retained in quarantine, never approved source data.")
    checksum = hasher.hexdigest()
    if stage.stat().st_size != count or digest(stage.read_bytes()) != checksum:
        raise ValueError("Staged source changed during validation; capture remains pending")
    prefix = "snapshots" if record["outcome"] == "VALIDATED" else "quarantine"
    relative = f"{prefix}/sha256/{checksum}"
    atomic_publish(stage, inside(root, relative), allow_identical=True)
    record["source"].update(sha256=checksum, byte_count=count, snapshot_id="sha256-" + checksum, snapshot_path=relative)
    record["completed_at_utc"] = now()
    record = record_seal(record)
    write_record(root, record, final=True)  # Snapshot published completely first.
    stage.unlink()
    return record


def inspect_archive(archive_dir):
    root = archive_root(archive_dir)
    starts, finals = {}, {}
    for kind, records in (("events", starts), ("manifests", finals)):
        directory = inside(root, kind)
        for path in sorted(directory.glob("*.json")):
            path = inside(root, kind + "/" + path.name)
            record = validate_record(provenance.read_json(path))
            if path.stem != record["capture_id"] or (kind == "events") != (record["outcome"] == "STARTED"):
                raise ValueError("Capture filename/state conflict")
            records[record["capture_id"]] = record
    for capture_id, record in finals.items():
        start = starts.get(capture_id)
        if not start or record["start_record_id"] != start["record_id"] or record["request"] != start["request"] or record["started_at_utc"] != start["started_at_utc"] or record["transport"] != start["transport"]:
            raise ValueError("Audit start/final linkage conflict")
        if record["source"]["snapshot_path"]:
            path = inside(root, record["source"]["snapshot_path"])
            if not path.is_file() or path.stat().st_size != record["source"]["byte_count"] or digest(path.read_bytes()) != record["source"]["sha256"]:
                raise ValueError("Missing or conflicting immutable snapshot")
    return {"captures": len(starts), "terminal_manifests": len(finals),
            "pending_capture_ids": sorted(set(starts) - set(finals)),
            "outcomes": {key: record["outcome"] for key, record in finals.items()}}


def recover(archive_dir, capture_id, confirm_stopped=False):
    """Append interruption result; leave partial/orphan bytes for investigation."""
    root = archive_root(archive_dir)
    if not confirm_stopped or not re.fullmatch(r"[a-f0-9]{32}", capture_id):
        raise ValueError("Explicit confirmation that the capture process stopped is required")
    report = inspect_archive(root)
    if capture_id not in report["pending_capture_ids"]:
        raise ValueError("Only pending captures can be recovered")
    start = provenance.read_json(inside(root, "events/" + capture_id + ".json"))
    record = copy.deepcopy(start)
    record.update(outcome="INTERRUPTED", completed_at_utc=now(), start_record_id=start["record_id"])
    record["validation"].update(error_type="InterruptedCapture", note="Operator confirmed process stopped; partial/orphan bytes require inspection. No completed source snapshot certified.")
    record = record_seal(record)
    write_record(root, record, final=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "inspect", "recover"))
    parser.add_argument("--archive-dir", default=os.environ.get("AESM_VINTAGE_ARCHIVE"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--local-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--capture-id")
    parser.add_argument("--confirm-stopped", action="store_true")
    args = parser.parse_args()
    if not args.archive_dir:
        parser.error("Set --archive-dir or AESM_VINTAGE_ARCHIVE to an absolute path outside Git")
    if args.command != "capture" and (args.dry_run or args.local_file or args.config):
        parser.error("--dry-run, --local-file and --config apply only to capture; recovery is never a dry run")
    if args.command == "inspect" and (args.capture_id or args.confirm_stopped):
        parser.error("inspect does not accept recovery controls")
    if args.command == "capture" and args.confirm_stopped:
        parser.error("--confirm-stopped applies only to recovery")
    if args.command == "capture":
        if not args.config:
            parser.error("capture requires --config")
        result = capture(provenance.read_json(args.config), args.archive_dir, args.local_file, args.dry_run, args.capture_id)
    elif args.command == "inspect":
        result = inspect_archive(args.archive_dir)
    else:
        result = recover(args.archive_dir, args.capture_id or "", args.confirm_stopped)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    if result.get("outcome") in ("TRANSFER_FAILED", "VALIDATION_FAILED", "INTERRUPTED"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
