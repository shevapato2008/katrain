# Kifu prepared read path 计划审核 — Astra 第 1 轮

**结论：需修订。** 无 Critical；以下 5 项 Important 在计划交付前补齐即可。建议作者一次修改后，用剩余第 2 轮仅核对这些问题，再交回用户；本轮不授权实施，也不追加无限审核循环。

审核对象：`docs/superpowers/plans/2026-10-27-kifu-search-prepared-read-path.md`，基于 `06d8e732f2c9cb956c76d9c9806f3f3584adcd43` 的文档草稿。按 writing-plans 检查规格及可执行性，并按仓库比例原则限制范围。只读取本地代码、现有验证记录和部署说明；没有运行测试、远端探针、DDL、业务写入或服务操作。以下行号对应本轮草稿。

## 已满足的方向与比例

- 完整 proof 移到准备阶段、原证明函数保留为唯一语义依据、在线 proof 禁入测试，能够解决“只缓存 SHA 但仍逐请求证明”的问题。现有 `_qualified_name_rows()` 还包括 transliteration、normative ja/zh/legacy-negative 等分支；实施时禁入断言应覆盖整个该入口，以及 selected-event、raw scope 和 `first_pass_cn.valid_override_search_ids()`，不只 first-pass 编译器。
- 读事务采用一致快照，正常发布与准备同事务，撤销可原子失效，未准备返回明确 503 而非少结果；这些边界清楚。canonical images、旧 receipts 和 undo journals 不加入派生列，独立 MetaData 避免旧 `create_all()` 自动建新表，符合已有代码约束。
- 六张表分别承担状态、名称、有限成员、展示、反向依赖和 dirty 输入，没有明显重复职责。它们服务当前读契约及增量失效，可保留；不需另增通用任务平台、持久 artifact SHA 层或报告/段位投影。
- 约 176k 数据分批准备、预算中止、显式 enable/disable、TEST 先行、新 177 PROD 小样本复验、保留旧 183 退役边界均合理。计时把完整 JSON last-body、排队、错误率、首个新棋手、公网和浏览器分开，349ms 样本的说明也准确。

## Important — 交付前必改

### I1. 将主性能门禁固定在用户的棋手搜索语境，避免自动扩大验收范围

**定位：** 计划 §1 行 39–46；Task 6 行 250–253。

当前表格把赛事、日期、任意模糊查询等默认全部纳入同一 20ms/200ms SLO，而用户的新目标是在“搜索某棋手”的语境提出。它们需要保留兼容性，但不应未经确认就变成必须同预算的新性能项目；同样不能靠显式 `player_id` 静默替换自由 q 的完整含义。

**最小修法：** 明确给用户的建议默认：主 SLO 为棋手姓名、已有 `player_id`、合法别名，并完整保留该 q 的同名/raw/碰撞语义；建议 1 QPS p95≤20ms、100 QPS p95≤200ms，待用户确认。赛事、日期、通用模糊、无条件页保持原结果/排序/分页契约，单列性能，不自动要求同一预算。负载清单分成主门禁与兼容性样本，混合比例不能稀释主门禁，也不能因此引入全文搜索平台。

**验收文案：** 主 SLO 的精确查询清单/分布、完整请求边界、错误率和首次新棋手规则写在同一处；未达标按该清单诚实报告。

### I2. 新表独立 owner 不能兑现对仍为 superuser 的 Web runtime 的权限承诺

**定位：** 计划 §4 行 111；Task 1 行 145–149；Task 2 Files 行 154–159。

该段先要求 Web 不能伪造 prepared/ready，又说当前连接若是 superuser/table owner，只给新表建立独立 owner 和受限写身份。对于仍保有 superuser 的 Web 连接，这一步无效。仓库的 `docker-compose.db.yml:7` 与 `docker-compose.yml:76` 使用同名 bootstrap/app 用户；当前真实角色权限本轮未探测，不能据此假定生产已是受限 runtime。实际 Web 使用 `katrain/web/core/db.py:26` 的 `settings.DATABASE_URL`；增加一个 `KIFU_PREPARE_DATABASE_URL` 本身不会改变它。

**最小修法：** 在计划内选定一个真实的信任边界，不把两种方案混写：

- 若保留现有受信 DB owner/运维能力，明确不能声称数据库权限抵御持有该全能身份的进程；保证的是完整准备器为唯一正常代码写入口、普通业务 DML 必然失效、在线 reader 不接受 caller 提供的 ready/verified。不要为抵御恶意 DB owner 新建秘密或全站权限平台。
- 若“Web DB 身份只能读 prepared”仍是发布门禁，则必须补出实际受限身份切换：受影响的 `KATRAIN_DATABASE_URL` / Session、collector 发布 engine、receiver `KIFU_INGEST_DATABASE_URL`、准备 CLI，以及旧 startup/schema 操作的兼容与回滚；不能只创建新表 owner。业务与准备仍必须用选定写身份的一条连接/事务。普通业务角色无 prepared DML 权限时，失效 trigger 要有固定的受控执行权限，只能置脏/失效，不能向 caller 暴露置 ready 或写任意派生结果的入口。

**验收文案：** 使用哪一种边界、实施时检查哪些角色属性/权限、何种结果拒绝 enable 写清楚；没有依据时不声称“runtime 无法伪造”。无需本轮远端查角色。

### I3. 实际 collector/receiver 的代码与连接切换尚未进入可执行发布步骤

**定位：** 计划 §4 行 101/111；Task 2 行 159/167；Task 5 行 233–234；Task 7 行 263–267。

`katrain/cron/jobs/kifu_ingest.py:25–30,591–592` 在独立常驻 cron 进程中导入 `publish_manifest`，并传入 `katrain.cron.db.engine`。receiver 的 `katrain/kifu_ingest/orchestration.py:61–65,558` 则从 `KIFU_INGEST_DATABASE_URL` 建 engine。两者不会因 web 换镜像或新增准备 CLI 自动采用新代码/新写身份。既有 `docs/operations/releases/2026-10-27-kifu-search/operators/README.md:68–70,95` 还明确要求所有非 web 容器的镜像、ID、启动时间等完全不变。

因此“web-only 发布 + writer 未变 + 新发布同事务准备”目前不能同时成立。旧 collector 下一次成功发布会触发 dirty，但没有新准备 hook 清除它；启用后的搜索将停在 503。若直接限制旧身份，旧发布也可能权限失败。

**最小修法：** 增加一个简短的 writer 切换表，列出 TEST 唯一 collector、PROD 固定 receiver、已列入本次的人工 apply/undo/import CLI 的真实调用文件、发布 engine 来源、代码加载方式和提交前 hook。将 Task 7 的旧 web-only operator 限定为 Web 阶段，另写必要的 receiver/唯一 collector 版本切换顺序：在无在途发布的安全边界加载新版本，保留 stage/key/budgets/host pin/原有锁，不启动第二个 collector，不 kill 活动事务；新版本实际生效前不 enable。哪些镜像/代码 pin 必须更新、哪些配置必须保持，应分清。回滚先 disable prepared，再处理 writer/web 版本兼容。

**验收文案：** 一次正常发布及 replay/undo 经真实新 writer 路径完成后，业务 receipt 不变、dirty 已消耗、ready 持续成立。若保留旧 collector 镜像和进程绝对不变是硬约束，应明确本方案暂不能启用；不能以“之后集成”跳过。

### I4. 同名授权需要 token 集合依赖，不能只保存单行资格和 owner/raw watch

**定位：** 计划 §3 行 84/87/92/94；Task 2 行 163–167；Task 3 行 188。

当前 schema/闭包描述只明确了单行 `eligible`、owner/raw/source 等 watch，没有规定“名称本身合资格”与“该同名集合允许 exact 搜索扩张”的区别。现有 `identity.py:_finite_shared_player_ids()`（行 867–929）验证 `shared_display` 授权及**所有同语言、同 normalized term 的 verified 行集合**；其中还包括不通过 `_qualified_name_rows()` 的行。这个集合检查不是简单对合资格名称计数。

具体回归：A、B 的 shared_display 已批准并已准备，随后为一个无旧依赖的新 owner C 插入同词 verified 行，C 自身 proof 不合资格。旧 reader 会因 observed 集合变成 A/B/C 而拒绝原 A/B shared 扩张；只准备 C 并保留 A/B 原来的允许标志，会错误扩张结果。全局 ready 先 false 并不足够，错误闭包清脏后仍会得到假 ready。

**最小修法：** 在现有 prepared names/dependencies 中明确表示单行公开资格与 exact/shared 集合授权（可用有限字段/类别，不必再加表）。增加 `(名称域, lang, normalized term)` 的正/否定集合 watch，包含 old/new term、所有 relevant verified 行及其状态，不仅 eligible 行；新 INSERT、改名、撤销、删除都重新准备受影响 token 组及其依赖。明确旧 reader 的 SQL exact/lower 匹配和 alias normalization 是不同规则，不能仅靠 `normalized_term == normalize(q)` 无意扩大 exact 分支。

**最低验证：** 用现有同名 fixture 增加上述 A/B→新增 C→移除/撤销 C 的一组对照，确认完整 ID/total/分支语义恢复一致；同时 proof 禁入测试仍通过。无需建设通用依赖图平台。

### I5. visible-only 准备覆盖与现有详情接口的可读范围不一致

**定位：** 计划 §2 行 75；Task 3 行 178/185；Task 5 行 231–235。

计划要求 `/albums/{id}` 同样使用 prepared display、缺行返回 503，但全覆盖门禁只检查 `(visible album × 五语)`。现有 `kifu.py:get_kifu_album()` 行 537–539 按 ID 读取，没有列表的 hidden/duplicate 过滤；因此已有但不在可见列表中的谱仍属于详情契约。visible-only 初始准备可以被标为 ready，但这些原本可读详情会因缺 display 返回 503。

**最小修法：** 分开列表谓词与准备覆盖域。既然详情也切 prepared，展示准备/覆盖须包含所有现有详情可读取的 album，列表仍按原 hidden/duplicate 条件过滤；依赖闭包也不能因为谱当前不可见就漏掉其详情展示。不要借性能改造改变既有详情为 404，或在缺行时偷偷恢复在线 proof。

**最低验证：** 一个 hidden album、一个 duplicate album 的详情在 ready 后维持原展示/SGF/report 行为，列表仍不返回它们；对应删除才是原有 404。只需聚焦这些现有契约。

## Minor — 非阻塞整理

1. 五语名称展示与请求轮次语言分开写明。`identity.py:42` 对 de/es/fr/ru/tr/ua 使用英文名字，但 `kifu.py:637` 保留 requested round language，现有 `test_kifu_name_api.py:110–136` 已验证俄语轮次。最小做法是在线继续执行轻量 `display_round_name(raw_round, requested_lang)`，无需把六种额外名字语言也物化。
2. Task 5 的 `--resume` 补一句 checkpoint 存在哪里、与哪一批提交原子更新；state 内的 phase/cursor 即可，不另起进度平台。Task 6 补明确 offered/achieved 到达率的失败条件，发生器自己的排队不能被当成服务端实际承受了 100 QPS。十步表格的当前标签已可读，不需为文案再开审核轮次。

## 第 2 轮范围

仅核对 I1–I5 是否被文档中的明确契约、触点和发布步骤解决，以及修改是否引入直接矛盾。Minor 不阻塞交付；不要求本轮执行角色探测、压测、全量 proof 扫描或部署。用户确认 SLO 及实施范围前，继续保持“只计划”的边界。

---

## 第 2 轮最终结论 — Approved

**结论：Approved（计划文档）。** 第 1 轮 I1–I5 均已在文档中闭环，无剩余 Critical/Important，也未发现这些修订引入的直接阻塞矛盾。审核对象为同一计划的 302 行版本，blob `e427e48f39170f1d6630b2fbd6dcf02072e8a9b5`，base 仍为 `06d8e732f2c9cb956c76d9c9806f3f3584adcd43`。本段为最终结论，上方第 1 轮意见保留为历史。

本轮只复核修订后的计划，未扩大源码审计，未运行测试、远端探针、迁移、准备或部署。

| 第 1 轮问题 | 第 2 轮核对结果与修订定位 |
|---|---|
| I1 主 SLO 范围 | 已解决。§1 行 41–47、Task 6 行 276–280 将棋手姓名/ID/合法别名及其完整同名/raw 语义设为主门禁；通用 q 保持契约并单列。首次新棋手、逐类延迟、到达率与错误统计没有被热样本或兼容性样本稀释。20ms/200ms 仍为待用户确认的建议目标。 |
| I2 权限边界 | 已解决。§4 行 129–131 明确采用 root 选定的受信 DBowner/运维边界，保留原 engine 和同连接事务，无新增必需凭证或全站角色迁移；不再承诺 REVOKE/独立 owner 可以约束 superuser。HTTP/caller-set ready、verified、GUC 均不能自证，普通源表 DML 仍强制失效；不受信调用者的实际发现会阻止 enable。 |
| I3 真实 writer 切换 | 已解决。§4 行 114–125、Task 2 行 180–193、Task 7 行 290–296 写明常驻 collector、receiver 与人工 CLI 的 engine/包加载/hook，区分 Web operator 和必要的唯一 cron 换版。新 hook 未实际生效不得 enable；保留原锁、stage/key/budgets/host pin，禁止第二 collector 与 kill 活动任务。正常发布/replay/undo 验证及先 disable 再回滚的顺序已明确。 |
| I4 同名集合失效 | 已解决。§3 行 85、93–97 分开单行资格与有限 exact/shared 授权；由实际 OLD/NEW 原值进入 dirty，再按 Python 原 normalizer 形成完整 token 闭包，覆盖不合资格 verified C。保留 SQL exact/lower 与 normalization 的区别，并要求在线实际命中 owner 集合与授权集合一致。Task 2 行 187、190 给出聚焦 A/B/C 和 old/new token 回归。 |
| I5 详情覆盖域 | 已解决。§2 行 76、§3 行 87、Task 3 行 211、Task 5 行 256–260 将所有原详情可读 album 纳入准备/失效/覆盖预算，包含 hidden/duplicate；列表过滤不变，原 record 不存在才保留 404，并有对应详情回归。 |

非阻塞整理也已落实：请求轮次语言继续轻量在线格式化（行 99），phase/cursor 与批提交原子持久化（行 257），100 QPS 的实际入口接收门禁与发生器排队分列（行 280）。六表和独立 MetaData 未扩成通用基础设施。

本轮计划审核到此结束，不进行第三轮。可交回用户确认性能口径与后续实施范围；Approved 不表示功能已经实现、性能已经达标或本轮获准执行发布。
