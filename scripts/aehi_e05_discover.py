#!/usr/bin/env python3
"""Discover candidate E05 household consumption series via ABS ANA_AGG.

Read-only discovery. An apparent match is NOT approved for publication.
Uses a narrow one-quarter query; verifies labels, dimensions and source units.
"""
import csv
import io
import json
import pathlib
import urllib.request
import urllib.parse

URL="https://data.api.abs.gov.au/rest/data/ABS,ANA_AGG,/M1..20.AUS.Q?startPeriod=2026-Q2&endPeriod=2026-Q2&format=csvfilewithlabels"
DEST=pathlib.Path("data-candidates/aehi-e05-source-discovery.json")
def main():
    request=urllib.request.Request(URL,headers={"User-Agent":"YSEFinance-AESM/4.1-review-only","Accept":"text/csv"})
    with urllib.request.urlopen(request,timeout=45) as response:
        if urllib.parse.urlparse(response.geturl()).hostname!="data.api.abs.gov.au": raise ValueError("Unexpected origin")
        content=response.read(5_000_001)
        if len(content)>5_000_000:raise ValueError("Too many results; refine query")
    table=csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    columns=table.fieldnames or []
    rows=list(table)
    if "OBS_VALUE" not in columns or "TIME_PERIOD" not in columns: raise ValueError("Not ABS observations")
    if len(rows)>1000: raise ValueError("Unexpectedly broad query")
    # ABS CSV labels use a human-readable "Data Item" column in addition to
    # the machine-readable DATA_ITEM code. Keep both during discovery.
    fields=("DATA_ITEM","Data Item","MEASURE","Measure","TSEST","Adjustment Type",
            "REGION","Region","FREQ","Frequency","TIME_PERIOD","OBS_VALUE",
            "UNIT_MEASURE","Unit of Measure","UNIT_MULT","Unit of Multiplier")
    details=[{k:row.get(k,"") for k in fields if k in columns} for row in rows]
    matches=[row for row in details if any(term in
        (str(row.get("Data Item",""))+" "+str(row.get("DATA_ITEM",""))).lower()
        for term in ("household","consumption","hfce"))]
    report={"status":"DISCOVERY_ONLY_NOT_APPROVED","source_url":URL,"csv_columns":columns,
       "rows_returned":len(rows),"candidate_rows":details,
       "possible_consumption_rows":matches,
       "note":"Discovery only. Confirm HFCE total (not government consumption or GDP), chain volume, seasonal adjustment, Australia, quarter, units and source revision before importing E05."}
    DEST.parent.mkdir(exist_ok=True,parents=True)
    DEST.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Rows examined:",len(rows),"candidate labels:",len(matches))
    for row in details:
        print("CODE:",row.get("DATA_ITEM",""),"LABEL:",row.get("Data Item",""),
              "PERIOD:",row.get("TIME_PERIOD",""),"VALUE:",row.get("OBS_VALUE",""),
              "UNIT:",row.get("Unit of Measure",row.get("UNIT_MEASURE","")))
    print("Saved review-only discovery file:",DEST)
    print("No AEHI public data or composite scores changed.")
if __name__=="__main__":main()
