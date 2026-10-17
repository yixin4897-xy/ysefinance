#!/usr/bin/env python3
"""ASFI V3.7: import two RBA quarterly series from original E2/E13 CSV files.

No score calculations. This produces a REVIEW CANDIDATE, not an automatically
approved public data release. Run:
  python scripts/import_asfi_rba.py --e2 path/to/e2-data.csv --e13 path/to/e13-data.csv
Or with direct downloads:
  python scripts/import_asfi_rba.py --download

Review the output and its provenance, then commit asfi-indicators.json separately.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
URLS = {
    "E2": "https://www.rba.gov.au/statistics/tables/csv/e2-data.csv",
    "E13": "https://www.rba.gov.au/statistics/tables/csv/e13-data.csv",
}
SERIES = {
    "S01": ("E2", "BHFDDIT", "Household debt to disposable income"),
    "S02": ("E13", "LPHTICRI", "Housing interest charged to household disposable income"),
}
APPROVAL = "DATA_IMPORT_REVIEW_REQUIRED"


def download(table):
    request = urllib.request.Request(URLS[table], headers={
        "User-Agent": "YSEFinance-AESM-Research/3.7 (contact: website contact form)",
        "Accept": "text/csv,text/plain,*/*",
    })
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(3_000_001)
    if not data or len(data) > 3_000_000:
        raise ValueError(f"{table}: empty/oversize file")
    return data


def text_decode(raw):
    return raw.decode("utf-8-sig")


def quarter_of(raw):
    value = raw.strip().strip('"')
    if not value:
        return None
    candidates = ("%d-%b-%Y", "%b-%Y", "%d/%m/%Y", "%Y-%m-%d",
                  "%Y/%m/%d", "%b %Y", "%Y-%m")
    for fmt in candidates:
        try:
            date = dt.datetime.strptime(value, fmt)
            if date.month not in (3, 6, 9, 12):
                return None
            return f"{date.year} Q{date.month // 3}"
        except ValueError:
            pass
    return None


def parse_csv(raw, table, series_id):
    rows = list(csv.reader(io.StringIO(text_decode(raw))))
    if len(rows) < 20:
        raise ValueError(f"{table}: unexpectedly short RBA CSV")
    header_idx = next((idx for idx, row in enumerate(rows[:30])
                       if row and row[0].strip().lower() == "series id"), None)
    if header_idx is None:
        raise ValueError(f"{table}: missing RBA Series ID metadata row")
    header = [x.strip() for x in rows[header_idx]]
    matches = [idx for idx, val in enumerate(header) if val == series_id]
    if len(matches) != 1:
        raise ValueError(f"{table}: series ID {series_id} absent or duplicated")
    col = matches[0]
    meta = {}
    for row in rows[:header_idx]:
        if len(row) > col and row:
            label = row[0].strip().lower().replace(" ", "_")
            if label:
                meta[label] = row[col].strip()
    desc = " | ".join([meta.get("title", ""),meta.get("description", "")]).lower()
    expected = "household debt to income" if table == "E2" else "interest charged to income"
    # Do not silently accept the wrong series when upstream metadata changes.
    if expected not in desc:
        raise ValueError(f"{table}: unexpected series label for {series_id}: {desc!r}")
    units = meta.get("units", "").strip()
    if units and not any(x in units.lower() for x in ("percent", "per cent", "%")):
        raise ValueError(f"{table}: expected percentage units, got {units!r}")
    observations = []
    for row in rows[header_idx + 1:]:
        if not row:
            continue
        period = quarter_of(row[0])
        if not period or len(row) <= col:
            continue
        value = row[col].strip().replace(",", "")
        if value in ("", "NA", "na", "-", "..", "n.a."):
            continue
        try:
            number = float(value)
        except ValueError:
            raise ValueError(f"{table}: invalid observation {period}: {value!r}")
        if not math.isfinite(number) or number < 0 or number > 1000:
            raise ValueError(f"{table}: out-of-bounds observation {period}: {number}")
        observations.append({"period": period, "value": round(number, 3)})
    if len(observations) < 12:
        raise ValueError(f"{table}: need at least 12 quarterly observations")
    keys = [x["period"] for x in observations]
    if len(set(keys)) != len(keys) or keys != sorted(keys, key=lambda p: (int(p[:4]),int(p[-1]))):
        raise ValueError(f"{table}: duplicate/out-of-order periods")
    current = dt.datetime.now(dt.timezone.utc)
    max_period = f"{current.year} Q{(current.month - 1)//3+1}"
    if keys[-1] > max_period:
        raise ValueError(f"{table}: future dated observation {keys[-1]}")
    return {
        "observations": observations,
        "source": {
            "publisher": "Reserve Bank of Australia",
            "table": table,
            "series_id": series_id,
            "series_description": meta.get("title", "") or meta.get("description", ""),
            "units": units or "Percent",
            "source_url": URLS[table],
            "publication_date_raw": meta.get("publication_date"),
            "csv_sha256": hashlib.sha256(raw).hexdigest(),
        },
    }


def produce(e2, e13):
    raws = {"E2": e2, "E13": e13}
    results = []
    for code, (table, series_id, title) in SERIES.items():
        record = parse_csv(raws[table], table, series_id)
        results.append({"code": code, "name": title, "unit": "%",
                        "source": record["source"],
                        "observations": record["observations"]})
    return {
        "schema_version": "1.0",
        "model": "ASFI",
        "data_status": APPROVAL,
        "composite_release_status": "HOLD",
        "source_retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "data_vintage": "Current RBA CSV download; historical observations may contain revisions; NOT point-in-time archived vintages.",
        "notes": "Raw source indicators only. No ASFI scores, model weights or risk ratings.",
        "series": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2", type=pathlib.Path)
    parser.add_argument("--e13", type=pathlib.Path)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "asfi-indicators.json")
    args = parser.parse_args()
    if args.download:
        if args.e2 or args.e13:
            parser.error("choose either --download or both local CSV paths")
        e2, e13 = download("E2"), download("E13")
    elif args.e2 and args.e13:
        e2, e13 = args.e2.read_bytes(), args.e13.read_bytes()
    else:
        parser.error("supply --download or both --e2 and --e13")
    result = produce(e2,e13)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in result["series"]:
        last = item["observations"][-1]
        print(f"{item['code']} ({item['source']['series_id']}): {len(item['observations'])} quarterly values, latest {last['period']} {last['value']}%")
    print(f"Prepared {args.output} with status {APPROVAL}; review before committing or publishing.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"IMPORT FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
