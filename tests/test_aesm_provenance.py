"""Metadata-only fixtures plus optional local workbook integration; no network."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import aesm_provenance as provenance


def fixture():
    # Metadata fixture from committed candidate, not a fresh official verification.
    track = provenance.read_json(ROOT / "data-candidates/aehi-e12-local-review.json")["tracks"]["A"]
    coverage = {k: track["validation"][k] for k in ("first_period", "last_period", "observation_count",
        "grid_count", "leading_missing_count", "trailing_missing_count", "internal_missing_count", "excluded_blank_periods")}
    return provenance.seal({
        "schema_version": "0.1.0", "indicator": "E12",
        "methodological_variant": {"id": "A", "name": "Metadata test fixture", "candidate_version": "V1",
            "status": "CANDIDATE_ONLY_PENDING_VALIDATION", "transformations": {"value": "Published annual change"}},
        "historical_classification": "latest_revised_data_research", "point_in_time_eligible": False,
        "identity_basis": "SHA256_CANONICAL_JSON_EXCLUDING_MANIFEST_ID",
        "sources": [provenance.source_record("track_A", track["source"], coverage, "E12", track)],
        "output_coverage": {"first_period": "1983-Q1", "last_period": "2026-Q2", "observation_count": 174,
            "frequency": "quarterly", "unit": "Percent annual change", "meaning": "Test fixture"},
        "evidence": [{"path": provenance.SCHEMA_PATH, "sha256": "a" * 64, "hash_basis": "UTF8_TEXT_LF_NORMALIZED"}],
        "evidence_commit": provenance.EVIDENCE_COMMIT,
        "validation_state": "LOCAL_SNAPSHOT_CHECKED_NOT_PUBLICATION_APPROVAL",
        "approval": dict.fromkeys(("indicator_definition_approved", "publication_approved", "production_pinned", "scoring_approved", "weights_approved"), False),
        "composite_release_statuses": dict(provenance.HOLD), "composite_scores": dict.fromkeys(provenance.HOLD),
        "limitations": ["Metadata fixture; no official-source verification implied."]})


class ProvenanceChecks(unittest.TestCase):
    def setUp(self):
        self.manifest = fixture()

    def test_schema_and_deterministic_identity(self):
        self.assertEqual(provenance.validate_manifest(self.manifest), self.manifest)
        self.assertEqual(provenance.seal(self.manifest), self.manifest)
        changed = copy.deepcopy(self.manifest)
        changed["limitations"].append("Another research caveat")
        self.assertNotEqual(provenance.seal(changed)["manifest_id"], self.manifest["manifest_id"])

    def test_unknown_fields_missing_fields_and_invalid_types_rejected(self):
        for operation in (lambda d: d.update(production_score=10),
                          lambda d: d.pop("historical_classification"),
                          lambda d: d["sources"][0]["coverage"].update(observation_count=True)):
            data = copy.deepcopy(self.manifest)
            operation(data)
            with self.assertRaises(ValueError):
                provenance.validate_manifest(provenance.seal(data))

    def test_approval_scoring_pinning_and_point_in_time_promotion_rejected(self):
        changes = [lambda d, k=k: d["approval"].update({k: True}) for k in self.manifest["approval"]]
        changes += [lambda d: d.update(point_in_time_eligible=True),
                    lambda d: d.update(historical_classification="point_in_time"),
                    lambda d: d["composite_scores"].update(AEHI=0),
                    lambda d: d["composite_release_statuses"].update(AESI="PUBLISHED")]
        for change in changes:
            data = copy.deepcopy(self.manifest)
            change(data)
            with self.assertRaises(ValueError):
                provenance.validate_manifest(provenance.seal(data))

    def test_conflicting_manifest_and_source_vintage_identity_rejected(self):
        data = copy.deepcopy(self.manifest)
        data["limitations"].append("Changed without a new manifest ID")
        with self.assertRaisesRegex(ValueError, "manifest identity"):
            provenance.validate_manifest(data)
        data = copy.deepcopy(self.manifest)
        data["sources"][0]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source-vintage identity"):
            provenance.validate_manifest(provenance.seal(data))

    def test_frequency_series_and_missingness_disagreement_rejected(self):
        for key, value in (("frequency", "monthly"), ("unit", "Index")):
            data = copy.deepcopy(self.manifest)
            data["sources"][0]["measurement"][key] = value
            with self.assertRaises(ValueError):
                provenance.validate_manifest(provenance.seal(data))
        data = copy.deepcopy(self.manifest)
        data["sources"][0]["series_id"] = "NOT_A_VERIFIED_SERIES"
        with self.assertRaises(ValueError):
            provenance.validate_manifest(provenance.seal(data))
        data = copy.deepcopy(self.manifest)
        data["sources"][0]["coverage"]["internal_missing_count"] = 1
        with self.assertRaises(ValueError):
            provenance.validate_manifest(provenance.seal(data))

    def test_release_retrieval_and_observation_dates_remain_distinct(self):
        source = self.manifest["sources"][0]
        self.assertEqual(source["release"]["date"], "2026-09-30")
        self.assertEqual(source["coverage"]["last_period"], "2026-Q2")
        self.assertIsNone(source["release"]["retrieved_at_utc"])
        for change in ({"retrieved_at_utc": "2026-10-24T00:00:00Z"},
                       {"retrieved_at_utc": "2026-10-24T00:00:00", "retrieval_status": "EVIDENCED"},
                       {"date": "2026-02-30"}):
            data = copy.deepcopy(self.manifest)
            data["sources"][0]["release"].update(change)
            with self.assertRaises(ValueError):
                provenance.validate_manifest(provenance.seal(data))

    def test_path_escape_and_symlink_rejected(self):
        for path in ("../production.json", "/absolute.xlsx", "C:/private.xlsx", "research-inputs/../secret.xlsx"):
            with self.assertRaises(ValueError):
                provenance.safe_path(path)
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaisesRegex(ValueError, "Symlink"):
                provenance.safe_path("data-candidates/provenance/manifests")

    def test_unofficial_url_and_misclassified_boundary_blanks_rejected(self):
        data = copy.deepcopy(self.manifest)
        data["sources"][0]["official_source_url"] = "https://www.abs.gov.au.evil.example/file.xlsx"
        with self.assertRaisesRegex(ValueError, "official provider"):
            provenance.validate_manifest(provenance.seal(data))
        data = copy.deepcopy(self.manifest)
        data["sources"][0]["coverage"]["excluded_blank_periods"][0] = "2000-Q1"
        with self.assertRaisesRegex(ValueError, "positions"):
            provenance.validate_manifest(provenance.seal(data))

    def test_duplicate_keys_nonfinite_json_and_unsupported_schema_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for content in ('{"a": 1, "a": 2}', '{"a": NaN}'):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    provenance.read_json(path)
        with self.assertRaises(ValueError):
            provenance.validate_schema(1, {"unsupported": True})

    def temporary_root(self, directory):
        root = Path(directory)
        (root / "docs").mkdir()
        shutil.copyfile(ROOT / provenance.SCHEMA_PATH, root / provenance.SCHEMA_PATH)
        return root

    def test_append_is_exclusive_idempotent_and_preserves_prior_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.temporary_root(tmp)
            path, created = provenance.append_manifest(self.manifest, root)
            self.assertTrue(created)
            original, stamp = path.read_bytes(), path.stat().st_mtime_ns
            self.assertFalse(provenance.append_manifest(self.manifest, root)[1])
            self.assertEqual(path.stat().st_mtime_ns, stamp)
            changed = copy.deepcopy(self.manifest)
            changed["limitations"].append("New append, no changed source metadata")
            provenance.append_manifest(provenance.seal(changed), root)
            self.assertEqual(len(provenance.read_store(root)), 2)
            self.assertEqual(path.read_bytes(), original)

    def test_conflicting_metadata_reuse_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.temporary_root(tmp)
            path, _ = provenance.append_manifest(self.manifest, root)
            before = path.read_bytes()
            changed = copy.deepcopy(self.manifest)
            changed["sources"][0]["release"].update(retrieved_at_utc="2026-10-24T00:00:00Z", retrieval_status="EVIDENCED")
            with self.assertRaisesRegex(ValueError, "Conflicting reuse"):
                provenance.append_manifest(provenance.seal(changed), root)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(list(path.parent.glob("*.json"))), 1)

    def test_invalid_prior_manifest_and_concurrent_lock_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.temporary_root(tmp)
            directory = root / provenance.STORE_PATH
            directory.mkdir(parents=True)
            prior = directory / "prior.json"
            prior.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                provenance.append_manifest(self.manifest, root)
            self.assertEqual(prior.read_text(), "{}")
            lock = directory.parent / ".append.lock"
            lock.write_text("another writer", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                provenance.append_manifest(self.manifest, root)
            self.assertEqual(lock.read_text(), "another writer")

    def test_original_source_hash_mismatch_rejected(self):
        with patch.object(provenance.e12, "read_workbook", return_value={"sha256": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                provenance.e12.build_candidate(ROOT / "research-inputs/e12")

    @unittest.skipUnless(all((ROOT / p).exists() for p in (
        "research-inputs/e04/310101 (1).xlsx", "research-inputs/e04/5206020_Household_Income (1).xlsx",
        "research-inputs/e04/5206008_Household_Final_Consumption_Expenditure (1).xlsx",
        "research-inputs/e12/64010Appendix1a.xlsx", "research-inputs/e12/640106.xlsx")),
        "Local original ABS workbooks not supplied")
    def test_local_pilot_actual_hashes_coverage_and_reproducibility(self):
        manifests = provenance.build_pilot()
        self.assertEqual(manifests, provenance.build_pilot())
        self.assertEqual([(m["indicator"], m["methodological_variant"]["id"], m["output_coverage"]["observation_count"])
                          for m in manifests], [("E04", "A", 179), ("E04", "B", 178), ("E12", "A", 174), ("E12", "B", 17)])
        self.assertEqual(len({s["source_sha256"] for m in manifests for s in m["sources"]}), 5)
        self.assertEqual(len({s["series_id"] for m in manifests for s in m["sources"]}), 6)
        for manifest in manifests:
            for source in manifest["sources"]:
                self.assertIsNone(source["release"]["retrieved_at_utc"])
                if manifest["indicator"] == "E04":
                    self.assertIsNone(source["official_source_url"])
                    self.assertIsNone(source["release"]["date"])


if __name__ == "__main__":
    unittest.main()
