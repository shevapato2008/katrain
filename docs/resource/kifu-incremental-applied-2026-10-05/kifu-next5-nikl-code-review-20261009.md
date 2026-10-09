# Next-five finite Mandarin rule code review

**PASS — no blocking findings in the exact four-file change below.** GO for this code packet; this review does not approve an unproduced name-candidate bundle or claim deployment/data application.

Actor `/root/durable_rule12_review_astra`; configured model/effort `gpt-6-astra/max`, supported by root's actual spawn record rather than inferred from the task name. UTC `2026-10-09T09:25:11.162168+00:00`. Read-only Git diff and local pure validation only; no database command, SSH, deployment, restart, commit or other Git mutation.

| Reviewed file | Actual SHA-256 |
|---|---|
| `katrain/web/kifu/name_zh_ko.py` | `ffb982053b555164eaf22b873b223a2e06c49ec20224d7348aa91c12d7add62e` |
| `katrain/web/kifu/name_evidence.py` | `4723cd5c6bcbbbb8d7c50414558d2dae8e86b732622718175194a0004ee6fb97` |
| `tests/web_ui/test_kifu_name_candidates.py` | `1ef9d5e7e03897bec2ac21e7ce40bd4e721c8408004196ee2286ac26bab0b905` |
| `docs/superpowers/plans/2026-10-09-nikl-four-mandarin-names.md` | `3d6d7c7d27ec2bae4d8afec4d4ad59400b2892fa6ea5c67b4400510c2ea77692` |

The tracked diff contains exactly those four paths. Their actual hashes match root's supplied packet and were rechecked immediately before writing this report.

## Source and implementation agreement

The change implements the decision in `norm-extension-review-astra.md` (SHA `aa641f62a994b704156596c0b43cd33bb15e922b6bcc053c3acb9a6da336f7d3`). All twelve added keys, Hangul outputs and derivation kinds equal the source-reviewed entries. `xu` retains the Ministry-hosted spelling explanation's exact body hash, line 206, requested HTTPS URL and actual HTTP final URL. `jian` explicitly applies the general ㅈ/ㅖ simplification and identifies the nearby examples as analogous, rather than falsely quoting a literal 졘→젠 example. `tian` and `xiao` correctly retain their medials. The new entries are bound to the actual fba body by the exact capture/domain gate; no new grammar or character-to-reading inference was introduced.

I compared the original R13 module with the new module: all original 18 entry dictionaries are exactly equal; `SOURCE_BASIS`, `RULE_VERSION`, old `RULE_URL`, old `RULE_BODY_SHA256` and `RULE_LOCATORS` are unchanged. `LEGACY_RULE_SYLLABLES` is frozen before the update and equals exactly the old 18 keys. `CURRENT_RULE_SYLLABLES` is exactly the 30 reviewed keys, with no additional syllable accepted.

The evidence validator accepts only these combinations:

- Exact non-www official URL with `92977a7c4e2d255aa62d91011372bea1a198f5c3ee6f92db5b02fa6366fb9d9b`: original 18 only.
- Exact www official URL with `fba7508fd4dfb60eee30561ff8e11c64493fb3f0bd9fecceacb1fcedd13c6731`: all 30 reviewed keys.

This means **the old hash is limited to the old 18; old entries themselves may use either reviewed capture**, as approved in the prior source decision. Every new syllable requires the www/fba pair. Cross-pairs and unknown hashes select an empty allowed set and fail. The existing exact capture keys, HTTP 200, normative role, Korean language, locators and aware timestamp checks remain intact. The rule's signed `used_entries` and output still must reproduce exactly before capture acceptance. Failed-fetch bodies gain no eligibility.

## Reader compatibility and scope

AST comparison against the reviewed R13 evidence module shows that only `_validate_positive_zh_ko` changes. No persisted-proof reader, legacy applied-ledger branch, source-anchor gate, owner binding, candidate-review binding, importer contract or eligibility classifier changes. With the same v1 constants and identical old entry dictionaries, an existing valid old proof retains the same capture equality and reproducible output; the new domain condition is true for every old entry. This preserves legacy qualification without rewriting proof bytes or stored data.

The documentation accurately describes the finite extension and separate owner-bound evidence work. The existing unknown-syllable negative test now uses still-unsupported `zhuo`, which preserves its purpose after `xu` becomes supported. Added synthetic fixture data is confined to tests and supplies no real-person source approval.

The new evidence file imports constants added by the new rule file; these two Python files are one coupled deployment packet. This code review does not authorize deploying one without the other or bypassing the existing native release checks.

## Focused verification

Fresh independent checks passed: all four file pins; exact original 18 dictionaries/constants; exact 18/30 frozen domains; twelve mapping/kind matches; AST scope; and in-memory compilation of the two modules and candidate test file.

Fresh independent command:

```text
.venv/bin/python -m pytest tests/web_ui/test_kifu_name_candidates.py -q -k 'positive_zh_ko_twelve_reviewed_syllables_render_five_names or positive_zh_ko_rule_capture_variants_bind_finite_domain or positive_zh_ko_four_reviewed_finite_outputs or positive_zh_ko_accepts_only_reviewed_first_batch_inputs'
```

Result: **19 passed, 175 deselected in 0.11s**, exit 0. This covers all five new outputs, the precise capture/domain cases and retained old outputs/inputs. Root additionally reported Sol's focused 74 candidate and 13 batch tests passing; those counts are producer evidence and were not independently rerun here. No broad suite or new test framework was added by this review.

The separate durable-override operation is outside this code approval. Root reported that its failed before/after configuration comparison restored the original file without a restart; this report makes no current-live persistence claim.
