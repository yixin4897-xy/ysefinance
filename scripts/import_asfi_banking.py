#!/usr/bin/env python3
"""Import S05 CET1 and S06 NSFR from APRA quarterly performance XLSX.
Standard library only. Rebuilds a REVIEW_REQUIRED candidate, never publishes it.
Usage: python scripts/import_asfi_banking.py "Quarterly ... performance.xlsx"
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NAME_TO_SHEET = {"Tab 1c": 7, "Tab 1e": 9}
CODES = {
    "S05": ("Tab 1c", 64, "Common Equity Tier 1 capital ratio", "2013 Q1"),
    "S06": ("Tab 1e", 83, "NSFR ratio a", "2018 Q1"),
}


def cells(root, number, strings):
    row = root.find(f"{NS}sheetData/{NS}row[@r='{number}']")
    if row is None:
        raise ValueError(f"Missing sheet row {number}")
    result = {}
    for cell in row.findall(NS + "c"):
        raw = cell.find(NS + "v")
        if raw is None or raw.text is None:
            continue
        col = re.match(r"^[A-Z]+", cell.get("r")).group(0)
        value = strings[int(raw.text)] if cell.get("t") == "s" else raw.text
        result[col] = value
    return result


def parse(z, index, strings, row_number, expected_label, first):
    root = ET.fromstring(z.read(f"xl/worksheets/sheet{index}.xml"))
    labels = cells(root, row_number, strings)
    title = labels.get("A", "").strip()
    if title != expected_label:
        raise ValueError(f"Expected {expected_label!r} in A{row_number}, got {title!r}")
    dates = cells(root, 4, strings)
    observations = []
    for col, label in dates.items():
        if col == "A" or col not in labels:
            continue
        if labels[col] in ("*", "-", "", "n.a."):
            continue
        try:
            date = dt.datetime.strptime(label, "%b %Y")
            ratio = float(labels[col])
        except ValueError as exc:
            raise ValueError(f"Unrecognised quarter/value at {col}: {label!r}") from exc
        if date.month not in (3, 6, 9, 12) or not math.isfinite(ratio) or ratio <= 0 or ratio > 2:
            raise ValueError(f"Invalid quarter/value {col}: {label}, {ratio}")
        period = f"{date.year} Q{date.month//3}"
        observations.append({"period": period, "value": round(ratio*100, 4)})
    if not observations or observations[0]["period"] != first or observations[-1]["period"] != "2026 Q2":
        raise ValueError("Unexpected observation coverage")
    if any(a["period"] >= b["period"] for a,b in zip(observations, observations[1:])):
        raise ValueError("Duplicate or out-of-order quarter")
    return observations


def main():
    p = argparse.ArgumentParser()
    p.add_argument("workbook", type=pathlib.Path)
    p.add_argument("--output", type=pathlib.Path, default=pathlib.Path("asfi-banking-indicators.json"))
    args = p.parse_args()
    raw = args.workbook.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(args.workbook) as z:
        names = ET.fromstring(z.read("xl/workbook.xml")).find(NS+"sheets")
        for name,index in NAME_TO_SHEET.items():
            if names[index-1].get("name") != name:
                raise ValueError(f"Workbook sheets changed; expected {name} at position {index}")
        sr = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in r.iter(NS+"t")) for r in sr]
        data = {}
        for code,(name,row,label,first) in CODES.items():
            data[code] = parse(z, NAME_TO_SHEET[name], strings, row, label, first)
    if abs(data["S05"][-1]["value"]-12.5)>.05 or abs(data["S06"][-1]["value"]-114.5)>.05:
        raise ValueError("Latest values do not match published June 2026 APRA ratios")
    result={
        "schema_version":"1.0","model":"ASFI",
        "data_status":"DATA_IMPORT_REVIEW_REQUIRED",
        "composite_release_status":"HOLD",
        "source_workbook_sha256":digest,
        "publication_date":"2026-09-17",
        "data_vintage":"APRA June 2026 original workbook; revised historical vintage",
        "series":[
            {"code":code,"name":CODES[code][2],"unit":"%",
             "source":{"publisher":"APRA","table":CODES[code][0],"row":CODES[code][1],
                       "release_date":"2026-09-17"},
             "observations":data[code]}
            for code in ("S05","S06")
        ],
    }
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Candidate saved:",args.output,"hash:",digest,"REVIEW REQUIRED")
    for code in ("S05","S06"):
        print(code,len(data[code]),"latest",data[code][-1])


if __name__=="__main__":
    main()
