# 五位 CN-origin 棋手 TEST-scope anchors：独立 PASS

2026-10-03；reviewer `/root/freq41_60_95_review_sol`，真实模型 GPT-6（不声称独立 subtype attestation），producer `/root/five_player_test_rebind_producer`。**五 source anchors PASS，HOLD 0；只签锚，不批准 downstream research/candidates、六 batches、fresh55绑定、TEST激活、person FK或alias。**

输入 manifest `48ecb49f0f46fc8057c560503ca25d008437a2e0a104ad794e1a47080cb5c0ae` 的 12 文件与 26 外部来源依赖 byte/hash全部吻合；pending anchors字节 SHA `b9a395736aea2413b362de64cb7594b91987d9cf019d1afa1a19c82746e2ecf6`。复制的四份signed-scope输入与独立原签包逐字节相等，五完整scope record canonical SHA均绑定实际已签TEST record，未使用content-only或pending hash。范围仍 **4,358 slots /4,238 albums**。

对比旧五完整签锚：**content唯一变化 `raw_display_scope_sha256`**。原名字、owner/raw、source_link、所有来源/语言/ID/DOB/时间/正文hash/locator、published reading、pinyin syllable segmentation、规范化与exceptions basis逐字不变。旧文字basis内保留的历史scope引用未伪造为新的正式signed-scope hash；相同精确membership已在上一步scope复核。

独立再次读取15 source角色所对应的 **11 distinct raw bodies**，核CWA exact name/ID/DOB/grade唯一行，GoRatings同profile zh/en的真实H1、html lang、DOB和URL profile ID。官方CWA JSON SHA仍 `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9`；胡明确真实 `data.Z08[10] /CWA000025 /胡耀宇 /1982-01-18 /Z08`，其余四旧 `data.[Z09] roster row playerNo=…` broad locator均可在真实Z09解析到唯一符合行。中文bridge用原保留五profile body核验；en发表名与分词保持 Tang Weixing→tang|wei,xing；Yang Dingxin→yang|ding,xin；Tan Xiao→tan|xiao；Hu Yaoyu→hu|yao,yu；Lian Xiao→lian|xiao。并非由exact name/date推断album person FK。

输入pending anchors实际validator拒绝；新签后实际 `validate_transliteration_anchor` 五项全部通过。签署真实时间 **`2026-10-03T04:21:41.320657+00:00`**，晚于producer与冻结 `2026-10-03T04:19:05.483311+00:00`；producer时间本身晚于scope独立签时 `04:16:36.927975+00:00`。每条新锚保留pending content、producer身份/time及content SHA，只补真实独立审批字段。

| raw | slots | status | 完整新签锚 canonical SHA-256（下游使用） |
| --- | ---: | --- | --- |
| 唐韦星 | 858 | PASS | `5d835b4014596213711010ff22529a753a117e902306d10c174c8beee27e9149` |
| 杨鼎新 | 864 | PASS | `faee96a89e541634cb38a07cb118200b3db705d8041319ee1385850b05646edc` |
| 檀啸 | 911 | PASS | `19e13066ed64ce637cb0322c26aef386a4038b6e7569c06a948490a2000f32fd` |
| 胡耀宇 | 868 | PASS | `5cceb8144798a8c5d5522f7d88fded991553a793de2cc6b24e719b6d3d702fba` |
| 连笑 | 857 | PASS | `c4c5967799dcfe60de713ea8bb0bc45b316c2d0f782bc11395c7d10444c1f204` |

受控目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-anchors-independent-review-sol`（0700，文件0400）。

- `anchors.test-scope-rebound.approved.json` byte SHA `34d0b937190f92518b4eeb722f0a29624cb4771b4a474e5b0e12cb9857d3f2ce`。
- `anchor-record-bindings.approved.json` byte SHA `f29800b60477558b0d1c7e12e39f458e1ce57d608b9c760a0e166fdd5634783c`，含五旧/新完整锚、完整scope与source-facts hashes。
- `source-facts.rechecked.json` byte SHA `377852395e10c3a369eb2cb75220b2edd9d4ba61707d584f99f8b442740861b0`，包含每角色真实body路径/hash及解析locator。
- `review-decision.json` byte SHA `5c63e69aaf10e1cd971dcc2dfcb8db5f222a28cc14acbe3502ac13599f35c151`。
- `manifest.json` byte SHA `1140b07eadc0289c5a9ef710e3888550ed04691ddb09510c3a04162b8142e5c2`。

本次没有DB连接或写入，没有改producer、旧签文件或应用代码，没有Git commit。下一producer应以表中五个**完整已签锚**重绑主五research与六完整batch，继续独立审批/最终fresh前像校验；本次不提前批准这些下游件。
