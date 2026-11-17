#!/usr/bin/env python3
"""Synthetic YouTube commentThreads adapter proof of concept; NO API/network access.

Accepts ONLY the bundled made-up response fixture. The fixture adds marker fields
NOT present in real YouTube responses, so the tool cannot be mistaken for a
permitted real-data importer. Raw comment content stays transient in memory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentiment import analyse

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
ALLOW_LANGUAGES = {"en", "zh"}
MAX_SYNTHETIC_THREADS = 100


def convert_synthetic_response(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Expected a synthetic JSON object")
    if payload.get("mock_only") is not True or payload.get("research_status") != "SYNTHETIC_TEST_ONLY":
        raise ValueError("Real YouTube responses are not permitted: synthetic marker required")
    if payload.get("kind") != "youtube#commentThreadListResponse":
        raise ValueError("Not a commentThreads mock response")
    if set(payload) != {"mock_only", "research_status", "kind", "items"}:
        raise ValueError("Unknown top-level fields")
    items = payload.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_SYNTHETIC_THREADS:
        raise ValueError("Require 1–100 synthetic threads")
    records = []
    for item in items:
        if not isinstance(item, dict) or item.get("fictional") is not True:
            raise ValueError("Every mock item must be marked fictional")
        if item.get("kind") != "youtube#commentThread":
            raise ValueError("Unexpected comment thread kind")
        snip = item.get("snippet")
        if not isinstance(snip, dict):
            raise ValueError("Missing thread snippet")
        comment = snip.get("topLevelComment")
        if not isinstance(comment, dict) or not isinstance(comment.get("snippet"), dict):
            raise ValueError("Missing top-level comment snippet")
        item_snip = comment["snippet"]
        # Deliberately select only a minimal subset of mocked fields.
        # Ignore id, authorDisplayName, authorChannelId, authorProfileImageUrl,
        # likeCount and the parent video's metadata.
        body = item_snip.get("textOriginal")
        stamp = item_snip.get("publishedAt")
        lang = item.get("reviewedLanguage")
        if lang not in ALLOW_LANGUAGES or not isinstance(body, str) or not isinstance(stamp, str):
            raise ValueError("Invalid text, timestamp, or reviewer-provided language")
        records.append({
            "platform": "youtube",
            "timestamp": stamp,
            "text": body,
            "language": lang,
            "synthetic": True,
        })
    aggregates = analyse(records, synthetic=True)
    return {
        "source": "FICTIONAL_YOUTUBE_SHAPED_PAYLOAD",
        "research_status": "SYNTHETIC_TEST_ONLY_NO_API",
        "api_calls_executed": 0,
        "identity_fields_stored": 0,
        "raw_comments_exported": 0,
        "aggregate": aggregates,
        "note": "Mock payloads do not establish permitted YouTube API use or real-world classifier performance",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic-only YouTube-shaped mock adapter, with no network")
    parser.add_argument("--mock", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.mock.resolve().parent != FIXTURE_DIR.resolve():
        parser.error("Only bundled synthetic fixtures may be used")
    payload = json.loads(args.mock.read_text(encoding="utf-8"))
    output = convert_synthetic_response(payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SIMULATED API SHAPE ONLY: {output['aggregate']['accepted_relevant_rows']} "
          "relevant fictional rows; ZERO API calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
