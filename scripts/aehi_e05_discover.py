#!/usr/bin/env python3
"""Discover ABS dataflows potentially carrying real household consumption E05.

Read-only metadata discovery, no indicators or scores published. Uses the ABS
Data API dataflow directory, not the ANA_AGG aggregate dataflow which does
not contain HFCE.
"""
import json
import pathlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

URL="https://data.api.abs.gov.au/rest/dataflow?detail=allstubs"
DEST=pathlib.Path("data-candidates/aehi-e05-dataflow-discovery.json")
MAX_BYTES=8_000_000

def read():
    request=urllib.request.Request(URL,headers={
        "User-Agent":"YSEFinance-AESM/4.1-source-discovery",
        "Accept":"application/xml",
        "Accept-Encoding":"identity"})
    with urllib.request.urlopen(request,timeout=50) as response:
        target=urllib.parse.urlparse(response.geturl())
        if target.scheme!="https" or target.hostname!="data.api.abs.gov.au":
            raise ValueError("Unexpected API redirect")
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("Dataflow listing too large")
    return raw

def discover(raw):
    root=ET.fromstring(raw)
    out=[]
    for elem in root.iter():
        if not elem.tag.endswith("}Dataflow"):continue
        names=[((child.text or "").strip()) for child in elem
               if child.tag.endswith("}Name")]
        descriptions=[((child.text or "").strip()) for child in elem
                      if child.tag.endswith("}Description")]
        label=" ".join(names+descriptions)
        id_=elem.attrib.get("id","")
        if not id_:continue
        if any(term in (label+" "+id_).lower() for term in
           ("national accounts","consumption","expenditure","household","ana_")):
            out.append({"dataflow_id":id_,"version":elem.attrib.get("version"),
                        "agency":elem.attrib.get("agencyID"),
                        "title":names[:2],"description":descriptions[:2]})
    return sorted(out,key=lambda x:x["dataflow_id"])

def main():
    raw=read()
    results=discover(raw)
    report={"status":"DISCOVERY_ONLY_NOT_APPROVED","source_url":URL,
            "candidate_dataflows":results,
            "reference_release":"ABS National Accounts, June 2026, Tables 2 and 8",
            "note":"Review each candidate dataflow's SDMX structure and DATA_ITEM list. Do not treat a dataflow title as a verified HFCE series."}
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Matching ABS dataflows:",len(results))
    for item in results:
        print(item["dataflow_id"],item["version"]," / ".join(item["title"]))
    print("Saved:",DEST)
    print("No website indicator values or index scores changed.")

if __name__=="__main__":main()
