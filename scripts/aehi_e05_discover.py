#!/usr/bin/env python3
"""Inspect ANA_EXP SDMX codelists to identify E05 HFCE series components.

Read only; no observation data imported and no AEHI scoring modified.
Uses a verified ABS metadata URL. Never guesses that ANA_AGG's M1/20
codes necessarily exist in the ANA_EXP flow.
"""
import json
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

URL="https://data.api.abs.gov.au/rest/dataflow/ABS/ANA_EXP/1.0.0?references=all"
OUT=Path("data-candidates/aehi-e05-codelist-discovery.json")
MAX=12_000_000
INTEREST=("household","consumption","final consumption","chain volume","seasonally adjusted","all sectors","total economy")
def ln(t):return t.rsplit("}",1)[-1]
def child_text(node,tag):
    for e in node:
        if ln(e.tag)==tag:return " ".join("".join(e.itertext()).split())
    return ""
def main():
    req=urllib.request.Request(URL,headers={"User-Agent":"YSEFinance-AESM/4.1-source-metadata","Accept":"application/xml","Accept-Encoding":"identity"})
    with urllib.request.urlopen(req,timeout=60) as response:
        p=urllib.parse.urlparse(response.geturl())
        if p.scheme!="https" or p.hostname!="data.api.abs.gov.au":raise ValueError("Unexpected origin")
        raw=response.read(MAX+1)
    if len(raw)>MAX:raise ValueError("Metadata response too large")
    root=ET.fromstring(raw)
    lists=[]
    for cl in root.iter():
        if ln(cl.tag)!="Codelist":continue
        codes=[]
        for code in cl:
            if ln(code.tag)!="Code":continue
            desc=child_text(code,"Name")
            codes.append({"id":code.attrib.get("id",""),"name":desc})
        if codes:
            candidates=[x for x in codes if any(k in (x["name"]+" "+x["id"]).lower() for k in INTEREST)]
            lists.append({"id":cl.attrib.get("id"),"version":cl.attrib.get("version"),"total_codes":len(codes),
                          "matching_codes":candidates[:100],"sample_codes":codes[:8]})
    if not lists:raise ValueError("No embedded codelists found; inspect DSD structure references")
    output={"status":"DISCOVERY_ONLY_NOT_APPROVED","source_url":URL,"codelists":lists,
            "note":"Verify which codelist attaches to DATA_ITEM, MEASURE, SECTOR, TSEST before constructing an exact E05 source key; names alone do not approve data."}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("ANA_EXP embedded codelists:",len(lists))
    for c in lists:
        print("CODELIST",c["id"],"total",c["total_codes"])
        for x in c["matching_codes"][:25]:print("   ",x["id"],":",x["name"])
    print("Full review JSON:",OUT)
    print("No AEHI data or scores changed.")
if __name__=="__main__":main()
