# Wu player 1: independent `.3` Spanish/Ukrainian artifact review

Reviewer: `/root/wu_es_ua_review_astra`, configured model `gpt-6-astra`, reasoning `high`; reviewed 2026-10-01 20:02 UTC. Producer: `/root/wu_es_ua_sol`, `gpt-6-sol`. These are different agents; this reviewer did not produce either candidate or the earlier Ukrainian editorial decision.

| Language | Display / kind | Artifact decision |
|---|---|---|
| `es` | `Go Seigen` / `conventional` | **needs-more**: substantive evidence passes; name-row preimage is missing |
| `ua` (source `uk`) | `Ґо Сейґен` / `conventional` | **needs-more**: substantive evidence and conflict decision pass; name-row preimage is missing |

Both candidate objects omit `name_preimage_sha256`. The [runbook](kifu-name-review-runbook.md) requires the complete current database name-row hash, or explicit `null` if absent, fixed **before independent review**. `validate_candidate` passing does not establish write readiness. Obtain the actual production rows read-only, add their exact preimages through the producer, then have this reviewer recheck the complete resulting artifacts before any signature. No other blocking defect was found. Neither controlled JSONL file nor database was changed by this review.

## Evidence checked

I read the captured raw bodies in `/tmp/wu-v3-{nki,es-godokoro,es-wiki,uk-wiki,uk-ufgo,wikidata}`, independently recomputed their hashes, extracted both fixed Wikipedia revisions, and verified each recorded passage and passage hash. All matched the evidence JSONL. This checks the saved source captures; it does not claim a fresh network capture.

- Spanish: [Godokoro](https://godokoro.es/que-es-el-go) contains substantive Spanish Go history explicitly pairing `Go Seigen` and `Wu Qingyuan`. [Wikipedia revision 154961776](https://es.wikipedia.org/w/index.php?title=Go_Seigen&oldid=154961776) independently contains the exact display spelling in Spanish biographical prose. The [Nihon Ki-in profile](https://www.nihonkiin.or.jp/player/htm/ki001001.htm) connects 呉清源, ゴ セイゲン, WU Qing Yuan, Fujian, Segoe Kensaku and the professional career. Disputed birth/retirement facts are unnecessary to the identity match.
- Ukrainian: [Wikipedia revision 44688592](https://uk.wikipedia.org/w/index.php?title=%D2%90%D0%BE_%D0%A1%D0%B5%D0%B9%D2%91%D0%B5%D0%BD&oldid=44688592) is substantive Ukrainian prose using `Ґо Сейґен`, paired with 吳清源 and the matching career. Its raw-response and extracted-body hashes match. Nihon Ki-in supplies the required independent identity corroboration; Wikipedia's disputed dates and weak references do not supply identity anchors.
- The [UFGO post p86404](https://forum.ufgo.org/viewtopic.php?p=86404#p86404) really uses `Го Сейген` in Ukrainian for Wu Qing Yuan. Its author's displayed federation presidency does not make an individual post a federation naming standard. The candidate retains this as a full `found` check and excludes it only from the primary display, with an explicit genuine-alternative rationale. Following the [editorial decision](kifu-name-wu-uk-editorial-decision.md), this treatment is acceptable. The separately saved [Mozgus article](https://mozgus.ua/tsikavi-fakty-pro-hru-ho/) also matches its documented hash and corroborates that same alternative. It is documentary context outside these controlled research rows, not an additional claimed controlled check. Alias persistence remains future work; no alias has been imported by this review.
- Exact `es` and `uk` labels in captured [Wikidata Q541005](https://www.wikidata.org/wiki/Q541005) match the candidates and remain discovery evidence only. All three found-check URLs, plus the independent Nihon Ki-in URL, appear exactly in the Ukrainian conflict decision. Source captures at 19:54 UTC precede the Sol candidate/conflict decision at `2026-10-01T19:56:40.679430+00:00`; the earlier Astra editorial memo is context, not a backdated approval of these captures. Chronology passes the validator including `ac6e9381`.

The pinned inventory links player 1 to 1,267 slots containing `Go Seigen`, 吴清源/吳清源 and ranked Chinese variants. The two candidate owners are exactly existing player 1; no raw value, new identity or association change is proposed. Both stored research rows and pending candidates pass their respective validators against the pinned inventory and `.3` registry. This is a positive-name review, not negative-source closure or full-catalog coverage.

## Reviewed pins

| Artifact | SHA-256 |
|---|---|
| `.3` registry, canonical JSON | `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61` |
| Production v2 inventory gzip file | `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9` |
| `wu-v3-es-ua-evidence.jsonl` | `3669b06badf368f1e39e4d361363d09611195c6ed8f331c097b56c9515c4cf6a` |
| `wu-v3-es-ua-candidates.jsonl` | `d09098933c1d821fdc1262b02eac21a18f248a99175245a4fa882f7248a22e49` |
| Spanish research, canonical JSON | `fae6b3fbc175054a23a7f80387aa668ee3304ef2974e11a7ebfe90b82fed5452` |
| Ukrainian research, canonical JSON | `4c10c70f57c914b5c548f1ee688f874a78c5dd39e2fc70d8cf36c6957654035d` |

The inventory and both controlled JSONL files have mode `0600`. No reviewer fields have been inserted. A later signature must use the actual signing time after all captures, production time, conflict decision and preimage verification.
