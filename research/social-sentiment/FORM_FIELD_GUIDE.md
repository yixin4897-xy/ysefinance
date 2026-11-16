# AESM YouTube API application — field-by-field worksheet

**As of 17 November 2026. DRAFT. NOT SUBMITTED.**
Based on the owner's live form screenshots and the official YouTube [Audit and Quota Extension form](https://support.google.com/youtube/contact/yt_api_form?hl=en), [quota/audit guide](https://developers.google.com/youtube/data/guides/quota_and_compliance_audits) and [additional derived metrics policy](https://developers.google.com/youtube/terms/derived-metrics-policy). Forms can change. **The owner must personally review agreements and submit.**

## What is known

- Project name: **YSE Finance - AESM Research**
- Google Cloud Project ID: `yse-finance-aesm-research`
- Numeric **Project Number: NOT YET PROVIDED**. Locate it on the Google Cloud project Dashboard / Welcome page. Do not substitute an ID or an earlier project's number.
- YouTube Data API v3: **enabled**, quota displayed by owner **10,000/day**, no API usage at last screenshot.
- Proposed app: **internal experimental analytical prototype** based on manually selected AU-relevant videos; **zero real YouTube comments collected**; no OAuth/user-facing YouTube login; PR #19 Draft, never deployed.
- Live collection, privacy/terms and derived-metric rights: **NOT IMPLEMENTED / NOT APPROVED**.

## Form walkthrough (enter facts only)

| Section / field | Suggested truthful response | Notes |
|---|---|---|
| Section 1: Request Type | **Initial compliance audit** is the purpose. The currently worded first choice says "Complete a compliance audit to request for additional quota"; second says "requested to complete re-audit" and does **not** apply. | Read help text carefully. The **separate quota details section explicitly supports default/no change**. If the first choice's wording remains ambiguous, ask YouTube support before submission. Never select periodic re-audit without a request. |
| Section 2: Organization name, contact | **YSE Finance**, with the actual legal operator and authorized contact details chosen by owner | Do not invent ABN, company registration, phone, company legal form or employee count. |
| Section 3: Business Model | Australian tax/accounting practice undertaking an independent economic research **prototype**. | Be transparent that the business may publish research/blog content in future; no claim that project is academic/non-profit. |
| Section 4: API client overview | Separate Google Cloud project and offline software prototype. No real API calls, API credential or public YouTube data feature yet. | Describe intended APIs, permission stage and functionality that actually exists. |
| Section 5: Project number | **Numerical Google Cloud Project Number** (owner to retrieve). | Not Project ID. |
| Section 5: Use Case Category | **Analytics & Reporting**. Use **Others (please specify)** only when appropriate to explain independent Australian economic discussion research beyond typical channel analytics. | Do **not** claim academic/non-profit status under Education & Research. Do not classify tax referral/marketing as the intended use. |
| Section 5: OAuth | **Not applicable (no user-facing component)** if future design remains read-only API-key access for a private back-office research pilot. | If OAuth is later required by particular endpoint or user-facing features, reassess. Don't select "Yes" just because form defaults to it. |
| Section 5: Additional derived metrics | Read and, if appropriate, personally agree to the amendment; request applicability for **cross-video Australian economic discussion topic/sentiment analysis**. | Consent checkbox is not an approval. YouTube decides whether use case qualifies. |
| Section 5: Expected API usage | Lowest truthful projected usage tier for a tiny pilot; no previous usage. | Initial synthetic design: 2 candidate videos × 2 pages × 50 comments/thread upper bound, 4 quota units, not actual data or guaranteed results. |
| Quota Details: Total quota requested | Select **No change / Default quota (10k quota points)** as the official form allows. | **Do not request any extra quota.** YouTube's docs explicitly route derived metrics applications through the standard audit/quota form. |
| Endpoints | Expected `commentThreads.list` (read-only), potentially `videos.list` for authorized metadata subject to review. | **Do not select `search.list` or `videos.insert` for quota extension** unless actually planned and documented. |
| Reason / detailed justification | Use the truthful short statement below, adjusted for the exact field and any strict word limit. | Explicitly state that no live collection has occurred. |
| Section 6: Privacy screenshots | **NOT READY**. Existing public policy lacks active YouTube API data disclosures. | Owner-approved policy additions, actual live website disclosures and genuine screenshot are required; a GitHub markdown draft is not an acceptable live screenshot. |
| Section 6: Homepage screenshot | **NOT READY**. The present site does not publicly implement a YouTube API client or the requested YouTube branding. | Do not fabricate player/brand/screenshots. Prepare a truthful public policy/notice path only after review. |
| Section 6: Terms documentation | Draft terms in `PRIVACY_AND_TERMS_DRAFT.md`; not adopted. | Need legal/privacy review and real effective Terms before representing as in force. |
| Section 6: Dashboard feature screenshot | **Synthetic-only prototype available** after running `build_demo_dashboard.py`. | Submit only a **genuine browser capture** showing prominent "SYNTHETIC DEMO" and describing the stage; Google may request more evidence. |
| Section 7: Attestations | Owner must verify the actual implementation and terms, then accept personally. | Never sign/attest on the owner's behalf; do not claim audit passed. |

## Plain-English purpose text for the form

> YSE Finance is an Australian tax and accounting practice developing a separate experimental economic research tool. We propose to analyze aggregate discussion topics and sentiment in a small, transparently selected sample of public comments on Australia-relevant YouTube economic news videos using the official YouTube Data API. Topics include living costs, housing, employment, consumer spending, and small-business conditions. The goal is to compare non-representative online discussion trends descriptively with independent Australian official statistics, not to profile individuals or replace national surveys. We do not infer sensitive user attributes, train third-party AI models on YouTube comments, or sell comment data. The prototype currently uses only fabricated test records; no actual YouTube API comments have been retrieved. We seek an initial compliance audit and confirmation of our eligibility for the Additional Policies for Derived Metrics and Data Storage, **with no increase to our existing 10,000-unit daily quota**. We will not perform real sentiment analysis or retain derived metrics under the amendment until the specific use case is accepted and our privacy, deletion and data-use controls are approved.

## Current actions that must remain blocked

- Do **not** click Submit with placeholder legal information, screenshot mockups of active privacy notices or unsupported data use claims.
- Do **not** create/expose an API key in a public PR or chat, and do not fetch comments merely because the API is enabled.
- Do **not** publish screenshots of simulated statistics as real Australian public reaction.
- Do **not** deploy the new research UI or change production website policies without separate owner and legal/privacy review.

## Owner's efficient next actions

1. Retrieve numeric Project Number from Cloud Console for **this project**.
2. Confirm legal operator/contact (only in private form; not GitHub).
3. Confirm with YouTube support how to describe the **initial** audit request where Section 1 references "additional quota" but Quota Details correctly offers **No change / Default quota**. The official documentation says the same form handles derived metrics.
4. Approve a **separate** accurately worded privacy/Terms update (with YouTube API disclosure, required Google links, actual deletion procedure, suitable branding), subject to legal/privacy review. Capture real live screenshots **only after** deployment.
5. Run local synthetic UI and capture an authentic labelled feature screenshot if requested.

**Decision state: application evidence in preparation. PR #19 stays Draft and unmerged.**
