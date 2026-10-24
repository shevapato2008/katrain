# Kiosk 小盘内容只读调查

调查基线 `faacf2597`，2026-10-24。只读取仓库和 TEST / PROD 数据库，未导入、改库、发布或调用收费模型。下述候选数只是几何第一门，不能当作已认证可用数量。

## 数据权威、来源与坐标

| 内容 | 权威与读取路径 | 坐标与当前行为 |
|---|---|---|
| 训练营 / 死活题 | `core/models_db.py:TsumegoProblem` 的 `tsumego_problems`；`api/v1/endpoints/tsumego.py:get_problem` 原样返回 `board_size / initial_black / initial_white / sgf_content` | 初始点及 SGF 使用左上原点的 SGF 字符点；`core/sgf_parser.py:Move.from_sgf` 转内部左下坐标。`ui/src/utils/sgfParser.ts` 与 `hooks/useTsumegoProblem.ts` 使用题目尺寸进行相同翻转。初始 JSON 和整棵 SGF 都必须派生。 |
| 原始题库导入 | `scripts/sync_tsumego_db.py` 从 `data/life-n-death` SGF 导入；题型来自根注释，来源多为 101weiqi | 分类不能证明局部含义；例如 `capturing` 中仍可能存在征子或劫。不要重跑同步脚本来产生派生内容。 |
| 新 OGS 教程 | `tutorials/ogs_models.py:TutorialOgsStep.payload`；`tutorials/ogs_import.py` 固定来源版本并保留 `raw_source`；`tutorials/ogs_course.py:public_step_output / step_sgf` | 全部结构点 `[x,y]` 是左上原点。结构包括 setup、所有树节点、letters、shapes、viewport、remove_targets。树根 `point=null`，非根 null 是 pass；correct/wrong 独立保存。 |
| OGS 冻结源 | 上游 commit `1c1c2b82d027f7c307ab25886112cf0a6baf680a`，locale `5304fd731af8856a16d198d506111d61`；`scripts/ogs/README.md`、`export_course.mjs`、`ogs_course.py:export_zip` | 248 课、3,551 步；原始 SGF 下载与 source.zip 必须保持原尺寸，派生不能替换来源档案或 `raw_source`。 |
| 实体盘 | `kiosk/pages/TsumegoProblemPage.tsx`、`kiosk/tutorial/useOgsPhysicalBoard.ts` | 两处明确只允许 19 路。OGS 顶部行坐标直接等于视觉 row；转共享 tsumego `Stone` 才做 `y=18-row`。共享 `usePhysicalTsumego` 管理清盘、摆盘、提示灯、提子、错手、屏幕落子同步、复位和结题收敛。 |

当前没有小盘到 19 路的内容适配器。`tutorials/viewport.py` 只是给**已有 19 路**图计算裁剪显示，非 19 路返回完整盘；裁剪不改变棋规。`core/tsumego_frame.py` 是分析用填充框，不能作为保留原题语义的派生证明。

## 实际可达环境与规模

本机 Docker daemon 未启动；主仓和工作树没有本地 `data/life-n-death/index.json` 或本地 DB。停止于此，没有为调查启动服务或排障。

TEST `home-ubuntu` 的 `katrain-postgres / katrain_db` 与 PROD `ucloud-v100` 的 `katrain-ucloud-postgres-1 / katrain_prod_20260725` 可只读读取。PROD 容器中的默认 `katrain_db` 不是服务实际数据库，其中没有 OGS 表；实际名称从 web 容器环境 URL **仅解析 host / database 名称**确认，没有输出密码。两个 web 容器均为 `katrain-ogs-release:68db3ba5e-20261024`。

每次 SQL 使用 `BEGIN TRANSACTION READ ONLY` 或连接后 `SET TRANSACTION READ ONLY`，只执行 SELECT 并 rollback/commit 只读事务。可复查方式：SSH 后 `docker exec <postgres> psql -X -U katrain_user -d <实际库>`；或在现有 web 容器用 SQLAlchemy 读取现有 `KATRAIN_DATABASE_URL`，不打印 URL。不运行项目 startup/init_db 或同步脚本。

两环境题库尺寸/类别计数一致；按 `id + 原始SGF摘要` 排序汇总的摘要也一致：`756fa5a48e06616bb9169b9fe064e302`。OGS 按 `source_id + content_sha256` 汇总也一致：`c5821c6119fd50555ba3f13ad0d593d4`。这些是本次快照一致性证据，不能替代运行时 SHA-256 来源校验。TEST 共 79 本教材，PROD 共 10 本；本任务不要把 TEST 的其它教材误认为已发布内容。

| 训练营路数 | 实际题数 | 几何第一门候选 |
|---|---:|---:|
| 4 | 190 | 0 |
| 5 | 2 | 0 |
| 7 | 12 | 7 |
| 8 | 25 | 23 |
| 9 | 534 | 413 |
| 11 | 12 | 11 |
| 12 | 2 | 2 |
| 13 | 102 | 96 |
| 19 | 20,193 | 已是 19 路，保持原始 |
| 小盘合计 | **879** | **552** |

| 小盘题型 | 实际题数 | 几何第一门候选 |
|---|---:|---:|
| capturing | 304 | 267 |
| endgame | 51 | 0 |
| life-death | 298 | 85 |
| semeai | 49 | 40 |
| tesuji | 177 | 160 |

OGS：19 路 2,860 步（puzzle 2,520、choice 340）；9 路 689 步（puzzle 506、choice 180、pass/remove/finish 各 1）；13 路 puzzle 2 步；共 3,551。全部 **691 个小盘中 657 个**过几何第一门。小盘只有 page 18 / `ogs-learning:ko:5` 非空 viewport：`{col:0,row:3,cols:8,rows:10}`；其余 690 为 null。

全部 879 原始小盘 SGF 与 691 OGS 完整 payload 已只读导出到 `/tmp/kiosk-small-content-20261024.json`（约 6 MB，无凭证）。机械结果及逐项候选在 `/tmp/kiosk-geometry-results-20261024.json`，调查脚本 `/tmp/kiosk-geometry-investigate-20261024.py`。临时文件没有纳入 Git。

## 最小资格、来源与验证规则

1. **先固定来源。** 对完整原始 SGF或可见的 OGS 结构规范化做 SHA-256，并在版本化清单记录 source_id、原尺寸、hash、语义结论和原因。不以分类、关键词、稀疏程度或边距自动判定语义安全。源改变即清单失效。
2. **最小变换只平移。** `f(x,y)=(x+dx,y+dy)`；不得旋转导致“右上角”等正文方位变化。遍历初始与**所有分支**的点、设置/清除、标记和线端点；源左边参与则 dx=0，右边参与则 dx=19-n；上/下同理。任一轴两相反边都参与，无法保持两边，留原。每轴至少有一个完整未参与边；无边约束可居中。坐标不能截断或单独改 size。
3. **机械第一门的证明范围。** 平移保持邻接；每个参与点的源边界邻接也必须保持，因此记录树中所有棋串的连接和气集合在映射后保持。当前 879 SGF 的实际属性只有 GM/FF/CA/AP/SZ/GN/AN/SO/GC/C/AB/AW/PL/B/W；均可正常解析，DB 初始与 SGF 根设置、SZ 一致。实现仍应明确支持 FF4 点/范围、LB、AR/LN 等已知坐标属性，并对未知可能承载坐标的属性拒绝派生，不能静默漏变换。
4. **第二门完整走树。** 原盘和目标盘从相同初始轮到方开始，逐分支复制状态，比较每一步合法性、映射后的完整棋子集合、提子集合、棋串、气集合、ko/重复局面行为和叶子正确/失败标记；包括失败分支、pass、非交替落子、setup/AE 等特殊节点。不能只验正解主线。源本身非法、标记模糊到无法保留判题含义或无法重放的，记录源问题并留原；不擅自修题。
5. **语义第三门。** 有限树等价只证明已列分支，不证明新空白空间对所有自由探索和全局答案无影响。明确审核全局计目、盘宽示意、方向/坐标正文、征子延伸、全盘劫材等语义。只允许已审核的 hash/课目内容；全盘题或无法证明的内容留原，理由随题可审计。不能把过几何门的 552 / 657 全部标为可用。
6. **返回派生副本和原因。** 源 ID/进度仍用原 ID；返回 source_size、目标 size、dx/dy、来源 hash、验证规则版本、available/retained_reason。原始数据库、Galaxy 默认响应与下载不变。原始截图仍是来源证据，不能假称 19 路派生截图。
7. **真实闭环。** 同一个派生对象供绘盘、判题树、hint、自动回复、物理摆盘与 expected-board、提子/错手、撤销、清盘和 reset 使用；不能一处用 19 点另一处用源点。聚焦验证至少包括中央小盘、边角小盘、多个解答分支、提子和必须留原一例。

## 代表源与可审计结论

| 源 | 原题事实 | 建议结论 |
|---|---|---|
| Tsumego `92643`，8 路 capturing | AB `de ef eb ec fc dd fe`；AW `df ff ed ee fd dc`；唯一答案 `B[gd]`，`C[✓ 正确]`。所有初始/答案点均不触边。 | 明确局部吃子候选；可居中平移，并用完整走树证明。不能只改 SZ。 |
| Tsumego `129993`，9 路 tesuji | AB `fe dc ee`；AW `de ef fd ge ff`；`B[ed]` 正确；`B[gd];W[ed]` 和 `B[ec];W[ed]` 失败。 | 明确局部手筋候选，全部三个起手分支应保留。 |
| Tsumego `218387`，7 路 capturing | AB `df be ag dg af`；AW `ef bg cf cg cd ed bf`；答案 `B[ce]`。使用左、下边。 | 纯平移 `dx=0,dy=12` 保留左下角；`B[ce]→B[cq]`。验证不能丢失边缘限制。 |
| Tsumego `124386`，9 路 capturing | 答案包含 `B[ie]`、`B[if];W[ie];B[id]`；另有 `B[hh];W[if]` 失败。 | 必须保留右边，即 dx=10；不是把中央图随意铺到 19 路。 |
| Tsumego `108018`，4 路 life-death | 初始棋子分别使用四边；正确 `B[ba]`，失败 `B[dc];W[ba]`、`B[aa];W[dc]`。 | 留原；4 路两相反边同时决定气数和眼形，19 路平移无法保留。 |
| Tsumego `122131` / `123086` / `213404`，4/9/7 路官子 | 原注释分别含“盘面平空”“正解 盘面6目”“盘面11目”等结果；树覆盖不同边界。 | 留原并说明原盘全局目数/多边界参与，扩盘会改变题意与答案依据。 |
| OGS page 73，`capture_stone:1` | 9 路 B `[0,7]`、W `[0,8]` 标三角，正确点 `[1,8]`；原文要求提掉标记白子。 | 可保持左下两边平移 `[x,y]→[x,y+10]`；实体角白子仍只有一气。 |
| OGS page 7，`self-capture:1` | A `[8,0]`、B `[7,1]`、C `[4,5]`，原文解释 A/B 自杀、C 提子。 | 候选须把 A/B/C 和全部 setup 一起平移到右上边界，不能只验证树中的 C。 |
| OGS pages 12–13，`eyes:3–4` | 左下和右上分别摆两种眼形作对照，四边参与。 | 留原；保一角会改变另一角的眼与气，不能删除“辅助”棋形。 |
| OGS pages 1–2，`rules-intro:1–2` | 答案树分别接受全部 81 / 80 个源空点；正文“any empty intersection”。 | 留原；平移后仅接受 19 路中的 9 路子区，会错误判其余空点。 |
| OGS pages 31–33，ending-the-game | pass / 清死子 / finish；page33 原文黑24目、白18+4=22目、黑胜。 | 留原；新增空白会改变完整终盘含义。 |
| OGS page 35，`the-board:2`，13 路 | 正文明确比较 9×9、13×13、19×19，并要求在右边非角处下。 | 即使几何能平移，盘宽教学须留原，不能让13路示例暗中变19。 |
| OGS pages 468–479 / 1574–1579 | determine-winner 的“终局谁胜”；endgame4 的“全盘还有多少单官”。 | 留原；全局答案不可由局部树等价证明。 |

## OGS 首批语义审核范围建议

可以从明确的局部气、连接、提子教学开始：`rules-intro` pages 3–6；`count-liberties` 37–48；`in_atari` 55–60；`capture_stone` 73–78；`capture_chain` 79–94；`both_atari` 95–106；`escape` 107–112；`find_escape` 113–124；`connect` 137–142；`cut` 143–148。这些范围均过几何第一门，但仍需整树第二门及其各步正文审核。`count_chains` 49–54 仅 49/51/52/53 过几何门；`count-atari` 61–72 中 61/66 未过，不能整课盲放。

更复杂的 make-alive、capture-group、snapback、net、capturing_race 等也有大量候选，应该在相应局部证书和源审核后继续覆盖，不能因为复杂就永久一律跳过。征子/劫/全局计目先保原，按题给理由。局部角空的 `territory` 19–30 和 `count-territory` 456–467 几何可保角，但需要证明所问封闭区域及死子计数不变；它们与“全盘谁胜”不同，不应仅凭 territory 关键词永久排除。

## 板端代理与是否必须云部署

`ui/src/api/tutorialApi.ts` 的 kiosk 构建走 `/api/v1/board/tutorials`，`endpoints/board.py:get_ogs_step` 调 `RemoteAPIClient.get_ogs_step`；训练营板模式通过 `RepositoryDispatcher / RemoteTsumegoRepository / RemoteAPIClient` 读取云端。现有代理不转发 board_variant，返回的都是原始数据。

**在 RK 板端代理读到原始数据后调用共享纯函数，并在全版 Kiosk 的可选请求参数路径调用同一纯函数，不要求云先发布。** Galaxy 省略参数继续原尺寸；盒端前后端仍须一起交付。若选择只在云端派生、让盒端单纯转发，则云端也必须发布；不能只更新盒前端期待旧云自动给19路。

需要留意来源校验边界：`public_step_output` 刻意不返回 DB `content_sha256`、raw_source 和全部语言。盒端不能直接比较 DB 全 payload hash。无云改动的最小方案是对代理可见的稳定结构字段做规范化 hash，并对所选 locale 文案做对应已审核 hash 校验；清单来自被冻结的完整源。若仅按 source_id 或课名放行而不检测内容变更，达不到固定来源的双门要求。
