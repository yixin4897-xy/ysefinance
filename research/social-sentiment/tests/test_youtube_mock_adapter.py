"""Strictly synthetic YouTube-shaped adapter tests."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from youtube_mock_adapter import convert_synthetic_response  # noqa: E402

FIXTURE = ROOT / "fixtures" / "youtube_mock_response.json"


class MockYouTubeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_aggregate_only_and_zero_calls(self):
        result = convert_synthetic_response(self.fixture)
        self.assertEqual(result["source"], "FICTIONAL_YOUTUBE_SHAPED_PAYLOAD")
        self.assertEqual(result["api_calls_executed"], 0)
        self.assertEqual(result["identity_fields_stored"], 0)
        self.assertEqual(result["raw_comments_exported"], 0)
        self.assertEqual(result["aggregate"]["input_rows"], 13)
        self.assertEqual(result["aggregate"]["accepted_relevant_rows"], 13)
        self.assertEqual(len(result["aggregate"]["weeks"]), 2)

    def test_author_and_comment_content_not_exported(self):
        result = convert_synthetic_response(self.fixture)
        raw = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("FAKE AUTHOR A", raw)
        self.assertNotIn("authorDisplayName", raw)
        self.assertNotIn("authorChannelId", raw)
        self.assertNotIn("My supermarket groceries", raw)
        self.assertNotIn("房租压力很大", raw)
        self.assertNotIn("invalid.example", raw)

    def test_ordinary_api_response_rejected(self):
        invalid = dict(self.fixture)
        invalid.pop("mock_only")
        with self.assertRaisesRegex(ValueError, "synthetic marker"):
            convert_synthetic_response(invalid)

    def test_unmarked_item_rejected(self):
        invalid = json.loads(json.dumps(self.fixture))
        invalid["items"][0].pop("fictional")
        with self.assertRaisesRegex(ValueError, "marked fictional"):
            convert_synthetic_response(invalid)

    def test_bad_schema_rejected(self):
        invalid = json.loads(json.dumps(self.fixture))
        invalid["unexpected"] = "data"
        with self.assertRaisesRegex(ValueError, "Unknown"):
            convert_synthetic_response(invalid)

    def test_cli_synthetic_only(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "aggregate.json"
            r = subprocess.run(
                [sys.executable, str(ROOT / "youtube_mock_adapter.py"),
                 "--mock", str(FIXTURE), "--out", str(output)],
                text=True, capture_output=True, check=False
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("ZERO API calls", r.stdout)
            parsed = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(parsed["aggregate"]["accepted_relevant_rows"], 13)

    def test_cli_external_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = Path(temp) / "payload.json"
            sample.write_text(json.dumps(self.fixture), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(ROOT / "youtube_mock_adapter.py"),
                 "--mock", str(sample), "--out", str(Path(temp) / "out.json")],
                text=True, capture_output=True, check=False
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("Only bundled synthetic fixtures", r.stderr)


if __name__ == "__main__":
    unittest.main()
