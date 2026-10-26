# Astra 独立部署后真实数据/API审核（2026-10-26）

**结论：Approved，限本轮 23 盘 rank-only 纠正、当前有限公开页和两云后台运行范围。未发现本范围 must-fix。** 本结论来自部署完成后的新一轮只读查询与公开 GET，不沿用前一版 Approved，也不代表全历史补齐、设备视觉验收或新 source 首次插入已实证。

审查对象为 source `e9b4d3ecce03b3269f12922a476fd6d6c6545547`。独立取证窗口为 **2026-10-26 10:49–11:01 UTC**；关键数据库比较取于 10:55:16/17，公开 API 于 10:56–10:58，调度于 10:57:47，运行文件于 10:59:44/11:00:45。遵守适用 AGENTS 和 `kifu-album-sync`：只读 SQL 均设置 READ ONLY 与有界 statement timeout；未运行 publish/verify/import/translate/job、未改 DB/锁/调度/迁移/服务，未访问 SGF 文件目录、private games 或 Chat，未导航或重启 RK。唯一写入为本报告。

**四个红框与原谱优先**

独立查询 TEST/PROD 三个精确 album 的五语言详情，并检查原生快照、原始 SGF 哈希及库内等级来源。两端最终均通过；TEST 芮乃伟中文 GET 首次网络错误后仅重试一次，成功。

| 截图棋手/侧 | source ID | TEST / PROD album | 实际 display / origin | 库内明确等级来源与 as-of |
| --- | --- | --- | --- | --- |
| 於之莹 / 白 | 91635363 | 179081 / 178745 | 8p / library_current | 90638040，白方八段，2026-10-03 |
| 芮乃伟 / 白 | 91634842 | 179080 / 178744 | 9p / library_current | 91284543，黑方九段，2026-10-15 |
| 党毅飞 / 黑 | 91632021 | 179079 / 178743 | 9p / library_current | 90903437，黑方九段，2026-10-09 |
| 辜梓豪 / 白 | 91632021 | 179079 / 178743 | 9p / library_current | 85428764，白方九段，2026-07-19 |

原三盘比赛日均 2026-10-24，原 raw rank 仍为 null；API 中 fact/snapshot SHA、来源引用、as-of 与冻结记录一致，`valid_from=null`。独立对两库本轮 40 条新增事实逐条查其精确来源 SGF：owner FK、整谱 SHA、BR/WR 与 raw rank、日期均一致。数值来自原谱，官方 profile 用于职业身份资格；as-of 是来源资料日期，不是升段日或当局段位。

原谱优先另用 TEST album **178908** 实际 GET 验证：白方上野梨纱仍显示原谱“三段”，`white_rank_origin=source`、`white_rank_source=null`，没有被当前其他谱中的 4p 覆盖。见原发布[主包 TEST 验证](main/test-verification.json)、[PROD 验证](main/prod-verification.json)。

**两包、跨库映射和原记录保护**

| 冻结纠正包 | 盘数 / 新增事实 | TEST / PROD native batch | Stage 实际 canonical manifest SHA |
| --- | --- | --- | --- |
| rank-only-page-coverage-20261026-v1 | 18 / 32 | 938 / 931 | `7abc3136e13992127caf98bf670f6aa92e72b6651ca2f5092c3add8b9d549f44` |
| rank-only-current-page-tail-20261026-v1 | 5 / 8 | 939 / 932 | `133dc7ae199afd5a3b692a45d2edff05480709753c910652354aeb45438254ce` |

独立读取 TEST 持久 stage 两份完整 manifest，仅输出哈希和数量；两库原生 `KifuNameBatch` 均 applied，保存 logical manifest、rank bindings 和 receipt。两端 logical manifest 摘要分别同为 `e55731cfb0f1100e81125ea6abb01d28b732becd68d0466540a53b70f92fd03f`、`fd0e0e4426335246c7029101e19d28c090562fafe70ec33564e4e89129e348e4`；这些是 native logical representation 的摘要，不混称完整冻结 manifest 的摘要。各端 receipt 指向其本地 album/FK，未假定两库 ID 相同。

23 盘的原 SGF hash、album ID、双方 FK、原 raw rank、所取业务字段、source links，以及八个原 native artifact 摘要，均独立对照 after 记录一致；未另行比较派生 `search_text`。23 个 StateStore 完整行摘要也与 after 记录逐条相同，全部保持原 publication key 和 `prod_synced`。本轮读取到两库均 history=46、snapshot=54，其中 library_current=46、unknown=8。维护内总 album_count=176884 与 6→38→46、22→54→54 的前后变化，以[主包 TEST](main/test-integrity.json)、[PROD](main/prod-integrity.json)、[尾包 TEST](tail/tail-test-integrity.json)、[PROD](tail/tail-prod-integrity.json)的冻结比较为据；未重新扫描全库计数，也不把恢复后的自然任务变化纳入该不变量。

两包 stage 的 scope/apply/verification/replay 六类文件 canonical 摘要，逐个与本证据目录一致。原生 receipt SHA 同时匹配验证绑定：

| 包 | TEST receipt SHA | PROD receipt SHA |
| --- | --- | --- |
| 主包 | `4096960d299bfe76450790d5688d8da206c59992703d07eb6fc891c0dd7dabb1` | `860f53cbf925df34f9e61c384c82fb34c6dd375844926389447f1bf2f169f7ee` |
| 尾包 | `9b2f08087f6abea15a2ff4feeaeef33b7bceb8a798521b8cc6dc9197dc3cb34f` | `152a1dc4777e14f931bd98bc3cc4075bfc0edfab0e997db18a3f8bb66ca9cd49` |

主包双端各 90 条五语详情/18 张卡、尾包双端各 25 条详情/5 张卡的完整验证记录均 verified。两次实际 replay 记录均为同 native batch、双端 receipt identical；本审核核对这些记录与当前 native receipt，没有再次执行重放。见[主包 replay](main/replay-result.json)、[尾包 replay](tail/replay-result.json)。

尾包前的原两盘 `91741775/91742836`，独立查询原 batch `19x19-batch-19caaa5732be98c16944f87e`：manifest SHA 仍为 `5e89c7bd689de0fd9453301f4322c67a2156819572a5959b4826497a03ce52bd`，当前 status=prod_synced、attempts=0、updated_at=10:15:35。数据库保存的 TEST/PROD 原 verification 各 verified、10 条详情、2 张卡；原 receipt 和原 artifact 保持原绑定。这与[原续验记录](tail/original-recovery-result.json)的 prod_published→prod_synced、publication_calls=0、translation_calls=0 相符，不能只凭状态字段称成功；本次并未重新发布原包。

**尾包和剩余空位**

PROD 尾部五盘各做一次中文 GET，结果与两端数据库快照及冻结验证相符：

| source ID | 黑方 | 白方 |
| --- | --- | --- |
| 91740418 | 大竹优 7p，as-of 2026-07-16 | 小西理章 4p，2026-09-14 |
| 91740570 | 羽根直树 9p，2026-10-19 | 田中伸幸 5p，2026-10-12 |
| 91741359 | 赵治勋 9p，2026-10-01 | 许家元 9p，2026-10-19 |
| 91741775 | 金恩持 9p，2026-10-14 | 仲邑菫 unknown |
| 91742836 | 池本辽太 unknown | 六浦雄太 8p，2026-09-17 |

10:56 的 TEST/PROD 公共第一页各 20 盘、**34 侧有值 / 6 侧为空**，名单与[当前页冻结记录](current-public-page.json)一致。API total=176625 是公开可见口径，不应与数据库总 album_count=176884 混用。

- 金泽秀男：source91740310 黑方 FK 实际为 null；该盘不在两个纠正 scope 中。
- 同盘孙喆：独立 lookup 为 qualified 8p，来源 **90521056 白方、2026-10-01**。保留空位是现行纠正工具要求整盘双方已有稳定身份，不能称“孙喆无资料”。
- 萧钰洋：`professional_identity_unverified`。
- 李小溪94：`no_verifiable_raw_rank`，没有混用李小溪05。
- 仲邑菫、池本辽太：两人各五条 approved 且独立模型审核的姓名 evidence；本审核完整读取 payload 并递归检查全部字段，均无 body capture 对象，也无其它可替代的可复验官方主体捕获，当前 official proof lookup 为空。因此“名字有五语审核但职业证据不足”的表述成立，不能按知名度猜 p/d。见[证据计数](tail/tail-identity-evidence-counts.json)。

初始固定页内另两项也独立确认：鸟井裕太为 `professional_identity_unverified`；李小溪05 为 `official_grade_above_library_grade` 冲突。未用过时一段补值，未从 profile 直接写六段。这里确认的是当前绑定证据的可用性，不是宣称这些人现实中没有职业身份或等级。

**运行版本、恢复和预算**

| 组件 | 独立 docker inspect 的 image | 运行 / build | 独立文件核对 |
| --- | --- | --- | --- |
| TEST web | `sha256:85391af74060372fb0558ca35703f9b1fad16f23cea681cc7f4e6e67073c816e` | running；build=e9 | 97 个 runtime/active-asset 路径与发布回执相符 |
| TEST producer | `sha256:9604d05e4e096b4c97966e6c850492c87d60fe9fff1039c3fe94f67af081c08d` | running；build=e9；ingest enabled | 39 个 runtime 路径的文件或预期缺失状态相符 |
| PROD web/receiver | `sha256:f90b1526e8ec9375e3f0021a478b7a546fbf3026f6268b2b331adf97289b5355` | running、healthy；build=e9 | 97 个 runtime/active-asset 路径相符 |

上述三者源文件包括本轮实际变化的 player_ranks、rank correction、ingest ranks。两 web 的活动静态入口图匹配原部署回执；完整静态映射继承 93f 的保护记录见[TEST](cloud/web-deployed.filtered.json)、[PROD](cloud/prod/web-deployed.filtered.json)。本次没有新 UI 构建，也没有把 RK 图标版本 469 等同于 e9 全量设备部署。

两主机均无 `kifu-rank-lock-*` 容器。TEST 仅一套 katrain-cron，ingest enabled；PROD 原分析 cron 仍 running、启动时间 2026-10-10T18:04:39Z、ingest disabled，未发现第二套启用的 producer。10:57:47 查询 control=[]、enabled=true、interval=3600、heartbeat=10:57:42、consecutive_failures=0。自然 run **77942 已于 10:44:21 success、error_count=0**，此次审核没有触发或等待它。它的成功不证明存在新 source 首次 insert。

配置预算独立读取为 window7、head5、HTTP160、SGF100、source600s、recovery300s、total3300s、tokens100000。硬上限及 3300 协作预算、无可靠 updated_at、有限 head 覆盖、无 rolling 历史热回扫的边界仍按发布说明保留；未通过触发任务来验证预算截止。

**非阻塞观察与未证范围**

1. PROD `/api/v1/health` 在 10:56:37 返回 HTTP200/status=ok，但 local engine=unreachable；仅一次有界复查于 10:58:51 返回 reachable。期间公开棋谱 GET 均成功，容器 healthy。按用户范围没有操作 GPU 或展开排障，不把该短暂结果掩饰为始终正常。
2. TEST 的两次初始 URLError（芮乃伟中文、原谱优先样本）各仅重试一次，均 HTTP200；没有重跑整套 API 或测试。
3. 双端 `/galaxy/kifu` HTML 返回 HTTP200，SHA 同为 `ead7fb34d9a6b8efed6bd5b1180e8f87902c3b2b11c5d15138b4251681467e0d`。本审核没有浏览器渲染/截图或 RK 操作，故只确认实际公开 API、入口和静态依赖相容，不声称已独立重做设备视觉验收。
4. 未重新跑 146/392 测试、访问官方站点采新证据、调用模型或扫描全库。Git 发布链及父仓库 gitlink 取发布记录为依据，本审核独立确认的是实际运行镜像、build 和文件。完整官方主体解析的代码审查由另份 fresh code audit 覆盖，本报告的 Approved 不代替它。
5. 旧 v2 unknown snapshot 经授权纠正后，旧包再提交会 fail closed；本审核没有重发旧包，也不声称所有历史包在后续纠正后仍可原样重放。此次确认的幂等对象仅为上述两个冻结 correction。
6. 23 盘既有谱纠正和恢复原两盘续验已证实；e9 首次插入全新 source、全七天/全历史覆盖、2021 旧失败恢复、3300 秒硬截止和零空位均未被本轮实证。六个当前空位及两个初始页未知/冲突是明确保留的数据边界。

审核人：本轮 fresh 独立 Astra 审核代理。最终只读证据与当前交付说明一致；以上范围批准，非阻塞边界应随交付保留。

