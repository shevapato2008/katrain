# Next TW17 source review request

Status: unsigned. Final post-590/page context and root signatures are pending.

| PROD owner | Exact source → proposed TW | Source language | Source evidence / applied batch | Existing TW target | Gate |
|---|---|---|---|---|---|
| 4771 | 日下包夫 → 日下包夫 | jp | 53937 / 468 | NULL | source ready |
| 5397 | 浜島久義 → 浜島久義 | jp | 53942 / 468 | NULL | source ready |
| 5297 | 武田博愛 → 武田博愛 | jp | 54163 / 471 | NULL | source ready |
| 6599 | 小松伸昭 → 小松伸昭 | jp | 54178 / 473 | NULL | source ready |
| 6626 | 早瀬玄堂 → 早瀬玄堂 | jp | 54166 / 471 | NULL | source ready |
| 4235 | 塩入逸造 → 塩入逸造 | jp | 54169 / 471 | NULL | source ready |
| 6629 | 福原義虎 → 福原義虎 | jp | 54172 / 471 | NULL | source ready |
| 6686 | 九世安井算知 → 九世安井算知 | jp | 54185 / 473 | NULL | source ready |
| 6259 | 鈴木越雄 → 鈴木越雄 | jp | 54188 / 473 | NULL | source ready |
| 600 | 肖泽彬 → 肖澤彬 | cn | 61568 / 552 | 肖澤彬 / review | REVIEW gate unresolved |
| 229 | 叶子萌 → 葉子萌 | cn | 61572 / 552 | 叶子萌 / review | REVIEW gate unresolved |
| 595 | 周雨萱 → 周雨萱 | cn | 61576 / 552 | 周雨萱 / review | REVIEW gate unresolved |
| 385 | 行泓丞 → 行泓丞 | cn | 61330 / 545 | 行泓丞 / review | REVIEW gate unresolved |
| 662 | 朱彦臻 → 朱彦臻 | cn | 61334 / 545 | 朱彥臻 / review | REVIEW gate unresolved |
| 320 | 桂诗云 → 桂詩雲 | cn | 61512 / 549 | 桂詩雲 / review | REVIEW gate unresolved |
| 446 | 李貞垠 → 李貞垠 | cn | 61594 / 553 | 李貞垠 / review | source ready |
| 391 | 王琛 → 王琛 | cn | 61259 / 540 | 王琛 / review | REVIEW gate unresolved |

## Actual source files

- `PROD-tw-source-readonly.json.gz` and `TEST-tw-source-readonly.json.gz`: pinned r2 actual DB rows, source creation journals, applied bundle IDs/hashes, current target preimages, and linked SGF hashes.
- `tw-kba446-actual-capture.json.gz` and raw response: actual official KBA pkey10001264 full HTML, complete `이정은(李貞垠)` paragraph, and same-person diary link.
- `tw-Unihan-17.0.0.zip` and `tw-moe-strokes.pdf`: exact previously captured official normative bytes, with scoped locators in `tw-*scoped*variants.json`.

## Finite decisions

- Japanese sources retain every actual codepoint. 浜 and 瀬 have no Unihan17 variant records; 塩 has a semantic variant to 鹽, and no kTraditionalVariant. Those three are retained. There is no inferred 濱/瀨/鹽 conversion.
- 朱彦臻 retains 彦. Actual Unihan17 kTraditionalVariant includes both U+5F65 and self U+5F66; no conventional Taiwanese spelling is asserted.
- Four changed Chinese characters use actual MOE rows: 泽→澤, 叶→葉, 诗→詩, 云→雲. All other scoped characters are retained.
- Compatibility 李 U+F9E1 is retained only through actual official Hanja preservation; no normalization to 李.
- Generated TW outputs assert the accepted generated display channel, with no Taiwanese personal-name publication claim.

The 7 CN owners retain their existing REVIEW preimages and are **not ready under the current NULL-only verified-display gate**. No SQL, signing, product edits, Git writes, or new preimage bindings were performed.
