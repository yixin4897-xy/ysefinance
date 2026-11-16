"""Synthetic-only dashboard generator regression tests."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_demo_dashboard import render, SYNTHETIC_WATERMARK  # noqa: E402
from sentiment import analyse, load_records  # noqa: E402


class DemoDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = analyse(load_records(ROOT / "fixtures" / "synthetic_comments.jsonl"), synthetic=True)

    def test_is_functional_offline_html_and_synthetic_labeled(self):
        html = render(self.result)
        self.assertIn(SYNTHETIC_WATERMARK, html)
        self.assertIn('<div id="bars"', html)
        self.assertIn('addEventListener("click"', html)
        self.assertIn("CANDIDATE_ONLY_UNVALIDATED", str(self.result))
        self.assertIn("Not a public economic index".lower(), html.lower())

    def test_never_loads_external_assets_or_ga4(self):
        html = render(self.result)
        for forbidden in ("https://", "http://", "<iframe", "<script src", "googletagmanager", "gtag(", "fetch(", "XMLHttpRequest", "localStorage"):
            self.assertNotIn(forbidden, html)

    def test_no_raw_text_in_dashboard(self):
        html = render(self.result)
        self.assertNotIn("My supermarket groceries", html)
        self.assertNotIn("小生意现金流", html)
        self.assertNotIn("author_id", html)

    def test_reject_non_synthetic_aggregate(self):
        invalid = {**self.result, "provenance": "MANUAL_APPROVED_INPUT_UNVALIDATED"}
        with self.assertRaisesRegex(ValueError, "Only bundled synthetic"):
            render(invalid)

    def test_generator_cli_produces_local_html(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "demo.html"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "build_demo_dashboard.py"), "--out", str(target)],
                capture_output=True, text=True, check=False
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(target.is_file())
            self.assertIn("SYNTHETIC DEMO", target.read_text(encoding="utf-8"))
            self.assertIn("0 API calls", proc.stdout)


if __name__ == "__main__":
    unittest.main()
