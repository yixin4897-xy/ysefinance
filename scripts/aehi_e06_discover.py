#!/usr/bin/env python3
"""Inspect (do not publish) ABS Labour Force E06 candidate series via the official Data API.

The prior M9 probe returned approximately 15,500 (thousands), not a rate.
This script now discovers MEASURE codes for the same Australian population and
seasonally-adjusted monthly observations; no guessed measure code is approved.
No public file, approved data or ASFI/AEHI index score is modified.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request

API="https://data.api.abs.gov.au/rest/data/ABS,LF,/.3.1599.20.AUS.M?startPeriod=2026-07&format=csv"
MAX_BYTES=3_000_000

def probe(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!="https" or parsed.hostname!="data.api.abs.gov.au":
        raise ValueError("ABS API only")
    req=urllib.request.Request(url,headers={"Accept":"text/csv","User-Agent":"YSEFinance-AESM/4.1-E06-source-discovery"})
    with urllib.request.urlopen(req,timeout=40) as res:
        if urllib.parse.urlparse(res.geturl()).hostname!="data.api.abs.gov.au":
            raise ValueError("Unexpected API host redirect")
        raw=res.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("Unexpected response size")
    table=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    headers=table.fieldnames or []
    if "TIME_PERIOD" not in headers or "OBS_VALUE" not in headers:
        raise ValueError("ABS returned no SDMX CSV observations")
    data=list(table)
    if not data:raise ValueError("Zero observations")
    if len(data)>1000:raise ValueError("Too many series; discovery must be narrowly scoped")
    dimensions=[h for h in headers if h not in ("TIME_PERIOD","OBS_VALUE","OBS_STATUS","UNIT_MEASURE","UNIT_MULT","DECIMALS","CONF_STATUS","TIME_FORMAT","OBS_CONF","OBS_COM") and not h.endswith("_LABEL")]
    # This is an examination report only; the operator must confirm
    # each dimension using ABS Data Explorer, particularly measure M9.
    by_measure={}
    for row in data:
        key=row.get("MEASURE","")
        by_measure.setdefault(key,[]).append({"period":row.get("TIME_PERIOD"),"value":row.get("OBS_VALUE"),"unit":row.get("UNIT_MEASURE"),"unit_multiplier":row.get("UNIT_MULT")})
    report={"status":"DISCOVERY_ONLY_NOT_APPROVED","source_url":url,"row_count":len(data),
      "measure_candidates":{k:v[-3:] for k,v in sorted(by_measure.items())},
      "columns":headers,"candidate_dimensions":{h:sorted({r.get(h,"") for r in data})[:12] for h in dimensions},
      "first_rows":data[:2],"last_rows":data[-5:],
      "checks_to_complete":["MEASURE is unemployment RATE, not number of unemployed people",
       "SEX is persons / both sexes","AGE is total working-age population",
       "TSEST code 20 means seasonally adjusted","REGION is Australia",
       "FREQ is monthly","OBS_VALUE unit is percentage rather than decimal fraction",
       "Period/release cross-check against ABS Labour Force publication"]}
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,default=Path("data-candidates/aehi-e06-source-discovery.json"))
    args=ap.parse_args()
    report=probe(API)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("E06 candidate source probe succeeded (NOT verified):")
    print("Rows:",report["row_count"])
    print("CSV columns:",", ".join(report["columns"]))
    print("Potential measures and latest values (unapproved):")
    for measure,latest in report["measure_candidates"].items():
        print(measure,":",", ".join(str(x["period"])+ "="+str(x["value"]) for x in latest))
    print("Discovery report:",args.output)
    print("No publicly displayed data or index scores changed.")

if __name__=="__main__":
    main()
