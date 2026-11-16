# AESM Social Sentiment — example weekly report (SYNTHETIC ONLY)

**NOT REAL AUSTRALIAN SOCIAL DATA. DO NOT PUBLISH AS AN ECONOMIC FINDING.**

Research status: `CANDIDATE_ONLY_UNVALIDATED`  
Source: 27 fully invented discussion rows, `synthetic: true`; 26 retained after one exact duplicate is excluded.  
Window: two UTC weekly buckets starting 2 and 9 November 2026.  
Languages: 22 English, 4 Simplified Chinese invented examples.  
Platforms: `reddit` and `youtube` are **fictional category labels** in the fixture, not sources that were accessed.

## Demonstration: aggregate weekly table

| UTC week beginning | Relevant rows | Classified as negative | Classified as positive |
|---|---:|---:|---:|
| 2026-11-02 | 13 | 6 | suppressed (n<5) |
| 2026-11-09 | 13 | 6 | suppressed (n<5) |

Topic-level and small language/platform cells are suppressed under the prototype's `n >= 5` minimum. These labels are **baseline keyword tags**, not measured sentiment of Australian residents. The fixture was invented to exercise the pipeline and has no statistical interpretation.

## What this demonstrates

- The offline program accepts bounded, pre-redacted JSONL records and produces weekly topic/sentiment aggregates.
- A duplicate is removed; unique counts and source-language coverage remain reportable.
- Small cells are suppressed and no individual post, username, profile, contact detail or verbatim user quotation is included.
- Mixed and neutral classifications, uncertainty and incomplete topic coverage require explicit reporting.

## What this does NOT demonstrate

There is **no evidence** in these 27 fictional rows that Australians are more optimistic or pessimistic, that households face particular stress, or that the synthetic categories reflect Reddit/YouTube trends. Nothing here should be compared quantitatively to E04, ASFI, CPI or employment data. No platform authorization or live collection has occurred.

## Validation and next decision

Before a real pilot, obtain platform permissions, choose a reproducible Australian-relevant sampling frame, document data minimisation, test classification on human-labelled English and Chinese samples, inspect bias by platform, and define retention/deletion. Run a separate four-week live pilot **only after explicit approval**; no automatic deployment or publication.
