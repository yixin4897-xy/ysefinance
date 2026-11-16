#!/usr/bin/env python3
"""Generate a real, fully offline *synthetic-only* AESM demo for compliance review.

The HTML is a functional local prototype rendered from the bundled synthetic
discussion fixture. It makes zero network requests, stores no third-party data,
and must not be hosted as a live YouTube API client.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from sentiment import analyse, load_records

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "fixtures" / "synthetic_comments.jsonl"
THEME_LABELS = {
    "cost_of_living": "Cost of living",
    "housing": "Housing & mortgage",
    "employment": "Employment & income",
    "consumer_spending": "Consumer spending",
    "small_business": "Small business",
}
SYNTHETIC_WATERMARK = "SYNTHETIC DEMO — NO LIVE DATA / NOT APPROVED"


def render(aggregate: dict) -> str:
    if aggregate.get("provenance") != "SYNTHETIC_TEST_ONLY":
        raise ValueError("Only bundled synthetic aggregates can be rendered")
    if aggregate.get("research_status") != "CANDIDATE_ONLY_UNVALIDATED":
        raise ValueError("The experimental research label is required")
    weeks = aggregate["weeks"]
    if not weeks or len(weeks) > 8:
        raise ValueError("Expected 1–8 synthetic weeks")
    # Serialized JSON is embedded only after preventing an inline-script break-out.
    safe_data = json.dumps({"weeks": weeks, "themes": THEME_LABELS}, ensure_ascii=False).replace("<", "\\u003c")
    count = aggregate["accepted_relevant_rows"]
    duplicate = aggregate["deduplicated_rows"]
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>AESM Social Discussion — Synthetic Prototype | YSE Finance</title>
<style>
:root { color-scheme:light; --navy:#102c4a;--teal:#126a70;--cream:#f5f7fa;--ink:#19283a;--line:#dfe5ea;--gray:#536474; }
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:var(--cream);color:var(--ink)}
header{background:var(--navy);color:white;padding:24px max(22px,calc((100vw - 1120px)/2))}
header h1{margin:4px 0 8px;font-size:clamp(22px,2.6vw,32px)}header p{margin:0;color:#e2eaf1;line-height:1.5}
header .eyebrow{color:#b5dce6;font-size:12px;letter-spacing:1.2px;font-weight:700}
.banner{background:#fff3c8;padding:13px 20px;text-align:center;font-weight:800;border-bottom:2px solid #dfb95b;letter-spacing:.03em}
main{max-width:1120px;margin:auto;padding:24px 20px 42px}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.stat,.panel{background:white;border:1px solid var(--line);border-radius:12px;box-shadow:0 2px 14px rgba(16,44,74,.04)}
.stat{padding:18px}.stat b{font-size:25px;display:block;margin:6px 0}.stat span{color:var(--gray);font-size:13px}
section{margin-top:18px}.panel{padding:20px}h2{font-size:18px;margin:0 0 14px}p,li{line-height:1.5}
.controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:15px 0}
button{border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:8px;padding:9px 12px;cursor:pointer}
button[aria-pressed=true]{background:var(--teal);color:white;border-color:var(--teal)}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:11px;border-bottom:1px solid var(--line)}th{background:#f4f7f9}
.label{color:var(--gray);font-size:13px}.bars{display:grid;gap:14px}.bar-row{display:grid;grid-template-columns:130px 1fr 80px;align-items:center;gap:10px}
.track{height:14px;background:#e9eef2;border-radius:7px;overflow:hidden}.fill{height:100%;background:var(--teal);border-radius:7px}
.note{background:#eff7f7;border-left:4px solid var(--teal);padding:14px 16px;margin-top:18px}
footer{color:var(--gray);font-size:13px;margin-top:24px}
@media(max-width:680px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.bar-row{grid-template-columns:95px 1fr 60px;font-size:12px}table{font-size:12px}th,td{padding:8px 5px}}
</style>
</head>
<body>
<header><div class="eyebrow">YSE FINANCE · AESM INDEPENDENT RESEARCH</div>
<h1>Australian Economic Discussion — Research Prototype</h1>
<p>Functional offline view of fabricated discussion examples · Candidate research only · No real API collection</p></header>
<div class="banner">""" + html.escape(SYNTHETIC_WATERMARK) + """</div>
<main>
<div class="stats">
 <div class="stat"><span>Invented relevant rows</span><b>""" + str(count) + """</b><span>Not real comments</span></div>
 <div class="stat"><span>Duplicate removed</span><b>""" + str(duplicate) + """</b><span>Exact normalized match</span></div>
 <div class="stat"><span>Network / YouTube requests</span><b>0</b><span>No API credentials</span></div>
 <div class="stat"><span>Research status</span><b style="font-size:16px">UNVALIDATED</b><span>No population inference</span></div>
</div>
<section class="panel"><h2>Topic coverage · synthetic sample</h2>
<p class="label">Select a theme to display fabricated weekly counts; n &lt; 5 is suppressed. English/Chinese categories are not population samples.</p>
<div class="controls" id="themeControls" aria-label="Theme selection"></div>
<div id="bars" class="bars" aria-live="polite"></div>
</section>
<section class="panel"><h2>Weekly observations · fictional sample</h2><div style="overflow-x:auto">
<table><thead><tr><th>UTC week</th><th>Relevant</th><th>Negative</th><th>Positive</th><th>Unclassified topics excluded</th></tr></thead>
<tbody id="weeklyRows"></tbody></table></div>
<div class="note"><strong>What this demonstrates:</strong> Input validation, weekly aggregation, keyword topic classification, small-cell suppression and user interface controls. It does <strong>not</strong> validate economic conditions, commenter sentiment, source authorization or the accuracy of any AI model.</div>
</section>
<section class="panel"><h2>Governance and privacy status</h2>
<ul><li><strong>Source:</strong> 100% synthetic text created solely for software tests.</li>
<li><strong>Access:</strong> no YouTube API requests, account login, personal profiling or external processing.</li>
<li><strong>Retention:</strong> no real YouTube API data is held by this demo.</li>
<li><strong>Publication:</strong> PR #19 Draft only; no production website deployment.</li>
<li><strong>Next gate:</strong> a specific YouTube derived-metrics permission decision, reviewed privacy notice, platform rights and a separate owner approval for real data.</li></ul>
</section>
<footer>YSE Finance · AESM Social Sentiment Research · This is an internal synthetic demonstration and is not a public economic index.</footer>
</main>
<script>
"use strict";
const DATA = """ + safe_data + """;
const controls = document.getElementById("themeControls");
const bars = document.getElementById("bars");
const tbody = document.getElementById("weeklyRows");
function cell(v){return typeof v==="number"?String(v):"suppressed";}
for (const w of DATA.weeks){
  const tr=document.createElement("tr");
  [w.week_start_utc,cell(w.total_relevant),cell(w.sentiment.negative),cell(w.sentiment.positive),"Not shown"].forEach(v=>{
    const td=document.createElement("td");td.textContent=v;tr.appendChild(td);
  });tbody.appendChild(tr);
}
function showTheme(theme){
  controls.querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.theme===theme)));
  bars.replaceChildren();
  const vals=DATA.weeks.map(w=>({week:w.week_start_utc,value:w.topics[theme]}));
  const max=Math.max(1,...vals.map(v=>typeof v.value==="number"?v.value:0));
  for (const x of vals){
    const row=document.createElement("div");row.className="bar-row";
    const title=document.createElement("span");title.textContent=x.week;
    const track=document.createElement("div");track.className="track";
    const fill=document.createElement("div");fill.className="fill";
    fill.style.width=(typeof x.value==="number"?(x.value/max)*100:0)+"%";track.appendChild(fill);
    const number=document.createElement("strong");number.textContent=cell(x.value);
    row.append(title,track,number);bars.appendChild(row);
  }
}
Object.keys(DATA.themes).forEach((theme,index)=>{
  const button=document.createElement("button");button.type="button";
  button.dataset.theme=theme;button.textContent=DATA.themes[theme];
  button.setAttribute("aria-pressed","false");button.addEventListener("click",()=>showTheme(theme));
  controls.appendChild(button);
  if(index===0)showTheme(theme);
});
</script>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an entirely synthetic no-network research dashboard")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = analyse(load_records(INPUT), synthetic=True)
    page = render(result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print("Built FUNCTIONAL SYNTHETIC DEMO only: 0 API calls; no author data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
