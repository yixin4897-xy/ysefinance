"""Research-only E04/E12 provenance pilot; standard library, offline, no scores.

Schema validation is structural. --verify-sources also reproduces the frozen
pilot from local workbooks and existing candidate contracts. No production path.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import aehi_e04_import as e04
import aehi_e12_import as e12

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = "docs/aesm-provenance-manifest-schema-v0.1.json"
STORE_PATH = "data-candidates/provenance/manifests"
MASTER_PATH = "docs/aesm-master-indicator-contract-v0.1.json"
EVIDENCE_COMMIT = "6dc970f614f5199f9baa929b5c5c7d1bcf05106a"
HOLD = dict.fromkeys(("AEHI", "AESI", "ASFI"), "HOLD")


def read_json(path):
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("Nonfinite JSON value: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=pairs, parse_constant=invalid)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def seal(manifest):
    """Return a new content-addressed manifest; no mutation or output."""
    data = copy.deepcopy(manifest)
    data.pop("manifest_id", None)
    digest = hashlib.sha256(canonical(data)).hexdigest()
    data["manifest_id"] = f"{data['indicator'].lower()}-{data['methodological_variant']['id'].lower()}-{digest}"
    return data


def validate_schema(value, schema, location="$ "):
    """Validate the explicit JSON Schema subset used by V0.1, fail closed.

    No external schema resolution or dependencies. Public schema is also usable
    with standard JSON Schema Draft 2020-12 validators.
    """
    supported = {"$schema", "$id", "title", "type", "properties", "required",
                 "additionalProperties", "items", "minItems", "uniqueItems",
                 "minimum", "minLength", "pattern", "enum", "const", "anyOf"}
    if set(schema) - supported:
        raise ValueError("Unsupported schema keyword at " + location)
    if "anyOf" in schema:
        for choice in schema["anyOf"]:
            try:
                validate_schema(value, choice, location)
                break
            except ValueError:
                pass
        else:
            raise ValueError("No allowed schema type at " + location)
    types = {"object": lambda v: isinstance(v, dict),
             "array": lambda v: isinstance(v, list),
             "string": lambda v: isinstance(v, str),
             "integer": lambda v: type(v) is int,
             "boolean": lambda v: type(v) is bool,
             "null": lambda v: v is None}
    if "type" in schema:
        kind = schema["type"]
        if kind not in types or not types[kind](value):
            raise ValueError("Wrong type at " + location)
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError("Restricted constant changed at " + location)
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Unknown enum at " + location)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValueError("Empty string at " + location)
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ValueError("Invalid pattern at " + location)
    if type(value) is int and value < schema.get("minimum", value):
        raise ValueError("Below minimum at " + location)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError("Too few items at " + location)
        if schema.get("uniqueItems") and len({canonical(v) for v in value}) != len(value):
            raise ValueError("Duplicate items at " + location)
        for index, child in enumerate(value):
            validate_schema(child, schema["items"], f"{location}[{index}]")
    if isinstance(value, dict):
        if set(schema.get("required", [])) - set(value):
            raise ValueError("Required field absent at " + location)
        properties = schema.get("properties", {})
        for key, child in value.items():
            child_schema = properties.get(key, schema.get("additionalProperties"))
            if child_schema is False or child_schema is None:
                raise ValueError("Unexpected field at " + location + key)
            validate_schema(child, child_schema, location + key + ".")


def safe_path(relative, root=ROOT):
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or ":" in relative or relative.startswith("/")
            or any(p in (".", "..", "") for p in relative.split("/"))):
        raise ValueError("Only safe repository-relative paths allowed")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes checkout")
    for segment in (path, *path.parents):
        if segment == root:
            break
        if segment.is_symlink():
            raise ValueError("Symlink locators are forbidden")
    return path


def period_index(period, frequency):
    pattern = r"(\d{4})-Q([1-4])" if frequency == "quarterly" else r"(\d{4})-(0[1-9]|1[0-2])"
    match = re.fullmatch(pattern, period)
    if not match:
        raise ValueError("Invalid observation period")
    return int(match[1]) * (4 if frequency == "quarterly" else 12) + int(match[2])


def validate_manifest(manifest, root=ROOT):
    validate_schema(manifest, read_json(root / SCHEMA_PATH))
    if manifest != seal(manifest):
        raise ValueError("Conflicting or altered manifest identity")
    expected_roles = set(e04.SPECS) if manifest["indicator"] == "E04" else {"track_" + manifest["methodological_variant"]["id"]}
    sources = manifest["sources"]
    if {s["role"] for s in sources} != expected_roles or len(sources) != len(expected_roles):
        raise ValueError("Wrong or duplicated source roles")
    for source in sources:
        role = source["role"]
        if manifest["indicator"] == "E04":
            spec = e04.SPECS[role]
            expected = ("ABS", spec[1], "quarterly", spec[3], spec[4])
        else:
            track = e12.CONTRACTS[manifest["methodological_variant"]["id"]]
            expected = ("ABS", track["series_id"], "quarterly" if track["frequency"] == "Quarter" else "monthly", "Percent", "Seasonally Adjusted")
        actual = (source["provider"], source["series_id"], source["measurement"]["frequency"],
                  source["measurement"]["unit"], source["measurement"]["seasonal_adjustment"])
        if actual != expected:
            raise ValueError("Source series/variant measurement contract disagrees")
        if source["source_vintage_id"] != source["provider"].lower() + "-sha256-" + source["source_sha256"]:
            raise ValueError("Conflicting source-vintage identity")
        for key in ("official_source_url", "official_reference_url"):
            if source[key] is not None:
                url = urlsplit(source[key])
                hosts = {"www.abs.gov.au", "data.api.abs.gov.au"} if source["provider"] == "ABS" else {"www.rba.gov.au"}
                if url.scheme != "https" or url.hostname not in hosts or url.username or url.password or url.port:
                    raise ValueError("Source URL is outside the official provider")
        if source["archive_relative_path"] != "research-inputs/vintage-archive/sha256/" + source["source_sha256"] + ".xlsx":
            raise ValueError("Archive path must be content addressed")
        local = safe_path(source["source_local_path"], root)
        if local.name != source["source_filename"] or not source["source_local_path"].startswith("research-inputs/"):
            raise ValueError("Invalid source locator")
        safe_path(source["archive_relative_path"], root)
        release = source["release"]
        if (release["date"] is None) != (release["date_status"] == "UNKNOWN"):
            raise ValueError("Release date status disagrees")
        if release["date"]:
            dt.date.fromisoformat(release["date"])
        if (release["retrieved_at_utc"] is None) != (release["retrieval_status"] == "UNKNOWN"):
            raise ValueError("Retrieval timestamp status disagrees")
        if release["retrieved_at_utc"]:
            timestamp = dt.datetime.fromisoformat(release["retrieved_at_utc"].replace("Z", "+00:00"))
            if timestamp.utcoffset() != dt.timedelta(0):
                raise ValueError("Retrieval time must explicitly be UTC")
            if release["date"] and timestamp.date() < dt.date.fromisoformat(release["date"]):
                raise ValueError("Retrieval cannot precede the recorded release")
        if (source["official_source_url"] is None) != (source["official_source_url_status"] == "UNKNOWN"):
            raise ValueError("Official URL status disagrees")
        coverage = source["coverage"]
        freq = source["measurement"]["frequency"]
        start, end = (period_index(coverage[k], freq) for k in ("first_period", "last_period"))
        if end - start + 1 != coverage["observation_count"] + coverage["internal_missing_count"]:
            raise ValueError("Coverage count disagrees with endpoints")
        if coverage["grid_count"] != sum(coverage[k] for k in ("observation_count", "internal_missing_count", "leading_missing_count", "trailing_missing_count")):
            raise ValueError("Missingness does not reconcile to grid")
        if len(coverage["excluded_blank_periods"]) != sum(coverage[k] for k in ("internal_missing_count", "leading_missing_count", "trailing_missing_count")):
            raise ValueError("Missing-period list disagrees")
        missing = [period_index(p, freq) for p in coverage["excluded_blank_periods"]]
        actual_counts = (sum(p < start for p in missing), sum(p > end for p in missing),
                         sum(start <= p <= end for p in missing))
        if actual_counts != tuple(coverage[k] for k in ("leading_missing_count", "trailing_missing_count", "internal_missing_count")):
            raise ValueError("Missing-period positions disagree with classifications")
    output = manifest["output_coverage"]
    if period_index(output["last_period"], output["frequency"]) - period_index(output["first_period"], output["frequency"]) + 1 != output["observation_count"]:
        raise ValueError("Output coverage disagrees")
    for evidence in manifest["evidence"]:
        safe_path(evidence["path"], root)
    return manifest


def check_store(manifests, root=ROOT):
    """Detect duplicate IDs and conflicting metadata reuse without source files."""
    ids, sources = set(), {}
    for manifest in manifests:
        validate_manifest(manifest, root)
        if manifest["manifest_id"] in ids:
            raise ValueError("Duplicate manifest identity")
        ids.add(manifest["manifest_id"])
        for source in manifest["sources"]:
            key = (source["provider"], source["series_id"], source["source_vintage_id"])
            if key in sources and sources[key] != source:
                raise ValueError("Conflicting reuse of source-vintage metadata")
            sources[key] = source


def read_store(root=ROOT):
    directory = safe_path(STORE_PATH, root)
    manifests = []
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink():
            raise ValueError("Manifest symlinks are forbidden")
        manifest = read_json(path)
        if path.stem != manifest.get("manifest_id"):
            raise ValueError("Manifest filename/identity mismatch")
        manifests.append(manifest)
    check_store(manifests, root)
    return manifests


def append_manifest(manifest, root=ROOT):
    """Exclusive append in the fixed research store; identical reruns do not write.

    A short-lived exclusive lock serializes conflict checking and creation.
    Never repairs or overwrites an old manifest, even if malformed.
    """
    validate_manifest(manifest, root)
    directory = safe_path(STORE_PATH, root)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory.parent / ".append.lock"
    with lock.open("x", encoding="utf-8"):
        pass
    try:
        existing = read_store(root)
        same = next((m for m in existing if m["manifest_id"] == manifest["manifest_id"]), None)
        if same is not None:
            if same != manifest:
                raise ValueError("Conflicting manifest ID reuse")
            return directory / (manifest["manifest_id"] + ".json"), False
        check_store(existing + [manifest], root)
        path = directory / (manifest["manifest_id"] + ".json")
        payload = json.dumps(manifest, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
        with path.open("x", encoding="utf-8") as stream:
            stream.write(payload)
        return path, True
    finally:
        lock.unlink()


def evidence_record(path):
    raw = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "hash_basis": "UTF8_TEXT_LF_NORMALIZED"}


def source_record(role, source, coverage, indicator, track=None):
    e04_source = indicator == "E04"
    digest = source["source_file_sha256"] if e04_source else source["sha256"]
    filename = Path(source["source_file"]).name
    measurement = {
        "frequency": "quarterly" if e04_source or track["frequency"] == "Quarter" else "monthly",
        "unit": source["unit"] if e04_source else track["unit"],
        "seasonal_adjustment": source["seasonal_adjustment"] if e04_source else track["seasonal_adjustment"],
        "data_type": source["data_type"] if e04_source else "PERCENT",
        "table": source["table"], "sheet": source["sheet"], "metadata_range": source["metadata_range"],
        "observation_date_convention": "ABS_REFERENCE_MONTH_FIRST_DAY_NOT_PUBLICATION_DATE",
        "reference_year": {"value": None, "status": "UNKNOWN" if e04_source else "NOT_APPLICABLE_TO_ANNUAL_RATE",
                           "official_release_reference_year": "2023-24" if e04_source and role == "consumption_volume" else None,
                           "applies_to_this_snapshot": False},
    }
    return {
        "role": role, "provider": "ABS", "series_id": source["series_id"] if e04_source else track["series_id"],
        "description": source["description"] if e04_source else track["description"],
        "source_filename": filename, "source_sha256": digest, "source_vintage_id": "abs-sha256-" + digest,
        "vintage_identity_basis": "CONTENT_ADDRESSED_BYTES_NOT_FIRST_RELEASE_VINTAGE",
        "official_source_url": None if e04_source else source["source_url"],
        "official_source_url_status": "UNKNOWN" if e04_source else "RECORDED_PRIOR_SOURCE_REVIEW",
        "official_reference_url": (None if role == "population" else "https://www.abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product/latest-release") if e04_source else e12.RELEASE,
        "source_local_path": source["source_file"],
        "archive_relative_path": "research-inputs/vintage-archive/sha256/" + digest + ".xlsx",
        "archive_status": "NOT_ARCHIVED_BY_PILOT",
        "release": {"period": None if e04_source else source["release_vintage"],
                    "date": source["publication_date"],
                    "date_status": "UNKNOWN" if e04_source else "RECORDED_PRIOR_SOURCE_REVIEW",
                    "retrieved_at_utc": None, "retrieval_status": "UNKNOWN", "availability_timestamp_utc": None},
        "measurement": measurement, "coverage": coverage,
        "validation": {"state": "LOCAL_HASH_METADATA_COVERAGE_CHECKED",
                       "official_authenticity": "UNKNOWN" if e04_source else "PRIOR_REVIEW_RECORDED_NOT_REVERIFIED",
                       "fresh_official_download_verified": False,
                       "evidence_path": f"data-candidates/aehi-{indicator.lower()}-local-review.json"},
    }


def build_pilot():
    master = read_json(ROOT / MASTER_PATH)
    if master["release_controls"]["composite_release_statuses"] != HOLD:
        raise ValueError("Master contract HOLD controls required")
    candidates = {"E04": e04.build_candidate(ROOT / "research-inputs/e04"),
                  "E12": e12.build_candidate(ROOT / "research-inputs/e12")}
    manifests = []
    for indicator, candidate in candidates.items():
        candidate_path = f"data-candidates/aehi-{indicator.lower()}-local-review.json"
        saved = read_json(ROOT / candidate_path)
        a, b = copy.deepcopy(candidate), copy.deepcopy(saved)
        a.pop("generated_at_utc"); b.pop("generated_at_utc")
        if a != b:
            raise ValueError("Workbook/candidate disagreement; new independent review required")
        for variant in ("A", "B"):
            manifest = {
                "schema_version": "0.1.0", "indicator": indicator,
                "methodological_variant": {"id": variant, "name": "", "candidate_version": candidate["candidate_version"],
                                           "status": "CANDIDATE_ONLY_PENDING_VALIDATION", "transformations": {}},
                "historical_classification": "latest_revised_data_research", "point_in_time_eligible": False,
                "identity_basis": "SHA256_CANONICAL_JSON_EXCLUDING_MANIFEST_ID", "sources": [],
                "evidence": [evidence_record(p) for p in [MASTER_PATH, candidate_path, SCHEMA_PATH,
                              "scripts/aesm_provenance.py", "scripts/aehi_e04_import.py"] +
                             (["scripts/aehi_e12_import.py"] if indicator == "E12" else [])],
                "evidence_commit": EVIDENCE_COMMIT,
                "validation_state": "LOCAL_SNAPSHOT_CHECKED_NOT_PUBLICATION_APPROVAL",
                "approval": dict.fromkeys(("indicator_definition_approved", "publication_approved", "production_pinned", "scoring_approved", "weights_approved"), False),
                "composite_release_statuses": dict(HOLD), "composite_scores": dict.fromkeys(HOLD),
                "limitations": ["Latest-revised snapshot, not an as-first-published historical vintage.",
                                "Original retrieval timestamp and precise historical availability remain unknown.",
                                "Local byte/metadata checks do not grant source authenticity or publication approval.",
                                "Content-addressed archive paths are retention targets; this pilot copies no workbook."],
            }
            if indicator == "E04":
                for role, source in candidate["sources"].items():
                    count = source["observation_count"]
                    coverage = {"first_period": source["first_period"].replace(" Q", "-Q"),
                                "last_period": source["last_period"].replace(" Q", "-Q"),
                                "observation_count": count, "grid_count": count,
                                "leading_missing_count": 0, "trailing_missing_count": 0,
                                "internal_missing_count": 0, "excluded_blank_periods": []}
                    manifest["sources"].append(source_record(role, source, coverage, indicator))
                method = "method_" + variant.lower()
                manifest["methodological_variant"].update(
                    name="Closing ERP sensitivity" if variant == "A" else "Average adjacent closing ERP primary research candidate",
                    transformations={k: candidate["methodology"][k] for k in ("deflator", "real_income_aud_millions", method, "growth")})
                manifest["output_coverage"] = {"first_period": "1981-Q3" if variant == "A" else "1981-Q4",
                    "last_period": "2026-Q1", "observation_count": candidate[f"method_{variant.lower()}_growth_count"],
                    "frequency": "quarterly", "unit": "% non-annualised QoQ",
                    "meaning": "Derived growth only; common level grid ends before June 2026 because ERP is unavailable."}
                manifest["limitations"] += candidate["methodology"]["limitations"]
            else:
                track = candidate["tracks"][variant]
                coverage = {k: v for k, v in track["validation"].items() if k in (
                    "first_period", "last_period", "observation_count", "grid_count", "leading_missing_count",
                    "trailing_missing_count", "internal_missing_count", "excluded_blank_periods")}
                manifest["sources"] = [source_record("track_" + variant, track["source"], coverage, indicator, track)]
                manifest["methodological_variant"].update(name="Quarterly annual trimmed mean" if variant == "A" else "Complete-monthly annual trimmed mean",
                    transformations={"value": "Copy published annual percentage change; no splicing, filling, averaging or substitution."})
                manifest["output_coverage"] = {k: coverage[k] for k in ("first_period", "last_period", "observation_count")}
                manifest["output_coverage"].update(frequency="quarterly" if variant == "A" else "monthly", unit="Percent annual change", meaning="Independent source track; blank boundary cells excluded, not forecast or zero.")
                manifest["limitations"] += candidate["outstanding_validation_issues"]
            manifests.append(seal(manifest))
    check_store(manifests)
    return manifests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pilot", "validate"))
    parser.add_argument("--append", action="store_true", help="Exclusively append pilot metadata to fixed research directory")
    parser.add_argument("--verify-sources", action="store_true", help="Reproduce pilot metadata from local workbooks")
    args = parser.parse_args()
    if args.command == "validate" and args.append:
        parser.error("validate never writes")
    if args.command == "pilot":
        manifests = build_pilot()
        if args.append:
            for manifest in manifests:
                path, created = append_manifest(manifest)
                print("APPENDED" if created else "UNCHANGED", path.relative_to(ROOT))
    else:
        manifests = read_store()
        if not manifests:
            raise ValueError("No stored manifests")
        if args.verify_sources:
            expected = {m["manifest_id"]: m for m in build_pilot()}
            if {m["manifest_id"]: m for m in manifests} != expected:
                raise ValueError("Stored manifests differ from reproducible frozen pilot")
    print(f"Validated {len(manifests)} research manifests. All composites HOLD; no approvals granted.")


if __name__ == "__main__":
    main()
