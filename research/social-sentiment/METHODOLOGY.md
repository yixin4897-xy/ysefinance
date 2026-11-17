# AESM social-discussion research methodology — draft, not validated

## Scope and estimand

The candidate measures *themes and language in a **selected corpus of permitted economic discussions***, not a nationally representative sample, general consumer confidence, a policy-preference measure or a predictor of business/recession conditions. Unit of analysis is one redacted discussion text row; an account is not a unit of analysis and no individual-level trajectories may be constructed.

Proposed five thematic dimensions: cost of living/inflation, housing/mortgage pressure, employment/income, consumer spending, and small-business operating conditions. Classification is a transparent, fixed-keyword baseline rather than a trained AI model. Mixed and neutral opinions are retained. Multi-theme ties are excluded as unclassified rather than forced into one category.

## Workflow and data quality

1. **Rights and provenance review before acquiring data.** Record platform authorization, observation dates/time zone, source-language, selection method, topical inclusion criteria, retention rules and exclusions; store permission evidence outside Git. Preserve an audit trail of aggregate counts, not identifiable raw data.
2. **Data minimisation.** Handle only pre-redacted, permitted text, basic platform label, timestamp and language. Reject unexpected account/profile/identity fields. Never infer personal financial condition, sensitive traits or cross-platform identity. Keep source raw data outside repository; transient in-memory text parsing is not a substitute for a formal privacy review.
3. **Relevance and de-duplication.** Deduplicate exact normalized text within platform/language/UTC week. This prevents some duplicate boilerplate but can also undercount identical legitimate observations; record and later manually review. Reject no-topic and ambiguous tied-topic rows. Record input/accepted/dedup/invalid counts.
4. **Classification.** Five themes and four directional labels (positive, negative, neutral, mixed) using fixed lexicons. Mark whether the text appears personal, an economic claim or opinion, but these are heuristics and can misread negation, satire, quotes, translation, political opinion or factual news mentions. **Do not equate the share of negative comments with society-wide pessimism.**
5. **Aggregation.** Convert timezone-aware timestamps to UTC; assign week by UTC Monday. Report weekly retained counts and topic/sentiment counts; suppress cells below n=5. Keep languages separate in later validation; a combined sample is not a valid bilingual trend estimate. Compare ratios *within* a stable sampling frame only, with per-platform denominators.
6. **Validation before pilot.** Hand-label a blinded stratified sample by theme, language, source and week (two reviewers ideally). Report confusion matrices and accuracy/precision/recall, disagreement and negative/positive detection error. Test for sarcasm, dual topic and quote contamination. Assess per-platform sample composition and coverage stability.

## Relationship to E04/ASFI and official data

- E04 uses ABS-derived household real income purchasing power series, with the current public complete-input observation at 2026 Q1. It is not a personal wage index.
- ASFI public panels contain distinct RBA/APRA observations with varying vintage and population definitions; composite scores remain HOLD.
- CPI, labour force and RBA cash-rate releases must be compared by their own reference dates and publication vintages.
- Social discussion counts may be descriptively compared with those **separate** official indicators at the time of publication. No causality, forecasting, composite score, model promotion or backtesting claim is permitted from this pilot.

## Bias and uncertainty to document

Self-selection; platform geography (AU-labelled content is not necessarily by Australian residents); time-of-day; language mix; automated activity; news events; popularity/engagement algorithms; quotes of politicians; sarcasm; missing/unavailable discussions; API pagination and sampling; repeated content; platform restrictions; small-N instability. Document inclusion/exclusion percentages each week, not just model sentiment output.

## Decision gates

Phase 1: offline synthetic **PASS/FAIL** engineering tests. Phase 2: platform authorization and privacy review. Phase 3: limited real approved corpus + annotation validation. Phase 4: four-week research pilot with predefined comparisons. Phase 5: owner-approved external publication only if measurement is credible. The present deliverable is **Phase 1 only**.
