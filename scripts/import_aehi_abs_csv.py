#!/usr/bin/env python3
"""Create a REVIEW-ONLY AEHI observation candidate from original ABS CSV.

Use an exact, independently validated single ABS series export, not a web page.
The tool never edits aehi-verified-indicators.json and never approves a score.

Example:
 python scripts/import_aehi_abs_csv.py --code E06 --csv labour-force-export.csv \
   --period-column TIME_PERIOD --value-column OBS_VALUE \
   --series-id 'validated ABS identifier here' --frequency monthly \
   --publication-date 2026-10-15 --source-url https://data.api.abs.gov.au/rest/data/...
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import pathlib
import re

ROOT=pathlib.Path(__file__).resolve().parents[1]
PERIOD={"monthly":re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$"),
        "quarterly":re.compile(r"^(\d{4})-Q([1-4])$")}
EXPECTED={"E01":"quarterly","E04":"quarterly","E05":"quarterly","E06":"monthly"}
DATA_STATUS="DATA_IMPORT_REVIEW_REQUIRED"

def quarter_sort(value,freq):
    match=PERIOD[freq].fullmatch(value)
    if not match:raise ValueError(f"Invalid {freq} period: {value!r}")
    year=int(match.group(1));n=int(match.group(2))
    if year < 1950 or year > dt.date.today().year:
        raise ValueError(f"Out-of-range period: {value}")
    return year*12+(n*3 if freq=="quarterly" else n)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--code",required=True,choices=("E01","E04","E05","E06","E12"))
    ap.add_argument("--csv",required=True,type=pathlib.Path)
    ap.add_argument("--period-column",required=True)
    ap.add_argument("--value-column",required=True)
    ap.add_argument("--series-id",required=True)
    ap.add_argument("--frequency",required=True,choices=("monthly","quarterly"))
    ap.add_argument("--publication-date",required=True)
    ap.add_argument("--source-url",required=True)
    ap.add_argument("--unit",default="%")
    ap.add_argument("--series-column")
    ap.add_argument("--output",type=pathlib.Path)
    args=ap.parse_args()
    if args.code in EXPECTED and args.frequency!=EXPECTED[args.code]:
        raise ValueError(f"{args.code} must be {EXPECTED[args.code]} in this pilot")
    # E12 frequency must be approved separately because ABS changed release structure.
    if args.code=="E12":
        raise ValueError("E12 requires a separate approved monthly/quarterly comparability specification")
    if args.unit!="%" or not args.source_url.startswith("https://"):
        raise ValueError("Expected percent values and an HTTPS source")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",args.publication_date):
        raise ValueError("Invalid publication date format")
    dt.date.fromisoformat(args.publication_date)
    if not args.series_id.strip() or args.series_id.strip().lower().startswith("validated"):
        raise ValueError("Official ABS series ID must be specified exactly")
    raw=args.csv.read_bytes()
    if not raw or len(raw)>12_000_000:raise ValueError("Invalid CSV file size")
    rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows:raise ValueError("Empty CSV")
    if args.period_column not in rows[0] or args.value_column not in rows[0]:
        raise ValueError("Required CSV columns not found")
    if args.series_column and args.series_column not in rows[0]:
        raise ValueError("Series ID CSV column not found")
    items=[]
    for row in rows:
        if args.series_column and row[args.series_column]!=args.series_id:continue
        period=row[args.period_column].strip()
        num=row[args.value_column].strip()
        if not num or num.lower() in ("na","null",".."):continue
        key=quarter_sort(period,args.frequency)
        value=float(num)
        if not math.isfinite(value) or abs(value)>1000:raise ValueError("Invalid magnitude")
        items.append((key,{"period":period.replace("-Q"," Q").replace("-", " M") if args.frequency=="monthly" else period.replace("-"," "),
                           "value":round(value,5)}))
    if len(items)<12:raise ValueError("Need at least 12 observations")
    items.sort(key=lambda p:p[0])
    if any(a[0]>=b[0] for a,b in zip(items,items[1:])):
        raise ValueError("Duplicate quarter/month or unstable data selection")
    if args.code=="E06" and any(not 0<=o[1]["value"]<=30 for o in items):
        raise ValueError("Unemployment rate outside conservative bounds")
    # Avoid silently accepting mixed data series where no ID column was used.
    result={"schema_version":"1.0","model":"AEHI","data_status":DATA_STATUS,"composite_release_status":"HOLD",
       "review_warning":"Candidate data only; source series, unit, frequency, growth conventions and calculations still require independent review.",
       "source_file_sha256":hashlib.sha256(raw).hexdigest(),
       "series":[{"code":args.code,"unit":args.unit,"frequency":args.frequency,
       "source":{"publisher":"Australian Bureau of Statistics","verified_series_id":args.series_id,
          "source_url":args.source_url,"publication_date":args.publication_date,
          "source_file_sha256":hashlib.sha256(raw).hexdigest()},
       "observations":[o for _,o in items]}]}
    out=args.output or ROOT / "data-candidates" / ("aehi-"+args.code.lower()+"-review.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(f"Created unapproved {args.code} candidate with {len(items)} observations: {out}")
    print("This file MUST NOT be merged into public AEHI data without methodological review.")

if __name__=="__main__":
    main()
