# Fujitsu Cup five-language and finite-grammar independent review (2026-10-03)

**Decision:** PASS the five exact, source-attested display forms below. PASS the finite structural reading of **52 raw labels / 304 games**. HOLD the two `期` labels / two games. These decisions do **not** approve a canonical event identity or ID, any album-to-event link, the other six languages, or a database write.

I independently read the five retained HTTPS response bodies from the [source matrix](kifu-name-next-event-five-strict-source-matrix-2026-10-03.md), checked their SHA-256 hashes against its manifest, and read a sixth Haifong body captured for this review. The source bytes and a protected packet are under `~/.local/share/kifu-name-audit/2026-10-03/`. The Japanese organizer archive names `世界囲碁選手権・富士通杯`, lists 24 editions, and identifies Fujitsu as sponsor. This fixes the intended historic professional championship; a bare Fujitsu stem is insufficient to identify a game.

| Language | Decision | Exact reviewed display | Basis and limit |
|---|---|---|---|
| `cn` | PASS | `富士通杯世界围棋锦标赛` | [Sohu's 23rd-edition topic](https://sports.sohu.com/fujitsucup23/) prints `第23届富士通杯世界围棋锦标赛`; removing only the edition leaves the displayed phrase. This is a topic page, not an organizer archive. |
| `tw` | PASS | `富士通盃世界職業圍棋錦標賽` | [Haifong's 2025 history feature](https://www.haifong.org/news/content/DA2080B81489A3DA035BE72E6528AEB3) prints the exact full name, says Fujitsu sponsored it and it began in 1988, and discusses its international winners. The earlier [Haifong account](https://www.haifong.org/news/content/157A1D983409CB2FFAFF70140B175A51) calls the 1995 event `第八屆日本富士通盃`; `日本` is contextual there. HOLD the earlier compact proposal `日本富士通盃` as a canonical display. |
| `jp` | PASS | `世界囲碁選手権・富士通杯` | Exact `棋戦名称` in the [Nihon Ki-in series archive](https://archive.nihonkiin.or.jp/match/fujitsu/), with organizer, sponsor, format and end after edition 24. |
| `ko` | PASS | `후지쓰배 세계 바둑 선수권 대회` | Exact 1994 championship wording in the [Korea Baduk Archive](https://archives.baduk.or.kr/archives/talk/view.asp?no=7). The same page also writes `후지쯔배` elsewhere, so this passes the chosen exact form, not a unique Korean orthography. |
| `en` | PASS | `The World Go Championship The Fujitsu Cup` | Exact `Tournament name` field and page title in the [Nihon Ki-in English archive](https://archive.nihonkiin.or.jp/match/fujitsu/index-e.html). The unusual doubled title is preserved as printed. |

The additional Traditional Chinese body is HTTP 200, `lang="zh-tw"`, captured `2026-10-02T20:14:15.004271Z`, 21,129 bytes, SHA-256 `743e90c89ec7bace32663d465f0983cf17f456274832bc9f2d79ec2520772ff0`. The five earlier body hashes remain in the source matrix and the packet. These PASS decisions concern exact display evidence only; the sources do not independently validate all 306 imported games.

## Frozen raw scope

The v4 compressed group **file** SHA-256 is `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`; the exact `富士通杯` group SHA-256 within it is `f3a23dd1bbec26c8e77ee4085923dfff1e055b729d0643e006073a8f85661cc0`. The matching frozen production inventory **file** SHA-256 is `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`, and its embedded snapshot SHA-256 is `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`. Exact inventory selection gives 54 distinct raw labels and 306 albums. Every label reconstructs byte-for-byte from its v4 edition/core/round parts; every album has a distinct `19x19` source path, a nonempty date, and `event_id = NULL` in the frozen inventory. No `round_name` is populated. These are one imported source family, not 306 independent confirmations.

The **52 `届` labels / 304 games PASS only finite structural decomposition**: editions 1–15 and 17–23, Arabic and Han numeral variants, one missing initial `第`, and first/second/third or Arabic-number round variants. For every one of these 304 frozen rows, the date year equals `1987 + edition`. Editions 16 and 24 have no exact member in this group; this is an inventory gap, not evidence that those championship editions did not occur. Round text in the event field is a source label, not an independently confirmed bracket stage.

The **two `期` labels HOLD** for shared grammar and identity. Album `127887`, `第五期富士通杯`, is dated `1991-11-21` although the fifth main edition corresponds to 1992; album `58726`, `第九期富士通杯`, is dated `1995-12-21` although the ninth main edition corresponds to 1996. Both have no round. A `REPEATABLE READ READ ONLY` production query of just these two album rows confirmed the same dates and showed their SGF root `GN` and `GC` merely repeat the imported label. They may be preceding-year qualification games, but the available source does not establish that. Do not infer `期 ≡ 届` or silently assign either game to the main championship.

## Protected packet and next gate

`~/.local/share/kifu-name-audit/2026-10-03/fujitsu-cup-five-independent-review-sol/review-packet.json` contains the six source references and hashes, all 54 per-label decisions, and the finite 306-row ID/date/source-path binding. SHA-256: `3e5630d9ab0b94fba595b905ee8f764f02481d41376ef0629f6f12d6f9bd34ed`; `SHA256SUMS` records it. Directory mode is `0700`, files `0600`.

Before any event identity or foreign-key approval, obtain provenance-aware confirmation of the `期` rows, independently match the intended main-event rows to event records beyond the imported `19x19` labels, and review the six remaining display languages. No code, SGF or database record was changed.
