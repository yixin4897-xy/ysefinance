"""Contract integrity and negative publication/overlap regression checks."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("master_contract", ROOT / "scripts/validate_aesm_master_contract.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class MasterContractChecks(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(validator.CONTRACT.read_text(encoding="utf-8"))

    def test_complete_evidence_backed_draft(self):
        self.assertEqual(validator.validate(self.contract), [])

    def test_checkout_line_endings_allowed_but_content_changes_rejected(self):
        target = ROOT / "aesm-research.html"
        original = Path.read_bytes
        raw = original(target)
        def checkout_bytes(path):
            if path == target:
                return raw.replace(b"\r\n", b"\n")
            return original(path)
        with patch.object(Path, "read_bytes", checkout_bytes):
            self.assertEqual(validator.validate(self.contract), [])
        def changed_bytes(path):
            return original(path) + (b"modified" if path == target else b"")
        with patch.object(Path, "read_bytes", changed_bytes):
            self.assertTrue(validator.validate(self.contract))

    def test_missing_or_duplicate_indicator_rejected(self):
        for mutate in (lambda d: d["indicators"].pop(), lambda d: d["indicators"].append(copy.deepcopy(d["indicators"][0]))):
            with self.subTest(mutation=mutate):
                data = copy.deepcopy(self.contract)
                mutate(data)
                self.assertTrue(validator.validate(data))

    def test_composite_promotion_and_weights_rejected(self):
        for mutate in (
            lambda d: d["release_controls"]["composite_release_statuses"].update(AEHI="PUBLISHED"),
            lambda d: d["release_controls"]["composite_scores"].update(AESI=0),
            lambda d: d["release_controls"].update(publication_approved=True),
            lambda d: d["indicators"][0]["weight"].update(value=0.1),
            lambda d: d["indicators"][0].update(composite_contribution_allowed=True),
        ):
            data = copy.deepcopy(self.contract)
            mutate(data)
            self.assertTrue(validator.validate(data))

    def test_duplicate_resolution_or_unblocking_rejected(self):
        for change in ({"combined_composite_contribution_blocked": False}, {"exact_equivalence": True}, {"resolution": "DROP_E11"}):
            data = copy.deepcopy(self.contract)
            data["overlaps"][0].update(change)
            self.assertTrue(validator.validate(data))

    def test_e12_track_collapse_or_promotion_rejected(self):
        for promote in (False, True):
            data = copy.deepcopy(self.contract)
            e12 = next(r for r in data["indicators"] if r["code"] == "E12")
            if promote:
                e12["scoring"]["research_experiment"]["parameters_approved"] = True
            else:
                e12["methodology_variants"].pop()
            self.assertTrue(validator.validate(data))

    def test_changed_evidence_and_unknown_reference_rejected(self):
        data = copy.deepcopy(self.contract)
        data["evidence_catalog"]["aesm-research.html"]["sha256"] = "0" * 64
        self.assertTrue(validator.validate(data))

    def test_dictionary_swaps_and_gate_approval_rejected(self):
        data = copy.deepcopy(self.contract)
        data["indicators"][0]["registered_definition"]["text"] = data["indicators"][1]["registered_definition"]["text"]
        self.assertTrue(validator.validate(data))
        data = copy.deepcopy(self.contract)
        data["approval_gates"][-1]["status"] = "APPROVED"
        self.assertTrue(validator.validate(data))
        data = copy.deepcopy(self.contract)
        data["indicators"][0]["validation"]["evidence_refs"] = ["nonexistent.json"]
        self.assertTrue(validator.validate(data))

    def test_unknowns_and_approved_display_remain_separate(self):
        records = {r["code"]: r for r in self.contract["indicators"]}
        for code in ("E02", "E03", "E07", "E08", "E09", "E10", "E11"):
            self.assertEqual(records[code]["sources"], [])
            self.assertIsNone(records[code]["measurement"]["frequency"])
        for code in ("E01", "E05", "E06", "S01", "S02", "S03", "S04", "S05", "S06"):
            self.assertEqual(records[code]["capability_evidence"][0]["designation"], "VERIFIED_FOR_PUBLIC_DISPLAY")
            self.assertEqual(records[code]["approval_state"]["definition_production"], "NO_APPROVAL_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
