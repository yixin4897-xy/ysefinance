"""Offline E12 contract and candidate-governance checks."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import aehi_e12_import as e12


def fixture(key):
    """Synthetic data retains the real contract's periods, never official values."""
    spec = e12.CONTRACTS[key]
    cells = {f"A{r}": v for r, v in e12.LABELS.items()}
    col = spec["column"]
    cells.update({f"{col}{r}": v for r, v in {
        1: spec["description"], 2: "Percent", 3: "Seasonally Adjusted",
        4: "PERCENT", 5: spec["frequency"], 6: spec["interval"],
        9: str(spec["count"]), 10: spec["series_id"]}.items()})
    start = dt.date(1972, 9, 1) if key == "A" else dt.date(2024, 4, 1)
    total = spec["leading"] + spec["count"] + spec["trailing"]
    for i in range(total):
        month = start.year * 12 + start.month - 1 + i * int(spec["interval"])
        date = dt.date(month // 12, month % 12 + 1, 1)
        cells[f"A{i+11}"] = str((date - dt.date(1899, 12, 30)).days)
        if spec["leading"] <= i < total - spec["trailing"]:
            cells[f"{col}{i+11}"] = "3.6"
    cells[f"{col}7"] = cells[f"A{11+spec['leading']}"]
    cells[f"{col}8"] = cells[f"A{10+total-spec['trailing']}"]
    return {"path": "research-inputs/e12/" + spec["filename"], "sha256": spec["sha256"],
            "sheets": {"Index": {"B6": spec["table"]}, "Data1": cells}}


class E12Checks(unittest.TestCase):
    def test_independent_coverage_and_periods(self):
        for key, spec in e12.CONTRACTS.items():
            result = e12.extract_series(fixture(key), spec)
            self.assertEqual(result["validation"]["observation_count"], spec["count"])
            self.assertEqual(result["observations"][0]["period"], spec["first"])
            self.assertEqual(result["latest"]["period"], spec["last"])
            self.assertEqual(result["validation"]["leading_missing_count"], spec["leading"])
            self.assertEqual(result["validation"]["trailing_missing_count"], spec["trailing"])
            self.assertTrue(all(("Q" in o["period"]) == (key == "A") for o in result["observations"]))

    def test_metadata_failures(self):
        for key, spec in e12.CONTRACTS.items():
            for row in range(1, 11):
                book = fixture(key)
                book["sheets"]["Data1"][f"{spec['column']}{row}"] = "WRONG"
                with self.subTest(key=key, row=row), self.assertRaises(ValueError):
                    e12.extract_series(book, spec)
            for sheet, cell in (("Index", "B6"), ("Data1", "A5")):
                book = fixture(key)
                book["sheets"][sheet][cell] = "WRONG"
                with self.assertRaises(ValueError):
                    e12.extract_series(book, spec)

    def test_duplicate_series_and_cross_frequency_rejected(self):
        book = fixture("A")
        book["sheets"]["Data1"]["Z10"] = e12.CONTRACTS["A"]["series_id"]
        with self.assertRaises(ValueError):
            e12.extract_series(book, e12.CONTRACTS["A"])
        with self.assertRaises(ValueError):
            e12.extract_series(fixture("B"), e12.CONTRACTS["A"])

    def test_values_preserved_including_zero_and_negative(self):
        for value in ("0", "-0.3", "3.647"):
            book = fixture("A")
            book["sheets"]["Data1"]["I100"] = value
            rows = e12.extract_series(book, e12.CONTRACTS["A"])["observations"]
            self.assertEqual(next(o for o in rows if o["source_cell"] == "I100")["annual_change_percent"], float(value))

    def test_invalid_and_missing_values(self):
        for value in ("", "..", "NaN", "inf", "-inf", "n/a"):
            book = fixture("A")
            book["sheets"]["Data1"]["I100"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                e12.extract_series(book, e12.CONTRACTS["A"])
        for address in ("I53", "I226", "I227"):
            book = fixture("A")
            book["sheets"]["Data1"][address] = "" if address != "I227" else "3.6"
            with self.assertRaises(ValueError):
                e12.extract_series(book, e12.CONTRACTS["A"])

    def test_dates_reject_duplicates_gaps_fractional_and_wrong_month(self):
        for value in ("NaN", "100.5", "bad", None, "0",
                      str((dt.date(1990, 4, 1)-dt.date(1899, 12, 30)).days)):
            book = fixture("A")
            book["sheets"]["Data1"]["A100"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                e12.extract_series(book, e12.CONTRACTS["A"])
        for shift in (-1, 1):
            book = fixture("A")
            book["sheets"]["Data1"]["A100"] = book["sheets"]["Data1"][f"A{100+shift}"]
            with self.assertRaises(ValueError):
                e12.extract_series(book, e12.CONTRACTS["A"])

    def test_hash_mismatch_and_external_source_rejected(self):
        book = fixture("A")
        book["sha256"] = "0" * 64
        with patch.object(e12, "read_workbook", return_value=book):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                e12.build_candidate(ROOT / "research-inputs/e12")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "within repository"):
                e12.build_candidate(Path(folder))

    def test_candidate_restrictions(self):
        with patch.object(e12, "read_workbook", side_effect=[fixture("A"), fixture("B")]):
            baseline = e12.build_candidate(ROOT / "research-inputs/e12")
        changes = {"data_status": "VERIFIED", "score": 50, "publication_approved": True,
                   "production_pinned": True, "real_time_backtesting_eligible": True,
                   "composite_release_status": "RELEASED", "composite_release_statuses": {},
                   "track_policy": "splice", "value_convention": "annualise"}
        for key, value in changes.items():
            candidate = copy.deepcopy(baseline)
            candidate[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "restrictions"):
                e12.write_candidate(candidate, ROOT / "data-candidates/must-not-write.json")
        for field, value in (("series_id", "A130400382R"), ("frequency", "Month")):
            candidate = copy.deepcopy(baseline)
            candidate["tracks"]["A"][field] = value
            with self.assertRaisesRegex(ValueError, "contract"):
                e12.write_candidate(candidate, ROOT / "data-candidates/must-not-write.json")
        with self.assertRaisesRegex(ValueError, "Output"):
            e12.write_candidate(baseline, ROOT / "aehi-verified-indicators.json")
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(e12, "ROOT", Path(folder)):
                target = Path(folder) / "data-candidates/test.json"
                target.parent.mkdir()
                e12.write_candidate(baseline, target)
                with self.assertRaises(FileExistsError):
                    e12.write_candidate(baseline, target)

    @unittest.skipUnless(all((ROOT / "research-inputs/e12" / c["filename"]).exists()
                             for c in e12.CONTRACTS.values()), "Local ABS snapshots not supplied")
    def test_local_snapshots_and_output(self):
        candidate = e12.build_candidate(ROOT / "research-inputs/e12")
        for key, spec in e12.CONTRACTS.items():
            track = candidate["tracks"][key]
            source = track["source"]
            self.assertEqual(source["source_file"], "research-inputs/e12/" + spec["filename"])
            self.assertEqual(source["sha256"], hashlib.sha256((ROOT / source["source_file"]).read_bytes()).hexdigest())
            self.assertEqual(track["validation"]["observation_count"], spec["count"])
            self.assertEqual(track["latest"]["annual_change_percent"], 3.6)
        self.assertEqual(candidate["tracks"]["A"]["observations"][0]["annual_change_percent"], 10.6)
        self.assertEqual(candidate["tracks"]["B"]["observations"][0]["annual_change_percent"], 3.2)
        self.assertEqual(candidate["composite_release_statuses"], e12.HOLD)
        self.assertIsNone(candidate["score"])
        payload = json.dumps(candidate, allow_nan=False)
        self.assertNotIn("C:\\", payload)
        output = ROOT / "data-candidates/aehi-e12-local-review.json"
        if output.exists():
            saved = json.loads(output.read_text())
            saved.pop("generated_at_utc")
            candidate.pop("generated_at_utc")
            self.assertEqual(saved, candidate)


if __name__ == "__main__":
    unittest.main()
