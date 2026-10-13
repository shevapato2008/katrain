# Judan 十段戦 controlled positive research (2026-10-02)

This memo records ten **pending** positive name-research rows for `event:@judan-series-2026-10-02`, original name `十段戦` (`ja`). It excludes Ukrainian, whose positive source candidate is recorded separately. The rows contain no reviewer signature and approve no catalog identity, candidate write, or album link.

The protected capture set is `/Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ten-controlled/` (directory mode `0700`, files mode `0600`). It contains `research.pending.jsonl`, the validator output `research.validated.jsonl`, `capture-manifest.json`, raw target-language HTML/PDF bodies, and the manually reviewed German page text. Wikipedia checks use pinned revisions; their article evidence is paired with a separately registered Nihon Ki-in Japanese identity capture (`十段戦`, 64th-edition page, HTTP 200, body SHA-256 `8fbcb6874cb91b68fb9af0edbc548fcee8a6ca94686f51f37c4705439da10d78`).

| Language | Pending exact form | Captured source | Body SHA-256 |
|---|---|---|---|
| `en` | `Judan Title` | Nihon Ki-in English history article, headline “Judan Title Match” | `b60ba9a5d2d24f02f1daf218cf586d263cab83b93e5b27a03ce3006c8e61af35` |
| `cn` | `十段战` | Wikipedia, revision `92446810`, Simplified rendering | `b4ab9a0849dc6956af3417ba94cc8fab884d1f8d9728f49f31818c04a2dbf99e` |
| `tw` | `十段戰` | Wikipedia, revision `92446810`, Taiwan Traditional rendering | `109b8c816efbe1d80e1ce4a396a6dabbc4c450d455a98cd532c33016d8fb380d` |
| `jp` | `十段戦` | Nihon Ki-in, 64th-edition page | `8fbcb6874cb91b68fb9af0edbc548fcee8a6ca94686f51f37c4705439da10d78` |
| `ko` | `일본십단전` | Korea Baduk Association, Iyama Yuta player record | `7055f612296b446ad305817c5e0c63ca174029983de7334fd972abf0809568ca` |
| `de` | `Judan-Turnier` | Deutsche Go-Zeitung 1/2020, PDF page 47 | `b9775be1294b1f90dd36f661756a0c7c017cf5d4543a0978f20fd10ec6a8ee1e` |
| `es` | `Judan` | Wikipedia, revision `170927155` | `54e8d2cfc62f19a34072909849c1ff6bdb72f5e8ac6b539e20d37843f8267f49` |
| `fr` | `Judan` | Wikipedia, revision `236253769` | `05bef40ac28618e4b8db46cc80cef7d47d31886ae86dd94fa6b52240269f7458` |
| `ru` | `Дзюдан` | Wikipedia, revision `121059529` | `cccf5ceecce7cbf21685d1eba2e5628ae6d1e7f41495708402fa8766375b7c52` |
| `tr` | `Judan` | İstanbul Go Okulu, Cho Chikun history | `105318b1fb32210a591f013addf7af6b050df5c3a12d4a04f6ba9c2e0b1a8d36` |

The German text was manually extracted from PDF page 47 and retained as `source-bodies/de-page47-reviewed.txt`; its UTF-8 text SHA-256 is `8b6f67653e73e0b72e8dcfd84130271029b162620d100b25de7cb787d7bb9588`. The Russian and Chinese/Taiwanese Wikipedia bodies contain the tournament/organizer distinction; the French body calls Judan a Go tournament and names the Japanese organizers. The Korean record explicitly uses `일본십단전` for Iyama's 50th Japanese edition, distinguishing it from Korea's Siptan by the `일본` qualifier. The Turkish page uses `Judan` in numbered Japanese preliminaries/finals.

The English capture is a registered-host Nihon Ki-in history page whose headline contains `Judan Title Match`; it does not expose the archive's formal `Tournament name` field. The pending row preserves this source wording and the separately captured Japanese identity so an independent reviewer can assess that limitation. No name was silently upgraded from a prior decision.

Canonical registry SHA-256: `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`.

- Pending JSONL byte SHA-256: `aa05964480bf56b4b4ea880651e8ccacba7854ddd3d6077b0f13341ee2ee52ca`
- Capture manifest byte SHA-256: `9719beaf4528895aeca204caac0e51f5dd71ff65b94a8605aaa9e200618ecc64`
- Validated JSONL byte SHA-256: `2f1f8316ea5bb1f0d0b72e1546575e9b08160ceeb41698e50eb05e73acd9d63f`

Validation completed successfully with:

```sh
python scripts/kifu_name_research.py --registry docs/resource/kifu-name-source-registry-2026-10-02.5.json validate \
  --input /Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ten-controlled/research.pending.jsonl \
  --output /Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ten-controlled/research.validated.jsonl
```

All ten validated rows remain `pending`. The producer is recorded as parent-configured `gpt-6-luna` (high reasoning); runtime model identity is not independently attested. No candidate signatures, code, database, production data, or prior repository documents were changed, and no commit was made.
