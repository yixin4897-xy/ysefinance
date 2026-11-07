#!/usr/bin/env python3
"""Stage checked RBA source candidates; NEVER modify the live website data.
GitHub Actions calls this after scripts/import_asfi_rba.py --download.
It stages only if the latest observation series or source file digests changed
versus published data. It must never change ASFI scoring, approvals or risk labels.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
DEST = BASE / "data-candidates" / "rba-source-review.json"
CURRENT = BASE / "asfi-indicators.json"

def require_series(document):
    if document.get("model") != "ASFI" or document.get("composite_release_status") != "HOLD":
        raise ValueError("Unexpected model/status")
    data = {}
    for key, table, series_id in (("S01","E2","BHFDDIT"),("S02","E13","LPHTICRI")):
        matches = [x for x in document.get("series",[]) if x.get("code")==key]
        if len(matches) != 1:
            raise ValueError("Missing or duplicated "+key)
        item=matches[0]
        source=item.get("source",{})
        if source.get("table")!=table or source.get("series_id")!=series_id:
            raise ValueError("Unexpected series source "+key)
        observations=item.get("observations",[])
        if len(observations)<12:
            raise ValueError("Insufficient quarterly history "+key)
        if any(not isinstance(o.get("period"),str) or not isinstance(o.get("value"),(int,float)) for o in observations):
            raise ValueError("Malformed observation "+key)
        data[key]={"source_hash":source.get("csv_sha256"),"observations":observations}
    return data

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: aesm_stage_rba_candidate.py candidate.json")
    candidate=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    candidate_series=require_series(candidate)
    current=json.loads(CURRENT.read_text(encoding="utf-8"))
    published=require_series(current)
    changed=candidate_series!=published
    if changed:
        # Make reproducible content. Never write into asfi-indicators.json.
        candidate["data_status"]="DATA_IMPORT_REVIEW_REQUIRED"
        candidate["composite_release_status"]="HOLD"
        candidate["source_retrieved_utc"]=None
        candidate["source_review_note"]="AUTOMATED DRAFT ONLY: awaiting publication-date verification, source-revision checks and editorial approval. Do not merge candidate into live data without reviewing."
        DEST.parent.mkdir(exist_ok=True)
        DEST.write_text(json.dumps(candidate,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    out=os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out,"a",encoding="utf-8") as f:
            f.write("changed="+("true" if changed else "false")+"\n")
    print("RBA candidate "+("changed: manual review required" if changed else "unchanged: no PR needed"))
    print("Live ASFI scores and indicators untouched.")

if __name__ == "__main__":
    main()
