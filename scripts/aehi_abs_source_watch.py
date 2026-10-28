#!/usr/bin/env python3
"""Check AEHI ABS source publication endpoints; publish NO economic numbers.

The JSON output is a source-review artifact for humans to inspect.
A changing HTML page does not mean a verified economic series changed.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def read_metadata(url):
    request=urllib.request.Request(url,headers={"User-Agent":"YSEFinance-AESM-research-source-review/4.1","Accept":"text/html"})
    with urllib.request.urlopen(request,timeout=30) as response:
        content=response.read(2_000_001)
        if len(content)>2_000_000: raise ValueError("Source page too large")
        final_url=response.geturl()
        content_type=response.headers.get("content-type","")
        if "html" not in content_type.lower():raise ValueError("Unexpected content type "+content_type)
    source=content.decode("utf-8",errors="replace")
    match=re.search(r"<title[^>]*>(.*?)</title>",source,re.I|re.S)
    title=html.unescape(re.sub(r"\s+"," ",match.group(1)).strip()) if match else ""
    if not title or len(title)>300:raise ValueError("Missing/invalid source title")
    return {"requested_url":url,"resolved_url":final_url,"page_title":title,
            "html_sha256":hashlib.sha256(content).hexdigest(),
            "warning":"HTML hash detects page changes, NOT official changes to underlying indicator series."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default=str(ROOT/"aehi-source-review.json"))
    args=p.parse_args()
    reg=json.loads((ROOT/"aehi-source-registry.json").read_text(encoding="utf-8"))
    if reg.get("release_status")!="HOLD" or reg.get("model")!="AEHI":
        raise ValueError("AEHI score status must remain HOLD")
    sources={}
    for item in reg["indicators"]:
        url=item["source_url"]
        if not url.startswith("https://www.abs.gov.au/"):
            raise ValueError("Untrusted source "+url)
        if url not in sources:sources[url]=read_metadata(url)
    out={
        "model":"AEHI","candidate_status":"SOURCE_METADATA_REVIEW_ONLY",
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "sources":list(sources.values()),"indicator_codes":[i["code"] for i in reg["indicators"]],
        "note":"No economic observation, indicator value or index score is approved or extracted."
    }
    Path(args.output).write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print(f"Checked {len(sources)} official ABS source pages. No indicator values extracted.")

if __name__=="__main__":
    main()
