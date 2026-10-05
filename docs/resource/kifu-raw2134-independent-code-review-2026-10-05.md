# raw2134 independent code review

Reviewer: `/root/raw2134_code_review`

Scope: base `02b551f6` → `a60fd572ca80e81207f67999ee7ebbd402fe47f2`, plus the subsequent three-file exact-search correction in `/Users/fan/Repositories/katrain-kiosk-go-kifu/.worktrees/kifu-raw2134-compat`; both committed pending packets and `/tmp/kifu-raw2134-20261005` captures/PROD overlay.

**Decision: approve with the execution limits below. No unresolved critical or important findings.** The first review identified one important search defect; the parent fixed it and the correction passed independent focused verification. This is code/deployment-scope approval, not a signature approving pending category/template/name candidates. No real DB writes, remote commands, deployment, or author-file edits were performed during review.

## Resolved important finding

Original location: `scripts/build_kifu_raw2134_overlay.py:75-77` in commit `a60fd572`. The generated `needle = or_(needle, reviewed_raw_event_search_clause(db, q))` preserved fuzzy results even when the complete approved raw name matched. Thus `个人赛` also matched `2022全国个人赛1轮`, violating the promised exact 638-member scope; `段位赛` had the analogous issue for 901 members. OR could also let the old fuzzy branch bypass the new event-FK/selected-event exclusions.

Evidence before correction:

- Both captured inventories contained 2,381 nonduplicate event values containing `个人赛` versus a 638-member approved raw scope, and 1,405 containing `段位赛` versus 901. These inventory counts do not expose `list_hidden_reason` and were not treated as live endpoint totals.
- A temporary SQLite reproduction returned `[12]` for the approved raw helper but `[12, 13]` for the original OR integration when album 13 had the longer event/search text.

The correction is minimal: `legacy_raw_events.py:167` now returns `None` for no unique approved raw match; `build_kifu_raw2134_overlay.py:75-79` replaces `needle` only when a unique approved raw clause exists. The existing entity-match precedence, no-match fuzzy fallback, list visibility filters and pagination remain intact.

Independent verification after correction:

- The seven focused tests pass, including the generated patch integration test for exact raw match versus substring fallback.
- Executed the actual corrected `list_kifu_albums` function extracted from the captured PROD overlay against a temporary SQLite fixture, with identity lookup and response rendering stubbed to isolate filtering. Query `个人赛` returned IDs `[12]`, total `1`; the unmatched raw query `2022全国` retained fuzzy results `[13]`, total `1`.
- Rebuilt overlay hashes all match the manifest. Pending data packets remain unchanged.

## Data and write-safety checks

- Both committed gzip packets' `categories` and `names` objects exactly match the corresponding `/tmp` pending objects.
- Only the existing raw owners are present: 69522 / `Hoensha game` / 595 albums, 71508 / `个人赛` / 638, 74834 / `段位赛` / 901. Owner preimages and occurrence IDs equal the read-only captures. Current names are absent. Plans/candidates remain pending and final candidate reviewer signatures have not been copied from historical packets.
- All 33 display strings equal the two retained historical approved bundles byte for byte. Each owner still has eleven languages. `album_links` is empty. No event identities or album/player/event FK changes are proposed.
- Hoensha's 595 retained album/source rows equal the pinned inventory rows. All source associations are CWI. Both retained source-body SHA-256 values match. Both captured selection supplements are empty.
- The category script validates independent signatures, exact plan hash, full owner preimages, fixed three-raw scope/counts, catalogue before/after hashes, absent names, and Hoensha's source/album context. Apply uses the existing DB lock, transaction and journal. Replay checks unchanged after-images and returns zero changes. The existing conditional undo restores only matching after-images; name batch then category batch is the documented undo order.
- The narrow overlay changes `display_maps`'s final integration, endpoint search integration, and two added helpers. It preserves legacy models, original SGF/FKs, visible-row filtering, and the five primary languages / other-English display policy. The change does not touch blank/uncertain raw classes or hidden-row tagging.

## Verified overlay artifact

All captured before hashes and final overlay after hashes match `/tmp/kifu-raw2134-20261005/overlay-prod/manifest.json`.

| File | Final SHA-256 |
| --- | --- |
| `katrain/web/kifu/identity.py` | `d4473d559879b69ac7afb64e9cadbff53dbd03cc86dbba483c64f98656ca4ba1` |
| `katrain/web/api/v1/endpoints/kifu.py` | `d31bc207426398def48618c0774766e114a57b7dda14082aea8f1751d223d881` |
| `katrain/web/kifu/legacy_raw_events.py` | `dfea7b2a0f8acb0124d45766d174ce98f6f61203438ca52d63669ba61397d930` |
| `katrain/web/kifu/legacy_raw_event_rules.py` | `9bfe3b7efdb84922b356af48d0ddaf74def95c7833c78fb6006843c8e8ff22f7` |

Local verification command:

`PYTHONDONTWRITEBYTECODE=1 /Users/fan/Repositories/katrain-kiosk-go-kifu/.venv/bin/python -m pytest -q -p no:cacheprovider tests/web_ui/test_kifu_raw2134_categories.py tests/web_ui/test_kifu_legacy_raw_events.py`

Result after correction: **7 passed in 1.28s**. Tests used temporary fixture databases only.

## Practical execution limits

1. Finish the real independent category/template/final-candidate approvals on the final rebound packets and pass the original eleven-language validator before any write. This code review does not make the pending packets write-ready.
2. Refresh captures/rebind if queued work changes catalogue or album/source/selection state. Apply only the final independently checked hashes, with the documented TEST → PROD dry/apply flow. Undo names before categories.
3. Match the actual PROD file before hashes to the prepared manifest immediately before the narrow overlay. This review did not deploy or exercise a live modified endpoint; the existing zero-query runtime import result was reviewed as an author-produced artifact.
4. After deployment, perform the already planned representative five-language display and exact 901/638/595 ID-scope checks with hidden-row filtering intact. TEST's current reader needs no legacy overlay. No broader architecture or regression expansion is needed.
