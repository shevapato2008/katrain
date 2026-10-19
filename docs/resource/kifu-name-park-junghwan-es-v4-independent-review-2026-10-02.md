# Park Junghwan (player 54): independent Spanish source review

**Source-level result: PASS.** Reviewer `/root/park_es_v4_review`, actual model disclosed as `GPT-6`; reviewed 2026-10-02 at 05:04 UTC. This review covers the producer memo from `c15bc76a`, registry `.4` from `bcab519e`, the retained evidence, and the pending research/candidate bindings. It does not approve the player-name link or authorize any database write.

## Evidence checks

- The retained recapture at `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-es-chile/igochile-noticias-recapture.html` is 153,135 bytes with SHA-256 `97a893dde530d29ff5bee6e0b844382cd4e48d0e13e76ba32dda2daa014446de`. It is byte-identical to `igochile-noticias.html`. Both are mode `0600`; the evidence directory is `0700`.
- `recapture-metadata.json` is mode `0600`, SHA-256 `f6fa28ad518832cd943c27f72c5f742ea5dd137060e6fcfa9e7d2093a51aa3cb`, and records the matching URL and resolved URL, HTTP 200, `text/html; charset=UTF-8`, byte count, body hash, and fetch time `2026-10-02T05:00:20.141854+00:00` after request start `05:00:18.635183+00:00`.
- The retained HTML declares `<html lang="es-CL">`. Its 25 July 2021 article, “Dentro de la Liga A china,” contains the exact Spanish passage `Park Junghwan 9p de Corea`. At the end of that same article, it says `(Fuente: AGA)` and links the original Go report. A live page check at the exact retained URL confirmed the same passage, date, and attribution. The evidence therefore supports published Spanish use while preserving that the Chilean page republishes AGA material.
- The retained KBA identity body `park-junghwan-player-54/bodies/kba_identity.md` is 11,700 bytes and hashes to `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e`, matching its earlier capture manifest entry. It identifies `박정환 (朴廷桓)`, Korean 9-dan, born 1993-01-11. This independently supports the identity match for the Spanish report’s Korean professional Go context.

## Registry and artifact checks

- Registry `.4` recomputes to canonical SHA-256 `b2d0b2fd65ce22b036e0160574301d954545450638edadf3981d1d53faf7a34c`, matching the producer memo. Relative to `.3`, the sole source addition is `chile-go-federation` at tier `language_go`, language `es`, home URL `https://igochile.cl/igochile2/`. It is the only addition to the Spanish required-source list; all prior entries remain. Every `complete_for_negative_claims` value remains `false`.
- The research file is 1,356 bytes, SHA-256 `a824f1bedb9233ef1da3674f328db2df89692de93471ff50ea962fc45e63bce0`; its canonical record hash is `e8e555755679f4c421426435757f39cf852a4f87b31173f3fb689cdc22db916d`. `scripts/kifu_name_research.py validate` exits 0 against `.4` and returns owner key `player:54:es`, `scope_status: found`, and `review_status: pending`.
- The candidate file is 350 bytes, SHA-256 `a2388ad7b5008a8fe35cb92649394cf6211a8bedca993176c1e5d2694808a173`. Its `research_sha256` matches the canonical research record. `_validate_candidate` accepts it as a pending conventional candidate when supplied the explicit schema-only owner context `{player: {54}, event: {}, raw_player: {}, raw_event: {}}`; that isolated context validates the candidate schema and is not evidence of production inventory membership.

The source and artifact checks pass. The record remains pending for an independent name decision and all separate identity-binding, inventory/preimage, alias-conflict, batch, and database-write gates. No production database or name link was inspected or changed as part of this source-level review.
