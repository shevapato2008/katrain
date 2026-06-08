# 对弈付费分析 + 积分充值(kiosk + galaxy)· 需求

> Track: `sbc-pure-play-remote-analysis` · 2026-06-05 由 RK3562 板上实测推导出最初问题,
> 2026-06-07 经需求讨论扩展为「对弈分析按次付费 + 积分充值」产品。分支 `feature/rk3588-ui`。
> 本文件是**最终需求(WHAT)**;可执行实现计划见同目录 `plan.md`(HOW)。

## 1. 背景

- RK3562 kiosk(弈航)本地引擎 = `realtime_api`(:8000,HTTP 包装 `katago analysis`),
  **b6c96 主网 + b18c384nbt-humanv0 人类副网**,Mali-G52 OpenCL FP32,`numAnalysisThreads=1`(单线程)。
- 拟人 AI 落子链路已通:`HumanStyleStrategy` → `overrideSettings.humanSLProfile`(如 `preaz_6k`)→
  人类网 policy 出招,**1 visit ≈ 1.2–1.4s/步**。
- 板上 katrain 引擎配置(`~/.katrain/config.json` → engine):
  `backend=http, http_url=http://127.0.0.1:8000, max_visits=1, fast_visits=1, http_has_human_model=true`。

## 2. 起因问题(2026-06-05 实测实锤)

对弈模式(`MODE_PLAY`)下,katrain web 会对**每个新节点自动发 eval 分析查询**:

- 特征:`priority: 1002`,带 `includeOwnership: true, includeMovesOwnership: true`,
  `overrideSettings: {wideRootNoise: 0.04, maxTime: 8.0}`,`analyzeTurns: [N]`;
- **与前端「图表」按钮无关** —— 图表全程关闭仍照发(图表只控显示,不门控后端);
- 它们与 AI 落子查询(`priority: 10002` + `humanSLProfile`)**抢同一个单线程本地引擎** → 排队,
  AI 每步 wall-clock 9–12s(落子查询本身仅 ~1.2s)。

单条查询实测(板上 :8000,uncached 局面):

| 查询 | 耗时 |
|---|---|
| b6c96 主网 + ownership | **162ms** |
| humanv0 人类网 + ownership | **1198ms** |
| 任一网 无 ownership(cached) | 19ms |
| 游戏内任意查询 wall-clock | **9–12s(= 队列,非计算)** |

日志取证:`journalctl -u smartbox-katrain | grep "Sending KataGo HTTP analysis query"`,
看 payload 里的 `priority` 与 `humanSLProfile` 有无。

## 3. 产品决策

**对弈中的 AI 分析(领地/支招/变化图)从"免费且自动"改为"按次付费、用户主动触发"**,
对标星阵围棋(19x19)的道具消费模型。两端(kiosk + galaxy)行为统一。

1. **对弈 = 纯下棋**:对局中本地引擎默认只服务 AI 落子(人类网 1 visit),**不做任何自动 per-node eval**。
2. **分析按次付费**:领地、支招(=建议)、变化图 默认关闭,用户点击才执行一次,每次扣积分。
3. **积分服务端权威**:积分余额/扣减以**云端服务器**为准。kiosk 是 shadow-user 转发远程登录,
   联网时实时读/扣;**离线时付费分析禁用并提示需联网**。
4. **引擎拆分只在 kiosk**:kiosk 把付费分析路由到**远程强引擎(b28 GPU)**;
   galaxy 本就跑在强引擎服务器上,付费分析**复用自身引擎**,不拆分。两端共享"积分系统 + UI 改造"。
5. **排位局全禁分析**(galaxy + kiosk 一致,反作弊):付费分析**只在自由对弈/非排位局**开放;
   排位局全程禁用所有分析控件。
6. **对弈页移除胜率图表**:图表只在复盘报告中出现。
7. **充值架构一步到位、真支付留插槽**:订单 + 流水 + `settle()` 入账生命周期现在就做对;
   本期用 ManualConfirm Provider(个人收款码 + 人工核对)+ 兑换码上线;
   微信/支付宝商户网关留成空壳 Provider,个体户/公司注册后插入,业务层不返工。

## 4. 需求

- **R1 抑制自动 eval(性能)**:kiosk 对弈(`MODE_PLAY`)下抑制 per-node 自动 eval 分析,
  门控用 `KATRAIN_MODE`(kiosk 模式);本地引擎每步只收一条 genmove(HumanStyle)查询。
- **R2 积分单池系统(服务端权威)**:
  - 复用 `User.credits`(单一余额);新增积分流水表(扣分=分析消费 / 加分=充值·兑换码)。
  - API:查余额、扣分(**原子 + 幂等**)、加分;每个付费动作单价由 config 配置(领地/支招/变化图)。
- **R3 对弈页付费分析改造(kiosk + galaxy 共享逻辑)**:
  - 领地/支招/变化图 默认关;按钮右上角徽标显示"还能用几次 = ⌊余额 / 单价⌋"。
  - 点一次:余额够 → 扣分 + 执行一次分析(kiosk 走远程、galaxy 走自身)→ 一次性展示结果(不再自动持续)。
  - 余额不够 → 弹"道具用尽 / 充值"弹窗(仿 19x19)。
  - 数子(规则数子)、悔棋 / 停一手 / 认输 免费。
  - **排位局**:上述控件全程禁用(置灰),不可付费触发。
  - kiosk 断网:付费分析禁用并提示需联网。
- **R4 对弈页移除胜率图表**:图表只在复盘报告显示;对弈页不留死控件 / 持续 loading。
- **R5 充值模块(可插拔 Provider)**:
  - 订单 + 流水 + `settle()` 入账架构(真实支付生命周期)。
  - 本期 Provider:ManualConfirm(个人收款码 + 用户提交凭证 + 管理员确认到账)+ 兑换码。
  - 预留 WeChatPay / Alipay Provider(统一下单 + webhook),注册资质后插入。
  - 充值页面(参考 19x19 充值模块)。
- **R6 远程引擎打通(不计费)**:
- **R7 抑制开关解耦(离线可测)**:eval抑制 不得依赖 board 远程瘦客户端模式;新增独立开关 `KATRAIN_SBC_PURE_PLAY`,使板子在 `server` 模式(本地登录可用)下也能抑制 eval。详见 `R7-decouple-suppress-from-board.md`。
- **R8 HTTP 引擎去 per-query spawn(性能·主因)**:`engine.py:_post_json` 每条查询用 `multiprocessing spawn` 起子进程(重 import 整个 server,RK3562 ~9s/步)。改用线程/async httpx,使每步落子 ≤~2s。详见 `R8-http-engine-per-query-spawn.md`。
  - 新增可配置 `engine/remote_url`(realtime_api 协议,`humanSLProfile`/`overrideSettings` 透传)。
  - kiosk 付费实时分析 + 复盘 → 远程 b28(**b28 未部署,本期按可配置 URL 开发**,用本地 :8000 或 mock 验证链路)。
  - 复盘报告**本期不计费**,只打通远程引擎能出报告。
  - galaxy 复用自身引擎,不拆分。

## 5. 数据 / 架构要点(已查实)

- **积分系统现状 = 纯 stub**:`models_db.py:39` `credits = Column(Float, default=10000.00)` 存在但
  零业务逻辑——从不扣减、不能充值、无流水/订单表、无支付集成、无相关 API。需从零搭流水/订单/Provider。
- **kiosk 按用户登录**(非共享终端):shadow-user 转发远程登录 + 本地 JWT(`auth.py:84-132`,
  shadow `hashed_password="SHADOW_USER_NO_LOCAL_AUTH"`)。积分可归属具体用户。commit `971da4f` 修复了登录时序。
- **双引擎 = 半成品**:`web/core/router.py` 有骨架(按 `is_analysis` 路由)但未接进 server/interface;
  HTTP 引擎客户端 `KataGoHttpEngine`(`engine.py:539-787`)本身完整——支持 ownership/policy、
  `extra_settings`→`overrideSettings.humanSLProfile` 透传、`/health` 探测 `has_human_model`。缺编排层。
- **自动 eval 触发点**:`core/game.py:560` `played_node.analyze(...)`(PRIORITY_DEFAULT=1000),
  以及 `analyze_extra("ponder")`、teaching `analyze_undo`、新局/载入 `analyze_all_nodes`。
- **对弈控件**:两端经 `POST /api/ui/toggle` 切 `show_*` 标志(`interface.py:884-898`,状态在
  `get_state().ui_state`)。galaxy 已有 `canShowAnalysis`(rated + not over)门控,正好作改造挂载点。
  kiosk 控件 `kiosk/components/game/GameControlPanel.tsx`;galaxy `galaxy/components/game/RightSidebarPanel.tsx`;
  棋盘渲染共享 `components/Board.tsx`。
- **SBC 构建边界**:kiosk 走 `static-kiosk-2d/`,改动须遵守 `CLAUDE.md` 的 kiosk 隔离契约
  (`src/kiosk/**` 不得 import galaxy/Board3D;积分/充值的共享逻辑放共享 territory)。

## 6. 验收标准

1. kiosk 对拟人 AI:落子后 AI 响应稳定 **≤ ~2s**(humanv0 1visit ~1.3s + 余量)。
2. 对弈期间 katrain 日志中,本地 :8000 **只出现 genmove 查询**(无 priority-1002 自动 eval)。
3. 自由对弈:领地/支招/变化图 默认关,徽标显示可用次数;点一次正确扣分并出一次结果;
   余额不足弹充值弹窗;扣分**原子且幂等**(并发/重试不双扣)。
4. **排位局**:两端所有分析控件全程禁用,无法付费触发。
5. 对弈页无胜率图表;无失效控件 / 持续 loading。图表仅在复盘报告出现。
6. 充值:管理员加分 / 兑换码生效,余额实时反映;ManualConfirm 订单 pending→paid→入账闭环可走通。
7. 远程引擎:配置 `engine/remote_url` 后,kiosk 付费分析与复盘查询发往远程 URL(日志可证);
   未配置时回退本地;galaxy 行为不变。
8. 回归:关闭付费门控 / 非 kiosk 模式时,galaxy 既有对局与分析行为与基线一致。

## 7. 本期不做(Non-goals)

- 真实微信 / 支付宝商户网关(资质未办)——只留 Provider 接口与 webhook 路由空壳。
- 复盘报告计费——本期仅打通远程引擎出报告。
- 双层"星币 + 道具次数"模型——用单池积分 + 单价替代。
- b28 GPU 远程引擎的部署——本期按可配置 URL 开发,部署后填 URL 即可。

## 8. 参考

- `docs/dual-engine/PRD-katago-dual-engine.md` —— 本地+云双引擎(复盘走远程的既定方向)。
- `docs/human-model-support/` —— HTTP 引擎人类模型协议(`/health` 报 `has_human_model`、
  `overrideSettings.humanSLProfile` 透传);**服务端 realtime_api 已全部实现**。
- 板侧服务与配置:`smartbox-software/provisioning/`(`configs/realtime_api.yaml`、
  `systemd/smartbox-katago-api|katrain|kiosk.service`)。
- 消费模型对标:星阵围棋(19x19)对弈页道具(领地/支招/变化图)+ 充值(星币)。
