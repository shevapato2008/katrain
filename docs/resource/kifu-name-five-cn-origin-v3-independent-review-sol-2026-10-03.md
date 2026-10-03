# 五个中文原名 v3 包独立复核：来源事实 PASS，正式链 HOLD

独立审核 `/root/five_cn_v3_independent_review_sol`，GPT-6（运行时身份，无独立模型证明）。输入 producer manifest SHA-256 `51fad4bc71b5f7d7c9747130fc9ac4d92976f815076f9ad46dfc272a5e45fb6b`。逐项核对 manifest 所索引实际文件字节、完整 CWA 名册与 GoRatings zh/en 正文、官方 ID/同 DOB/原名/英文名、分词、有限范围及 30 格输出。未修改生产者包，未连接数据库，未改应用代码。

| 层 | PASS | HOLD |
| --- | ---: | ---: |
| 主五语言正文 hash 与实际姓名 span | 25 | 0 |
| CWA→GoRatings zh/en 来源姓名、DOB、读音与分词事实 | 5 | 0 |
| 正式 v3 anchor | 0 | 5 |
| RU/UA 每语 12 个精确 token 对照完整原始表 | 24 | 0 |
| 正式新增规则 | 0 | 2 |
| 次六语言机械输出事实 | 30 | 0 |
| 正式 batch / candidate | 0 | 6 / 30 |

4,358 个互异 `(album_id, side, raw)`、逐名数量与紧凑排序三元组 scope hash 全部相符。唐韦星/杨鼎新/檀啸/胡耀宇/连笑分别 858/864/911/868/857 槽。来源人物 ID 与 DOB 与此前独立评审完全相符。raw owner ref 仅为包内符号，不批准人物 FK、别名或写库。

## 一次窄修正清单

1. 五个 anchor `approval.content_sha256` 均与当前 `content` 的 canonical hash 不符。生产者应对最终内容重算：UTF-8、保留汉字、键排序、紧凑 JSON。审核者不修补生产者声明。当前实际值如下。

| 原值 | 当前实际 content SHA-256 |
| --- | --- |
| 唐韦星 | `b1afe9bcd37e354d414d0f28cec7482e9550ddb8d5c78fcd7035739630132eb6` |
| 杨鼎新 | `e8e8c28e06f16e0648f9af5d5b5ae2edff200a7381903cb35715a745b386d31f` |
| 檀啸 | `64d5a1895f6f1c3a976fdb65198b3a61bbb02fdd2e081e89dcfb01019dd461fd` |
| 胡耀宇 | `fbebcd8dc5667316dd714eb1f35db1af33d78b7925cd4a7c4ef13db0ce2aad3b` |
| 连笑 | `094011419b7868585386f682767e8d27160a9e64891cf7905cf422dc188efc10` |

2. RU/UA 原始表中 24 个 token 值全部吻合，含新增 `tan/hu/lian`。但规则 sources 缺 `http_status=200`、真实 `fetched_at`、`body_excerpt`、`identity_basis`、`language_basis`、`observed_lang`（ru/uk）。调用真实 `validate_transliteration_sources` 得到 `transliteration source provenance or language invalid`。必须复用实际抓取 metadata，不得补造。保留当前内容与 producer，修订后重新算 content hash，再独立审签。

3. 六个 batch content 必须精确具有 `version/lang/source_lang/reading_system/entity_kind/rule_sha256/approved_name_snapshot_sha256/members`。当前缺 `version=secondary-transliteration-v1`、`reading_system=pinyin-syllables-v1`、`rule_sha256`、`approved_name_snapshot_sha256`；多出 `finite_scope/operation/rule_dependencies`。member 多出的 `status` 须移出签署内容，member 只保留 owner/lang/display_name/source_anchor_sha256/rule_sha256/raw_value/raw_display_scope_sha256。

4. **hash 的层次必须区分**：approval.content_sha256 是 content hash；member/candidate 的 source_anchor_sha256 和 rule_sha256、batch.rule_sha256 必须指向最终完整已签 record 的 canonical hash（包括 approval），不能指向 content hash。当前全部候选与 member 用的是 content hash，且 anchor 内容 hash 已过期。先签 anchor/rule，再由 producer 绑定完整 signed record hash。

5. 绑定真实 approved-name snapshot 与其 hash、v2 raw-owner 声明及目标前像；不得用空 snapshot 冒充实际状态。batch produced_at 必须不早于所用规则及 anchor reviewed_at，随后独立签 batch。candidate 保持 pending，待完整链及真实 validator 通过后再签；本轮 30 格输出事实 PASS 不等于正式批准。

受保护不可覆写评审目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-v3-independent-review-sol/`，目录 0700、文件 0400，包含 producer 原样 anchors、逐名实际 hash、24 token 核对、30 输出核对、结构化 HOLD 与 reviewer record。manifest SHA-256 `04296eba9275d815b44da4a1ff88e64d68ca74a7dbfcc1f3726a193484388c54`。没有新正式批准记录，没有写入许可；内容来源事实无需重新采集。
