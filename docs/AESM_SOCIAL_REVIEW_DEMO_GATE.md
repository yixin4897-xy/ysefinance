# AESM Social Discussion — synthetic review entry

**Scope:** `aesm-social-review-demo.html` is an **unindexed, static, client-side, 100% fictional demonstration** of a topic selector. It makes no YouTube Data API requests and cannot be submitted as proof of a functioning YouTube-connected API Client.

**Where it will live if separately approved:** `https://ysefinance.com.au/aesm-social-review-demo.html`. This URL is **NOT LIVE** until the PR is separately merged and GitHub Pages deployment succeeds. The page is public to anyone with the URL (not authenticated); `noindex` is **not** privacy protection. Do not enter this as a genuine YouTube API Client primary URL. The form reviewer may need an actual implemented client for approval.

## What was done
- A single self-contained HTML page was created from the conceptual five-topic design explored in [PR #19](https://github.com/yixin4897-xy/ysefinance/pull/19). It is **not the output of PR #19's Python classifier**, and does not represent an aggregation of that fixture.
- English/Chinese topic switcher and fabricated illustrative two-week bar chart. Values are explicitly labelled `fake`; no population inference.
- Persistent, visible `SYNTHETIC DEMO ONLY · ZERO LIVE API REQUESTS · NO APPROVED DERIVED METRICS` notice.
- No YouTube logo: branding guidelines say that logos used in apps must link to the actual YouTube feature/content, and must not imply endorsement. This page **does not integrate** any such feature.
- Links to real `/privacy.html`, `/aesm-social-terms.html`, and the YouTube Terms of Service; no tracking, backend, Google Cloud secrets, scraping, uploads, cookies, or personal data.
- `noindex,nofollow,noarchive` meta directive; no homepage link, site navigation, sitemap or E04/ASFI changes.

## Actual evidence status after this PR (if published)
1. **Privacy screenshot:** actual approved published policy Section 9 and Google Privacy Policy visible; still review future deletion implementation before claiming a live data service.
2. **Homepage screenshot:** homepage contains published Privacy Policy link. **No YouTube branding on homepage**, and this feature isn't a YouTube-connected API Client. The original form's branding requirement is **not satisfied**.
3. **Terms documentation:** published `/aesm-social-terms.html`, effective 18 Nov 2026 for research-information page only; not for an operating API service.
4. **Dashboard screenshot:** new page can be truthfully captured as a *functional synthetic-only preview*. It is **not evidence of real YouTube API feature or authorized derived metrics**.

## Approval gates
- [ ] Confirm whether the YouTube audit reviewers will accept an explicitly synthetic application prototype rather than a working API Client, and whether Section 1 can truthfully represent an initial derived-metrics audit at unchanged 10k quota.
- [ ] Confirm whether a publicly accessible, unindexed demonstration meets the intended visibility/privacy needs; it is not access-controlled.
- [ ] Conduct owner website/browser/mobile review, privacy/legal review of all published statements and links.
- [ ] Separately approve any merge and deployment of this HTML only, after reviewer requirements are understood. Leave [PR #19](https://github.com/yixin4897-xy/ysefinance/pull/19) Draft.
- [ ] Add proper, compliant YouTube attribution **only when genuine YouTube-connected functionality is implemented**, in compliance with [official branding guidance](https://developers.google.com/youtube/terms/branding-guidelines). Do not add logos merely to fabricate a provider-evidence screenshot.
- [ ] Before real API integration, implement accurate notices, any applicable user consent, data minimisation, refresh and deletion controls, security and reviewer-access requirements. Read [official developer policies](https://developers.google.com/youtube/terms/developer-policies).

**No approval, API keys, live comments, API traffic, genuine YouTube feature, provider submission, or Google endorsement is represented or implied by this PR.**
