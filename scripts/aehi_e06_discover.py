#!/usr/bin/env python3
"""Inspect (do not publish) ABS Labour Force E06 candidate series via the official Data API.

The ABS Labour Force Data Explorer link identifies dataflow LF and provides
M9.3.1599.30+10+20.AUS.M as a set of estimation-method series. We PROBE
the 20 member and verify labels before treating it as a valid E06.
No public file, approved data or ASFI/AEHI index score is modified.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request

API="https://data.api.abs.gov.au/rest/data/ABS,LF,/M9.3.1599.20.AUS.M?startPeriod=2023-01&format=csv"
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
    dimensions=[h for h in headers if h not in ("TIME_PERIOD","OBS_VALUE","OBS_STATUS","UNIT_MEASURE","UNIT_MULT","DECIMALS","CONF_STATUS","TIME_FORMAT","OBS_CONF","OBS_COM") and not h.endswith("_LABEL")]
    # This is an examination report only; the operator must confirm
    # each dimension using ABS Data Explorer, particularly measure M9.
    report={"status":"DISCOVERY_ONLY_NOT_APPROVED","source_url":url,"row_count":len(data),
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
    print("Latest 3 observations:")
    for row in report["last_rows"][-3:]:
        print(row.get("TIME_PERIOD"),row.get("OBS_VALUE")," | ",
              "; ".join(f"{k}={v}" for k,v in report["candidate_dimensions"].items()))
    print("Discovery report:",args.output)
    print("No publicly displayed data or index scores changed.")

if __name__=="__main__":
    main()
