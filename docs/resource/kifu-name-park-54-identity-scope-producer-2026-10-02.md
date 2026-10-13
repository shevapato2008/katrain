# Park Junghwan player 54: identity-scope producer audit

Captured 2026-10-02 by `/root/park_54_identity_scope_luna`, assigned model `gpt-6-luna` (the worker could not independently inspect the serving runtime). This is a read-only producer audit for a later independent identity reviewer. It approves no names-to-game associations and authorizes no database write.

## Scope and snapshot

I used the frozen production inventory at `/Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-name-inventory-prod-v2-20261002.json.gz` (compressed file SHA-256 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`; canonical inventory SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`; snapshot time `2026-10-01T18:11:45.460901Z`). The inventory has 173,025 albums. It is a frozen snapshot, not a live read.

Exact `朴廷桓` appears in 1,526 album-side slots: 755 Black and 771 White. Every row is from source ID 1, dataset `19x19`, match method `source_path`; all 1,526 source paths are distinct. Dates range 2007-06-11 through 2026-01-24; there are 1,380 distinct event strings. Existing `black_player_id`/`white_player_id` fields are null for all 1,526 target slots, so the inventory does not show these already linked to player ID 54.

I read all 1,526 SGFs from `home-ubuntu:/home/fan/Repositories/katrain/data/kifu-album/19x19/` into the controlled evidence directory. All files parsed. Each SGF root has `朴廷桓` in the inventory-recorded color; each SGF date equals its inventory date; each SGF opponent equals the other inventory player. There are 1,518 unique mainline digests, with eight repeated-mainline pairs (16 rows); these pairs repeat the same game under differently formatted opponent/event metadata and should be treated as duplicate game contexts during review, not counted as 16 independent match witnesses.

## Independent professional-game index comparison

The independent index is GoRatings’ Park Junghwan profile and game list: <https://www.goratings.org/en/players/1090.html>. The captured page returns HTTP 200 and contains 1,561 dated games from 2007-05-02 through 2026-09-30. Its game entries provide date, Park color, W/L result, opponent, and, for most entries, a Go4Go game link. The profile also links professional identity sources; the Korean Baduk Association player record is <https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000457>.

I matched each inventory SGF against the profile using exact date and Park color, then compared the SGF winner to the profile result. This is a screening comparison, not a full game match:

| Classification | Slots | Treatment |
|---|---:|---|
| One profile row on exact date and color; SGF winner agrees with profile W/L | 1,385 | Priority candidate scope for independent identity review; no auto-approval |
| Multiple profile rows share exact date and color | 42 | Hold: date/color does not uniquely select an indexed game |
| No profile row shares exact date and color | 89 | Hold: no indexed date/color match |
| Unique date/color row, result missing, draw, or contradictory | 10 | Hold and resolve against the game record |

The ten unique-date/color exceptions are: album `1425` (2023-02-10, profile Loss versus SGF draw); `3113` (2023-08-03, SGF result absent); `19431` (2025-06-23, SGF result absent); `34519` (2013-06-23, profile Loss versus SGF `W+R`); `45840` (2013-04-11, SGF result absent); `60290` (2013-03-06, profile Win versus SGF `B+R` while Park was White); `61243` (2020-08-20, profile Loss versus SGF Draw); `103835` (2011-07-12, SGF result absent); `113443` (2022-06-01, profile opponent Kang Dongyun differs from SGF opponent 刘兆哲, and profile Loss conflicts with SGF `B+5.5`); and `122369` (2011-10-19, SGF result absent). Album `1426` on 2023-02-10 is a same-date/same-opponent record whose White loss agrees with the profile; review it alongside `1425`, whose SGF is marked draw.

The 1,385 rows are only candidate scope for human review. Date, color, and result corroboration do not prove that the exact source SGF is the exact professional game, particularly where opponent names have not been reconciled across scripts. The eight repeated-mainline pairs should be collapsed as game contexts for reviewer workload while retaining both album slots in any eventual finite proposal.

## Full-mainline match availability and limits

I parsed each source SGF’s first-child mainline and recorded the move count, complete canonical move sequence, its SHA-256, and the original SGF-byte SHA-256. **No external full-mainline match was established (0/1,526).** GoRatings supplies a game index and links, but the linked sample Go4Go SGF page `https://www.go4go.net/go/games/sgfview/104124` returned HTTP 500 (“Service unavailable (with message)”) for both `www` and bare-host URLs during capture. I therefore did not treat its index entries as move-sequence confirmation.

GoMagic lists a “Park Junghwan SGF Pack (1440 games)” at <https://gomagic.org/ja/download/park-junghwan-sgf-pack-1440-games/>; its landing page marks the download subscriber-only. I did not access a gated download. Thus an independently keyed full-SGF archive exists in principle, but an accessible copy was not available in this audit. Full-game match coverage remains unmeasured; it is not zero true matches.

## Controlled evidence and hashes

All row-level game evidence and captures are outside the repository under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-identity-work/`, directory mode `0700`; files below are mode `0600`.

| Artifact | SHA-256 | Contents |
|---|---|---|
| `park-54-full-row-evidence.jsonl` | `602c6ccc9dc2746e47ffc055b110a6854882d75fa5d5f08447a5385d11fa6960` | 1,526 rows with inventory metadata, SGF-byte hash, complete mainline, mainline hash, profile matches and screening disposition |
| `source-sgf-sha256.manifest` | `0dd6ac54c1f1a55eb8d5ba8242d7fa026fbcc68c47d8a2609fef19c709d17152` | Per-file SHA-256 for all 1,526 copied source SGFs |
| `goratings-park-profile.html` | `95f9c260308f6ce85ba79f9ac076feb42d2d634f3113abe4c04234979759ae68` | Raw GoRatings profile response, 894,369 bytes |
| `goratings-index.jsonl` | `78fdc8b857685c8f8bb5aaeb28a3a9e93859691a41bd02236508342e6332ff85` | Parsed 1,561 profile game-index rows |
| `gomagic-pack-landing.html` | `fd2003e1468d5373afa9ede1ef98a2d9db7e88e88a29c6c0eb861adb8831f48a` | Raw GoMagic pack landing response, 344,630 bytes |
| `external-access-checks.json` | `c01d526e67ce519ec3eb88e64b81de024abda825bc7cbecff859658dc4567567` | Captured Go4Go response failures and tested URLs |

Repository evidence reviewed for the identity/name context includes `docs/resource/kifu-name-park-junghwan-11lang-research-2026-10-02.md`, `docs/resource/kifu-name-park-junghwan-independent-review-2026-10-02.md`, and `docs/resource/kifu-name-player-five-source-index-2026-10-02.md`. Those name-source decisions remain separate from this exact-slot identity scope.
