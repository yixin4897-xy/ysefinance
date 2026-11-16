"""Unit tests for the explicitly non-production AESM social-discussion pilot."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sentiment  # noqa: E402


class SentimentPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = ROOT / "fixtures" / "synthetic_comments.jsonl"

    def test_fixture_is_complete_synthetic_input(self):
        records = sentiment.load_records(self.fixture)
        self.assertGreaterEqual(len(records), 20)
        self.assertTrue(all(row.get("synthetic") is True for row in records))
        self.assertTrue(all(set(row).issubset(sentiment.APPROVED_KEYS) for row in records))

    def test_topic_and_sentiment_english(self):
        self.assertEqual(sentiment.classify("My mortgage repayments feel harder")[0:2], ("housing", "negative"))
        self.assertEqual(sentiment.classify("Small business cash flow improved")[0:2], ("small_business", "positive"))
        self.assertEqual(sentiment.classify("My groceries at the supermarket are more expensive")[0:2], ("cost_of_living", "negative"))

    def test_chinese_keyword_baseline(self):
        theme, sentiment_label, text_type = sentiment.classify("我的房贷压力越来越大")
        self.assertEqual((theme, sentiment_label, text_type), ("housing", "negative", "personal_experience"))

    def test_unrelated_text_rejected_as_unclassified(self):
        self.assertEqual(sentiment.classify("Sunny day in the park")[0], "unclassified")

    def test_mixed_sentiment(self):
        self.assertEqual(sentiment.classify("My wages improved but the job search is harder")[1], "mixed")

    def test_synthetic_dataset_aggregates_and_deduplicates(self):
        result = sentiment.analyse(sentiment.load_records(self.fixture), synthetic=True)
        self.assertEqual(result["provenance"], "SYNTHETIC_TEST_ONLY")
        self.assertEqual(result["research_status"], sentiment.STATUS)
        self.assertEqual(result["input_rows"], 27)
        self.assertEqual(result["deduplicated_rows"], 1)
        self.assertEqual(result["accepted_relevant_rows"], 26)
        self.assertEqual(len(result["weeks"]), 2)
        self.assertFalse(result["no_composite_score"] is False)

    def test_outputs_do_not_include_raw_comment_text(self):
        result = sentiment.analyse(sentiment.load_records(self.fixture), synthetic=True)
        text = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("My supermarket groceries", text)
        self.assertNotIn("小生意现金流", text)
        self.assertNotIn("author_id", text)
        self.assertNotIn("profile", text)

    def test_small_cells_are_suppressed(self):
        result = sentiment.analyse(sentiment.load_records(self.fixture), synthetic=True)
        for week in result["weeks"]:
            self.assertTrue(all(v == "suppressed" or v >= sentiment.MIN_CELL for v in week["topics"].values()))
            self.assertTrue(all(v == "suppressed" or v >= sentiment.MIN_CELL for v in week["sentiment"].values()))

    def test_unknown_and_personal_columns_are_blocked(self):
        bad = [{"platform": "reddit", "timestamp": "2026-11-02T12:00:00Z", "text": "Rent is higher", "language": "en", "synthetic": True, "username": "example"}]
        with self.assertRaisesRegex(ValueError, "unknown or personal-identifier"):
            sentiment.analyse(bad, synthetic=True)

    def test_unmarked_synthetic_record_rejected(self):
        bad = [{"platform": "youtube", "timestamp": "2026-11-02T12:00:00Z", "text": "Mortgage stress", "language": "en"}]
        with self.assertRaisesRegex(ValueError, "marked synthetic"):
            sentiment.analyse(bad, synthetic=True)

    def test_real_input_requires_explicit_attestation(self):
        real = [{"platform": "youtube", "timestamp": "2026-11-02T12:00:00Z", "text": "My mortgage repayments are harder", "language": "en"}]
        with self.assertRaisesRegex(ValueError, "requires --approval"):
            sentiment.analyse(real, synthetic=False)

    def test_approval_gate_rejects_out_of_scope_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            approval = Path(tmp) / "approval.json"
            approval.write_text(json.dumps({
                "governance_approved": True, "rights_confirmed": True, "data_minimised": True,
                "approval_reference": "TEST-ONLY", "approved_by": "TEST-REVIEWER",
                "allowed_platforms": ["youtube"], "valid_until": "2099-12-31"
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not approved"):
                sentiment.approval_check(approval, {"reddit"})

    def test_timezone_required(self):
        bad = [{"platform": "youtube", "timestamp": "2026-11-02T12:00:00", "text": "Mortgage stress", "language": "en", "synthetic": True}]
        with self.assertRaisesRegex(ValueError, "ISO 8601 UTC/offset"):
            sentiment.analyse(bad, synthetic=True)

    def test_cli_generates_two_aggregate_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "out.json"
            md_out = Path(tmp) / "out.md"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "sentiment.py"), "--input", str(self.fixture),
                 "--synthetic-fixture", "--json-out", str(json_out), "--markdown-out", str(md_out)],
                capture_output=True, text=True, check=False
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(json_out.read_text(encoding="utf-8"))["accepted_relevant_rows"], 26)
            self.assertIn("NOT VALIDATED", md_out.read_text(encoding="utf-8"))

    def test_cli_prevents_synthetic_mode_on_outside_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "fake.jsonl"
            copied.write_text(self.fixture.read_text(encoding="utf-8"), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "sentiment.py"), "--input", str(copied),
                 "--synthetic-fixture", "--json-out", str(Path(tmp) / "o.json"),
                 "--markdown-out", str(Path(tmp) / "o.md")],
                capture_output=True, text=True, check=False
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("restricted", completed.stderr)


if __name__ == "__main__":
    unittest.main()
