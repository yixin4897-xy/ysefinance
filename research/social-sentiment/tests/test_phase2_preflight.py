"""Offline Phase 2 tests: YouTube permission/quota planning and synthetic classification audit."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from youtube_preflight import plan  # noqa: E402
from annotation_eval import evaluate  # noqa: E402


class Phase2PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.youtube_manifest = ROOT / "fixtures" / "youtube_preflight_synthetic.json"
        cls.annotation_fixture = ROOT / "fixtures" / "annotations_synthetic.json"
        cls.manifest = json.loads(cls.youtube_manifest.read_text(encoding="utf-8"))
        cls.annotations = json.loads(cls.annotation_fixture.read_text(encoding="utf-8"))

    def test_youtube_preflight_uses_zero_api_calls(self):
        result = plan(self.manifest)
        self.assertEqual(result["research_status"], "DESIGN_ONLY_NO_COLLECTION")
        self.assertEqual(result["api_calls_executed"], 0)
        self.assertEqual(result["real_comments_processed"], 0)
        self.assertEqual(result["maximum_expected_quota_units"], 4)
        self.assertEqual(result["upper_bound_top_level_comments"], 200)

    def test_real_collection_flag_is_refused(self):
        altered = {**self.manifest, "live_collection_authorized": True}
        with self.assertRaisesRegex(ValueError, "disabled"):
            plan(altered)

    def test_request_cap_is_enforced(self):
        altered = {**self.manifest, "max_total_requests": 3}
        with self.assertRaisesRegex(ValueError, "cap exceeded"):
            plan(altered)

    def test_bad_video_id_rejected(self):
        altered = json.loads(json.dumps(self.manifest))
        altered["candidate_videos"][0]["video_id"] = "a-bad-ID"
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            plan(altered)

    def test_duplicate_video_id_rejected(self):
        altered = json.loads(json.dumps(self.manifest))
        altered["candidate_videos"][1]["video_id"] = altered["candidate_videos"][0]["video_id"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            plan(altered)

    def test_unknown_metadata_rejected(self):
        altered = json.loads(json.dumps(self.manifest))
        altered["candidate_videos"][0]["author_email"] = "should-not-appear"
        with self.assertRaisesRegex(ValueError, "only"):
            plan(altered)

    def test_preflight_cli_never_performs_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "youtube-plan.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "youtube_preflight.py"),
                 "--manifest", str(self.youtube_manifest), "--out", str(out)],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ZERO calls", result.stdout)
            obj = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(obj["api_calls_executed"], 0)

    def test_synthetic_annotations_report_errors_without_text(self):
        result = evaluate(self.annotations)
        self.assertEqual(result["n"], 27)
        self.assertEqual(result["research_status"], "DIAGNOSTIC_NOT_VALIDATED")
        self.assertEqual(result["provenance"], "SYNTHETIC_ANNOTATIONS_ONLY")
        self.assertTrue(result["languages"].get("en", 0) > 0)
        self.assertTrue(result["languages"].get("zh", 0) > 0)
        self.assertNotIn("rent is not expensive", json.dumps(result).lower())
        self.assertLess(result["joint_accuracy_on_fabricated_examples"], 1.0)

    def test_annotations_reject_unmarked_real_input(self):
        altered = json.loads(json.dumps(self.annotations))
        altered[0]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "synthetic"):
            evaluate(altered)

    def test_annotation_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "eval.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "annotation_eval.py"),
                 "--annotations", str(self.annotation_fixture), "--out", str(out)],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            obj = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(obj["n"], 27)
            self.assertEqual(obj["research_status"], "DIAGNOSTIC_NOT_VALIDATED")


if __name__ == "__main__":
    unittest.main()
