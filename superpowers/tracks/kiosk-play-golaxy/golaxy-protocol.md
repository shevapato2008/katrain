# 星阵围棋 (Golaxy / 19x19.com) — 人机对弈协议参考

> **Live-verified 2026-07-02** by hooking XHR/WebSocket in the logged-in web client and playing real moves (账号 usercode `61707593`).
> Scope: **人机对弈 (vs-AI "engine play")** — the `自由对弈` flow at `https://19x19.com/engine/play/normal/game`.
> 现有的 `katrain/web/platforms/golaxy/PROTOCOL.md` 覆盖的是**人人对弈 (gameroom + STOMP)** 与观战；本文档补上人机对弈这条**此前缺失**的路径。

---

## TL;DR

人机对弈是一个**无状态的 REST genmove 隧道**——**没有 WebSocket、没有服务器端 gameId、没有对局会话**。客户端自己持有着手列表，每一手把**完整历史**发给隧道，拿回 AI 的下一手。这也是为什么 URL 里没有对局 id、前端 store 里 `gameId=0`、刷新页面靠本地 sgf 恢复。

```
GET https://api.19x19.com/api/engine/dcnn/tunnel/genmove
```

**接入不依赖星阵官方合作**：端点、参数、坐标编码、鉴权均已从 web 客户端逆向并实盘验证。

---

## 1. 鉴权 (Auth) — 复用已有实现

已在 `katrain/web/platforms/golaxy/adapter.py` 实现且验证：手机号 OAuth2（+86），支持密码 / 短信验证码 / refresh_token。

- API base: `https://api.19x19.com`
- Token endpoint: `POST /api/auth/oauth/token`
- Client credentials: `Basic Z29sYXh5X3dlYjp4aW5nemhlbjA3MzA=` (`golaxy_web:xingzhen0730`)
- SMS code: `GET /api/auth/sms/code?username=<PHONE>&login=true&area=0086`
- 短信登录 body: `username=0086-<PHONE>&password=null&grant_type=sms_code&client_id=golaxy_web&sms_code=<CODE>&scope=any`
- 返回 `{access_token, refresh_token, token_type:"bearer", expires_in}`
- **`access_token` 是不透明 UUID（非 JWT）**，存在 web 客户端 localStorage（`access_token` / `refresh_token` / `usercode`）。
- 认证请求头：人机隧道用 **`Auth_token: <access_token>`**（注意 header 名是 `Auth_token`，不是标准 `Authorization`；其它社交接口用 `authorization: bearer <token>`）。

---

## 2. genmove 隧道（人机对弈的全部）

### Request
```
GET https://api.19x19.com/api/engine/dcnn/tunnel/genmove
Header:
  Auth_token: <bearer access_token>
Query params (实盘抓取，全部):
  moves         = <CSV of coord ints>   # 完整着手历史，见 §3 坐标编码。开局为空
  board_size    = 19
  boardSize     = 19                     # 两个都发（冗余）
  komi          = 7.5
  rule          = chinese
  handicap      = 0
  level         = <eloScore>             # AI 强度 = bot 的 eloScore，见 §4（星铠虾1级=1100）
  style         = 555559                 # 固定观测值
  elodiff       = 0                      # 自由对弈=0（升降级对弈可能非0）
  resign        = 6                      # 观测值 6（疑似认输/让子边界；先原样透传）
  org           = golaxy_web
  context_name  = ai_game_player
```

### Response
```json
{"code":"0","msg":"","data":{"coord":286,"prob":0.187845}}
```
- `code`: `"0"` = 成功（字符串）。
- `data.coord`: AI 下一手的坐标整数（见 §3）。
- `data.prob`: 该手的策略概率/置信度（float，仅参考）。

### 语义
- **一问一答**：POST 人类手不是单独的调用——客户端把（含刚落的人类手在内的）完整 `moves` 发过去，隧道返回**对方(AI)的下一手**。
- **无状态**：不带 gameId；服务端不保存对局（前端 sgf 才是真状态）。KaTrain 只需自己维护 `moves` 列表。
- 轮到谁：隧道按 `moves` 长度的奇偶决定该谁走，返回该方的手。人类执白时，开局用空/单手历史调一次让 AI(黑) 先手。

---

## 3. 坐标编码 (coord) — 已用 9 手实盘验证

```
coord = (19 - boardRow) * 19 + colIndex
```
- `boardRow`：棋盘行号 1..19，**19 在最上方**。
- `colIndex`：0..18 从左到右。字母 A=0, B=1, …, H=7, **J=8（跳过 I）**, K=9, …, Q=15, R=16, S=17, T=18。
- 直觉：就是「从左上角起、先行后列」的 0..360 序号。

**反解**：
```
row(boardRow) = 19 - floor(coord / 19)
colIndex      = coord % 19
```

**金标准对照表（本次实盘）** — 用作单元测试：
| 手 | 落点 | coord |
|---|---|---|
| B | Q16 | 72  |
| W | Q4  | 300 |
| B | D4  | 288 |
| W | D16 | 60  |
| B | Q10 | 186 |
| W | R6  | 263 |
| B | D10 | 174 |
| W | C6  | 249 |
| B | K4  | 294 |
| (resp) | B4 | 286 |

校验示例：Q16 → colIndex(Q)=15, boardRow=16 → (19-16)*19+15 = 3*19+15 = **72** ✓；coord 249 → row=19-floor(249/19)=19-13=6, col=249%19=2=C → **C6** ✓。

> ⚠️ **PASS 编码未抓**：本期若支持 pass 需实测（打一手 pass 看 coord，可能是 361/-1/特殊值）。默认本期不支持 pass。

---

## 4. AI 级别表 (`level` = `eloScore`) — 全 39 级

来源：web 客户端 Vuex `state.gameConfig.aiLevelList`（2026-07-02）。`genmove` 的 `level` 参数直接取 `eloScore`。
字段：`eloScore | levelName | name | goalDifference | timing(主时|读秒|次数)`。

| level (eloScore) | 段位/级 (levelName) | bot 名 (name) | goalDiff | timing |
|---|---|---|---|---|
| 3300 | 星阵3星 | 星猛虎 | 6 | 60\|60\|3 |
| 3200 | 星阵2星 | 星雄狮 | 6 | 60\|60\|3 |
| 3100 | 星阵1星 | 星巨象 | 6 | 60\|60\|3 |
| 3000 | 9段 | 星壮牛 | 5 | 45\|40\|3 |
| 2900 | 准9段 | 星蓝鲸 | 5 | 45\|40\|3 |
| 2800 | 8段 | 星美鹿 | 5 | 45\|40\|3 |
| 2600 | 准8段 | 星孤狼 | 5 | 45\|40\|3 |
| 2500 | 7段 | 星奇豚 | 4 | 45\|40\|3 |
| 2400 | 准7段 | 星萌猪 | 4 | 45\|40\|3 |
| 2300 | 6段 | 星骏马 | 4 | 45\|40\|3 |
| 2200 | 准6段 | 星呆羊 | 4 | 45\|40\|3 |
| 2100 | 5段 | 星跳鼠 | 4 | 45\|40\|3 |
| 2000 | 准5段 | 星云鹤 | 4 | 40\|30\|3 |
| 1900 | 4段 | 星灵狐 | 3 | 40\|30\|3 |
| 1800 | 准4段 | 星白鹭 | 3 | 40\|30\|3 |
| 1700 | 3段 | 星智狗 | 3 | 40\|30\|3 |
| 1600 | 准3段 | 星巧猫 | 3 | 40\|30\|3 |
| 1500 | 2段 | 星皮猴 | 3 | 40\|30\|3 |
| 1400 | 准2段 | 星乖兔 | 3 | 40\|30\|3 |
| 1300 | 1段 | 星树熊 | 3 | 40\|30\|3 |
| 1200 | 准1段 | 星长蛇 | 3 | 40\|30\|3 |
| 1100 | 1级 | 星铠虾 | 2 | 30\|30\|3 |
| 1000 | 2级 | 星夜鹰 | 2 | 30\|30\|3 |
| 900  | 3级 | 星憨鹅 | 2 | 30\|30\|3 |
| 800  | 4级 | 星刺头 | 2 | 30\|30\|3 |
| 700  | 5级 | 星黄鸭 | 2 | 30\|30\|3 |
| 620  | 6级 | 星轻燕 | 2 | 30\|30\|3 |
| 540  | 7级 | 星绿蛙 | 2 | 30\|30\|3 |
| 460  | 8级 | 星老龟 | 2 | 30\|30\|3 |
| 380  | 9级 | 星钳蟹 | 2 | 30\|30\|3 |
| 300  | 10级 | 星尾鱼 | 2 | 30\|30\|3 |
| 290  | 11级 | 星敏螳 | 2 | 30\|30\|3 |
| 280  | 12级 | 星鸣蝉 | 2 | 30\|30\|3 |
| 270  | 13级 | 星飞蜓 | 2 | 30\|30\|3 |
| 260  | 14级 | 星舞蝶 | 2 | 30\|30\|3 |
| 250  | 15级 | 星忙蜂 | 2 | 30\|30\|3 |
| 240  | 16级 | 星慢蜗 | 2 | 30\|30\|3 |
| 230  | 17级 | 星花虫 | 2 | 30\|30\|3 |
| 220  | 18级 | 星小蚁 | 2 | 30\|30\|3 |

> `goalDifference` 与 `timing` 在本期人机（不计时）里非必需；`level` 才是决定 AI 强度的关键参数。

---

## 5. 用到 / 没用到的东西

- ✅ **用到**：`GET /api/engine/dcnn/tunnel/genmove` + `Auth_token` header。仅此一个接口即可完成整局人机对弈。
- ❌ **没用到**：
  - 社交 WebSocket `wss://ws.19x19.com/api/social/channel/WS_STOMP_ENDPOINT_GOLAXY`（STOMP over SockJS，位于前端组件 `gameLinkGlobal.stompClient`）**只承载在线状态/心跳**（`/channel/wsuser/{usercode}` 的 `MSG_WSUSER_HEARTBEAT`、`SEND /channel/wsuser/heartbeat`），**与人机着手无关**。
  - `/api/social/wsgame/*`（那是人人对弈 gameroom 路径）。
  - 客户端本地引擎：页面**没有加载任何 WASM/棋力引擎**，AI 完全在服务端算。

---

## 6. 复现方法（如需重新抓）

1. 浏览器登录 19x19.com，进入 `自由对弈` 开一局人机。
2. DevTools Console 注入 XHR hook（包装 `XMLHttpRequest.prototype.open/send`，对 URL 含 `genmove` 的请求记录 `this.__u` 全 URL + `responseText`）。
3. 在盘上落一手 → 读记录：query 即上文参数，response 即 `{data:{coord,prob}}`。
4. 级别表：读 Vuex `document.querySelector('#app').__vue__.$store.state.gameConfig.aiLevelList`。
> 注意：`Auth_token`/`refresh_token` 是敏感凭证，抓取时务必 redact，勿写入仓库或日志。

---

## 7. 对 KaTrain 集成的直接结论

- golaxy adapter 只需加一条 **engine-play 路径**：维护本地 `moves` 列表 + 配置，调隧道、解 `coord`。**无需 STOMP、无需 gameId、无需 attach**。
- 现有 `golaxy/adapter.py` 的 `submit_move`（`/api/social/wsgame/genmove/{gameId}`）是**人人对弈**路径，人机**不要复用**它。
- 详细落地步骤见同目录 [`plan.md`](./plan.md)。
