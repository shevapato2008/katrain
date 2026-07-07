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
- 认证请求头（**2026-07-03 真机复测更正**）：人机隧道用 **`Authorization: bearer <access_token>`** + 浏览器风格的 `Origin` / `Referer` / `User-Agent`。
  - ⚠️ 早前（2026-07-02）记录的 `Auth_token: <access_token>` **是错的**（或端点已改版）：即使用一个刚拿到的有效 token，该 header 也会被拒，返回 HTTP 200 `code=6003 msg="invalid token"`。实测矩阵证明隧道要的是与社交接口**同一套** `Authorization: bearer <token>` 方案，且需要浏览器风格请求头（见下 §2 与 `engine_client.py`）。

---

## 2. genmove 隧道（人机对弈的全部）

### Request
```
GET https://api.19x19.com/api/engine/dcnn/tunnel/genmove
Header (2026-07-03 真机复测确认):
  Authorization: bearer <access_token>
  Origin:  https://19x19.com
  Referer: https://19x19.com/engine/play/normal/game
  User-Agent: <浏览器 UA>            # 见 engine_client._BROWSER_UA
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

- ✅ **用到**：`GET /api/engine/dcnn/tunnel/genmove` + `Authorization: bearer <token>` header（+ 浏览器 Origin/Referer/UA，见 §1）。仅此一个接口即可完成整局人机对弈。
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

---

## 8. 自由对弈可调参数实测（Phase 0，2026-07-03，用真机 token 直打隧道）

为「补全自由对弈设置面板」实测隧道对 komi/rule/handicap 的真实接受面（level=1100，逐一变体）。结论：

### 8.1 贴目 komi —— 完全生效 ✅
- `komi=0` 首手从 Q16(coord 72) 变为 R16(coord 73)、prob 0.57→0.34：**komi 真正参与计算**。`0.5 / 6.5 / 7.5` 均 `code=0`。→ 面板可自由开放 komi（数字/预设）。

### 8.2 规则 rule —— 中国 ✅ / 日本 ✅ / 韩国 ❌
- `rule=chinese` ✅、`rule=japanese` ✅（`code=0`，接受）。
- `rule=korean` ❌ → `code=8008 msg="dcnn request wrong"`（隧道**拒绝**）。
- → 面板只放 **中国 / 日本**，**不放韩国**。（人机不做服务端数子，rule 主要影响 komi 默认与终局，日本可接受即可。）

### 8.3 让子 handicap —— 支持，但机制是「**塞子 + handicap 参数**」⚠️
- `handicap=N` **配空 `moves` 会被忽略**：h2/h4/h9 空手一律返回黑 Q16（同 h0），**不会自动摆星位**。
- 但同一份非空 `moves` 下，`handicap` 参数**改变着手方**：
  | moves | handicap | 返回 coord | 含义 |
  |---|---|---|---|
  | `[72,288]` | 0 | 319 (Q3) | 按 B,W 交替 → 下一手**黑** |
  | `[72,288]` | 2 | 300 (Q4) | 前 2 手视为**连续黑让子** → 下一手**白** |
  | `[60,72,288]` | 3 | 300 (Q4) | 前 3 手皆黑让子 → 下一手白 |
- **结论**：`handicap=N` 告诉隧道「`moves` 前 N 手是**连续的黑让子**，之后轮白」。因此让子实现 = **把 N 颗标准星位（黑）塞进 `moves` 开头 + 同时发 `handicap=N`**；塞完轮**白**（人执黑则 AI 白先开一手；人执白则等人先落）。
- **19 路标准让子点（Golaxy coord = (19-row)*19+col）**：D4=288, Q4=300, D16=60, Q16=72, D10=174, Q10=186, K4=294, K16=66, K10(天元)=180。
  - 2子 `[288,72]`；3子 `[288,72,300]`；4子 `[288,300,60,72]`；5子 +天元 `…,180`；6子 4角+`174,186`；7子 6子+`180`；8子 4角+`174,186,294,66`；9子 8子+`180`。（顺序对隧道不敏感——实测任意黑子子集皆 `code=0`；用标准点即可。）
  - 让子局 komi 惯例取 **0.5**。
- ✅ 可干净实现（对应 plan §12 Task 2b 的「需塞子」分支 + 保留 `handicap` 参数）。

> 抓取所用 token 仅本地内存使用，未写入仓库/日志。

### 8.4 自由对弈真实配置（从星阵前端 `app.js` 提取，权威）
`/browse` 被 SSRF 拦（VPN 把域名映射到 198.18.x.x），claude-in-chrome 扩展未连；改从 CDN `assets.19x19.com/web-resource/golaxy/20260701_script/js/app.9dd37558.js` 直取配置对象（studying real source，非脑补）。

**对弈类型** `gameType`：`competitive_match 升降战` / `placement_match 定级战` / `casual_match 自由战`(=自由对弈)。

**19 路自由对弈的真实可调项（其余固定）：**
1. **让子** `ha_19`（下拉，**唯一核心新控件**）：`分先(komi 7.5,h0)` / `让先(komi 0,h0)` / `让2子(komi 2,h2)` / `让3子…让9子(komi=N,h=N)`；chinese 全表另有 `倒贴(komi -7.5)` / `自由贴目`。**komi 由让子自动推导，非独立选项**（chinese：分先 7.5、让先 0、让N子 N；japanese：分先 6.5、让N子 0）。
2. **颜色/先手** `cl`：`猜先(0)` / `执黑(1)` / `执白(-1)`。（现有 kiosk 只有 黑/白，需加"猜先"）
3. **对手等级**：39 级 bot 滑块（现有）。

**19 路上固定（不可改，故对齐时也固定）：**
- **棋盘** 19（配置支持 19/13/9，物理 kiosk 固定 19）。
- **规则/贴目**：`engineRule` 里 `japanese` 的 `boardSize:"13,9"` —— **日本规则在 19 路不提供**！19 路只有 `chinese`(+`button` AI赛规则)。故 19 路贴目恒为 `黑贴3又3/4子`(7.5, chinese)，截图里它是灰的正因如此。**19 路不放"中国/日本"切换、不放贴目选择器。**
- **计时** `tc`：`不计时`/`计时` —— 本期固定不计时。

**→ 对齐 Golaxy 自由对弈 = 加"让子"下拉（komi 自动推导）+ 颜色扩为 猜先/执黑/执白；棋盘/规则/贴目/计时 全固定。原 §12 计划里的 komi/规则 选择器应删除。**

> ⚠️ 更正 §8.3：让子局 komi 用 **让子档位对应值（chinese 让N子=N、分先=7.5）**，非我 Phase 0 探针里用的 0.5（0.5 隧道也接受，但与星阵不一致）。让子机制仍为「塞 N 颗标准星位(黑) + handicap=N」（Phase 0 §8.3 实测成立）。

---

## 9. 局内分析隧道（领地/支招/形势/变化图）—— 从 app.js 源码逆向

> **2026-07-07** 从当前 bundle `assets.19x19.com/web-resource/golaxy/20260701_script/js/app.9dd37558.js` 逆向（studying real source，非脑补）。genmove(§2) 只是隧道家族的一员；星阵局内的 **领地/支招/变化图/形势** 四个功能背后是 **同族的 `serve:"engine"` REST 隧道**，鉴权/坐标/参数与 genmove 一致，因此**可同样对接**。
> ⚠️ 以下**端点、方法、参数构造、缓存/限次机制、响应字段名**均来自源码，确凿；但**逐端点响应的完整 JSON 结构**尚需一次实盘 (B) 精校（`变化图` 有额度可测）。已在 §9.5 标注待测点。

### 9.1 端点表（`apiList`，源码原文）
```
applyJudgeData : /api/engine/dcnn/tunnel/public/area   (公共/无鉴权 area)
area           : /api/engine/dcnn/tunnel/area          serve:engine   → 领地(每点归属 + winrate + delta)
options        : /api/engine/dcnn/tunnel/options       serve:engine   → 支招(候选着列表)
variation      : /api/engine/dcnn/tunnel/variation     serve:engine   → 变化图(AI 变化手序)
judge          : /api/engine/dcnn/tunnel/judge         serve:engine   → 形势(winner/delta/owner)
genmove        : /api/engine/dcnn/tunnel/genmove       serve:engine   → 对手落子(§2)
```
base host = `https://api.19x19.com`（`serve:"engine"`），与 genmove 同域同鉴权（`Authorization: bearer <token>` + 浏览器 Origin/Referer/UA，见 §1）。

### 9.2 请求（GET，参数构造 `probsParamsGet`）
源码 `probsParamsGet(e)`：**先删除传入的 `level`/`style`**，再用固定基底覆盖：
```js
n = { moves:"", boardsize:BS, board_size:BS, level: maxLevel||8888,
      style: this.style, komi: this.komi, rule: this.rule, org: this.org }
// 然后 probsDataPush() 追加 context_name
```
- **method = GET**，参数拼进 query（`urlParse(url, params)`），与 genmove 完全同构。
- `moves`：完整着手历史 CSV（§3 坐标编码），开局为空。
- `board_size` **和** `boardsize` 都发（19），冗余，同 genmove。
- ⚠️ **`level` = `maxLevel`（观测 `probsLevel=8888` = 满血最强引擎），与对手 bot 的强度无关**。即：不管你在跟几级的 bot 下，**分析/支招/形势/变化图都用最强引擎算**。komi/rule/org 取当前对局配置。
- `type`（area/options/judge/variation）是**内部路由键**（选 `apiList[type].url`），非业务查询参数。

### 9.3 各端点响应（字段来自源码消费处）
- **judge（形势）** → **⚠️ 实测更正见 §9.5**：真实为 `{code:0, data:{belong:"<361 字符 U/B/W>", winner, delta}}`（下面 owner-map 说法作废）。~~`{code:0, data:{winner:"B"|"W"|"U"|"D", delta:<number>, owner:{<coord>:1|-1|0}}}`~~
  - `owner[coord]`：`1`=黑地、`-1`=白地、`0`=未定（`U`/`D` → 有未定/和棋，前端不 `/2`）。
  - `delta`：**目差（子）**；前端 `winner∉{U,D}` 时取 `delta/2` 显示为"黑领先 N 目"。
- **area（领地）** → 每点归属值 `{<coord>:<areaValue>}`（`areaValue<0` 或 `<areaMinValue` 不画），**并含 `winrate`（0..1）与 `delta`**（前端 `area.res.winrate` / `area.res.delta` → 底部"黑棋胜率/黑棋领先"就来自这里）。
- **options（支招）** → `parseData(raw)`（`JSON.parse` 字符串）后取 `.coord`：候选着**坐标列表**（附带各手概率/胜率，字段名待 §9.5 实测）。
- **variation（变化图）** → 同 options：`parseData` 后取 `.coord`，得**一串变化手的坐标序列**。
- `parseData`：若为字符串则 `JSON.parse`，否则原样。

### 9.4 计费/限次 + 缓存（关键产品约束）
- **限次道具**：前端 `propsMine.options` / `propsMine.variation` 是**剩余次数**（截图角标 `支招:0`、`变化图:7`）。每次真实请求消耗一次；`0` 则不可用。→ 对接后**每点一次花用户一次星阵额度**，UI 必须**按需触发 + 显示剩余次数**，不可常驻自动请求。
- **客户端缓存**：`setStoreData` 只缓存 `{area, options, variation}`，键为 `(type, moves)`——**同一局面重复看不重复扣次**；`judge` **不缓存**（每次实算，可能免费或另计）。对接时应**复刻按 moves 缓存**以省额度。
- **互斥叠加**：`boardChatFun` 里 area/branch(变化图)/prop(支招)/gameJudge(形势) 互相 `off`——**同一时刻只显示一种叠加**。

### 9.5 实测确认（2026-07-07 · 浏览器自动化直打隧道 · moves=`72,300`[黑Q16,白Q4] · 账号 61707593）

直接以页面 `fetch` 打四个隧道（token 从 localStorage 取、仅用于 header、未落盘），真实响应：

**variation（变化图）** — `code 0`：
```json
{"code":"0","data":{"winrate":0.375,"delta":-2.1,"coord":[60,288,320,301,319,299,317,54,73,53,51]}}
```
- `coord` = **变化手序坐标数组**（本次 11 手，即 UI 上 1..11）。**无需指定从哪手展开**——默认返回主变。
- `winrate`(0..1) + `delta`(目差) = 该变化局面评估。**限次**（本次 7→6）。

**judge（形势）** — `code 0`，**免费**（未扣任何道具）：
```json
{"code":"0","data":{"belong":"UUU…(361 字符 U/B/W，每点一位)…","winner":"U","delta":0}}
```
- `belong`：**长度 361 的字符串**，每点归属 `U`未定 / `B`黑 / `W`白（**非** object map）。
- `winner`：`U`未定 / `B` / `W` / `D`和；`delta`：目差。
- ⚠️ **更正 §9.3**：judge 用 **`belong` 字符串**（不是 `owner` 对象）；judge 顶层**没有 winrate**（只有 belong/winner/delta）。winrate 来自 **variation**（和 area）。

**area（领地）** 与 **options（支招）** — **首次样本**（道具剩 0）均 **`7003`**：
```json
{"code":"7003","msg":"item is not sufficient","data":""}
```

**area / options 成功结构（2026-07-07 第二次实测，领地/支招 充值后，同 moves=`288,300`[黑D4,白Q4]）：**

**area（领地）** — `code 0`：
```json
{"code":"0","msg":"","data":{"winrate":0.375,"delta":-2.2,"area":[<722 个 float>]}}
```
- ⚠️ **`data.area` 是长度 722 的扁平数组（= 361 × 2），不是 §9.3 源码推测的 `{coord:value}` 映射。**
- **前 361 项 = 每点归属**，下标即 coord（`c=(19-row)*19+col`）：`>0`→黑地、`<0`→白地、`|值|`≈归属强度（范围约 `[-1,1]`）。**实盘校验**：黑子 D4(coord 288)=`+0.683`、白子 Q4(coord 300)=`-0.729`（互相印证坐标+符号）。交错假设 `a[2i],a[2i+1]` 已证伪。
- **后 361 项** 本样本≈ `-0.99` 常量（近空盘；含义不明，**kiosk 只用前 361**）。
- 顶层 `winrate`(黑棋胜率 0..1) + `delta`(黑棋目差) —— 即前端底部"黑棋胜率/黑棋领先"。
- **限次**（本次 领地 398→396，抓结构花 2 次）。

**options（支招）** — `code 0`：
```json
{"code":"0","msg":"","data":{"coord":[60,59,320,41,72],"prob":[0.4,0.189,0.144,0.133,0.122],"winrate":[0.376,0.377,0.374,0.372,0.374],"delta":[-2.1,-2.1,-1.9,-1.8,-2.2]}}
```
- 四个**等长并行数组**（本次 5 个候选）：`coord`=候选着坐标（coord 编码）、`prob`=推荐概率（降序，和≈1）、`winrate`=该手后黑胜率、`delta`=该手后黑目差。
- **无需 `parseData`**（本次 data 已是对象，非字符串；若为字符串则按 §9.3 `JSON.parse`）。**限次**（支招 399→398）。

**variation（变化图）** — 复测同 §9.5 顶部结构（`{winrate,delta,coord[11]}`），本次 `coord=[60,72,54,53,73,91,111,40,41,59,97]`，坐标编码一致。**限次**（变化图 4→3）。

**由此确认：**
- **计费**：`judge` **免费**；`variation`/`area`/`options` **各自独立限次**（本次 变化图 7、领地 0、支招 0）。
- **错误码 `7003 "item is not sufficient"` = 道具次数不足** → UI 据此提示"次数不足/充值"、禁用该按钮。
- **`type` 不进 query**（未发 type 即 `code 0`）；analysis 用 `level=8888`（满血）实测可行；参数集 = `moves/board_size/boardsize/komi/rule/handicap/level/style/org/context_name`。
- ⚠️ **不要据 judge 本次 code 0 就当"免费"**：星阵把 领地/支招/变化图 都做成**付费道具**（实测截图：`领地 x400 = 28星币`，道具用尽弹"可用余额兑换"）。`judge` 这次没扣道具可能是独立额度/形势判断另计，样本仅 1，**不足以断言无限免费**。且这些分析全在**星阵服务器**算（我们只做隧道代理，本地 RK3562 不参与）；本地弱 KataGo 能算但（i）非最优、（ii）等于对弈中挂自家引擎助战。
- **对齐星阵 = 按付费道具处理**：领地/支招/变化图 全走隧道、用**用户自己的星阵 token**，消耗记在**用户星阵账号**上；kiosk 只显示真实剩余次数，`7003` 时提示"次数不足 · 请在星阵充值"，**不做假免费分析**。**人机对弈无胜率图**（星阵没有，我们也不放）。

> token 全程仅在页面内存用于 header，未写入仓库/日志/文档。

### 9.6 → 对 kiosk 的直接映射（对接落点）
| kiosk 按钮（应对齐后） | 星阵端点 | 局内语义 |
|---|---|---|
| 领地 | `tunnel/area` | 每点归属叠加（+胜率/目差） |
| 支招（原"建议"） | `tunnel/options` | 候选着标记（限次） |
| 变化图（**新增**） | `tunnel/variation` | AI 变化手序（限次） |
| 形势/胜率（原"图表"改按需） | `tunnel/judge` 或 `area.winrate` | winner/delta/owner |
- 我方 `GameControlPanel` 现有的 领地/建议/图表 走的是**本地 KataGo 分析**，引擎对局下无数据→失效（且用本地引擎助战=作弊）。对接后改为**调星阵这四个隧道**，即"用星阵自己的、受其限次约束的局内助手"，非作弊。
- 落地细节（按钮全量对齐 + 限次感知 UI + 缓存）另见 `../kiosk-ui-redesign/` 的对局态设计稿更新与本 track plan。
