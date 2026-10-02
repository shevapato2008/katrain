# `段位赛` / `个人赛` finite root-SGF audit — 2026-10-02

**Result:** 622 exact-label albums have no conflicting fuller title in their captured root properties and form a finite **candidate** set for independent generic-display review. The other 917 albums remain HOLD: 54 show a fuller named event title in the second `GN`, and 863 have differing year/other wording that should not be discarded. This is a source-property partition, not a tournament-identity or eleven-language approval. No production write, code change, candidate signature, or event mapping was made.

## Capture and integrity

Using the frozen production v2 inventory's exact `event` values, I read `katrain_prod_20260725.public.kifu_albums` on `ucloud-v100` in **one `REPEATABLE READ READ ONLY` transaction** at `2026-10-02T15:30:05.318708+00:00` (PostgreSQL snapshot `1595244:1595244:`). The query returned **1,539 distinct album IDs**: `段位赛` 901 and `个人赛` 638. For every row, I captured current ID, duplicate marker, raw players/ranks, event, round, date, `event_id`, source/source path and SHA-256 of `sgf_content`. I parsed the SGF **in memory** with `katrain.core.sgf_parser.SGF.parse_sgf` and retained only root `EV`, ordered `GN`, and `GC` properties. No SGF body or moves were written to the manifest.

The entire current member set and the captured preimage fields match the frozen inventory: same 1,539 IDs, exact event values, players, ranks, dates, rounds, duplicate markers and `event_id`; each production source path matches its protected inventory source link. All `event_id` and duplicate markers are null. The frozen inventory's internal SHA-256 is `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`; its compressed-file SHA-256 is `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`.

All 1,539 SGFs parsed successfully. Every root has **no `EV`**, exactly two `GN` values with `GN[0]` equal to the stored generic `event`, and one `GC` value that begins with `GN[1]`. This directly reproduces the earlier [duplicate-`GN` audit](kifu-name-duplicate-gn-data-audit-2026-10-02.md): the second value differs for 891/901 rank rows and 26/638 individual rows. Source-path provenance is the `19x19` import; the path and SGF self-consistency do not independently verify a historical event identity.

## Conservative per-game partition

| Exact stored value | Only repeated generic `GN` and simple `GC` — candidate | Explicit fuller named second `GN`, supported by `GC` | Different year/other second `GN` — ambiguous HOLD | Total |
|---|---:|---:|---:|---:|
| `段位赛` | **10** | **42** | **849** | **901** |
| `个人赛` | **612** | **12** | **14** | **638** |
| **Total** | **622** | **54** | **863** | **1,539** |

- **Generic-root candidates:** exactly `GN[raw][raw]`, no `EV`, and `GC` contains only that repeated label followed by result and move count. Examples: rank album `105733` and individual album `36444`. These are eligible for an independent generic-description decision only; a short label could still be source shorthand for a named competition.
- **Fuller named title:** rank second `GN` contains `全国围棋段位赛` or `中国棋王战` (42 rows); individual second `GN` contains `全国围棋个人赛`, `全国个人赛`, or `一洲杯` (12 rows). Every `GC` begins with that second title. Examples: rank `36514` has `第2期全国围棋段位赛升段组第8轮`, rank `36701` has `第1届中国棋王战第1轮`, and individual `36453` has `一洲杯全国围棋锦标赛个人赛男子组第6轮`. None can receive the bare generic display simply from the stored first `GN`; title, edition, group and round require their own later review.
- **Ambiguous fuller wording:** 848 rank and 14 individual second values are a year plus the generic label, such as rank `27998`: `1993段位赛`, and individual `36719`: `1993个人赛`. One further rank row, `95616`, has `1998年中国段位赛第2轮`. All are held: even a year-only addition is source information, and the latter also adds country/round. A dated generic phrase is not enough to infer one formal series, nor is it safe to replace it with the undated template.

For this partition, “fuller named” means an **explicit lexical title in the SGF**, not external historical confirmation of a series or edition. No malformed or parser-conflicting rows appeared, but the ambiguous bucket remains a real hold. The 622 candidates have no *root-property* conflicting title; they are not approved display rows.

## Protected finite artifacts and next boundary

- Full protected per-row manifest: `~/.local/share/kifu-name-audit/2026-10-02/generic-1539-root-sgf/root-properties.jsonl`; **1,540 JSONL records** (one capture header plus 1,539 album rows), 1,002,164 bytes, SHA-256 `7fe3e9b3fda13afe66fd32a94616c4ba338a2ba9d6b6a326470d3dca00a4929e`. Each album row includes its partition, captured SGF hash, source path/context, and root EV/GN/GC values. Directory mode `0700`; file mode `0600`.
- Exact candidate IDs with individual SGF hashes/source paths: `~/.local/share/kifu-name-audit/2026-10-02/generic-1539-root-sgf/generic-exact-candidate-ids.json`; **10 rank + 612 individual IDs**, 93,870 bytes, SHA-256 `8ded14d92bbb5f8441b183fb325843d244892f183a22d0f7d1797030173f1451`; mode `0600`. This is the finite root-safe review queue, not an approval or import payload.

An independent reviewer can start with those 622 IDs, verify that the displayed generic wording does not hide a known named competition, and review the relevant eleven-language templates. The 54 explicit-title rows need effective-event selection and title/structure review; the 863 differing generic/year rows need separate disposition. The original [independent lexical review](kifu-name-rank-individual-independent-review-2026-10-02.md) remains correct that **global 1,539-row generic import is HOLD**. Any later write must bind current per-row preimages and SGF hashes again; this read-only capture alone authorizes none.
