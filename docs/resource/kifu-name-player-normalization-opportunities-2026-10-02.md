# Player name normalization opportunities

Read-only analysis of the pinned production inventory and the current conservative parser. Counts describe raw album associations, not confirmed people. A normalized base name is a review aid only: it does not establish identity, approve a translation, or authorize merging records.

## Snapshot and method

- Inventory: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-name-inventory-prod-v2-20261002.json.gz`
- SHA-256: `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`
- Inventory reports 173,025 games, 173,016 visible games, and 8,651 sampled games. The association list has one row per game and columns in `association_columns` order.
- For every row, counted non-null `player_black` and `player_white` strings as separate occurrences, then passed each raw value and its corresponding `black_rank`/`white_rank` to `katrain.web.kifu.name_parse.parse_player`. Distinct raw spellings and normalized base names are exact string counts; normalization here means only the parser’s current terminal Chinese numeral + `段` extraction and outer whitespace trim.
- Reproduce from the repository root:

  ```python
  import gzip, json
  from collections import Counter
  from katrain.web.kifu.name_parse import parse_player

  path = "/Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-name-inventory-prod-v2-20261002.json.gz"
  data = json.load(gzip.open(path, "rt", encoding="utf-8"))
  ix = {name: i for i, name in enumerate(data["association_columns"])}
  raw, bases = Counter(), Counter()
  for row in data["album_associations"]:
      for name_col, rank_col in (("player_black", "black_rank"), ("player_white", "white_rank")):
          value = row[ix[name_col]]
          if value is not None:
              parsed = parse_player(value, row[ix[rank_col]])
              raw[value] += 1
              bases[parsed.name] += 1
  print(len(raw), sum(raw.values()), len(bases), sum(bases.values()))
  ```

## Counts

| Measure | Count |
| --- | ---: |
| Non-null player-side occurrences | 346,050 |
| Distinct raw player spellings | 7,251 |
| Distinct parser output base strings | 6,433 |
| Raw spellings merged by current rank parsing | 818 fewer distinct outputs (11.3% of raw distinct count) |
| Occurrences classified `readable_unlinked` | 342,496 |
| Occurrences classified `placeholder` | 3,515 |
| Occurrences classified `corrupt_pending` | 39 |
| Parser exceptions `invalid_explicit_rank` | 5,221 |
| Parser exceptions `rank_conflict` | 1 |

The 3,515 placeholder occurrences are `Black` (1,158), `White` (1,158), `Unknown` (1,198), and `?` (1). The 39 corrupt occurrences use 25 distinct raw strings; 31 include malformed fragments beginning `崔珪昞]`, with other examples including `伊藤誠]BR[九段` and `钘ゆ辰绉�琛宂WR[8p`. They become an empty base name under the current parser, so they must not be treated as a shared person cluster.

## High impact rank parsed clusters

These are the largest current base-name buckets with more than one raw spelling. Variants commonly mix an unranked spelling with one or more rank-suffixed spellings. The counts are useful for prioritizing review burden only; they do not assert that each variant refers to the same person.

| Parser base | Occurrences | Raw spellings | Examples of raw variants |
| --- | ---: | ---: | --- |
| 李昌镐 | 2,199 | 9 | `李昌镐` (2,140), `李昌镐九段` (36), `李昌镐七段` (7), full-width-space + `九段` (2) |
| 赵治勋 | 2,065 | 5 | `赵治勋` (2,052), `赵治勋九段` (10), `赵治勋七段` (1) |
| 曹薰铉 | 1,970 | 3 | `曹薰铉` (1,937), `曹薰铉九段` (31), full-width-space + `九段` (2) |
| 林海峰 | 1,690 | 5 | `林海峰` (1,669), `林海峰九段` (15), `林海峰七段` (3) |
| 小林光一 | 1,644 | 4 | `小林光一` (1,630), `小林光一九段` (10), `小林光一八段` (3) |
| 朴廷桓 | 1,540 | 3 | `朴廷桓` (1,526), `朴廷桓二段` (11), `朴廷桓九段` (3) |
| 李世石 | 1,443 | 3 | `李世石` (1,405), `李世石九段` (35), `李世石三段` (3) |
| 依田纪基 | 1,396 | 5 | `依田纪基` (1,385), `依田纪基九段` (6), `依田纪基八段` (3) |

Rank changes over a career explain some suffix variety, but confirming that explanation for any row requires independent evidence. Likewise, same-base outputs may conceal genuinely different people.

## Ambiguous and corrupt cases

- **Different rank data and rank-like name suffixes:** parser currently preserves explicit rank text and reports conflict only for a detected embedded Chinese rank. Among the 5,221 invalid explicit-rank cases, some data may be descriptive text or titles rather than rank. No blanket cleanup is safe.
- **Terminal Arabic numeral + `段`:** 15 distinct raw strings (17 occurrences) look like possible terminal rank suffixes not extracted today. Examples include `唐韦星7段` (2), `朴廷桓7段`, and `洪奭羲6段`; one candidate is malformed comma-separated text (`小林光一,九段,十段`) and one contains multiple full-width spaces (`叶　畅　5段`). This is a small, bounded parser opportunity, but each candidate should be retained in raw form and exposed with a parse exception when malformed.
- **Full-width and repeated whitespace:** collapsing whitespace runs would affect 87 distinct spellings / 115 occurrences, but most of those are not proven player-name equivalences. The current parser already tolerates whitespace between a name and Chinese rank while retaining internal whitespace in the base name.
- **Composite historical descriptions:** 191 spellings / 822 occurrences contain punctuation such as commas, ampersands, or parentheses. Many are lists, multi-player descriptions, or notes (for example historic relay/team game descriptions), not one player name. They should remain unlinked instead of being split or normalized into identities.
- **Overlong values:** 81 spellings / 86 occurrences exceed 40 characters. This is a useful review flag, not evidence of corruption by itself.
- **Unicode folding and transliteration:** NFKC, simplified/traditional conversion, romanization, and character substitutions can collapse distinct spellings and are outside safe parser normalization without reviewed, source-backed mappings.

## Highest value next changes

1. **Extend only the terminal rank grammar for unambiguous Arabic `1`–`9` + `段`.** Keep the raw value, extract the suffix into rank metadata, and add focused fixtures covering valid suffixes, internal spaces, title-like `十段`, comma-separated text, and conflicting explicit rank. This addresses 12 observed spellings (13 occurrences) while making no identity claim.
2. **Add a conservative whitespace quality flag, not a global canonicalization.** Report values with repeated or unusual Unicode whitespace and let review distinguish formatting variants; preserve the base string until a narrowly specified rank suffix is removed. There are 87 spellings / 115 occurrences to inspect.
3. **Make corrupt and composite values easier to route for review.** The existing bracket-fragment rule catches 39 occurrences. Add a separate diagnostic for very long or list-like SGF player values, but leave them raw and unlinked; 81 spellings exceed 40 characters and 191 include list punctuation. Do not split composite values automatically.

No identifiers were connected, no translations were assigned, and no database or parser code was changed.
