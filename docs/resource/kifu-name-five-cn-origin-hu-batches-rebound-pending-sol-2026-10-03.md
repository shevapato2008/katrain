# 胡耀宇已签修锚：六批次第二阶段待审重绑

2026-10-03；producer `/root/anchor_format4_impl_sol`，GPT-6 运行时身份（未独立认证子型号）。承接[独立修锚 PASS](kifu-name-five-cn-origin-hu-locator-independent-review-sol-2026-10-03.md)，新版本 `hu-batches-rebound-pending-v2`。未产生独立 batch／candidate 签署，没有提交、应用代码修改、DB 连接／写入或克隆操作。

独占目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-hu-batches-rebound-pending-sol/`，目录0700、文件0400。真实 producer／生产时间在 manifest、六 batch pending approval 和30候选内。

五锚已签集合、anchor bindings 和五scope/category的 owners 文件按原字节复制；六 rule 内容及原审批完整保留。所有胡耀宇新依赖绑定完整**已签**锚 canonical SHA `c4a9f2341449c7d4586718e30dcc4895c0ebf809645a50e7868df49bd2a63172`，不再使用旧错误锚或第一阶段 pending 锚 hash。

六 batch 的 content 仅胡成员 anchor hash 改变。每批原 reviewer／approved／结论均删除，替换新 producer、真实时间、pending status 与新 content hash。30 candidate 全部重绑 pending batch hash；胡六行另重绑已签胡锚。旧最终 preimage binding及审核签署不沿用。主五25候选中胡五行改回明确的 `identity_anchor_full_signed_record_sha256`、保持正确 `data.Z08[10]` locator；候选批准仍 pending。其余20行逐值未变。

## 产物及字节 SHA-256

下列文件均位于上述独占目录。

| 文件 | SHA-256 |
| --- | --- |
| `raw-anchors-v3.approved.json` | `f2349f4c9b3c435c9203c25981ad9393627d523bd9e72b38707576143e4fee6c` |
| `anchor-record-bindings.approved.json` | `e3d7b51025df4ad4045cd7ea9b8199e6873331a975138efb900c16d040f8e1b6` |
| `owners.approved.json` | `fc3bdafda183dc98b493cac2fe9b435f8f383f3abf7fd2734c8d91fe2f26301b` |
| `rules.approved.json` | `6b8f9a67ccf7e501081d843f2d5802493baa092d5cd21bb2d0f46bdfb96aff9c` |
| `transliteration-batches.pending.json` | `ed883227500c2fe96c9987e4af16cce8ee83d9aecd6cbfbcb579cb1c1940b6d5` |
| `transliteration-section.pending.json` | `ce371e16cdf1ea4089cfe24f31fe1ee50d7753a1614546647154322ccb3f8345` |
| `six-language-candidates.pending.json` | `eda95f330083082e86c86461688b73ef723f06bd418f144315a729e98edfcb62` |
| `primary-five-candidates.pending.json` | `f154a647f16faaab1870df78ee77ba089c9a4e9be0d08f43095715101bf52288` |
| `validation.json` | `d9d65f3b728329fc9d0ab90542e48636fbbedf80cd23ca79888c0fd009b5c998` |
| `manifest.json` | `7d21c35258b0408ebcbbbc9fbefee13632015c815e5c027b605cdebb0bb8f7e6` |

实际运行五锚 `validate_transliteration_anchor` 全通过；六规则经过 `validate_transliteration` 的规则检查。30个显示值按原 rule及已签 reading_words重新计算，全部与原输出一致；30个 candidate与其成员字段、范围、规则及新批次hash逐项绑定吻合。五组原成员和4,358槽范围未变，主五其余20行未变。生产时间晚于五锚审核时间。

实际 section 校验在新批次签署处如预期拒绝：`transliteration content lacks exact approval`；30个 pending candidate均由 `validate_transliterated_candidate` 拒绝：`transliterated candidate restricted to six approved languages`（它同时要求 approved状态，此处为pending）。这证明未签批次／候选未越过批准闸门；没有把待审产物包装成最终 write-ready bundle，也没有操作数据库来验证。

下一步独立签六 batch，随后30 candidate必须继承**新完整 batch签署 hash和确切审核字段**。主五候选仍需自己的候选批准；实际目标新鲜前像捕获、最终审批与新输入的隔离rehearsal依旧待办。旧clone回执不能替代这些新hash的验收。
