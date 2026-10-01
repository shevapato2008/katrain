# Oteai ID 22 × Ukrainian: independent source review

Reviewed 2026-10-01 21:53 UTC. Scope: the source-only follow-up in `kifu-name-oteai-ua-source-research-followup-2026-10-02.md` and its controlled raw captures. **Verdict: PENDING.** This is neither a conventional-name decision nor an approved negative closure, generated spelling, candidate, or database write.

## What the captures support

- The Japanese source name and reading are **`大手合` / `おおてあい`**. The [Nihon Ki-in history page](https://archive.nihonkiin.or.jp/juniorclub/history/history07.htm) places the reading beside the name and describes the dan-promotion competition. [Shogakukan's Digital Daijisen entry](https://kotobank.jp/word/%E5%A4%A7%E6%89%8B%E5%90%88-39406) gives `おお‐てあい` for the same Go sense. The dictionary also lists other senses/readings, so the Go definition and the association history matter to this identity check. These are Japanese anchors, not Ukrainian usage.
- **No positive Ukrainian conventional form is supported by the captured pages.** The [UFGO topic 824](https://forum.ufgo.org/viewtopic.php?t=824) has `Отеаи` and `Отэаи` inside Russian posts and `Oteai` inside an English quotation. Its HTML `lang=uk` describes the interface, not those passages. The captured [Russian Wikipedia page](https://ru.wikipedia.org/wiki/%D0%9E%D0%BE%D1%82%D1%8D%D0%B0%D0%B8) uses `Оотэаи` in Russian. These are useful rejected leads, not Ukrainian attestations or completed Ukrainian-language non-hits.
- The controlled `capture-manifest.json` has SHA-256 `95bca1580a899e81ab02d64151d9ac8f547a2ea8a258cf6702274eb75e9fd1be`. I checked all **34/34** stored response files against the manifest's byte hashes; all match. The nine captured UFGO native-search pages each display `Нічого не знайдено` in the result region. This supports only the nine recorded public site-search responses, not a full-site or forum absence claim.

## Why a negative closure is not ready

The existing ownerless v1 template (`kifu-name-oteai-uk-manifest.json`) is still `pending_review` and binds registry `2026-10-02.2`. It declares both Ukrainian Wikipedia descriptive searches 8 and 9 as one-page, exhausted checks. The captured API JSON contradicts that: search 8 reports 97 hits and continuation through offset 50; offsets 0–40 returned 50 results, while offset 50 returned HTTP **429** and the rest remain unread. Search 9 reports 12 hits and continuation to offset 10; the final two results were not captured. Neither a 429 response nor an unfetched page is a completed negative check. The older template and its hashes cannot be reused as an approved closure.

The six-language `secondary_reasonable_v1` policy permits an honestly bounded scan, but there is no revised, independently reviewed scope here. Any finite boundary must retain the actual next URL, mark `pagination_exhausted=false`, and identify the unreviewed pages and channels. The checked Ukrainian UFGO search responses and Wikidata Q4335071 `uk` fields can contribute to a future minimum professional-plus-exact-entity scope, provided the exact Wikidata entity is bound to `大手合` and the source language and event identity are reviewed. The captured `uk` API response has empty `uk` labels/aliases and no `ukwiki` sitelink; its `jawiki` sitelink is an identity lead, not a separate captured Japanese label response.

## Minimum follow-up

1. Fetch and review search 9 at `sroffset=10`. Retry search 8 at `sroffset=50` and continue to its terminal page, **or** submit an explicit v2 bounded scope ending at the last successfully read page (offset 40), with the real offset-50 continuation, the 429 and remaining 47 results recorded as limitations. The failed page cannot be counted as read. Resolve any relevant results found in the follow-up.
2. Build a new exact-owner `event:22 × ua × ja` research/scope record against the intended pinned registry, with corrected pagination, the nine UFGO native-search results, and a separate exact-QID Japanese identity capture for Wikidata Q4335071. Keep Russian forum/Wikipedia occurrences as independently adjudicated foreign-language leads. Have an independent reviewer assess source applicability, actual body languages, excluded leads, and the declared finite boundary.
3. Only after an approved negative closure, separately resolve Ukrainian transcription/wording and obtain an independent `generated_review` before any generated display name or import.

This review makes no claim that a Ukrainian conventional name does not exist outside the pages actually read.
