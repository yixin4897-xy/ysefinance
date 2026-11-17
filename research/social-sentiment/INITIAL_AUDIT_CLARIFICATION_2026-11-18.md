# YouTube API — Initial Derived Metrics Audit Clarification
**Prepared: 18 November 2026 · For owner review and truthful submission only. Not sent.**

## Verified direction (official YouTube documentation)
- New or unsure developers are directed to an API Compliance Audit using the official Audit and Quota Extension Form: https://developers.google.com/youtube/data/guides/quota_and_compliance_audits
- Since June 1, 2026, audited Analytics & Reporting developers may request acceptance under the Additional policies for derived metrics and data storage: https://developers.google.com/youtube/terms/derived-metrics-policy
- Example 'Viewer Sentiment Analysis' includes NLP on Data API comments, but **AESM's specific cross-channel, macroeconomic topic research is NOT automatically approved**.
- The actual web form requests a homepage screenshot with Privacy Policy link **and visible YouTube branding**: https://support.google.com/youtube/contact/yt_api_form?hl=en
- We do not need additional quota; default 10,000 units per day is already available. Distinguish quota units from API request count.
- **No live YouTube comments or YouTube API requests have been collected or performed by this research project.**

## Suggested official initial audit clarification

**Subject:** Initial YouTube API compliance audit — AESM Social Sentiment Research (derived metrics; no quota increase)

Hello YouTube API Services Compliance Team,

I represent YSE Finance, an Australian registered tax agent that is developing a limited internal research prototype under our Australian Economic Insights (AESM) project.

We would like to request guidance on the initial compliance audit required to seek permission for a specific **Analytics & Reporting / Viewer Sentiment Analysis** use case under the Additional Policies for Derived Metrics and Data Storage. **We are not requesting additional API quota**; the Google Cloud project has the default 10,000 quota units per day.

**Proposed scope:** After approval, we would use the official YouTube Data API v3 `commentThreads.list` endpoint to retrieve a small sample of publicly available top-level comments from preselected Australian-relevant economic news and educational videos. We propose to measure weekly, topic-level discussion patterns about living costs, mortgages and housing, employment, consumer spending, and small-business conditions. Outputs would be aggregated, would not identify commenters, and would be clearly distinguished from both official Australian statistics and YouTube-produced metrics. We would not infer sensitive or protected attributes, claim to represent Australia's population, or sell personal/comment-level information.

**Actual development status:** The current review interface is a static interactive **synthetic-only demonstration**. It has no YouTube API integration, credentials, OAuth flow, live comments, or derived metrics produced from YouTube data. No real YouTube API comment data has been collected or stored. We have made the project's privacy notice, research-information Terms of Use and demo interface available for inspection, without suggesting that the API feature is already operational.

We would appreciate clarification of four questions before we submit the final supporting evidence:

1. Can a first-time developer seeking **permission for derived viewer-sentiment analytics**, at unchanged default quota, use the standard Audit and Quota Extension Form before a live YouTube-connected API Client is operating? If not, what initial approval or preliminary review procedure should be used?
2. Is our **independent cross-video and cross-channel Australian economic discussion aggregation** potentially eligible as Viewer Sentiment Analysis, or are approvals limited to video/channel/creator-centric analytics? Would a narrower video-level or channel-level scope be required?
3. The form asks for a **homepage screenshot with YouTube branding visible**. As the prototype currently makes zero YouTube API calls and does not display a YouTube video or player, is a truthful screenshot showing the Privacy Policy link and explicit non-integration disclaimer sufficient for preliminary review? If not, what evidence/branding is appropriate before live API integration?
4. The form asks for a **Primary Access URL and Dashboard/Feature Screenshots**. May we provide a public, unindexed synthetic review interface and an explanation of the planned API feature, or must we first implement a working YouTube API Client? If working integration is mandatory, how can we obtain a decision on the specific derived-metrics permission before conducting otherwise potentially restricted analytics?

Current review links:
- Privacy Policy: https://ysefinance.com.au/privacy.html
- Terms of Use (currently research-information terms only): https://ysefinance.com.au/aesm-social-terms.html
- Synthetic-only demonstration: https://ysefinance.com.au/aesm-social-review-demo.html

We can provide the actual Google Cloud numeric Project Number and further implementation plans privately in the official application. We have not included API keys or credentials in this message.

Please let us know the appropriate first-audit path and minimum evidence for an application at this development stage.

Kind regards,
YSE Finance
https://ysefinance.com.au/

## Evidence truthfulness table

| Form evidence | Present status | Audit caveat |
|---|---|---|
| 1 Privacy Policy screenshot | Published Section 9 with the Google Privacy Policy and YouTube policy links | Describes future retention/deletion intent, not an implemented live-data pipeline |
| 2 Homepage screenshot | Published footer Privacy Policy link | **Does not show YouTube branding**; no real YouTube feature is yet integrated |
| 3 Terms of Service documentation | Published AESM research-information Terms of Use effective 18 Nov 2026 | Terms are not consent for an operating API client; no live API feature exists |
| 4 Dashboard / feature screenshot | Published functional static synthetic topic-toggle page | NOT a YouTube-connected API Client or evidence of provider permission |

## Do NOT do yet
- Do not select re-audit if YouTube has not requested a re-audit.
- Do not claim any additional quota need, live API use, operational 30-day refresh/deletion mechanism, user-authorisation flow or already-approved metrics.
- Do not fabricate a YouTube logo, homepage integration, user consent screenshot, credentials or operational feature.
- Do not submit screenshot evidence as showing a live API Client.
- Do not enable live sentiment aggregation on real YouTube comments until explicit permission and technical privacy controls are in place.

## Owner form fields when proceeding
- Project ID: `yse-finance-aesm-research`; **Project Number is different**, numeric and must be copied from the project's actual Google Cloud Console.
- Category: **Analytics & Reporting**.
- OAuth 2.0: **Not applicable (no user-facing component)** if remaining internal and no Google sign-in.
- Expected requests: **Fewer than 1,000 requests per day**, consistent with intended small pilot.
- Quota requested: **No change / Default quota (10k quota points)**.
- Endpoint expected: **`commentThreads.list`**.
- Primary Access URL: do not misrepresent the synthetic-only demo as a working API Client; ask YouTube how to represent the present state.

Sources:
- https://developers.google.com/youtube/terms/derived-metrics-policy
- https://developers.google.com/youtube/terms/developer-policies-guide
- https://developers.google.com/youtube/data/guides/quota_and_compliance_audits
- https://support.google.com/youtube/contact/yt_api_form?hl=en
