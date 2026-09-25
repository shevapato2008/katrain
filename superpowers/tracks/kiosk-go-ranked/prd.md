# RK3562 围棋升降级对弈：结算、数子与正式环境

- 日期：2026-09-25
- 设备：RK3562，1024×600，`rk3562` / 主机名 `gzpeite`
- 代码基线：`origin/develop` `fdf7fa39e4a619e4f88e18768857d295c37c1b2e`
- 状态：领地判断 1024×600 设计已获用户确认，进入前后端开发

## 现场事实

2026-09-25 的对局 `444c434ffc4c4474b4c5eeac4084bb87` 因识别延迟超时，本机保留 151 手、`W+T`。盒子在 14:32:10 向 `go.sailorvoyage.top` 报告待结算成功，14:32:47 上传结算收到 HTTP 422：`game_record SGF player_black does not match`。提交的结构字段有 `player_black=fan`、`player_white=20级`，SGF 根却没有 `PB`、`PW`。盒端 `sync_queue` 将 422 记为永久失败；home 云端仍占着 `pending_settlement`，未写入 `user_games` 或 `ai_ladder_game_ledger`。

现有数子路径要求当前手已有分析分数；升降级局的 `analysis_allowed=False` 阻止补算，所以本盘虽超过 100 手仍无法数子。结算失败退出后，设置页仍显示“认输那一局，在这里开新局”；这会以 0 手认输替换真实结果。应避免用户把已结束棋局当作未结束棋局再次认输。

目前 `go.sailorvoyage.top` 经阿里云网关到 `home-ubuntu:8001` 测试服务。UCloud 正式库 `katrain_prod_20260725` 与 home 测试库 `katrain_db` 都有 `ai_ladder_profiles`、`ai_ladder_pending_games`、`ai_ladder_active_games`、`ai_ladder_game_ledger`、`user_games`、`sync_queue` 六张表，列结构相同。home 上该账号已有 7 条升降级账本，UCloud 为 0。用户已决定**不迁移历史成绩，也不迁移今天这盘**，切换后只让新局进入正式库。

## 同步路径与故障位置

1. 盒端向当前 `KATRAIN_REMOTE_URL` 调 `POST /api/v1/ai-ladder/games/reserve`，云端在 `ai_ladder_active_games` 留一个 `reserved` 占位并按云端 `ai_ladder_profiles` 选对手；盒端在本机 SQLite `ai_ladder_pending_games` 保存同一 `game_id`、冻结对手与预约凭证。
2. 盒端建局后调 `POST /api/v1/ai-ladder/games/{game_id}/activate`，云端占位转为 `active`。终局后盒端把真实棋谱和结果先写入本机 `user_games` 与本机升降级账本，再调 `pending-settlement`，云端转为 `pending_settlement`；本机 `sync_queue` 以 `ladder-settlement:{game_id}` 唯一键排队。
3. 同步 worker 用登录用户的 token 向该 URL 调 `POST /api/v1/ai-ladder/settlements`。云端验证预约凭证、冻结规则、结构化成绩与 SGF 根节点，再在同一事务中写正式 `user_games`、`ai_ladder_game_ledger`，更新 `ai_ladder_profiles`，删除 `ai_ladder_active_games` 占位。成功回执使本机队列变为 `completed`，并采纳云端段位档案。云端 `sync_queue` **不参与这条即时收件路径**。
4. 本盘卡在第 3 步的验证阶段：SGF 缺 `PB/PW`，因此 HTTP 422，云端事务没有写棋谱、账本或段位，也没有删除待结算占位。本机队列把 422 记为永久失败；只点重试不能改变旧 payload。正式环境切换前须隔离该测试队列，不能将它重放到 UCloud。

## 目标与验收

1. home 测试部署包含最新 `develop` 提交；UCloud 的发布分支保留专用部署文件并包含同一最新 `develop` 提交。两端服务健康，数据库可支持预约、数子裁判结果、棋谱和账本的原子结算。
2. RK3562 新建升降级棋局的身份认证、预约、待结算和结算都指向 UCloud 正式环境。通过一次新的测试对局的服务端收据和正式库对应行验证。旧测试库的历史和本盘不搬迁；切换必须避免旧 outbox 向正式库重放和旧测试预约挡住正式新局。
3. 用户已确认：按中国规则由云端 AI 判定，允许满 100 手后主动数子结束。服务端须确认同一局面，私下取得云端裁判分数，形成明确胜负并进入同一结算流程；计算结果是未完全收官局面的 AI 判断，终局文案须如实说明。分析不得在终局前泄露；计算失败要保留未结束状态和可理解的错误。双 pass 的自动收尾遵循同一裁判原则；失败时不得以“无结论”偷落账。
4. 新升降级结果的 SGF 根节点包含与结构字段完全一致的 `PB`、`PW`、`RE`、`RU`、`SZ`、`KM`；云端仍严验数据，不能放松校验来掩盖盒端缺字段。
5. `pending_settlement` 不再呈现为“再认输”。已结束但送达失败时先展示真实终局和可行的重试；保留显式的“放弃未送达成绩，按负局了结”逃生口，写入的是云端该 game_id 的**唯一**负局墓碑，真实棋谱可能被合成弃权记录替代，必须在二次确认中说清楚。它不代表在棋盘上再次认输。已结算局不出现阻挡新局的动作。
6. 只读审查 `smartbox-software` 中国际象棋、中国象棋、五子棋的升降级云端地址、身份地址、结果发送与失败状态，报告是否有相同测试/正式环境混用问题；不改该仓代码。
7. 领地判断：1024×600 独立 HTML 预览已获用户确认。升降级棋局由云端 KataGo 返回当前盘面的黑白归属，仅作局中参考，不作为正式胜负；每局最多成功请求 3 次，显示剩余次数、请求中、结果、失败和用尽状态。领地、数子、停一手沿用星阵对弈的 `grid-nine`、`squares-four`、`hand-pointing` 图标。移动后清除旧局面覆盖层；请求失败不扣次数，重试不得重复扣次。

## 范围和约束

- 数子属于终局裁判，领地判断属于局中参考。两者不能共用“允许玩家看到分析”的权限；计数和服务端资源限制分别处理。
- UCloud 的发布结构来自 `release/ucloud-20260805`，不能将纯 `develop` 目录直接覆盖生产发布；保留 Compose、密钥和数据卷。生产库操作先备份、核对迁移差异并保留回滚锚点。
- 当前测试局及测试段位不进正式库；正式库从既有账号的初始定级开始。
- 其他棋类仅调查和报告。领地判断设计稿确认是开发该功能的硬门槛。

## 其他棋类只读核查

| 棋类 | RK3562 当前实际目标 | 结算代码路径 | 结论 |
|---|---|---|---|
| 国际象棋 | `SMARTBOX_RANKED_ORIGIN=https://ranked.sailorvoyage.top`；大厅为 `https://lobby.sailorvoyage.top` | `setup-wizard/app/services/lobby_bridge.py` 向 ranked 的 `/api/v1/ranked/chess/games/{id}/settle` 提交 | 升降级仍走测试环境；与围棋有同类目标环境问题，非本次代码修改范围。 |
| 中国象棋 | `XIANGQI_RANKED_CLOUD_BASE_URL` 默认跟随上述 `SMARTBOX_RANKED_ORIGIN` | `xiangqi/api/xiangqi_api/ranked_sync.py` 维护本机结算 outbox，经 setup-wizard ranked proxy 发往 ranked 服务 | 默认同样走测试环境；未发现它调用围棋 `/settlements` 的证据。 |
| 五子棋 | `GOMOKU_RANKED_CLOUD_URL=https://ranked.sailorvoyage.top` | `gomoku/api/gomoku_api/ranked_cloud.py` 向 `/api/v1/ranked/games/{id}/settle` 提交 | 同样走测试环境；与围棋共用盒子登录身份，但升降级账本不在 KaTrain 数据库。 |

以上是配置与代码路由核查，不代表已经复现这三类棋各自的对局结算故障。`smartbox-software` 代码未修改。

## 待实测确认

- RK3562 到 UCloud 正式 API、身份 API 和私有 KataGo 分析端点的真实连通性及证书/权限；据此选定数子的云端计算路径。
- 切换后本机旧预约、会话和所有状态的旧 outbox 的隔离或归档方式，以及新局的实际启动情况。队列只存相对路径，切换目标前必须停掉 worker 和恢复入口。
- UCloud 部署最新 develop 对现有发布分支的合并冲突、迁移影响和磁盘余量；生产根分区目前只有约 16 GB 可用，需要按实际发布峰值评估。
