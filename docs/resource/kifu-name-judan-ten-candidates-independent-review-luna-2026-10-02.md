# Independent review: Judan ten-language candidates

Reviewed `2026-10-02T15:17:26Z` by `/root/judan_eleven_candidates_luna`. Parent-assigned reviewer configuration: `gpt-6-luna`, high reasoning; runtime model identity is not independently attested. Decision: **PASS for all ten conventional display candidates** for `event:@judan-series-2026-10-02`.

I recomputed the pending candidate file SHA-256 as `9e7f234115d8cbf21b6c3e73ba00583172d3b58d8c3077e5285973f0e3b42050`. Every canonical candidate row hash matches the table. For each row, the canonical hash of its bound research record matches `research_sha256`; language, display form, and symbolic owner match the research record; producer ID and model match the research producer; and the row is pending, unsigned, and has `name_preimage_sha256: null`. I reran `_validate_candidate` for all pending rows and the signed copies against registry `.5`, using only `event:@judan-series-2026-10-02` as a temporary symbolic `link_targets` input. This validates row fields and source binding only.

I also checked the captured bodies against their capture manifests and confirmed the exact display strings in the source bodies or reviewed German page-47 extraction. The previous independent source reviews report PASS for the nine non-English first-batch rows and the repaired English row. The old `Judan Title` row remains excluded under its prior HOLD. The English `Judan` is attested as a standalone tournament table entry in the CWI Japanese professional Go archive; the official Nihon Ki-in page independently identifies its Japanese 十段戦 series. The other rows use the exact localized tournament form reviewed in their source: `十段战`, `十段戰`, `十段戦`, `일본십단전`, `Judan-Turnier`, `Judan` (Spanish), `Judan` (French), `Дзюдан`, and `Judan` (Turkish). The archived German PDF SHA-256 matches its manifest, and its reviewed page-47 extraction hash is `8b6f67653e73e0b72e8dcfd84130271029b162620d100b25de7cb787d7bb9588`.

Protected source-reviewed copy: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ten-candidates-source-producer/candidate.source-reviewed.jsonl`. It preserves each producer field and adds only `review_status: approved`, reviewer `/root/judan_eleven_candidates_luna`, `reviewer_model: gpt-6-luna`, this review time, and the source-review conclusion. Its SHA-256 is `3178ffb5ce5f63f58bf3e9f6a811f60affba375c31e80c28650a61b33eab2a0f`. Approval is limited to source-reviewed conventional display choices. No UA row was included, no preimage was bound, no event or album link was approved, and no database write was made.

| Language | Display | Pending row SHA-256 | Signed row SHA-256 |
|---|---|---|---|
| `en` | `Judan` | `cb39d047d93bc530fd9ff0ef6f76b306284c90f740fefacf1c9b5b75babf4e32` | `b62925cece3f51415e90dd4f082e0c11ae9d599e5199999e912e921975a21e93` |
| `cn` | `十段战` | `88a5d5700b7956f2a226358b3e42f52c2af2213471f4fde4d29f8997b1c2c6a9` | `3c17741f281ebd87c7d8efeed4a3f602de68e54b0772a01680dfe68ecb37e6dc` |
| `tw` | `十段戰` | `5b1210cc491ddb319e6f8e24e377eb179723b8f9e20dc8c2adf372676d6b2497` | `4498958b6f31692e4f701a14e59596dc23df182b12b15ddfb7461671c1a0cc6a` |
| `jp` | `十段戦` | `6d1817e70f24340869f87d7a11748fd88bc82833292039cf77057e0f23adc6b8` | `0aae98c180eff3455445777de5e05ee097107d11c3caa062fbff072bb61f60e6` |
| `ko` | `일본십단전` | `3f773622227ae839003d95261220ed1e0caa744527a01dfb1a52c423d8f6e365` | `450d4df558c224810f6da552beed3d7c8943b4c9dbbf9e7a9438257baf6b5725` |
| `de` | `Judan-Turnier` | `964bf6c1b0f0f235f96c748151d65f79948263b6303fcaa76fb6dc16aef7dc2a` | `b63e1fe8babfc5f08681c0c0effc79d59cbcd8efba323f0e7b5a0a135b7b2ab7` |
| `es` | `Judan` | `50da307b957f2aefde3965ba75b8f59919ad9fc299904b3fcba317a85f206efd` | `9cf7225f14e917f235fb7786ea1ed0e7199fc4ffbdcdf9903f9c8b21393b73b3` |
| `fr` | `Judan` | `0e14fc6fc398d2709e183b920742cc08b40e55d7657215f7e99f81bd898aef9a` | `6ce4100492566f70784f5091e0006f706ea17335878430ad805f6f5e90af8fd3` |
| `ru` | `Дзюдан` | `7f416506d65019fcdcbed1f058b98fd6f41cdd805663f13c545d7dea765ed037` | `48dbcdbeb6081992911f2cb87b4f7c3696d496a479b054d53f542de42540aa41` |
| `tr` | `Judan` | `ede31481c1f63a18fd8259fe6ca34d90ccb60bf6753cfa874a76e609aa7428b3` | `f4e6ebc37fe1349045f28d5b877993a08718ca5dcc01bbfe1fc920e0ef66da4b` |
