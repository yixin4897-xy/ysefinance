#!/usr/bin/env python3
"""Inspect actual SDMX dimension order for ABS ANA_EXP E05 discovery.

The earlier guessed ANA_AGG-shaped data key returned HTTP 422.
This tool makes a METADATA-ONLY request, does not fetch raw time series,
and never touches the public dashboard or composite scores.
"""
import json
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

URL="https://data.api.abs.gov.au/rest/dataflow/ABS/ANA_EXP/1.0.0?references=all"
OUT=Path("data-candidates/aehi-e05-ana-exp-structure.json")
MAX=6_000_000

def main():
    req=urllib.request.Request(URL,headers={"User-Agent":"YSEFinance-AESM/4.1-metadata-discovery","Accept":"application/xml"})
    with urllib.request.urlopen(req,timeout=50) as resp:
        target=urllib.parse.urlparse(resp.geturl())
        if target.scheme!="https" or target.hostname!="data.api.abs.gov.au":
            raise ValueError("Unexpected origin")
        raw=resp.read(MAX+1)
    if len(raw)>MAX:raise ValueError("Metadata response too large")
    root=ET.fromstring(raw)
    def local(tag):return tag.rsplit("}",1)[-1]
    structures=[]
    for dsd in root.iter():
        if local(dsd.tag)!="DataStructure":continue
        dimensions=[]
        for elem in dsd.iter():
            if local(elem.tag) not in ("Dimension","TimeDimension"):continue
            dims={"id":elem.get("id"),"position":elem.get("position")}
            refs=[x.attrib for x in elem.iter() if local(x.tag)=="Ref"]
            if refs:dims["references"]=refs[:3]
            dimensions.append(dims)
        if dimensions:
            structures.append({"id":dsd.get("id"),"version":dsd.get("version"),"dimensions":dimensions})
    report={"status":"DISCOVERY_ONLY_NOT_APPROVED","request_url":URL,"data_structures":structures,
       "warning":"No E05 series value or estimated growth rate is approved. Fix query key only after inspecting the real ANA_EXP dimension order."}
    OUT.parent.mkdir(exist_ok=True,parents=True)
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("ANA_EXP data structures found:",len(structures))
    for st in structures:
        print("Structure:",st["id"],st["version"])
        for dim in st["dimensions"]:
            print("  Position",dim["position"],"ID",dim["id"])
    print("Saved metadata:",OUT)
    if not structures:
        raise ValueError("No referenced data structure found; metadata URL may need adjustment")
    print("No public data or composite scores changed.")

if __name__=="__main__":
    main()
