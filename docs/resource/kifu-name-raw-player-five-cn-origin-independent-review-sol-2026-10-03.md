# 五个中文原名 4,358 槽：来源/读音事实 PASS，正式 anchor/batch HOLD

2026-10-03，独立审核 `/root/freq41_60_95_review_sol`。审核 [Luna producer 提案](kifu-name-raw-player-five-cn-origin-11lang-producer-pending-luna-2026-10-03.md)，输入 manifest SHA-256 `7453b9a9a796be62331c79a903e80de5dba417ffea37a5cbca4b6e246aea0ae6`；90 个被索引文件的字节数和 hash 均吻合。结论只用于精确 raw 值及冻结有限成员，人物 FK/alias 均 **0**。

| 审核层 | PASS | HOLD | 结论 |
| --- | ---: | ---: | --- |
| 主五语言来源姓名/显示事实 | 25 | 0 | 值、实际 span、观测语言、正文、来源人物 ID/DOB 与已签 95 格一致 |
| CWA→GoRatings 中文/英文对应及分词事实 | 5 | 0 | 已核实遗漏于 producer 包的原始中文桥接正文 |
| 正式 raw anchor_format=3 | 0 | 5 | 提案不是完整 validator 格式，缺 provenance 与精确绑定 |
| 四条已签 Latin 规则原样复用 | 4 | 0 | 保留既有签署，核对 content hash/签署有效性 |
| de/es/fr/tr 机械输出事实 | 20 | 0 | 逐词拼接/首字母大写与输出完全一致 |
| ru/ua 输出 | 0 | 10 | 已签有限 token_map 缺音节，未补造值 |
| 正式四语批次 | 0 | 4 | 缺完整签名、source anchor/snapshot/owner 绑定 |

**4,358 个槽均具备九语文本显示事实；11 语齐全仍为 0。** 九语共 39,222 个语言×槽单元，ru/ua 共 8,716 单元 HOLD。此数是事实可用范围，未签正式新 candidate、anchor、batch 或数据库应用批准。

## 精确范围与读音

| 原值 | 槽 | CWA playerNo | GoRatings ID / DOB | 已实证英文名与分词 |
| --- | ---: | --- | --- | --- |
| 唐韦星 | 858 | CWA000040 | 897 / 1993-01-15 | Tang Weixing; `tang / wei xing` |
| 杨鼎新 | 864 | CWA000062 | 1193 / 1998-10-19 | Yang Dingxin; `yang / ding xin` |
| 檀啸 | 911 | CWA000018 | 995 / 1993-03-10 | Tan Xiao; `tan / xiao` |
| 胡耀宇 | 868 | CWA000025 | 184 / 1982-01-18 | Hu Yaoyu; `hu / yao yu` |
| 连笑 | 857 | CWA000052 | 1082 / 1994-04-08 | Lian Xiao; `lian / xiao` |

4,358 个互异 `(album_id, side, raw)` 与冻结库存全部精确原值出现、此前[17,241 槽独立显示评估](kifu-name-five-primary-frequency-41-60-raw-display-and-identity-independent-assessment-sol-2026-10-03.md)中的同五个子集完全相同，全部人物 FK 为 NULL；0 漏槽、0 新增槽。五个成员 hash 与 producer 四批内的 `finite_scope_sha256`/数量吻合。此前 22 个异常槽及其原上下文继续保留；没有重写日期/段位或根据连续赛事推断同一人。

全范围成员 SHA-256 `c791ed6e0374c04a7a62e3a59fe153f18949c7adcd833595b827a0d9f98ec647`。按 `(album_id, side, raw)` 排序，紧凑 UTF-8 JSON 三元组列表、保留汉字。逐名 hash、完整冻结上下文与原 scope 在受控记录中。

25 格完整对应先前已签来源：cn 为 CWA 官方名册；tw 为海峰正文；jp 唐/杨为日本棋院百灵杯正文，檀/胡/连为 GoRatings 日文页面；ko/en 为 GoRatings 本语页面。实际姓名 span 按正文核对；日本表格的姓名间空白未误当新姓名。海峰应氏对阵冲突仍按此前评估保留，未用这篇报道批准棋谱身份。主五语实际显示串与先前矩阵一致。

CWA 全名册 1,062 条中，五个姓名+DOB 均唯一命中，playerNo 相符。原始 GoRatings 中文/英文页同 ID、同 DOB，中文 H1 与官方原名相符，英文 H1 与声明分词逐词对应。这证明**来源姓名与读音**，不把 GoRatings 或 CWA 人物 ID 变成 raw owner ID。

## 已留存的五个中文桥接正文

以下 URL 均为 `https://www.goratings.org/zh/players/{ID}.html`，无需新网络采集。路径根为 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/`。已在独立目录 `bridges/` 按 ID 原字节冻结。

| 原值 / ID | 原留存相对路径 | bytes | SHA-256 |
| --- | --- | ---: | --- |
| 唐韦星 / 897 | `five-primary-41-60-second9-luna/897-zh.html` | 433930 | `71a4c194cbbb7be920946e6467976aac80322c6f6c882c19a41a6e0e0dca1481` |
| 杨鼎新 / 1193 | `five-primary-41-60-second9-luna/1193-zh.html` | 441269 | `fe52704fbf41713249141c8ddbefa3252732809ebd3eb3d1f4b0da066352e626` |
| 檀啸 / 995 | `five-primary-41-60-first10-luna/995-zh.html` | 475159 | `754306e935d9f619c79b53c339830f241751aa6da53af8a3987f14e4e30f5977` |
| 胡耀宇 / 184 | `five-primary-41-60-second9-luna/184-zh.html` | 429853 | `70dc3bd54a8452767af53e3be6ff816256ca4a3fce7cab77073a95864f64bed2` |
| 连笑 / 1082 | `five-primary-41-60-second9-luna/1082-zh.html` | 423218 | `59b64c481667f8826200637e845c5045ea03fdb0e30f5b4fdc2349e427dff01b` |

## 正式提案 HOLD 的具体补齐要求

**五个 v3 anchor：** 必须组成 `evidence_kind=transliteration_anchor` 的 `content`/`approval` 记录。content 保留正确 raw owner、`anchor_format=3`、精确原值和上述分词，并补齐：

- `entity_kind=player`、`source_lang=zh-Hans`、`reading_system=pinyin-syllables-v1`、`reading_text`、`source_reading`、`reading_normalization_version=pinyin-source-v1`、`reading_normalization_basis`、`source_reading_kind=published_roman_name`。
- `sources` 按 `original / identity_bridge / reading` 三角色提供 CWA / GoRatings zh / GoRatings en。每条应有 URL、HTTP status、真实 fetched_at、body hash/excerpt、identity/language basis、observed_lang、publisher/person namespace/ID、exact_name、birthdate、record_locator。原提案未包含 /zh/ 正文及这些结构化记录；现有真实正文可复制复用，HTTP/抓取时间等须采用真实留存 metadata，不能补造。
- `source_link` 的 method=`official_name_dob_to_localized_profile_id_v1`、official_match_count=1、official_scope_sha256=完整 CWA 正文 hash、unresolved_conflicts=[]、review_basis；须绑定已核实的事实，不能把局面对阵冲突当人物键证据。
- `raw_display_scope_sha256`、`original_language_basis`、`reading_applicability_basis`、`spelling_exceptions_basis`；精确绑定有限审核范围，并核实提案 raw owner ref。当前提案 ref 未与实际目标 raw owner 前像相核实，不能声称已经批准。
- approval 包含真实 producer/reviewer ID/model、带时区 produced_at/reviewed_at、批准 status/conclusion 与精确 content hash。生产者不得自签，也不得沿用其他记录的签名；本轮只签事实，正式修订由 producer 完成后再独立签署。

**四个 batch：** 必须具有完整 content/approval、`version=secondary-transliteration-v1`、reading_system、完整已签 rule 的 `rule_sha256`、完整 approved-name snapshot 及 hash。每个 member 需绑定 owner、lang、display_name、source_anchor_sha256、rule_sha256、raw_value、raw_display_scope_sha256。现有 member 数量、原值、分词、输出及 finite member hash 正确，但没有完整 anchor/snapshot/owner 签署链。不得将语义输出 PASS 当正式 batch 批准。

**ru/ua：** 两个已签有限规则均缺如下 token，十格全部 HOLD：

- 唐韦星：`tang, wei, xing`。
- 杨鼎新：`ding, xin, yang`。
- 檀啸：`tan, xiao`。
- 胡耀宇：`hu, yao`。
- 连笑：`lian, xiao`。

## 受控交付

`~/.local/share/kifu-name-audit/2026-10-03/raw-player-five-cn-origin-independent-review-sol/`（0700，文件 0400）：25 条来源审核、5 条官方/桥接/读音事实、5 条正式 anchor HOLD、4 条原样已签规则及复用审核、30 条次六语输出判断、4 条正式 batch HOLD、冻结精确范围/上下文、5 份中文 bridge、review record 与 manifest。所有 PASS/HOLD 明确分层，签事实不签缺字段的正式记录。

- review-record SHA-256 `807b5eeb36e6df01b1b6322cc862794f221d69b8f45c5aad3aeb21fcd74282fe`。
- manifest SHA-256 `6972bdba56beab7a24160751244d8b76322f402f00831b133ccc70fd40dc4011`。

无数据库连接/写入、生产者文件修改、代码修改或提交。未运行完整 candidate/batch validator；现有提案缺正式字段，不能通过其闸门。来源、分词、已签规则和输出的聚焦离线复验已完成；正式构造与签署需下一轮。
