#!/usr/bin/env python3
"""Rebuild ASFI S03/S04 candidate data from APRA's original QPEX XLSX.

Uses only the Python standard library (ZIP/XML). The output is always labelled
DATA_IMPORT_REVIEW_REQUIRED. Never changes ASFI composite HOLD status.
Example:
  python scripts/import_asfi_apra.py "Quarterly authorised deposit-taking institution property exposures statistics June 2026.xlsx"
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
EXPECTED_RELEASE = "2026-09-17"
EXPECTED_SHEETS = {5: "Tab 1b", 6: "Tab 1c"}
OUT = "asfi-apra-indicators.json"


def shared_strings(zip_file):
    root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in row.iter(NS+"t")) for row in root]


def worksheet(zip_file, index, strings):
    root = ET.fromstring(zip_file.read("xl/worksheets/sheet%d.xml" % index))
    results = {}
    for r in root.findall(NS+"sheetData/"+NS+"row"):
        line = {}
        for c in r.findall(NS+"c"):
            v = c.find(NS+"v")
            if v is None or v.text is None:
                continue
            raw = v.text
            if c.get("t") == "s":
                raw = strings[int(raw)]
            col = re.match(r"^[A-Z]+", c.get("r")).group(0)
            line[col] = raw
        results[int(r.get("r"))] = line
    return results


def get_num(sheet, row, col):
    try:
        value = float(sheet[row][col])
    except (KeyError, ValueError):
        raise ValueError("Missing/suppressed or non-numeric cell %s%d" % (col,row))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Invalid amount in %s%d" % (col,row))
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook", type=pathlib.Path)
    ap.add_argument("--output", type=pathlib.Path, default=pathlib.Path(OUT))
    args = ap.parse_args()
    data = args.workbook.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(args.workbook) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = list(wb.find(NS+"sheets"))
        for index, name in EXPECTED_SHEETS.items():
            if sheets[index-1].get("name") != name:
                raise ValueError("Unexpected workbook worksheet order for %s" % name)
        texts = shared_strings(z)
        stock = worksheet(z,5,texts)
        flow = worksheet(z,6,texts)
        if "Non-performing loans" not in stock[69].get("A","") or "Total credit oustanding" not in stock[16].get("A",""):
            raise ValueError("Changed Tab 1b row labels")
        if "Debt-to-income" not in flow[35].get("A","") or "Owner-occupied" not in flow[9].get("A","") or "Investment" not in flow[10].get("A",""):
            raise ValueError("Changed Tab 1c row labels")
        columns = [col for col in flow[4] if col not in ("A","B")]
        out03=[];out04=[]
        for col in columns:
            serial = get_num(flow,4,col)
            if serial != get_num(stock,4,col):
                raise ValueError("Quarter date mismatch")
            day = (dt.datetime(1899,12,30)+dt.timedelta(days=serial)).date()
            if day.month not in (3,6,9,12) or day.day not in (30,31):
                raise ValueError("Unexpected quarter-end date")
            period=f"{day.year} Q{day.month//3}"
            # S03 numerator: row 35 high DTI 6x+ total housing loan funding.
            # Denominator: owner-occupied + investment new term loans, not
            # row 7 overall loans (which includes other types).
            s03=get_num(flow,35,col)/(get_num(flow,9,col)+get_num(flow,10,col))*100
            # S04: non-performing loans / total residential credit outstanding.
            s04=get_num(stock,69,col)/get_num(stock,16,col)*100
            for result,value in [(out03,s03),(out04,s04)]:
                if not 0<=value<=100:
                    raise ValueError("Ratio out of bounds for "+period)
                result.append({"period":period,"value":round(value,4)})
    if len(out03)<12 or out03[-1]["period"]!="2026 Q2":
        raise ValueError("Unexpected APRA quarter coverage")
    if not(5.55<out03[-1]["value"]<5.57 and 1.00<out04[-1]["value"]<1.02):
        raise ValueError("Latest amounts fail APRA published highlight cross-check")
    result={
      "schema_version":"1.0","model":"ASFI",
      "data_status":"DATA_IMPORT_REVIEW_REQUIRED",
      "composite_release_status":"HOLD",
      "source_workbook_sha256":digest,
      "publication_date":EXPECTED_RELEASE,
      "data_vintage":"Current APRA June 2026 QPEX workbook, may contain revised historical quarters.",
      "scope":"All ADIs excluding other ADIs, Level 2",
      "series":[
        {"code":"S03","name":"New owner-occupied and investor housing loans at DTI ≥6","unit":"%",
         "source":{"publisher":"APRA","table":"Tab 1c","numerator":"Debt-to-income ≥6x (row 35)","denominator":"Owner-occupied + investment new term loans funded (rows 9 + 10)","release_date":EXPECTED_RELEASE},"observations":out03},
        {"code":"S04","name":"Non-performing residential property loans as share of credit outstanding","unit":"%",
         "source":{"publisher":"APRA","table":"Tab 1b","numerator":"Non-performing loans (row 69)","denominator":"Total credit outstanding (row 16)","release_date":EXPECTED_RELEASE},"observations":out04}
      ]
    }
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Saved",args.output,"status",result["data_status"],"sha256",digest)
    print("S03",len(out03),out03[-1],"S04",len(out04),out04[-1])


if __name__=="__main__":
    main()
