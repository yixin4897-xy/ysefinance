#!/usr/bin/env python3
"""Offline E04 derivation. Writes a new review candidate only; never publishes."""
import argparse
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import posixpath
import re
import statistics
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STATUS = "CANDIDATE_ONLY_PENDING_VALIDATION"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SPECS = {
    "income": ("5206020_Household_Income (1).xlsx", "A2302939L",
               "GROSS DISPOSABLE INCOME ;", "$ Millions", "Seasonally Adjusted",
               "DERIVED", "Table 20. Household Income Account, Current prices"),
    "consumption_current": ("5206008_Household_Final_Consumption_Expenditure (1).xlsx",
                            "A2302236T", "FINAL CONSUMPTION EXPENDITURE: Current prices ;",
                            "$ Millions", "Seasonally Adjusted", "DERIVED",
                            "Table 8. Household Final Consumption Expenditure (HFCE)"),
    "consumption_volume": ("5206008_Household_Final_Consumption_Expenditure (1).xlsx",
                           "A2303280V", "FINAL CONSUMPTION EXPENDITURE: Chain volume measures ;",
                           "$ Millions", "Seasonally Adjusted", "DERIVED",
                           "Table 8. Household Final Consumption Expenditure (HFCE)"),
    "population": ("310101 (1).xlsx", "A2133251W",
                   "Estimated Resident Population (ERP) ;  Australia ;", "000",
                   "Original", "STOCK_CLOSE",
                   "TABLE 1. Population Change, Summary - Australia ('000)"),
}


def read_workbook(path):
    """Read saved OOXML cells with stdlib; resolve sheet names through relationships.

    This deliberately narrow reader rejects formulas rather than trusting cached values.
    No Excel engine, network, recalculation or workbook writes are used.
    """
    raw = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        props = workbook.find("m:workbookPr", NS)
        if props is not None and props.get("date1904", "0").lower() in ("1", "true"):
            raise ValueError("Unsupported Excel 1904 date system")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(t.text or "" for t in item.findall(".//m:t", NS))
                       for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        rels = {r.get("Id"): r for r in ET.fromstring(
            archive.read("xl/_rels/workbook.xml.rels"))}
        sheets = {}
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            relation = rels[sheet.get("{" + REL + "}id")]
            if relation.get("TargetMode") == "External":
                raise ValueError("External worksheet unsupported")
            target = relation.get("Target")
            target = (target.lstrip("/") if target.startswith("/") else
                      posixpath.normpath("xl/" + target))
            if not target.startswith("xl/"):
                raise ValueError("Invalid worksheet path")
            cells = {}
            for cell in ET.fromstring(archive.read(target)).findall(
                    ".//m:sheetData/m:row/m:c", NS):
                address = cell.get("r")
                if address in cells:
                    raise ValueError("Duplicate cell: " + address)
                if cell.find("m:f", NS) is not None:
                    raise ValueError("Formula cell unsupported: " + address)
                value = cell.find("m:v", NS)
                text = value.text or "" if value is not None else ""
                if cell.get("t") == "s":
                    text = strings[int(text)]
                elif cell.get("t") == "inlineStr":
                    text = "".join(t.text or "" for t in cell.findall(".//m:t", NS))
                elif cell.get("t") in ("e", "b"):
                    raise ValueError("Error/boolean cell unsupported: " + address)
                cells[address] = text
            sheets[sheet.get("name")] = cells
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "sheets": sheets}


def quarter_index(serial):
    try:
        number = float(serial)
        if not math.isfinite(number) or not number.is_integer():
            raise ValueError()
        date = dt.date(1899, 12, 30) + dt.timedelta(days=number)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("Invalid Excel date: " + str(serial)) from error
    # ABS labels quarters using the first day of their final month.
    if date.day != 1 or date.month not in (3, 6, 9, 12) or date.year < 1950:
        raise ValueError("Invalid ABS quarterly label: " + date.isoformat())
    return date.year * 4 + date.month // 3 - 1


def period(index):
    return f"{index // 4} Q{index % 4 + 1}"


def validate_observations(observations):
    if not observations:
        raise ValueError("No observations")
    if any(not math.isfinite(v) or v <= 0 for v in observations.values()):
        raise ValueError("Observations must be finite and positive")
    keys = list(observations)
    if any(b != a + 1 for a, b in zip(keys, keys[1:])):
        raise ValueError("Duplicate, unordered or missing quarter")


def extract_series(book, spec):
    _, series_id, description, unit, adjustment, data_type, table = spec
    sheets = book["sheets"]
    if sheets.get("Index", {}).get("B6") != table:
        raise ValueError("Unexpected ABS table for " + series_id)
    cells = sheets.get("Data1", {})
    labels = {2: "Unit", 3: "Series Type", 4: "Data Type", 5: "Frequency",
              6: "Collection Month", 7: "Series Start", 8: "Series End",
              9: "No. Obs", 10: "Series ID"}
    if any(cells.get("A" + str(row)) != label for row, label in labels.items()):
        raise ValueError("Unexpected ABS metadata row layout")
    columns = [a[:-2] for a, v in cells.items()
               if re.fullmatch(r"[A-Z]+10", a) and v == series_id]
    if len(columns) != 1:
        raise ValueError("Expected exactly one series column: " + series_id)
    col = columns[0]
    expected = {1: description, 2: unit, 3: adjustment, 4: data_type,
                5: "Quarter", 6: "3", 10: series_id}
    for row, value in expected.items():
        if cells.get(col + str(row)) != value:
            raise ValueError(f"Unexpected metadata {series_id} row {row}")
    rows = sorted({int(re.search(r"\d+$", a).group()) for a, v in cells.items()
                   if v and re.sub(r"\d+", "", a) in ("A", col)
                   and int(re.search(r"\d+$", a).group()) > 10})
    observations = {}
    for row in rows:
        date_text, value_text = cells.get("A" + str(row)), cells.get(col + str(row))
        if not date_text or not value_text:
            raise ValueError(f"Missing date or observation: {series_id} row {row}")
        index = quarter_index(date_text)
        if index in observations:
            raise ValueError("Duplicate quarter: " + series_id)
        try:
            observations[index] = float(value_text)
        except ValueError as error:
            raise ValueError("Non-numeric observation: " + series_id) from error
    validate_observations(observations)
    if (len(observations) != int(cells[col + "9"]) or
            min(observations) != quarter_index(cells[col + "7"]) or
            max(observations) != quarter_index(cells[col + "8"])):
        raise ValueError("Coverage disagrees with ABS metadata: " + series_id)
    provenance = {"publisher": "ABS", "series_id": series_id,
                  "source_file": book["path"], "source_file_sha256": book["sha256"],
                  "table": table, "sheet": "Data1", "metadata_range": f"{col}1:{col}10",
                  "description": description, "unit": unit, "seasonal_adjustment": adjustment,
                  "data_type": data_type, "frequency": "quarterly",
                  "first_period": period(min(observations)),
                  "last_period": period(max(observations)), "observation_count": len(observations),
                  "publication_date": None, "download_timestamp": None,
                  "vintage_note": "Supplied local snapshot; hash identifies bytes, not original release vintage"}
    return observations, provenance


def growth(levels):
    return {q: 100 * (levels[q] / levels[q - 1] - 1)
            for q in levels if q - 1 in levels}


def calculate(inputs):
    for values in inputs.values():
        validate_observations(values)
    # A shorter tail is allowed; internal gaps have already been rejected.
    common = sorted(set.intersection(*(set(inputs[k]) for k in SPECS)))
    if len(common) < 3:
        raise ValueError("Need at least three common quarters for both growth methods")
    deflators, levels_a, levels_b, rows = {}, {}, {}, []
    for q in common:
        y = inputs["income"][q]
        c = inputs["consumption_current"][q]
        v = inputs["consumption_volume"][q]
        n = inputs["population"][q]
        average = ((inputs["population"][q - 1] + n) / 2
                   if q - 1 in inputs["population"] else None)
        deflators[q] = 100 * c / v
        real_millions = y * v / c
        levels_a[q] = 1000 * real_millions / n
        if average is not None:
            levels_b[q] = 1000 * real_millions / average
        rows.append({"period": period(q), "income_current_aud_millions": y,
                     "consumption_current_aud_millions": c,
                     "consumption_volume_aud_millions": v,
                     "consumption_implicit_price_deflator": deflators[q],
                     "population_end_thousands": n, "population_average_thousands": average,
                     "real_gross_income_aud_millions": real_millions,
                     "real_income_per_capita_a": levels_a[q],
                     "real_income_per_capita_b": levels_b.get(q)})
    ga, gb = growth(levels_a), growth(levels_b)
    paired = sorted(set(ga) & set(gb))
    for q, row in zip(common, rows):
        row.update(growth_a_percent=ga.get(q), growth_b_percent=gb.get(q),
                   growth_b_minus_a_pp=gb[q] - ga[q] if q in ga and q in gb else None)
    differences = {q: gb[q] - ga[q] for q in paired}
    maximum = max(abs(d) for d in differences.values())
    return {"first_common_period": period(common[0]), "latest_common_period": period(common[-1]),
            "common_level_count": len(common), "method_a_growth_count": len(ga),
            "method_b_growth_count": len(gb),
            "unmatched_source_periods": {k: [period(q) for q in values if q not in common]
                                         for k, values in inputs.items()},
            "comparison": {"unit": "percentage_points", "signed_difference": "B minus A",
                           "first_period": period(paired[0]), "latest_period": period(paired[-1]),
                           "observation_count": len(paired), "maximum_absolute_difference_pp": maximum,
                           "maximum_difference_periods": [period(q) for q, d in differences.items()
                                                          if abs(d) == maximum],
                           "average_absolute_difference_pp": statistics.fmean(abs(d) for d in differences.values()),
                           "latest_difference_pp": differences[paired[-1]],
                           "latest_absolute_difference_pp": abs(differences[paired[-1]])},
            "observations": rows}


def build_candidate(input_dir):
    # Persist portable, repository-relative provenance, never workstation paths.
    input_dir = input_dir.resolve()
    try:
        input_dir.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError("Input directory must be within the repository") from error
    books, inputs, sources = {}, {}, {}
    for role, spec in SPECS.items():
        filename = spec[0]
        if filename not in books:
            path = (input_dir / filename).resolve()
            try:
                source_path = path.relative_to(ROOT.resolve()).as_posix()
            except ValueError as error:
                raise ValueError("Input workbook must be within the repository") from error
            books[filename] = read_workbook(path)
            books[filename]["path"] = source_path
        inputs[role], sources[role] = extract_series(books[filename], spec)
    return {"schema_version": "1.0", "model": "AEHI", "code": "E04",
            "name": "Real gross household disposable income per capita growth",
            "data_status": STATUS, "composite_release_status": "HOLD",
            "composite_release_statuses": {k: "HOLD" for k in ("AEHI", "AESI", "ASFI")},
            "score": None, "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "growth_convention": "quarter_on_quarter_percent_non_annualised",
            "sources": sources,
            "methodology": {
                "deflator": "100 * consumption_current / consumption_volume",
                "real_income_aud_millions": "income_current * consumption_volume / consumption_current",
                "method_a": "1000 * real_income_aud_millions / quarter_end_ERP_thousands",
                "method_b": "1000 * real_income_aud_millions / ((ERP_t + ERP_t_minus_1) / 2)",
                "growth": "100 * (unrounded_level_t / unrounded_level_t_minus_1 - 1)",
                "limitations": [
                    "Both methods are candidates; no preferred method approved",
                    "Average adjacent closing ERP is an approximation to quarterly average population",
                    "Income and consumption are seasonally adjusted; ERP is original; derived ratio not independently adjusted",
                    "Gross income includes depreciation; not net disposable income or a distributional measure",
                    "Chain-volume reference year not independently established here; level price base remains unlabelled",
                    "Local workbook publication/download dates unknown; snapshots may have different revision vintages",
                    "No interpolation, projection, population carry-forward or annualisation",
                    "Table 24 inspected during source review; no direct real household income per capita series found there",
                ]},
            **calculate(inputs)}


def write_candidate(candidate, output):
    # Exclusive creation protects previous candidates and all original files.
    output = output.resolve()
    if output.parent != (ROOT / "data-candidates").resolve() or output.suffix != ".json":
        raise ValueError("Output must be a new JSON directly in data-candidates/")
    payload = json.dumps(candidate, indent=2, allow_nan=False) + "\n"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "research-inputs/e04")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data-candidates/aehi-e04-local-review.json")
    args = parser.parse_args()
    candidate = build_candidate(args.input_dir)
    write_candidate(candidate, args.output)
    print(json.dumps({"output": str(args.output), "status": STATUS,
                      "latest_common_period": candidate["latest_common_period"],
                      "comparison": candidate["comparison"]}, indent=2))


if __name__ == "__main__":
    main()
