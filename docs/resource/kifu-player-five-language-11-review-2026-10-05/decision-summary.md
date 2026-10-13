# Five-language name import decision — 2026-10-05

Reviewer: `/root/five_lang_db_decision` (gpt-6). No database or repository code writes performed. Approved artifact files below are new local copies; original pending research/candidates remain unchanged.

## Signed player scope

All 11 players / 55 cells pass independent source-body, language, person identity, profile date-of-birth, current owner preimage and current name preimage review. Each batch is existing-owner names only, with no album links or identity edits.

| Batch | PROD IDs | TEST IDs | Cells per environment |
|---|---|---|---:|
| clean5 | 56,57,80,201,242 | 56,57,80,202,243 | 25 |
| next5 | 17,69,108,878,879 | 17,69,109,1090,1091 | 25 |
| final1 | 880 | 1092 | 5 |

For each environment, files are `{TEST,PROD}/bundle.<batch>.approved.json`, `research.<batch>.pending.jsonl`, `validation.<batch>.approved.json`, and `inventory.json.gz`. Registry is `registry.json` in the packet root. All signed bundles validate `ready=true`, `write_ready=true`, no errors or write errors. The evidence remains producer-pending research by contract; the independent approval is on its hash-bound candidate.

Exact approved name forms and all source URLs/hashes are recorded in `clean5-independent-approval.json` and `remaining6-independent-approval.json`. Important repaired cells include Wang Li Chen, 왕리청 (王立诚); 장쉬 (张栩); and exact Japanese 劉昌赫 from the official second LG Cup opponent passage, without converting the compatibility character in another source.

## Execution

Copy this directory to each target host. `run-reviewed-remote.py` pins all six canonical bundle hashes and uses the live web container's `KATRAIN_DATABASE_URL` internally without printing it. Run one batch through TEST, then PROD, before continuing.

```sh
ssh home-ubuntu python3 /tmp/kifu-name55-packaging-20261005/run-reviewed-remote.py TEST clean5 dry-run
ssh home-ubuntu python3 /tmp/kifu-name55-packaging-20261005/run-reviewed-remote.py TEST clean5 apply
ssh ucloud-v100 sudo -n python3 /tmp/kifu-name55-packaging-20261005/run-reviewed-remote.py PROD clean5 dry-run
ssh ucloud-v100 sudo -n python3 /tmp/kifu-name55-packaging-20261005/run-reviewed-remote.py PROD clean5 apply
```

Then replace `clean5` with `next5`, then `final1`. Stop if any live dry-run/preimage check fails. The helper uses the existing compatible TEST web image and PROD importer image, a read-only packet mount, and the live web network. Both images passed import/CLI smoke checks; remote batch dry-run/apply is performed by the parent. No deployment is required.

TEST: `katrain-web:kifu-cn-events-20261005-r5`, network container `katrain-web`.
PROD: `katrain-kifu-importer:five-gate-978491a2`, network container `katrain-ucloud-katrain-web-1`; sudo Docker.

Current inventory format 4 captures and full current-row captures accompany each environment. Name-only changes do not change the album/source inventory hash or the owners/aliases catalog hash. Other candidates' exact name preimages remain protected by live transactional checks, so the first batch does not require rebuilding the remaining research/inventory.

## Top 20 event types

The proposal JSON is research input, not verified evidence. Catalog CN copies, script conversions, English descriptive translations, Wikipedia interlanguage titles, and source homepages do not automatically qualify. Product codes are `cn,tw,jp,ko,en`.

Only 大手合 is already verified in all five languages. Its ID is PROD22 / TEST1; TEST22 is another event. All other listed event IDs below are the same on PROD/TEST and had no name rows in the read-only capture.

| Event ID | Catalog series | Decision / minimum prerequisite |
|---:|---|---|
| 22 PROD / 1 TEST | 大手合 | Skip: five verified names already present. |
| 24 | 日本本因坊战 | Fastest next source-ready five cells; rebind existing ID and null preimages, update registry hash, independently sign. |
| 25 | 日本十段战 | Fastest next source-ready five cells; same finite rebind. |
| 28 | 日本王座战 | Existing source packet supports exact forms; produce finite existing-owner bundle. Avoid unsupported composite TW name. |
| 27 | 日本名人战 | Existing sources support compact forms; use exact TW 日本圍棋名人賽 and professional KO spelling. Keep separate from old Meijin. |
| 23 | 日本碁圣战 | Existing source review; check allowed source tier/registered host for TW/KO and preserve 碁聖 distinction from 棋聖. |
| 70 | 日本NHK杯电视围棋锦标赛 | Existing source packets; repair only captures missing timestamp/HTTP metadata, then finite bundle. |
| 43 | 三星杯世界围棋大师赛 | Retained five-language bodies; bounded review needed, especially Japanese historical sponsor wording. |
| 40 | 日本龙星战 | Partial CN/JP/EN possible; TW personal blog and KO national ambiguity do not complete five verified cells. |
| 26 | 日本棋圣战 | Proposal alone insufficient; direct per-language series evidence needed. |
| 29 | 日本天元战 | Proposal alone insufficient; direct per-language series evidence needed. |
| 30 | 日本旧名人战 | Require explicit old-series authority; never reuse modern Meijin evidence by title alone. |
| 41 | 中国围棋甲级联赛 | Proposal alone insufficient; direct per-language series evidence needed. |
| 42 | 中国女子围棋甲级联赛 | Proposal alone insufficient; distinguish women's series in each source. |
| 50 | 韩国围棋联赛 | Proposal alone insufficient; official Korean title plus target-language attestations. |
| 51 | 韩国女子围棋联赛 | Proposal alone insufficient; preserve women's-series distinction. |
| 53 | 台湾棋王赛 | Proposal alone insufficient; national series distinction required. |
| 58 | 中国围棋天元战 | Proposal alone insufficient; distinguish Japan/Korea namesakes. |
| 65 | 中国围棋名人战 | Proposal alone insufficient; distinguish Japan/Korea namesakes. |
| 66 | LG杯世界棋王赛 | Proposal alone insufficient; direct target-language event wording. |

## Concrete next event batch: 10 cells

IDs24 and25, no owner creation and no album links:

| ID | CN | TW | JP | KO | EN |
|---:|---|---|---|---|---|
|24|本因坊战|本因坊戰|本因坊戦|본인방전|Honinbo|
|25|十段战|十段戰|十段戦|일본십단전|Judan|

Reuse `~/.local/share/kifu-name-audit/2026-10-02/honinbo-final-review-astra-v2/validator-evidence.jsonl` and `judan-v2-bundle-draft/research.pending.jsonl`, filtered to those five languages. Retained Honinbo bodies are in `honinbo-controlled-research/`; Judan bodies are in `judan-ten-controlled/source-bodies/` and `judan-ten-en-repair/source-bodies/`. CN/TW pinned encyclopedia revisions require keeping their independent Japanese event corroboration. Names have source-level approval; no current-ID event bundle is signed by this decision. Do not reuse the old large album-link scopes.
