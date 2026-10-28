#!/usr/bin/env python3
"""Offline E12 quarterly scoring experiment; latest-revised research only."""
import argparse
import copy
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import statistics

import aehi_e12_import as importer

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data-candidates/research"
KS = (10, 20, 30)
# Calendar windows are descriptive, predeclared and overlapping; not causal labels.
WINDOWS = {
    "full_history": ("1983-Q1", "2026-Q2"),
    "pre_september_2001": ("1983-Q1", "2001-Q2"),
    "september_2001_onward": ("2001-Q3", "2026-Q2"),
    "post_2011_method_change": ("2011-Q3", "2026-Q2"),
    "early_high_inflation_1983_1990": ("1983-Q1", "1990-Q4"),
    "disinflation_1991_1993": ("1991-Q1", "1993-Q4"),
    "gfc_window_2007_2009": ("2007-Q1", "2009-Q4"),
    "low_inflation_2016_2019": ("2016-Q1", "2019-Q4"),
    "pandemic_2020_2021": ("2020-Q1", "2021-Q4"),
    "inflation_surge_2022_2023": ("2022-Q1", "2023-Q4"),
    "recent_2024_2026q2": ("2024-Q1", "2026-Q2"),
}
FLAGS = ["latest_revised_data_research", "not_point_in_time",
         "research_parameters_not_approved", "historical_target_application_counterfactual"]


def score(inflation, k):
    if isinstance(inflation, bool) or k not in KS:
        raise ValueError("Invalid inflation or research slope")
    try:
        value = Decimal(str(inflation))
    except InvalidOperation as error:
        raise ValueError("Inflation must be numeric") from error
    if not value.is_finite():
        raise ValueError("Inflation must be finite")
    distance = max(Decimal(2) - value, Decimal(0), value - Decimal(3))
    return float(max(Decimal(0), Decimal(100) - k * distance))


def describe(values):
    ordered = sorted(values)
    def percentile(p):
        # Linear interpolation, zero-based position (n-1)*p (type 7).
        position = (len(ordered) - 1) * p
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return {"minimum": ordered[0], "p10": percentile(.1), "p25": percentile(.25),
            "median": statistics.median(values), "mean": statistics.fmean(values),
            "p75": percentile(.75), "p90": percentile(.9), "maximum": ordered[-1],
            "population_stddev": statistics.pstdev(values)}


def summarize(rows):
    if not rows:
        raise ValueError("Empty research window")
    n = len(rows)
    result = {"count": n, "first_period": rows[0]["period"], "last_period": rows[-1]["period"],
              "inflation_percent": describe([r["annual_change_percent"] for r in rows]),
              "below_band_count": sum(r["annual_change_percent"] < 2 for r in rows),
              "in_band_count": sum(2 <= r["annual_change_percent"] <= 3 for r in rows),
              "above_band_count": sum(r["annual_change_percent"] > 3 for r in rows), "scores": {}}
    for k in KS:
        values = [r["scores"][str(k)] for r in rows]
        bins = {"[0,20)": 0, "[20,40)": 0, "[40,60)": 0,
                "[60,80)": 0, "[80,100)": 0, "100": 0}
        labels = list(bins)
        for value in values:
            bins["100" if value == 100 else labels[int(value // 20)]] += 1
        result["scores"][str(k)] = {
            **describe(values), "zero_count": values.count(0), "maximum_count": values.count(100),
            "distribution": {label: {"count": count, "share_percent": 100 * count / n}
                             for label, count in bins.items()},
            "highest_score_quarters": [r["period"] for r, v in zip(rows, values) if v == max(values)],
            "lowest_score_quarters": [r["period"] for r, v in zip(rows, values) if v == min(values)]}
    return result


def calculate(track):
    contract = importer.CONTRACTS["A"]
    if (track.get("series_id") != contract["series_id"] or track.get("frequency") != "Quarter"
            or track.get("unit") != "Percent" or track.get("seasonal_adjustment") != "Seasonally Adjusted"):
        raise ValueError("Only validated Track A quarterly annual inflation is supported")
    rows, previous = [], None
    for observation in track["observations"]:
        date = dt.date.fromisoformat(observation["reference_date"])
        serial = (date - dt.date(1899, 12, 30)).days
        _, index, period = importer.parse_date(serial, contract)
        if period != observation["period"] or (previous is not None and index != previous + 1):
            raise ValueError("Duplicate, missing, unordered or nonquarterly observation")
        previous = index
        value = observation["annual_change_percent"]
        scores = {str(k): score(value, k) for k in KS}
        decimal_value = Decimal(str(value))
        rows.append({**copy.deepcopy(observation),
                     "signed_deviation_from_2_5_pp": float(decimal_value - Decimal("2.5")),
                     "target_band_distance_pp": float(max(Decimal(2)-decimal_value, Decimal(0), decimal_value-Decimal(3))),
                     "score": scores["20"], "scores": scores,
                     "methodology_flags": list(track["methodology_flags"]) + FLAGS})
    if not rows:
        raise ValueError("No quarterly observations")
    return rows


def build_experiment(input_dir=ROOT / "research-inputs/e12"):
    contract = importer.CONTRACTS["A"]
    path = (Path(input_dir) / contract["filename"]).resolve()
    try:
        relative = path.relative_to(ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("Source must be inside repository") from error
    # Read only A. Monthly workbook and build_candidate (which reads B) are never used.
    book = importer.read_workbook(path)
    if book["sha256"] != contract["sha256"]:
        raise ValueError("Track A source hash mismatch")
    book["path"] = relative
    track = importer.extract_series(book, contract)
    rows = calculate(track)
    summaries = {name: summarize([r for r in rows if start <= r["period"] <= end])
                 for name, (start, end) in WINDOWS.items()}
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {"schema_version": "1.0", "experiment": "E12_QUARTERLY_TARGET_BAND_DISTANCE_V1",
            "data_status": importer.STATUS, "research_only": True, "publication_approved": False,
            "parameters_approved": False, "weights_approved": False,
            "composite_release_statuses": dict(importer.HOLD), "composite_score": None,
            "historical_classification": "latest_revised_data_research",
            "real_time_backtesting_eligible": False, "track": "A", "series_id": contract["series_id"],
            "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": track["source"], "input_validation": track["validation"],
            "implementation": {"script": "scripts/aehi_e12_scoring_research.py", "sha256": code_hash},
            "methodology": {"distance": "max(2 - inflation, 0, inflation - 3)",
                            "score": "max(0, 100 - k * distance)", "slopes": list(KS),
                            "provisional_benchmark_k": 20, "sensitivity_candidate_k": 10,
                            "slope_selection_approved": False,
                            "score_direction": "higher_is_closer_to_reference_band",
                            "quantiles": "linear interpolation at (n-1)*p; type 7",
                            "stddev": "population", "windows_overlap": True,
                            "no_interpolation_filling_or_monthly_inputs": True,
                            "flags": FLAGS},
            "window_definitions": {k: list(v) for k, v in WINDOWS.items()},
            "observations": rows, "summaries": summaries,
            "limitations": ["Reference band applies officially to headline CPI; trimmed mean application is a research choice",
                            "Pre-target-regime scores are counterfactual modern-reference descriptions",
                            "34 pre-September-2001 ABS/RBA differences remain unresolved; RBA data not used",
                            "2002 precision history and 2011 seasonal methods require reconciliation",
                            "Quarterly continuity maintained by ABS through December 2025 source changes",
                            "Overlapping annual rates and windows are not independent samples",
                            "Latest-revised snapshot includes information unavailable historically",
                            "No causal, forecast, recession probability, weight or composite validation"]}


def write_experiment(result, output):
    guards = {"data_status": importer.STATUS, "research_only": True, "publication_approved": False,
              "parameters_approved": False, "weights_approved": False, "composite_score": None,
              "composite_release_statuses": importer.HOLD, "real_time_backtesting_eligible": False,
              "historical_classification": "latest_revised_data_research", "track": "A", "series_id": "A3604511X"}
    if any(key not in result or result[key] != value for key, value in guards.items()):
        raise ValueError("Research-only restrictions violated")
    output = Path(output).resolve()
    if output.parent != OUTPUT_DIR.resolve() or output.suffix != ".json":
        raise ValueError("Output must be a new research JSON in data-candidates/research/")
    payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "research-inputs/e12")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "aehi-e12-quarterly-scoring-v1.json")
    args = parser.parse_args()
    result = build_experiment(args.input_dir)
    write_experiment(result, args.output)
    print(json.dumps({"status": result["data_status"], "count": len(result["observations"]),
                      "latest": result["observations"][-1]}, indent=2))


if __name__ == "__main__":
    main()
