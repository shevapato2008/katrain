# 棋谱段位独立只读调查（2026-11-03）

范围：全库来源、原始 BR/WR 方言、棋手关联、历史段位证据、现有 rank fact/snapshot 发布链，以及 Kiosk/Galaxy 的段位展示。未改产品代码、未写数据库、未执行同步或发布，未读取、列举或 glob `data/kifu-album/`。以下是调查结论与修复边界，不是实施计划。

## 核心结论

`25055` 的“业余七段/业余九段”源于两层问题：旧 SGF 的 `7d/9d` 被全局解释成业余，Kiosk 列表再给 `d` 加“业余”。它并非棋手实际身份是业余。与之逐步操作相同的星阵记录 `140858` 使用 `7p/9p`。应以星阵的中立数据格式 `Np / Nd / Nk` 统一有证据的规范值，同时保留旧 SGF、原始段位和来源；不能把所有 `d`、所有星阵记录或全部棋手直接改成职业。

SGF FF4 的 BR/WR 是 SimpleText，推荐 `d/dan` 表示“段”，并没有规定它只表示业余。因此“历史来源的 `d` 永远是业余”不是 SGF 标准。依据：[SGF FF4 BR/WR 定义](https://www.red-bean.com/sgf/properties.html#BR)。星阵本库也同时存在 `p`、`d`、中文“段”、业余、院生和空值，输入同样需要判断，不能把“统一为星阵标准”误解成“星阵来源全是职业”。

## 全库规模和原始方言

PROD 实际库为 `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725`。只读事务查询得到 176,949 盘，176,690 盘公开可见，353,898 个黑白段位槽。黑方 FK 已填 161,738，白方 FK 已填 162,478。所有 SQL 均在 `BEGIN ... READ ONLY` 或 `SET TRANSACTION READ ONLY` 后执行，设置 5–15 秒 statement timeout，未调用应用 startup/init_db。

真实来源关联表只有两类：`19x19` 覆盖 154,231 盘、154,243 个来源链接；`CWI` 覆盖 22,718 盘、22,718 个来源链接。下表七个目录是导入桶，不应当作七种经过验证的来源身份。统计包含隐藏和重复行，符合“全库统一”的范围；括号说明例外，不把它们悄悄排除。

| 导入桶 | 盘数 | 空值 | 明确 p/pro | d/dan | 中文裸“段” | 业余前缀 | 级/k/kyu | 其他 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 19x19 | 154,231 | 47,393 | 29,010 | 9,586 | 219,845 | 241 | 3 | 2,384 |
| Go_Seigen | 891 | 79 | 8 | 1,647 | 0 | 0 | 2 | 46 |
| CWI_1950_1978 | 16,178 | 359 | 31,423 | 26 | 0 | 0 | 10 | 538 |
| CWI_Dosaku | 153 | 214 | 83 | 0 | 0 | 0 | 0 | 9 |
| CWI_History_Full | 4,735 | 2,577 | 4,320 | 2,537 | 0 | 0 | 0 | 36 |
| CWI_Jowa | 293 | 114 | 0 | 452 | 0 | 0 | 0 | 20 |
| CWI_Shusaku | 468 | 27 | 0 | 909 | 0 | 0 | 0 | 0 |
| 合计 | 176,949 | 50,763 | 64,844 | 15,157 | 219,845 | 241 | 15 | 3,033 |

这里按原始字符串外形统计，“其他”包括头衔、院生、年龄、多人联棋、非标准段位和无效值。不要把本列合并成“无效段位”后丢掉语义。全库常见值包括 `业余` 186、`十段` 171、`院生` 158、`名人` 157、`天元` 132；CWI 还存在 `6d ama` 44、`5d ama` 30、`7d ama` 12，旧吴清源集合存在 `1d ama`、`1k ama`、`provisional 3d`、`7d & 7d`。

按现有 `normalize_rank` 函数实际解析，结果为：`professional_dan` 64,844；`amateur_dan` 15,208；`dan_unspecified` 219,848；`kyu` 15；空值 50,763；不可规范解析 3,220。与原始方言表不同，是因为 241 个业余前缀中只有 51 个包含可解析数字，另外还存在少量全角/空白等规范化差异。上述 `amateur_dan` 是**当前代码的分类**，不能当作调查认定的真实业余数量。

## 可验证的职业身份覆盖与历史反例

全库 3,689 个 canonical player。调用现有 `lookup_professional_identity_evidence`（每批不超过 200 人）后，1,022 人通过其严格官方主体解析：日本棋院 137、韩国棋院移动站 255/主站 507、中国职业名册 107、海峰 16。这是当前证据提取器的覆盖下界，不是“只有 1,022 位职业棋手”。

上述集合关联了 5,609 个当前被解析为业余的槽和 151,331 个裸“段”槽。它们构成待核对范围，不能直接全改职业。专业身份是人与来源的证据；历史对局的段位还需要对局日期有效的证据。

本库确实含有后来成为职业棋手的早期级位/院生记录：

| Album | 原始棋手 | 原段位 | 日期/赛事 |
| --- | --- | --- | --- |
| 142610 | KobayashiKoichi（FK 小林光一） | 1k | 1966-05-15，1966InseiTournament |
| 157560 | Cho Chikun（FK 赵治勋） | 1k | 1962-07-31，赴日前送行棋 |
| 157561 | Cho Chikun | 3k | 1965-10-23，1965 Insei Tournament |
| 157565 | Cho Chikun | 1k | 1968-02-13，1968 Insei Tournament |

此外，`5977` 佐藤洸矢、`10236` 宋一美、`11791` 黄皓等星阵记录明确写“业余”；`5570`、`5805`、`6039` 等写“院生”。`24557` Muramatsu Shofu 是 `1d ama`、作家围棋协会授子棋；`24643` Namiki Keiichi 是 `1k ama`、伤员慰问棋。即使 CWI 首页把主体集合介绍为职业棋谱，其中也存在这类对手，目录或来源不能覆盖明确业余证据。[CWI 来源说明](https://homepages.cwi.nl/~aeb/go/games/)。

## 1989-01-17 的确切证据链

| 字段 | 25055 | 140858 |
| --- | --- | --- |
| 来源 | CWI | 19x19 |
| origin/source path | `data/kifu-album/Go_Seigen/1989-01-17.sgf` | `data/kifu-album/19x19/41563564.sgf` |
| 黑方/白方 | Yoda Norimoto / Go Seigen | 依田纪基 / 吴清源 |
| BR/WR | 7d / 9d | 7p / 9p |
| 黑白 FK | NULL / 1 | 57 / 1 |
| 隐藏/duplicate_of | 均 NULL | 均 NULL |
| rank snapshot | 均不存在 | 均不存在 |

两盘 173 手的完整规范化操作指纹相同：`a77f1798822b47b455e30e5b9eecb18ce5d0fb0fbc09bb09ac3f32d534466b4f`。该指纹由另一位独立调查者使用正式 SGF parser 得到，包含每个主线节点的摆子/清除操作、初始行棋方、颜色、pass 和完整着手，不仅比较落子坐标。具体元数据和去重处置见同次独立去重调查。

日本棋院的[依田纪基官方档案](https://www.nihonkiin.or.jp/player/htm/ki000101.htm)明确给出 1987 年七段、1990 年八段、1993 年九段，直接支持这盘 **7p**，不能拿当前九段回填。[吴清源官方档案](https://www.nihonkiin.or.jp/player/htm/ki001001.htm)给出 1950 年九段，支持 1989 年 **9p**。两位的职业身份和历史段位均已被交叉核实。

canonical player 1 的确切 aliases 包含 `Go Seigen`；57 没有任何 alias，全库 alias 表仅 39 行。`Yoda Norimoto` 虽然是其已经审核的英文展示名，却不是身份索引里的 alias，因此旧行黑方 FK 没被绑定。`build_rank_identity_index` 只接受 canonical/精确 alias，不用展示翻译发现人物；这不是把英文显示名临时塞进所有身份匹配的理由。可通过有证据的精确 alias/同盘同色身份归属补关联，并记录原 FK。

现有官方职业证据提取器还漏掉这两位：吴清源已保存的官方 capture 含主体和 `棋士段位 九段`，但 `_official_subject` 要求中间必须出现 `ファンメッセージ`，退役棋手页面没有该可选栏目而被拒绝。最小修复应仅让该栏目可选，仍要求唯一主体与其自己的段位字段。依田的官方原语 capture 位于研究 payload 的 `original_language_evidence`，而 `_approved_context` 只遍历 `research.source_checks`；不能拿 `identity_basis` 的普通文字或 URL 当成已验证 capture。应接纳并验证确切 capture 结构，或重新保存一份符合现有源检查契约的 capture。

## 全库星阵同盘交叉核对下界

复用去重调查的全库解析结果，将生产库原始段位 scalar 按 album ID 连接。在“至少 30 手、无 parser flag、无变图”的完整操作相同组里，有 1,225 组同时含旧源和星阵，涉及 1,239 条旧源记录。这个过滤是本次等级证据 census 的保守下界，不代表其他组无价值或已经审核通过。

- 1,599 个旧源槽和星阵对应槽都使用 `p`，其中 1,576 槽段数一致；另有 **23 槽段数冲突**，不能只因系统同为职业就忽略。比如 `152818` 的白方 `6p` 对应星阵 `32183` 的 `5p`，`153518` 的黑方 `1p` 对应星阵 `52828` 的 `9p`。需要同盘人物/日期验证及历史证据仲裁，不能把星阵标准化形式与星阵每条数据绝对正确混为一谈。
- 93 个旧源 `d` 槽有**段数相同、系统为 p**的星阵对应槽：Go_Seigen 77、CWI_History_Full 16，涉及 47 盘。
- 另有 2 个空值和 2 个复合头衔值能在同操作星阵槽找到 `p`；包括这些在内共 97 个候选槽、49 盘。
- 93 个 d→p 候选的星阵对应段位均一致；43 槽日期完全相等，41 槽双方 FK 均相等，只有 19 槽同时满足日期完全相等、双方 FK 相等、候选段位一致。余下还需日期/别名归属核对，不能把 97 个候选全部叫“自动可修复”。

`25055` 属于完整操作、确切日期均一致，但旧黑方 FK 缺失的组；官方人物/升段历史已补足证据。部分其他组存在 `1900-01-01` 占位日期或旧源多年/多日日期，必须保留不确定性。不能仅为补段位而让星阵错误占位日期覆盖较好的旧源日期。

## 代码链路和现有审计机制的可复用边界

原始值链路：`scripts/import_kifu.py:parse_sgf_file` 直接将 BR/WR 存入黑白 rank 列；增量入口 `kifu_ingest/preparation.py:derive_metadata` 同样 SGF 优先，没有历史来源段位系统规范化。`web/kifu/name_parse.py:parse_player` 只保留可识别段位，不建立职业身份。

当前 `web/kifu/player_ranks.py:normalize_rank` 把显式 d/dan 固定为 `amateur_dan`，即使 `professional_identity=True` 也不改；裸段才会借职业证据转为专业。`kifu_ingest/ranks.py` 冻结 source > library_current > unknown。`display_rank_for_game_slot` 仍优先返回原始 rank，因此**只写一个规范化 source snapshot 也不会让 7d 显示成 7p**。API 的 `_rank_displays` 是 list/detail/prepared reads 的共享出口，适合在验证精确绑定后返回中立规范值，原始字段继续原样返回。

现有库仅 136 个 rank facts（103 professional、33 dan_unspecified；当前 professional 88），184 个 snapshots（source/professional 42、source/dan_unspecified 35、source/无系统 1、library_current/professional 92、unknown 14）。它们覆盖的是增量发布链的少量记录，不是旧库已经有全量等级审计。

可复用的数据表是 `kifu_player_rank_history`、`kifu_album_rank_snapshots`、`kifu_name_batches`、`kifu_name_changes`。现有发布器已实现原图/来源/FK 验证、immutable fact SHA、snapshot 绑定、事务内 before/after journal、CAS、回放验证和条件撤销。全库规范化应复用这些审计能力，冻结规范化策略、原始槽、精确来源、来源 SGF SHA、规范值、历史证据与同盘星阵证据；不需要增加本地化段位数据库列，也不应原地改写 immutable 历史事实。

但现有 `scripts/kifu_rank_correction.py` **不能原样承担旧库修复**：它限制 1–20 个数字 ID 的 19x19 原生发布，要求原 BR/WR 为空、原生 publication receipt 存在。旧 CWI 包含大写来源、嵌套人物目录和日期文件名；rank fact 现有 source_key 仅允许小写，snapshot source_item_id 仅允许数字，API 绑定也构造单层数字路径。需向后兼容地增加规范化策略/证据版本和精确 source_path 表达，保留旧 snapshot/hash 的有效性；旧库修复入口须有独立的精确前像和审计批次，不能假造原生增量 receipt。

`catalog_album_cleanup` 虽允许 patch rank/FK，但它是“缺名字行删除+外部备份”工具，要求 delete_ids 非空，且没有完整处理新增 rank snapshot 依赖，不能把它直接作为全库等级迁移工具。

全库统一必须覆盖四种诚实结果：有历史职业证据的 `Np`；有明确历史业余证据的 `Nd`；已知级位的 `Nk`；系统或段数仍未知的保留原值/未知结果。当前职业档案只能提供身份背景，不足以覆盖入段前的所有对局；原始缺等级时也不能把当前等级伪装成当年等级。未来星阵增量应走同一规范化决策并冻结结果，避免旧库改好后又产生新的方言分歧。

## 两个界面的同一个展示问题

Kiosk 列表调用 `kiosk/utils/listRecordPresentation.ts:getListRank`，自己的中文分支把 `9p` 显示为“职业九段”，却把 `9d` 显示为“业余9段”。Kiosk 详情和 Galaxy 列表调用共享 `utils/rank.ts:formatRank`，当前 `9p` 会输出“职业9段”，其单测明确期望“职业5段”。Kiosk/Galaxy 某些 report/import 摘要还直接拼接中立值。

应以一个共享的棋谱格式化入口统一规范值的中文职业段位：`1p…9p` → “职业一段…职业九段”，繁体为“職業一段…職業九段”；其他语言继续本地化既有模板。业余/级位保留其系统，裸段和未知不能凭姓名或界面补“职业”。API 返回中立值与系统/来源证据，不向数据库写“职业九段”。

## 最低充分验证范围

数据规范化：一次全量只读 dry-run 与分类汇总，确保 176,949 盘/353,898 槽全部计入明确结果或待核结果；不把“待核”计成“已修复”。迁移测试聚焦精确 SGF/槽/FK/来源绑定、星阵同盘证据、旧 snapshot 兼容、前像变化拒绝、重放幂等和 journal 撤销。职业当前档案不能覆盖早期院生/级位，明确 `ama`/业余与未知保留。对 raw SGF 和原 rank 字段验证 SHA/值不变即可，无须重跑引擎分析。

展示验证：共享 formatter 只需 cn/tw/en 的 p/d/k、裸段、空值和旧复合值代表用例；API list/detail 使用相同 fixture 验证 `25055` 规范为 7p/9p，原字段仍 7d/9d，`140858` 保持 7p/9p。Kiosk 与 Galaxy 各做一组真实列表/详情预览，确认均为“职业七段/职业九段”，并复用一个明确业余和一个未知/空值样例。达到后结束，不需要全语言全状态截图或 GPU 回归。

## 调查材料

数据只从生产库 SELECT 和已有临时快照读取。原始 snapshot：`/tmp/kifu-preview-investigation/prod-full.jsonl.gz`，SHA256 `d89d339b0fe0951e59d34abfbb89ee4221e0113328d90ab5ffa0c232e12ead74`。

本次材料在 `/tmp/kifu-preview-investigation/`：`rank-context.json`（canonical/alias/合格官方证明摘要）、`rank-scalars.csv`（全库 rank 原值）、`rank-scalar-census-results.json`（完整分类与 97 个同盘候选）、`rank-scalar-census.py`（只读计算）。最终分类以 DB scalar + 独立 SGF parser 的操作指纹为准；早期 `rank-census.py` 是正则探索结果，不作为最终 root 字段或重复判定依据。

最终结果文件 SHA256：`abb5fe96742d5966b384724ef3df5ccb59c5c7735f3bb5ac7cad6f8a2f325898`。外部页面首次 Firecrawl 获取因账户 0 credits 失败，随后用 web 读取上述 SGF/CWI/日本棋院原站资料；失败未阻断本次调查。
