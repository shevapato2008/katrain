# Wu player 1: production-bound Spanish/Ukrainian approval

Independent reviewer `/root/wu_es_ua_review_astra`, actual configured model `gpt-6-astra`, signed at `2026-10-01T20:34:42.281354+00:00`.

| Language | Decision |
|---|---|
| `es` | **approve** `Go Seigen`, `conventional` |
| `ua` / source `uk` | **approve** `Ґо Сейґен`, `conventional`; retain genuine `Го Сейген` alternative for alias planning |

This review resolves the missing-preimage blocker in the [historical `.3` review](kifu-name-wu-es-ua-v3-review.md). The original candidate file remains unchanged and pending. Only the new mode `0600` file `wu-v4-prod-bound-v3-candidates.jsonl` was signed; no database writes occurred.

I compared every source field with the archived original candidates: producer, production time, research hash, display, exclusions and Ukrainian conflict adjudication are unchanged. Canonical source-candidate hashes are `6e95eb8c2b190592b94f4366c2602ff4c6cc6d6c8f416bd1593b8ad11173a2c7` (`es`) and `f61c8952814bd8e7d18d2f4a8380b6a494649390638fa085e05656f6455d9500` (`ua`). Both equal their binding references.

The actual capture file hashes to `b1008149c2163938e31822119e38f5e5425b973517073a6aeb4a4f1ba605ea7b`. Its owner is player 1, production database matches the migration record, and code `4de9e9f30090` resolves to `4de9e9f30090ab20c9556c38800ce61dd21bdf39`. Both language preimages are explicit `null`. I independently queried production in a read-only transaction immediately before signing: player 1 is `Go Seigen`, and neither `es` nor `ua` has a name row. The transaction was rolled back.

Binder `/root/wu_preimage_binder` (`gpt-6.1-sol`) differs from producer `/root/wu_es_ua_sol` (`gpt-6-sol`) and this reviewer. Source production at 19:56 UTC precedes capture at `20:22:44.345508+00:00`, binding at `20:31:11.818551+00:00`, and the new signature. Source capture/conflict chronology and all found-source URLs retain the previously verified ordering and exact values.

The evidence file, research hashes, pinned inventory and immutable `.3` registry retain all pins from the historical review. Its independent raw-body, fixed-revision, actual-language and identity checks continue to apply to these unchanged bytes. The UFGO alternative remains a genuine Ukrainian use, excluded only from primary display, not rejected as an error; this approval does not create an alias row.

After signing and reloading the file, both `validate_candidate` checks and an exact two-member offline `validate_bundle` check passed: `approved=2`, `pending=0`, `ready=true`, `write_ready=true`, no evidence or write errors. This validates only these two existing-player name decisions. It does not authorize production import, replace import-time preimage checks or establish full-catalog coverage.

| Controlled candidate file state | SHA-256 |
|---|---|
| Original historical `.3` file | `d09098933c1d821fdc1262b02eac21a18f248a99175245a4fa882f7248a22e49` |
| New production-bound file before review | `58dffccdb62f878f06bc3ad99ed2898e2c43cf77bfc4fffb6cd0cb691798b9ac` |
| New production-bound file after signatures | `5aab0e1dc3c0e0e8428d08ae8674461ec271a9eb803ef6f41acde83e73c094ae` |
