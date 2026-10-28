#!/usr/bin/env python3
"""Fetch a pinned ABS Data API time-series CSV and stage a review-only AEHI candidate.

One configuration is one **exact** SDMX series. API dataflow, key, expected
dimensions, observation units and interpretation must be reviewed first.
No score, public JSON or publication gate can be changed by this command.

Example:
 python scripts/aehi_abs_api_import.py --config docs/aehi-pinned-series.json --code E06
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import pathlib
import re
import urllib.parse
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
API_HOST="data.api.abs.gov.au"
MAX_SIZE=10_000_000
ALLOWED_CODES={"E01","E04","E05","E06","E12"}
QUARTER=re.compile(r"^[12]\d{3}-Q[1-4]$")
MONTH=re.compile(r"^[12]\d{3}-(0[1-9]|1[0-2])$")

def validate_url(url):
    p=urllib.parse.urlparse(url)
    if (p.scheme,p.hostname)!=( "https",API_HOST) or p.username or p.password or p.port:
        raise ValueError("Only the official ABS Data API HTTPS endpoint is allowed")
    if not p.path.startswith("/rest/data/") or "/all" in p.path or len(url)>1800:
        raise ValueError("Explicitly pinned SDMX dataflow and series key required (never /all)")
    parameters=urllib.parse.parse_qs(p.query)
    if parameters.get("format",[""])[0] not in ("csv","csvfilewithlabels"):
        raise ValueError("Use a CSV-format ABS query")
    return url

def read_official_csv(url):
    request=urllib.request.Request(url,headers={
        "User-Agent":"YSEFinance-AESM/4.1 research (review-only)",
        "Accept":"text/csv"})
    with urllib.request.urlopen(request,timeout=35) as response:
        final=urllib.parse.urlparse(response.geturl())
        if final.scheme!="https" or final.hostname!=API_HOST:
            raise ValueError("Unexpected API redirect outside official ABS host")
        raw=response.read(MAX_SIZE+1)
        if len(raw)>MAX_SIZE:raise ValueError("ABS CSV unexpectedly large")
        content_type=response.headers.get("Content-Type","").lower()
        if "html" in content_type:raise ValueError("HTML returned in place of CSV")
    text=raw.decode("utf-8-sig")
    table=csv.DictReader(io.StringIO(text))
    if not {"TIME_PERIOD","OBS_VALUE"}.issubset(set(table.fieldnames or [])):
        raise ValueError("Missing ABS SDMX CSV observation headers")
    return raw,list(table)

def parse(config,rows,digest):
    code=config["code"]
    if code not in ALLOWED_CODES:raise ValueError("Invalid AEHI code")
    if not config.get("approved_series_metadata",False):
        raise ValueError("Series metadata must be independently reviewed before processing")
    dimensions=config.get("expected_dimensions",{})
    if not dimensions or not all(isinstance(k,str) and isinstance(v,str) and v for k,v in dimensions.items()):
        raise ValueError("Exact ABS series dimensions required")
    freq=config.get("frequency")
    if freq not in ("monthly","quarterly"):raise ValueError("Unsupported frequency")
    if code=="E06" and freq!="monthly":raise ValueError("E06 unemployment is monthly")
    if code=="E12":raise ValueError("E12 held pending CPI methodology approval")
    if code in ("E01","E04","E05") and freq!="quarterly":raise ValueError("National Accounts must be quarterly")
    if not config.get("verified_metric_definition") or config.get("value_transform") not in ("identity","ratio_to_percent","qoq_pct_change"):
        raise ValueError("Metric and unit transformation must be explicitly approved")
    observations=[]
    raw_levels=[]
    for row in rows:
        if any(row.get(k)!=v for k,v in dimensions.items()):
            raise ValueError("Downloaded CSV contained unexpected ABS series dimensions")
        period=row.get("TIME_PERIOD","")
        if not (MONTH if freq=="monthly" else QUARTER).fullmatch(period):
            raise ValueError("Wrong period convention: "+period)
        value_text=row.get("OBS_VALUE","")
        if value_text in ("","..","null","na"):
            raise ValueError("Missing observation for "+period)
        try: value=float(value_text)
        except ValueError as ex:raise ValueError("Invalid OBS_VALUE") from ex
        if not (-1e10<value<1e10):raise ValueError("Out-of-range magnitude")
        if config["value_transform"]=="qoq_pct_change" and value<=0:
            raise ValueError("Growth base levels must be strictly positive")
        if config["value_transform"]=="ratio_to_percent":value*=100
        if code=="E06" and not 0<=value<=30:raise ValueError("Invalid unemployment rate")
        display=period.replace("-Q"," Q") if freq=="quarterly" else period.replace("-", " M")
        raw_levels.append((period,value,display))
    if config["value_transform"]=="qoq_pct_change":
        if freq!="quarterly" or code not in ("E01","E04","E05"):
            raise ValueError("QoQ transformation is reserved for quarterly national accounts")
        for i in range(1,len(raw_levels)):
            prev,base,_=raw_levels[i-1]
            period,value,display=raw_levels[i]
            def quarter_index(v):
                y,q=v.split("-Q")
                return int(y)*4+int(q)
            if quarter_index(period)!=quarter_index(prev)+1:
                raise ValueError("Missing quarter in source levels before growth computation")
            observations.append({"period":display,"value":round((value/base-1)*100,5)})
    else:
        observations=[{"period":display,"value":round(value,5)} for _,value,display in raw_levels]
    if len(observations)<12:raise ValueError("Insufficient observations")
    if code in ("E01","E04","E05") and config["value_transform"]=="identity":
        raise ValueError("National Accounts raw level cannot be displayed as growth percentage")
    if any(a["period"]>=b["period"] for a,b in zip(observations,observations[1:])):
        raise ValueError("Duplicate or out-of-order ABS observations")
    return {"code":code,"name":config["verified_metric_definition"],"unit":"%",
            "frequency":freq,"source":{"publisher":"ABS","verified_series_id":config["series_id"],
            "source_url":config["url"],"source_file_sha256":digest,
            "publication_date":None,"review_required_for_publication_date":True},
            "growth_convention":("quarter_on_quarter_percent" if config["value_transform"]=="qoq_pct_change" else "original_source_units"),
            "observations":observations}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--config",type=pathlib.Path,required=True)
    p.add_argument("--code",choices=sorted(ALLOWED_CODES),required=True)
    p.add_argument("--output",type=pathlib.Path)
    args=p.parse_args()
    manifest=json.loads(args.config.read_text(encoding="utf-8"))
    matching=[x for x in manifest.get("series",[]) if x.get("code")==args.code]
    if len(matching)!=1:raise ValueError("A single pinned, approved ABS series configuration is required")
    cfg=matching[0]
    validate_url(cfg["url"])
    raw,rows=read_official_csv(cfg["url"])
    if not rows:raise ValueError("Empty source series")
    candidate=parse(cfg,rows,hashlib.sha256(raw).hexdigest())
    output={"model":"AEHI","data_status":"DATA_IMPORT_REVIEW_REQUIRED",
            "composite_release_status":"HOLD",
            "review_note":"NOT FOR PUBLICATION. Verify ABS source release date, original metadata, series IDs, growth horizon, seasonal adjustment and revisions.",
            "series":[candidate]}
    path=args.output or ROOT/"data-candidates"/("aehi-"+args.code.lower()+"-api-review.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(args.code,"staged",len(candidate["observations"]),"observations for review at",path)
    print("Public AEHI data and index scoring not changed.")

if __name__=="__main__":
    main()
