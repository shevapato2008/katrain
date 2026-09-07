# P3 计划对抗审查：全部 77 条发现

六个独立 agent 并行审出，最严重的 6 条经对抗证伪全部存活。

## [1] [high] plan.md:2155-2163（Task 12 的 server.py 聊天闸）+ requirements.md §3 D-U2 第 3 条

**错在哪**：计划断言「WS 里的 current_user 与 live.py 里 Depends(get_current_user) 拿到的 pydantic User 不是同一个类型」并据此用 `getattr(current_user, "phone_e164", None)` —— 两句都错：server.py:2770-2772 用的正是同一个 `get_user_from_token`（endpoints/auth.py:106-125，`return User(**user_dict)`），所以就是同一个 `katrain.web.models.User`；而那个模型（models.py:176-186）没有 `phone_e164` 字段，计划也只打算给它加 `phone_bound`（plan.md:1606-1607），pydantic v2 默认 extra='ignore' 会把 `_to_dict` 里的 `phone_e164` 静默丢掉 ⇒ getattr 恒为 None ⇒ **已绑手机的人也发不了言**。

**怎么证明**：`sed -n '2767,2772p' /Users/fan/Repositories/katrain-phone-login/katrain/web/server.py` 与 `sed -n '106,125p' /Users/fan/Repositories/katrain-phone-login/katrain/web/api/v1/endpoints/auth.py` 看到同一个构造点；再跑 `cd /Users/fan/Repositories/katrain-phone-login && ./.venv/bin/python -c "from katrain.web.models import User; u=User(username='x', phone_e164='+8613800138000'); print(hasattr(u,'phone_e164'))"` → False。

**改成**：把 plan.md:2161 改成 `if not current_user.phone_bound:`（与同 Task 里 live.py 那段 plan.md:2169 一致），删掉 2155-2160 那段「不是同一个类型 / 打日志确认是哪个类」的注释与步骤；requirements.md §3 D-U2 里 `elif not current_user.phone_e164` 同改。若确实要用原始号，则必须同时把 `phone_e164` 加进 models.py 的 pydantic `User` 与 auth.py:323 的 `_to_dict`。

## [2] [high] plan.md:824（Task 5「调用点：与 assert_secret_key_is_safe(...) 同一处（config.py 里现有那次调用的紧邻位置）」）

**错在哪**：`config.py` 里**没有**对 `assert_secret_key_is_safe` 的调用——它只在 config.py:13 被定义，生产唯一调用点是 `katrain/web/server.py:176`（`_lifespan_server` 的第一件事）。照计划字面执行会把 SMS fail-fast 放进一个不存在的位置；而 Task 5 的 7 条测试（plan.md:698-749）全部**直接调函数**，没有一条断言它被接进 lifespan ⇒ 函数没人调也全绿。这正是本仓已经踩过并写进 tests/web_ui/test_secret_key_gate.py:39-55 的那个坑（「函数被测透，唯一的生产调用点没有闸」）。spec §2.1 把生产 fail-fast 列为硬性约束。

**怎么证明**：`grep -rn "assert_secret_key_is_safe" /Users/fan/Repositories/katrain-phone-login/katrain/` —— config.py 只有定义与一句注释，调用在 server.py:176；再读 tests/web_ui/test_secret_key_gate.py:39-55 的结论。

**改成**：改成：在 `katrain/web/server.py:176` 那行之后紧跟 `assert_sms_provider_is_configured(settings.KATRAIN_MODE, settings.SMS_PROVIDER)`；并在 Task 5 补一条照抄 `test_gate_is_wired_into_the_server_lifespan` 形状的接线断言（`inspect.getsource(server._lifespan_server)` 里必须出现该函数名），变异验证=删掉那一行当场变红。

## [3] [high] plan.md:2161 (Task 12, server.py chat gate) vs plan.md:1607 (Task 8, pydantic User)

**错在哪**：聊天闸读 `getattr(current_user, "phone_e164", None)`，但计划只给 pydantic `User` 加了 `phone_bound`，从没加 `phone_e164` ⇒ 该属性恒缺失、fail-closed，所有人（含已绑号）都发不了言。

**怎么证明**：`katrain/web/api/v1/endpoints/auth.py:126` `get_user_from_token` 返回 `User(**user_dict)`，即 `katrain/web/models.py` 的 pydantic `User`；`server.py:2823` 的 WS `current_user` 正是它。计划 Task 8 只写「pydantic `User` 加 `phone_bound: bool = False`」。⇒ 计划自己的 `test_chat_from_bound_user_is_broadcast`（plan.md:2109）必红。计划在 2154-2160 的注释里已经点出这个风险，然后自己踩了进去。

**改成**：把 Task 12 的 server.py 判据改成与 live.py 同名的 `getattr(current_user, "phone_bound", False)`（同一个闸不能有两个属性名）；或者在 Task 8 里给 pydantic `User` 同时加 `phone_e164`——但那会把原始号带进 `/users/online`、`/api/v1/social` 等所有回 `User` 的响应，所以正确解是统一用 `phone_bound`。

## [4] [high] plan.md:824（Task 5「调用点」）

**错在哪**：计划说 fail-fast 的调用点在「`config.py` 里现有那次调用的紧邻位置」——`config.py` 里根本没有 `assert_secret_key_is_safe` 的调用，唯一调用点在 `katrain/web/server.py:176`（`_lifespan_server`）。照字面写会把闸塞进 config 模块顶层，等于每次 import config 就 fail-fast。

**怎么证明**：`grep -rn assert_secret_key_is_safe --include='*.py' katrain` → `config.py:6`(注释) / `config.py:13`(def) / `server.py:171,176`。config.py 内零调用。

**改成**：把这一行改成「调用点：`katrain/web/server.py:176` `_lifespan_server` 里 `assert_secret_key_is_safe(...)` 的紧邻下一行」。顺带确认 `tests/web_ui/test_secret_key_gate.py:69` 的 `test_gate_runs_before_any_database_work` 仍绿（插在其后不改 `gate_at`，实测不受影响）。

## [5] [high] plan.md:761-778（`assert_sms_provider_is_configured`）+ 缺失的 `tests/conftest.py` 改动

**错在哪**：闸一旦按 §2 接进 `_lifespan_server`，全量测试会集体红：测试进程的 `KATRAIN_MODE` 默认就是 `"server"`，而 `conftest.py` 没有注入 `KATRAIN_SMS_PROVIDER`。更糟的是闸**禁止 server 模式用 console**，所以连「conftest 里设成 console」这条退路也被自己堵死——只能声称 `aliyun`，于是 Task 6-9 的每一次 `issue()` 都会拿空凭据真去打 dysmsapi。

**怎么证明**：`katrain/web/core/config.py:83` `KATRAIN_MODE: str = "server"`、`:174` `data.setdefault("KATRAIN_MODE", os.getenv("KATRAIN_MODE", "server"))`；`tests/conftest.py:76-79` 只 setdefault 了 `KATRAIN_SECRET_KEY`，并在注释里写明「测试如果不注入，所有建 app 的用例会集体红」——这就是同一条链。⇒ Task 16 Step 1 的 `comm -23` 不可能为空。

**改成**：给闸开一条与「测试走生产同一条路」相容的口子：把 `console` 的禁令改成「server 模式 + 非测试进程」判不了，改判「`SMS_PROVIDER` 为空即拒」，另用一个显式的 `KATRAIN_SMS_ALLOW_CONSOLE=1`（默认关、生产不设）放行 console；并在 Task 5 的文件清单里加 `tests/conftest.py`，`os.environ.setdefault("KATRAIN_SMS_PROVIDER", "console")` + 那个开关，与 SECRET_KEY 同形。

## [6] [high] plan.md:761-778（Task 5 fail-fast）+ plan.md:2618-2622（收尾第 1 条）

**错在哪**：收尾自己写着「没有凭据、没实发过一条」，而这个闸会让**两台线上机器在合并后拒绝启动**（`KATRAIN_SMS_PROVIDER` 今天在两边都没设）。计划没有任何一步要求在部署前把这个 env 配上，也没说清「没凭据时该配什么」。

**怎么证明**：`assert_sms_provider_is_configured("server", "")` → `RaiseRuntimeError`，而它在 `_lifespan_server` 的第一批语句里 ⇒ uvicorn 起不来。测试环境 go.sailorvoyage.top 与生产 modelstella.com 的 compose 里现在都没有这个变量（同 F10 实测里查 `FORWARDED_ALLOW_IPS` 的那次，两边都是空）。

**改成**：在 Task 16 之后加一步部署前置：先在 home-ubuntu 的 compose 里加 `KATRAIN_SMS_PROVIDER=`（明确取值）并确认服务起得来，再上 ucloud（用户级规矩：先测试环境再生产）。并在计划里写死「拿不到阿里云凭据时线上配什么」——如果答案是 `aliyun` + 空 key，那 send-code 会对每个用户 502，这一点必须在计划里说出来，而不是留给部署当天发现。

## [7] [high] plan.md:106-116（`normalize_e164` 实现）vs plan.md:132（拒绝用例参数表）

**错在哪**：`normalize_e164("12345")` 不抛 `ValueError`，返回 `"+8612345"` ⇒ Task 1 Step 4 标的「Expected: PASS（全部）」做不到。裸号补 `+86` 之后只剩「总位数 7-15」这一个下限，挡不住短号。

**怎么证明**：把 plan.md:98-116 的函数原样跑一遍：`normalize_e164("12345")` → `'+8612345'`（`^\+[1-9]\d{6,14}$` 匹配 `+8612345`：`8` + 6 位）。我已实跑确认，8 个拒绝用例里只有它没抛。

**改成**：补一条国内号的长度判据：`elif not s.startswith("+")` 分支里补完区号后，若 `default_region_cc == "86"` 则要求本体恰好 11 位且首位为 1；或在正则之外加一句「`+86` 开头必须是 14 字符」。改完把 `"12345"` 与 `"+861380013800"` 一起留在拒绝表里。

## [8] [high] plan.md:1393（测试用 `REGISTER_IP_DAILY`）vs plan.md:1484（实现读 `settings.REGISTER_DAILY_CAP`）

**错在哪**：两个名字，两件事，且**两个都没进 `Settings`**（Task 5 的字段清单 plan.md:794-812 里没有）。`monkeypatch.setattr(..., raising=False)` 会安静地设上测试那个名字，实现读的另一个名字在 pydantic 模型上不存在 ⇒ AttributeError → 500，而不是断言里的 429。另外这把 D-U2 明确要求的「同一个限流器一行 Depends 挂到 `/auth/register`」降级成了全站每日总量闸，而计划的用例名和断言仍写着 per-IP。

**怎么证明**：读 plan.md:1393 与 1484 两行；再看 plan.md:794-812 的 `Settings` 新增字段列表，两个名字一个都没有。计划 1487-1494 的 ⚠️ 自己承认降级了，却没同步改测试。

**改成**：按计划自己推荐的 (a)：给 `users` 加 `signup_ip`（走同一套零手写 DDL 迁移，与 `phone_e164` 同批），做真 per-IP；`Settings` 加 `REGISTER_IP_DAILY`，测试与实现统一用这一个名字。若最终选 (b)，就把用例改名为 `test_register_is_capped_globally` 并断言 `register_capacity`，同时在计划里写明「这条闸的失败模式是今天没人能注册」。

## [9] [high] plan.md:2652（Task 16 Step 3 第 4 项）；requirements.md D-U2「UI 落在设置页 + 撞到免费额度闸时的那一处提示」

**错在哪**：绑定手机的**用户入口一个都没实现**：Task 13-15 只做了 api.ts / AuthContext / LoginModal 的验证码登录 / 同意项。galaxy 没有设置页，`/billing/quota` 在整个前端零消费者 ⇒ Step 3 第 4 项「设置页绑定手机 → 免费额度从『绑定手机号可每周免费复盘』变成『本周剩余 1 次』」无从执行，Task 11 新加的 `blocked_reason` 也没有任何 UI 会读。

**怎么证明**：`cd katrain/web/ui && grep -rn 'free_weekly\|billing/quota\|allowance' src` → 零命中；`ls src/galaxy/pages` → 没有 Settings/Profile 页。Task 13-15 的 Files 清单里也没有任何绑定入口组件。

**改成**：补一个 Task 15.5：`src/galaxy/components/auth/BindPhoneDialog.tsx`（复用 CountryCodeSelect + PhoneConsent + `API.bindPhone`），挂两个入口——galaxy 侧边栏/账户菜单一处，`ReportsPage` 撞到 402 `free_weekly_blocked === "phone_unbound"` 时一处；同时让复盘页真的去读 `/billing/quota` 的 `free_weekly.blocked_reason`。否则 Task 11 的 `blocked_reason` 是个没人读的字段，Task 16 Step 3.4 只能标「未验」。

## [10] [high] plan.md:2274 (Task 13 Step 3, `_phonePost` 的 headers 行)

**错在哪**：`API._authHeader()` 在 `api.ts` 里根本不存在——真正的助手是模块级导出的 `authHeaders(token?)`（`katrain/web/ui/src/api.ts:297`），于是四个手机 API 一调就 `TypeError: API._authHeader is not a function`。

**怎么证明**：`grep -rn "_authHeader" /Users/fan/Repositories/katrain-phone-login/katrain/web/ui/src` → 零命中；`grep -n "export function authHeaders" .../src/api.ts` → 297（另有 9 个文件在用它）。Task 13 的四条 vitest 都 mock 了 fetch，`_phonePost` 一进来就抛，四条全红。

**改成**：`_phonePost` 里改成 `headers: { "Content-Type": "application/json", ...authHeaders() }`，并在 Task 13 Step 3 写明 `authHeaders` 是 `api.ts:297` 已导出的模块级函数（它顺带处理 strict 盒子返回 `{}` 的那一档），不是 `API` 上的方法。

## [11] [high] plan.md:2161（Task 12 Step 3，server.py 聊天闸）

**错在哪**：用的是 `getattr(current_user, "phone_e164", None)`，但 WS 的 `current_user` 就是 `katrain/web/models.py:176` 那个 pydantic `User`，而整份计划只往它加了 `phone_bound`（plan.md:1607），从没加过 `phone_e164` ⇒ getattr 永远 None ⇒ **所有人（包括已绑号的）都发不了言**。计划自己在同一段写的「与 live.py 的 pydantic User 不是同一个类型」也是错的：两处都出自 `auth.py:125 return User(**user_dict)`。

**怎么证明**：读 `katrain/web/server.py:2765-2767`（WS 里 `current_user = await get_user_from_token(...)`）→ `katrain/web/api/v1/endpoints/auth.py:106,125`（`-> User`，`return User(**user_dict)`）→ `katrain/web/models.py:176` 的 `class User(BaseModel)`。再 `grep -n "phone_e164" superpowers/tracks/phone-login/plan.md` 确认没有一行把它加进 `models.py`。Task 12 的 `test_chat_from_bound_user_is_broadcast` 会当场变红。

**改成**：两处统一成 `if not current_user.phone_bound:`（直接属性访问，不用 getattr——字段是 Task 8 加进 `_to_dict` 与 pydantic `User` 的，缺了应该响而不是静默 fail-closed）；删掉「不是同一个类型」那条注释和「实现时先打日志确认是哪个类」那一步，答案已经确定。

## [12] [high] plan.md:1186（`getattr(last, "delivered_ok", True)`）与 plan.md:1268-1270（把列推迟到 Task 4 之后再补的那条「注意」）

**错在哪**：`delivered_ok` 不在 Task 4 的模型里，Task 6 用 `getattr(..., True)` 兜底；列漏掉时 `row.delivered_ok = False`（plan.md:1239）只是给 SQLAlchemy 实例挂了个未映射属性，**测试仍然绿而生产行为相反**——因为测试的两次 `issue()` 共用同一个 `db` session，identity map 返回同一个对象、stray 属性还在；生产的下一个请求是新 session，读回来是 True。

**怎么证明**：我用仓里的 SQLAlchemy 2.0.46 实跑过：同 session 查回来 `last is r` 为 True、`getattr(last,'delivered_ok',True)` 得 False；新开 session 查同一行得 True。⇒ 删掉 Task 4 的列后 `test_provider_failure_does_not_start_the_phone_cooldown` 照样过。可复现脚本：建一个只有 `id/phone` 两列的模型，`r.delivered_ok=False; commit()`，再在同/异 session 各查一次。

**改成**：把 `delivered_ok = Column(Boolean, nullable=False, default=True)` 写进 **Task 4** 的 `SmsChallenge` 模型和 Task 4 的列断言集合（`add_missing_columns` 的 `_default_clause`，migrations.py:351-372，会给它渲染 `DEFAULT TRUE`，迁移没问题）；冷却查询把判据放进 SQL：`.filter(models_db.SmsChallenge.delivered_ok.is_(True))`，删掉 Python 侧的 `getattr` 兜底。

## [13] [high] plan.md:1393（测试用 `REGISTER_IP_DAILY`）与 plan.md:1484（实现读 `settings.REGISTER_DAILY_CAP`）

**错在哪**：同一个 Task 里两个名字对不上，而且**两个都没被加进 `Settings`**：端点 `settings.REGISTER_DAILY_CAP` → AttributeError；测试的 `monkeypatch.setattr(settings, "REGISTER_IP_DAILY", 2, raising=False)` 在 pydantic 2.12 上直接 ValueError（`raising=False` 只跳过存在性预检，真正的 setattr 照样抛）。

**怎么证明**：`grep -n "REGISTER_" superpowers/tracks/phone-login/plan.md` 只有这两行且名字不同；`grep -n "REGISTER" katrain/web/core/config.py` 为空。实测：`./.venv/bin/python -c "from katrain.web.core.config import settings; setattr(settings,'REGISTER_IP_DAILY',2)"` → `ValueError: "Settings" object has no field "REGISTER_IP_DAILY"`。

**改成**：按 Task 7 自己推荐的 (a) 落地并定死一个名字（`REGISTER_IP_DAILY` + `users.signup_ip` 列），把字段同时写进 `Settings` 字段区和 `__init__` 的 `data.setdefault(...)` 两处（照 config.py:117-191 的形状，与 Task 2 的 `TRUSTED_PROXY_HOPS`、Task 5 的 `SMS_*` 同一段），测试与实现引用同一个名字。

## [14] [high] plan.md:1892（Task 10 `set_password` 实现）

**错在哪**：`repo.get_by_username(current_user.username)` 这个方法不存在——仓储上的名字是 `get_user_by_username`（`katrain/web/core/auth.py:64` 抽象声明、`:208` 实现）。运行时 AttributeError ⇒ `/auth/set-password` 每次 500，Task 10 的六条用例全红。

**怎么证明**：`grep -n "def get_" /Users/fan/Repositories/katrain-phone-login/katrain/web/core/auth.py` → `get_user_by_username` / `get_user_by_id` / `get_followers` / `get_following`，没有 `get_by_username`。

**改成**：这次查库本来就是多余的：`current_user.phone_bound` 在 Task 8 之后已经在 pydantic `User` 上了，直接写 `if not current_user.phone_bound: raise HTTPException(400, {"code":"phone_unbound"})`。顺带把 Task 8/9/10 新增的 `get_by_phone` / `get_phone_e164` 与既有 `get_user_by_*` 命名对齐（`get_user_by_phone` 等），别在同一个 ABC 里留两套命名。

## [15] [high] plan.md Task 9, `bind_phone` 仓储实现（plan.md:1763-1774，`u.phone_e164 = phone_e164` 在 :1767）

**错在哪**：`bind_phone` 无条件覆盖 `u.phone_e164`，于是「已绑手机的用户再绑一个新号」是一条**自助换绑**路径——而计划自己在 :2693 把「不做自助换绑与解绑」写成「一号一账号」经济论证的**必要前提**，又在 :2020 写「这条短路的正确性有一个前提:不存在『解绑手机』的路径」。换绑同时就是旧号的解绑。

**怎么证明**：读 plan.md:1763-1774：`bind_phone` 里除了 `filter_by(id=user_id).one()` 之外没有任何对 `u.phone_e164` 现值的判断；再看 Task 9 的六条测试（plan.md:1690-1720），没有一条用「已绑号的用户再次 bind」这个状态。落地后可实测：同一账号连续 bind 两个不同号，第二次返 200 且 `users.phone_e164` 变成第二个号。攻击链可证：手上有 3 张卡时，acct1 绑 A 消费免费复盘 → acct1 改绑 B（A 空出）→ acct2 绑 A 消费 → acct2 改绑 C（A 再空出）……每轮释放一个号给新账号，免费复盘份数不受卡数限制。合规侧同样破：用户可以用 A 号发言后改绑 B，仓里没有 `retired_phones`（需求 §1.2 明确不做），发言与实名主体的对应关系当场丢失。

**改成**：在 `bind_phone` 里先读现值：`if u.phone_e164 is not None and u.phone_e164 != phone_e164: return "already_bound"`，端点上返 409 `{"code": "already_bound", "message": "该账号已绑定手机号，换绑请联系客服"}`；同号重复绑定幂等返 200。Task 9 补两条用例（已绑号再绑新号 → 409 且库里号不变；再绑同号 → 200），并配一次变异（去掉守卫 → 用例变红）。

## [16] [high] plan.md Task 6 `issue()` 第 4 步与落行处（plan.md:1204-1206 计数、:1228 `provider_charged=True`）+ Task 5 `sms.py` 的两个 raise（plan.md:919 与 :921 用的是同一个 `SmsProviderError`）

**错在哪**：「供应商失败也计入日额度」的保守口径把**供应商明确拒收**（阿里云返回 `Code != OK`，即确定没计费）和**不可达/超时**（确实不知道收没收）合成了同一件事 ⇒ 一个不鉴权的攻击者可以用格式合法但一定被拒的号（`+9991234567`、12 位的 `+861380013800` 等）零成本把全站日额度打满，`send-code` 当天对所有人返 503 `sms_capacity`。

**怎么证明**：读 plan.md:1228：行以 `provider_charged=True` 落库，失败分支（:1235-1240）只把 `delivered_ok` 置 False，**不动 `provider_charged`**，而 :1204-1206 的日额度计数只按 `provider_charged=True` 数 ⇒ 被拒的行照样占额度。再读 plan.md:919/921：不可达与被拒抛的是同一个 `SmsProviderError`，调用方无从区分。算术：`SMS_DAILY_CAP_INTL=50`、`SMS_IP_DAILY=20`（plan.md:820/824）⇒ 3 个 IP × 20 次请求即可打满国际额度，攻击者花费为零、我们的短信费也为零，代价是国际通道整天不可用（而计划把国际通道定为「端到端先跑通」的那条，requirements §D-U4）。同号限流不构成阻碍：per-phone 计数键是攻击者自选的号串；冷却也不生效（失败不置冷却，plan.md:1237）。

**改成**：把两种失败分开：`sms.py` 拆成 `SmsProviderUnavailable`（网络层异常，保守计入额度）与 `SmsProviderRejected`（HTTP 200 但 `Code != OK`，阿里确定未计费）；`issue()` 捕到 rejected 时把该行 `provider_charged=False`（或直接删行）再抛。另外给「被拒次数」单独配一个远小于日额度的独立计数器（例如 per-IP 每日拒收 3 次即拉黑当日），否则拒收本身就是免费的额度消耗器。Task 6 变异表（plan.md:1281-1286）补一行：把 rejected 也计入额度 ⇒ 新增的「拒收不吃额度」用例变红。

## [17] [high] plan.md:737-748 (Task 5, test_aliyun_signature_matches_official_vector)

**错在哪**：The docstring says it pins the signature with 官方示例向量, but the only assertions are sort-order independence and len(sig)==28 — every base64(HMAC-SHA1) is 28 chars and every canonical-sorted string-to-sign is order-independent, so a wrong string-to-sign stays green.

**怎么证明**：python3 -c "import base64,hmac,hashlib,urllib.parse; ..." — I ran it: correct 'GET&%2F&' prefix gives CcKODMBPhTI057R1vq4tB8nFpAM=; a 'POST&%2F&' prefix gives /4bxc/M86lwsQa9TM0/hqhzzAQk=; forgetting the trailing '&' on the secret gives 6cxlxvzrKrmv0Fav3E2HOVHQqw8=. All three are 28 chars and all three are order-independent, so all three pass this test. Since 本轮 aliyun 不作为验收项 (no credentials, never sent one), this test is the entire defense for that provider.

**改成**：Assert the exact expected base64 for one frozen (secret, params) pair taken from Aliyun's documented example, and additionally assert the intermediate canonical string equals the documented one (expose _string_to_sign). Add a mutation record: change the prefix to 'POST&%2F&' and confirm it goes red.

## [18] [high] plan.md Task 7 test list (lines ~1310-1400); the only XFF-aware test is the unit test at plan.md:267/349

**错在哪**：No test at any level observes which IP the send-code endpoint actually passes to the rate limiter. Task 2 proves client_ip_for_ratelimit is correct as a function; Task 6 proves sc.issue partitions by whatever client_ip it is handed. If the endpoint is written `ip = request.client.host`, every test in Tasks 2, 6 and 7 is still green — and that is precisely the production defect F10 documents, which spec §2.4 says must have an assertion.

**怎么证明**：grep -n 'orwarded' superpowers/tracks/phone-login/plan.md → only lines 267, 329, 349, 353, 388, all inside Task 2's unit test and the module docstring. No endpoint-level test sets X-Forwarded-For. (Task 2's own test_two_different_clients_get_different_buckets IS sound at the unit level — both _req() calls share the same default peer, so `return peer` does go red — the gap is one layer up.)

**改成**：Add to Task 7: with SMS_IP_DAILY=1, POST send-code with headers={'X-Forwarded-For':'203.0.113.9'} → 200; same XFF, different phone → 429 sms_quota_ip; then headers={'X-Forwarded-For':'198.51.100.7'}, third phone → must be 200. Mutation: replace the endpoint's client_ip_for_ratelimit(request) with request.client.host and confirm the third call turns 429.

## [19] [high] plan.md:2161 (Task 12 impl) vs /Users/fan/Repositories/katrain-phone-login/katrain/web/api/v1/endpoints/auth.py:125 and /Users/fan/Repositories/katrain-phone-login/katrain/web/server.py:2769-2772

**错在哪**：`getattr(current_user, "phone_e164", None)` will always be None, so the chat gate mutes every user including bound ones. The plan leaves this as an open question; it is answerable from the source today.

**怎么证明**：server.py:2769 sets current_user = await get_user_from_token(...); auth.py:125 ends `return User(**user_dict)` — the pydantic katrain/web/models.py:176 User. Task 8 adds `phone_bound` to that model, not `phone_e164`, and _to_dict (core/auth.py:323-334) never carries phone_e164 either. Run: sed -n '120,126p' katrain/web/api/v1/endpoints/auth.py; grep -n 'class User' -A12 katrain/web/models.py

**改成**：Use `if not current_user.phone_bound:` — the same attribute live.py uses — and drop the getattr default, so a future rename fails loudly instead of silently muting the whole site. Delete the 'confirm which class this is by logging' note; the answer is models.User.

## [20] [high] plan.md:2123-2127 (Task 12, test_unbound_user_message_is_not_broadcast_to_anyone) + /Users/fan/Repositories/katrain-phone-login/katrain/web/session.py:258-268

**错在哪**：`assert not _has_pending(ws_observer)` cannot measure the gate. Broadcast is fire-and-forget (loop.create_task / run_coroutine_threadsafe), so with the gate removed the leaked frame may not have been delivered yet when _has_pending runs → green. In the other direction, the observer's queue already holds the game_update and spectator_count frames the server sends at connect (server.py:2800 and 2815), so _has_pending is True regardless unless the fixture drains them → red regardless. Same root problem sinks test_chat_from_bound_user_is_broadcast, which does ws_observer.receive_json()['text'] on what will be the game_update frame.

**怎么证明**：Read session.py:258-268 (_schedule_broadcast uses create_task, never awaited by the request handler) and server.py:2800/2815 (two frames pushed on connect). Then: with the gate removed, run the test in a loop — it will pass intermittently.

**改成**：Replace the absence assertion with an ordering assertion that has a synchronization point: after the unbound user's message is rejected, have a bound user send a sentinel; drain the observer to the first frame with type=='chat' and assert its text is the sentinel and never 'leak'. Same drain-to-type-chat for test_chat_from_bound_user_is_broadcast.

## [21] [high] plan.md front-matter 前端文件表 + Tasks 13-15; acceptance item at plan.md:2652

**错在哪**：No task builds any bind-phone entry point. API.bindPhone is defined at plan.md:2295 and never called from any component. Task 16 Step 3 item 4 asks the verifier to 'go to 设置页 bind the phone, then watch the 复盘页 free-quota copy change' — neither the settings UI nor the quota copy exists, and no task creates them. Meanwhile Tasks 11 and 12 revoke free reports and chat from every existing account.

**怎么证明**：grep -rn 'billing/quota\|free_weekly' katrain/web/ui/src → 0 hits (the frontend has no billing client at all). grep -n 'bindPhone' superpowers/tracks/phone-login/plan.md → only 2207 and 2295, both definitions.

**改成**：Either add a task before 16 that renders the binding flow (settings page + the '撞到免费额度闸' prompt named in requirements D-U2, which is the only place the user has a motive), or delete item 4 from Task 16 and record 'no bind UI shipped' in the 收尾清单 as a hard blocker before BILLING_ENFORCED is ever opened.

## [22] [high] plan.md:1474-1493（Task 7 「给 /auth/register 挂同一个限流器」+ 二选一注记）

**错在哪**：必答题的推荐：**选 (a) 真 per-IP**，并把计划正文里那段 (b) 的代码删掉而不是留着。(a) 的成本不是计划说的「一行」而是 5 行，但全在既有机制上；(b) 写出来的是一个任何匿名脚本几秒就能扳下的「全站今日注册关闭」开关，且没有绕过口。

**怎么证明**：(a) 的 5 行逐条可查：① `katrain/web/core/models_db.py:64-88` User 加 `signup_ip = Column(String(45), nullable=True)`（1 行，和 Task 4 的 phone_e164 同一处）；② `katrain/web/core/auth.py:58` 抽象方法签名加 `signup_ip: Optional[str] = None`（1 行）；③ `katrain/web/core/auth.py:190-194` 实现签名 + `models_db.User(..., signup_ip=signup_ip)`（2 行）；④ `katrain/web/api/v1/endpoints/auth.py:352` 调用点加 `signup_ip=ip`（1 行）。因为是带默认值的关键字参数，`grep -rn 'create_user(' katrain tests` 列出的其余约 40 个调用点（几乎全在 tests/）一行都不用动。迁移确实零手写 DDL：`katrain/web/core/migrations.py:324-347` 的 `add_missing_columns` 对 nullable 且无 scalar default 的列走 `_default_clause`（migrations.py:350-368）返回 None，拼出 `ALTER TABLE "users" ADD COLUMN "signup_ip" VARCHAR(45)`，两个方言都过；`katrain/web/core/auth.py:142-144` 的 init_db 启动时就调它。关键的一条：`katrain/web/core/auth.py:323-334` 的 `_to_dict` 是**显式白名单**（只列 id/uuid/username/hashed_password/rank/credits/is_admin/avatar_url/created_at），只要不往里加，signup_ip 就绝不会进 `/auth/me`、`OnlineUser`、`/api/v1/social`——所以 (a) 没有「把 IP 泄露到公开资料」这条代价。(b) 的表现：`db.query(func.count(User.id)).filter(User.created_at >= day0)` 数的是**今天全站新建的所有 user 行**，打满之后每一个真实新用户都拿 429 `register_capacity`；改 cap 要改 env 再重启容器（`katrain/web/core/config.py:39` `class Settings(BaseModel)`，值在构造时从 os.getenv 装配），没有 admin 旁路。生产今天一共 9 个账号（requirements.md D-U1），任何「不妨碍正常增长」的 cap 都低到一次脚本就能打满。(b) 数的行里还混着 `katrain/web/server.py:210` 启动自建的 admin 账号和盒子本地库的影子用户——量的不是注册压力。最后，(b) 让 spec §2.4 那条硬性断言（「两个不同客户端 IP 拿到的桶不是同一个」）在 register 这一端**根本写不出来**，而 plan.md:1387 那条用例名字就叫 `test_register_is_rate_limited_by_ip` 却一个 IP 都没变——正是 F10 点名的「在一个桶的世界里也是绿的」形状。

**改成**：删掉 plan.md:1474-1493 那段 (b) 代码与二选一注记，改写成 (a)：加 `users.signup_ip` 列 + `create_user(..., signup_ip=None)` + 调用点传 `client_ip_for_ratelimit(request)`；限流查询改成 `.filter(User.signup_ip == ip, User.created_at >= day0)`；测试补一条 Task 2 同形的断言：两个不同 `X-Forwarded-For` 各自拿到自己的配额（第一个 IP 打满后第二个 IP 仍能注册）。顺带把 plan.md:1490 的「成本一行」改成「五行，签名两处 + 调用点一处 + 模型一行；_to_dict 是白名单所以不用动，也因此不外泄」。

## [23] [high] plan.md:1393（测试）与 plan.md:1484（实现）

**错在哪**：限流开关的名字在测试和实现里对不上（`REGISTER_IP_DAILY` vs `REGISTER_DAILY_CAP`），而且**两个名字都没有在 config.py 的 Settings 里声明**。Settings 是 pydantic BaseModel，两边都会当场抛异常，不是「读到默认值」。

**怎么证明**：已实测：`cd /Users/fan/Repositories/katrain-phone-login && ./.venv/bin/python -c "from katrain.web.core.config import settings; setattr(settings,'REGISTER_IP_DAILY',2)"` → `ValueError: \"Settings\" object has no field \"REGISTER_IP_DAILY\"`（`raising=False` 只影响 monkeypatch 自己的存在性检查，挡不住 pydantic 的 __setattr__），`... settings.REGISTER_DAILY_CAP` → `AttributeError: 'Settings' object has no attribute 'REGISTER_DAILY_CAP'`。再对照 `grep -n 'REGISTER_' superpowers/tracks/phone-login/plan.md` 只有这两行，Task 5 的 config.py 清单（plan.md:678-780）里一个都没有。Task 2（plan.md:388-395）对 TRUSTED_PROXY_HOPS 明写了「Settings 里加字段、__init__ 里加 env 装配，**两处都要写**」，Task 7 一处都没写。

**改成**：在 `katrain/web/core/config.py` 的 Settings 里加 `REGISTER_IP_DAILY: int = 20`，并在 __init__ 里加 `data.setdefault("REGISTER_IP_DAILY", int(os.getenv("KATRAIN_REGISTER_IP_DAILY", 20)))`；测试和实现统一用这一个名字。

## [24] [high] plan.md:2274（Task 13 `API._phonePost` 里的 `...API._authHeader()`）

**错在哪**：`API._authHeader()` 这个方法在仓里不存在。真正的鉴权头助手是 `api.ts` 里模块级导出的 `authHeaders(token?)`。照抄这行会让 `npm run build` 直接挂，而实现者最可能的「修法」是自己再写一个 _authHeader，那会绕过 authHeaders 里那段严格盒端的特判。

**怎么证明**：`grep -rn '_authHeader' /Users/fan/Repositories/katrain-phone-login/katrain/web/ui/src` → 零命中（exit 1）。真正的助手在 `katrain/web/ui/src/api.ts:297` `export function authHeaders(token?: string)`，`apiPost`（api.ts:311）就是这么用的。`npm run build` = `tsc -b && vite build`（package.json:7），tsconfig.app.json 的 include 是 `src` ⇒ 会被检查。我用仓里那份 tsc 跑了等价片段：`/Users/fan/Repositories/katrain/katrain/web/ui/node_modules/.bin/tsc --strict --noEmit ...selfref.ts` → `error TS2339: Property '_authHeader' does not exist on type '{ _phonePost: ...; sendPhoneCode: ...; }'`。

**改成**：把 plan.md:2274 改成 `headers: { "Content-Type": "application/json", ...authHeaders() }`，并在计划里明写「用 api.ts:297 已有的 authHeaders，**不要另写一个**」——api.ts:279/298 那段 `if (isStrictBoxKiosk) return {}` 带着注释「严格盒端…这里绝不能自己造 Bearer 头」，复制一份等于在共享领土里把这条规矩绕过去。

## [25] [high] plan.md:2350-2420（Task 14 全部 8 条）与 plan.md:2496-2545（Task 15 全部 6 条）

**错在哪**：这 14 条用例都是裸 `render(<LoginModal open onClose={() => {}} />)`，没有任何 Provider。`useAuth` 和 `useSettings` 在没有 Provider 时**直接抛异常**，所以每一条在渲染那一行就炸——Step 2 写的「Expected: FAIL — 找不到「验证码登录」」是假的红因，照着它去改组件会走错方向。

**怎么证明**：`katrain/web/ui/src/context/AuthContext.tsx:153-157` → `throw new Error('useAuth must be used within an AuthProvider')`；`katrain/web/ui/src/context/SettingsContext.tsx:12-16` 同形。LoginModal 第 14、15 行两个都调。仓里已经把这个坑写在注释里了，就在同目录：`katrain/web/ui/src/galaxy/components/auth/AuthRequiredDialog.tsx:53-55`「按需挂载：`LoginModal` 自己调 `useSettings()`，在没有 SettingsProvider 的地方(比如只渲染本页的单测)光是构造它就会抛」。另外 `AuthContext.tsx:41-56` 挂载即 `fetch('/api/v1/auth/me')`，不 stub 会打真网络。

**改成**：两个测试文件都抽一个 `renderModal()` 助手，套 `<AuthProvider><SettingsProvider>…</SettingsProvider></AuthProvider>`，并照 `katrain/web/ui/src/context/AuthContext.test.tsx:1-40` 的现成写法先 stub `global.fetch` 与 localStorage；Step 2 的 Expected 改成真实红因。

## [26] [high] plan.md:2589-2600（Task 15 Step 5「确认 /privacy 这个链接真的到得了」）

**错在哪**：这条检查会被它自己刚写进 PhoneConsent.tsx 的 `href="/privacy"` 命中，因此必然报绿——它量的是链接文本，不是路由。而 /privacy 今天不存在，且落到的不是 404 而是禅模式棋盘。另外仓里已经有一份隐私政策正文，这条 grep 看不见它，而那份正文一个字没提手机号。

**怎么证明**：现在跑 `cd /Users/fan/Repositories/katrain-phone-login && grep -rn '"/privacy"\|path="privacy"' katrain/web/ui/src --include='*.tsx'` → 零命中，exit 1。我把 `<Link href="/privacy" target="_blank">policy</Link>` 单独写进一个临时 .tsx 再跑同一条 grep → 命中，exit 0：所以 Task 15 写完代码后这条 gate 恒绿。路由：`katrain/web/ui/src/AppRouter.tsx:36-49` 只有 `/kiosk/*`、`/galaxy/*`、`/record`、`/*`；非 strict 构建下 `/*` → `ZenModeApp`（AppRouter.tsx:46-47），所以点「《隐私政策》」打开的是禅模式棋盘，不是 404。已有正文：`katrain/web/ui/src/legal/privacy.ts`（PRIVACY_TITLE / PRIVACY_CONTENT，4.3KB），`grep -rn 'legal/privacy' katrain/web/ui/src` 零消费者；`grep -n '手机' katrain/web/ui/src/legal/privacy.ts` 零命中——它只写了用户名/对弈记录/设备信息/操作日志。

**改成**：判据换成落在路由上而不是链接上：`grep -n 'path="/privacy"' katrain/web/ui/src/AppRouter.tsx`（或 GalaxyApp 的路由表），并在真浏览器里打开 /privacy 确认渲染的是政策页。页面内容用 `src/legal/privacy.ts` 当唯一真源（把手机号那一条补进去），不要另写一份与它并行。Task 15 的选项 (b)「链到已有的政策页」按事实是不成立的，应删掉。

## [27] [high] plan.md:2437-2441（Task 14 Step 3「把 isRegister: boolean 换成 mode」这一句）与 katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx

**错在哪**：改动面比一句话大：isRegister 有 11 处 / 9 行。最容易漏、也最要命的是 `handleSubmit` 的第一道守卫 `if (!username || !password)`——验证码模式下这两个都是空，提交会**当场短路成「Please fill in all fields」**，Task 14 那条期待「还没有绑定账号」的用例永远不可能绿。其次是 `toggleMode` 的二值取反和成功后 setTimeout 里的状态复位，三模式下都得重写。

**怎么证明**：`grep -in isregister /Users/fan/Repositories/katrain-phone-login/katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx` → 行 16/32/39/53/65/75/103/119/126，共 11 处。再读 LoginModal.tsx:24-30：`handleSubmit` 开头就是 `if (!username || !password) { setError(i18n.t('auth:err_fill_all', ...)); return; }`。

**改成**：Step 3 把改动点逐条列出来，至少四处必须点名：(1) LoginModal.tsx:27 的守卫改成按 mode 分支（phone 模式校验的是手机号+验证码+同意勾选）；(2) :65 `toggleMode` 从取反改成显式 setMode，并新增「忘记密码？」→ setMode('phone')；(3) :49-55 成功后的复位要把新增的 phone / code / 倒计时 timer / consent 一起清掉，否则下次打开对话框会带着上一位用户的手机号和一个还在跑的倒计时；(4) :99/:112 那两个 onKeyPress=Enter 提交，手机号与验证码两格也要有。

## [28] [medium] plan.md:1892（Task 10 set-password 实现）`me = repo.get_by_username(current_user.username)`

**错在哪**：仓储没有 `get_by_username` 这个方法；实际名字是 `get_user_by_username`（抽象声明 core/auth.py:62，实现 core/auth.py:210）。照抄会 AttributeError。

**怎么证明**：`grep -n "def get_user_by_username\|def get_by_username" /Users/fan/Repositories/katrain-phone-login/katrain/web/core/auth.py` → 只有 62/210 两处 `get_user_by_username`。

**改成**：plan.md:1892 改为 `me = repo.get_user_by_username(current_user.username)`。

## [29] [medium] plan.md:1597 与 plan.md:1764（Task 8 `get_by_phone` / Task 9 `bind_phone` 的仓储实现）`session = self._session()`

**错在哪**：`SQLAlchemyUserRepository` 上没有 `_session`；取会话一律是 `self.session_factory()`（构造于 core/auth.py:95-96，全类 12 处都这么写，如 :191、:210、:220）。另外类名是 `SQLAlchemyUserRepository`（core/auth.py:94），计划正文写的 `SqlAlchemyUserRepository` 大小写不对，按它去 grep 会找不到。

**怎么证明**：`grep -n "class SQLAlchemyUserRepository\|self.session_factory()\|self._session" /Users/fan/Repositories/katrain-phone-login/katrain/web/core/auth.py`。

**改成**：两处 `self._session()` 改成 `self.session_factory()`；plan.md:1595 的类名改成 `SQLAlchemyUserRepository`。

## [30] [medium] plan.md:1762-1775（Task 9 `bind_phone` 仓储实现）

**错在哪**：函数体用了 `datetime.now(timezone.utc)` 和 `except IntegrityError`，但 `core/auth.py` 模块顶部只有 `from datetime import datetime, timedelta`（core/auth.py:3，**没有 timezone**），而 `IntegrityError` 是在 `create_user` 函数体内部才 import 的（core/auth.py:202），模块作用域拿不到。照抄两处都会 NameError，而且是只在「绑号被占」这条分支才炸的那种。

**怎么证明**：`sed -n '1,10p;200,205p' /Users/fan/Repositories/katrain-phone-login/katrain/web/core/auth.py`。

**改成**：在 plan.md 的 Task 9 Step 3 里明写：`core/auth.py` 顶部补 `from datetime import timezone` 与 `from sqlalchemy.exc import IntegrityError`（或在 `bind_phone` 体内 import，与既有 create_user 同形）。

## [31] [medium] plan.md:473（Task 3 Step 5 的端到端 500→401 用例）`client_with_sentinel_user.post("/api/v1/auth/login", data={...})`

**错在哪**：`/auth/login` 收的是 JSON 体（`login_data: LoginRequest`，pydantic BaseModel，定义在 endpoints/auth.py:80，端点在 :232），不是表单。`data=` 发 form-urlencoded ⇒ FastAPI 返 422，断言 `== 401` 直接红，而红的原因与 verify_password 无关；实现者很可能把断言改成 422，那条用例就再也证明不了任何东西。

**怎么证明**：`sed -n '80,84p;231,234p' /Users/fan/Repositories/katrain-phone-login/katrain/web/api/v1/endpoints/auth.py`；对照全仓既有写法 `grep -rn "auth/login" /Users/fan/Repositories/katrain-phone-login/tests/` —— 20 处全是 `json=`。

**改成**：plan.md:473 改成 `client_with_sentinel_user.post("/api/v1/auth/login", json={"username": "shadowy", "password": "x"})`。

## [32] [medium] plan.md:2274（Task 13 `api.ts` 的 `_phonePost`）`...API._authHeader()`

**错在哪**：`API` 对象（api.ts:324 起）上没有 `_authHeader`；模块导出的是顶层函数 `authHeaders(token?)`（api.ts:297），既有代码一律写 `authHeaders(token)`（api.ts:311、334、372、429）。照抄过不了 tsc/构建，而 Task 13 Step 5 要求两个构建都绿。

**怎么证明**：`grep -n "_authHeader\|export function authHeaders\|authHeaders(" /Users/fan/Repositories/katrain-phone-login/katrain/web/ui/src/api.ts`。

**改成**：plan.md:2274 改成 `headers: { "Content-Type": "application/json", ...authHeaders() },`（`authHeaders` 已在同文件模块作用域内）。

## [33] [medium] plan.md:2357、2365、2374、2386、2402、2408、2504、2510、2517、2525、2533、2541（Task 14/15 里全部 `render(<LoginModal open onClose={() => {}} />)`）

**错在哪**：`LoginModal` 组件体第 14-15 行就调 `useSettings()` 与 `useAuth()`，两个 hook 在没有 Provider 时都**抛异常**（AuthContext.tsx:153-157 `throw new Error('useAuth must be used within an AuthProvider')`；SettingsContext.tsx:12-18 同形）。这 12 处 render 全部会在渲染那一刻抛，两个 Task 的 14 条用例一条也跑不起来。

**怎么证明**：`sed -n '13,16p' /Users/fan/Repositories/katrain-phone-login/katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx` 与 `sed -n '153,158p' /Users/fan/Repositories/katrain-phone-login/katrain/web/ui/src/context/AuthContext.tsx`。

**改成**：在两个测试文件里加一个 `renderModal()` 辅助，把 `<LoginModal>` 包进 `<SettingsProvider><AuthProvider>…</AuthProvider></SettingsProvider>`（或 mock 这两个 context 模块），plan.md 的 Step 1 片段照此改写一次即可，两个 Task 复用。

## [34] [medium] plan.md:1980-1981、1994-1996（Task 11 的 `test_unbound_user_report_does_not_consume_free_quota` / `test_billing_gate_off_is_unchanged_for_everyone`）

**错在哪**：这两条对 `POST /api/v1/reports` 的结果做断言，但复用的是同一个 `db` 夹具。`/api/v1/billing/quota` 的会话来自 `get_db`（core/db.py:46-51，直接用模块级 `SessionLocal`），而 `POST /reports/` 的会话来自 `get_report_db`（reports.py:127-133，取 `app.state.report_session_factory`）—— 两条完全不同的库接缝。夹具没把两边接到同一个库时，`db.query(QuotaBucket).count() == 0` 会**无论实现对错都绿**（桶建在另一个库里），正好是这个 Task 唯一要防的那种假绿。

**怎么证明**：`sed -n '127,134p' /Users/fan/Repositories/katrain-phone-login/katrain/web/api/v1/endpoints/reports.py` 对照 `sed -n '46,52p' /Users/fan/Repositories/katrain-phone-login/katrain/web/core/db.py`；既有夹具的正确形状见 tests/web_ui/test_report_charging.py:71（`fastapi_app.state.report_session_factory = TestSessionLocal`）。

**改成**：在 Task 11 的夹具说明里明写：必须同时设 `app.state.report_session_factory = TestSessionLocal` **和** `app.dependency_overrides[get_db] = ...`（指向同一个 `TestSessionLocal`），并加一条前置断言证明 report 路径确实会往这个 `db` 里写（例如先跑一次已绑号的免费复盘、断言 `QuotaBucket.count() == 1`），否则那条 `== 0` 不成立为证据。

## [35] [medium] plan.md:1980、1986、1994（Task 11 三条 POST /api/v1/reports 用例的请求体 `{"user_game_id": 1, "report_type": "normal"}`）

**错在哪**：reports.py:247-256 先按 `UserGame.id == task.user_game_id AND UserGame.user_id == current_user.id` 查，查不到直接 404 "Game not found" —— 在计费/额度那段之前。计划没有任何夹具建这行 UserGame，于是 `test_billing_gate_off_is_unchanged_for_everyone` 期望的 200/"pending" 会是 404，另两条期望的 402 也到不了。

**怎么证明**：`sed -n '233,257p' /Users/fan/Repositories/katrain-phone-login/katrain/web/api/v1/endpoints/reports.py`；对照既有做法 tests/web_ui/test_report_charging.py 里如何造 UserGame。

**改成**：Task 11 的夹具清单里补一条：为 `auth_client_no_phone` / `auth_client_with_phone` 各建一行 `models_db.UserGame`（带可解析的 `sgf_content`，因为 reports.py:292 会 `count_moves`），并在计划里写出它的 id 与所属用户。

## [36] [medium] plan.md:2274（Task 3 的 `_phonePost`）

**错在哪**：`API._authHeader()` 不存在。仓里的鉴权头助手是 `api.ts:297` 的**模块级** `authHeaders(token?)`（且它在 strict kiosk 下返回 `{}`、否则从 localStorage 取 token）。`npm run build` 是 `tsc -b && vite build`，这一行会让 Task 13 Step 5 的两个构建都过不去。

**怎么证明**：`grep -n '_authHeader' katrain/web/ui/src/api.ts` → 零命中；`sed -n '297,309p' katrain/web/ui/src/api.ts` 看到 `export function authHeaders(...)`；`sed -n '7,9p' katrain/web/ui/package.json` 看到 build 链着 `tsc -b`。

**改成**：把 `...API._authHeader()` 改成 `...authHeaders()`（同文件模块级函数，`apiPost` 在 :311 就是这么用的）。顺带：send-code / phone-login 是不鉴权端点，带上这个头无害但也无用，只有 bind / set-password 需要——可以让 `_phonePost` 接一个 `auth: boolean` 参数，别让四个端点都无差别带 token。

## [37] [medium] plan.md:2589-2600（Task 15 Step 5 的 `/privacy`）+ plan.md:2607（该 Task 的 git add）

**错在哪**：仓里有 `src/legal/privacy.ts` 但**零个 importer、没有任何路由**，所以 Step 5 的 grep 必然空 ⇒ 一定要走选项 (a) 新建页面。而新建的页面必然落在 `src/galaxy/components/auth/` 之外（`AppRouter.tsx` 或一个新 page），于是：① Task 15 的 `git add <目录>` 不会把它带上；② Task 15 没有 `npm run build` / `build:kiosk-2d` 步骤，而 `AppRouter.tsx` 两个包都吃。

**怎么证明**：`grep -rn 'legal/privacy\|Privacy' katrain/web/ui/src` → 只有 `src/legal/privacy.ts:1` 自己；`grep -n 'path=' src/AppRouter.tsx` → 没有 privacy 路由。

**改成**：在 Task 15 里写死落点与归属：把页面放 `src/galaxy/pages/PrivacyPage.tsx`、路由加在 galaxy 自己的路由表里（不动 `AppRouter.tsx`，就不涉及 kiosk 包），内容 import 现成的 `src/legal/privacy.ts`；git add 显式列出这两个文件；并给 Task 15 补上与 Task 13/14 同样的两个构建步骤。

## [38] [medium] plan.md:1801-1900（Task 10 `/auth/set-password` 的用例表）

**错在哪**：计划实际新增了**四个**端点，但「每一个都要显式回答盒子问题」的红用例只给了三个：Task 7/8/9 各有 `*_403_on_strict_box` 与 `*_503_on_board_and_does_not_forward`，Task 10 一条都没有。代码里 `_guard_phone_endpoint(request)` 是调了，但没有任何断言守着它——哪天有人把它挪到 `verify_and_consume` 之后或删掉，全套仍绿。

**怎么证明**：数 plan.md:1810-1860 的用例：`test_requires_auth` / `test_sets_password_and_old_one_stops_working` / `test_challenge_phone_must_match...` / `test_unbound_user_gets_phone_unbound...` / `test_rejects_a_login_purpose_challenge` / `test_old_tokens_still_work...`，没有 strict/board 两条。对比 plan.md:1355-1365 与 1454-1460。

**改成**：给 Task 10 补 `test_set_password_403_on_strict_box(strict_box_auth_client)` 与 `test_set_password_503_on_board_and_does_not_forward(board_auth_client, remote_spy)`，并把 Step 的变异验证写成「注释掉 `_guard_phone_endpoint(request)`，这两条当场变红」。

## [39] [medium] plan.md:2412-2421（Task 14 的 i18n 中文默认值闸）

**错在哪**：这条闸本身跑不起来也拦不住东西：`LEGACY_ENGLISH_DEFAULTS` 从未定义（ReferenceError）、`readFileSync` 没 import；而且判据 `^[A-Za-z ?'.!]+$` 只认纯字母加五个标点——任何带数字、逗号、`{}` 插值的英文默认值（`'Please wait {n} seconds'`、`'Code sent, 60s'`）都溜过去，正是新增文案最可能的形状。

**怎么证明**：读 plan.md:2415-2420 三行；再看真实反例 `katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx:28` `i18n.t('auth:err_fill_all', 'Please fill in all fields')` —— 它能被这条闸抓到，但 `'Passwords do not match'`（:34）也能，于是白名单必须逐条列全，与同一 Task「顺带把本次触碰到的旧键默认值改成中文」的指示直接打架。

**改成**：判据换成正判不换反判：断言**本轮新增的那批键**（显式列出 key 名）的默认值必须命中 `/[一-龥]/`，旧键完全不进这条闸的射程；同时把 `readFileSync` 的 import 和文件路径（用 `new URL('../LoginModal.tsx', import.meta.url)`，别用相对 cwd）写进用例。

## [40] [medium] plan.md:938-1090（Task 6 的用例）与 plan.md:952-960（夹具说明）

**错在哪**：`settings.SMS_PROVIDER` 默认是 `""`，而 `get_provider()` 对空值直接抛 `SmsProviderError`（plan.md:922-931）。Task 6 的 11 条用例里只有 3 条 monkeypatch 了 provider，其余 5 条（`test_issue_stores_only_a_hash` / `test_cooldown_...` / `test_verify_consumes_once_only` / `test_purpose_mismatch_...` / `test_expired_...`）会在 `issue()` 里当场抛，Step 4 的「Expected: PASS（11 条）」做不到。

**怎么证明**：读 plan.md:922-931 的 `get_provider()` 三个分支；再数 plan.md:938-1090 里出现 `monkeypatch.setattr(sc.sms, "get_provider", ...)` 的用例只有三条。

**改成**：在 Task 6 的夹具说明里写死一个 autouse fixture：`monkeypatch.setattr(sc.sms, "get_provider", lambda: _P(None))`（记录码到列表，`_last_code()` 从它取），需要模拟失败的用例再各自覆盖。这条 fixture 和上面第 3 条的 conftest 开关是同一个问题的两半，改的时候一起改。

## [41] [medium] plan.md:824（「调用点：与 `assert_secret_key_is_safe(...)` 同一处（`config.py` 里现有那次调用的紧邻位置）」）与 Task 5 的 Files 段（plan.md:678 起）、`git add` 行（plan.md:945）

**错在哪**：`config.py` 里没有任何一处**调用** `assert_secret_key_is_safe`（只有 :6 的注释和 :13 的定义），唯一的生产调用点是 `katrain/web/server.py:176`，在 `_lifespan_server` 里。计划把实现者指向了错的文件；而 Task 5 的 Files 与 `git add` 又都不含 `server.py`，配上 Global Constraints #11「不许 `git add -A`」，接线那一行会被漏出提交——闸函数写完了没人调，`console` 在生产照样静默生效。

**怎么证明**：`grep -rn "assert_secret_key_is_safe" katrain/` → `config.py:6`（注释）、`config.py:13`（def）、`server.py:171,176`（唯一调用）。仓里已经有这个教训的现成闸：`tests/web_ui/test_secret_key_gate.py:47 test_gate_is_wired_into_the_server_lifespan`（注释里写着「函数被测透，唯一的生产调用点没有闸」）。

**改成**：把 plan.md:824 改成「调用点：`server.py:176` 的 `assert_secret_key_is_safe(...)` 紧邻一行」，Task 5 的 Files 与 `git add` 都加上 `katrain/web/server.py`，并照 `test_secret_key_gate.py:47` 抄一条断言：`inspect.getsource(server._lifespan_server)` 里必须含 `assert_sms_provider_is_configured`。

## [42] [medium] plan.md:785（`SMS_PROVIDER: str = ""`）+ plan.md:925-933（`get_provider` 未知名就抛）+ Task 7 Step 1 的 `client` 夹具（plan.md:1322 起）

**错在哪**：Task 5 产出的 `get_provider()` 在默认配置（`SMS_PROVIDER=""`）下抛 `SmsProviderError`，而 Task 7–10 的 HTTP 测试从没配过它 ⇒ 每次 send-code 都走 502 分支。另外 `_send_and_get_cid` / `_last_code` 在 Task 8/9/10 三个测试文件里被用了十几次，却只在 Task 6 的说明段（plan.md:1103）提了一句由 `_P` 记录，两个新文件里既没定义也没导入。

**怎么证明**：顺着读：`get_provider()`（plan.md:925）对 `""` 落到 `raise SmsProviderError`；Task 7 的 `test_send_code_does_not_leak_whether_the_phone_has_an_account` 断言两次都 200、`test_send_code_never_returns_200_when_rate_limited` 断言 429——两条在 502 世界里都不可能过。`grep -n "_last_code\|_send_and_get_cid" plan.md` 看它们出现在 test_phone_endpoints.py / test_set_password.py 段落里而无定义。

**改成**：在 Task 7 Step 1 里把夹具契约写死：`monkeypatch.setattr(settings, "SMS_PROVIDER", "console")`（或直接注入记录码的 provider 替身），并把 `_send_and_get_cid` / `_last_code` 放进 `tests/web_ui/conftest.py`（或一个共享 helper 模块）由三个文件导入，别让每个 Task 各自发明一份。

## [43] [medium] plan.md:132（garbage 参数含 `"12345"`）与 plan.md:173-190（`_E164_RE` + `normalize_e164`）

**错在哪**：计划给的实现不会拒绝 `"12345"`：裸号补默认区号后得 `+8612345`，共 7 位数字，正好被 `^\+[1-9]\d{6,14}$` 放过。`test_normalize_rejects_garbage[12345]` 直接红，而实现者最省事的「修法」是把用例删掉——那条本该守的下限就没了。

**怎么证明**：把 plan.md:170-200 那段 `phone.py` 原样存成文件跑：`normalize_e164("12345")` 返回 `'+8612345'`（其余 7 个 garbage 参数都正确抛 ValueError）。我已按原文跑过，输出如此。

**改成**：在补默认区号那条分支上加一条位数下限（例如默认区号是 `86` 时要求补完为 `+86` + 11 位），并把这条判据写成独立用例；不要靠删测试参数收场。

## [44] [medium] plan.md Task 6 `issue()` 第 1 步冷却查询的 purpose 过滤（plan.md:1181）

**错在哪**：60 秒同号冷却的键是 `(phone_e164, purpose)`，而 `purpose` 是不鉴权端点 `send-code` 的请求体字段、完全由调用方控制（`VALID_PURPOSES = {login, bind, set_password}`，plan.md:1420）⇒ 同一个手机号在同一分钟内能收到 3 条短信，直接踩穿 requirements §2.10 记的运营商流控「同一签名对同号 1 条/分钟」，用户拿到的是我们解释不了的运营商侧失败——正是需求写「我们自己的限流必须比这更严」要避免的那件事。

**怎么证明**：读 plan.md:1177-1190：`last` 的 filter 里有 `purpose == purpose`；再读 :1193-1199 的小时/日计数（`_count(db, phone_e164=phone_e164)`）**没有** purpose 过滤 ⇒ 作者自己在同一个函数里对「同号」用了两种键。落地后可实测：对同一号连发 `purpose=login`、`purpose=bind`、`purpose=set_password` 三次，全部返 200。

**改成**：冷却查询去掉 `purpose == purpose`，只按 `phone_e164` 算（冷却保护的是那部手机，不是某个用途）。Task 6 补一条用例：`issue(login)` 后立刻 `issue(bind)` 必须抛 `RateLimited("sms_cooldown")`；配变异（把 purpose 过滤加回去 ⇒ 该用例变红）。

## [45] [medium] plan.md Task 6 `sms_challenge.py`：plan.md:1187 `last.created_at.replace(tzinfo=timezone.utc)`、plan.md:1255 `row.expires_at.replace(tzinfo=timezone.utc)`

**错在哪**：这两处用的是**无守卫**的 `.replace(tzinfo=utc)`，它只在读回来的值是 naive 时才正确。SQLite 上 `DateTime(timezone=True)` 读回 naive（所以全部单测恒绿），PostgreSQL + psycopg2 读回的是**带会话时区偏移的 aware** 值，`.replace()` 会把真实偏移直接抹掉 ⇒ 生产上一旦 PG 会话时区不是 UTC，`elapsed` 变成负数，**每个用户第一次取码就被判 `sms_cooldown`、`retry_after_sec≈28860`**，而 SQLite 测试一条都不红。仓里已有正确写法的两处先例，作者没有沿用。

**怎么证明**：实测已跑（本仓 `.venv`，SQLite 内存库，`DateTime(timezone=True)` + `server_default=func.now()`）：`created_at` 读回 `datetime.datetime(2026, 9, 7, 2, 58, 19)`，`expires_at` 读回 `datetime.datetime(2026, 9, 7, 3, 3, 19, 931816)`——**两个都是 naive**，所以 `.replace()` 在测试里永远是对的。仓里的守卫式先例：`katrain/web/core/ai_ladder_ranked.py:1236-1238`（`if created.tzinfo is None: created = created.replace(...)`）与 `katrain/web/api/v1/endpoints/ai_ladder.py:218-219`（同形）。生产侧一条命令可判：`docker exec <pg> psql -c "SHOW timezone"`。

**改成**：抽一个 `_as_utc(dt)`：`return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)`，plan.md:1187 与 :1255 两处都换成它（与 `ai_ladder_ranked.py:1236-1238` 同形）。测试里对这两条不写 SQLite 断言（证不了），改在 `_as_utc` 上直接喂 aware/naive 两种输入各断言一次。

## [46] [medium] plan.md Task 6 `issue()` 第 1 步（plan.md:1177-1190，判据在 :1186 `if last is not None and getattr(last, "delivered_ok", True):`）

**错在哪**：查询先取「该号该用途最新的一行」，再在 Python 里看它 `delivered_ok`——于是只要**最新那一行**是失败的，整条 60 秒冷却就被跳过，哪怕 5 秒前还有一条成功发出去的。判据落在了错的那一行上：想找的是「最近一次成功发送」，写出来的是「最近一次发送，如果它失败就当没有冷却」。

**怎么证明**：读 plan.md:1177-1190：`.order_by(created_at.desc()).first()` 之后才判 `delivered_ok`，`delivered_ok` 不在 filter 里。构造用例即可证：成功发一条 → 人工把一条更新的失败行插进去（或让供应商抛一次）→ 再 `issue()`，当前实现放行，正确实现应仍在冷却。计划现有的 `test_provider_failure_does_not_start_the_phone_cooldown`（plan.md:1119-1129）对这个缺陷免疫——它的场景里根本没有更早的成功行。

**改成**：把判据挪进 SQL：filter 里加 `models_db.SmsChallenge.delivered_ok.is_(True)`，去掉 `getattr(last, "delivered_ok", True)`。补一条用例：成功一次 → 失败一次 → 第三次必须仍抛 `sms_cooldown`。

## [47] [medium] plan.md Task 7 给 `/auth/register` 挂限流那段（plan.md:1481-1485，`if recent >= settings.REGISTER_DAILY_CAP:`）与它的测试（plan.md:1393 `monkeypatch.setattr(settings, "REGISTER_IP_DAILY", 2, ...)`）

**错在哪**：实现读 `settings.REGISTER_DAILY_CAP`、测试改的是 `settings.REGISTER_IP_DAILY`，而 Task 5 的 `Settings` 字段清单（plan.md:806-826）与 `__init__` env 装配（plan.md:828-841）**两个名字一个都没加**。`Settings` 是 `pydantic.BaseModel`（`katrain/web/core/config.py:38`），读不存在的属性抛 `AttributeError` ⇒ 照抄这段会让 **`/auth/register` 每一次调用都 500**，而那条测试因为 `raising=False` 只是造了个无人读的属性、永远不会绿。

**怎么证明**：`grep -n 'REGISTER_DAILY_CAP\|REGISTER_IP_DAILY' superpowers/tracks/phone-login/plan.md` → 只有 :1393 与 :1484 两处，Task 5 的配置清单里零命中。`sed -n '38p' katrain/web/core/config.py` → `class Settings(BaseModel)`（不是 `BaseSettings`，没有兜底）。另：这段还用了 `func` 与 `models_db`，而 `katrain/web/api/v1/endpoints/auth.py` 的 import 段（:1-19）两者都没有。

**改成**：按计划自己推荐的 (a) 落地：`users` 加 `signup_ip = Column(String(64), nullable=True)`（走同一套零手写 DDL 迁移），限流键用 `client_ip_for_ratelimit`；配置项统一叫一个名字（建议 `REGISTER_IP_DAILY: int = 10`），Task 5 的 `Settings` 与 `__init__` 两处都加，测试与实现用同一个名字；顺手在 auth.py 顶部补 `from sqlalchemy import func` 与 `from katrain.web.core import models_db`。

## [48] [medium] plan.md Task 10 的注释与断言（plan.md:1853、:1892-1899 `test_old_tokens_still_work_after_password_change`）、提交信息 :1929、收尾清单 :2697

**错在哪**：三处都写「改密码踢不掉已签发的旧 token，**最长 7 天**」，并要求 UI 照这个口径说给用户听。实际是 `REFRESH_TOKEN_EXPIRE_DAYS = 90`，`/auth/refresh` 只校验签名 + 用户名存在，不看密码有没有改过 ⇒ 持有 refresh token 的人在改密码后仍能**连续换发 7 天期的 access token 长达 90 天**。把 90 天说成 7 天，是在一条明确要求「状态必须诚实」的轨道上给用户一个错的安全承诺。

**怎么证明**：`sed -n '73,74p' katrain/web/core/config.py` → `ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*7` / `REFRESH_TOKEN_EXPIRE_DAYS: int = 90`；`katrain/web/core/auth.py:46` 用的正是后者；`katrain/web/api/v1/endpoints/auth.py:287-310` 的 `refresh` 端点里除了 `token_type == "refresh"` 与 `repo.get_user_by_username(username)` 之外没有任何与密码版本相关的检查。

**改成**：两条二选一。最小：把三处文案与 UI 口径改成「最长 90 天」，并把 `test_old_tokens_still_work_after_password_change` 扩成也断言 refresh 仍可换发（把真实现状钉住）。更对：`users` 加 `password_changed_at`（同一套迁移，一列），`refresh` 与 `get_user_from_token` 里比 `payload["iat"] < password_changed_at` 则 401 —— 这比 JWT 版本位便宜，且顺带把 `set-password` 变成真正的「踢掉旧会话」。

## [49] [medium] plan.md Task 6 模块 docstring（plan.md:1160-1164）与 Task 4 `SmsChallenge` 的 docstring（plan.md:591-598）

**错在哪**：两处都把「全部从表里数 SQL」论证成「天然跨重启**跨 worker**」。跨重启成立，跨 worker 不成立：`issue()` 是「先 `SELECT count(*)` 判额度、再 `INSERT`」，中间没有任何锁、条件 UPDATE 或唯一约束 ⇒ 多进程下 N 个并发请求会同时读到同一个 `submitted` 值并全部放行，`SMS_DAILY_CAP_*` 这个被需求称作「硬闸」的东西退化成建议值。今天恰好安全，只是因为 F5 记的「单进程」+ 检查与 commit 之间没有 `await`——正是 F5 自己标注的「会过期的前提」，而失效表现同样是「限流变松，没有任何报错」。

**怎么证明**：读 plan.md:1200-1232：`submitted = _count(...).scalar()` → `if submitted >= cap: raise` → `db.add(row); db.commit()`，三步之间无 `await`、无 `with_for_update()`、无唯一约束。对照仓里已有的正确写法：`katrain/web/core/quota.py:79-89` `try_consume` 用的是 `UPDATE ... WHERE used + :n <= allowance` + `rowcount == 1`——同一个仓、同一类问题、已经解对过一次。判据：把服务改成 `--workers 2` 或用两个进程并发打 `send-code`，日额度会被打穿。

**改成**：额度改成条件 UPDATE：建一行 `sms_daily_counters(day_key, is_intl, sent)`，用 `UPDATE sms_daily_counters SET sent = sent + 1 WHERE day_key=:d AND is_intl=:i AND sent < :cap` 判 `rowcount == 1`（与 `quota.try_consume` 同形），拿不到就 `sms_capacity`；或者退一步，把 docstring 里「跨 worker」三个字删掉并写明「本闸的原子性依赖单进程，改 workers 前必须先换成条件 UPDATE」——不要留一句会被下一个人当作已解决的论证。

## [50] [medium] plan.md Task 11 (Step 4 'Expected: PASS') and Task 16 Step 1 ('新增失败为空')

**错在哪**：The Task 11 change newly breaks three currently-passing tests that no task mentions: exact-dict comparison of the /quota shape, and the two endpoint tests that exercise the free-weekly branch with users that have no phone.

**怎么证明**：tests/web_ui/test_billing_api.py:158 `assert b["free_weekly"] == {"used": 0, "allowance": 1}` — adding blocked_reason breaks equality and the unbound short-circuit makes allowance 0. tests/web_ui/test_report_charging.py:260 test_first_report_of_the_week_is_free_second_is_charged asserts `_balance(user) == before`; tests/web_ui/test_report_charging.py:291 asserts `task.free_grant_period == quota.period_key('week')` — both users are created via SQLAlchemyUserRepository with phone_e164 NULL, so the free branch is skipped. Confirm none is pre-existing: grep -n 'billing_api\|report_charging' superpowers/tracks/phone-login/test-baseline.txt → only test_redeem_flow.

**改成**：Name all three in Task 11: bind a phone in the app_with_game / _make_user fixtures for those cases, and change test_billing_api.py:158 to a subset check plus an explicit `blocked_reason is None`. Otherwise Task 16's zero-new-failures gate is unpassable and the temptation is to add them to the baseline, which retires three real assertions.

## [51] [medium] /Users/fan/Repositories/katrain-phone-login/superpowers/tracks/phone-login/plan.md:173 (_E164_RE) vs plan.md:133 (test_normalize_rejects_garbage)

**错在哪**：The supplied implementation does not pass the supplied test, and the accepted range lets short garbage become a billable international SMS. '12345' → '+8612345', which matches ^\+[1-9]\d{6,14}$ (7 digits is inside 1+6..14).

**怎么证明**：I ran the plan's exact normalize_e164 over its own reject list: every case raises except '12345', which returns '+8612345'. Then is_domestic('+8612345') is False → it is routed to SendMessageToGlobe and charged against SMS_DAILY_CAP_INTL, the expensive counter.

**改成**：After prefixing the default region, enforce a per-region national length — at minimum, reject any +86 number that is not exactly 11 digits (reuse the same constant is_domestic uses) — and keep '12345' in test_normalize_rejects_garbage. Step 4's 'Expected: PASS（全部）' is currently a false claim; fix the implementation, not the test.

## [52] [medium] plan.md:1178-1186 (Task 6, issue() cooldown query)

**错在哪**：The cooldown picks the newest row that is provider_charged and only then checks delivered_ok. But every row is created with provider_charged=True (plan.md:1225), so that filter is a no-op, and applying the delivered_ok check after ordering means one failed send wipes out the cooldown left by a successful send seconds earlier. Neither test_cooldown_is_computed_from_the_table_not_memory nor test_provider_failure_does_not_start_the_phone_cooldown can distinguish this from the correct implementation.

**怎么证明**：Trace the two tests: the cooldown test issues twice with no failure in between (newest row is delivered) → red either way; the failure test has only one prior row and it is the failed one → green either way. Neither builds the discriminating state: success at t0, provider failure at t0+1, request at t0+2.

**改成**：Move the predicate into the query: `.filter(models_db.SmsChallenge.delivered_ok.is_(True))` and drop the provider_charged filter (it selects everything). Add the three-step case above and assert it still raises sms_cooldown.

## [53] [medium] plan.md:1393 (test) vs plan.md:1484 (impl); Settings additions at plan.md ~Task 5

**错在哪**：The register limiter's test and implementation read two different setting names and neither is declared. The test monkeypatches settings.REGISTER_IP_DAILY with raising=False (silently creating an unused attribute); the endpoint reads settings.REGISTER_DAILY_CAP, which does not exist → AttributeError → 500, not 429. The test is also named ..._by_ip while the snippet counts users globally by created_at.

**怎么证明**：grep -n 'REGISTER_IP_DAILY\|REGISTER_DAILY_CAP' superpowers/tracks/phone-login/plan.md → 1393 and 1484 only; grep -n 'REGISTER' katrain/web/core/config.py → no hits. Neither name appears in the Task 5 Settings/__init__ blocks.

**改成**：Pick one name, declare it in both the Settings class body and the __init__ env assembly inside Task 5 (the plan's own '两处都要写' rule), and rename the test to what it proves. If option (b) (global daily cap) is taken, the name must be test_register_is_capped_per_day — a test called by_ip that proves a global cap is exactly the '闸量错了对象' shape.

## [54] [medium] plan.md:1360 (Task 7, test_send_code_does_not_leak_whether_the_phone_has_an_account)

**错在哪**：set(a.json()) == set(b.json()) compares dict keys only. A response of {'challenge_id':…, 'cooldown_sec':60, 'registered': true|false} has identical key sets in both branches and still enumerates accounts. The test also varies the phone between the two calls, so it does not hold the only variable it claims to isolate.

**怎么证明**：In a REPL: set({'a':1,'b':True}) == set({'a':2,'b':False}) → True. Then mutate the endpoint to return an extra 'registered' boolean and re-run — the test stays green.

**改成**：Assert the full body: `assert a.json().keys() == {'challenge_id','cooldown_sec'}` and `assert a.json()['cooldown_sec'] == b.json()['cooldown_sec']` (challenge_id must of course differ). Record the mutation: add 'registered' to the response and confirm it goes red.

## [55] [medium] plan.md:2411-2420 (Task 14, the source-scanning i18n default test)

**错在哪**：The gate both under- and over-reports, and as written cannot run. The regex only matches single-quoted defaults, but double quotes is the only way to write an English default containing an apostrophe — and LoginModal.tsx:119 already does exactly that, so the worst offender is invisible. The [a-z_]+ key class drops keys with digits. The filter /^[A-Za-z ?'.!]+$/ drops any English default containing a digit or parenthesis ('Send code (60s)'). In the other direction it flags every pre-existing English default, which is why it needs LEGACY_ENGLISH_DEFAULTS — a variable the plan never defines (readFileSync and API are also never imported). None of that is caught by type checking.

**怎么证明**：grep -n "i18n.t('auth:switch_to_register" katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx → line 119, double-quoted default. cat katrain/web/ui/src/tsconfig.app.json → "exclude": ["src/**/*.test.tsx", "src/**/*.test.ts"], so `tsc -b` never sees the undefined identifier; it only fails at vitest runtime.

**改成**：Delete this test. The seven tests directly above it already assert on rendered text (screen.getByText('验证码登录'), /已提交发送/, /还需等待 42 秒/), which judges the control rather than the source string and is immune to quote style. If a source-level gate is genuinely wanted it belongs in eslint.config.js covering both quote styles, and it must ship with a mutation record showing (a) one added English default turns it red and (b) it reports zero violations on today's tree.

## [56] [medium] plan.md Task 6 Step 1 (tests at ~1000-1120) — the prose about _P at plan.md:1121

**错在哪**：Eight of Task 6's tests call sc.issue without installing a provider. settings.SMS_PROVIDER defaults to '' (plan.md Task 5 Settings block), and sms.get_provider() raises SmsProviderError("未知的 SMS_PROVIDER=''") for that value, so test_issue_stores_only_a_hash, ..._invalidates_the_old_one, ..._cooldown..., ..._two_different_ips..., test_verify_consumes_once_only, ..._wrong_code..., ..._purpose_mismatch and ..._expired... all die at the send step. The _P double and _last_code() are mentioned only in a prose sentence, never as a fixture.

**怎么证明**：Read plan.md's get_provider (Task 5 Step 3, final function): name not in ('console','aliyun') → raise SmsProviderError. Then note which Task 6 tests contain monkeypatch.setattr(sc.sms, 'get_provider', ...) — only two of ten.

**改成**：Specify in Task 6 an autouse fixture that installs _P (a recording double) and exposes _last_code(), plus _advance/_advance_expiry and the db fixture, with an explicit note that no test may reach a real provider.

## [57] [medium] plan.md:2645-2655（Task 16 Step 3 第 4、5 条）对照 plan.md:88-95（前端文件结构表）

**错在哪**：验收项指向三个没有任何 Task 建的界面：设置页的绑定入口、复盘页的免费额度文案、发言被拒的回执。后端把 blocked_reason / free_weekly_blocked / chat_requires_phone 都做了，但没有一个读者——D-U1-M「状态要诚实」那套论证在用户屏幕上完全落不了地，而 Task 13 加的 API.bindPhone / API.setPassword 是共享领土里的零调用者死代码。

**怎么证明**：前端文件结构表（plan.md:88-95）只有 api.ts / AuthContext.tsx / LoginModal.tsx / CountryCodeSelect.tsx，加上 Task 15 的 PhoneConsent.tsx，没有设置页也没有复盘页。三条实测：`grep -rn 'v1/billing' katrain/web/ui/src` → 零命中（`GET /quota` 前端从来没人调，所以 Task 11 的 `blocked_reason: "phone_required"` 没有读者）；`grep -rn '402\|detail\.code' katrain/web/ui/src/api/reportApi.ts katrain/web/ui/src/galaxy` → 无 402/detail 处理；`grep -rn 'chat_requires_identity' katrain/web/ui/src` → 零命中，而后端 `katrain/web/server.py:2825` 早就在发这个码——现成的同形错误今天就是静默的，Task 12 新加的 chat_requires_phone 会沿同一条静默通道走掉。

**改成**：二选一并写死：要么补一个 Task 14.5「绑定卡片（设置页）+ 复盘页额度文案读 blocked_reason + 对局聊天的 {type:'error',code} 回执」，要么把 Task 16 Step 3 的第 4、5 条删掉、连同 API.bindPhone/setPassword 一起挪进收尾清单说明「后端已就绪、本轮无 UI」。现在这样两头都不着，验收时只会被划勾划过去。

## [58] [medium] plan.md:1474（「在 register 函数体开头、strict_box_sso_enabled() 检查之后」）

**错在哪**：这个位置在 board 模式的转发分支**之前**，于是盒子上的注册也会先在本地库上数一遍再决定要不要 429，给盒子的注册路径凭空多一个故障面，违反 D-U3「盒子什么都不改」。

**怎么证明**：读 `katrain/web/api/v1/endpoints/auth.py:323-349`：顺序是 `strict_box_sso_enabled()` → 403（:324-325）→ `remote_client = getattr(...)`（:326）→ `if remote_client is not None:` 原样转发给云端（:328-345）→ `# Server mode: local registration`（:347）。「strict 检查之后」= 落在 :326 附近，在转发之前。

**改成**：把限流那几行放到 `# Server mode: local registration`（auth.py:347）之后；并补一条用例：board_client 注册照常转发、不被本地计数拦（可复用 tests/web_ui/test_board_auth.py 的现成夹具）。

## [59] [medium] plan.md:2350-2420（Task 14 测试文件）

**错在哪**：测试文件里有三个未定义标识符（`API`、`readFileSync`、`LEGACY_ENGLISH_DEFAULTS`），且第 5 条用例（未绑号 404）根本没有 render，只有一句 `// ...填号、填码、提交` 的占位——但 Step 4 写着「Expected: PASS（8 条）」。

**怎么证明**：读 plan.md:2350-2356 的 import 段：只 import 了 render/screen/fireEvent/waitFor、describe/it/expect/vi、LoginModal；而 plan.md:2364 起用 `vi.spyOn(API, 'sendPhoneCode')`，plan.md:2415 用 `readFileSync(...)`，plan.md:2419 用 `LEGACY_ENGLISH_DEFAULTS`。plan.md:2394-2399 那条用例通篇没有 `render(`。

**改成**：补 `import { API } from '../../../../api'` 与 `import { readFileSync } from 'node:fs'`，把 LEGACY_ENGLISH_DEFAULTS 显式定义在文件顶部；第 5 条要么写全（render + 填号 + 填码 + 点提交），要么从「PASS（8 条）」里去掉改成 7 条。

## [60] [medium] plan.md:2413-2420（Task 14 第 8 条「所有新增文案的默认值是中文」）

**错在哪**：这条闸只匹配单引号写法，而今天文件里唯一一条英文默认值恰好是双引号——它对现成的反例就是瞎的；实现者把新键写成 i18n.t('auth:get_code', "Get code") 就能绿。它还只读 LoginModal.tsx 一个文件，本 Task 新建的 CountryCodeSelect.tsx 和 Task 15 的 PhoneConsent.tsx 一个字都扫不到。

**怎么证明**：闸的正则是 `/i18n\.t\('auth:[a-z_]+',\s*'([^']*)'\)/g`（plan.md:2416），只吃 `'...'`。对照 `sed -n '119p' katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx` → `i18n.t('auth:switch_to_register', "Don't have an account? Register")`，双引号，该正则不命中。扫描范围见 plan.md:2415 的 `readFileSync('src/galaxy/components/auth/LoginModal.tsx')`。

**改成**：正则同时吃 '、"、模板串（`(['\"`])([\\s\\S]*?)\\1`），扫描对象从单个文件改成整个 `src/galaxy/components/auth/` 目录逐文件跑；再做一次变异：把某个新键的默认值改成双引号包的英文，确认它当场变红——不红说明这条闸还没写完。

## [61] [medium] Task 14 / Task 15 全程（plan.md:2337-2618）与收尾清单（plan.md:2687-2706）

**错在哪**：新增的十来个 auth:* 键从头到尾没有一步写进 katrain/i18n/，也没进收尾清单。i18n.t 的语义是「键不在字典里就回默认值」，所以英/日/韩/俄等 10 种语言的用户在登录框会看到整段中文——这跟需求 §0.3「所有国家的手机号都要支持」正好顶上。（顺带回答一个前置疑问：**测试环境返回的是默认值不是 key**，`translations` 初值 `{}` 且 `src/test/setup.ts` 不调 loadTranslations，所以 `screen.getByText('验证码登录')` 这类中文字面量在单测里是能命中的——计划这一处没错。）

**怎么证明**：`katrain/web/ui/src/i18n.ts:52` → `return this.translations[key] || defaultText || key`。现有的 auth 键是全语言登记的：`for l in en cn jp; do grep -c '^msgid "auth:' katrain/i18n/locales/$l/LC_MESSAGES/katrain.po; done` → 20/20/20，且 `grep -A1 'msgid "auth:switch_to_register"' katrain/i18n/locales/en/.../katrain.po` 的 msgstr 是英文。再 `grep -n 'katrain/i18n' superpowers/tracks/phone-login/plan.md` → 零命中。

**改成**：Task 14 和 Task 15 各加一步：走 katrain-i18n-expert 把新键补进 11 个 locale 的 .po 并 `uv run python i18n.py` 重生成 .mo；做不到就把「本轮手机登录界面只有中文，其余 10 种语言回落中文默认值」明确写进收尾清单交回 Fan。

## [62] [low] plan.md:407 与 plan.md:450（Task 3 正文与实现注释里的 `auth.py:77 SHADOW_USER_NO_LOCAL_AUTH`）

**错在哪**：该常量在 `katrain/web/api/v1/endpoints/auth.py:77`，不在 Task 3 的 Files 所指的 `katrain/web/core/auth.py`；巧的是 `core/auth.py:77` 恰好是 `@abstractmethod def unfollow_user`，照着行号翻会翻到一段完全无关的代码。

**怎么证明**：`grep -rn "SHADOW_USER_NO_LOCAL_AUTH" /Users/fan/Repositories/katrain-phone-login/katrain/` 与 `sed -n '77p' /Users/fan/Repositories/katrain-phone-login/katrain/web/core/auth.py`。

**改成**：两处改写全路径：`katrain/web/api/v1/endpoints/auth.py:77`。

## [63] [low] plan.md:1479-1481（Task 7 给 /auth/register 挂限流的片段）

**错在哪**：片段用了 `func.count(models_db.User.id)` 与 `models_db.User.created_at`，但 `katrain/web/api/v1/endpoints/auth.py` 的 import 段（:1-19）既没有 `func` 也没有 `models_db`（只 import 了 `Session`）。照抄是 NameError。

**怎么证明**：`sed -n '1,20p' /Users/fan/Repositories/katrain-phone-login/katrain/web/api/v1/endpoints/auth.py`。

**改成**：在片段前加一行说明：`endpoints/auth.py` 需补 `from sqlalchemy import func` 与 `from katrain.web.core import models_db`（或在函数体内 import，与该文件既有的 `from katrain.web.core.auth import get_password_hash`（:348）同形）。

## [64] [low] plan.md:806/821（`SMS_DAILY_CAP_INTL: int = 50`）与 plan.md:2692（收尾清单「按 100 落，实发前复核」）

**错在哪**：同一份计划里两个不同的值：Task 5 的配置与定标理由写死 50（并论证「必须比国内低一个量级」），收尾清单和 requirements §3 D-U4 说按 100 落。实现者不知道以哪个为准，而 Global Constraints 里又说「实现时以最终值为准」。

**怎么证明**：`grep -n "SMS_DAILY_CAP_INTL" /Users/fan/Repositories/katrain-phone-login/superpowers/tracks/phone-login/plan.md /Users/fan/Repositories/katrain-phone-login/superpowers/tracks/phone-login/requirements.md`。

**改成**：统一成一个数（Task 5 的 50 有写明的定标依据，建议留 50），把 plan.md:2692 与 requirements §3 D-U4 那张表里的 100 一并改掉，或在 2692 明写「已定为 50，requirements 的 100 作废」。

## [65] [low] plan.md:1285（Task 6 Step 5 变异表第三行「第 4 步里 provider_charged=True 改成 False」）

**错在哪**：第 4 步（plan.md:1202-1215）只做日额度查询，没有 `provider_charged=True` 这个字面量；它在第 5 步的行构造里（plan.md:1228）。按表去第 4 步找会找不到，变异步骤没法照做。

**怎么证明**：`awk 'NR>=1202 && NR<=1232' /Users/fan/Repositories/katrain-phone-login/superpowers/tracks/phone-login/plan.md`。

**改成**：表格那格改成「第 5 步建行时的 `provider_charged=True` 改成 `False`（plan 第 1228 行那句）」。

## [66] [low] plan.md:1827-1828 与 plan.md:1858（Task 10 两条用例）

**错在哪**：`test_sets_password_and_old_one_stops_working(auth_client_with_phone)` 体内用了 `client`、`test_old_tokens_still_work_after_password_change(auth_client_with_phone)` 体内也用了 `client`，但两条的参数表里都没有 `client` 夹具 ⇒ NameError。

**怎么证明**：照 plan.md:1823-1828、1851-1858 逐行读参数表与函数体。

**改成**：两条的签名各加一个 `client` 参数（`def test_...(client, auth_client_with_phone):`）。

## [67] [low] plan.md:1503（Task 7 的 git add）

**错在哪**：Task 7 要新增一个限流上限的 Settings 字段（无论叫 `REGISTER_IP_DAILY` 还是 `REGISTER_DAILY_CAP`），但提交只 add 了 `auth.py`、`models.py`、测试，**漏了 `katrain/web/core/config.py`**。留在工作区的改动等于不存在，而且下一个 Task 的 `git status --porcelain` 会一直显示它脏、掩盖 F12 那行真正该看的噪声。

**怎么证明**：对比 plan.md:1503 的 add 清单与 plan.md:1484 用到的 `settings.REGISTER_DAILY_CAP`（该字段不在 plan.md:794-812 的 Task 5 清单里，只能在 Task 7 加）。

**改成**：把 `katrain/web/core/config.py` 加进 Task 7 Step 5 的 add 列表；如果选了 signup_ip 方案，再加上 `katrain/web/core/models_db.py`。

## [68] [low] plan.md:2464、plan.md:2607（Task 14 / Task 15 的 git add）

**错在哪**：两处写的是 `git add katrain/web/ui/src/galaxy/components/auth/`——一个**目录**，不是显式文件清单。Global Constraint #11 的原话是「一律显式列文件」。这里 F12 那个 fixture 不在该目录下所以不会误伤，但同一个动作在别处就会。

**怎么证明**：读 plan.md:2464 与 2607，对比 plan.md:38-40 的 Global Constraint #11 与其余 12 个 Task 的写法（全部逐个列文件）。

**改成**：展开成 `git add katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx katrain/web/ui/src/galaxy/components/auth/CountryCodeSelect.tsx katrain/web/ui/src/galaxy/components/auth/PhoneConsent.tsx katrain/web/ui/src/galaxy/components/auth/__tests__/...`。

## [69] [low] plan.md:2571（PhoneConsent 文案）

**错在哪**：告知文案把收集者写成「智星盒」，而 requirements.md §2.10 已经查证过：【智星盒】不是企业全称的子集（能用的是【万智星】）。PIPL 十七条要求告知的是**个人信息处理者的名称**，写一个不是法定主体名的产品名，正是这个 Task 想解决的问题的反面。

**怎么证明**：读 plan.md:2571 与 requirements.md §2.10 第一句；两处对同一个名字的判断相反。

**改成**：把默认文案里的主体名改成与 `SMS_SIGN_NAME` 同源的企业名（或直接留 `{{company}}` 占位并在 Task 15 里点名「上线前由 Fan 定稿法定主体名」，与收尾第 9 条并列交回）。

## [70] [low] plan.md:1595（Task 8 Step 3 的注释 `# SqlAlchemyUserRepository`）

**错在哪**：类名拼错，真实类名是 `SQLAlchemyUserRepository`；全仓只有这一个 `UserRepository` 实现，实现者按注释去 grep 会找不到落点。

**怎么证明**：`grep -rn "class SQLAlchemyUserRepository" katrain/web/core/auth.py` → `:94`；`grep -rn "SqlAlchemyUserRepository" katrain tests` → 零命中。

**改成**：注释改成 `# SQLAlchemyUserRepository（katrain/web/core/auth.py:94）`。

## [71] [low] plan.md Task 6 `issue()` 的落行—发送顺序（plan.md:1225-1234 落行并 `db.commit()`，:1235 才 `await ...send(...)`）

**错在哪**：进程在 `db.commit()` 与供应商调用之间崩掉（或客户端断开导致协程被取消）时，库里留下一行 `provider_charged=True, delivered_ok=True`：它既占掉一格全站日额度，又给这个号起了 60 秒冷却——而用户既没收到短信，也没拿到 `challenge_id`（响应根本没发出去）。用户立刻重试，得到的是「还需等待 60 秒」这句和事实相反的话。

**怎么证明**：读 plan.md:1232-1240：`db.commit()` 在 `try` 之外、`await send` 之前；失败分支只有 `SmsProviderError` 一条，`asyncio.CancelledError` / 进程被 kill 都不经过它。可造：在 `await sms.get_provider().send(...)` 之前 `os._exit(1)`，重启后查该号最近一行 → `delivered_ok is True`，再 `issue()` 同号必被冷却拦。

**改成**：把落行时的 `delivered_ok` 默认改成 `False`（即「还没证明发出去」），发送成功后再置 `True` 并 commit；冷却查询本来就只该看 `delivered_ok.is_(True)`（见上一条），这样崩溃留下的行只吃日额度（保守，符合原意），不会误起冷却。模型上 `delivered_ok = Column(Boolean, nullable=False, default=False)`。

## [72] [low] plan.md Task 4 `SmsChallenge` 模型（plan.md:565-605）与收尾清单（plan.md:2688-2706）

**错在哪**：`sms_challenges` 明文长期保存 `phone_e164` 且**没有任何清理/保留期**：任何人对 `send-code` 打过的号（包括从来没有、也永远不会成为用户的号）都会永久留一行。计划的收尾清单列了 9 条「没做」，这一条不在里面 ⇒ 交回给 Fan 的风险面是不全的；而 Task 15 又同时承认「同意没有后端留痕」，两件事合起来是「留了不该留的、没留该留的」。日额度/限流的三个计数查询也会随这张只增不减的表逐日变慢。

**怎么证明**：读 plan.md:565-605：模型里没有任何 TTL/清理钩子；`grep -n '清理\|cleanup\|retention\|保留期' superpowers/tracks/phone-login/plan.md` 在 Task 4/6/收尾三处均零命中（需求 §1.2 的「不做 90 天清理任务」讲的是 `retired_phones`，不是 challenge 行）。

**改成**：要么加一个极轻的清理（`issue()` 里顺手 `DELETE FROM sms_challenges WHERE created_at < now() - 30 days`，一条语句，不引 cron），要么至少把「验证码表明文存号且无保留期」写进收尾清单第 11 条，和第 8 条（同意无留痕）一起交回给 Fan 定保留期。

## [73] [low] plan.md:473 (Task 3 Step 5, test_login_with_sentinel_hash_user_returns_401_not_500)

**错在哪**：/auth/login takes a JSON body, not a form, so posting data={...} yields 422 — the test is red whether or not verify_password is fixed. The tempting repair is to relax it to `!= 500`, which is the assertion that stops proving anything (a 422 also satisfies it).

**怎么证明**：sed -n '231,233p' /Users/fan/Repositories/katrain-phone-login/katrain/web/api/v1/endpoints/auth.py → `async def login(request: Request, login_data: LoginRequest, response: Response)`; LoginRequest is a pydantic BaseModel (auth.py:79-81).

**改成**：json={"username": "shadowy", "password": "x"} and keep the assertion at == 401.

## [74] [low] plan.md:1892 (Task 10 set_password impl)

**错在哪**：repo.get_by_username does not exist; the repository method is get_user_by_username. The endpoint would 500 rather than return 400 phone_unbound. The lookup is also redundant — current_user is already the pydantic User carrying phone_bound after Task 8.

**怎么证明**：grep -n 'def get_user_by_username\|def get_by_username' /Users/fan/Repositories/katrain-phone-login/katrain/web/core/auth.py → only get_user_by_username at :62 (ABC) and :209 (impl).

**改成**：Replace the two lines with `if not current_user.phone_bound: raise HTTPException(400, {'code': 'phone_unbound'})`.

## [75] [low] plan.md:1612 (Task 8, test_repo_to_dict_carries_phone_bound)

**错在哪**：The plan says this assertion exists to catch a test double that did not grow phone_bound, but it exercises the real SQLAlchemyUserRepository (bound_user_repo), so it is green in exactly the world it claims to guard. It is also guarding a risk that does not exist here.

**怎么证明**：grep -rn 'UserRepository' tests/ — every web_ui fixture constructs the real SQLAlchemyUserRepository (test_billing_api.py:35, test_report_charging.py:67, test_report_retry_authorization.py:45, …); there is no repository double in tests/web_ui/.

**改成**：Drop the claim about 替身, or move the assertion to the identity object that endpoints actually read: Task 9's `auth_client.get('/api/v1/auth/me').json()['phone_bound'] is True` after a successful bind already covers the real failure mode.

## [76] [low] plan.md Task 3/6/7/9/11/12 test signatures (fixtures client, auth_client, auth_client_no_phone, auth_client_with_phone, board_client, strict_box_client, strict_box_auth_client, board_auth_client, remote_spy, db, billing_enforced, zero_balance, bound_user, existing_phone_user, phone_taken_by_someone_else, ws_bound, ws_unbound, ws_observer, bound_user_repo, other_users_challenge, failing_provider)

**错在哪**：About twenty fixtures are invented with no home. tests/web_ui/conftest.py contains only kivy mocks — there is no shared client/auth_client/db. Every existing web_ui test builds its app fixture inline. The plan says once (Task 3 Step 5) to copy test_billing_api.py's shape, then never revisits it, and it never states the two traps that shape carries.

**怎么证明**：cat tests/web_ui/conftest.py (kivy mocks only). Then read tests/web_ui/test_billing_api.py:20-50 (isolated sqlite, SQLAlchemyUserRepository, dependency_overrides[get_db], driven by httpx.AsyncClient(ASGITransport(app)) — which does NOT run lifespan) and tests/conftest.py's long docstring on _lifespan_server unconditionally overwriting app.state.user_repo.

**改成**：Add a Task 0 that writes tests/web_ui/conftest_phone.py (or a per-file fixture block) with those fixtures spelled out, and state two things explicitly: (1) Task 12's websocket tests need TestClient, which DOES run lifespan, so app.state.session_factory must be set before entering the client or the repo injection is overwritten and the real-DB write guard fires; (2) Task 11's db fixture must be the same session factory the app uses, otherwise `db.query(QuotaBucket).count() == 0` is trivially true and test_quota_does_not_create_a_bucket_for_an_unbound_user — the assertion the whole Task exists for — is green no matter what billing.py does.

## [77] [low] plan.md:1476-1485（Task 7 挂限流那段代码）

**错在哪**：这段代码用了 `func.count(...)` 和 `models_db.User`，但 endpoints/auth.py 两个都没 import；另外它跨模块调用了 `sms_challenge._today_start()` 这个带下划线的私有函数。

**怎么证明**：`sed -n '1,20p' katrain/web/api/v1/endpoints/auth.py` —— import 段只有 logging / typing / httpx / fastapi / jose / pydantic / core.auth 三个符号 / core.box_sso / config / db.get_db / models.User,UserInDB / sqlalchemy.orm.Session，没有 sqlalchemy.func，也没有 models_db。

**改成**：在 Task 7 的 Step 3 里显式列出要加的两行 import；把 `_today_start` 在 sms_challenge.py 里改成公开名 `today_start()`（Task 6 内部同步改），或在 Task 7 自己算一遍 day0，别跨模块拿私有函数。

