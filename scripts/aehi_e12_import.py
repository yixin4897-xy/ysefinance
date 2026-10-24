#!/usr/bin/env python3
"""Offline, snapshot-pinned E12 Candidate V1. No production or network path."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import re

from aehi_e04_import import read_workbook

ROOT = Path(__file__).resolve().parents[1]
STATUS = "CANDIDATE_ONLY_PENDING_VALIDATION"
HOLD = {name: "HOLD" for name in ("AEHI", "AESI", "ASFI")}
RELEASE = "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/aug-2026"
CONTRACTS = {
    "A": {
        "filename": "64010Appendix1a.xlsx", "series_id": "A3604511X",
        "description": "Percentage Change from Corresponding Quarter of Previous Year ;  Trimmed Mean ;  Australia ;",
        "table": "APPENDIX 1a. CPI: Quarterly Analytical Series and Seasonal Adjustment Factors on pre-October 2025 basis",
        "frequency": "Quarter", "interval": "3", "column": "I",
        "first": "1983-Q1", "last": "2026-Q2", "count": 174,
        "grid_first": "1972-Q3", "grid_last": "2027-Q2", "leading": 42, "trailing": 4,
        "sha256": "71f8b078d9fc59b011ad1bf3ae77ce23c6dee7eb667fc276acf6821e9bc11f02",
        "methodology_flags": ["established_quarterly_pre_october_2025_basis",
                              "historical_method_changes_unresolved", "seasonal_revisions",
                              "december_2025_source_changes_abs_continuity_maintained"],
    },
    "B": {
        "filename": "640106.xlsx", "series_id": "A130400382R",
        "description": "Percentage Change from Corresponding Month of Previous Year ;  Trimmed Mean ;  Australia ;",
        "table": "TABLE 6. CPI: Analytical Series, Weighted Average of Eight Capital Cities",
        "frequency": "Month", "interval": "1", "column": "AH",
        "first": "2025-04", "last": "2026-08", "count": 17,
        "grid_first": "2024-04", "grid_last": "2026-08", "leading": 12, "trailing": 0,
        "sha256": "1df9e8b27beb31c8ab3ed36ee8f9d309fb0e0e61706d48df17fcf766ce44f01a",
        "methodology_flags": ["complete_monthly_not_monthly_cpi_indicator",
                              "short_annual_history", "evolving_monthly_seasonal_factors",
                              "seasonal_revisions"],
    },
}
LABELS = {2: "Unit", 3: "Series Type", 4: "Data Type", 5: "Frequency",
          6: "Collection Month", 7: "Series Start", 8: "Series End",
          9: "No. Obs", 10: "Series ID"}


def parse_date(serial, contract):
    try:
        value = float(serial)
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError()
        date = dt.date(1899, 12, 30) + dt.timedelta(days=value)
        if date.year < 1950 or date.day != 1:
            raise ValueError()
        if contract["frequency"] == "Quarter":
            if date.month not in (3, 6, 9, 12):
                raise ValueError()
            return date, date.year * 4 + date.month // 3 - 1, f"{date.year}-Q{date.month // 3}"
        return date, date.year * 12 + date.month - 1, f"{date.year}-{date.month:02d}"
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("Invalid ABS observation date: " + str(serial)) from error


def extract_series(book, contract):
    cells = book["sheets"].get("Data1", {})
    if book["sheets"].get("Index", {}).get("B6") != contract["table"]:
        raise ValueError("Unexpected ABS table")
    if any(cells.get(f"A{r}") != v for r, v in LABELS.items()):
        raise ValueError("Unexpected metadata layout")
    columns = [a[:-2] for a, v in cells.items()
               if re.fullmatch(r"[A-Z]+10", a) and v == contract["series_id"]]
    if len(columns) != 1:
        raise ValueError("Expected exactly one exact ABS Series ID")
    col = columns[0]
    expected = {1: contract["description"], 2: "Percent", 3: "Seasonally Adjusted",
                4: "PERCENT", 5: contract["frequency"], 6: contract["interval"]}
    for r, value in expected.items():
        if cells.get(f"{col}{r}") != value:
            raise ValueError(f"Unexpected metadata row {r}")
    rows = sorted({int(re.search(r"\d+$", a).group()) for a, v in cells.items()
                   if v and re.fullmatch(r"(?:A|" + col + r")\d+", a)
                   and int(re.search(r"\d+$", a).group()) > 10})
    observations, grid, blanks = [], [], []
    for r in rows:
        date, index, period = parse_date(cells.get(f"A{r}"), contract)
        if grid and index != grid[-1][0] + 1:
            raise ValueError("Duplicate, unordered or missing reference period")
        grid.append((index, period))
        text = cells.get(f"{col}{r}", "")
        if text == "":
            blanks.append(period)
            continue
        try:
            value = float(text)
            if not math.isfinite(value):
                raise ValueError()
        except (TypeError, ValueError) as error:
            raise ValueError("Non-numeric or nonfinite annual observation") from error
        observations.append({"period": period, "reference_date": date.isoformat(),
                             "annual_change_percent": value, "source_cell": f"{col}{r}"})
    if not observations:
        raise ValueError("No observations")
    periods = [o["period"] for o in observations]
    if any(periods[0] < p < periods[-1] for p in blanks):
        raise ValueError("Missing internal observation")
    try:
        coverage = (parse_date(cells[f"{col}7"], contract)[2],
                    parse_date(cells[f"{col}8"], contract)[2], int(cells[f"{col}9"]))
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("Invalid coverage metadata") from error
    if coverage != (periods[0], periods[-1], len(observations)):
        raise ValueError("Coverage disagrees with metadata")
    if coverage != (contract["first"], contract["last"], contract["count"]):
        raise ValueError("Coverage disagrees with validated snapshot contract")
    if (grid[0][1], grid[-1][1], sum(p < periods[0] for p in blanks),
            sum(p > periods[-1] for p in blanks)) != (
            contract["grid_first"], contract["grid_last"], contract["leading"], contract["trailing"]):
        raise ValueError("Unexpected grid coverage or missing data")
    return {"series_id": contract["series_id"], "frequency": contract["frequency"],
            "unit": "Percent", "seasonal_adjustment": "Seasonally Adjusted",
            "description": contract["description"], "methodology_flags": contract["methodology_flags"],
            "source": {"publisher": "ABS", "source_file": book["path"],
                       "sha256": book["sha256"], "source_url": RELEASE + "/" + contract["filename"],
                       "release_vintage": "August 2026", "publication_date": "2026-09-30",
                       "vintage_basis": "Byte identity independently verified against official ABS downloads during local source validation",
                       "original_download_timestamp": None, "table": contract["table"],
                       "sheet": "Data1", "metadata_range": f"{col}1:{col}10",
                       "date_column": "A", "observation_column": col,
                       "date_system": "Excel 1900", "date_display_format": "mmm\\-yyyy"},
            "validation": {"first_period": periods[0], "last_period": periods[-1],
                           "observation_count": len(observations), "internal_missing_count": 0,
                           "leading_missing_count": contract["leading"],
                           "trailing_missing_count": contract["trailing"],
                           "excluded_blank_periods": blanks, "grid_count": len(grid),
                           "exact_metadata_validated": True, "coverage_validated": True,
                           "source_hash_validated": True},
            "latest": observations[-1], "observations": observations}


def build_candidate(input_dir):
    tracks = {}
    for track, contract in CONTRACTS.items():
        path = (Path(input_dir) / contract["filename"]).resolve()
        try:
            relative = path.relative_to(ROOT.resolve()).as_posix()
        except ValueError as error:
            raise ValueError("Source must be within repository") from error
        book = read_workbook(path)
        if book["sha256"] != contract["sha256"]:
            raise ValueError("Source SHA-256 differs from validated release snapshot")
        book["path"] = relative
        tracks[track] = extract_series(book, contract)
    return {"schema_version": "1.0", "model": "AEHI", "code": "E12",
            "name": "Trimmed Mean Inflation", "candidate_version": "V1",
            "data_status": STATUS, "composite_release_status": "HOLD",
            "composite_release_statuses": dict(HOLD), "score": None,
            "publication_approved": False, "production_pinned": False,
            "real_time_backtesting_eligible": False,
            "historical_classification": "latest_revised_data_research",
            "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "track_policy": "independent_no_splicing_filling_averaging_or_substitution",
            "value_convention": "published_annual_percentage_change_no_recomputation",
            "outstanding_validation_issues": [
                "Reconcile earliest ABS back-history and documented 2002 precision / 2011 seasonal-adjustment changes",
                "Explain 34 ABS/RBA annual differences through June 2001 before substitution or calibration",
                "Approve scoring frequency and historical window; assess monthly revision sensitivity",
                "Historical as-of vintages unavailable; real-time backtesting prohibited"],
            "tracks": tracks}


def write_candidate(candidate, output):
    if (candidate.get("code") != "E12" or candidate.get("candidate_version") != "V1"
            or candidate.get("data_status") != STATUS
            or candidate.get("composite_release_status") != "HOLD"
            or candidate.get("composite_release_statuses") != HOLD
            or "score" not in candidate or candidate["score"] is not None
            or any(candidate.get(k) is not False for k in
                   ("publication_approved", "production_pinned", "real_time_backtesting_eligible"))
            or candidate.get("historical_classification") != "latest_revised_data_research"
            or candidate.get("track_policy") != "independent_no_splicing_filling_averaging_or_substitution"
            or candidate.get("value_convention") != "published_annual_percentage_change_no_recomputation"):
        raise ValueError("Candidate-only restrictions must remain enforced")
    if set(candidate.get("tracks", {})) != set(CONTRACTS):
        raise ValueError("Independent tracks required")
    for key, contract in CONTRACTS.items():
        track = candidate["tracks"][key]
        if (track.get("series_id") != contract["series_id"]
                or track.get("frequency") != contract["frequency"]
                or track.get("source", {}).get("sha256") != contract["sha256"]):
            raise ValueError("Independent track contract violated")
    output = Path(output).resolve()
    if output.parent != (ROOT / "data-candidates").resolve() or output.suffix != ".json":
        raise ValueError("Output must be a new JSON directly in data-candidates/")
    payload = json.dumps(candidate, indent=2, allow_nan=False) + "\n"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "research-inputs/e12")
    parser.add_argument("--output", type=Path, default=ROOT / "data-candidates/aehi-e12-local-review.json")
    args = parser.parse_args()
    candidate = build_candidate(args.input_dir)
    write_candidate(candidate, args.output)
    print(json.dumps({k: {"count": v["validation"]["observation_count"], "latest": v["latest"]}
                      for k, v in candidate["tracks"].items()}, indent=2))


if __name__ == "__main__":
    main()
