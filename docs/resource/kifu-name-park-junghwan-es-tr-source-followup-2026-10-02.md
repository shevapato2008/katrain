# Park Junghwan (player 54): Spanish and Turkish source follow-up

Producer: `/root/park_es_tr_sources` (`gpt-6`), 2026-10-02. Scope is limited to product languages `es` and `tr`. Identity anchor: the official [Korea Baduk Association profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000457) identifies `9단 박정환 (朴廷桓)`, Korean affiliation, and birth date 1993-01-11. Its captured body is archived at `/Users/fan/.local/share/kifu-name-player-top100-20261002/five-player-source-index/bodies/park_junghwan_kba.md`, SHA-256 `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e`.

The pinned source registry is `2026-10-02.3`, canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. No registry file was changed.

## Spanish (`es`): registered search found no positive name source

Targeted searches of current `.3` registered sources did not surface a positive Park Junghwan passage from AEGO (`aego`), Godokoro (`godokoro-es`), or Spanish Wikipedia (`wikipedia-es`). Queries included `site:aego.biz "Park Junghwan"`, `site:aego.biz "Park Jung-hwan"`, `site:godokoro.es "Park Junghwan"`, and `site:es.wikipedia.org "Park Junghwan" go coreano`. The existing captured [Spanish Wikipedia Go article](https://es.wikipedia.org/wiki/Go) is in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-player-54/bodies/es_go.html` (SHA-256 `ee1947947968f13de4105b6e6fb69b594e52539a43314aefa96f712ab6d71603`); it is Spanish but does not name this player. These are targeted checks, not an exhaustive scan or a negative closure.

Two Spanish target-language positives remain outside `.3`:

| Source | Name passage | Captured body |
|---|---|---|
| [Federación Chilena de Go, Go news page](https://igochile.cl/igochile2/noticias-de-go/) | `Park Junghwan 9p de Corea` in Spanish prose about professional Go. The page identifies the federation as Chile's Go organization. | `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-es-chile/igochile-noticias.html`; SHA-256 `97a893dde530d29ff5bee6e0b844382cd4e48d0e13e76ba32dda2daa014446de`; mode `0600`. |
| [Kifubara Spanish player page](https://kifubara.app/es/players/a42b2257-fad2-4fc5-b978-b76b607239ee) | `Park Junghwan (9p) - KR jugador pro de Go`. | `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-player-54/bodies/es_kifubara.html`; SHA-256 `597f7dbba7b38a35574c8021600c8d982282d180b69c15dcfa08ead40326c00e`; mode `0600`. |

The minimal `.4` addition to enable a registry-bound Spanish candidate is one source entry for the national Go federation: `{ "id": "chile-go-federation", "tier": "official", "language": "es", "home_url": "https://igochile.cl/igochile2/" }`. The positive page is already captured and directly supplies `Park Junghwan`; identity cross-check is the KBA profile above. Kifubara is corroborating only and need not be added for this candidate. This is a proposal only; no registry edit and no Spanish candidate row were made.

## Turkish (`tr`): pending conventional candidate from a registered local source

The registered Turkish Go blog [Merdiven's January 2017 archive](https://merdivengo.blogspot.com/2017/01/) links to the post [“Tygem sunucusundaki gizemli go oyuncusu bir yapay zeka mı?”](https://merdivengo.blogspot.com/2017/01/tygem-sunucusundaki-gizemli-go-oyuncusu.html). Its Turkish prose describes a Korea-based Tygem Baduk account and lists `Park Junghwan (9d)` among the professional players it faced. The candidate is the exact source spelling `Park Junghwan`; this is direct locally published Turkish-context usage, not an unsourced fallback. The KBA anchor independently matches the player's Korean identity and 9-dan rank.

The captured archive body is `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-player-54/tr-es-followup/bodies/merdiven_2017-01.html`, SHA-256 `d53b4c40f7cb06a8eca91decb4f9815624423ae61f9d07228b2b879fa6ed5101`, 153,580 bytes, mode `0600`; its parent directory is mode `0700`. The capture reports HTTP 200. This HTML has no page-language attribute, so I reviewed the captured full page and recorded `observed_lang: "tr"`, `language_basis: "reviewed_text"`; the project validator accepted that evidence.

Turkish targeted searches also checked `site:tgod.org.tr "Park Junghwan"`, `site:gookulu.com "Park Junghwan"`, and `site:tr.wikipedia.org/wiki "Park Junghwan" go`; these did not surface a better matching source. Since a registered target-language source produced a direct positive name use, this does not assert a complete search or absence elsewhere.

The current-registry research record and conventional candidate are archived privately:

- Research: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-player-54/tr-es-followup/research.jsonl`, mode `0600`; validated output: `research.validated.jsonl`, mode `0600`.
- Candidate: `candidate-pending.jsonl`, mode `0600`; display `Park Junghwan`, `tr`, `conventional`, status `pending`; its `research_sha256` is `4a8dbec5bbdf4fae1924c2d83623d9e5b7d3e6f82fd1fb44a45ad8a7fb721da1`.
- Research validation used `scripts/kifu_name_research.py validate --registry docs/resource/kifu-name-source-registry-2026-10-02.3.json`; it returned a valid pending record for `player:54:tr`.

This is a source-level pending candidate only. It contains no reviewer signature, production preimage/binding, album association, or authorization to write the database. The registry and database were not modified.
