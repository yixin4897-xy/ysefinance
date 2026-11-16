# AESM — Phase 2 preparation: YouTube API sampling and classifier validation

**As at 16 November 2026. Status: DESIGN_ONLY_NO_COLLECTION.**
**This document does not authorize collecting, storing, or analysing actual platform comments.**

## What has been built (offline)

1. `youtube_preflight.py` checks a **local editor-curated candidate-video manifest**, requires an explicit `live_collection_authorized: false` flag, and estimates an upper bound for paginated `commentThreads.list` quota. It contains **no** network or authentication code. It cannot retrieve comments.
2. `annotation_eval.py` compares existing baseline keyword labels with a **fabricated, synthetic** bilingual annotated fixture. It reports confusion counts and language splits without exporting text. These metrics are **not empirical precision/recall** and provide no evidence of real-world accuracy.
3. CI runs the existing synthetic-analysis program, the preflight tool, diagnostics, and unit tests. No real provider endpoint, secrets or API credentials are used.

## YouTube Data API details to verify before a live pilot

- Official endpoint: `GET https://www.googleapis.com/youtube/v3/commentThreads`
- `part=snippet` and one explicit `videoId` are the proposed minimal fields for fetching top-level comment threads. Use `textFormat=plainText`, `order=time`, bounded `maxResults` (1–100), and `pageToken` only within the approved quota budget.
- `commentThreads.list` is currently documented as **1 quota unit per page request**; additional pages cost additional units. The *plan* assumes every selected video uses the maximum permitted pages, so estimated units are an upper bound. The true returned count may be smaller, and comments can be disabled or unavailable.
- `commentThreads` does **not** provide exhaustive replies. A research design must state whether it studies top-level discussion only, and cannot describe it as all YouTube comments.
- A video ID and video title may be published publicly; this preflight stores **only a source-selection manifest**, not comments or author identifiers.
- Whether the proposed research and any aggregate retention are allowed by current YouTube API Services terms and Australian privacy law must be assessed by a reviewer **before credentials or network access**. Public accessibility is not a blanket license to build commercial sentiment datasets.
- **Critical additional gate — derived-metrics amendment:** YouTube's June 2026 [additional derived-metrics policy](https://developers.google.com/youtube/terms/derived-metrics-policy) describes certain viewer sentiment analysis as acceptable **only after acceptance of the applicable Developer Policies amendment**. The broader economic-sentiment study planned here is not automatically approved by that example; verify the precise use case and obtain any applicable acceptance, compliance review or permission **before** conducting analytics or publishing comment-derived metrics. Do not treat a public-data API key as such approval.

Official documentation:
- https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list
- https://developers.google.com/youtube/data/determine_quota_cost
- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/terms/developer-policies-guide

## Data-minimisation and retention design

If future authorised acquisition is approved, the ingestion module must:

- Refuse to run without owner sign-off and platform-specific access rights verified against a written scope and effective date.
- Not keep channel/user IDs, usernames, profile URLs, exact geolocation, user-linked histories or unnecessary personal data. Do not attempt cross-platform matching or classification of users' private financial/sensitive attributes.
- Prevent committing any raw API payload or redacted comments to GitHub or the public site. Review whether even transformed aggregates count as YouTube API Data and are subject to deletion/refresh obligations; do not assume they can be stored indefinitely.
- Observe developer-policy storage windows: limited non-authorised API data is generally not stored for more than **30 calendar days**; specific consent and user deletion/revocation duties may require deletion sooner (including **7 calendar days** in some cases). Implement item-level invalidation and a documented deletion-request pathway before live acquisition.
- The same [additional derived-metrics policy](https://developers.google.com/youtube/terms/derived-metrics-policy) describes up to 36-month retention for **accepted** derived-metric use cases; this is *not* an entitlement for YSE Finance without the required amendment/acceptance. Keep the default conservative 30-day raw API-data control until permissions are confirmed.
- Respect YouTube user privacy policy, API terms, rate limits, attribution, and usage rules; avoid anti-bot workarounds, unapproved AI model training and all direct user profiling.
- Never send full third-party user comments to an external LLM service without a separate privacy/data-rights assessment and appropriate authorization. Phase 2 classifier remains local rule-based only.

## Video-selection plan (no videos have been selected)

An eventual owner-approved pilot could choose a **small, stratified set of Australian-relevant economic news explainer videos** spanning:
- five themes: living costs, housing, employment, consumer spending and small business;
- English and Chinese discussions as **separate corpora** with independent denominator checks;
- more than one publisher or editorial viewpoint to limit single-channel framing effects;
- dates and fixed sampling windows logged before observation; comment age and moderation restrictions noted.

Record selection criteria, why content is Australian-relevant, video publication period, quota budget, excluded channels, and reporting boundaries **before** obtaining comments. Neither publisher location nor comment language proves a commenter resides in Australia.

The bundled `youtube_preflight_synthetic.json` uses fake video IDs and invented selection reasons. A hypothetical 2 videos × 2 pages/video × 50 threads/page costs at most **4 quota units** and yields at most **200 top-level threads**. This is a **planning calculation**, not a forecast of response counts, API allowance or real costs.

## Classifier audit and decision threshold

The small `annotations_synthetic.json` fixture intentionally includes negation and sarcasm, as well as Chinese phrases. Apparent accuracy is measured only against these **fabricated labels**. Real approved-data pilot quality needs:

- double-blind, human-reviewed stratified examples, with inter-reviewer agreement;
- per-theme and per-language precision/recall/confusion matrices and missed-topic rates;
- performance checks for negation, irony, quoted economic news, code-switching, duplicate and spam content;
- a predefined stopping rule if coverage or classification quality is inadequate;
- no public sentiment share/index unless separately validated, approved and permitted by terms.

## Approval checkpoints (all outstanding)

1. **Owner** approves platform, budget and purpose of an eventual limited pilot.
2. **Compliance/privacy reviewer** confirms provider rights, allowed commercial research purposes, disclosures, minimisation, retention and deletion.
3. **Implementation review** of a separately proposed official-API connector (not present in this PR).
4. **Explicit live-data authorization** before requesting credentials or sending the first network request.
5. **Separate publication approval** before any finding or chart is released externally.

PR #19 remains Draft. PR #8, E04, ASFI, composite HOLD flags and YSE Finance production pages must stay unchanged.
