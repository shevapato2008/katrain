# Honinbo v2 source evidence capture (2026-10-02)

Prepared a protected evidence package for the finite Honinbo v2 bundle work. It contains raw HTTPS response bodies and a per-raw-group manifest for all exact `1st Honinbo` through `34th Honinbo` groups. This package supplies evidence only; it does not approve any `identity_review` or authorize a database write.

## Protected outputs and hashes

Artifacts are in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-v2-source-captures/` (directory mode `0700`, files mode `0600`). Raw response bodies are under `https-captures/`.

- `honinbo-raw-group-evidence.json`: byte SHA-256 `c789ed607941d0a3a7631c22d04ed7badb555c58869c8e3ad8db79f0812227cf`. It maps all 34 raw values to exact excerpts from a retained CWI SGF member and the matching numbered rows in the official Japanese and CWI indexes. Each check records URL, fetched time, response-body SHA-256, excerpt, and identity match.
- `https-capture-manifest.json`: byte SHA-256 `30ae63734e2c4b51d553db72e561a741f34876d39be8487e36fbcb3dad1c301d`. It records requested/final URLs, HTTP status, fetch times, selected response headers, byte lengths, body hashes, and retained filenames.

Captured bodies (all HTTP 200):

| Source | Bytes | Response-body SHA-256 |
|---|---:|---|
| CWI `games.tgz` archive | 46,246,395 | `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad` |
| CWI Honinbo title-games index | 31,369 | `e04b9168fba2f1b6f06a032ca3afd1b36181c4ce7aeddd5ed970137e3265aac2` |
| CWI first-edition page | 11,769 | `31dbc1c1821f03393c488367fe128b6b8e893a40429ee0606e6c1e1a220104c7` |
| Nihon Ki-in Japanese historical record | 73,644 | `6b5227b19ea9d39cd14fb69984a868239851636f9f56d19977a5eac93408f07e` |
| Nihon Ki-in English archive | 26,108 | `24dca07baa1c8ef214566feb9d4a8a096f022a5f6fd1d8406bf8c115ed07ddc6` |
| Nihon Ki-in current event page | 295,850 | `d96c496abca1c292ad0814200cf4d66adb7a7ed233347934a1a4bce11eda6f26` |

## What the captures support

The captured CWI index says it gives title games for the Honinbo (`本因坊`) title. The Nihon Ki-in English archive labels the tournament name `Honinbo Title`; its Japanese historical page is titled `本因坊戦 歴代記録`. The current Nihon Ki-in page has the field `創設年 | 1939年`. CWI's first-edition page states: `The 1st Honinbo Tournament started in June 1939 with 27 players.`

For each raw group, the CWI archive member has a root `EV` exactly matching that raw label. The captured official Japanese historical table and CWI index both give the matching edition number and year. The official table uses `対局年`; it lists `1期 | 1941` and `34期 | 1979`. Thus the series began in 1939, the first title match was in 1941, and the 34th title match was in 1979. These dates are kept distinct from the SGF game dates.

I independently extracted all 1,617 archive paths from the pinned link-prep input against the newly retained CWI tar response. All 1,617 member hashes and SGF root `EV` and `RO` values matched the prepared rows; there were 34 raw groups and 1,616 distinct archive members, with zero mismatches. The link-prep input file SHA-256 is `ce1aded31526c047abc9ac44bff2a43921d0dd3b6c286082801d20ea1168a584`; its declared canonical link-set SHA-256 is `d77b853f0394880dd5be20d512610540ba79d88792b701f21f9461f97a6a35d2`. The pinned inventory file SHA-256 is `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`; its internal inventory SHA-256 is `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`.

## Scope and handoff

The CWI tarball is a game collection, not an official event record. Its root `EV` values establish the captured source labels; the official Japanese table and CWI title-games index corroborate the edition number and period. The per-group evidence does not independently establish each production game's identity or certify every link. Adjacent Honinbo-like raw groups remain outside this capture.

The existing bundle draft froze empty `source_checks` at `2026-10-02T14:22:12Z`. These responses were fetched later, beginning at `2026-10-02T14:39:36Z`. After attaching the checks and updating each group's identity and period basis, set a new freeze time later than the evidence captures and recompute all 34 identity-scope hashes. The earlier hashes are not approvals and must not be reused. An independent reviewer still needs to inspect the retained bodies and sign each exact group using their actual reviewer identity and model. No database, SGF, signed candidate, existing document, or prior bundle was changed; no commit was made.
