# Park Junghwan (player 54): independent Turkish candidate review

Reviewer: `/root/park_tr_review`; reviewer model: GPT-6. Reviewed producer commit `3bd9193b` and its pending candidate/source memo. This is a source-level review only; no candidate production, candidate status change, registry edit, or database write was performed.

## Decision

**PASS — approve `Park Junghwan` as the source-attested Turkish-context conventional form for `player:54:tr`.** The controlled Merdiven archive body contains a Turkish-authored Go article whose heading links to the specific January 2017 post. Its Turkish prose says the Tygem Baduk server is Korea-based, then lists `Park Junghwan (9d)` among the high-level professional players faced by the Master(P) account. The spelling is exactly `Park Junghwan`; `(9d)` is the adjacent rank, not part of the candidate display.

The archive has no HTML language attribute, but the substantive article prose is plainly Turkish. Site navigation, archive furniture, and mixed site content do not supply the language determination. The captured page itself includes the article heading and permalink `https://merdivengo.blogspot.com/2017/01/tygem-sunucusundaki-gizemli-go-oyuncusu.html`, so the reviewed full-body context is sufficient for this source-level decision.

## Identity, source, and integrity checks

- The Korea Baduk Association profile body independently identifies `박정환 (朴廷桓)`, Korean affiliation, 9 dan, and birth date 1993-01-11. Captured body SHA-256: `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e`.
- The `.3` registry contains `merdiven-go-tr`, tier `reference`, language `tr`, with home URL `https://merdivengo.blogspot.com/`. The registry loader reports version `2026-10-02.3` and canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`, matching the research record.
- Controlled Merdiven archive body: 153,580 bytes; SHA-256 `d53b4c40f7cb06a8eca91decb4f9815624423ae61f9d07228b2b879fa6ed5101`, matching the source check and producer memo.
- Research record canonical SHA-256 is `4a8dbec5bbdf4fae1924c2d83623d9e5b7d3e6f82fd1fb44a45ad8a7fb721da1`, matching the pending candidate's `research_sha256`. Candidate display, owner, and language are `Park Junghwan`, player 54, and `tr`; decision kind is `conventional`, status remains `pending`.
- Re-ran `scripts/kifu_name_research.py validate` with registry `.3`; it succeeded, and the resulting normalized JSONL was byte-identical to the archived `research.validated.jsonl`.

The Merdiven post directly supports exact Latin-script usage in Turkish Go prose. The independent KBA identity anchor corroborates which Korean professional and rank the passage denotes. These sources are sufficient for this source-level pass; it does not establish an official Turkish naming standard or broad usage frequency. The pending candidate still requires the project's separate approval/import process.
