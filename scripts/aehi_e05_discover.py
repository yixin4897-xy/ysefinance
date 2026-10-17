#!/usr/bin/env python3
"""Discover E05 HFCE within official ABS ANA_EXP (GDP expenditure) dataflow.

Read-only metadata/one-quarter discovery. Never alters published AEHI data.
The ANA_AGG flow was excluded after source directory inspection showed that
ANA_EXP is the GDP-expenditure dataflow.
"""
import csv
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request

# Filter to chain-volume (M1), seasonally adjusted (20), Australia (AUS),
# and quarterly (Q), subject to validation of actual ANA_EXP dimension order.
URL="https://data.api.abs.gov.au/rest/data/ABS,ANA_EXP,/M1..20.AUS.Q?startPeriod=2026-Q2&endPeriod=2026-Q2&format=csvfilewithlabels"
DEST=Path("data-candidates/aehi-e05-ana-exp-discovery.json")
MAX_BYTES=8_000_000

def main():
    request=urllib.request.Request(URL,headers={
        "User-Agent":"YSEFinance-AESM/4.1-E05-source-discovery",
        "Accept":"text/csv","Accept-Encoding":"identity"})
    with urllib.request.urlopen(request,timeout=45) as response:
        target=urllib.parse.urlparse(response.geturl())
        if target.scheme!="https" or target.hostname!="data.api.abs.gov.au":
            raise ValueError("Unexpected redirect")
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("Query too broad; refine ANA_EXP dimensions")
    table=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields=table.fieldnames or []
    if "OBS_VALUE" not in fields or "TIME_PERIOD" not in fields:
        raise ValueError("Unexpected SDMX CSV format")
    rows=list(table)
    if not rows or len(rows)>2000:raise ValueError("No rows or too many; inspect dataflow dimensions")
    # CSV with labels has both DATA_ITEM (code) and Data Item (readable description).
    item_fields=[x for x in fields if "item" in x.lower() or "component" in x.lower()]
    descriptions=[]
    for row in rows:
        name=" ".join(str(row.get(k,"")) for k in item_fields)
        descriptions.append({"code":row.get("DATA_ITEM"),"name":name,
            "measure":row.get("MEASURE"),"adjustment":row.get("TSEST"),
            "region":row.get("REGION"),"frequency":row.get("FREQ"),
            "period":row.get("TIME_PERIOD"),"value":row.get("OBS_VALUE"),
            "unit":row.get("Unit of Measure",row.get("UNIT_MEASURE")),
            "unit_multiplier":row.get("UNIT_MULT")})
    matches=[v for v in descriptions if any(term in v["name"].lower()
            for term in ("household","consumption","hfce"))]
    report={"status":"DISCOVERY_ONLY_NOT_APPROVED","source_url":URL,
      "csv_columns":fields,"rows_returned":len(rows),
      "candidate_rows":matches,
      "all_row_names":[{"code":x["code"],"name":x["name"]} for x in descriptions[:300]],
      "note":"Confirm total HFCE (exclude government, per capita or subcategory), original chain-volume and seasonal adjustment fields, 2026 Q2 benchmark and exact series before candidate import."}
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("ABS flow: ANA_EXP | rows:",len(rows),"| HFCE-related:",len(matches))
    for x in matches[:30]:
        print("CODE:",x["code"],"|",x["name"],"| VALUE:",x["value"],
              "| ADJUSTMENT:",x["adjustment"],"| UNIT:",x["unit"])
    print("Source discovery saved:",DEST)
    print("No published indicators or index scores changed.")

if __name__=="__main__":main()
