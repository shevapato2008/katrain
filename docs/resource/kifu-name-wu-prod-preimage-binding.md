# Wu player ID 1: production preimage binding

Bound 2026-10-02 by `/root/wu_preimage_binder` (`gpt-6.1-sol`). This mechanical step creates new pending copies for independent review. It does not approve names or write to the database.

The mode `0600` capture `wu-name-preimages-prod-20261002.json` has file SHA-256 `b1008149c2163938e31822119e38f5e5425b973517073a6aeb4a4f1ba605ea7b`. Its owner is `player:1`, database is `katrain_prod_20260725`, and capture code SHA `4de9e9f30090` resolves to commit `4de9e9f30090ab20c9556c38800ce61dd21bdf39`. All eleven product languages are present. Capture time is `2026-10-01T20:22:44.345508+00:00`; binding time is `2026-10-01T20:31:11.818551+00:00`.

Artifacts remain under the access-controlled local audit directory `/Users/fan/.local/share/kifu-name-audit/2026-10-02/`:

| New pending artifact | Rows | File SHA-256 |
|---|---:|---|
| `wu-v4-prod-bound-v2-candidates.jsonl` | 9 | `26b3b4efd93d832b313bac38427bb8fe82b31dc8a3b447b78771e7b8b70a259c` |
| `wu-v4-prod-bound-v3-candidates.jsonl` | 2 | `58dffccdb62f878f06bc3ad99ed2898e2c43cf77bfc4fffb6cd0cb691798b9ac` |

Each row adds the captured top-level `name_preimage_sha256` and a `preimage_binding` object recording the binder, capture/binding times, the same preimage, capture file hash, and canonical SHA-256 of the exact original candidate row. Missing name rows use explicit `null` (`ko`, `tr`, `ru`, `es`, `ua`). All eleven rows are `pending`; the nine prior review signatures are removed. Producer identity, model, production time, research hash, display decision, exclusions, and Ukrainian conflict adjudication are preserved exactly.

Reloaded files have mode `0600`. All eleven rows pass `validate_candidate` with their original evidence and immutable [`.2`](kifu-name-source-registry-2026-10-02.2.json) / [`.3`](kifu-name-source-registry-2026-10-02.3.json) registries, whose canonical hashes remain `e2ed3cafa9b6f32d8ba30c78aecdf9667801df3cf34745227e5da588e98dd58e` and `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. The pinned production inventory file SHA-256 remains `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`.

Original candidate file hashes remain `463791f295758fc9b24c9b3c4a5c5e7af0705bb63e4b099dd7e07451d883259e` (nine rows) and `d09098933c1d821fdc1262b02eac21a18f248a99175245a4fa882f7248a22e49` (two rows). Evidence, registries and capture bytes were also checked unchanged. Independent reviewer signatures must be made on these newly bound pending copies before batch assembly.
