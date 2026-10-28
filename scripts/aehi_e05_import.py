
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

SOURCE = Path("data-candidates/aehi-e05-official.csv")
CURRENT = Path("aehi-verified-indicators.json")
OUTPUT = Path("data-candidates/aehi-e05-proposed.json")

SERIES_KEY = "PCT_VCH.FCE.PHS.20.AUS.Q"
EXPECTED = {
    "MEASURE": "PCT_VCH",
    "DATA_ITEM": "FCE",
    "SECTOR": "PHS",
    "TSEST": "20",
    "REGION": "AUS",
    "FREQ": "Q",
}

URL = (
    "https://data.api.abs.gov.au/rest/data/"
    "ABS,ANA_EXP,1.0.0/"
    + SERIES_KEY
    + "?startPeriod=2024-Q1"
)

def main():
    raw = SOURCE.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()

    with SOURCE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        rows = list(csv.DictReader(file))

    if len(rows) != 10:
        raise ValueError(
            f"Expected 10 observations, found {len(rows)}"
        )

    observations = []
    seen = set()

    for row in rows:
        for field, expected in EXPECTED.items():
            if row[field] != expected:
                raise ValueError(
                    f"Invalid {field}: {row[field]}"
                )

        period = row["TIME_PERIOD"]
        if period in seen:
            raise ValueError(f"Duplicate period: {period}")

        seen.add(period)

        value = float(row["OBS_VALUE"])

        observations.append({
            "period": period.replace("-", " "),
            "value": value,
        })

    observations.sort(key=lambda x: x["period"])

    expected_periods = [
        f"{year} Q{quarter}"
        for year in range(2024, 2027)
        for quarter in range(1, 5)
        if (year, quarter) <= (2026, 2)
    ]

    if [x["period"] for x in observations] != expected_periods:
        raise ValueError("Missing or unexpected quarters")

    latest = observations[-1]

    if latest["value"] != 0.4:
        raise ValueError("Latest value differs from review")

    dataset = json.loads(
        CURRENT.read_text(encoding="utf-8-sig")
    )

    if dataset["composite_release_status"] != "HOLD":
        raise ValueError("Composite score must remain HOLD")

    codes = [s["code"] for s in dataset["series"]]

    if sorted(codes) != ["E01", "E06"]:
        raise ValueError(
            f"Unexpected existing indicators: {codes}"
        )

    e05 = {
        "code": "E05",
        "name": "Real Household Consumption Growth",
        "unit": "%",
        "frequency": "quarterly",
        "source": {
            "publisher": "ABS",
            "verified_series_id": (
                "ABS:ANA_EXP/1.0.0 / " + SERIES_KEY
            ),
            "source_url": URL,
            "source_file_sha256": sha256,
            "publication_date": "2026-09-02",
            "review_required_for_publication_date": True,
            "publication_date_role": (
                "ABS June 2026 National Accounts official release date; "
                "not an archived API data vintage"
            ),
            "source_file_reviewed_date": str(date.today()),
            "data_vintage": (
                "Current ABS API observations; "
                "not archived original-release vintage"
            ),
        },
        "growth_convention": "quarter_on_quarter_percent",
        "observations": observations,
    }

    dataset["series"].append(e05)
    dataset["series"].sort(key=lambda x: x["code"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            dataset,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    print("E05 candidate import prepared")
    print("Existing E01 and E06 preserved")
    print("Observation count:", len(observations))
    print("Latest:", latest)
    print("SHA256:", sha256)
    print("Composite:", dataset["composite_release_status"])
    print("Output:", OUTPUT)
    print("Canonical dataset NOT modified")


if __name__ == "__main__":
    main()
