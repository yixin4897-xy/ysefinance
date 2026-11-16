# AESM Social Sentiment — data-source feasibility (16 Nov 2026)

**This is a permissions and technical-access review, not an approval to collect.** YSE Finance is a business; do not assume a research exception or that public data may be commercially mined. Recheck platform terms and consult qualified legal/privacy advisers before starting acquisition.

| Source | Research value | Current access boundary | Phase 1 decision |
|---|---|---|---|
| Reddit | Australian cost of living, housing, jobs and business discussion | Explicit approval required before any data API access; commercial use requires written approval / contract; responsible-builder policy covers scraping and data mining | **HOLD — permission required; no scraping/API use** |
| YouTube | Comments on Australian economic news videos | Official YouTube Data API `commentThreads.list` may return published comments for a video; platform policy, privacy, quota, attribution and approved uses still apply; API credentials and permitted scope need review | **Design-only, no API calls in Phase 1** |
| Google Trends | Topic search interest, **not comment sentiment** | Google Trends API remains restricted Alpha requiring application; manually exported lawful aggregate data may be separately reviewed | **Optional aggregate comparator** |
| Xiaohongshu | Chinese-speaking discussion about life in Australia | No verified authorized general-purpose automated collection path established for this project | **No automated scraping** |
| X | Fast-moving policy and rate discussion; not representative | X prohibits non-API website scripting and sets developer/API rules and quotas | **No non-API automation** |

## Official references

- Reddit Developer Platform and Accessing Reddit Data: https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data
- Reddit Responsible Builder Policy (updated October 2026): https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy
- Reddit Data API Terms (last revised July 2026): https://redditinc.com/policies/data-api-terms
- YouTube `commentThreads.list`: https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list
- YouTube Developer Policies: https://developers.google.com/youtube/terms/developer-policies/
- Google Trends API Alpha: https://developers.google.com/search/apis/trends
- X automation rules: https://help.x.com/en/rules-and-policies/x-automation
- OAIC APP 3 data minimisation/scraping guidance: https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-3-app-3-collection-of-solicited-personal-information

## API feasibility and costs

**YouTube:** `commentThreads.list` supports `videoId` and paginated `maxResults`, with a documented quota cost of 1 unit per call. Access/setup conditions and quota allocation depend on the Google Cloud project; forecast real costs only after choosing the specific videos, pages and refresh frequency. Requests can reveal user content; do not access until permitted data-use and minimisation rules are reviewed.

**Reddit:** Business/monetised research requires Reddit's explicit permission and a separate commercial arrangement; pricing is not established. Treat any cost estimate as **unknown pending quotation**. Neither unofficial libraries nor browser scripts circumvent this requirement.

**Google Trends:** API is application-only Alpha as of this review; no guaranteed access or API pricing is established. The dashboard/manual export and official aggregate series are possible *alternative* research inputs, subject to provenance checking.

**X and Xiaohongshu:** costs and accessible authorized data are unresolved. Do not start paid subscriptions or automation without a decision.

## Four-week pilot proposal (not initiated)

Week 1: confirm legal/platform rights and written data-handling approval; define 5 research dimensions, inclusion/exclusion rules, AU relevance and pre-sampling frame. Week 2: use permitted limited data and manually labelled holdout to measure precision/recall and bias by language/platform. Week 3: inspect weekly topic counts, platform coverage, deduplication, missingness and sentiment classification errors. Week 4: assess stability and write a comparison with official data and E04/ASFI; determine if publication merits consideration.

Stop criteria: no documented access rights; inability to de-identify; excessive classifier errors; highly skewed platform coverage; invalid weekly denominators; inadequate observations; evidence of possible sensitive-trait inference; lack of a lawful deletion/retention process.

## Publication boundary

No social sentiment percentages, scores, rankings, claims about the Australian population, or quotes from unapproved sources are to be published. The simulated fixtures provide **zero** empirical evidence. Keep all AESM public and private composite states unchanged.
