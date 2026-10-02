# 五主语言95格：辅助span修正版独立复核

2026-10-03；独立审核者 `/root/freq41_60_95_review_sol`。审核[修正候选](kifu-name-five-primary-frequency-41-60-95-aux-span-correction-pending-root-2026-10-03.md)，逐字节对照此前[95格独立审核及四项HOLD](kifu-name-five-primary-frequency-41-60-95-independent-review-sol-2026-10-03.md)。

**PASS：修正版来源姓名包95 PASS / 0 HOLD；四项辅助metadata修正4 PASS / 0 HOLD。** 本裁决仅签署来源姓名、外部职业身份、语言、固定registry `.8`出版方映射与证据完整性。候选95条仍为pending；不批准raw槽、本地主键/FK、数据库覆盖或写入。

修正版：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-41-60-95-aux-span-corrected-root`。87个包内文件中85个字节完全相同；只改变sources.manifest.json和manifest.json。结构差异严格为四个辅助actual_name_span、来源清单哈希，以及总manifest新增correction追溯字段。95个candidate JSON与全部原始响应字节不变，因此原62+补证28+日本棋院4+江维杰tw裁决1的95格结论逐格保留。

从四份原HTML重新解码、解析非空H1，均与修正span及原locator.value一致；四项未被改为主姓名来源。日本棋院四个主候选及江维杰tw来源/真实异体证据均未变化。重算283个不同包内/历史输入/证据引用文件，清单与记录哈希全部相符；固定registry `.8`哈希保持相同。修正版目录0700、所有87个文件0600，无符号链接。

| 外部ID | 修正前辅助span | 原H1 / 修正后span | 复核 |
| --- | --- | --- | --- |
| 964 | `江維傑` | `江维杰` | PASS |
| 1193 | `楊鼎新` | `杨鼎新` | PASS |
| 1194 | `范廷ギョク` | `范廷钰` | PASS |
| 897 | `唐韋星` | `唐韦星` | PASS |

| 固定输入 | SHA-256 |
| --- | --- |
| candidates.pending.json | `f69ae74059cd547c0615c733c47fb92747a3d4d916481234e4d4ccaa3de6e325` |
| sources.manifest.json | `4ac657425e9057ea0458c7748479adf1d16ecd9e41e28a84b4c407f3ba471c7b` |
| manifest.json | `8794c45ae9d05cfe8332dfbcee716072640b41a75d139c2d4c5708d480768899` |
| registry `.8` | `2cfd665b215d1e8651ec9313953504d7c9ac0536d02548bfb8b8f80210593911` |

逐格签署记录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-41-60-95-aux-span-corrected-independent-review-sol/review.manifest.json`（目录0700，文件0600），SHA-256 `db8e02d5a52e45cf58179e7b14f86dd671f238553880940d943d55f6b3937867`。记录含95个精确candidate ID/值/来源/hash/span/语言/定位与4项纠正；签署时间 `2026-10-02T23:56:49.544382+00:00`。

只新增此独立报告和受保护审核记录；未改生产者包、旧HOLD报告、registry、代码、数据库或Git提交。
