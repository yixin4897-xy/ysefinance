"""Offline E04 checks. Synthetic fixtures never become candidate observations."""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("e04", ROOT / "scripts/aehi_e04_import.py")
e04 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e04)


def serial(year, month):
    return str((dt.date(year, month, 1) - dt.date(1899, 12, 30)).days)


def fixture_book():
    description = e04.SPECS["income"]
    dates = [serial(2020, m) for m in (3, 6, 9, 12)]
    labels = ["Unit", "Series Type", "Data Type", "Frequency", "Collection Month",
              "Series Start", "Series End", "No. Obs", "Series ID"]
    values = [description[2], description[3], description[4], description[5],
              "Quarter", "3", dates[0], dates[-1], "4", description[1]]
    cells = {"A" + str(i): label for i, label in enumerate(labels, 2)}
    cells.update({"B" + str(i): value for i, value in enumerate(values, 1)})
    for row, date in enumerate(dates, 11):
        cells["A" + str(row)] = date
        cells["B" + str(row)] = str(100 + row)
    return {"path": "synthetic.xlsx", "sha256": "a" * 64,
            "sheets": {"Index": {"B6": description[6]}, "Data1": cells}}


def fixture_inputs():
    # Constant real aggregate and accelerating closing population distinguish A/B.
    quarters = list(range(2020 * 4, 2020 * 4 + 4))
    return {"income": dict(zip(quarters, (100, 110, 120, 130))),
            "consumption_current": dict(zip(quarters, (200, 220, 240, 260))),
            "consumption_volume": dict.fromkeys(quarters, 100.0),
            "population": dict(zip(quarters, (1000, 1020, 1060, 1120)))}


class MetadataChecks(unittest.TestCase):
    def test_metadata_and_provenance(self):
        values, source = e04.extract_series(fixture_book(), e04.SPECS["income"])
        self.assertEqual(len(values), 4)
        self.assertEqual(source["first_period"], "2020 Q1")
        self.assertEqual(source["source_file_sha256"], "a" * 64)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "within the repository"):
                e04.build_candidate(Path(directory))

    def test_wrong_identity_description_units_seasonality_frequency_type_table(self):
        for address in ("B1", "B2", "B3", "B4", "B5", "B6", "B10"):
            book = fixture_book()
            book["sheets"]["Data1"][address] = "WRONG"
            with self.subTest(address=address), self.assertRaises(ValueError):
                e04.extract_series(book, e04.SPECS["income"])
        book = fixture_book()
        book["sheets"]["Index"]["B6"] = "Wrong table"
        with self.assertRaisesRegex(ValueError, "table"):
            e04.extract_series(book, e04.SPECS["income"])

    def test_duplicate_series_column(self):
        book = fixture_book()
        book["sheets"]["Data1"]["C10"] = e04.SPECS["income"][1]
        with self.assertRaisesRegex(ValueError, "exactly one"):
            e04.extract_series(book, e04.SPECS["income"])

    def test_missing_invalid_and_nonpositive_observations(self):
        for value in ("", "..", "NaN", "inf", "0", "-1"):
            book = fixture_book()
            book["sheets"]["Data1"]["B12"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                e04.extract_series(book, e04.SPECS["income"])

    def test_dates_and_quarter_continuity(self):
        for value in (serial(2020, 3), serial(2020, 12), serial(2020, 4), "NaN", ""):
            book = fixture_book()
            book["sheets"]["Data1"]["A12"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                e04.extract_series(book, e04.SPECS["income"])

    def test_declared_coverage_and_count(self):
        for address, value in (("B7", serial(2019, 12)), ("B8", serial(2021, 3)), ("B9", "5")):
            book = fixture_book()
            book["sheets"]["Data1"][address] = value
            with self.subTest(address=address), self.assertRaisesRegex(ValueError, "Coverage"):
                e04.extract_series(book, e04.SPECS["income"])


class CalculationChecks(unittest.TestCase):
    def test_independent_formulas_and_comparison(self):
        result = e04.calculate(fixture_inputs())
        rows = result["observations"]
        self.assertEqual(rows[0]["consumption_implicit_price_deflator"], 200)
        self.assertEqual(rows[0]["real_income_per_capita_a"], 50)
        self.assertIsNone(rows[0]["real_income_per_capita_b"])
        self.assertIsNone(rows[1]["growth_b_percent"])
        self.assertAlmostEqual(rows[1]["real_income_per_capita_b"], 50000 / 1010)
        # Constant real income means each method's growth is inverse denominator growth.
        expected_a = [(1020 / 1060 - 1) * 100, (1060 / 1120 - 1) * 100]
        expected_b = [(1010 / 1040 - 1) * 100, (1040 / 1090 - 1) * 100]
        differences = [b - a for a, b in zip(expected_a, expected_b)]
        for row, a, b in zip(rows[2:], expected_a, expected_b):
            self.assertAlmostEqual(row["growth_a_percent"], a)
            self.assertAlmostEqual(row["growth_b_percent"], b)
        comparison = result["comparison"]
        self.assertAlmostEqual(comparison["maximum_absolute_difference_pp"], max(map(abs, differences)))
        self.assertAlmostEqual(comparison["average_absolute_difference_pp"], sum(map(abs, differences)) / 2)
        self.assertAlmostEqual(comparison["latest_difference_pp"], differences[-1])
        self.assertEqual(comparison["observation_count"], 2)

    def test_constant_population_methods_identical(self):
        inputs = fixture_inputs()
        inputs["population"] = dict.fromkeys(inputs["population"], 1000)
        result = e04.calculate(inputs)
        self.assertEqual(result["comparison"]["maximum_absolute_difference_pp"], 0)

    def test_trailing_mismatch_does_not_carry_population_forward(self):
        inputs = fixture_inputs()
        q = max(inputs["income"]) + 1
        for role in ("income", "consumption_current", "consumption_volume"):
            inputs[role][q] = 200
        result = e04.calculate(inputs)
        self.assertEqual(result["latest_common_period"], "2020 Q4")
        self.assertEqual(result["unmatched_source_periods"]["income"], ["2021 Q1"])

    def test_prior_population_outside_monetary_coverage_can_support_b(self):
        inputs = fixture_inputs()
        inputs["population"] = {2019 * 4 + 3: 990, **inputs["population"]}
        result = e04.calculate(inputs)
        self.assertEqual(result["method_b_growth_count"], 3)

    def test_gaps_and_insufficient_overlap_fail(self):
        inputs = fixture_inputs()
        del inputs["population"][2020 * 4 + 1]
        with self.assertRaisesRegex(ValueError, "quarter"):
            e04.calculate(inputs)
        inputs = fixture_inputs()
        inputs["population"] = dict(list(inputs["population"].items())[-2:])
        with self.assertRaisesRegex(ValueError, "three common"):
            e04.calculate(inputs)


class OutputAndReaderChecks(unittest.TestCase):
    def test_existing_candidate_and_public_file_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data-candidates").mkdir()
            path = root / "data-candidates/review.json"
            with patch.object(e04, "ROOT", root):
                e04.write_candidate({"data_status": e04.STATUS}, path)
                before = path.read_bytes()
                with self.assertRaises(FileExistsError):
                    e04.write_candidate({}, path)
                self.assertEqual(path.read_bytes(), before)
                with self.assertRaisesRegex(ValueError, "data-candidates"):
                    e04.write_candidate({}, root / "aehi-verified-indicators.json")

    def test_reader_resolves_relationships_and_rejects_formulas_and_date_system(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.xlsx"
            for formula, date1904 in ((False, False), (True, False), (False, True)):
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr("xl/workbook.xml", '<workbook xmlns="' + e04.NS['m'] + '" xmlns:r="' + e04.REL + '"><workbookPr date1904="' + str(int(date1904)) + '"/><sheets><sheet name="Data1" sheetId="99" r:id="rId7"/></sheets></workbook>')
                    z.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="rId7" Target="worksheets/custom.xml"/></Relationships>')
                    z.writestr("xl/worksheets/custom.xml", '<worksheet xmlns="' + e04.NS['m'] + '"><sheetData><row r="1"><c r="B1">' + ('<f>1+1</f>' if formula else '') + '<v>2</v></c></row></sheetData></worksheet>')
                if formula or date1904:
                    with self.assertRaises(ValueError):
                        e04.read_workbook(path)
                else:
                    self.assertEqual(e04.read_workbook(path)["sheets"]["Data1"]["B1"], "2")

    @unittest.skipUnless((ROOT / "research-inputs/e04/310101 (1).xlsx").exists(),
                         "Local ABS workbooks not supplied")
    def test_local_workbooks_end_to_end(self):
        candidate = e04.build_candidate(ROOT / "research-inputs/e04")
        relative_candidate = e04.build_candidate(ROOT / "research-inputs" / "e04" / ".")
        for result in (candidate, relative_candidate):
            result.pop("generated_at_utc")
        self.assertEqual(candidate, relative_candidate)
        for role, source in candidate["sources"].items():
            expected = "research-inputs/e04/" + e04.SPECS[role][0]
            self.assertEqual(source["source_file"], expected)
            self.assertFalse(Path(source["source_file"]).is_absolute())
            self.assertEqual(source["source_file_sha256"], hashlib.sha256(
                (ROOT / source["source_file"]).read_bytes()).hexdigest())
        self.assertEqual(candidate["data_status"], "CANDIDATE_ONLY_PENDING_VALIDATION")
        self.assertEqual(candidate["composite_release_status"], "HOLD")
        self.assertIsNone(candidate["score"])
        self.assertEqual(candidate["latest_common_period"], "2026 Q1")
        self.assertEqual(candidate["common_level_count"], 180)
        self.assertEqual(candidate["method_a_growth_count"], 179)
        self.assertEqual(candidate["method_b_growth_count"], 178)
        latest = candidate["observations"][-1]
        self.assertEqual(latest["income_current_aud_millions"], 457000)
        self.assertEqual(latest["population_end_thousands"], 27921.2)
        self.assertAlmostEqual(latest["real_income_per_capita_a"], 15282.099215890055)
        json.dumps(candidate, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
