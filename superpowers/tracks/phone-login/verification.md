# P3 手机绑定与验证码登录 —— 验收记录

日期：2026-09-11
分支：`feature/phone-login`（worktree `/Users/fan/Repositories/katrain-phone-login`）
被验提交：`33d6f77f`（Task 17 完成态）

本文件只记**实际跑出来的读数**。没有读数的项按事实分成「本轮无 UI」与「本轮不可验」两类，
**不标「已验」**。收尾清单里的对应条目引用本文件取证。

---

## 0. 验收环境

```
PYTHONUNBUFFERED=1 KATRAIN_SMS_PROVIDER=console KATRAIN_SMS_ALLOW_CONSOLE=1 \
KATRAIN_SECRET_KEY=<验收专用> KATRAIN_DATABASE_URL=sqlite:////tmp/phone-acc/acc.sqlite3 \
./.venv/bin/python -m katrain --ui web --host 127.0.0.1 --port 8099 --disable-engine --log-level info
```

- 闸放行探测：`mode= server provider= console allow_console= True`，不抛异常。
- `/health` → `{"status":"ok","engines":{"local":"error_502","cloud":"unconfigured"}}`（本机无 KataGo，不影响本轮任何一项）。
- 注册两个账号，响应体各含 `"phone_bound": false` —— 这同时是 Task 8 把 `phone_bound` 加进
  pydantic `User` 的落地证据（pydantic v2 默认 `extra='ignore'`，没进模型的键会被静默丢掉）。

**三条与计划不同、下次照这里做：**

1. **必须 `PYTHONUNBUFFERED=1`。** `ConsoleProvider.send` 用的是 `print`（`sms.py:61`），
   重定向到文件时 Python 块缓冲，验证码会迟迟不落盘，V2/V4/V6 全都取不到码。
2. **`KATRAIN_DATABASE_URL` 不是可选项。** 本机默认走 PostgreSQL（`config.py:207`，
   启动日志 `Using PostgreSQL/External DB at localhost:5432/katrain_db`），不覆盖就不是在验本机。
3. **没有 uvicorn 访问日志**（`--log-level info` 也没有）。「请求打没打出去」只能用
   `$B network | grep -c` 数，grep 服务端日志恒 0，会得出「前端根本没发请求」的错误结论。

---

## 1. 基线比对（Step 1 / Step 2）

Task 11 主动改动的三条，单独跑：**3 passed**。
（`test_quota_endpoint_shape`、`test_first_report_of_the_week_is_free_second_is_charged`、
`test_free_report_records_its_period_not_a_charge_ref`）

全量 pytest：**64 failed, 4022 passed, 2 skipped, 1 xfailed, 18 errors in 349.11s**

```
after=82  base=85
comm -23 after base  →  （空）          # 新增失败为零
comm -13 after base  →  3 条            # 基线里红、现在绿
    tests/platforms/test_golaxy_alignment_campaign.py::test_direct_cli_pins_current_repo_katrain_before_poisoned_pythonpath_and_disables_kivy_args
    tests/platforms/test_golaxy_sampling_campaign.py::test_sampling_direct_cli_pins_current_repo_before_poisoned_pythonpath
    tests/web_ui/test_social_api.py::test_follow_unfollow
git diff --stat -- test-baseline.txt  →  （空）   # 基线文件一个字节没改
```

比的是**失败名字集合**不是条数；两边都 `LC_ALL=C sort` 之后再 `comm`。
`test_stellabox_branding.py::test_brand_specific_translations_use_chinese_brand_only_for_cn_and_tw`
在基线第 65 行 —— 它是 develop 起就有的既有红，本轮**没有**改绿。

## 2. 三个构建 + 全量 vitest（Step 3）

```
build=0
build:kiosk-2d=0                 → ✅ kiosk boundary clean
build:smartbox-kiosk-2d=0        → ✅ strict Box SSO boundary clean + ✅ kiosk boundary clean
vitest: Test Files 175 passed | Tests 1775 passed, 7 skipped (1782)
```

**计划标题写的是「两个构建」，实际要跑三个。** `build:smartbox-kiosk-2d` 是唯一跑
`verify-kiosk.sh` 严格 localStorage-token dist 扫描的那一档，漏了它等于那条闸从没验过。

（`${PIPESTATUS[0]}` 在 zsh 下恒为空，不能当退出码证据；上面这三个数是不带管道重跑取的。）

---

## 3. 真浏览器逐项（Step 5）

工具：gstack `/browse`（项目规定：所有网页浏览走它）。

### 驱动方式与计划不同的两处（下次照这里做）

**(a) `$B js` / `$B eval` 都不 await promise。** 计划里 V1/V3/V4/V5/V6 的
`await new Promise(r=>setTimeout(r,1200)); …` 写法**静默返回空**，命令看起来「跑过了」
但什么都没断言到。改法：把结果挂到 `window` 上，再用 until 循环轮询：

```bash
$B eval /tmp/phone-acc/ws.js            # 脚本里 (()=>{ window.__r=undefined; (async()=>{…; window.__r=…})(); return 'started' })()
until [ "$($B js "window.__r!==undefined")" = "true" ]; do sleep 1; done
$B js "window.__r"
```

**(b) 「一律用 `$B js` 按文案找元素再 `.click()`」在这个 build 上不成立。**
`$B goto` 之后 React 还没 hydrate 就点会静默无效；掀掉 disabled 的 MUI 按钮 `.click()`
也不触发 handler。保住计划本意（不绑别人的类名）的改法是**按文案找 → 打 `data-acc` 标记 →
`$B click` 真点**，并在 goto 之后先等 hydrate：

```bash
tagclick() { $B js "…find(x=>/$1/.test(x.textContent)).setAttribute('data-acc','hit')…"; $B click "[data-acc=hit]"; }
waitfor()  { until [ "$($B js "$1")" = "true" ]; do sleep 1; done; }
```

### V1 切到验证码登录、发码、按钮变倒计时 —— ✅

```
对话框文本: 登录智星盒 | 国家/地区 | +86 中国大陆 | 国家/地区 | 手机号 | 手机号 |
           验证码 | 验证码 | 获取验证码 | 我同意「智星盒」的运营方北京万智星科技有限公司
           收集我的手机号，仅用于身份验证与登录。《隐私策略》 | 密码登录 | 取消 | 登录
$B text | grep -c '+86'               → 1
手机号输入框 found                     → true
点「获取验证码」后按钮状态             → {"label":"58 秒后可重发","disabled":true}
```

### V2 服务端日志里是掩码不是明文 —— ✅

```
[SMS console] to=+86 138****8000 intl=False code=308354
grep -ac '13800138000' server.log     → 0          # 整份日志里不存在连续 11 位号
```

第二条是这一项真正的断言：把 `mask_e164(...)` 换成裸 `phone_e164` 它立刻变成非 0。

### V3 冷却期内再发 → 屏上说得出还要等多久 —— ✅（判据已修正）

```
验证码发送太频繁，还需等待 38 秒
grep -Ec '发送太频繁.*还需等待'        → 1
grep -Ec '操作失败|Operation failed|Request failed|\[object Object\]'  → 0
[SMS console] 条数                     → 2（没多发第三条，后端真拒了）
```

**计划这一项的判据是假绿的，已改。** 原判据 `grep -Ec '等待|[0-9]+ ?秒'` 会被**倒计时按钮**
「38 秒后可重发」命中 —— 实测第一次尝试里错误根本没出现（屏上还挂着上一次的成功提示），
那条 grep 照样返回 1。判据必须落在错误文案「发送太频繁」上。

**触发后端 429 的路径也与计划不同。** 计划说「手工把按钮 `disabled` 掀掉再点」就能逼后端走一遍。
实测：`handleSendCode` 本来就**没有**前端冷却短路（它总是发请求），真正挡住的是按钮的
`disabled`；而掀掉 `disabled` 之后 `.click()` 仍不触发 React handler。真正走得通、
**且是真实用户会走的**那条路是「切回密码模式再切回验证码模式」—— `switchTo` 调 `resetTransient`
把前端 `cooldown` 清零，后端 60 秒冷却仍在，一点就是真 429。

### V4 未绑号提交 → 屏上是一条可走的路 —— ✅

```
这个手机号还没有绑定账号。请先用用户名密码登录，再到左下角「设置 → 绑定手机号」绑定。
diff(before,after) | grep -c '^>.*绑定'   → 1
grep -Ec '操作失败|Operation failed|…'    → 0
```

判据落在 **diff 里新出现的那一行**上：同意勾选那行文案本来就带「绑定」二字，整页 grep 恒 ≥1。

### V5 未绑号发言被拒，且拿得到回执 —— ✅（不在屏上验，理由：无入口）

先取「没有入口」这个事实（**计划写的路径 `components/game/ChatPanel.tsx` 是过期的**，
实际在 `galaxy/components/game/ChatPanel.tsx`）：

```
ChatPanel 的 importer（排除它自己）        → 零命中
sendChat 的非测试消费者（排除定义处）      → 零命中
chatMessages 的非测试消费者（排除定义处）  → 零命中
```

所以改在**同一条生产通道**上验：真 token → `POST /api/session` → 真 WS → 真 chat 帧。

```json
{"all":["game_update","spectator_count","error"],
 "picked":[{"type":"error","code":"chat_requires_phone"}]}
```

恰好一帧 `error`，**且一帧 `type:"chat"` 都没有** —— 发言没有广播出去。
`all` 里的 `game_update` / `spectator_count` 是连上就推的，拿「队列里有没有东西」判广播一定假绿。

### V6 密码登录 → 侧边栏绑定入口 → 复盘页额度文案当场变 —— ✅

绑定前（acc_bind）：
```
$B network | grep -c 'billing/quota'   → 1      # 硬判据：复盘页真的去读了这个端点
free_weekly                            → {"used":0,"allowance":0,"blocked_reason":"phone_required"}
页面文案                                → 绑定手机号后可享每周免费普通复盘
```

从侧栏「设置」菜单走绑定（13800138001，完整发码 → 填码 → 绑定，对话框自行关闭）。

绑定后（**同一 ISO 周内**）：
```
free_weekly                            → {"used":0,"allowance":1,"blocked_reason":null}
页面文案                                → 本周剩余 1 次免费普通复盘
diff(before,after)                      → 非空（就这一行变了，「绑定手机号」按钮同时消失）
```

这是 Task 11「未绑号触碰 quota 之前短路、一行桶都不建」那条实现的用户可见证据 ——
换成「拿 allowance=0 去 peek」，这里的 `allowance` 会是 0 且当周再也回不去。

`billing/quota` 的请求计数是本项的硬判据：改动前这个端点在整个前端**零消费者**，
`blocked_reason` 是个没人读的字段。

### V7 《隐私政策》链接真的到得了政策页 —— ✅

```
链接 {text:"《隐私策略》", target:"_blank"}
HREF = http://127.0.0.1:8099/galaxy/privacy
grep -c '智星盒隐私策略' privacy.txt    → 1
grep -c '手机号' privacy.txt            → 2
正文抬头: 智星盒隐私策略 本隐私策略说明由智星盒团队开发的"智星盒"（StellaBox）应用的隐私数据相关政策和…
```

判据故意落在**渲染出来的正文**上：改动前 `/privacy` 不是 404 而是落到禅模式棋盘，
只 grep href 会被自己刚写的那行命中、恒绿。第二条守的是「政策正文里真的写了收手机号」——
仓里那份 4.3KB 正文原本一个字没提手机号。

### V8 改密码入口（Task 17，计划成文时还没有这个 Task）—— ✅

```
对话框: 修改密码 | 国家/地区 | +86 中国大陆 | 手机号 | 验证码 | 获取验证码 | 新密码 | 取消 | 确认修改
（没有同意勾选，也没有隐私链接 —— requireConsent = !isSetPassword，符合设计）
成功后: 密码已经改好了。已经登录的设备不会被强制退出，最长 90 天内仍可继续使用。
grep -Ec '90 ?天'                       → 1
```

`auth.py:540-542` 的 docstring 明写要求 UI 说出这条 90 天上限；不说就是给用户一个错的安全承诺。

---

## 4. 承重实测（Step 6）

登录框在验证码模式下长高了，这条链变了，所以要量。

**量的盒子与计划说的不同。** 计划警告「量 `.MuiDialogContent-root` 不要量 `[role=dialog]`」是对的，
但漏了一种：**900–1199 档的侧栏是 MUI Drawer，它自己也带 `role=dialog`** ⇒ DOM 里有两个，
`document.querySelector('[role="dialog"]')` 抓到的是侧栏，脚本一路返回 `NOT_OPEN` 而不是报错。
判据必须改成「**含 `.MuiDialogContent-root` 的那个**」：

```js
const paper = [...document.querySelectorAll('[role="dialog"]')]
  .find((d) => d.querySelector('.MuiDialogContent-root'));
```

**`$B viewport` 会重置页面**（对话框当场消失），所以不能「开框之后再缩视口」；要先设视口再开框。

读数（1280x420，侧栏 docked ⇒ DOM 里只有登录框一个 dialog）：

| 状态 | contentClient | contentScroll | overflows | paperBottom | submitBottom |
|---|---|---|---|---|---|
| A 密码模式（基准） | 203 | 255 | true | 388 | 364 |
| B 验证码模式 | 203 | 261 | true | 388 | 364 |
| C 验证码模式 + 错误条（最撑） | 203 | 328 | true | 388 | 364 |

在最撑的 C 态上显式跑滚动：

```json
{"vh":420,"atTop":0,"atBottom":125,"maxScroll":125,"canScroll":true,
 "submitBottom":364,"consentBottom":235,"paperBottom":388}
```

四条关系式同时成立：

1. `overflows === true`（328 > 203）✅
2. `canScroll === true`，0 → 125 且 125 **恰好等于** `maxScroll`（滚轮真能推到底）✅
3. `paperBottom (388) <= vh (420)` —— 对话框自己没被推出视口 ✅
4. `submitBottom (364) <= vh (420)` —— 提交按钮够得到 ✅（同意勾选框 235 也够得到）

具体像素只作记录，判据是上面四条关系式。

---

## 5. 部署前置（Step 8 / 9 / 10）

### 仓内闸（Step 8）+ 变异验证（Step 9）—— ✅

`tests/web_ui/test_compose_declares_sms_provider.py` 三条：**3 passed**。

| 变异 | 期待变红 | 实测 |
|---|---|---|
| M1 删掉 compose 里 `KATRAIN_SMS_PROVIDER` 那一行 | 第 1、2 条 | ✅ 恰好这两条红 |
| M2 把 `:?…` 改成 `:-aliyun` | 只第 2 条 | ✅ 只这一条红 |
| M3 `config.py` 的 `os.getenv` 字面量改成 `KATRAIN_SMS_VENDOR` | 只第 3 条 | ✅ 只这一条红 |

三次都改坏 → 跑 → grep 回读确认改到了 → 还原 → grep 回读确认还原了。
跑完 `git status --porcelain -- docker-compose.yml katrain/web/core/config.py` 为空。

### 两台机器的实测回显（Step 10）—— ❌ **两台都没配，这条分支今天不许合**

**只跑了只读探测，没有改任何配置、没有重建任何容器。**

| | home-ubuntu（测试） | ucloud-v100（生产） |
|---|---|---|
| 容器名 | `katrain-web` | **`katrain-ucloud-katrain-web-1`**（不是 `katrain-web`） |
| `config_files` | `/home/fan/Repositories/katrain/docker-compose.yml`,<br>`/home/fan/Repositories/katrain/docker-compose.override.yml` | `/opt/katrain/releases/29aa20f7/deploy/ucloud/compose.yml`,<br>`/opt/katrain/releases/29aa20f7/deploy/ucloud/compose.production.yml` |
| `echo SMS=[$KATRAIN_SMS_PROVIDER]` | **`SMS=[]`** | **`SMS=[]`** |
| compose 里的 `env_file` | 无 | 无 |
| env 文件里有没有这个变量 | `.env` → 0 命中 | `/etc/katrain/ucloud.env` → 0 命中 |
| cron 吃不吃这条闸 | `ModuleNotFoundError: No module named 'katrain.web'` | `ModuleNotFoundError: No module named 'katrain.web'` |

三条要点：

- **两台都是空**，而 Task 5 的 fail-fast 闸在 server 模式下拒绝空 provider 启动 ⇒
  今天合并 ⇒ **两台线上机器都起不来**。
- **`config_files` 两台都是逗号分隔的两份**，`docker compose` 必须每份各给一个 `-f`，
  只喂第一份等于用另一套配置重建容器。生产那两份还是 **release 钉死的路径**
  （`releases/29aa20f7/`），下次发布换目录时这个路径会变，照 `docker inspect` 现探。
- **cron 两台都不吃这条闸**（`Dockerfile.cron` 只 `COPY katrain/cron/`），所以 cron 不用配。
  哪天 `Dockerfile.cron` 改成 `COPY . /app`，这一行回显会变，那时 cron 也得配上。

待办（需 Fan 批准后执行，顺序照 2026-08-31 的裁定：先测试环境再生产）：
两台各配 `KATRAIN_SMS_PROVIDER=aliyun`（凭据留空），`docker compose -f <份1> -f <份2> up -d <web 服务>`，
然后回显 `SMS=[aliyun]` 并贴回本文件。**不许加 `--remove-orphans`**（这台机器的磁盘 compose
与正在跑的 stack 对不上过，加上它会把教学媒体的对象存储一起删掉）。

---

## 6. 本轮无 UI / 本轮不可验（不标「已验」）

### 本轮无 UI —— 后端闸是真的，用户看不见

1. **对局聊天的 `chat_requires_phone` 回执**。三条 grep 零命中（见 V5）。
   后端在真通道上实测拒住了，但前端没有任何入口能触发它。
2. **评论被拒回执（Task 16 的 `useComments` 403 → 中文）**。
   `CommentSection.tsx` **零真 importer**（唯一文本命中是 `useComments.ts` 里的一句注释），
   `useComments` 的唯一消费者就是这个没人 import 的组件 ⇒ 整条路在屏幕上不可达。

### 本轮不可验

3. **真短信通道**。没有凭据、**没有实发过一条**。本轮所有验证码都来自 `console` provider
   打印到本机日志。阿里云签名报备是这条路的关键路径且**不在代码里**（5–10 个工作日，不承诺时效；
   签名 6 个月无发送记录会失效）。
4. **`BILLING_ENFORCED` 开闸后的行为**。该字段没有 env 装配（见 plan.md 收尾 10b），
   本轮验的 `/quota` 与 `free_weekly` 在 `BILLING_ENFORCED=False` 下**依然**如实反映绑定状态
   （V6 实测），但「未绑号用户拿不到免费额度」那条真正的扣费行为没有也无法在本机验。
5. **PostgreSQL 上的建表/迁移**。本机只有 SQLite。见 plan.md 收尾 17。

---

## 7. 本轮新发现、要交回给 Fan 的

**A. 手机宽度下绑不了号、改不了密码（本轮造成的一半）。**

`MainLayout.tsx:21/44`：宽度 < 900px 时 `GalaxySidebar` **整个不挂**，改挂 `GalaxyBottomNav`；
而 Task 16 的「绑定手机号」与 Task 17 的「修改密码」两个入口**都在 `GalaxySidebar` 的设置菜单里**。
实测 430 宽下「更多」里只有直播/棋谱库/教程，没有账号相关的任何一项。

两半要分开看：
- 登录入口在 mobile 档缺席是**既有的**（`develop` 上 `LoginModal` 就挂在 `GalaxySidebar`，
  本轮没碰 `MainLayout.tsx` / `useGalaxySidebar.ts` / `GalaxyBottomNav.tsx` 三个文件）;
- 但**这两个新入口是本轮加的**，等于本轮新做的功能在手机上不可达。

这条同时让 V4 那句引导文案在手机上落空：屏上说「到左下角「设置 → 绑定手机号」」，
而手机宽度下左下角没有那个菜单。

**B. 计划里两条驱动约定在这个 `/browse` build 上不成立**，已在第 3 节写清替代写法
（不 await promise；`.click()` 不触发 React handler + 要等 hydrate）。下一条轨道照那里抄。

**C. V3 的判据是假绿的**，已改成断言错误文案本身。形状是「闸量错了对象」——
断言词同时出现在**倒计时按钮**和**错误提示**里，而只有后者才是这一项要证的东西。
