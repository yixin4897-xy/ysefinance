#!/usr/bin/env python3
"""Discover E05 HFCE codes in ABS ANA_EXP using its verified 6-D key order.

ANA_EXP dimensions: MEASURE.DATA_ITEM.SECTOR.TSEST.REGION.FREQ.
Only one quarter is requested. This is a read-only candidate probe: no
publication of ABS observations or AEHI/ASFI/AESI composite scores.
"""
import csv
import io
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

# M1 = chain-volume measure candidate; blank DATA_ITEM and SECTOR mean
# discover all codes. 20 = seasonally adjusted, AUS = Australia, Q = quarterly.
# All dimension definitions still require checking against SDMX codelists.
KEY="M1...20.AUS.Q"
URL=f"https://data.api.abs.gov.au/rest/data/ABS,ANA_EXP,/{KEY}?startPeriod=2026-Q2&endPeriod=2026-Q2&format=csvfilewithlabels"
DEST=Path("data-candidates/aehi-e05-ana-exp-discovery.json")
LIMIT=8_000_000

def main():
    req=urllib.request.Request(URL,headers={"User-Agent":"YSEFinance-AESM/4.1-data-discovery","Accept":"text/csv"})
    try:
        with urllib.request.urlopen(req,timeout=50) as resp:
            parsed=urllib.parse.urlparse(resp.geturl())
            if parsed.scheme!="https" or parsed.hostname!="data.api.abs.gov.au":
                raise ValueError("Unexpected API redirect")
            raw=resp.read(LIMIT+1)
    except urllib.error.HTTPError as ex:
        details=ex.read(1200).decode("utf-8",errors="replace")
        raise RuntimeError(f"ABS Data API returned HTTP {ex.code}: {details}") from ex
    if len(raw)>LIMIT:raise ValueError("Candidate response too large; narrow query")
    table=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    columns=table.fieldnames or []
    if not {"DATA_ITEM","TIME_PERIOD","OBS_VALUE"}.issubset(columns):
        raise ValueError("Unexpected CSV columns: "+str(columns))
    rows=list(table)
    if not rows or len(rows)>1200:raise ValueError("Candidate query returned zero or too many observations")
    fields=("MEASURE","Measure","DATA_ITEM","Data Item","SECTOR","Sector","TSEST",
            "Adjustment Type","REGION","Region","FREQ","Frequency","TIME_PERIOD",
            "OBS_VALUE","UNIT_MEASURE","Unit of Measure","UNIT_MULT")
    selected=[{k:r.get(k,"") for k in fields if k in columns} for r in rows]
    matches=[r for r in selected if any(w in
       (str(r.get("Data Item",""))+" "+str(r.get("DATA_ITEM",""))).lower()
       for w in ("household","consumption","hfce"))]
    result={"status":"DISCOVERY_ONLY_NOT_APPROVED","source_url":URL,
        "dimensions":"MEASURE.DATA_ITEM.SECTOR.TSEST.REGION.FREQ",
        "row_count":len(selected),"matching_rows":matches,
        "all_candidate_codes":[{"code":r.get("DATA_ITEM"),"label":r.get("Data Item"),
                                "sector":r.get("SECTOR"),"sector_label":r.get("Sector")} for r in selected],
        "note":"Confirm Household Final Consumption Expenditure TOTAL, chain-volume, seasonally adjusted, Australia and reference-quarter source level before calculating QoQ growth."}
    DEST.parent.mkdir(exist_ok=True,parents=True)
    DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ANA_EXP six-dimensional query:",KEY)
    print("Rows returned:",len(rows),"possible HFCE:",len(matches))
    for r in matches[:25]:
        print("CODE:",r.get("DATA_ITEM"),"LABEL:",r.get("Data Item"),
              "SECTOR:",r.get("SECTOR"),"VALUE:",r.get("OBS_VALUE"),
              "UNIT:",r.get("Unit of Measure",r.get("UNIT_MEASURE")))
    print("Review file:",DEST)
    print("No website values or composite scores changed.")
if __name__=="__main__":
    main()
