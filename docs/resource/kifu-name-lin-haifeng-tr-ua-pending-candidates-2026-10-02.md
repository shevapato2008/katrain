# 林海峰 Turkish/Ukrainian pending candidate handoff

Prepared 2026-10-02 (UTC). This records two source-backed **pending** conventional-name rows. The independent source decisions are in [the Sol decision memo](kifu-name-lin-haifeng-tr-ua-sol-source-decision-2026-10-02.md), commit `94869363`. This work does not approve either row, bind the raw slots to this professional, enumerate game slots, or authorize any production write.

## Candidates and sources

| Language | Pending display | Registered source and directly observed passage | Identity check |
|---|---|---|---|
| `tr` | `Rin Kaiho` | `go-school-tr`, [İstanbul Go Okulu article](https://www.gookulu.com/cho_chikun/), captured HTTP 200, `html lang="tr"`: `... ancak o sırada Meijin olan Rin Kaiho’ya dokuzuncu Asahi en iyi 10 Pro turnuvasında kaybetmişti.` The authored Turkish account identifies Rin Kaiho as the then-Meijin and Cho Chikun's opponent in the ninth Asahi Best Ten Pro tournament. | [Nihon Ki-in profile](https://www.nihonkiin.or.jp/player/htm/ki000009.htm), captured HTTP 200, `html lang="ja"`: `林 海峯（リン カイホウ / LIN, Hai Fong）`; the profile identifies the Shanghai-born 9-dan and Go Seigen pupil. The cross-source match from the Turkish match/tournament context is an inference. |
| `ua` | `Рін Кайхо` | `ufgo`, [UFGO interview post 88623](https://forum.ufgo.org/viewtopic.php?p=88623), captured HTTP 200, `html lang="uk"`: `В основному це книги японських майстрів 80-х років - Рін Кайхо, Ісіда Йосіо, Кобаясі Коічі, Чо Чікун.` This Ukrainian answer names him among Japanese Go masters whose books the interviewee read. | The same Nihon Ki-in profile anchors a Japanese professional with the corresponding reading `リン カイホウ`. The forum passage itself has no biography details; the Go-book context supports, but does not independently prove, the match. |

Both rows preserve forms observed in the target language. No generated transliteration or Chinese-reading alternate was introduced. The raw source `林海峰` also belongs to a Hong Kong entertainer and other namesakes; the pinned inventory occurrence count is not an identity decision for its games.

## Private audit bundle and validation

All candidate materials and copied source bodies are in mode-`0700` directory `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lin-haifeng-tr-ua-pending/`; files are mode `0600`. `capture-manifest.json` records source timestamps, byte counts, status, target language and response hashes. No game-slot list or player/album link is included.

Pinned inputs:

- Production v2 inventory gzip SHA-256: `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`; internal inventory SHA-256: `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`. It contains 1,669 black/white occurrences of the exact raw value `林海峰`.
- Registry `.3` canonical SHA-256: `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61` (registry file SHA-256: `9e2016ac9675c44aa0bbdb304f8c5e1134a4a020d4d577c1c37890a813e0821b`). Both `go-school-tr` and `ufgo` are registered for these product languages. Their source scopes remain incomplete for negative claims.
- Turkish body SHA-256: `105318b1fb32210a591f013addf7af6b050df5c3a12d4a04f6ba9c2e0b1a8d36` (138,378 bytes).
- Ukrainian post 88623 body SHA-256: `38bb725493331508551abe8112e1f9af98591e50f9e66062e50a00b8abf06705` (84,507 bytes).
- Nihon Ki-in identity body SHA-256: `4fc1d68871389496bee83fac727cdcd4603fb6c38c420a1f388a5193182c0309` (41,842 bytes).

`kifu_name_research.py validate` passed for both pending research records using registry `.3`. Direct offline candidate validation through `name_candidates._validate_candidate` passed both rows against the pinned inventory and pending research hashes. This is individual-row/source validation only; no complete bundle or album-link scope was constructed.

| Private file | SHA-256 |
|---|---|
| `candidates.pending.jsonl` | `5bbd65a5f42a47b75f29984174fe0aed456e8d4171389b26650df97e72c13eba` |
| `research.pending.jsonl` | `69a8df0ca0899764744a2b7ed301b810b58370e22895b92c1dd922374c6b7beb` |
| `research.validated.jsonl` | `7943383c838a8295660ae2af081547ca6b2de841f66bf161e0160f637366e194` |
| `candidate-validation.json` | `82dd1b5a5c37d0944cb15e3f22447241360c0c81cd095ed483422e623443c1db` |
| `capture-manifest.json` | `f83c7a27df4e579c70621bbe9fba5946f56095a8d17a81ba92832a9f10dc564d` |

Both candidate rows remain `review_status: pending` without reviewer fields. No research-scope absence claim, slot-level identity binding, alias import, album association, or database write was made.
