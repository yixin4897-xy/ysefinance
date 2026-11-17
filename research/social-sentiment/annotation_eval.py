#!/usr/bin/env python3
"""Offline classifier error analysis on SYNTHETIC labelled examples only.

This is an engineering diagnostic, NOT empirical evidence of accuracy on social media.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from sentiment import THEMES, classify

SENTIMENTS = ("positive", "negative", "neutral", "mixed")
MIN_ROWS = 12


def evaluate(examples: list[dict]) -> dict:
    if not isinstance(examples, list) or len(examples) < MIN_ROWS:
        raise ValueError(f"Require at least {MIN_ROWS} synthetic labelled examples")
    theme_correct = 0
    sentiment_correct = 0
    joint_correct = 0
    languages = Counter()
    theme_confusion = Counter()
    sentiment_confusion = Counter()
    per_language = Counter()
    for row in examples:
        if not isinstance(row, dict) or set(row) != {"text", "language", "expected_theme", "expected_sentiment", "synthetic"}:
            raise ValueError("Reject unspecified fields; no personal identifiers in evaluation samples")
        if row["synthetic"] is not True:
            raise ValueError("Only marked synthetic annotations are permitted in this offline diagnostic")
        if row["expected_theme"] not in set(THEMES) | {"unclassified"}:
            raise ValueError("Unknown expected theme")
        if row["expected_sentiment"] not in SENTIMENTS:
            raise ValueError("Unknown expected sentiment")
        if row["language"] not in ("en", "zh"):
            raise ValueError("Unknown language")
        if not isinstance(row["text"], str) or not 1 <= len(row["text"]) <= 2000:
            raise ValueError("Invalid synthetic text length")
        theme, sentiment, _ = classify(row["text"])
        lang = row["language"]
        languages[lang] += 1
        theme_confusion[(row["expected_theme"], theme)] += 1
        sentiment_confusion[(row["expected_sentiment"], sentiment)] += 1
        theme_correct += int(theme == row["expected_theme"])
        sentiment_correct += int(sentiment == row["expected_sentiment"])
        correct_both = theme == row["expected_theme"] and sentiment == row["expected_sentiment"]
        joint_correct += int(correct_both)
        per_language[(lang, "total")] += 1
        per_language[(lang, "joint")] += int(correct_both)

    n = len(examples)
    return {
        "provenance": "SYNTHETIC_ANNOTATIONS_ONLY",
        "research_status": "DIAGNOSTIC_NOT_VALIDATED",
        "n": n,
        "languages": dict(sorted(languages.items())),
        "theme_exact_matches": theme_correct,
        "sentiment_exact_matches": sentiment_correct,
        "joint_exact_matches": joint_correct,
        "theme_accuracy_on_fabricated_examples": round(theme_correct / n, 4),
        "sentiment_accuracy_on_fabricated_examples": round(sentiment_correct / n, 4),
        "joint_accuracy_on_fabricated_examples": round(joint_correct / n, 4),
        "joint_by_language": {
            lang: {"count": languages[lang], "matches": per_language[(lang, "joint")]}
            for lang in sorted(languages)
        },
        "theme_confusion": [
            {"expected": expected, "predicted": predicted, "count": count}
            for (expected, predicted), count in sorted(theme_confusion.items())
        ],
        "sentiment_confusion": [
            {"expected": expected, "predicted": predicted, "count": count}
            for (expected, predicted), count in sorted(sentiment_confusion.items())
        ],
        "limitations": [
            "These examples are fictional and do not measure real-world classification quality",
            "The expected labels were crafted as tests, not independently annotated by researchers",
            "Negation, sarcasm, dialect, platform context and overlapping topics remain error sources",
            "Do not use these diagnostics as a validated AU economic sentiment statistic"
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic-only sentiment error analysis")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    fixtures = (Path(__file__).resolve().parent / "fixtures").resolve()
    if args.annotations.resolve().parent != fixtures:
        parser.error("Only bundled synthetic fixtures may be used")
    data = json.loads(args.annotations.read_text(encoding="utf-8"))
    result = evaluate(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SYNTHETIC diagnostics: n={result['n']}, theme_matches={result['theme_exact_matches']}, "
          f"sentiment_matches={result['sentiment_exact_matches']}; not population validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
