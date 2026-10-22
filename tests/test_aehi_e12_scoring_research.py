"""Research score arithmetic, temporal integrity, isolation and regression checks."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import aehi_e12_scoring_research as research
import aehi_e12_import as importer


def track():
    return {"series_id": "A3604511X", "frequency": "Quarter", "unit": "Percent",
            "seasonal_adjustment": "Seasonally Adjusted", "methodology_flags": ["synthetic_fixture"],
            "observations": [{"period": period, "reference_date": date, "annual_change_percent": value,
                              "source_cell": f"I{row}"}
                             for row, (period, date, value) in enumerate([
                                 ("2001-Q2", "2001-06-01", 1), ("2001-Q3", "2001-09-01", 2.5),
                                 ("2001-Q4", "2001-12-01", 5)], 1)]}


class ResearchChecks(unittest.TestCase):
    def test_formula_boundaries_and_sensitivity(self):
        # Explicit independent expected results include deflation and clipping.
        for rate, expected in [(-1, (70, 40, 10)), (0, (80, 60, 40)),
                               (1, (90, 80, 70)), (2, (100, 100, 100)),
                               (2.5, (100, 100, 100)), (3, (100, 100, 100)),
                               (4, (90, 80, 70)), (5, (80, 60, 40)),
                               (7, (60, 20, 0)), (13, (0, 0, 0))]:
            self.assertEqual(tuple(research.score(rate, k) for k in research.KS), expected)
        self.assertEqual(research.score(3.6, 20), 88)
        for rate in (float("nan"), float("inf"), float("-inf"), True, "missing", None):
            with self.assertRaises(ValueError):
                research.score(rate, 20)
        with self.assertRaises(ValueError):
            research.score(3, -1)

    def test_preserve_raw_values_flags_and_input(self):
        source = track()
        before = copy.deepcopy(source)
        rows = research.calculate(source)
        self.assertEqual(source, before)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["signed_deviation_from_2_5_pp"], -1.5)
        self.assertEqual(rows[0]["target_band_distance_pp"], 1)
        self.assertEqual(rows[2]["score"], 60)
        self.assertEqual(rows[2]["annual_change_percent"], 5)
        self.assertIn("not_point_in_time", rows[0]["methodology_flags"])

    def test_temporal_integrity_and_monthly_rejection(self):
        for field, value in (("series_id", "A130400382R"), ("frequency", "Month"),
                             ("unit", "Index"), ("seasonal_adjustment", "Original")):
            source = track()
            source[field] = value
            with self.assertRaises(ValueError):
                research.calculate(source)
        for kind in ("gap", "duplicate", "unordered", "monthly_label"):
            source = track()
            if kind == "gap": source["observations"].pop(1)
            if kind == "duplicate": source["observations"][1] = source["observations"][0]
            if kind == "unordered": source["observations"].reverse()
            if kind == "monthly_label": source["observations"][1]["period"] = "2001-09"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                research.calculate(source)

    def test_summary_distribution_ties_and_quantiles(self):
        rows = research.calculate(track())
        result = research.summarize(rows)
        self.assertEqual(result["count"], 3)
        self.assertEqual((result["below_band_count"], result["in_band_count"], result["above_band_count"]), (1, 1, 1))
        summary = result["scores"]["20"]
        self.assertEqual(summary["mean"], 80)
        self.assertEqual(summary["p25"], 70)
        self.assertEqual(summary["highest_score_quarters"], ["2001-Q3"])
        self.assertEqual(summary["lowest_score_quarters"], ["2001-Q4"])
        self.assertEqual(sum(b["count"] for b in summary["distribution"].values()), 3)
        self.assertAlmostEqual(sum(b["share_percent"] for b in summary["distribution"].values()), 100)
        self.assertEqual(research.describe([88])["population_stddev"], 0)
        with self.assertRaises(ValueError):
            research.summarize([])

    def test_hash_mismatch_and_external_source_fail(self):
        with patch.object(importer, "read_workbook", return_value={"sha256": "wrong"}):
            with self.assertRaisesRegex(ValueError, "hash"):
                research.build_experiment()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "inside repository"):
                research.build_experiment(folder)

    def test_output_governance_and_exclusive_creation(self):
        valid = {"data_status": importer.STATUS, "research_only": True, "publication_approved": False,
                 "parameters_approved": False, "weights_approved": False, "composite_score": None,
                 "composite_release_statuses": importer.HOLD, "real_time_backtesting_eligible": False,
                 "historical_classification": "latest_revised_data_research", "track": "A", "series_id": "A3604511X"}
        changes = {"data_status": "APPROVED", "research_only": False, "publication_approved": True,
                   "parameters_approved": True, "weights_approved": True, "composite_score": 88,
                   "composite_release_statuses": {}, "real_time_backtesting_eligible": True,
                   "historical_classification": "point_in_time", "track": "B", "series_id": "other"}
        for key, value in changes.items():
            result = {**valid, key: value}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "restrictions"):
                research.write_experiment(result, ROOT / "must-not-write.json")
        with self.assertRaisesRegex(ValueError, "research JSON"):
            research.write_experiment(valid, ROOT / "aehi-verified-indicators.json")
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(research, "OUTPUT_DIR", Path(folder)):
                output = Path(folder) / "fixture.json"
                research.write_experiment(valid, output)
                with self.assertRaises(FileExistsError):
                    research.write_experiment(valid, output)

    @unittest.skipUnless((ROOT / "research-inputs/e12/64010Appendix1a.xlsx").exists(),
                         "Validated local quarterly ABS workbook not supplied")
    def test_local_all_rows_independent_formula_and_reproducibility(self):
        original_reader = importer.read_workbook
        with patch.object(importer, "read_workbook", wraps=original_reader) as reader:
            result = research.build_experiment()
            self.assertEqual(reader.call_count, 1)
            self.assertEqual(reader.call_args.args[0].name, "64010Appendix1a.xlsx")
        rows = result["observations"]
        self.assertEqual(result["methodology"]["provisional_benchmark_k"], 20)
        self.assertEqual(result["methodology"]["sensitivity_candidate_k"], 10)
        self.assertFalse(result["methodology"]["slope_selection_approved"])
        self.assertEqual(len(rows), 174)
        self.assertEqual((rows[0]["period"], rows[-1]["period"]), ("1983-Q1", "2026-Q2"))
        self.assertEqual(rows[-1]["scores"], {"10": 94, "20": 88, "30": 82})
        self.assertEqual(rows[-1]["annual_change_percent"], 3.6)
        candidate = json.loads((ROOT / "data-candidates/aehi-e12-local-review.json").read_text())
        for row, original in zip(rows, candidate["tracks"]["A"]["observations"]):
            for key in original:
                self.assertEqual(row[key], original[key])
            for k in research.KS:
                rate = Decimal(str(original["annual_change_percent"]))
                if rate < 2: expected = Decimal(100) - k * (2-rate)
                elif rate > 3: expected = Decimal(100) - k * (rate-3)
                else: expected = Decimal(100)
                self.assertEqual(row["scores"][str(k)], float(max(0, expected)))
        summaries = result["summaries"]
        self.assertEqual(summaries["pre_september_2001"]["count"], 74)
        self.assertEqual(summaries["september_2001_onward"]["count"], 100)
        self.assertEqual(summaries["pre_september_2001"]["last_period"], "2001-Q2")
        self.assertEqual(summaries["september_2001_onward"]["first_period"], "2001-Q3")
        output = research.OUTPUT_DIR / "aehi-e12-quarterly-scoring-v1.json"
        if output.exists():
            saved = json.loads(output.read_text())
            saved.pop("generated_at_utc")
            result.pop("generated_at_utc")
            self.assertEqual(saved, result)
        self.assertNotIn("C:\\", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
