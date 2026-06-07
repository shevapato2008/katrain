# 手动测试指南（早上用）· 对弈付费分析 + 积分充值

> 夜间自主开发完成 **阶段 1–4a**(后端,全部带测试、已分阶段提交)。
> **阶段 4b(付费分析 handler)/ 5(前端)/ 6(充值 UI)/ board 云端 billing 代理** 未做——
> 它们需要「在线云端 + 真机 + 可视化评审」,而且你有「**先看 mockup 再改 UI**」的偏好,
> 所以留到早上和你一起做(见文末「下一步」)。

分支:`feature/rk3588-ui`。本次新增 4 个提交:

```
0507a5f7 rated-game analysis gating + remote analysis engine (phase 3+4a)
62c4ffb2 server-authoritative integer credit ledger (phase 2)
fb4d2fc2 R1 suppress kiosk auto-eval during play (phase 1)
（d3949769 之前的基线）
```

---

## 0. 环境准备(重要)

所有 Python 测试/运行都用 conda 的 **`py311_katago`** 环境(有 fastapi/pytest;仓库自带的 `.venv` 缺 web 依赖)。

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate py311_katago
cd /Users/fan/Repositories/katrain-rk3588-ui
```

---

## 1. 先跑自动化测试(看绿,30 秒)

```bash
CI=true python -m pytest \
  tests/web_ui/test_suppress_auto_eval.py \
  tests/web_ui/test_billing.py \
  tests/web_ui/test_billing_api.py \
  tests/web_ui/test_migrations.py \
  tests/web_ui/test_rated_gating.py -q
```

期望:**44 passed**。这覆盖了:抑制自动 eval、积分账本(原子/幂等/退款/reconcile)、
billing API(鉴权/兑换/管理员)、迁移(旧库不丢数据)、排位禁分析 + 远程引擎选择。

> 说明:`tests/web_ui` 全量跑会有约 30 个 **既有**失败/错误(集成测试要起在线服务、
> `TestClient(app=)` 的 httpx 版本不匹配、conftest 把 interface mock 掉),**与本次改动无关**——
> 我已用「改动前/后计数对比」确认零新增回归(失败数实际还降了)。

---

## 2. 阶段 1 · kiosk 自动 eval 抑制(性能修复)

### 2a. 本机快速验证(galaxy 行为不变 + board 抑制)
已由 `test_suppress_auto_eval.py` 覆盖:board 模式走子/新局/悔棋/编辑局都不再发 eval,
server(galaxy)模式照常发 eval,复盘/研究模式不受影响。

### 2b. 板上真机验证(RK3588,最关键)
把本分支部署到板子后,板上:

```bash
journalctl -u smartbox-katrain -f | grep "Sending KataGo HTTP analysis query"
```

然后在 kiosk 上**下几步棋**,观察日志:
- ✅ 期望:只出现带 `humanSLProfile` 的 **genmove** 查询;
- ❌ 不应再出现 `priority: 1002` + `includeOwnership: true` 的自动 eval。

体感:**AI 落子从 9–12s 降到 ≤ ~2s**(humanv0 1visit ~1.3s + 余量)。这是本期最痛点的修复。

> 如果板上仍有 eval:确认板子 `~/.katrain/config.json` / 服务环境变量 `KATRAIN_MODE=board`。
> 抑制只在 `KATRAIN_MODE==board` 且对弈(MODE_PLAY)时生效。

---

## 3. 阶段 2 · 积分账本 + billing API(服务端权威)

在本机起一个 **server 模式** 后端(galaxy)来测。默认管理员 `admin/admin`,
启动时会自动把 admin 标记为 `is_admin=True`,并 reconcile 历史挂起预扣。

### 3a. 启动后端
```bash
# 用你平时起 galaxy 的方式即可,例如:
python -m katrain --ui web --host 127.0.0.1 --port 8001
```
> 你的 galaxy 连的是 PostgreSQL。首次启动会自动:建 billing 新表、给 users 表
> 补 `is_admin` 列(ALTER,不丢数据)、补索引。**不会**动你已有的数据。
> (`users.credits` 在旧 PG 上仍是 float 列,但业务按整数处理,功能正常——后续如要真正改成
> INTEGER 列需一次单独的数据迁移,本期没动,无风险。)

### 3b. 一组 curl 冒烟(把 8001 换成你的端口)
```bash
BASE=http://127.0.0.1:8001/api/v1

# 1) 管理员登录拿 token
ADM=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2) 看单价 + 套餐
curl -s $BASE/billing/prices -H "Authorization: Bearer $ADM"; echo

# 3) 看自己余额
curl -s $BASE/billing/balance -H "Authorization: Bearer $ADM"; echo

# 4) 管理员给某用户加分(把 someuser 换成真实用户名)
curl -s -X POST $BASE/billing/admin/grant -H "Authorization: Bearer $ADM" \
  -H 'Content-Type: application/json' -d '{"username":"admin","amount":500}'; echo

# 5) 管理员生成 2 个兑换码,每个 300 分
curl -s -X POST $BASE/billing/admin/codes -H "Authorization: Bearer $ADM" \
  -H 'Content-Type: application/json' -d '{"count":2,"credits":300}'; echo

# 6) 用其中一个码兑换(把 CODE 替换)
curl -s -X POST $BASE/billing/redeem -H "Authorization: Bearer $ADM" \
  -H 'Content-Type: application/json' -d '{"code":"CODE"}'; echo
# 再兑换一次同一个码 → 应 400(不可重复),且不会重复加分

# 7) 非管理员调管理员接口 → 应 403(用一个普通用户的 token 试)
```

期望要点:
- 加分/兑换后余额**实时正确**;
- 同一个兑换码第二次兑换 **400**(幂等/防重复,不双加);
- 非管理员调 `/billing/admin/*` → **403**;
- 兑换码错误(无效/已用/过期)返回**统一**的「invalid」错误(不泄露码是否存在)。

### 3c. board 模式 fail-safe(可选)
如果以 `KATRAIN_MODE=board` 起后端,`/billing/balance`、`/redeem`、`/admin/*` 会返回
**503 `need_online_billing`**——这是**故意**的:kiosk 绝不拿本地 SQLite 当账本权威
(防篡改)。云端代理是早上要一起接的部分。

---

## 4. 阶段 3 + 4a · 排位禁分析(服务端反作弊)+ 远程引擎

### 4a. 排位禁分析(已由 `test_rated_gating.py` 覆盖,可真机/本机复测)
机制:**所有**分析动作都经 `WebKaTrain.__call__` 这一个入口,排位/ranked 局在这里被统一拦截——
不只是前端置灰,后端直接拒绝。即使有人绕过前端直接 POST `/api/analysis/extra`、
`/api/analysis/continuous`、`/api/analysis/show-pv`、`/api/ui/toggle`(hints/ownership/policy/eval)
也会被挡。

手动验证思路(起后端后):
1. 用 PvAI **排位**入口开一局(`/api/game/setup` 的 `mode='ranked'/'rated'`);
2. 直接 `curl` 调 `POST /api/analysis/extra` 等分析接口;
3. 期望:引擎**不被触发**、无分析结果返回(后端日志会打印 `Analysis action '...' blocked in rated game`)。
4. 自由对弈(free)同样操作 → 分析正常。

> 已接好的写入点:PvAI 的 `mode`(ranked/rated)→ `game_type`。
> **待接(早上)**:PvP 撮合(matchmaker)创建的排位局也要把 `game_type` 传进 `new_game`——
> 目前只有 PvAI setup 路径接了。这是个一行级的小接线,但要起多人对局才能集成验证。

### 4b. 远程强引擎(R6,可选)
在 `~/.katrain/config.json` 的 `engine` 段加:
```json
"engine": { "...": "...", "remote_url": "http://<b28-or-local>:8000" }
```
启动后 `analysis_engine()` 会用远程引擎做分析/复盘;不配则回退本地。b28 未部署时可临时指向本机 :8000 验证链路。
(真正消费它的「付费分析 handler」是阶段 4b,早上做。)

---

## 5. 下一步(早上和你一起做,按你「先 mockup 后实现」的习惯)

1. **阶段 4b — 付费分析 handler(后端)**:`reserve → 跑一次(高优先级)→ commit/失败 refund`,
   服务端派生幂等键 `analysis:{session}:{node}:{kind}`、`paid_analysis` 一次性结果 + entitlement。
   需要解决:非请求上下文里的 DB session、user 整数 id 解析、结果广播——要起真引擎集成验证。
2. **阶段 5 — 前端(两端)**:徽标「还能用几次」、点击消费、余额不足弹「充值」、移除对弈页胜率图。
   **先出 mockup 给你看**(kiosk + galaxy),你确认后再写代码。
3. **阶段 6 — 充值模块**:ManualConfirm(个人收款码 + 凭证 + 管理员确认)+ 兑换码页;
   微信/支付宝留接口契约。需要你的收款码素材 + 决定套餐/单价数值。
4. **board 云端 billing 代理**:把 kiosk 的 `/billing/*` 转发到 `REMOTE_API_URL`,要在线云端联调。
5. **小接线**:matchmaker 排位局 → `game_type` 透传(4a 的收尾)。

### 待你拍板的数值(写代码前要定)
- 单价:`BILLING_PRICES`(领地/支招/变化图,现占位各 10 分);
- 套餐:`BILLING_PACKAGES`(现占位 6/30/98 元);
- 新号赠送:`BILLING_FREE_GRANT`(现 10000);
- 同一节点同道具是否允许「付费重算」(force_recompute)语义。

— 都在 `katrain/web/core/config.py`,改了即生效。
