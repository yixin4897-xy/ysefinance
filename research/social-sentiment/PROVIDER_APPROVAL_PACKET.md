# YSE Finance / AESM — YouTube API analytics permission preparation
**Draft for an application by the site owner; NOT submitted; no approval or API credential exists in this project.**
Prepared: 17 November 2026. Verify all current Google/YouTube policy terms immediately before submission.

## Critical issue to resolve

YouTube's general developer policies normally prohibit creating new or derived metrics from API Data. Beginning June 2026, its additional derived metrics policy describes some permitted analytics **only for audited developers whose specific analytics use case and amendment have been accepted**. The example of approved viewer-sentiment analytics does not itself establish permission for an independent, cross-video, cross-publisher Australian economic commentary monitor.

**Decision: HOLD all YouTube API comment retrieval, derived sentiment aggregation and publication until YouTube explicitly confirms whether this proposed use is permitted and any required amendment/audit is completed.**

References:
- [Additional policies for derived metrics and data storage](https://developers.google.com/youtube/terms/derived-metrics-policy)
- [Developer policies §III.E.4 and §III.E.8 / §III.L](https://developers.google.com/youtube/terms/developer-policies)
- [Policy compliance guide and audit route](https://developers.google.com/youtube/terms/developer-policies-guide)
- [Official commentThreads.list parameters and 1-unit quota cost](https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list)

## Proposed project description for a Google/YouTube compliance enquiry

> YSE Finance, an Australian tax and accounting business, is considering an internal, limited research project named "AESM Social Sentiment Research" to analyse **topic-level economic discussion** in public comments on Australian-relevant news and explainer videos about living costs, housing, employment, consumer spending and small-business operating conditions.
>
> We propose to use the official YouTube Data API **commentThreads.list** for a small, preselected sample of public videos, at first only top-level comments. We do not propose downloading videos, profiling viewers, merging accounts, inferring users' personal/sensitive financial status or personal demographics, selling access to comment-level data, or training a language model on commenters' data.
>
> We would seek to produce **aggregate, anonymised research categories** by week (e.g., number of selected discussions mentioning living costs), clearly labelled as a non-representative sample of comments. We would like to compare these patterns descriptively with separate ABS/RBA statistical releases and YSE Finance's published independent E04/ASFI indicators. We will not present YouTube-derived metrics as YouTube-endorsed or infer broad Australian population sentiment. We do not intend to publish or retain individual comment text or author identifiers.
>
> **Please confirm:** Is this specific cross-video, cross-channel, independent economic discussion analytics use case allowed under the additional derived-metrics amendment / Analytics & Reporting approval? If not, which narrower use case, audit or written authorization would be required? What deletion, 30-day refresh, viewer consent, aggregate-retention and attribution requirements apply?

This text is an **application draft**, not a statement that YouTube has approved the use case. Do not misstate existing access, Google Cloud project IDs, registered privacy policies or data provenance.

## Internal checklist for the owner (all pending)

- [ ] Confirm exact commercial research purpose and whether results will remain internal or eventually appear on the public site.
- [ ] Identify the YouTube API project and approved legal/business operator; **do not place its keys, secrets, OAuth tokens or actual project IDs in GitHub PRs**.
- [ ] Review YouTube API Services Terms, developer policies, and the additional derived-metrics policy with current date and effective terms.
- [ ] Request an API compliance audit / quota extension or amendments where required and obtain a specific written response about **this use case** (not an assumption based on an example).
- [ ] Establish the required user-facing Terms/Privacy Policy, data subject deletion route and any operator notices.
- [ ] Authorize a bounded video-selection plan, maximum pages/quota, permitted sampling period, refresh/retraction process, and spending ceiling.
- [ ] Complete OAIC/privacy review: no sensitive-trait inference, personal financial profiles, or unneeded identifiable content.
- [ ] Approve deletion schedule for non-authorised API Data (generally no longer than 30 days without refresh or deletion), and verify whether any accepted derived-metric retention exception actually applies to the granted use case.
- [ ] Confirm a legal data-use basis for any third-party classifier. No raw comment text to third-party LLMs by default.
- [ ] **Separate owner authorisation to implement** a live connector; a policy application alone does not start collection.
- [ ] **Separate owner authorisation to publish** any actual observations.

## Bounded research sampling proposal (NOT active)

Plan for 5 economic themes, with English and Chinese as **separate corpora**; avoid using one channel's editorial perspective as a national proxy. Predeclare inclusion/exclusion rules: Australian relevance by video subject, publisher diversity, publication date, moderation availability, known selection bias, comment language, and relevance of the thread.

The dry-run CLI takes a local JSON manifest of candidate video IDs, topic, language, Australia-relevance rationale and selection rationale. It allows up to 10 videos and 3 pages per video, with a maximum 30 request budget. Each **commentThreads.list** page is documented at 1 quota unit; this is an upper-bound calculation, not a monetary price estimate, count of unique users, or approval.

Predefine a report card for each approved week: sampled videos by topic, sampled video dates, requested/available top-level threads, relevant/unclassified counts, duplicates, moderation gaps, English/Chinese counts, suppressed small cells, manual annotation performance, and comparison periods of ABS/RBA/E04/ASFI. Display **no** public economic sentiment score.

## Required approval record (private, not committed)

| Field | Required evidence |
|---|---|
| Operator | Legal entity and internal owner, confirmed outside this repo |
| Source licence/policy | Dated version of YouTube policies reviewed |
| API analytics approval | YouTube response / approved amendment and exact scope |
| Data use | Purpose, allowed APIs, permitted videos and publication scope |
| Privacy review | Documented data minimisation, notice, consent (if applicable) and deletion rights |
| Raw data retention | Enforced expiry and refresh/delete rules |
| Aggregate metrics | Whether permission applies, storage and publication restrictions |
| Reviewers | Owner and independent privacy/compliance reviewer |
| Expiry | When the permission must be rechecked |

When no specific approval is documented, the project remains in synthetic-only mode. **The existing local JSON attestation mechanism in the prototype is not, by itself, proof of third-party rights.**

## How to move forward, without modifying production

1. The owner may use the description above in YouTube's official API compliance / quota extension process, selecting the applicable "Analytics & Reporting" use case when offered.
2. Obtain YouTube's explicit decision and a privacy/retention plan. Keep private approvals outside GitHub.
3. Review the testable code in PR #19; leave it Draft.
4. Only after confirmation and separate authorization, build a narrowly scoped official-API connector and run a limited live sample under a new reviewed change. The present PR has **zero live-data collection capability**.
