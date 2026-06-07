# 计划审核 Prompt(发给 Codex / Gemini)

> 用途:把本 prompt + `requirements.md` + `plan.md` 一起发给独立审核方(Codex CLI 有仓库访问;
> Gemini 若无仓库访问,凭本文「精简上下文」也能审)。目标:**找问题、提改进建议**,不是夸。

---

## 你的角色

你是一位资深全栈 + 平台架构师,要对一份"围棋对弈应用增加**对弈分析按次付费 + 积分充值**"的
需求与实现计划做**对抗式评审**。请挑刺:架构缺陷、正确性漏洞、安全风险、边界遗漏、排期不合理、
测试不足、过度设计或欠设计。每条结论都要可执行(指出位置 + 给出具体改法)。

## 要读的文件

1. `superpowers/tracks/sbc-pure-play-remote-analysis/requirements.md` —— 最终需求(WHAT)。
2. `superpowers/tracks/sbc-pure-play-remote-analysis/plan.md` —— 实现计划(HOW,7 阶段)。

(若你能访问仓库,请同时核对计划里引用的代码:`katrain/web/interface.py`、`katrain/core/engine.py`、
`katrain/core/game.py`、`katrain/web/core/models_db.py`、`katrain/web/core/auth.py`、
`katrain/web/core/config.py`、前端 `katrain/web/ui/src/{kiosk,galaxy,components,context,hooks}/`。
确认计划描述与真实代码一致——如有不符请指出。)

## 精简上下文(无仓库访问也能审)

- **产品**:KaTrain(Go/围棋 + KataGo 引擎)。双 UI:**galaxy**(云端全功能 web)、**kiosk**
  (RK3562/3588 单板机终端,精简 2D 构建 `static-kiosk-2d`,**不含 three.js / galaxy 路由**)。
  两 UI 共享 `katrain/core` 与部分前端「shared territory」。`KATRAIN_MODE ∈ {server, board}`,
  board=kiosk。
- **起因**:kiosk 本地 KataGo 单线程(Mali GPU 弱)。对弈中前端对每个新节点自动发 eval 分析
  (带 ownership),与 AI 落子查询抢同一引擎 → AI 每步 wall-clock 9–12s(实际计算仅 ~1.2s)。
- **产品决策**:对弈中的 AI 分析(领地/支招/变化图)从"免费自动"改为"**按次付费、用户主动触发**"
  (对标星阵围棋 19x19 的道具消费)。两端统一。对弈页移除胜率图表(只在复盘报告显示)。
  **排位局全程禁所有分析**(反作弊),付费分析只在自由对弈开放。
- **关键既有事实**:积分=纯 stub(`User.credits` float,默认 10000,零业务逻辑);**无 alembic**,
  `Base.metadata.create_all` 自动建新表;kiosk 是 shadow-user 转发远程登录(**按用户**,非共享终端);
  rated 目前**仅前端 URL param**,后端不知情;HTTP KataGo 引擎客户端完整(支持 ownership/policy、
  humanSLProfile 透传、/health 探测)。
- **本期范围**:R1 抑制 kiosk 自动 eval / R2 积分单池服务端权威(原子+幂等)/ R3 对弈页付费分析改造
  (两端)/ R4 移除对弈图表 / R5 充值模块(可插拔 Provider:本期 ManualConfirm 个人收款码人工核对
  + 兑换码,微信/支付宝留空壳)/ R6 远程强引擎打通(可配置 `engine/remote_url`,不计费,b28 未部署)。
- **硬约束**:① 没有公司/个体户注册,无法做合规自动化微信/支付宝收款(只能人工核对过渡);
  ② b28 GPU 远程引擎未部署,按可配置 URL 开发;③ kiosk 可能离线(积分/远程分析需联网);
  ④ 积分余额必须**服务端权威**(客户端不可信)。
- **决策(已定,但欢迎质疑)**:积分用**单池**(一个余额,每动作按单价扣)而非双层"星币+道具次数";
  支付**架构一步到位**(订单+流水+settle 生命周期)但**真扣款用 ManualConfirm 过渡**。

## 请按以下维度审,逐条给问题

1. **架构**:单池积分 vs 双层道具,服务端权威的落地是否到位?Provider 抽象 + ManualConfirm→真网关的
   迁移路径是否真的"不返工"?双引擎编排(play_engine / analysis_engine)是否合理?
2. **正确性 / 并发**:`spend` 的原子性与幂等(`ref_id` 唯一键)在 SQLite/Postgres 下是否真能防双扣?
   失败退款、超时、重试、断网、用户狂点按钮的竞态有没有漏?ref_id 生成方式(`session:node:kind:nonce`)
   会不会"换 nonce 即可重复触发同一节点扣多次"——这是 bug 还是预期?
3. **安全 / 反作弊 / 反薅羊毛**:排位局禁分析是否真在**服务端**强制(不止前端置灰)?积分能否被客户端
   篡改?管理员接口鉴权?兑换码爆破/重用?ManualConfirm 凭证伪造?webhook 空壳上线后接真网关时的
   验签与重放防护是否预留?
4. **排期 / 可交付**:7 阶段的依赖与顺序对吗?哪些能更早独立上线?阶段 5 前端是否被阻塞过久?
   有没有"大爆炸集成"风险点该再拆?
5. **测试充分性**:每阶段测试能否覆盖关键风险(尤其并发扣分、退款、rated 服务端门控、kiosk-2d 构建闸)?
   缺哪些用例?
6. **产品 / UX 边界**:"还能用几次=⌊余额/单价⌋"的徽标语义、余额不足弹窗、移除对弈图表、离线提示
   是否自洽?单池下"余额兑换"被简化为"去充值"合理吗?
7. **领域特定(KaTrain/KataGo)**:抑制自动 eval 是否会误伤教学/ponder/复盘/载入分析等合法路径?
   付费"跑一次分析"用现有 `analyze_extra`/单发查询是否恰当?humanSLProfile/ownership 透传无误?
8. **遗漏 / 风险**:有没有需求或计划没覆盖但会在上线时爆炸的点(迁移、回退开关、多端余额一致性、
   退款审计、i18n、kiosk 离线降级、b28 不可用降级)?

## 输出格式

给一个发现清单,每条:

```
[严重度: Blocker/High/Medium/Low] <一句话标题>
位置: <requirements/plan 的章节 或 文件:行>
问题: <为什么是问题,会导致什么>
建议: <具体怎么改>
```

最后附:
- **Top 3 必改**(不改会出事的)。
- **可砍/过度设计**(本期能省的)。
- **一句话总体判断**:这个计划能否照着干?最大的单点风险是什么?
