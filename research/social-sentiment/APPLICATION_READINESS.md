# YouTube API derived-metrics application readiness — 17 November 2026

**Researcher-side application packet, not a submission or approval.** The owner has enabled YouTube Data API v3 in Google Cloud project `yse-finance-aesm-research`, and reported a **10,000-unit daily limit with 0 units used** (from the Google Cloud console screenshots in the working discussion). No live API credential, API request, approved derived-metric application, or deployed YouTube analytics service has been verified.

| Requirement (form fields seen by owner) | Status | What can honestly be supplied |
|---|---|---|
| Project name / ID | KNOWN | YSE Finance - AESM Research / `yse-finance-aesm-research` |
| **Project number** (digits only) | NOT YET PROVIDED | Obtain from Google Cloud project's Welcome or Dashboard; do not substitute the Project ID or number of another project |
| Category | IDENTIFIED | Analytics & Reporting. If supplementary Others is available, describe **cross-video Australian economic discussion research**, not a channel performance product |
| OAuth requirement | DESIGN_ONLY | Proposed offline/internal non-user-facing analytics, no OAuth. Set "Not applicable" only if future actual implementation matches this |
| Expected API usage | ESTIMATED, NO LIVE USAGE | Synthetic preflight: 2 fictional videos x 2 pages x 50 => <=4 commentThreads.list units, not a claimed deployment or ongoing quota |
| Requested total quota | **RESOLVED AT QUOTA DETAILS** | Official form includes **No change / Default quota (10k quota points)**. Select this when submitting the first compliance audit for derived-metrics permission; do **not** request increased quota. Section 1 wording still requires accurate identification as an initial audit, not a periodic re-audit. |
| Derived metrics policy | OFFERED IN SECTION 5, NOT ACCEPTED | Screenshot shows required acknowledgement checkbox. Accept only after owner reads/understands terms, **and do not assume application approval** |
| API Client overview/screenshots | PROTOTYPE ONLY | Run `build_demo_dashboard.py` locally; capture a genuine screenshot clearly stamped SYNTHETIC DEMO; label as local feature prototype, not a deployed YouTube client |
| Privacy Policy screenshots | NOT READY | Public policy currently concerns YSE Finance tax and website processing, without YouTube API scope; proposed supplement drafted in `PRIVACY_AND_TERMS_DRAFT.md`, not published |
| Homepage screenshot with privacy link and YouTube branding | NOT READY | Only capture from **actual published** page after the owner separately approves correct YouTube-linked notices and branding. Existing home page does not show a deployed YouTube research feature |
| Terms of Service documentation | DRAFT, NOT EFFECTIVE | Proposed addendum exists. Review with legal/privacy adviser; publish only if approved and accurate. Then capture actual document/page evidence |
| YouTube-derived metrics rights | **HOLD** | Specific written permission / acceptance and proper audit; not granted by enabling API or self-checking a box |
| Data retention and deletion implementation | DESIGN_ONLY | No live data exists; plan deletion/refresh requirements. Real automated deletion and retraction controls must be built/tested before processing real comments |
| Privacy/legal review | PENDING | Reviewer must approve exact business purpose, disclosures, data rights, deletion route and data minimisation |
| Owner approval to collect real comments | NOT GIVEN | Separate explicit authorization required |
| Publication / website merge | NOT GIVEN | PR #19 remains Draft, not deployed |

## What the owner can do today

1. **Do not submit the form yet**: resolve the request-type mismatch through YouTube's official API Services support/clarification channel. The form is not a substitute for getting an audit/permission decision.
2. Verify the proper **numeric Project Number** for `yse-finance-aesm-research` in Google Cloud; keep credentials private.
3. Decide whether the prototype will remain **internal research** or eventually become a public web feature. This changes privacy notice and screenshot obligations.
4. Review the proposed privacy and Terms addendum, alongside the actual current `https://ysefinance.com.au/privacy.html`, before any policy change. If approved, manage the public-site change in a **separate PR** (not PR #19) and then capture genuine live evidence.
5. Run the offline demonstration and obtain a genuine screenshot for the functional feature **with the synthetic label visible**.
6. Only after official approval and an owner go-ahead, propose a narrow compliant official-API connector in another reviewed PR.

## Official links

- https://developers.google.com/youtube/terms/derived-metrics-policy
- https://developers.google.com/youtube/terms/developer-policies-guide
- https://developers.google.com/youtube/data/guides/quota_and_compliance_audits
- https://support.google.com/youtube/contact/yt_api_form?hl=en
- https://ysefinance.com.au/privacy.html

## Important non-claims

This packet does not imply that YouTube has approved any sentiment metric, that the current YSE Finance public website already contains YouTube-specific terms, that any Cloud Project Number is known, that real comments have been accessed, or that a 4-unit synthetic budget implies a 4-unit live request allocation.
