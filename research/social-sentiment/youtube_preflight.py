#!/usr/bin/env python3
"""Plan a YouTube commentThreads.list pilot without making any API/network calls.

No YouTube authentication, API key, comments, comment authors, or fetched data.
This is a permissions/selection/quota estimation tool ONLY.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

METHOD = "commentThreads.list"
UNITS_PER_PAGE = 1
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
ALLOWED_TOPICS = {"cost_of_living", "housing", "employment", "consumer_spending", "small_business"}
ALLOWED_LANGUAGES = {"en", "zh"}


def plan(manifest: dict) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("Expected JSON manifest object")
    if manifest.get("research_status") != "DESIGN_ONLY":
        raise ValueError("Manifest must explicitly be DESIGN_ONLY")
    if manifest.get("live_collection_authorized") is not False:
        raise ValueError("Preflight must explicitly keep live collection disabled")
    videos = manifest.get("candidate_videos")
    if not isinstance(videos, list) or not 1 <= len(videos) <= 10:
        raise ValueError("Require 1–10 candidate videos")
    pages = manifest.get("max_pages_per_video", 1)
    per_page = manifest.get("comments_per_page", 100)
    if type(pages) is not int or not 1 <= pages <= 3:
        raise ValueError("max_pages_per_video must be an integer from 1 to 3")
    if type(per_page) is not int or not 1 <= per_page <= 100:
        raise ValueError("comments_per_page must be an integer from 1 to 100")
    total_request_cap = manifest.get("max_total_requests", 20)
    if type(total_request_cap) is not int or not 1 <= total_request_cap <= 30:
        raise ValueError("max_total_requests must be an integer from 1 to 30")
    seen = set()
    sampled = []
    for video in videos:
        if not isinstance(video, dict) or set(video) != {"video_id", "topic", "language", "selection_reason", "australia_relevance"}:
            raise ValueError("Each candidate needs only video_id/topic/language/selection_reason/australia_relevance")
        video_id = video["video_id"]
        if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id) or video_id in seen:
            raise ValueError("Invalid or duplicate 11-character video ID")
        seen.add(video_id)
        if video["topic"] not in ALLOWED_TOPICS or video["language"] not in ALLOWED_LANGUAGES:
            raise ValueError("Unrecognised topic/language")
        for name in ("selection_reason", "australia_relevance"):
            if not isinstance(video[name], str) or not 10 <= len(video[name].strip()) <= 400:
                raise ValueError(name + " must be a meaningful concise explanation")
        sampled.append({
            "video_id": video_id,
            "topic": video["topic"],
            "language": video["language"],
            "selection_reason": video["selection_reason"].strip(),
            "australia_relevance": video["australia_relevance"].strip()
        })
    worst_case_calls = len(sampled) * pages
    if worst_case_calls > total_request_cap:
        raise ValueError("Planned request cap exceeded")
    return {
        "research_status": "DESIGN_ONLY_NO_COLLECTION",
        "authorisation": "NOT_REQUESTED_OR_VERIFIED",
        "real_comments_processed": 0,
        "api_calls_executed": 0,
        "quota_method": METHOD,
        "quota_units_per_request": UNITS_PER_PAGE,
        "maximum_expected_requests": worst_case_calls,
        "maximum_expected_quota_units": worst_case_calls * UNITS_PER_PAGE,
        "upper_bound_top_level_comments": worst_case_calls * per_page,
        "max_pages_per_video": pages,
        "comments_per_page": per_page,
        "candidate_video_count": len(sampled),
        "candidates": sampled,
        "sampling_bias_caution": "Manually curated videos are not representative of Australians or YouTube users",
        "response_scope": "Top-level comment threads; replies not counted as comprehensive coverage",
        "policy_gate": [
            "No credentials and no network logic are present in this program",
            "Confirm authorized business use, privacy disclosures, storage/retention and deletion processes",
            "Use only official YouTube Data API when separately approved",
            "Avoid account-level profiling or personally identifiable data retention",
            "Reassess source/video selection and quota before any live operation"
        ],
        "official_docs": [
            "https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list",
            "https://developers.google.com/youtube/data/determine_quota_cost",
            "https://developers.google.com/youtube/terms/developer-policies"
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline YouTube Data API sampling/quota preflight; NO LIVE CALLS")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    inp = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = plan(inp)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DRY RUN ONLY: {result['candidate_video_count']} candidate videos, "
          f"up to {result['maximum_expected_quota_units']} API quota units, ZERO calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
