"""Read-only validation of the frozen AESM V4.1 V0.1 draft contract.

This validates documentation integrity and HOLD safeguards, not economic validity.
Standard library only; no network, importers, publication or output files.
"""
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/aesm-master-indicator-contract-v0.1.json"
EXPECTED_CODES = {f"E{i:02}" for i in range(1, 13)} | {f"S{i:02}" for i in range(1, 9)}


def validate(contract, root=ROOT):
    """Return errors; do not mutate the contract or repository."""
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    require(contract.get("schema_version") == "0.1.0", "Unexpected draft schema")
    require(contract.get("contract_version") == "0.1.0-draft.1", "Unexpected contract version")
    require(contract.get("status") == "DRAFT_DOCUMENTATION_ONLY", "Contract must remain draft")
    controls = contract.get("release_controls", {})
    require(controls.get("composite_release_statuses") == dict.fromkeys(("AEHI", "AESI", "ASFI"), "HOLD"), "All composite statuses must remain HOLD")
    require(controls.get("composite_scores") == dict.fromkeys(("AEHI", "AESI", "ASFI")), "Composite scores must be explicit nulls")
    for key in ("publication_approved", "production_consumer_enabled", "pr_8_state_mutated"):
        require(controls.get(key) is False, f"Release control {key} must be false")
    require(controls.get("pr_8_required_state") == "DRAFT", "PR #8 must remain Draft")
    records = contract.get("indicators", [])
    codes = [r.get("code") for r in records]
    require(len(codes) == 20 and set(codes) == EXPECTED_CODES, "Exactly 20 unique dictionary indicators required")
    catalog = contract.get("evidence_catalog", {})
    require(bool(catalog), "Evidence catalog required")
    for key, evidence in catalog.items():
        path = (root / evidence.get("path", "")).resolve()
        require(evidence.get("path") == key, f"Evidence key/path mismatch: {key}")
        require(path.is_relative_to(root.resolve()), f"Evidence outside checkout: {key}")
        require(evidence.get("git_commit") == contract.get("evidence_commit"), f"Evidence commit mismatch: {key}")
        if path.is_file() and path.is_relative_to(root.resolve()):
            require(evidence.get("hash_basis") == "GIT_BLOB_BYTES", f"Explicit Git blob hash basis required: {key}")
            try:
                blob = subprocess.check_output(
                    ["git", "show", f"{evidence['git_commit']}:{key}"],
                    cwd=root, stderr=subprocess.PIPE,
                )
            except (subprocess.CalledProcessError, OSError):
                require(False, f"Committed evidence unavailable: {key}")
                continue
            require(hashlib.sha256(blob).hexdigest() == evidence.get("sha256"), f"Committed evidence hash mismatch: {key}")
            require(path.read_bytes().replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n"), f"Evidence changed; review and version required: {key}")
        else:
            require(False, f"Evidence missing: {key}")

    def check_refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.endswith("evidence_ref"):
                    require(child in catalog, f"Unknown evidence reference: {child}")
                elif key == "evidence_refs":
                    for ref in child:
                        require(ref in catalog, f"Unknown evidence reference: {ref}")
                else:
                    check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)

    check_refs(contract)
    dictionary = (root / "aesm-research.html").read_text(encoding="utf-8")
    names = dict(re.findall(r'<span class="code">(E\d{2})</span> ([^<]+)</li>', dictionary))
    names.update(dict(re.findall(r'<span class="code">(S\d{2})</span></td><td><strong>([^<]+)</strong>', dictionary)))
    names = {key: html.unescape(value) for key, value in names.items()}
    for record in records:
        code = record.get("code")
        definition = record.get("registered_definition", {})
        require(definition.get("evidence_ref") == "aesm-research.html", f"Dictionary authority lost: {code}")
        require(definition.get("text") == names.get(code), f"Registered definition/code differs from dictionary: {code}")
        require(record.get("weight") == {"status": "UNAPPROVED", "value": None}, f"Unapproved weight required: {code}")
        require(record.get("composite_definition_candidate_only") is True, f"Candidate definition guard lost: {code}")
        require(record.get("composite_contribution_allowed") is False, f"Composite contribution enabled: {code}")
        require(record.get("membership", {}).get("approved") is False, f"Membership approval invented: {code}")
        scoring = record.get("scoring", {})
        require(scoring.get("score") is None and scoring.get("normalization") is None and scoring.get("direction") is None, f"Unapproved production scoring populated: {code}")
        for field in ("definition_production", "derivation_production"):
            require(record.get("approval_state", {}).get(field) == "NO_APPROVAL_EVIDENCE", f"Production approval invented: {code}/{field}")
        for field in ("scoring", "weighting", "composite_publication"):
            require(record.get("approval_state", {}).get(field) == "NOT_APPROVED", f"Approval guard lost: {code}/{field}")
        for required in ("measurement", "sources", "coverage", "validation", "outstanding_decisions"):
            require(required in record, f"Missing field {code}/{required}")
        for source in record.get("sources", []):
            identifier = source.get("verified_series_id")
            if source.get("identifier_type") == "WORKBOOK_LOCATOR":
                require(identifier is None, f"Workbook locator must not become an invented Series ID: {code}")
    by_code = {r.get("code"): r for r in records}
    for code in ("E04", "E12"):
        variants = by_code.get(code, {}).get("methodology_variants", [])
        require(len(variants) == 2 and {v.get("variant_id") for v in variants} == {"A", "B"}, f"Two distinct variants required: {code}")
        require(all(v.get("publication_approved") is False for v in variants), f"Variant publication enabled: {code}")
        if code == "E12":
            require(all(v.get("production_pinned") is False and v.get("real_time_backtesting_eligible") is False for v in variants), "E12 track restrictions lost")
    e12 = by_code.get("E12", {})
    experiment = e12.get("scoring", {}).get("research_experiment", {})
    for flag in ("parameters_approved", "weights_approved", "publication_approved", "real_time_backtesting_eligible"):
        require(experiment.get(flag) is False, f"E12 research restriction lost: {flag}")
    overlap = next((o for o in contract.get("overlaps", []) if o.get("id") == "O01"), {})
    require(set(overlap.get("indicators", [])) == {"E11", "S08"}, "E11/S08 relationship required")
    require(overlap.get("combined_composite_contribution_blocked") is True, "Combined E11/S08 contribution must be blocked")
    require(overlap.get("status") == "UNRESOLVED" and overlap.get("exact_equivalence") is None and overlap.get("resolution") is None and overlap.get("independent_review_approved") is False, "E11/S08 cannot be silently resolved")
    for issue in contract.get("contradictions", []):
        require(issue.get("silent_override_permitted") is False and issue.get("resolution") is None, "Contradiction silently resolved")
    require(len(contract.get("approval_gates", [])) == 7, "Seven approval gates required")
    require(all(g.get("status") == "NOT_GRANTED_BY_THIS_CONTRACT" for g in contract.get("approval_gates", [])), "Draft cannot grant approval gates")
    return errors


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        raise SystemExit("\n".join(errors))
    print("AESM V0.1 draft: 20 indicators, evidence integrity and HOLD guards validated.")
    print("No economic methodology, source freshness or publication approval implied.")


if __name__ == "__main__":
    main()
