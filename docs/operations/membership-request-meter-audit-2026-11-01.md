# 按请求统一计量：源码与测量输入核查

2026-11-01。仅为本次价格／额度方案修订提供源码证据；没有修改产品、访问数据库或 GPU、重启服务或执行发布。V100 当前实际测试由主代理单独完成。这里的旧性能记录不是本次实测，也不能替代容量验收。

## 实际请求与商品边界

- 个人报告 worker 遍历 `range(resume_from, len(moves) + 1)`，因此 N 手完整报告包括第 0 局面与终局，共 N+1 次局面分析。每次 `analyzeTurns=[len(played)]`、`maxVisits=requested_visits`、`includeOwnership=True`、`includePolicy=False`；同时获得领地和候选着法，不是两个 GPU 请求。见 `katrain/cron/jobs/report_analyze.py:230`、`:313`。
- 旧报告费用却是 `ceil(N × visits / 1000)`，非零最低 1 legacy credit；250 手／500 visits 为 125 credits，不是 251 个新标准请求。这是旧版本的商品计价，统一请求计价必须明确切换版本，不能把旧 task／已付订单按新算法重算。见 `katrain/web/core/analysis_cost.py:13`、`:34`。
- 当前三个入口的默认深度并不统一：hint 配置默认 100 visits（`core/physical_play.py:31`），payload 不请求 ownership；PVP territory 为 200 visits 且请求 ownership（`core/pvp_territory.py:173`）；quick-analyze 默认 100，接受客户端 visits（`endpoints/analysis.py:45`）。它们不能直接作为新固定 500 visits 商品；旧直通入口仍须纳入授权守卫。
- 所以不能依据“领地精度要求较低”就断言“500 visits 领地比现有支招便宜”：现有支招默认深度反而更低。可以把新标准分析统一定为受控模型的 500 visits，结果一次包含两种显示；如果另设低深度领地产品，需要单列 profile、计量权重和实测质量，不能把降低深度说成同质量的免费节省。
- 同一 operation 结果的领地／支招切换、重复查看免费；若明确发起更深分析则重新报价。统一计量的单位应是“固定模型/profile 的标准分析单位”，不是 HTTP 请求数或按钮次数，否则重试、多局面 payload、不同模型成本会混淆。

## 本次测量应使用的请求形状

复用 `katrain.cron.sgf.parse_game` 的完整主线、初始摆子、initialPlayer、rules、komi。该模块仅用标准库；系统 Python 3.9 无法解析其类型语法，现有 `../katrain-kiosk-debug/.venv/bin/python` 可直接运行，不需创建环境或读取应用配置。

对选定前缀 k：`moves=parsed.moves[:k]`，`analyzeTurns=[k]`，19×19，500 或 2000 visits，ownership 开、policy 关，`overrideSettings={reportAnalysisWinratesAs: BLACK}`。默认 human-SL profile 为空；开启它还会多做根节点对称采样，不应把不同 profile 的样本混在同一速率。见 `report_analyze.py:300` 与 `cron/config.py:73`。

`KataGoClient` 当前真实调用 `validate_result()` 没传 `min_visits`，默认值为 1。测量程序必须自己严格检查 final、匹配 request id/turn、实际 root visits、模型 SHA 验证事实、361 个有限 ownership 值和候选着法，不能仅见 HTTP 200 就计入吞吐；这一旧缺口仍需后续实现修正（`cron/clients/katago.py:98`、`:105`）。

wrapper 将不同请求送入同一个常驻 KataGo 进程，代码没有 HTTP 级结果缓存；随机 request id 也不等于冷 NN cache。启动 warmup 会发 1-visit 查询，模型／GPU plan 冷启动与正常请求不是同一成本。应记录“已预热进程、不同局面”与“重复局面”差异，不为测冷缓存重启生产引擎。见 `deploy/katago-cron/realtime_api/katago_wrapper.py:115`、`warmup.py:76`。队列等待与并发可影响 wall time，需分别报告单请求延迟和一批请求的总吞吐。

## 可复用的公开样本

已用现有纯 SGF parser 在本机核对，无数据库导入：

| 文件 | 主线手数／位置数 | 初始状态 | SHA-256 |
| --- | --- | --- | --- |
| `tests/data/panda1.sgf` | 204／205 | 19 路，中国规则，贴目 0.5，2 个黑子，白先；无无效着手或中途摆子丢失 | `2dc0b6771cb58fc8266e97bb171ad183017b2bc977f58f6760890251fd00907b` |
| `tests/data/LS vs AG - G4 - English.sgf` | 180／181 | 19 路，中国规则，贴目 7.5，无初始摆子，黑先；无无效着手或中途摆子丢失 | `ce3f6254ce3037b9706b015b641c00b6b1b0a5b9ecb5c21b157c7668defa7bdc` |

首选 panda1：文件头明确允许带 PANDANET 署名转载。第二个是公开 AlphaGo／李世石第四局，但含分析解说文字，保留原署名，不把全部解说复制到公开报告。首、中、后盘前缀可测不同局面；小样本均值不能证明所有 500 手棋谱的最坏情况。

## 已有历史性能证据

- `deploy/katago-cron/README.md:38`：2026-10-02 的 V100 `:8002` 使用 tf3-b11c768、SHA `93bdb63a…`，`:8000` 仍是 b28。第 39 行记录预热后的 2000 visits 单请求约 9 秒，四并发共 14.57 秒，即约 0.274 个位置／秒；两引擎当时共用显存约 3186 MiB。这不是本次 500 visits 结果。
- `docs/operations/kifu-analysis.md` 的“Ten-game production batch, 2026-10-05”：1951 个 2000 visits 位置实际总 wall time 12946 秒，约 6.636 秒／位置，包含 worker 周期、排队和持久化成本，不能与裸引擎延迟直接互换。
- 同文 home 两 GPU 的 50 局结果来自 RTX 3090，不是 V100，不能用其吞吐计算 V100 售卖容量。
- `scripts/kifu_batch_transfer.py:459`、`:489` 已记录 root_visits、positions、wall_seconds、root_visits_per_second；其时间是包含停机的有效任务吞吐，并非 kernel benchmark。该脚本会接数据库／运行 worker，不适合直接为本轮小样本测价而启动。
- 当前 source 的报告并发默认 3（`cron/config.py:116`），报告 flight window 默认 4（第 46 行）；这不是两张 GPU 的证明。主代理只读实机信息确认新 PROD 是同一张 V100 上运行 b28 与 transformer 两引擎。不能把两个端口的单独满载吞吐相加成双卡容量，visits 也不能跨模型视作相同算力。

## 澄清前的历史试算（不是当前目录）

下方250手、29/99/299及5000/18000/60000单位是用户最终澄清前的历史探索。当前以[300手v3修订](../superpowers/specs/2026-11-01-membership-points-and-request-budget-v3.md)和`artifacts/membership-cost-20261101/economics-300-move-v3.json`为准；价格与正式销售仍待确认。

1. 以 250 手报告为展示参考时，一盘是 251 个标准位置，7 盘／周等值 1757 个标准单位；短棋和长棋按实际 N+1 消耗。若深度档仍为 2000 visits，可报价为 4 个标准单位／位置，但成本／速度并不保证严格为 4 倍，须用实测校准。
2. 30 天按每天一盘 250 手平均为 7530 个标准单位。若坚持 29 元购买 50 积分等值量，则基础单价应满足 `50 / 7530 ≈ 0.0066401 积分／标准单位`；若基础价取 0.01，则 50 积分只有 5000 单位、约 19.92 盘，不能同时承诺完全用足 7 盘／周的 30 天。自然周与 30 天会员期限错位、首次／末次部分周允许前置消费，也需要明确周期总预算或如实说明周上限只是节奏限制。
3. 取消 24h 锚点与双资源桶，usage 改为当前周期总量及统一周预算；账户仍保留并发、全局容量和队列守卫。Free 每周一份普通报告若保留，应限定报告用途，不能变成任意私有局面的免费互动额度；旧 P3 可信身份前置不自动消失。
4. 新“1 元 = 1 积分”是展示货币，不等于旧整数 credit。现有 SKU 分别为 6 元／600、30 元／3300、98 元／12000 credits（`core/config.py:89`），历史含赠额且购买单价不同。必须冻结展示换算、内部最小整数单位和价格版本；不得把旧余额直接改名为同数新积分，或按新包比例任意缩小旧余额。历史账本、已付订单、在途授权按原单位快照保留，转换若实施须有可审计迁移记录与对账。不要同时暗建第二套可购买钱包。
5. 旧计划已确认的价格、24h、两资源配额、29 元／100 次与批量报告独立低价口径均须标成被新方案取代；原子预留／退款、幂等履约、合法完整 SGF、模型/深度校验、失败结果交付隔离、旧入口旁路防护、账号绑定、TEST mock 数据库隔离仍然适用，不能随商品简化一并删除。

核查仅执行源码读取、纯 SGF 解析和本文写入。没有跑产品测试，也没有输出部署配置或连接秘密。后续价格结论以主代理本次测量与最多两轮独立 Astra Max 修订评审为准。

## 主代理实测摘要的派生经济模型

主代理提供新 V100 测量摘要后，补充[数值模型](artifacts/membership-cost-20261101/economics.json)：使用 TF3 单请求与三并发两种吞吐分别计算 κ=0.3／0.5／0.7／1 的容量、3500 元租金成本、三档满额使用分摊毛利，以及 4200 元固定成本的 κ=0.5 情景。该文件只含派生计算与假设，不含原始引擎响应；本核查 agent 没有运行 GPU。

在三并发实测速率、κ=0.5 下，租金分摊单次约 0.0036403 元；以 29／99／299 元换取 5000／18000／60000 个标准单位，满额使用毛利约 37.24%／33.81%／26.95%，加入 700 元固定预留后约 24.68%／20.58%／12.34%。但采用串行实测速率的同一 κ=0.5，三档租金分摊毛利都为负；不能把批处理效率当作所有使用场景的保证。

同质满额用户的租金收支平衡人数为 121／36／12。三并发 κ=0.5 的月总量容量上限为 192／53／16 人，而同步用满周上限的压力情景仅为 127／35／11 人；两类数字含义不同，不能只按月人数卖满后声称峰值和时延已验证。5000 单位相当于约 19.92 盘 250 手参考报告，但精确只能完整覆盖 19 盘，界面写“约 20 盘”时必须保留估算说明，扣费以实际 N+1 为准。
