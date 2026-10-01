# Zhao player 608: independent five-record artifact review

Reviewed **2026-10-01T22:37:35Z** (2026-10-02 Shanghai) by `/root/cao_uncertain_sol`; runtime identifies this reviewer as GPT-6 (exact model suffix not exposed here). Scope: the five pending `es/fr/ru/tr/ua` research/candidate JSONL rows described in [the producer memo](kifu-name-zhao-608-es-fr-ru-tr-ua-pending-artifacts-2026-10-02.md). **PENDING / Important correction required before candidate review.** This review approves no candidate, alias, owner preimage, raw-slot link, or write.

All ten rows use `owner: {kind: player, id: 608}` and `review_status: pending`; production 608 is the intended environment-specific ID, while test 609 cannot be substituted into these records. The two mode-0600 JSONLs rehash to the memo's SHA-256 values (`cb857d58…783a232` research, `8cbe1e2c…30c86f` candidates). All five research rows pass `validate_research_record` with registry `.3` (canonical `dd6e5f62…58e`), and each pending candidate's `research_sha256` matches its research record. Their shared `produced_at=2026-10-01T22:28:35Z` follows the recorded source captures and the cited source-level decisions; I found no reversed timestamp. The pinned inventory still has no associated player 608, so these results do not make any candidate write-ready.

**Important provenance issue:** successful format validation does not prove a stored `body_excerpt` was copied from the response whose SHA-256 is claimed. I located and rehashed the captured bodies, decoded them as published, and compared **all six primary checks, all six variant notes, and all five Wikipedia `article_evidence.passage` values** against raw and visible page text. The KBA original-name and Nihon Ki-in reading excerpts in each of the five records are exact visible-text substrings. A visible-text `NO` below means the stored excerpt is not a contiguous passage of its saved source body:

| Row | Primary `source_checks` | `source_variant_notes` | Wikipedia article passage |
|---|---|---|---|
| `es` | Wikipedia title `YES` | Wikipedia `Cho Chihun` `YES` | `YES` |
| `fr` | Wikipedia larger excerpt `NO` | FFG `CHO Chikun` `YES`; Wikipedia larger excerpt `NO` | `YES` in visible text |
| `ru` | RusGoLib `NO` | GoMagic `NO` | — |
| `tr` | Istanbul Go School `NO`; Turkish Wikipedia API `YES` | — | `YES` |
| `ua` | UFGO p88623 `YES` | UFGO p89714 Latin use `NO`; Kharkiv genitive use `NO` | — |

The forms themselves do occur in the cited bodies: RusGoLib's actual heading is `Тё Тикун (Cho Chikun) (20.06.1956)`; GoMagic has `Чо Чикун, 9-дан про`; Istanbul Go School uses `Cho Chikun` in its Turkish title and biography; Bohdan's Ukrainian sentence says `Анонсований матч Cho Chikun vs DeepZenGo`; the Kharkiv report has `«Позиційний аналіз» Чо Чікуна`. The nonliteral records instead join separated text, alter punctuation, or substitute an English summary. The Russian Seoul-versus-Busan conflict is correctly retained. The UA items share the UFGO publisher and cannot be counted as independent publishers.

Correct the seven nonliteral excerpts from the actual controlled bodies, then regenerate affected research and candidate hashes. The Spanish/French primary rationale also needs the strongest reviewed Go-source usage bound as an actual check or an explicit note that the current positive is only a Wikipedia title (`es`) or pronunciation aside (`fr`). The display forms agree with prior independent source decisions: `Cho Chikun` (`es/fr/tr`), `Тё Тикун` (`ru`), and `Чо Чікун` (`ua`), with alternatives retained as leads rather than approved aliases. No controlled source body, JSONL, database, or candidate was changed by this review.
