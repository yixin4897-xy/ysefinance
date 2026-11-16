#!/usr/bin/env python3
"""Offline AESM social discussion research prototype. No API/network calls."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

STATUS = "CANDIDATE_ONLY_UNVALIDATED"
THEMES = {
    "cost_of_living": ("cost of living", "inflation", "groceries", "supermarket", "electricity bill", "food prices", "生活成本", "物价", "超市", "电费", "食品价格"),
    "housing": ("mortgage", "home loan", "housing", "rent", "landlord", "refinance", "repayments", "房贷", "租房", "房租", "住房", "还款"),
    "employment": ("job search", "jobs", "layoff", "unemployment", "salary", "wages", "pay rise", "hiring", "求职", "招聘", "失业", "工资", "裁员", "加薪", "工作"),
    "consumer_spending": ("holiday", "restaurant", "spending", "shopping", "saving", "discretionary", "cancelled our trip", "旅行", "消费", "购物", "储蓄", "外食", "推迟消费"),
    "small_business": ("small business", "cash flow", "suppliers", "customer traffic", "profit margin", "invoices", "生意", "小企业", "小生意", "现金流", "客流", "供应商", "利润"),
}
NEGATIVE = ("struggling", "struggle", "worry", "worried", "harder", "expensive", "unaffordable", "pressure", "stress", "rising costs", "lost my job", "layoffs", "困难", "担心", "压力", "吃紧", "负担不起", "涨价", "裁员", "下降")
POSITIVE = ("improved", "improving", "better", "affordable", "relief", "recovered", "easier", "lower prices", "sales up", "好转", "改善", "降低", "增加", "复苏", "更容易")
APPROVED_KEYS = {"platform", "timestamp", "text", "language", "source_type", "synthetic"}
PERSONAL_KEYS = {"author", "author_id", "username", "user_id", "email", "phone", "profile", "url", "comment_id", "channel_id", "handle", "location", "ip"}
MAX_ROWS = 10000
MIN_CELL = 5


def classify(text: str) -> tuple[str, str, str]:
    lowered = text.casefold()
    scores = {theme: sum(1 for term in terms if term in lowered) for theme, terms in THEMES.items()}
    highest = max(scores.values())
    winners = [theme for theme, count in scores.items() if count == highest] if highest else []
    theme = winners[0] if len(winners) == 1 else "unclassified"
    negative = any(term in lowered for term in NEGATIVE)
    # A word boundary prevents "affordable" from matching "unaffordable".
    positive = any((bool(re.search(r"\baffordable\b", lowered)) if term == "affordable" else term in lowered) for term in POSITIVE)
    sentiment = "mixed" if positive and negative else "negative" if negative else "positive" if positive else "neutral"
    personal = bool(re.search(r"\b(i|my|we|our)\b", lowered)) or "我" in lowered
    claim = any(term in lowered for term in ("abs data", "statistics", "according to", "rba", "数据显示", "统计局"))
    text_type = "personal_experience" if personal else "economic_claim" if claim else "opinion_or_other"
    return theme, sentiment, text_type


def load_records(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8-sig") as fh:
            records = [json.loads(line) for line in fh if line.strip()]
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            records = list(csv.DictReader(fh))
    else:
        raise ValueError("Only .jsonl and .csv input are supported")
    if len(records) > MAX_ROWS:
        raise ValueError("Input exceeds offline pilot limit of 10,000 rows")
    if not records:
        raise ValueError("Empty input")
    return records


def approval_check(path: Path | None, platforms: set[str]) -> None:
    if path is None:
        raise ValueError("Real data requires --approval: a reviewed permission attestation")
    obj = json.loads(path.read_text(encoding="utf-8"))
    required = {"governance_approved", "rights_confirmed", "data_minimised", "approval_reference", "approved_by", "allowed_platforms", "valid_until"}
    if not isinstance(obj, dict) or not required.issubset(obj):
        raise ValueError("Missing approval attestation fields")
    if any(obj.get(k) is not True for k in ("governance_approved", "rights_confirmed", "data_minimised")):
        raise ValueError("Approval/rights/data-minimisation gate is not satisfied")
    if not str(obj["approval_reference"]).strip() or not str(obj["approved_by"]).strip():
        raise ValueError("Approval reference and reviewer are required")
    if not isinstance(obj["allowed_platforms"], list) or not platforms.issubset(set(obj["allowed_platforms"])):
        raise ValueError("One or more input platforms are not approved")
    valid_until = date.fromisoformat(obj["valid_until"])
    if valid_until < datetime.now(timezone.utc).date():
        raise ValueError("Approval has expired")
    # This is a review gate, not proof that the platform actually granted rights.


def analyse(records: list[dict], synthetic: bool, approval: Path | None = None) -> dict:
    parsed = []
    platforms = set()
    seen = set()
    duplicate_count = 0
    irrelevant_count = 0
    invalid_count = 0
    for row in records:
        if not isinstance(row, dict) or not set(row).issubset(APPROVED_KEYS):
            raise ValueError("Input has unknown or personal-identifier fields; preprocess locally before research")
        if PERSONAL_KEYS.intersection(row):
            raise ValueError("Personal identifiers are not permitted")
        if synthetic and str(row.get("synthetic", "")).lower() not in ("true", "1"):
            raise ValueError("Synthetic mode requires each record to be marked synthetic")
        if not synthetic and str(row.get("synthetic", "")).lower() in ("true", "1"):
            raise ValueError("Do not mix synthetic observations into a real dataset")
        text = row.get("text")
        platform = row.get("platform")
        language = row.get("language")
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            invalid_count += 1
            continue
        if not isinstance(platform, str) or not platform.strip() or language not in ("en", "zh"):
            invalid_count += 1
            continue
        try:
            dt = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError("Timestamp must have a timezone")
            dt = dt.astimezone(timezone.utc)
            if dt > datetime.now(timezone.utc) + timedelta(hours=1):
                raise ValueError("Future timestamp")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Timestamp must be an ISO 8601 UTC/offset date-time") from exc
        platforms.add(platform)
        week = (dt.date() - timedelta(days=dt.weekday())).isoformat()
        normalized = re.sub(r"\s+", " ", text.casefold()).strip()
        key = (platform, language, week, normalized)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        theme, sentiment, kind = classify(text)
        if theme == "unclassified":
            irrelevant_count += 1
            continue
        parsed.append((week, platform, language, theme, sentiment, kind))
    if not synthetic:
        approval_check(approval, platforms)
    weeks = Counter(row[0] for row in parsed)
    topic_by_week = Counter((row[0], row[3]) for row in parsed)
    sentiment_by_week = Counter((row[0], row[4]) for row in parsed)
    platform_by_week = Counter((row[0], row[1]) for row in parsed)
    languages = Counter(row[2] for row in parsed)
    language_topic_by_week = Counter((row[0], row[2], row[3]) for row in parsed)
    def guarded(n: int) -> int | str:
        return n if n >= MIN_CELL else "suppressed"
    result = {
        "research_status": STATUS,
        "provenance": "SYNTHETIC_TEST_ONLY" if synthetic else "MANUAL_APPROVED_INPUT_UNVALIDATED",
        "not_population_representative": True,
        "no_composite_score": True,
        "method": "transparent_keyword_baseline_not_validated_for_inference",
        "input_rows": len(records),
        "accepted_relevant_rows": len(parsed),
        "deduplicated_rows": duplicate_count,
        "unclassified_rows": irrelevant_count,
        "invalid_rows": invalid_count,
        "source_platforms": sorted(platforms),
        "languages": dict(sorted(languages.items())),
        "minimum_disclosure_cell": MIN_CELL,
        "weeks": [
            {
                "week_start_utc": w,
                "total_relevant": guarded(weeks[w]),
                "topics": {t: guarded(topic_by_week[(w, t)]) for t in THEMES},
                "sentiment": {s: guarded(sentiment_by_week[(w, s)]) for s in ("positive", "negative", "neutral", "mixed")},
                "platform": {p: guarded(platform_by_week[(w, p)]) for p in sorted(platforms)},
                "topics_by_language": {
                    lang: {t: guarded(language_topic_by_week[(w, lang, t)]) for t in THEMES}
                    for lang in ("en", "zh")
                }
            }
            for w in sorted(weeks)
        ],
        "limitations": [
            "Not a representative sample of Australians",
            "Keyword classifications require human validation; sarcasm and context can be misread",
            "No causality, official economic forecast, public sentiment index, or individual profiling",
            "Week assignment uses timestamp converted to UTC",
            "Small topic/platform/sentiment cells are suppressed",
            "Do not compare platform rates before sampling and language coverage review"
        ]
    }
    return result


def markdown_report(result: dict) -> str:
    lines = [
        "# AESM social discussion pilot — NOT VALIDATED",
        "",
        f"**Source mode:** {result['provenance']}",
        f"**Research status:** {result['research_status']}",
        "",
        "This report does not represent Australian population sentiment. It contains no official index, forecast, or personal-level data.",
        "",
        f"Input rows: {result['input_rows']}; retained relevant rows: {result['accepted_relevant_rows']}; "
        f"duplicates: {result['deduplicated_rows']}; unclassified: {result['unclassified_rows']}; "
        f"invalid: {result['invalid_rows']}.",
        "",
        "| UTC week beginning | Relevant rows | Negative discussions | Positive discussions |",
        "|---|---:|---:|---:|",
    ]
    for w in result["weeks"]:
        lines.append(f"| {w['week_start_utc']} | {w['total_relevant']} | {w['sentiment']['negative']} | {w['sentiment']['positive']} |")
    lines += [
        "",
        "## Interpretation",
        "The figures are a reproducible test of ingestion, weekly aggregation and cell suppression only. "
        "No conclusion about Australian economic conditions can be drawn from this sample.",
        "",
        "## Next steps",
        "Secure platform-specific rights, document sampling, manually validate classification accuracy, "
        "compare English and Chinese discussion separately, and only then consider a four-week pilot.",
        "",
        "## Disclosure rules",
        "Cells with fewer than five observations are suppressed. Raw discussion text, user identifiers, "
        "and inferred sensitive traits are never written to the result.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="AESM offline social-discussion pilot; no platform collection")
    parser.add_argument("--input", type=Path, required=True, help="Permitted, minimised CSV or JSONL file")
    parser.add_argument("--synthetic-fixture", action="store_true", help="Only for bundled synthetic fixtures")
    parser.add_argument("--approval", type=Path, help="Required for manually supplied real discussion data")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()
    if args.synthetic_fixture:
        fixture_dir = (Path(__file__).resolve().parent / "fixtures").resolve()
        if args.input.resolve().parent != fixture_dir:
            parser.error("--synthetic-fixture is restricted to bundled fixture files")
        if args.approval:
            parser.error("Synthetic fixtures cannot be mixed with real-data approval")
    records = load_records(args.input)
    result = analyse(records, synthetic=args.synthetic_fixture, approval=args.approval)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_out.write_text(markdown_report(result), encoding="utf-8")
    print(f"OFFLINE pilot complete: {result['provenance']}; retained {result['accepted_relevant_rows']} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
