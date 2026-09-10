# P3 · 手机绑定与验证码登录 —— 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 给 galaxy 加手机号绑定与验证码登录，并把每周免费复盘额度与发言权闸在"已绑手机"上。

**Architecture:** 一张 `sms_challenges` 表承载验证码、冷却、限流三件事（全部 SQL 查询，不用进程内存）；
供应商抽象 `console|aliyun` 两个实现，生产未显式配置就 fail-fast；免费额度的闸**在触碰 quota 之前短路**，
不建 allowance=0 的桶；手机号是"拿免费额度 + 发言"的门票，**不是"有账号"的门票**——注册契约一个字节不变。

**Tech Stack:** FastAPI / SQLAlchemy 2.0 / SQLite(dev)+PostgreSQL(prod) / React+TS+MUI / vitest + pytest

**Spec:** `superpowers/tracks/phone-login/requirements.md`（§3 是已裁定的最终决策）
配套实测：`superpowers/tracks/phone-login/preflight-findings.md`（F1–F13）

---

## Global Constraints

每一条都来自 spec §2 / §3，实现时逐条适用，不重复抄进各 Task：

1. **不新增任何 Python 依赖**（F8：生产依赖清单是 release 分支独有的 hash-pinned
   `requirements-web-runtime.txt`；只往 `requirements-web.txt` 加包 ⇒ **只在生产运行时 ImportError**）。
   E.164 手写；阿里云用标准库 `hmac`/`hashlib`/`urllib.parse` + 已有 `httpx` 自签。
2. **不开真短信通道**。`console` 提供方做完测透；`aliyun` 按文档实现但**不作为验收项**——
   拿不到凭据就验不了，验不了不许声称它能用。
3. **状态必须诚实**：`console` 在生产不许静默生效；任何超限都不许返 200；
   成功文案写「验证码已提交发送」而**不是**「已发送到您的手机」。
4. **`verify` 只收 `challenge_id` 不收手机号**，失败计数挂在 challenge 行上。
5. **per-IP 限流不得用 `request.client.host`**（F10：生产上它对所有用户恒为 `172.20.0.1`）。
6. **四个新端点每一个都要显式回答盒子问题**（F6），一个都不能漏。
7. **迁移零手写 DDL**：列上不写 `unique=True`，唯一性走 `__table_args__` 里的 `Index(..., unique=True)`（F1/F2）。
8. **i18n 默认值写中文**：`t('key', '中文默认')`。现有 `LoginModal.tsx` 写英文默认值，是反例，别照抄。
9. 供应商调用 `async` + `httpx.AsyncClient(timeout=3.0)`。单进程下同步阻塞拖垮整站。
10. 阿里云已知事实：签名用【万智星】**不能**用【智星盒】；国际/港澳台不需要资质签名模板；
    官方流控 同号 1条/分钟、5条/小时、10条/天，全平台同号 40条/天——**我们必须比这更严**。
11. **本轨道任何提交不许 `git add -A`**，一律显式列文件（F12：跑 pytest 会改掉
    `katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json`，提交前先 `git checkout --` 还原）。
12. 共享领土（`src/api.ts`、`src/components/`）改动后 **`npm run build` 与 `npm run build:kiosk-2d` 都要绿**。

---

## ⚠️ 相对 spec §1.1 的一处收窄（Fan 需知情）

spec §1.1 写「手机号登录（**含首次即注册**）」。那句话是在"注册强制手机"的前提下写的，
而 **D-U2 推翻了那个前提**（注册契约不变、手机可后绑）。两者不能同时成立：
注册仍需用户名 ⇒ 手机号登录无法在没有用户名的情况下建号。

**本轮落法：`POST /auth/phone/login` 只登录、不注册。** 号没绑过任何账号 ⇒
`404 {"code": "phone_not_bound"}`，文案指向"先用用户名密码登录，在设置里绑定手机号"。

**为什么不顺手做手机注册**：它要多一个"起用户名"步骤、一种无密码账号状态（`hashed_password`
是 `nullable=False`，得塞哨兵值）、以及"要用盒子得先设个密码"的引导。而 D-U2 的核心论证是
**经济闸已经由额度闸关严，注册路径不需要再收窄** ⇒ 多这条路收益低、面大。
将来要加，本轮的表、端点、UI 全部原样复用，不返工。

**代价说清楚**：本轮的手机验证码登录对**新用户**没有直接价值（他们得先注册再绑），
对**存量用户与已绑号用户**有三重价值（忘密码能进、一键登录、拿免费额度与发言权）。

---

## 文件结构

每个 Task 的 `**Files:**` 段是**唯一真源**（这里不再重复一份表——重复的表会过期，
而本计划的第一版正是因为一张过期的表把实现者指向了不存在的调用点）。

跨 Task 的名字与类型以 `superpowers/tracks/phone-login/interface-contract.md` 为准，
那份里每一行都是打开源码核实过的。

> **本计划已经过一轮对抗审查**（六个独立 agent 并行审 + 逐条证伪，77 条发现见
> `review-findings.md`；27 条 high 已全部落实）。凡与审查结论冲突的写法都已改掉。
> 计划里那些"看起来多余"的断言，多半是审查抓出来的假绿点，**别顺手删**。

### Task 1: E.164 归一化

**Files:**
- Create: `katrain/web/core/phone.py`
- Test: `tests/web_ui/test_phone_e164.py`

**Interfaces:**
- Consumes: 无（本 Task 不依赖任何前置 Task，纯函数、不碰库不碰网）
- Produces:
  - `normalize_e164(raw: str, default_region_cc: str = "86") -> str` —— 失败抛 `ValueError`，**不返回 None**
  - `is_domestic(e164: str) -> bool`
  - `mask_e164(e164: str) -> str`
  - 模块常量 `CN_CC = "86"`、`CN_NATIONAL_LEN = 11` —— `normalize_e164` 的国内长度闸与
    `is_domestic` 的通道判别**共用这两个常量**，不许各写一个字面量
  - 消费者：Task 7 `/auth/phone/send-code`、Task 8 `/auth/phone/login`、Task 9 `/auth/phone/bind`
    在**进任何限流/落库之前**先 `normalize_e164(body.phone)`；Task 5 `sms.py` 用 `is_domestic`
    决定走 `SendSms` 还是 `SendMessageToGlobe`

**这个 Task 的防线是什么**（审查发现 [7] / [43] / [51]）：旧版实现里裸号补 `+86` 之后
只剩「总位数 7-15」这一个下限，`normalize_e164("12345")` 返回 `"+8612345"`（`8` + 6 位，
正好被 `^\+[1-9]\d{6,14}$` 放过）⇒ 计划自己的 `test_normalize_rejects_garbage[12345]` 必红，
而最省事的「修法」是删掉那条参数。删掉之后的代价是真的：`is_domestic("+8612345")` 为 False
⇒ 它被路由到 `SendMessageToGlobe`、计进 `SMS_DAILY_CAP_INTL` 那个**贵的**计数器。

**修法的两条边同时要守**：
1. 下限必须挂在 `+86` 上（中国大陆手机号恰好 11 位、首位为 1），**不能**去抬全局下限——
   E.164 的全球下限就是 7 位数字，纽埃（`+683` + 4 位订户号）是合法的短国家码国际号，
   抬全局下限等于把它们连坐误杀。
2. 判据落在**归一后的号码**上（`s.startswith("+86")`），不落在 `default_region_cc` 上：
   这样 `normalize_e164("+8612345")` 这种显式带区号的短号也一样被挡。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_e164.py
"""Task 1: E.164 归一化 —— 接受什么、拒绝什么、以什么形式给用户看。"""

import pytest

from katrain.web.core.phone import is_domestic, mask_e164, normalize_e164


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("13800138000", "+8613800138000"),        # 裸国内号，按默认区号补
        ("+86 138 0013 8000", "+8613800138000"),  # 空格
        ("+86-138-0013-8000", "+8613800138000"),  # 连字符
        ("008613800138000", "+8613800138000"),    # 00 国际前缀
        ("+85298765432", "+85298765432"),         # 香港
        ("+14155552671", "+14155552671"),         # 美国
    ],
)
def test_normalize_accepts_and_canonicalizes(raw, expected):
    assert normalize_e164(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "abc",
        "+",
        "+86",
        "12345",                  # 裸短号：补完区号是 +8612345，**必须**被国内长度闸挡下
        "+8613800138000123456",   # 超长
        "+0123456789",            # 国家码首位为 0
        "+861380013800",          # +86 但只有 10 位本体
        "+8623800138000",         # +86、11 位，但首位不是 1（座机/短号，发不了短信）
    ],
)
def test_normalize_rejects_garbage(raw):
    """`None` 不在这张表里：passlib 之外这里也有同款陷阱 —— 今天
    `normalize_e164(None)` 已经在第一行 `if not raw` 上抛了，把它写进来是一条
    **拆掉实现也不会红**的假绿断言。表里每一条都是真的靠新增判据才红的。"""
    with pytest.raises(ValueError):
        normalize_e164(raw)


def test_short_country_code_international_is_not_collateral_damage():
    """挡住 `"12345"` 的那条下限**只能挂在 +86 上**。

    最省事的「修法」是把 `_E164_RE` 的 `\\d{6,14}` 抬成 `\\d{10,14}` —— 那样
    `"12345"` 确实红转绿，代价是所有短国家码国际号一起被误杀。纽埃 `+683` 的
    订户号是 4 位，`+6831234` 是合法 E.164。这条用例就是那个抬法的红灯。"""
    assert normalize_e164("+6831234") == "+6831234"
    assert is_domestic("+6831234") is False


def test_normalize_is_idempotent():
    once = normalize_e164("13800138000")
    assert normalize_e164(once) == once


def test_is_domestic_only_for_mainland_11_digit():
    assert is_domestic("+8613800138000") is True
    assert is_domestic("+85298765432") is False     # 香港走国际通道
    assert is_domestic("+14155552671") is False
    # `normalize_e164` 现在已经不会产出这种号了；这条是**纵深**：库里的行可能是
    # 手工插的、也可能是将来放宽了归一规则的。位数不对的 +86 一律不许当国内号
    # 去发国内模板 —— 那种失败的报错是运营商的、我们解释不了。
    assert is_domestic("+861380013800") is False


def test_mask_keeps_country_code_and_last_four():
    assert mask_e164("+8613800138000") == "+86 138****8000"
    assert mask_e164("+14155552671") == "+1 415****2671"
    assert mask_e164("+85298765432") == "+852 987****5432"
    # 中段真的没了 —— 只断言等号的话，一个「原样返回」的实现也能凑出格式来。
    assert "0013" not in mask_e164("+8613800138000")


def test_mask_falls_back_to_full_mask_for_unknown_country_code():
    """认不出国家码就不猜切分。猜错了会把国家码的位数当成号码的位数漏出去。"""
    assert mask_e164("+6831234") == "+***1234"


def test_mask_rejects_non_e164():
    with pytest.raises(ValueError):
        mask_e164("8613800138000")   # 没有前导 +
    with pytest.raises(ValueError):
        mask_e164("+86-138")         # 本体不是纯数字
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_e164.py -q`
Expected: FAIL — 收集期就炸：`ModuleNotFoundError: No module named 'katrain.web.core.phone'`
（`1 error`，一条用例都跑不到）

- [ ] **Step 3: 写最小实现**

```python
# katrain/web/core/phone.py
"""E.164 手机号归一化。**手写，不引第三方号段库**（见计划 Global Constraints #1）。

我们只需要三件事：把用户输入存成 E.164 规范形式、判断"该走国内还是国际短信通道"、
给用户看一个掩码形式。不判断号段是否真实存在 —— 那是运营商的事，发出去就知道了。
"""
import re

# E.164：`+` 后 7-15 位数字，首位不为 0。这是**全球下限**，不是中国大陆的下限。
# 不许拿它去挡短号：真实存在 7 位的国际号（纽埃 +683 的订户号是 4 位），
# 把这里抬到 11 位等于把所有短国家码国际号一起误杀。
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_SEPARATORS = re.compile(r"[\s\-().]")

# 中国大陆：手机号恰好 11 位、首位为 1。座机与短号一律不收 —— 我们只发短信。
# `normalize_e164` 的长度闸与 `is_domestic` 的通道判别共用这两个常量。
CN_CC = "86"
CN_NATIONAL_LEN = 11
_CN_MOBILE_RE = re.compile(r"^1\d{%d}$" % (CN_NATIONAL_LEN - 1))

DEFAULT_REGION_CC = CN_CC

# 只用于**显示**的国家码切分表。认不出来就整体打码，不猜。
_DISPLAY_CC = frozenset({"852", "853", "886", "86", "81", "82", "91", "44", "1"})


def normalize_e164(raw: str, default_region_cc: str = DEFAULT_REGION_CC) -> str:
    """把用户输入归一成 `+<国家码><号码>`。无法归一时抛 ValueError（**不返回 None**：
    静默的 None 会一路流到库里变成"未绑定"，而用户以为自己绑上了）。"""
    if not raw or not raw.strip():
        raise ValueError("手机号为空")
    s = _SEPARATORS.sub("", raw.strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    elif not s.startswith("+"):
        # 裸号：按默认区号补。国内号习惯写成 11 位裸号，也可能带一个国内长途前缀 0。
        s = "+" + default_region_cc + s.lstrip("0")
    if not _E164_RE.match(s):
        raise ValueError(f"不是合法的 E.164 手机号: {raw!r}")
    # 中国大陆的下限。**挂在归一后的号码上，不挂在 default_region_cc 上** ——
    # 这样显式写成 "+8612345" 的短号也一样被挡。没有这一条，"12345" 会变成
    # "+8612345"（7 位数字）被上面的全球下限放过，然后因为 is_domestic 为 False
    # 被路由到国际通道、计进那个贵的日额度计数器。
    if s.startswith("+" + CN_CC):
        national = s[1 + len(CN_CC) :]
        if not _CN_MOBILE_RE.match(national):
            raise ValueError(f"不是合法的中国大陆手机号（应为 1 开头的 {CN_NATIONAL_LEN} 位）: {raw!r}")
    return s


def is_domestic(e164: str) -> bool:
    """是否走国内通道（阿里云 SendSms）。**只有中国大陆 11 位号**。

    港澳台走国际通道（SendMessageToGlobe）—— 那条不需要签名与模板报备。
    位数不对的 +86 号一律按国际处理：`normalize_e164` 今天已经不产出这种号了，
    这里是纵深（手工插的行、将来放宽的归一规则）。
    """
    return e164.startswith("+" + CN_CC) and len(e164) == 1 + len(CN_CC) + CN_NATIONAL_LEN


def mask_e164(e164: str) -> str:
    """给用户看的掩码形式。原始号只从专用鉴权端点以这个形式出去。"""
    if not e164.startswith("+") or not e164[1:].isdigit():
        raise ValueError("mask_e164 只接受 E.164")
    body = e164[1:]
    for cc_len in (3, 2, 1):   # 长的先试，否则 "+86…" 会被 "+8…" 抢走
        cc, rest = body[:cc_len], body[cc_len:]
        if cc in _DISPLAY_CC and len(rest) >= 7:
            return f"+{cc} {rest[:3]}****{rest[-4:]}"
    # 认不出国家码：不猜切分（猜错会把国家码的位数当号码位数漏出去），整体只留末 4 位。
    return "+" + "*" * max(0, len(body) - 4) + body[-4:]
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_e164.py -q`
Expected: PASS（22 条：接受 6 + 拒绝 10 + 短国家码 1 + 幂等 1 + is_domestic 1 + 掩码 3）

- [ ] **Step 5: 变异验证**

两条边各变一次，**一次只变一处，验完立刻改回**：

| 变异 | 应该变红的用例 |
|---|---|
| 删掉 `normalize_e164` 里 `if s.startswith("+" + CN_CC):` 那整段 | `test_normalize_rejects_garbage[12345]`、`[+861380013800]`、`[+8623800138000]` 共 3 条 |
| 把 `_E164_RE` 的 `\d{6,14}` 改成 `\d{10,14}`（"抬全局下限"那种省事修法） | `test_short_country_code_international_is_not_collateral_damage` 1 条 |

Run（每次变异后各跑一遍）：`./.venv/bin/python -m pytest tests/web_ui/test_phone_e164.py -q`
Expected: 第一次变异 FAIL（3 failed / 19 passed）；第二次变异 FAIL（1 failed / 21 passed）；
两次都改回后 PASS（22 条）。

- [ ] **Step 6: 提交**

```bash
git status --porcelain   # 先确认 engine_game_state.json 没被跑测试改脏（Global Constraints #11）
git add katrain/web/core/phone.py tests/web_ui/test_phone_e164.py
git commit -m "feat(phone): E.164 归一化与国内/国际通道判别

手写不引号段库(生产依赖清单是 release 分支独有的 hash-pinned 文件,
只往 requirements-web.txt 加包会只在生产运行时 ImportError)。

归一失败抛 ValueError 不返回 None —— 静默的 None 会流到库里变成'未绑定',
而用户以为自己绑上了。

国内长度闸(+86 必须是 1 开头的 11 位)挂在归一后的号码上,不挂在
default_region_cc 上。没有它,'12345' 补成 '+8612345' 会被 E.164 的全球
下限(7 位)放过,再因为 is_domestic 为 False 被路由到国际通道、计进那个
贵的日额度。这条下限**不能**改成抬全局下限:+683 的订户号只有 4 位,
那样会把所有短国家码国际号一起误杀 —— 有一条用例专门守着这个。"
```

---

---

### Task 2: 可信客户端 IP（F10 的落地）

**Files:**
- Create: `katrain/web/core/client_ip.py`
- Modify: `katrain/web/core/config.py`（`Settings` 加 `TRUSTED_PROXY_HOPS` 字段 + `__init__` 里加 env 装配，**两处都要**）
- Test: `tests/web_ui/test_client_ip.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `client_ip_for_ratelimit(request: Request) -> str`（`katrain/web/core/client_ip.py`）。
    **Task 7 的端点必须把 FastAPI 注入的那个 `Request` 原样传进来**，一行不打折：
    ```python
    client_ip = client_ip_for_ratelimit(request)          # 不是 request.client.host
    challenge_id = await sc.issue(db, phone_e164=phone, purpose=purpose, client_ip=client_ip)
    ```
  - `settings.TRUSTED_PROXY_HOPS: int`（默认 `1`；env `KATRAIN_TRUSTED_PROXY_HOPS`；`0` = 完全不信任 XFF）
- **给 Task 7 的显式移交**（审查发现 [18]）：本 Task 只证明这个函数本身对。
  「端点实际把哪个 IP 交给限流器」**一条断言都不在本 Task**——把端点写成
  `ip = request.client.host`，Task 2 / Task 6 / Task 7 现有用例**全部照绿**，
  而那正是 F10 记的那个生产缺陷。那条端点级断言（`X-Forwarded-For` 换一个值必须换一个桶）
  归 Task 7 写，spec §2.4 要求它必须存在。

**为什么必须有这个 Task**（F10 实测）：生产 web 容器在 bridge 网络 `katrain-ucloud_app` 上，
对端恒为网关 `172.20.0.1`，而 `FORWARDED_ALLOW_IPS` 为空 ⇒ **uvicorn 不信任 XFF ⇒
`request.client.host` 对每一个用户都是同一个值**。照直用它做 per-IP 限流，
全站第 N 个正常用户就被挡，而表现是"限流生效了"不是报错。

不写死 `FORWARDED_ALLOW_IPS`：生产网关 172.20.0.1 / 测试 172.19.0.1 本来就不同值，
且 Docker 重建网络后会变，变了是**静默**退回"全站一个桶"。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_client_ip.py
"""Task 2: 限流分桶用的客户端 IP（preflight F10）。

用**真的** `starlette.requests.Request`，不用 `Mock`：
  - `request.client` 是真的 `Address`，"没有对端"那一支是真的 `None` ——
    `Mock` 上随便读一个属性都会自动长出一个真值对象，那条分支在 Mock 里
    很容易写成永远走不到；
  - `request.headers` 是真的 `Headers`（ASGI 规范保证 raw header 名是小写的，
    实现里就该用小写去查）。
"""

import pytest
from starlette.requests import Request

from katrain.web.core.client_ip import client_ip_for_ratelimit


def _req(xff=None, peer="172.20.0.1"):
    headers = [] if xff is None else [(b"x-forwarded-for", xff.encode())]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (peer, 12345) if peer else None,
    }
    return Request(scope)


def _set_hops(monkeypatch, n):
    """**故意不带 `raising=False`**：字段没加进 `Settings` 时这里当场红。
    带上 `raising=False` 的话，Task 的 config 那一半可以整个没做而测试全绿。"""
    from katrain.web.core import client_ip as m

    monkeypatch.setattr(m.settings, "TRUSTED_PROXY_HOPS", n)


def test_takes_nth_from_right_with_one_hop(monkeypatch):
    _set_hops(monkeypatch, 1)
    # 客户端伪造了两跳，nginx 用 $proxy_add_x_forwarded_for 追加了真实对端 —— 取右起第 1 跳
    assert client_ip_for_ratelimit(_req("1.2.3.4, 5.6.7.8, 203.0.113.9")) == "203.0.113.9"


def test_two_different_clients_get_different_buckets(monkeypatch):
    """**这条是这个 Task 存在的理由。**
    只断言"限流会拦"的用例对 F10 那个缺陷免疫 —— 在"全站一个桶"的世界里它也是绿的。"""
    _set_hops(monkeypatch, 1)
    a = client_ip_for_ratelimit(_req("203.0.113.9"))
    b = client_ip_for_ratelimit(_req("198.51.100.7"))
    assert a != b


def test_falls_back_to_peer_when_no_xff(monkeypatch):
    _set_hops(monkeypatch, 1)
    assert client_ip_for_ratelimit(_req(None, peer="10.0.0.5")) == "10.0.0.5"


def test_hops_larger_than_chain_falls_back_to_leftmost(monkeypatch):
    """链比配置短 —— 不许 IndexError，也不许静默返回对端（那等于全站一个桶）。"""
    _set_hops(monkeypatch, 5)
    assert client_ip_for_ratelimit(_req("203.0.113.9, 198.51.100.7")) == "203.0.113.9"


def test_zero_hops_means_do_not_trust_the_header(monkeypatch):
    _set_hops(monkeypatch, 0)
    assert client_ip_for_ratelimit(_req("203.0.113.9", peer="172.20.0.1")) == "172.20.0.1"


def test_never_returns_empty(monkeypatch):
    _set_hops(monkeypatch, 1)
    assert client_ip_for_ratelimit(_req(", ,")) == "172.20.0.1"          # 全是空段
    assert client_ip_for_ratelimit(_req("203.0.113.9", peer=None)) == "203.0.113.9"
    assert client_ip_for_ratelimit(_req(None, peer=None)) == "unknown"   # 既没头也没对端


def test_settings_default_is_one_hop(monkeypatch):
    """字段真的在 `Settings` 上，默认 1 跳（我们的部署就是 nginx 一层）。"""
    monkeypatch.delenv("KATRAIN_TRUSTED_PROXY_HOPS", raising=False)
    from katrain.web.core.config import Settings

    assert Settings().TRUSTED_PROXY_HOPS == 1


def test_env_var_overrides_hops(monkeypatch):
    """env 装配那一行真的写了。只加字段不加装配的话这条红 ——
    而那种漏法在生产上的表现是"配了没生效"，一声不吭。"""
    monkeypatch.setenv("KATRAIN_TRUSTED_PROXY_HOPS", "0")
    from katrain.web.core.config import Settings

    assert Settings().TRUSTED_PROXY_HOPS == 0
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_client_ip.py -q`
Expected: FAIL — 收集期就炸：`ModuleNotFoundError: No module named 'katrain.web.core.client_ip'`
（`1 error`，一条用例都跑不到）

- [ ] **Step 3: 写最小实现**

```python
# katrain/web/core/client_ip.py
"""限流用的客户端 IP。**不要用 `request.client.host`。**

实测（preflight F10）：生产 web 容器在 bridge 网络上，对端恒为网关 172.20.0.1，
而 uvicorn 的 `forwarded_allow_ips` 默认只信 127.0.0.1 且部署未放开
⇒ `request.client.host` 对**每一个用户**都是同一个值。拿它分桶，
全站第 N 个正常用户就被限流挡住，而表现是"限流生效了"，不是报错。

为什么不去放开 `FORWARDED_ALLOW_IPS`：那个值生产是 172.20.0.1、测试是 172.19.0.1，
本来就不是一个数，且 Docker 重建网络后会变 —— 变了之后是**静默**退回全站一个桶。
所以在应用里自己解析，信任跳数写成配置。
"""
from fastapi import Request

from katrain.web.core.config import settings

UNKNOWN = "unknown"


def client_ip_for_ratelimit(request: Request) -> str:
    # 直接读字段，**不用 `getattr(settings, ..., 默认值)` 兜底**：字段没加上时
    # 兜底会把"配置没做"这个错误掩盖成"永远 1 跳"，而它是静默的。
    hops = settings.TRUSTED_PROXY_HOPS
    client = request.client
    peer = (client.host if client is not None else "") or UNKNOWN
    if hops <= 0:
        return peer
    raw = request.headers.get("x-forwarded-for") or ""
    chain = [p.strip() for p in raw.split(",") if p.strip()]
    if not chain:
        return peer
    # 取右起第 hops 跳。右端是最靠近我们的一跳（nginx 用 $proxy_add_x_forwarded_for
    # 追加真实对端），左端是客户端可以随便写的。链比配置短就退到最左 ——
    # 退到对端等于全站一个桶，那正是本模块要避免的。
    idx = max(0, len(chain) - hops)
    return chain[idx]
```

`config.py` 两处都要改：

```python
    # katrain/web/core/config.py :: Settings —— 放在 REFRESH_TOKEN_EXPIRE_DAYS 之后（今天在 :74）
    # 限流分桶取 X-Forwarded-For 右起第几跳。见 core/client_ip.py（preflight F10）。
    # 我们的部署是 nginx 一层 ⇒ 1。0 = 完全不信任该头，退回 request.client.host
    # （只有在**没有**反向代理时才对）。
    TRUSTED_PROXY_HOPS: int = 1
```

```python
        # katrain/web/core/config.py :: Settings.__init__ —— 紧跟 REFRESH_TOKEN_EXPIRE_DAYS
        # 那一行之后（今天在 :191）
        data.setdefault("TRUSTED_PROXY_HOPS", int(os.getenv("KATRAIN_TRUSTED_PROXY_HOPS", 1)))
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_client_ip.py -q`
Expected: PASS（8 条）

- [ ] **Step 5: 变异验证**

| 变异 | 应该变红的用例 |
|---|---|
| `client_ip_for_ratelimit` 最后一行 `return chain[idx]` 改成 `return peer`（= 直接用 `request.client.host` 的那个世界） | 4 条：`test_takes_nth_from_right_with_one_hop`、`test_two_different_clients_get_different_buckets`、`test_hops_larger_than_chain_falls_back_to_leftmost`、`test_never_returns_empty`（它第二段断言"有 XFF、没有对端"也要走链） |
| 删掉 `config.py :: __init__` 里那行 `data.setdefault("TRUSTED_PROXY_HOPS", ...)`（只加字段、忘了装配） | `test_env_var_overrides_hops` 1 条 |

Run（每次变异后各跑一遍）：`./.venv/bin/python -m pytest tests/web_ui/test_client_ip.py -q`
Expected: 第一次变异 FAIL（4 failed / 4 passed）；第二次变异 FAIL（1 failed / 7 passed）；
两次都改回后 PASS（8 条）。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/core/client_ip.py tests/web_ui/test_client_ip.py katrain/web/core/config.py
git commit -m "feat(auth): 限流用的可信客户端 IP,不用 request.client.host

F10 实测:生产 web 在 bridge 网络上对端恒为网关 172.20.0.1,而
forwarded_allow_ips 未放开 ⇒ request.client.host 对每个用户都是同一个值。
照直做 per-IP 限流,全站第 N 个正常用户就被挡,表现是'限流生效了'。
不写死 FORWARDED_ALLOW_IPS:生产 172.20.0.1/测试 172.19.0.1 本就不同值,
Docker 重建网络还会变,变了是静默退回全站一个桶。

带一条专门的断言:两个不同客户端 IP 拿到的桶不是同一个。
只断言'限流会拦'的用例对这个缺陷免疫 —— 一个桶的世界里它也是绿的。

注意:本提交只证明这个函数对。'端点实际把哪个 IP 交给限流器'那条断言
在 Task 7(send-code 端点)里 —— 端点写成 request.client.host 的话,
这里的用例一条都不会红。"
```

---

---

### Task 3: `verify_password` 收口（F3/F9）

**Files:**
- Modify: `katrain/web/core/auth.py`（只改 `verify_password`，`:15-16`）
- Test: `tests/web_ui/test_phone_auth.py`（新建，本 Task 起头）

**Interfaces:**
- Consumes: 无
- Produces: `verify_password(plain_password: str, hashed_password: str) -> bool` —— **永不抛
  `UnknownHashError` / `ValueError`**（`TypeError` 不在收口范围内——复审实测确认需求要
  收口的 5 个哨兵值全部落在 `ValueError` 一侧，`TypeError` 只在调用方传了非 str 时才出现，
  那是调用方的编程错误而非"口令不匹配"，必须原样炸出来；吞掉它的表现是仓储层哪天回来的
  不是 str 时全站每次登录静默变 401，日志不响）。Task 8（手机验证码登录，给没有可用口令的
  账号签 token）与 Task 10（`/auth/set-password`，给这类账号补密码）都建在"这个函数遇到
  哨兵值返回 False 而不是把 500 抛出去"上。

**为什么**（F3 实测，本 session 复跑确认）：
`verify_password("anything", h)` 对 `h ∈ {"", "!", "*", "not-a-bcrypt-hash", "SHADOW_USER_NO_LOCAL_AUTH"}`
**全部抛 `passlib.exc.UnknownHashError: hash could not be identified`** 而不是返回 False。
仓里已埋着一颗同款的雷：`katrain/web/api/v1/endpoints/auth.py:77` 的
`SHADOW_USER_NO_LOCAL_AUTH = "SHADOW_USER_NO_LOCAL_AUTH"` 是个普通字符串，
`:187` 的 `_get_or_create_shadow_user` 拿它当 `hashed_password` 建号。
今天够不着（影子用户只在盒子本地库，而 board 模式的 `/auth/login` 先把请求转发给云端），
但那是**靠调用顺序保住的，不是靠结构**。

> **行号更正**（审查发现 [62]）：这个常量在 `katrain/web/api/v1/endpoints/auth.py:77`，
> **不在**本 Task 要改的 `katrain/web/core/auth.py`。巧的是 `core/auth.py:77` 恰好是
> `@abstractmethod def unfollow_user` —— 照旧写法翻行号会翻到一段完全无关的代码。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_auth.py
"""P3 手机绑定与验证码登录的鉴权侧用例。Task 3 起头，后续 Task 继续往这个文件加。"""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from katrain.web.core.auth import get_password_hash, verify_password  # noqa: E402


@pytest.mark.parametrize(
    "bad_hash",
    ["", "!", "*", "not-a-bcrypt-hash", "SHADOW_USER_NO_LOCAL_AUTH"],
)
def test_verify_password_returns_false_for_unparsable_hash(bad_hash):
    """无法识别的 hash 必须返回 False，不许抛。

    抛的后果：这类账号被打 /auth/login 会 **500 而不是 401**，
    而 500 与 401 可区分"此人存在且没有可用口令" —— 一个免费的账号枚举器。

    `None` 故意不在这张表里：passlib 今天对 `None` 已经返回 False，
    写进来就是一条**拆掉实现也不会红**的假绿断言。表里 5 条都实跑确认过今天抛。"""
    assert verify_password("anything", bad_hash) is False


def test_verify_password_still_works_for_real_hashes():
    h = get_password_hash("correct-horse")
    assert verify_password("correct-horse", h) is True
    assert verify_password("wrong", h) is False


@pytest.fixture
def client_with_sentinel_user(isolated_session_factory):
    """一个真的能打 `/auth/login` 的 app，库里放两个账号：
    `shadowy`（哨兵口令，没有可用密码）与 `normal`（正常 bcrypt 口令，做对照组）。

    `isolated_session_factory` 是 `tests/conftest.py` 里**现成的**夹具
    （`tmp_path` 下的一次性 sqlite + `Base.metadata.create_all` 过）。

    **必须在进 `TestClient` 之前**设 `app.state.session_factory`：
    `TestClient(app)` 当上下文管理器用时会跑 lifespan，而 `_lifespan_server`
    会用它无条件重建 6 个 repo 覆盖 `app.state`。只设 `app.state.user_repo`
    会被覆盖掉，写就落到开发机的真库上 —— `tests/conftest.py` 的写闸会当场拦下。

    用户在 `with` **里面**建：这样拿到的 `app.state.user_repo` 就是端点将要用的
    那一个（lifespan 重建之后的），不是被覆盖掉的那一个。
    `create_app(enable_engine=False)` + 服务端模式下 lifespan 不设
    `app.state.remote_client`，所以 `/auth/login` 走的是本地认证那一支（实跑确认）。
    """
    from katrain.web.api.v1.endpoints.auth import SHADOW_USER_NO_LOCAL_AUTH
    from katrain.web.server import create_app

    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory
    with TestClient(app) as c:
        app.state.user_repo.create_user("shadowy", SHADOW_USER_NO_LOCAL_AUTH)
        app.state.user_repo.create_user("normal", get_password_hash("pw"))
        yield c


def test_login_with_sentinel_hash_user_returns_401_not_500(client_with_sentinel_user):
    """结构断言：哨兵口令账号走完整条 `/auth/login` 拿到的是 401。
    这条挡的是"以后有人在别处又塞一个哨兵值"。

    `/auth/login` 收的是 **JSON**（`login_data: LoginRequest`，
    `katrain/web/api/v1/endpoints/auth.py:232`），不是表单。用 `data=` 会拿到 422，
    那时红的原因与 `verify_password` 无关，而最省事的"修法"是把断言改成 422 —— 
    那条用例从此什么都证明不了。全仓既有的 20 处 `auth/login` 调用都用 `json=`。"""
    c = client_with_sentinel_user
    # 对照组先跑：证明这条路本来就通、库里真的建上了人。
    # 没有它的话，`create_user` 静默失败也会给出 401（"用户不存在"），一样绿。
    ok = c.post("/api/v1/auth/login", json={"username": "normal", "password": "pw"})
    assert ok.status_code == 200, ok.text

    r = c.post("/api/v1/auth/login", json={"username": "shadowy", "password": "x"})
    assert r.status_code == 401
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_auth.py -q`
Expected: FAIL — `6 failed, 1 passed`。
5 条参数化是 `passlib.exc.UnknownHashError: hash could not be identified`；
端到端那条**不是断言失败**，是同一个 `UnknownHashError` 从 `c.post(...)` 里直接抛出来
（`TestClient` 默认 `raise_server_exceptions=True`；生产上 uvicorn 里它是一个 500）——
traceback 最后一帧是 `katrain/web/core/auth.py:16 in verify_password`。
唯一绿的是 `test_verify_password_still_works_for_real_hashes`。

- [ ] **Step 3: 写最小实现**

`katrain/web/core/auth.py:15-16`，整个函数替换成：

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验口令。**无法识别的 hash 返回 False，不抛。**

    passlib 对空串/哨兵值/任何非 bcrypt 串抛 `UnknownHashError`。让它抛出去的后果是
    这类账号被打 /auth/login 时 **500 而不是 401** —— 而 500 与 401 可区分，
    于是任何人都能免费枚举出"哪些账号存在但没有可用口令"。

    仓里已经有这样的哨兵：`SHADOW_USER_NO_LOCAL_AUTH`
    （`katrain/web/api/v1/endpoints/auth.py:77`，`:187` 的 `_get_or_create_shadow_user`
    拿它建盒子影子用户）。今天够不着，因为 board 模式先把 /auth/login 转发给云端了 ——
    那是**调用顺序**保住的，不是结构。这里收口之后就与调用顺序无关。

    **只吞 `ValueError` 与 `TypeError`，不写 `except Exception`**：
    `UnknownHashError` 是 `ValueError` 的子类（实跑确认过 MRO），密码超长这类也是
    `ValueError`，它们都该当"口令不匹配"。而 bcrypt 后端缺失抛的是
    `passlib.exc.MissingBackendError`（`RuntimeError` 的子类）—— 那种故障必须原样炸成
    500 让人看见，吞掉它的表现是"全站所有人的密码都突然不对了"，一声不吭。
    """
    try:
        return bool(pwd_context.verify(plain_password, hashed_password))
    except (ValueError, TypeError):
        return False
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_auth.py -q`
Expected: PASS（7 条：5 条参数化 + 真 hash 1 条 + 端到端 1 条）

- [ ] **Step 5: 变异验证**

| 变异 | 应该变红的用例 |
|---|---|
| `except (ValueError, TypeError)` 收窄成 `except TypeError`（= "只挡类型错" 那种半吊子收口；`UnknownHashError` 是 `ValueError` 子类，会重新漏出去） | 6 条：5 条参数化 + `test_login_with_sentinel_hash_user_returns_401_not_500` |
| 夹具里删掉 `app.state.session_factory = isolated_session_factory` 这一行 | `test_login_with_sentinel_hash_user_returns_401_not_500` —— 报的是 `tests/conftest.py` 那条真库写闸的 `RuntimeError: 测试往开发机的真实数据库写了`，证明这条 e2e 真的跑在自己的一次性库上。**前提**：pytest 头部那行必须是 `real-db write guard: ARMED on …`；开发机的 `DATABASE_URL` 若本身就是临时 sqlite，闸未武装，这条变异不会红（那不是"通过了"，是这条变异今天证不了） |

Run（每次变异后各跑一遍）：`./.venv/bin/python -m pytest tests/web_ui/test_phone_auth.py -q`
Expected: 第一次变异 FAIL（6 failed / 1 passed）；第二次变异 FAIL（**1 error / 6 passed** ——
闸是在夹具里抛的，pytest 记成 error 不是 failure）；两次都改回后 PASS（7 条）。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/core/auth.py tests/web_ui/test_phone_auth.py
git commit -m "fix(auth): verify_password 遇到无法识别的 hash 返回 False 而不是抛

F3 实测:'' / '!' / '*' / 任意非 bcrypt 串都抛 UnknownHashError ⇒ 这类账号被打
/auth/login 会 500 而不是 401,而 500 与 401 可区分,等于一个免费的账号枚举器。
仓里已埋着同款哨兵 SHADOW_USER_NO_LOCAL_AUTH
(katrain/web/api/v1/endpoints/auth.py:77),今天够不着是靠调用顺序
(board 先转发云端),不是靠结构。这里收口之后与调用顺序无关。

只吞 ValueError/TypeError,不写 except Exception:bcrypt 后端缺失抛的
MissingBackendError 是 RuntimeError,必须原样炸成 500 —— 吞掉它的表现是
'全站所有人的密码都突然不对了',一声不吭。

端到端那条用 json= 不是 data=:/auth/login 收的是 JSON(login_data:
LoginRequest),data= 会拿到 422,那时红的原因与 verify_password 无关。
它还先跑一个正常账号拿 200 做对照 —— 否则 create_user 静默失败也会给 401。"
```

---

### Task 4: 库表 —— `User` 两列 + `sms_challenges`（含 `delivered_ok`）

**Files:**
- Modify: `katrain/web/core/models_db.py`
- Test: `tests/web_ui/test_phone_migration.py`

**Interfaces:**
- Consumes: 无 —— 本 Task 只碰 `models_db.py`，不依赖前面任何 Task 的产出。
- Produces:
  - `models_db.User.phone_e164 = Column(String(20), nullable=True)`
  - `models_db.User.phone_verified_at = Column(DateTime(timezone=True), nullable=True)`
  - `models_db.User.__table_args__ = (Index("ix_users_phone_e164", "phone_e164", unique=True),)`
  - `models_db.SmsChallenge`，列固定为：`id / challenge_id / phone_e164 / purpose / code_hash /
    attempts / consumed_at / provider_charged / delivered_ok / is_intl / client_ip /
    created_at / expires_at`
  - **两个布尔列各管一件事，不许合并**（Task 6 按这个口径写 `issue()`）：
    | 列 | 管什么 | 成功 | `SmsRejected` | `SmsUnreachable` |
    |---|---|---|---|---|
    | `provider_charged` | 算不算**全站日额度** | `True` | `False` | `True` |
    | `delivered_ok` | 算不算**同号 60s 冷却** | `True` | `False` | `False` |
  - 下游用法（写死在这里，Task 6 不许再发明第二种）：冷却查询用
    `.filter(models_db.SmsChallenge.delivered_ok.is_(True))`，日额度查询用
    `.filter(models_db.SmsChallenge.provider_charged.is_(True))`。
    **两处都在 SQL 里判，不许在 Python 侧写 `getattr(row, "delivered_ok", True)`。**

**迁移机制**（F1/F2 实测）：`migrations.add_missing_columns()` 拼的 `ALTER TABLE … ADD COLUMN`
**不带 UNIQUE**，`create_missing_indexes()` 用 `index.create()` **保留 index 的 unique**
⇒ 列上不写 `unique=True`、唯一性放 `__table_args__`，两个方言都自动迁移，零手写 DDL。
`sms_challenges` 是**新表**，由 `Base.metadata.create_all()` 建（`SQLAlchemyUserRepository.init_db()`
的第一句）；`add_missing_columns()` 只管"表已存在、少了列"这条路，跳过不存在的表。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_migration.py
"""手机号两列 + sms_challenges 表，以及**迁移那条路**真的会把它们加上。

只测 `create_all` 证明不了生产：线上库早就存在，跑的是
`migrations.add_missing_columns()` / `create_missing_indexes()`
（`SQLAlchemyUserRepository.init_db()` 里那一串）。
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db


def _fresh_engine(tmp_path, name):
    """按模型新建一个库 —— "全新部署"那条路。"""
    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    models_db.Base.metadata.create_all(eng)
    return eng


def _legacy_users_db(tmp_path, name):
    """只有老三列的 users 表 —— 线上库在这次改动之前的形状。"""
    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    md = MetaData()
    Table(
        "users",
        md,
        Column("id", Integer, primary_key=True),
        Column("username", String, unique=True, index=True),
        Column("hashed_password", String),
    )
    md.create_all(eng)
    return eng


def _unique_column_sets(insp, table_name):
    """这张表上「哪几组列被强制唯一」，不管它落成索引还是表约束。

    **不能只看 `get_indexes()`**：列上写 `unique=True` 时，唯一性会落成
    CREATE TABLE 里的表约束，`get_indexes()` 根本看不见它 —— 于是"只看索引"的
    断言对「有人把 unique 从 __table_args__ 挪到列上」这个错误完全免疫。
    """
    out = set()
    for ix in insp.get_indexes(table_name):
        if ix["unique"]:
            out.add(tuple(ix["column_names"]))
    for uc in insp.get_unique_constraints(table_name):
        out.add(tuple(uc["column_names"]))
    return out


def test_user_phone_columns_and_unique_index_exist(tmp_path):
    insp = inspect(_fresh_engine(tmp_path, "t1"))
    cols = {c["name"] for c in insp.get_columns("users")}
    assert {"phone_e164", "phone_verified_at"} <= cols
    idx = {i["name"]: i for i in insp.get_indexes("users")}
    assert "ix_users_phone_e164" in idx
    # **不许写 `is True`**：SQLite 的 inspector 把 unique 反射成 int 1，
    # 而 `1 is True` 为假 ⇒ 那样写的断言恒红，最省事的"修法"就是把它删掉。
    # 2026-09-07 实测：`[(i["name"], i["unique"]) for i in insp.get_indexes("users")]`
    # → `[('ix_users_id', 0), ('ix_users_username', 1), ('ix_users_uuid', 1)]`。
    assert bool(idx["ix_users_phone_e164"]["unique"]) is True


def test_phone_column_itself_is_not_unique():
    """列上不许写 `unique=True`（F2）。

    `add_missing_columns()` 拼的 ADD COLUMN 不带 UNIQUE，写在列上会让
    "新建库"与"迁移旧库"得到不同的表结构 —— 后者根本没有唯一性。
    """
    col = models_db.User.__table__.columns["phone_e164"]
    assert col.unique is not True
    assert col.nullable is True  # 存量账号留 NULL，不造占位号


def test_null_phones_do_not_collide(tmp_path):
    """F1：SQLite 与 PostgreSQL 的唯一索引都不管 NULL ⇒ 几百个老账号不需要占位号。"""
    session = sessionmaker(bind=_fresh_engine(tmp_path, "t3"))()
    session.add(models_db.User(username="a", hashed_password="h"))
    session.add(models_db.User(username="b", hashed_password="h"))
    session.commit()
    assert session.query(models_db.User).count() == 2
    session.close()


def test_two_users_cannot_share_a_phone_number(tmp_path):
    """唯一索引必须**真的拦得住**。

    只断言"索引存在且 unique=1"是在断言元数据；一个号绑到两个账号上会让
    `get_by_phone()` 的 `one_or_none()` 直接抛，而受害者是先绑的那个人。
    """
    Session = sessionmaker(bind=_fresh_engine(tmp_path, "t4"))
    session = Session()
    session.add(models_db.User(username="a", hashed_password="h", phone_e164="+8613800138000"))
    session.commit()
    session.add(models_db.User(username="b", hashed_password="h", phone_e164="+8613800138000"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.close()


def test_sms_challenges_table_shape(tmp_path):
    insp = inspect(_fresh_engine(tmp_path, "t5"))
    cols = {c["name"] for c in insp.get_columns("sms_challenges")}
    assert cols >= {
        "id", "challenge_id", "phone_e164", "purpose", "code_hash", "attempts",
        "consumed_at", "provider_charged", "delivered_ok", "is_intl", "client_ip",
        "created_at", "expires_at",
    }
    idx = {i["name"]: i for i in insp.get_indexes("sms_challenges")}
    assert bool(idx["ix_sms_challenge_cid"]["unique"]) is True


def test_delivered_ok_is_a_mapped_column_not_a_stray_attribute(tmp_path):
    """`delivered_ok` 必须是**映射过的列**，断言要落在**另一个 session** 上。

    列没映射时 `row.delivered_ok = False` 只是给实例挂了个游离属性：
    同一个 session 因 identity map 返回同一个对象，读回来还是 False（**测试绿**）；
    生产的下一个请求是新 session，那个属性根本不存在，调用方的
    `getattr(row, "delivered_ok", True)` 会兜成 True（**行为相反**）。
    2026-09-07 用仓里的 SQLAlchemy 实跑复现过：同 session 读到 False，
    异 session 读到 AttributeError/兜底值。
    """
    Session = sessionmaker(bind=_fresh_engine(tmp_path, "t6"))
    now = datetime.now(timezone.utc)
    s1 = Session()
    s1.add(
        models_db.SmsChallenge(
            challenge_id="cid-1",
            phone_e164="+8613800138000",
            purpose="login",
            code_hash="h" * 64,
            attempts=0,
            provider_charged=True,
            is_intl=False,
            client_ip="203.0.113.9",
            expires_at=now + timedelta(seconds=300),
        )
    )
    s1.commit()
    row = s1.query(models_db.SmsChallenge).filter_by(challenge_id="cid-1").one()
    assert row.delivered_ok is True       # 默认：交出去了就当送达
    assert row.provider_charged is True
    row.delivered_ok = False
    s1.commit()
    s1.close()

    s2 = Session()
    reread = s2.query(models_db.SmsChallenge).filter_by(challenge_id="cid-1").one()
    assert reread.delivered_ok is False
    s2.close()


def test_add_missing_columns_migrates_an_existing_users_table(tmp_path):
    """生产上跑的是这条路：表早就在，靠 ADD COLUMN / CREATE INDEX 补。"""
    eng = _legacy_users_db(tmp_path, "old1")
    migrations.add_missing_columns(eng)
    migrations.create_missing_indexes(eng)
    insp = inspect(eng)
    assert {"phone_e164", "phone_verified_at"} <= {c["name"] for c in insp.get_columns("users")}
    assert ("phone_e164",) in _unique_column_sets(insp, "users")


def test_migrated_old_db_and_fresh_db_agree_on_users(tmp_path):
    """F2 的真判据：**新建库与迁移旧库必须得到同一个结构**。

    2026-09-07 先在今天的 `models_db`（还没有 phone 列）上验过这条前提成立：
    两条路的列集合与唯一列集合都相等（`{('username',), ('uuid',)}`），
    所以这条测试红起来只可能是 phone 那两列/那条索引的问题。
    """
    fresh = inspect(_fresh_engine(tmp_path, "fresh"))
    old = _legacy_users_db(tmp_path, "old2")
    migrations.add_missing_columns(old)
    migrations.create_missing_indexes(old)
    migrated = inspect(old)

    assert {c["name"] for c in migrated.get_columns("users")} == {
        c["name"] for c in fresh.get_columns("users")
    }
    assert _unique_column_sets(migrated, "users") == _unique_column_sets(fresh, "users")
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_migration.py -q`

Expected: **FAIL —— `6 failed, 2 passed`**（2026-09-07 在今天的 `models_db` 上实跑过，
逐条都是这个报错）：

| 用例 | 报错 |
|---|---|
| `test_user_phone_columns_and_unique_index_exist` | `AssertionError: assert {'phone_e164', 'phone_verified_at'} <= {...}` |
| `test_phone_column_itself_is_not_unique` | `KeyError: 'phone_e164'` |
| `test_two_users_cannot_share_a_phone_number` | `TypeError: 'phone_e164' is an invalid keyword argument for User` |
| `test_sms_challenges_table_shape` | `sqlalchemy.exc.NoSuchTableError: sms_challenges` |
| `test_delivered_ok_is_a_mapped_column_not_a_stray_attribute` | `AttributeError: module 'katrain.web.core.models_db' has no attribute 'SmsChallenge'` |
| `test_add_missing_columns_migrates_an_existing_users_table` | `AssertionError: assert {'phone_e164', 'phone_verified_at'} <= {...}` |

**另外两条今天就是绿的，这是对的，不要为了"全红"去改它们**：
`test_null_phones_do_not_collide` 和 `test_migrated_old_db_and_fresh_db_agree_on_users`
断言的是**加了这两列之后必须仍然成立的不变量**（NULL 不许互撞；两条建库路径的结构必须
一致）。它们的红是由 Step 5 的变异证明的 —— 把唯一性挪到列上、或去掉 `unique=True`，
它们当场红。**先跑一次记下这个 6/2 的分布**，实现之后如果变成 7/1 或 5/3，
说明改动的影响面和预期不一样，先搞清楚再往下走。

- [ ] **Step 3: 写最小实现**

`models_db.py` 的 `User` 类里，在 `avatar_url` 之后、`created_at` 之前加：

```python
    # 手机号。**列上不写 unique**：唯一性走下面 __table_args__ 里的 Index。
    # migrations.add_missing_columns() 拼的 ADD COLUMN 不带 UNIQUE，而
    # create_missing_indexes() 用 index.create() 会保留 index 的 unique ⇒
    # 只有写成 Index，「新建库」和「迁移旧库」才得到同一个结构（F1/F2）。
    # 存量账号留 NULL：SQLite 与 PostgreSQL 的唯一索引都不管 NULL，
    # 所以不需要给老账号造占位号。
    phone_e164 = Column(String(20), nullable=True)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
```

在 `User` 类末尾（四个 `relationship` 之后）新增：

```python
    __table_args__ = (Index("ix_users_phone_e164", "phone_e164", unique=True),)
```

新增模型（放在 `QuotaBucket` 附近；`Column/String/Integer/Boolean/DateTime/Index/func`
在 `models_db.py` 顶部都已 import，不需要加 import）：

```python
class SmsChallenge(Base):
    """验证码。**一张表同时承载三件事**：验证码本身、同号冷却、日额度计数。

    为什么不用进程内字典：字典**重启即清零**（F5：`billing.py` 里那个 defaultdict
    就是这个形状，而且它记的是"失败计数"不是冷却）。从表里数 SQL 天然跨重启，
    也不需要第二个存储。

    ⚠️ **跨重启成立，跨 worker 不成立 —— 别把这句读成"已经解决了"。**
    `sms_challenge.issue()` 是「先 `SELECT count(*)` 判额度、再 `INSERT`」，
    中间没有锁、没有条件 UPDATE、也没有唯一约束 ⇒ 多进程并发时 N 个请求会读到
    同一个计数并全部放行，`SMS_DAILY_CAP_*` 这个需求里称作"硬闸"的东西退化成建议值。
    **今天安全的全部理由只有两条**：
      1. 生产是单进程 —— `server.py` 里 `uvicorn.run(app, ...)` 没传 `workers`；
      2. 判额度与 `db.commit()` 之间没有 `await`，同一个事件循环里不会被切走。
    任何一条不成立就失效，而失效表现是**限流变松、没有任何报错**。
    要上多 worker，先把日额度换成 `core/quota.py` 的 `try_consume()` 那种
    `UPDATE … WHERE used + :n <= allowance` + `rowcount == 1` 的条件更新 ——
    同一个仓、同一类问题、已经解对过一次。

    **不进 PROTECTED_TABLES**（`migrations.PROTECTED_TABLES`）：表里没钱也没历史。
    漂移重建会把当天额度计数清零 —— 但 drop+create 只在 SQLite 上跑
    （`SQLAlchemyUserRepository.init_db()` 里那个 `if engine.dialect.name == "sqlite"`
    分支），生产 PG 不可能发生。写在这里免得下一个人误判成漏洞。

    **保留期：没有。** 任何人对 `send-code` 打过的号都会在这里永久留一行明文，
    包括从来不会成为用户的号。本轮不做清理任务 —— 这条要进收尾清单交回给 Fan 定
    保留期，不能只留在代码里没人看见。
    """

    __tablename__ = "sms_challenges"

    id = Column(Integer, primary_key=True, index=True)
    # 不可猜串。verify 只认这个、不收手机号 —— 否则任何人可以拿别人的号
    # 打满失败次数，零成本远程锁死任意用户的登录，受害者手机上一条短信都不响。
    challenge_id = Column(String(43), nullable=False)
    phone_e164 = Column(String(20), nullable=False)
    purpose = Column(String(16), nullable=False)      # login | bind | set_password
    code_hash = Column(String(64), nullable=False)    # 只存 hash，永不存明文
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    # 这一条算不算**全站日额度**。阿里云按提交计费、运营商回执失败也照收，
    # 所以分母是"已提交"不是"已送达"；超时/不可达也算（我们不知道它收没收）。
    # 唯一置 False 的情况是供应商**明确拒收**（HTTP 200 且 Code != OK）：
    # 那一条确定没花钱，算进去等于让攻击者拿必被拒的号零成本打满全站额度。
    provider_charged = Column(Boolean, nullable=False, default=False)
    # 这一条算不算**同号 60s 冷却**。只有真交出去并被接收才算。
    # **必须是真列**：只在实例上挂同名属性时，同一个 session 因 identity map
    # 读回来还是改过的值（测试绿），而生产的下一个请求是新 session，读回来相反。
    delivered_ok = Column(Boolean, nullable=False, default=True)
    is_intl = Column(Boolean, nullable=False, default=False)
    client_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_sms_challenge_cid", "challenge_id", unique=True),
        Index("ix_sms_challenge_phone_purpose", "phone_e164", "purpose", "created_at"),
        Index("ix_sms_challenge_cap", "provider_charged", "is_intl", "created_at"),
        Index("ix_sms_challenge_ip", "client_ip", "created_at"),
    )
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_migration.py -q`
Expected: PASS（8 条）

- [ ] **Step 5: 变异验证**

逐条改坏、跑同一条命令、确认指定用例**当场红**，然后改回来：

| 把什么改坏 | 必须变红的用例 |
|---|---|
| `phone_e164` 的唯一性从 `__table_args__` 挪到列上（`Column(String(20), nullable=True, unique=True)`，同时删掉那条 `Index`） | `test_phone_column_itself_is_not_unique` + `test_migrated_old_db_and_fresh_db_agree_on_users`（迁移那条路会少一组唯一列） |
| `Index("ix_users_phone_e164", "phone_e164", unique=True)` 去掉 `unique=True` | `test_user_phone_columns_and_unique_index_exist` + `test_two_users_cannot_share_a_phone_number` |
| 删掉 `delivered_ok` 这一列 | `test_sms_challenges_table_shape` + `test_delivered_ok_is_a_mapped_column_not_a_stray_attribute`（后者在**第二个 session** 上报 `AttributeError`，第一个 session 里它照样是 False —— 这正是要拿两个 session 断言的原因） |

- [ ] **Step 6: 提交**

```bash
git status --porcelain      # 先确认 engine_game_state.json 没被跑测试改脏（F12）
git add katrain/web/core/models_db.py tests/web_ui/test_phone_migration.py
git commit -m "feat(db): users 加 phone_e164/phone_verified_at + sms_challenges 表

列上不写 unique,唯一性走 __table_args__ 的 Index(F1/F2:add_missing_columns
拼的 ADD COLUMN 不带 UNIQUE,create_missing_indexes 保留 index 的 unique
⇒ 新建库与迁移旧库得到同一个结构)。存量账号 phone 留 NULL,不造占位号。
带一条 fresh-vs-migrated 的对照用例 —— 只测 create_all 证明不了生产那条路。

sms_challenges 一张表承载验证码、同号冷却、日额度三件事,全部 SQL 查询。
provider_charged 与 delivered_ok 是两件事不是一件:前者管日额度(供应商明确
拒收的确定没计费,不算;超时不可达算),后者管 60s 冷却(只有真送出去才算)。
两列都必须是真列 —— 只在实例上挂同名属性时,同 session 因 identity map
读回来是改过的值(测试绿),而生产下一个请求是新 session,读回来相反。

跨 worker 那句删掉了:issue() 是 SELECT count 再 INSERT,中间无锁,
今天安全只因为生产单进程且判额度与 commit 之间没有 await。"
```

---

---

### Task 5: 配置 + fail-fast（接进 lifespan）+ 供应商抽象（拒收/不可达分开）

**Files:**
- Create: `katrain/web/core/sms.py`
- Modify: `katrain/web/core/config.py`
- Modify: `katrain/web/server.py` ← **接线那一行在这里，不在 config.py**
- Modify: `tests/conftest.py` ← **不改它，闸接上之后 8 个今天全绿的文件会集体炸**
- Modify: `docker-compose.yml`
- Test: `tests/web_ui/test_sms_provider.py`

**Interfaces:**
- Consumes: Task 1 的 `katrain.web.core.phone.mask_e164(e164: str) -> str`
  （`mask_e164("+8613800138000")` → `"+86 138****8000"`）。
- Produces:
  - `config.KNOWN_SMS_PROVIDERS: tuple = ("console", "aliyun")`
  - `config.assert_sms_provider_is_configured(mode: str, provider: str, allow_console: bool = False) -> None`
    —— server 模式下 `""` / 未知名一律抛 `RuntimeError`；`"console"` 在 `allow_console=False`（默认）
    时也抛，`allow_console=True` 时放行；board 模式一律放行。
  - `settings` 新增 **15 个字段**，每个都配一条 env 装配（13 个是 `KATRAIN_SMS_*`；
    `REGISTER_IP_DAILY` 例外，是 `KATRAIN_REGISTER_IP_DAILY`）：
    `SMS_PROVIDER / SMS_ACCESS_KEY_ID / SMS_ACCESS_KEY_SECRET / SMS_SIGN_NAME /
    SMS_TEMPLATE_CODE / SMS_CODE_TTL_SEC / SMS_COOLDOWN_SEC / SMS_PHONE_HOURLY /
    SMS_PHONE_DAILY / SMS_IP_DAILY / SMS_MAX_ATTEMPTS / SMS_DAILY_CAP_CN /
    SMS_DAILY_CAP_INTL / SMS_ALLOW_CONSOLE / REGISTER_IP_DAILY`
  - `sms.SmsProviderError(Exception)` / `sms.SmsRejected(SmsProviderError)` /
    `sms.SmsUnreachable(SmsProviderError)`
  - `sms.SmsProvider.send(phone_e164: str, code: str, is_intl: bool) -> None`
  - `sms.ConsoleProvider()`、
    `sms.AliyunProvider(access_key_id, access_key_secret, sign_name, template_code, transport=None)`
    （`transport` 只给测试注入 `httpx.MockTransport`，生产传 `None`）
  - `sms.get_provider() -> SmsProvider`
  - **接线**：`server._lifespan_server` 里 `assert_secret_key_is_safe(...)`（`server.py:176`）
    的**紧邻下一行**。
  - **下游打桩的唯一接缝**：`monkeypatch.setattr(sms, "get_provider", lambda: stub)`。
    Task 6 的 `issue()` 调的是 `sms.get_provider()`（模块属性），打这个点就能截住全部发送。
    **Task 6 起，每一个会走到 `issue()` 的用例都必须打它**（理由见 Step 3 的 conftest 段）。
  - **两类失败的语义**（Task 6 按此分流，见 Task 4 的两列表）：
    `SmsRejected` = 供应商明确拒收，确定没计费 ⇒ **不计入日额度**；
    `SmsUnreachable` = 超时/连不上/5xx/非 JSON，不知道收没收 ⇒ **计入日额度**。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_sms_provider.py
"""短信供应商抽象 + 生产 fail-fast。

这个文件里有两类断言，缺一不可：
  1. 闸函数本身对不对（直接调它）；
  2. 闸**真的接在生产唯一那条启动路径上**（读 `_lifespan_server` 的源码）。
第 2 类不是多余的 —— `tests/web_ui/test_secret_key_gate.py` 里写着本仓已经踩过
的那个坑：函数被测透，唯一的生产调用点没有闸，把那一行删掉整套测试不会红。
"""
import inspect as py_inspect

import httpx
import pytest

from katrain.web.core import config, sms
from katrain.web.core.config import KNOWN_SMS_PROVIDERS, assert_sms_provider_is_configured

# 阿里云 RPC 签名机制文档里的示例向量。**照抄文档，不是我们自己算的**：
# 拿它钉死 string-to-sign 与最终签名，才挡得住"签名算错"——那种错的表现是
# 运营商侧 SignatureDoesNotMatch，一个我们在自己日志里解释不了的失败。
_DOC_PARAMS = {
    # 顺序**故意不按字典序**：签名要求先 sorted()，这样排列本身就在检验它。
    "Format": "XML",
    "Version": "2014-05-26",
    "AccessKeyId": "testid",
    "SignatureMethod": "HMAC-SHA1",
    "Timestamp": "2016-02-23T12:46:24Z",
    "SignatureVersion": "1.0",
    "SignatureNonce": "3ee8c1b8-83d3-44af-a94f-4e0ad82fd6cf",
    "Action": "DescribeRegions",
}
_DOC_STRING_TO_SIGN = (
    "GET&%2F&AccessKeyId%3Dtestid%26Action%3DDescribeRegions%26Format%3DXML"
    "%26SignatureMethod%3DHMAC-SHA1"
    "%26SignatureNonce%3D3ee8c1b8-83d3-44af-a94f-4e0ad82fd6cf"
    "%26SignatureVersion%3D1.0%26Timestamp%3D2016-02-23T12%253A46%253A24Z"
    "%26Version%3D2014-05-26"
)
_DOC_SIGNATURE = "OLeaidS1JvxuMvnyHOwuJ+uX5qY="


def _doc_provider(transport=None):
    return sms.AliyunProvider(
        access_key_id="testid",
        access_key_secret="testsecret",
        sign_name="万智星",
        template_code="SMS_1",
        transport=transport,
    )


# --- 闸函数本身 -------------------------------------------------------------

def test_server_mode_refuses_to_start_without_a_provider():
    """生产未显式配置就 fail-fast。**console 不许在生产静默生效** ——
    那会让 send-code 一路返回 200 而用户永远收不到码（spec §2.1）。"""
    with pytest.raises(RuntimeError, match="KATRAIN_SMS_PROVIDER"):
        assert_sms_provider_is_configured("server", "")


def test_server_mode_refuses_the_console_provider():
    with pytest.raises(RuntimeError, match="console"):
        assert_sms_provider_is_configured("server", "console")


def test_console_is_allowed_only_with_the_explicit_opt_in():
    """默认关 ⇒ 拒；显式打开 ⇒ 放行。本机真浏览器验收靠这条，生产两台机器都不设。"""
    assert assert_sms_provider_is_configured("server", "console", allow_console=True) is None


def test_the_opt_in_does_not_rescue_an_empty_or_unknown_provider():
    """放行口只对 console 开，不是"配错也能起"的万能开关。"""
    for bad in ("", "aliyu"):
        with pytest.raises(RuntimeError):
            assert_sms_provider_is_configured("server", bad, allow_console=True)


def test_server_mode_refuses_an_unknown_provider_name():
    """`KATRAIN_SMS_PROVIDER=aliyu` 这种手滑今天能正常启动，直到第一个用户
    点"发送验证码"才在 get_provider() 里炸 —— 启动期判得了的事不留到请求期。"""
    with pytest.raises(RuntimeError, match="未知的 SMS_PROVIDER"):
        assert_sms_provider_is_configured("server", "aliyu")


def test_server_mode_accepts_aliyun():
    assert assert_sms_provider_is_configured("server", "aliyun") is None


def test_board_mode_is_allowed_without_a_provider():
    """盒子不发短信（四个端点在盒子上 403/503），不该因此拒绝启动。"""
    assert assert_sms_provider_is_configured("board", "") is None


def test_every_known_provider_name_can_actually_be_constructed(monkeypatch):
    """闸放行的名字，工厂必须造得出来。

    两份名单各写各的时，"闸放行了一个工厂造不出来的名字"这种配置会一路活到
    第一个用户点发送。KNOWN_SMS_PROVIDERS 是唯一真源，这条测试是它的绑定。
    """
    for name in KNOWN_SMS_PROVIDERS:
        monkeypatch.setattr(config.settings, "SMS_PROVIDER", name)
        assert isinstance(sms.get_provider(), sms.SmsProvider), name


def test_sms_settings_are_wired_to_env_not_only_declared(monkeypatch):
    """字段声明了但 `Settings.__init__` 里没装配 ⇒ 线上设了 env 也不生效，
    表现是"限流参数怎么调都不动"这种没有任何报错的故障。两处都要写。"""
    monkeypatch.setenv("KATRAIN_SMS_PROVIDER", "aliyun")
    monkeypatch.setenv("KATRAIN_SMS_DAILY_CAP_INTL", "7")
    monkeypatch.setenv("KATRAIN_SMS_COOLDOWN_SEC", "11")
    fresh = config.Settings()
    assert fresh.SMS_PROVIDER == "aliyun"
    assert fresh.SMS_DAILY_CAP_INTL == 7
    assert fresh.SMS_COOLDOWN_SEC == 11


# --- 两个提供方 -------------------------------------------------------------

@pytest.mark.asyncio
async def test_console_provider_prints_a_masked_number_and_the_code(capsys):
    p = sms.ConsoleProvider()
    await p.send("+8613800138000", "123456", is_intl=False)
    out = capsys.readouterr().out
    assert "+86 138****8000" in out     # 掩码，不打明文号
    assert "+8613800138000" not in out
    assert "123456" in out              # 开发要看得到码


def test_aliyun_picks_endpoint_and_action_by_region():
    p = _doc_provider()
    assert p._endpoint(is_intl=False) == "https://dysmsapi.aliyuncs.com/"
    assert p._endpoint(is_intl=True) == "https://dysmsapi.ap-southeast-1.aliyuncs.com/"
    assert p._action(is_intl=False) == "SendSms"
    assert p._action(is_intl=True) == "SendMessageToGlobe"


def test_aliyun_string_to_sign_matches_the_documented_example():
    """把中间产物钉死。

    只断言 `len(sig) == 28` 是假绿：**任何** base64(HMAC-SHA1) 都是 28 字符；
    只断言"与字典顺序无关"也是假绿：任何做了 sorted() 的实现都满足它。
    两条都对一个拼错的 string-to-sign 免疫。
    """
    assert _doc_provider()._string_to_sign(_DOC_PARAMS) == _DOC_STRING_TO_SIGN


def test_aliyun_signature_matches_the_documented_example():
    """HMAC 密钥是 secret + 尾随 `&`。少了那个 `&` 得到的是
    `R8VkbeU3DqhHmAVCdxW/CjqsRK0=` —— 同样 28 字符、同样与顺序无关。"""
    assert _doc_provider()._sign(_DOC_PARAMS) == _DOC_SIGNATURE


# --- send() 的三条出口 ------------------------------------------------------

@pytest.mark.asyncio
async def test_aliyun_domestic_send_signs_and_succeeds_when_code_is_ok():
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"Code": "OK", "Message": "OK"})

    p = _doc_provider(transport=httpx.MockTransport(handler))
    assert await p.send("+8613800138000", "123456", is_intl=False) is None
    assert seen["Action"] == "SendSms"
    assert seen["PhoneNumbers"] == "13800138000"     # 国内通道**不带** +86
    assert seen["SignName"] == "万智星"
    assert seen["TemplateCode"] == "SMS_1"
    assert "123456" in seen["TemplateParam"]
    assert seen["Signature"]                          # 请求里真的带了签名


@pytest.mark.asyncio
async def test_aliyun_intl_send_uses_the_global_action_and_full_e164():
    """国际通道不需要签名与模板报备 ⇒ 它是最先能端到端跑通的那条（D-U4）。"""
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"Code": "OK"})

    p = _doc_provider(transport=httpx.MockTransport(handler))
    await p.send("+85298765432", "654321", is_intl=True)
    assert seen["Action"] == "SendMessageToGlobe"
    assert seen["To"] == "+85298765432"
    assert "654321" in seen["Message"]


@pytest.mark.asyncio
async def test_aliyun_code_not_ok_raises_sms_rejected():
    """HTTP 200 但 Code != OK = **明确拒收，确定没计费**。

    合成一类的后果：send-code 不鉴权，攻击者拿格式合法但一定被拒的号
    零成本把全站日额度打满，当天所有人拿不到码，而我们一分钱短信费都没花。
    """
    def handler(request):
        return httpx.Response(200, json={"Code": "isv.MOBILE_NUMBER_ILLEGAL", "Message": "bad"})

    p = _doc_provider(transport=httpx.MockTransport(handler))
    with pytest.raises(sms.SmsRejected):
        await p.send("+9991234567", "123456", is_intl=True)


@pytest.mark.asyncio
async def test_aliyun_5xx_raises_sms_unreachable():
    """5xx 时我们**不知道**它收没收 ⇒ 保守计入日额度。"""
    def handler(request):
        return httpx.Response(503, text="upstream down")

    p = _doc_provider(transport=httpx.MockTransport(handler))
    with pytest.raises(sms.SmsUnreachable):
        await p.send("+8613800138000", "123456", is_intl=False)


@pytest.mark.asyncio
async def test_aliyun_timeout_raises_sms_unreachable():
    def handler(request):
        raise httpx.ConnectTimeout("simulated")

    p = _doc_provider(transport=httpx.MockTransport(handler))
    with pytest.raises(sms.SmsUnreachable):
        await p.send("+8613800138000", "123456", is_intl=False)


def test_rejected_is_not_swallowed_by_except_unreachable():
    """两个类必须是**兄弟**，不是父子。

    把 SmsRejected 写成 SmsUnreachable 的子类，Task 6 里 `except SmsUnreachable`
    就会把拒收也当成不可达 —— 拒收重新开始占日额度，而且没有任何报错。
    """
    assert issubclass(sms.SmsRejected, sms.SmsProviderError)
    assert issubclass(sms.SmsUnreachable, sms.SmsProviderError)
    assert not issubclass(sms.SmsRejected, sms.SmsUnreachable)
    assert not issubclass(sms.SmsUnreachable, sms.SmsRejected)


# --- 闸必须在生产唯一的启动路径上 -------------------------------------------
#
# 上面那些直接调 assert_sms_provider_is_configured()，把**函数**测透了；
# 它在生产的唯一调用者是 server._lifespan_server。照抄
# tests/web_ui/test_secret_key_gate.py 里那两条的形状。
# 区别一处：那边搜的是**裸函数名**，会连 `from … import …` 那一行一起命中 ——
# 于是"只删调用、留着 import"这种改法它看不见。这里搜**带左括号**的形式。

def test_sms_gate_is_wired_into_the_server_lifespan():
    """删掉 server.py 里那一行调用，这条必须红。"""
    from katrain.web import server

    src = py_inspect.getsource(server._lifespan_server)
    assert "assert_sms_provider_is_configured(" in src, (
        "服务端 lifespan 里没有 SMS_PROVIDER 闸 —— 闸函数写得再好，没人调就是摆设"
    )


def test_sms_gate_runs_before_any_database_work():
    """闸必须挡在任何 DB 动作之前，否则一个配错的部署会先把 engine/router 拉起来、
    可能已经写了库，再拒绝启动 —— 那不是 fail-fast。"""
    from katrain.web import server

    lines = py_inspect.getsource(server._lifespan_server).splitlines()
    gate_at = next(
        (i for i, l in enumerate(lines) if "assert_sms_provider_is_configured(" in l), None
    )
    assert gate_at is not None, "lifespan 里根本没有这个调用"
    db_markers = ("init_db", "SessionLocal", "create_engine", "session_factory")
    first_db = next(
        (i for i, l in enumerate(lines) if any(m in l for m in db_markers)), len(lines)
    )
    assert gate_at < first_db, (
        f"闸在第 {gate_at} 行，而第一处 DB 动作在第 {first_db} 行 —— 闸必须在前面"
    )
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_provider.py -q`
Expected: FAIL — **收集期就炸，19 条全部 error**：模块顶部第一句
`from katrain.web.core import config, sms` 就抛
`ImportError: cannot import name 'sms' from 'katrain.web.core'`。
（把 `sms.py` 建出来之后再跑一次，会换成第二句的
`ImportError: cannot import name 'KNOWN_SMS_PROVIDERS' from 'katrain.web.core.config'` ——
两句 import 都到位之前，不要开始写实现。）

- [ ] **Step 3: 写最小实现**

**(a) `katrain/web/core/config.py`** —— 在 `MIN_SECRET_KEY_CHARS` 之后加常量，在
`assert_secret_key_is_safe` 之后加闸函数：

```python
# `sms.get_provider()` 认得的全部名字。**唯一真源** —— 启动闸只放行这里面的名字，
# 否则"闸放行了一个工厂造不出来的名字"会一路活到第一个用户点发送。
KNOWN_SMS_PROVIDERS = ("console", "aliyun")


def assert_sms_provider_is_configured(mode: str, provider: str, allow_console: bool = False) -> None:
    """服务端模式下必须显式选一个**真**提供方。

    为什么不让 console 在生产兜底：那会让 send-code 一路返回 200 而用户
    **永远收不到码** —— 一种"坏了"和"好着"在用户那里长得一模一样的故障
    （spec §2.1）。盒子不发短信（四个端点在盒子上 403/503），放行。

    为什么未知名也拒：`KATRAIN_SMS_PROVIDER=aliyu` 这种手滑今天能正常启动，
    直到第一个用户点"发送验证码"才在 get_provider() 里炸成 502。
    启动期判得了的事，不要留到请求期。
    """
    if mode != "server":
        return
    name = (provider or "").strip()
    if not name:
        raise RuntimeError(
            "拒绝以未配置的 SMS_PROVIDER 启动服务端：设置 KATRAIN_SMS_PROVIDER=aliyun。"
        )
    # console 的**显式**放行口。Global Constraint #3 禁的是「静默生效」——
    # 一个默认关、必须专门去设的 env 不是静默；而没有它，本机真浏览器验收
    # 根本读不到验证码（表里只存 code_hash，aliyun 空凭据必 502）⇒ 那一整关做不了。
    # 生产两台机器都不设它，闸照旧拒 console。
    if name == "console" and not allow_console:
        raise RuntimeError(
            "拒绝在服务端使用 console 短信提供方：它只打印不发送，"
            "接口会一路返回成功而用户永远收不到码。"
            "本机开发请用 KATRAIN_MODE=board 或直接跑单测。"
        )
    if name not in KNOWN_SMS_PROVIDERS:
        raise RuntimeError(
            f"未知的 SMS_PROVIDER={name!r}：可选 {list(KNOWN_SMS_PROVIDERS)}。"
            "（KATRAIN_SMS_PROVIDER 拼错时，启动期不拒就要等第一个用户去发现。）"
        )
```

`Settings` 类里加字段（放在 `REPORT_RETRY_GRACE_SEC` 之后、`def __init__` 之前）：

```python
    # --- 短信 -----------------------------------------------------------
    SMS_PROVIDER: str = ""                 # console | aliyun；服务端为空即拒绝启动
    SMS_ACCESS_KEY_ID: str = ""
    SMS_ACCESS_KEY_SECRET: str = ""
    SMS_SIGN_NAME: str = "万智星"           # 【智星盒】不可用，见 spec §2.10
    SMS_TEMPLATE_CODE: str = ""
    SMS_CODE_TTL_SEC: int = 300
    SMS_COOLDOWN_SEC: int = 60
    SMS_PHONE_HOURLY: int = 5              # 比阿里云官方流控（5 条/小时）不松
    SMS_PHONE_DAILY: int = 10
    SMS_IP_DAILY: int = 20
    SMS_MAX_ATTEMPTS: int = 5
    # 全站日额度。**两个独立常数，不是"一个 cap 加一个比例"** —— 比例是式子，
    # 调其中一个会静默改另一个；两个独立常数改哪个就是哪个。
    # 定标依据（写在这里，免得后人以为是拍的）：
    #   国内 300：上线首月峰值按 100 个新注册/日 × 1.6 条（含一次重发）≈ 160，
    #            留约 2 倍余量；按 ~¥0.045/条 ⇒ **封顶约 ¥13.5/日**。
    #   国际  50：单价按最坏目的地约 $0.15/条 ⇒ **封顶约 $7.5/日**。国际号是长尾
    #            （要求是"要能绑"不是"主力市场"），却是**最贵的攻击面** ——
    #            所以封顶必须比国内低一个量级，不是低三成。
    # 选这两个数的判据不是"够用"，是**上限被打满时的损失，是我们愿意在没人值班的
    # 夜里承受的**。requirements §3 D-U4 那张表写的是 300 / 100，且那一行自己标着
    # 「⚠️ 待核 …… 实现时以最终值为准」——**这里就是那个最终值**：国内取 300
    # （与需求一致），国际取两个候选里更低的 50。两个都能用下面的 env 覆盖，
    # 改数不需要改代码。
    SMS_DAILY_CAP_CN: int = 300
    SMS_DAILY_CAP_INTL: int = 50
    # console 的显式放行口。**生产两台机器都不设**，只在本机真浏览器验收时开。
    SMS_ALLOW_CONSOLE: bool = False
    # /auth/register 的 per-IP 日限（D-U2：建了限流器就要给那个已知无限流的端点用）。
    # 消费者在 Task 7；声明必须在这里，否则 Settings 是 pydantic BaseModel，读不存在的
    # 属性直接抛，而 monkeypatch 也设不上（raising=False 只跳过存在性预检）。
    REGISTER_IP_DAILY: int = 10
```

`Settings.__init__` 里加装配（放在 `REFRESH_TOKEN_EXPIRE_DAYS` 那行之后）。
**字段和装配是两处，两处都要写** —— 只加字段的话线上设了 env 也不生效：

```python
        # 短信。字段声明 + 这里的 env 装配是两件事，缺一个就"env 设了不生效"。
        data.setdefault("SMS_PROVIDER", os.getenv("KATRAIN_SMS_PROVIDER", ""))
        data.setdefault("SMS_ALLOW_CONSOLE", os.getenv("KATRAIN_SMS_ALLOW_CONSOLE", "") == "1")
        data.setdefault("REGISTER_IP_DAILY", int(os.getenv("KATRAIN_REGISTER_IP_DAILY", 10)))
        data.setdefault("SMS_ACCESS_KEY_ID", os.getenv("KATRAIN_SMS_ACCESS_KEY_ID", ""))
        data.setdefault("SMS_ACCESS_KEY_SECRET", os.getenv("KATRAIN_SMS_ACCESS_KEY_SECRET", ""))
        data.setdefault("SMS_SIGN_NAME", os.getenv("KATRAIN_SMS_SIGN_NAME", "万智星"))
        data.setdefault("SMS_TEMPLATE_CODE", os.getenv("KATRAIN_SMS_TEMPLATE_CODE", ""))
        data.setdefault("SMS_CODE_TTL_SEC", int(os.getenv("KATRAIN_SMS_CODE_TTL_SEC", 300)))
        data.setdefault("SMS_COOLDOWN_SEC", int(os.getenv("KATRAIN_SMS_COOLDOWN_SEC", 60)))
        data.setdefault("SMS_PHONE_HOURLY", int(os.getenv("KATRAIN_SMS_PHONE_HOURLY", 5)))
        data.setdefault("SMS_PHONE_DAILY", int(os.getenv("KATRAIN_SMS_PHONE_DAILY", 10)))
        data.setdefault("SMS_IP_DAILY", int(os.getenv("KATRAIN_SMS_IP_DAILY", 20)))
        data.setdefault("SMS_MAX_ATTEMPTS", int(os.getenv("KATRAIN_SMS_MAX_ATTEMPTS", 5)))
        data.setdefault("SMS_DAILY_CAP_CN", int(os.getenv("KATRAIN_SMS_DAILY_CAP_CN", 300)))
        data.setdefault("SMS_DAILY_CAP_INTL", int(os.getenv("KATRAIN_SMS_DAILY_CAP_INTL", 50)))
```

**(b) `katrain/web/core/sms.py`**（新建）：

```python
"""短信供应商抽象。**零新增依赖**：标准库 hmac/hashlib/base64/urllib.parse + 已有的 httpx。

不用阿里云官方 SDK 的两个理由：(1) 生产依赖清单是 release 分支独有的 hash-pinned
`requirements-web-runtime.txt`，往 `requirements-web.txt` 加包只会**在生产运行时**
ImportError（F8）；(2) 官方 SDK 是同步的，而这里必须 async —— 单进程下同步阻塞拖垮整站。

**两类失败必须分开，这不是风格问题，是钱：**
    SmsRejected     供应商明确拒收（HTTP 200 但 Code != OK）⇒ 确定没计费 ⇒ 不占日额度
    SmsUnreachable  超时 / 连不上 / 5xx / 非 JSON ⇒ 不知道它收没收 ⇒ 保守计入日额度
合成一类的后果：`send-code` 不鉴权，攻击者拿格式合法但一定被拒的号（`+9991234567`）
零成本把全站日额度打满，当天所有人拿不到码，而我们一分钱短信费都没花 —— 花掉的是可用性。
"""
import base64
import hashlib
import hmac
import urllib.parse
import uuid
from datetime import datetime, timezone

import httpx

from katrain.web.core.config import settings
from katrain.web.core.phone import mask_e164


class SmsProviderError(Exception):
    """把码交给供应商这一步失败了。调用方**必须**在两个子类之间分流，
    不要只 `except SmsProviderError` —— 那等于又把两件事合成了一件。"""


class SmsRejected(SmsProviderError):
    """供应商**明确拒收**：HTTP 200，但响应体里 Code != OK。
    含义是"这条没发出去，也没计费" ⇒ 不计入日额度，也不置同号冷却。"""


class SmsUnreachable(SmsProviderError):
    """超时 / 连不上 / 5xx / 响应体不是 JSON。
    含义是"不知道它收没收" ⇒ 保守计入日额度，但不置同号冷却
    （一次抖动不该把用户锁 60 秒）。"""


class SmsProvider:
    async def send(self, phone_e164: str, code: str, is_intl: bool) -> None:
        raise NotImplementedError


class ConsoleProvider(SmsProvider):
    """开发用。只打印，不发送。生产被 assert_sms_provider_is_configured 挡住。"""

    async def send(self, phone_e164: str, code: str, is_intl: bool) -> None:
        # 打掩码不打明文：这行会进开发机的终端和日志文件。
        print(f"[SMS console] to={mask_e164(phone_e164)} intl={is_intl} code={code}")


class AliyunProvider(SmsProvider):
    # 阿里云要求的百分号编码：空格→%20、`*`→%2A、`~` 不编码。
    # Python 的 quote 本来就不编 `~`、且从不产生 `+`，所以 safe="~" 正好等价。
    _SIGN_SAFE = "~"

    def __init__(self, access_key_id, access_key_secret, sign_name, template_code, transport=None):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.sign_name = sign_name
        self.template_code = template_code
        # 只给测试注入 httpx.MockTransport；生产传 None（httpx 用默认传输）。
        self._transport = transport

    @staticmethod
    def _endpoint(is_intl: bool) -> str:
        # 国际那条不需要签名与模板报备 ⇒ 它是最先能端到端跑通的通道（D-U4）。
        return (
            "https://dysmsapi.ap-southeast-1.aliyuncs.com/"
            if is_intl
            else "https://dysmsapi.aliyuncs.com/"
        )

    @staticmethod
    def _action(is_intl: bool) -> str:
        return "SendMessageToGlobe" if is_intl else "SendSms"

    def _string_to_sign(self, params: dict) -> str:
        """阿里云 RPC 签名的规范化串。

        **单独暴露成方法是为了能被单测钉死**：只断言"签名长 28 字符"或"与字典
        顺序无关"是假绿 —— 任何 base64(HMAC-SHA1) 都是 28 字符，任何做了
        sorted() 的实现都与顺序无关，一个拼错的 string-to-sign 照样通过。
        """
        canon = "&".join(
            f"{urllib.parse.quote(k, safe=self._SIGN_SAFE)}="
            f"{urllib.parse.quote(str(v), safe=self._SIGN_SAFE)}"
            for k, v in sorted(params.items())
        )
        return "GET&%2F&" + urllib.parse.quote(canon, safe=self._SIGN_SAFE)

    def _sign(self, params: dict) -> str:
        """HMAC-SHA1(secret + "&") → base64。那个尾随 `&` 是签名规范的一部分。"""
        mac = hmac.new(
            (self.access_key_secret + "&").encode(),
            self._string_to_sign(params).encode(),
            hashlib.sha1,
        )
        return base64.b64encode(mac.digest()).decode()

    async def send(self, phone_e164: str, code: str, is_intl: bool) -> None:
        params = {
            "Action": self._action(is_intl),
            "Version": "2018-05-01" if is_intl else "2017-05-25",
            "Format": "JSON",
            "AccessKeyId": self.access_key_id,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": uuid.uuid4().hex,
            "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if is_intl:
            params.update({"To": phone_e164, "Message": f"Your verification code is {code}"})
        else:
            params.update(
                {
                    "PhoneNumbers": phone_e164[len("+86"):],
                    "SignName": self.sign_name,
                    "TemplateCode": self.template_code,
                    "TemplateParam": f'{{"code":"{code}"}}',
                }
            )
        params["Signature"] = self._sign(params)

        try:
            async with httpx.AsyncClient(timeout=3.0, transport=self._transport) as client:
                resp = await client.get(self._endpoint(is_intl), params=params)
        except Exception as exc:
            # 连不上 / 超时：**不知道**阿里收没收 ⇒ 调用方保守计入日额度。
            raise SmsUnreachable(f"短信供应商不可达: {exc}") from exc

        if resp.status_code >= 500:
            raise SmsUnreachable(f"短信供应商 {resp.status_code}")
        try:
            body = resp.json()
        except ValueError as exc:
            raise SmsUnreachable(f"短信供应商返回了非 JSON（{resp.status_code}）") from exc

        if str(body.get("Code", "")).upper() != "OK":
            # HTTP 200 且 Code != OK：阿里**明确拒收**，确定没计费。
            raise SmsRejected(f"短信供应商拒收: {body.get('Code')} {body.get('Message')}")


def get_provider() -> SmsProvider:
    """按配置造一个提供方。

    未知名在这里抛，**但真正的防线是启动闸** —— `assert_sms_provider_is_configured()`
    在 lifespan 里就拒绝未知名，所以生产走不到这条 raise（走到了说明有人绕过了闸）。
    """
    name = (settings.SMS_PROVIDER or "").strip()
    if name == "console":
        return ConsoleProvider()
    if name == "aliyun":
        return AliyunProvider(
            access_key_id=settings.SMS_ACCESS_KEY_ID,
            access_key_secret=settings.SMS_ACCESS_KEY_SECRET,
            sign_name=settings.SMS_SIGN_NAME,
            template_code=settings.SMS_TEMPLATE_CODE,
        )
    raise SmsProviderError(f"未知的 SMS_PROVIDER={name!r}")
```

**(c) `katrain/web/server.py`** —— 接线。把 `_lifespan_server` 开头那两处各改一行：

```python
    from katrain.web.core.config import assert_secret_key_is_safe, assert_sms_provider_is_configured
```

```python
    assert_secret_key_is_safe(settings.KATRAIN_MODE, settings.SECRET_KEY)
    # 同一条口径的第二道闸：生产不许在"没有短信通道"或"console"的状态下起来。
    # console 在生产静默生效的表现是 send-code 一路 200 而用户永远收不到码 ——
    # 坏了和好着在用户那里长得一样。必须和 SECRET_KEY 闸一样挡在任何 DB 动作之前。
    assert_sms_provider_is_configured(
        settings.KATRAIN_MODE, settings.SMS_PROVIDER, settings.SMS_ALLOW_CONSOLE
    )
```

**注意位置**：`config.py` 里**没有**对 `assert_secret_key_is_safe` 的调用（只有开头的
一句注释和 `:13` 的定义），唯一的生产调用点是 `server.py:176`，在 `_lifespan_server` 里。
闸接在**那一行的下一行**，别去 config.py 找调用点 —— 那里没有。

**(d) `tests/conftest.py`** —— 在现有那段 `os.environ.setdefault("KATRAIN_SECRET_KEY", …)`
（文件 `:68-71`）**之后**追加，形状照抄它：

```python
# --- 测试进程必须拿一个显式的短信提供方 -------------------------------------
#
# `_lifespan_server` 在 SECRET_KEY 闸的下一行调 `assert_sms_provider_is_configured()`。
# 测试进程的 `KATRAIN_MODE` 默认就是 "server"（config.py 的 `KATRAIN_MODE: str = "server"`），
# 不注入的话**每一个跑 lifespan 的用例都会在 startup 抛 RuntimeError**。
# 2026-09-07 用一个模拟该闸的 pytest 插件跑了全量实测：**8 个今天全绿的文件、49 条**
#   tests/test_guest_free_play.py                         (15)
#   tests/test_local_play_recording.py                    ( 2)
#   tests/test_local_play_setup.py                        ( 2)
#   tests/web_ui/test_ai_ladder_api.py                    ( 1)
#   tests/web_ui/test_game_termination_and_chat_identity.py (15)
#   tests/web_ui/test_ladder_injection.py                 ( 3)
#   tests/web_ui/test_lobby_boundaries.py                 ( 7)
#   tests/web_ui/test_ranked_rules.py                     ( 4)
# 加上这一行之后再跑同一套，相对基线的新增失败回到 **0**（同日实测）。
#
# **只能注入 "aliyun"**：闸禁止 server 模式用 console。这不是绕开闸，是与
# SECRET_KEY 完全同一条口径 —— 测试走**和生产同一条路**（真的带着一个合法的
# 提供方名字启动）。不要改成"测试时跳过这个闸"：那样闸在测试里就是死的。
#
# **代价说清楚**：凭据是空的，所以任何**没打桩**就走到 `sms.get_provider().send()`
# 的用例会真的去打 dysmsapi（3 秒超时后抛 SmsUnreachable，或拿到 Code != OK 抛
# SmsRejected）。Task 6 起，凡是会走到 `sms_challenge.issue()` 的用例一律要打
# `monkeypatch.setattr(sms, "get_provider", lambda: stub)`。
os.environ.setdefault("KATRAIN_SMS_PROVIDER", "aliyun")
# 凭据在测试进程里**强制清空**，不是 setdefault：`setdefault` 不会覆盖开发机或
# 线上机器 shell 里可能已经存在的 KATRAIN_SMS_ACCESS_KEY_*，而那意味着一个漏打桩
# 的用例会**真发短信、真花钱**。清空之后最坏结果是阿里云拒收，不是账单。
os.environ["KATRAIN_SMS_ACCESS_KEY_ID"] = ""
os.environ["KATRAIN_SMS_ACCESS_KEY_SECRET"] = ""
```

**(e) `docker-compose.yml`** —— `katrain-web` 服务的 `environment:` 里加五行，
`:?` 的形状照抄同一段里的 `KATRAIN_SECRET_KEY`（`katrain-cron` **不用加**：它跑的是
cron 脚本，不走 `_lifespan_server`）：

```yaml
      - KATRAIN_SMS_PROVIDER=${KATRAIN_SMS_PROVIDER:?KATRAIN_SMS_PROVIDER 必须在 .env 里设置，本轮唯一合法值是 aliyun}
      - KATRAIN_SMS_ACCESS_KEY_ID=${KATRAIN_SMS_ACCESS_KEY_ID:-}
      - KATRAIN_SMS_ACCESS_KEY_SECRET=${KATRAIN_SMS_ACCESS_KEY_SECRET:-}
      - KATRAIN_SMS_SIGN_NAME=${KATRAIN_SMS_SIGN_NAME:-万智星}
      - KATRAIN_SMS_TEMPLATE_CODE=${KATRAIN_SMS_TEMPLATE_CODE:-}
```

用 `:?` 而不是给个默认值：给默认值等于让这道闸在标准部署路径上永远不会响，
那它就只剩装饰作用了。

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_provider.py -q`
Expected: PASS（19 条）

再跑一遍被 conftest 改动直接影响的那 8 个文件，确认闸接上之后它们**没有**变红：

Run:
```
CI=true ./.venv/bin/python -m pytest \
  tests/test_guest_free_play.py tests/test_local_play_recording.py \
  tests/test_local_play_setup.py tests/web_ui/test_ai_ladder_api.py \
  tests/web_ui/test_game_termination_and_chat_identity.py \
  tests/web_ui/test_ladder_injection.py tests/web_ui/test_lobby_boundaries.py \
  tests/web_ui/test_ranked_rules.py tests/web_ui/test_secret_key_gate.py -q
```
Expected: 没有任何一条以 `RuntimeError: 拒绝以未配置的 SMS_PROVIDER 启动服务端` 结束。
（这几个文件**单独跑**时本来就有连不上 PostgreSQL 的既有失败 —— 判据是
"没有 SMS 相关的报错"，不是"全绿"；全量的新增失败比对在 Task 16。）

- [ ] **Step 5: 变异验证**

逐条改坏、跑 `./.venv/bin/python -m pytest tests/web_ui/test_sms_provider.py -q`、
确认指定用例**当场红**，然后改回来：

| 把什么改坏 | 必须变红的用例 |
|---|---|
| 删掉 `server.py` 里 `assert_sms_provider_is_configured(...)` 那一行（`import` 那行留着） | `test_sms_gate_is_wired_into_the_server_lifespan` + `test_sms_gate_runs_before_any_database_work`。**两条都要红** —— 搜的是带左括号的形式，所以留着 import 骗不过去 |
| 把新加的那行挪到 `repo.init_db()` 之后 | `test_sms_gate_runs_before_any_database_work`（`test_sms_gate_is_wired_...` 仍绿 —— 这正是要两条的原因） |
| `_string_to_sign` 的前缀 `"GET&%2F&"` 改成 `"POST&%2F&"` | `test_aliyun_string_to_sign_matches_the_documented_example` + `test_aliyun_signature_matches_the_documented_example`（签名变成 `MxbnVAM4w6sft9xjVpe/GCKueuk=`，仍然是 28 字符 —— 老那条 `len(sig) == 28` 对它是绿的） |
| `_sign` 里 HMAC 密钥去掉尾随 `"&"` | `test_aliyun_signature_matches_the_documented_example`（变成 `R8VkbeU3DqhHmAVCdxW/CjqsRK0=`） |
| `send()` 里 `raise SmsRejected(...)` 换成 `raise SmsUnreachable(...)` | `test_aliyun_code_not_ok_raises_sms_rejected` |
| `class SmsRejected(SmsUnreachable)` | `test_rejected_is_not_swallowed_by_except_unreachable` |
| 闸里 `if name not in KNOWN_SMS_PROVIDERS` 那一支删掉 | `test_server_mode_refuses_an_unknown_provider_name` |
| `config.__init__` 里 `data.setdefault("SMS_DAILY_CAP_INTL", …)` 那行删掉（字段保留） | `test_sms_settings_are_wired_to_env_not_only_declared` |

- [ ] **Step 6: 提交**

```bash
git status --porcelain      # 先确认 engine_game_state.json 没被跑测试改脏（F12）
git add katrain/web/core/sms.py katrain/web/core/config.py katrain/web/server.py \
        tests/conftest.py docker-compose.yml tests/web_ui/test_sms_provider.py
git commit -m "feat(sms): 供应商抽象(console|aliyun) + 生产 fail-fast 接进 lifespan

闸接在 server.py:176 assert_secret_key_is_safe 的下一行 —— config.py 里没有
任何一处调用它,只有定义。带两条源码断言(照抄 test_secret_key_gate.py):
闸出现在 _lifespan_server 里、且排在任何 DB 动作之前。搜的是带左括号的形式,
所以'只删调用留着 import'骗不过去。

console 在生产不许静默生效:那会让 send-code 一路返回 200 而用户永远收不到码,
一种坏了和好着在用户那里长得一样的故障。未知名也在启动期拒 —— 拼错的
KATRAIN_SMS_PROVIDER 否则要等第一个用户去发现。

供应商失败分两类:SmsRejected(HTTP 200 但 Code != OK,确定没计费,不占日额度)
vs SmsUnreachable(超时/5xx/非 JSON,不知道收没收,保守计入)。合成一类时,
攻击者拿必被拒的号就能零成本把全站日额度打满,而我们一分钱没花。

conftest 注入 KATRAIN_SMS_PROVIDER=aliyun 并强制清空凭据:闸禁止 server 模式
用 console,所以只能声称 aliyun;不注入的话 8 个文件 49 条会在 startup 集体炸
(实测)。与 SECRET_KEY 同一条口径 —— 测试走和生产同一条路,不是跳过闸。

签名用阿里云文档的示例向量钉死 string-to-sign 与最终签名:只断言长度 28
或与字典顺序无关是假绿,任何 base64(HMAC-SHA1) 都满足。"
```

- [ ] **Step 7: 部署前置（不在本 Task 执行；合并前必须做完）**

这道闸会让**两台线上机器在合并后拒绝启动** —— `KATRAIN_SMS_PROVIDER` 今天两边都没设。
按用户级规矩「先测试环境再生产」：

1. **home-ubuntu（测试，`go.sailorvoyage.top`）**：在那台机器上跑的 compose 的 `.env` 里加
   `KATRAIN_SMS_PROVIDER=aliyun`（凭据留空），重启 `katrain-web`，确认容器起得来
   （`docker compose logs katrain-web` 里没有 `拒绝以未配置的 SMS_PROVIDER`）。
2. **ucloud-v100（生产，`modelstella.com`）**：同上，测试环境验过之后再做。
3. 两台机器上跑的 compose 各在各自磁盘上，**不是仓里这份** —— 改仓里的
   `docker-compose.yml` 不会自动生效，必须上机改。

**"拿不到阿里云凭据时线上配什么"的答案写死在这里：配 `aliyun` + 空凭据。**
后果说清楚，不留给部署当天发现：
- 服务能正常启动，所有既有功能不受影响；
- 但 `POST /auth/phone/send-code` 会对**每一个**用户失败（空 AccessKeyId 让阿里云返回
  `Code != OK` ⇒ `SmsRejected`），端点按 Task 7 的口径返错，**不会**假装成功；
- 因此**在凭据到位之前，不许打开任何以"已绑手机"为条件的闸**：
  `BILLING_ENFORCED` 保持关（它本来就默认关），发言闸与免费额度闸的上线要排在
  "国际通道端到端发出过一条真短信"之后。否则等于用一个必然失败的通道去卡用户。
- 不要为了"让它先能用"而在生产配 `console`：闸会拒绝启动，这是故意的。

---

### Task 6: challenge 服务 —— 发 / 验 / 三种限流 / 日额度

**Files:**
- Create: `katrain/web/core/sms_challenge.py`
- Test: `tests/web_ui/test_sms_challenge.py`

**Interfaces:**
- Consumes:
  - `phone.is_domestic(e164: str) -> bool`（T1）。**不在这里调 `normalize_e164`**：进 `issue()` 的号
    已经是 E.164 规范形式，归一化在端点上做（T7），这里只判走国内还是国际通道。
  - `sms.get_provider() -> SmsProvider`、`SmsProvider.send(phone_e164: str, code: str, is_intl: bool) -> None`（T5）
  - `sms.SmsProviderError`（基类）/ `sms.SmsRejected`（供应商**明确拒收**，Code != OK，确定未计费）/
    `sms.SmsUnreachable`（超时、连不上，不知道收没收）（T5）
  - `models_db.SmsChallenge`（T4，**已含 `delivered_ok`**）
  - `settings.SMS_CODE_TTL_SEC / SMS_COOLDOWN_SEC / SMS_PHONE_HOURLY / SMS_PHONE_DAILY /
    SMS_IP_DAILY / SMS_MAX_ATTEMPTS / SMS_DAILY_CAP_CN / SMS_DAILY_CAP_INTL`（T5）
- Produces:
  - `async issue(db, phone_e164: str, purpose: str, client_ip: str) -> str` —— 返 `challenge_id`；
    超限抛 `RateLimited(code, retry_after_sec)`；供应商失败抛 `sms.SmsRejected` / `sms.SmsUnreachable`（原样上抛，不吞）
  - `verify_and_consume(db, challenge_id: str, code: str, purpose: str) -> str` —— 返 `phone_e164`；
    失败抛 `ChallengeInvalid(code)`。**同步函数**（不 await 任何东西），端点直接调
  - `class RateLimited(Exception)`：`.code: str` ∈ `{"sms_cooldown", "sms_quota_phone", "sms_quota_ip", "sms_capacity"}`、
    `.retry_after_sec: int | None`（只有 `sms_cooldown` 会给）
  - `class ChallengeInvalid(Exception)`：`.code: str` ∈ `{"challenge_not_found", "challenge_purpose_mismatch",
    "challenge_consumed", "challenge_expired", "challenge_locked", "challenge_code_mismatch"}`
  - `today_start() -> datetime`（**公开名，不是 `_today_start`**）—— 返回"今天"起点的 aware UTC，按东八区切。
    T7 给 `/auth/register` 挂日限流要用**同一个** day0，跨模块拿私有名会在下一次改名时静默失效。
  - `_as_utc(dt: datetime) -> datetime`（模块内时区守卫，接口契约 §3）

**本 Task 明确不做（交回收尾清单，实现时不要顺手加）：**

1. **日额度不是原子的**。`SELECT count(*)` 与 `INSERT` 之间没有锁、没有条件 UPDATE、没有唯一约束
   ⇒ **跨重启成立，跨 worker 不成立**：多进程下 N 个并发请求读到同一个 `submitted` 值并全部放行，
   `SMS_DAILY_CAP_*` 这个需求里叫"硬闸"的东西会退化成建议值。今天安全只因为线上是单进程、
   且 count 与 commit 之间没有 `await`。**改 `--workers` 之前必须先换成条件 UPDATE**
   （仓里已有正确形状：`core/quota.py:79-89` 的 `UPDATE ... WHERE used + :n <= allowance` + `rowcount == 1`）。
   这条要写进模块 docstring，不许再写"天然跨 worker"。
2. **`sms_challenges` 没有保留期清理**：明文存手机号且只增不减，包括从来不会成为用户的那些号。
3. **"被拒次数"没有独立计数器**。本 Task 让拒收不吃日额度（见下），拒收的行仍占 per-IP / per-phone 的格子，
   所以攻击成本是"每个 IP 每天 20 次"而不是零；但没有"拒收 3 次即拉黑当日"那种更便宜的闸。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_sms_challenge.py
"""验证码的发放与核销。

**本文件的夹具契约（三条，缺一条就有用例跑不到断言）：**

1. `stub_provider` 是 **autouse**：每条用例都装一个记录码的替身。不装的话
   `sms.get_provider()` 会按 `settings.SMS_PROVIDER` 走 —— 默认 `""` 当场抛
   `SmsProviderError`（用例根本走不到断言），而 T5 的 conftest 注入之后它是一个
   **真**提供方名，`aliyun` 会拿空凭据真去打 dysmsapi。本文件任何一条用例都不许打到真 provider。
2. SQLite 上 `DateTime(timezone=True)` 存进去/读回来都是 **naive UTC**（实测）。手工造行、
   改时间列一律写 naive（`_now_naive()`）—— 除非那正是用例要造的东西（两条时区用例）。
3. `db` 与 `db2` 是**同一个 engine 上的两个 Session**，用来证明冷却是从行上算的、
   不是某个 Session 的内部状态。
"""
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core import sms_challenge as sc

PHONE_CN = "+8613800138000"
PHONE_CN2 = "+8613800138001"
PHONE_CN3 = "+8613800138002"
PHONE_INTL = "+14155552671"
PHONE_INTL2 = "+14155552672"
IP1 = "203.0.113.9"
IP2 = "198.51.100.7"
IP3 = "192.0.2.44"

_SENT = []


class _P:
    """供应商替身：把码记到 `_SENT`，可选地再抛一个异常。

    **先记录再抛**：失败用例也拿得到那次提交的码。
    """

    def __init__(self, raise_=None):
        self.raise_ = raise_

    async def send(self, phone_e164, code, is_intl):
        _SENT.append({"phone": phone_e164, "code": code, "is_intl": is_intl})
        if self.raise_ is not None:
            raise self.raise_


@pytest.fixture(autouse=True)
def stub_provider(monkeypatch):
    """见文件 docstring 第 1 条。需要模拟失败的用例在自己体内再 setattr 一次覆盖它。"""
    _SENT.clear()
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P())
    yield
    _SENT.clear()


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture
def db2(engine):
    """第二个 Session，同一个 engine（`:memory:` 在同线程里是同一条连接）。"""
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _last_code():
    assert _SENT, "没有任何一条短信被提交给替身 provider"
    return _SENT[-1]["code"]


def _wrong_code():
    """保证与真码不同的一个码（真码是随机的，写死 '000000' 有百万分之一会撞上）。"""
    return "654321" if _last_code() != "654321" else "123456"


def _now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _advance(db, cid, seconds):
    """把某行的 created_at 挪 seconds 秒（负数 = 挪早，用来跨过 60 秒冷却窗）。"""
    row = sc._row_by_cid(db, cid)
    row.created_at = row.created_at + timedelta(seconds=seconds)
    db.commit()


def _advance_expiry(db, cid, seconds):
    row = sc._row_by_cid(db, cid)
    row.expires_at = _now_naive() + timedelta(seconds=seconds)
    db.commit()


def test_as_utc_tags_naive_and_converts_aware():
    """守卫本身。naive 当 UTC 打标；aware 按**真实偏移**换算 ——
    无守卫的 `.replace(tzinfo=utc)` 会把 11:00+08:00 当成 11:00 UTC，第二条当场红。"""
    assert sc._as_utc(datetime(2026, 9, 7, 3, 0)) == datetime(2026, 9, 7, 3, 0, tzinfo=timezone.utc)
    aware = datetime(2026, 9, 7, 11, 0, tzinfo=timezone(timedelta(hours=8)))
    assert sc._as_utc(aware) == datetime(2026, 9, 7, 3, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_issue_stores_only_a_hash(db):
    cid = await sc.issue(db, PHONE_CN, "login", IP1)
    row = sc._row_by_cid(db, cid)
    code = _last_code()
    assert len(code) == 6 and code.isdigit()
    assert row.code_hash == sc._hash(code)          # 存的是**发出去那个码**的 hash
    assert len(row.code_hash) == 64                 # sha256 hex
    assert code not in row.code_hash + row.phone_e164 + row.purpose
    # challenge_id 是随机串，不做 substring 断言（会千分之一误报）；只钉它不是码本身、且不可猜。
    assert row.challenge_id != code and len(row.challenge_id) >= 32


@pytest.mark.asyncio
async def test_issuing_a_new_code_invalidates_the_old_one(db):
    cid1 = await sc.issue(db, PHONE_CN, "login", IP1)
    _advance(db, cid1, seconds=-120)                # 只为跨过冷却窗
    cid2 = await sc.issue(db, PHONE_CN, "login", IP1)
    assert sc._row_by_cid(db, cid1).consumed_at is not None   # 旧码已作废
    assert sc._row_by_cid(db, cid2).consumed_at is None


@pytest.mark.asyncio
async def test_cooldown_holds_across_two_sessions(db, db2):
    """冷却是从**行**上算的，不是某个 Session 的内部状态。

    **不证明**跨进程：同一进程里的字典同样能过这条。跨 worker 那件事今天不成立，
    见模块 docstring 与本 Task 的"明确不做"第 1 条。
    """
    await sc.issue(db, PHONE_CN, "login", IP1)
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db2, PHONE_CN, "login", IP1)
    assert e.value.code == "sms_cooldown"
    # 上界这一半是在挡"elapsed 算成负数"：那种实现给出的 retry_after 是 28000 多秒。
    assert 0 < e.value.retry_after_sec <= sc.settings.SMS_COOLDOWN_SEC + 1


@pytest.mark.asyncio
async def test_cooldown_ignores_purpose(db):
    """冷却的键是**手机号**，跨 purpose。

    purpose 是不鉴权端点 send-code 的请求体字段、调用方全控；把它算进键里，
    同一个号同一分钟就能收 3 条，直接踩穿运营商"同签名对同号 1 条/分钟"的流控，
    用户拿到的是我们解释不了的运营商侧失败（requirements §2.10）。
    """
    await sc.issue(db, PHONE_CN, "login", IP1)
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, PHONE_CN, "bind", IP1)
    assert e.value.code == "sms_cooldown"


@pytest.mark.asyncio
async def test_cooldown_survives_a_newer_failed_send(db):
    """成功一条 → 之后有一条更新的**失败**行 → 冷却必须还在。

    "先取最新一行、再在 Python 里看 delivered_ok"的写法在这条上会放行：
    它问的是"最近一次发送，如果它失败就当没有冷却"，而要问的是"最近一次**成功**发送"。
    失败行手工插入（而不是让 provider 抛一次），因为那条路自己会被前一次的冷却挡住，
    造不出这个状态。
    """
    await sc.issue(db, PHONE_CN, "login", IP1)
    db.add(models_db.SmsChallenge(
        challenge_id="a-newer-row-that-was-never-delivered",
        phone_e164=PHONE_CN, purpose="login", code_hash="0" * 64, attempts=0,
        provider_charged=True, delivered_ok=False, is_intl=False, client_ip=IP1,
        created_at=_now_naive() + timedelta(seconds=1),
        expires_at=_now_naive() + timedelta(seconds=300),
    ))
    db.commit()
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, PHONE_CN, "login", IP1)
    assert e.value.code == "sms_cooldown"


@pytest.mark.asyncio
async def test_cooldown_uses_the_real_offset_of_an_aware_created_at(db):
    """生产（PG）读回的 created_at 是**带会话时区偏移的 aware 值**；SQLite 存不下时区，
    所以只能这样造：改内存里那个对象的属性、`flush()` 但**不 commit**，
    identity map 会把同一个对象连同这个 aware 值交回给 `issue()` 的查询
    （commit 会 expire 属性、下次访问就退回 SQLite 的 naive 值，故不能 commit）。

    这一行的**真实时刻是 10 分钟前**，冷却窗只有 60 秒 ⇒ 正确实现放行。
    无守卫的 `.replace(tzinfo=utc)` 会把 +08:00 的墙上时间当成 UTC、把它读成"8 小时后"，
    elapsed 变成 -28200 ⇒ 抛 `sms_cooldown`、`retry_after≈28860`。
    **这就是生产上"每个用户第一次取码就被判冷却"的那条路。**
    """
    cid = await sc.issue(db, PHONE_CN, "login", IP1)
    row = sc._row_by_cid(db, cid)
    row.created_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).astimezone(
        timezone(timedelta(hours=8))
    )
    db.flush()
    await sc.issue(db, PHONE_CN, "login", IP1)      # 不许抛


@pytest.mark.asyncio
async def test_provider_failure_does_not_start_the_phone_cooldown(db, monkeypatch):
    """一次抖动不该把用户锁 60 秒。这正是"占额度"与"起冷却"必须分成两位记的理由。"""
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P(raise_=sc.sms.SmsUnreachable("超时")))
    with pytest.raises(sc.sms.SmsUnreachable):
        await sc.issue(db, PHONE_CN, "login", IP1)
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P())
    cid = await sc.issue(db, PHONE_CN, "login", IP1)          # 不该被冷却挡住
    assert sc._row_by_cid(db, cid).delivered_ok is True


@pytest.mark.asyncio
async def test_phone_hourly_cap_is_enforced(db, monkeypatch):
    monkeypatch.setattr(sc.settings, "SMS_PHONE_HOURLY", 2)
    for _ in range(2):
        cid = await sc.issue(db, PHONE_CN, "login", IP1)
        _advance(db, cid, seconds=-120)             # 跨过冷却窗，仍在同一小时内
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, PHONE_CN, "login", IP1)
    assert e.value.code == "sms_quota_phone"


@pytest.mark.asyncio
async def test_two_different_ips_do_not_share_the_ip_bucket(db, monkeypatch):
    """只断言"IP 限流会拦"的用例，在"全站一个桶"的世界里也是绿的 —— 所以第三次换 IP 必须放行。"""
    monkeypatch.setattr(sc.settings, "SMS_IP_DAILY", 1)
    await sc.issue(db, PHONE_CN, "login", IP1)
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, PHONE_CN2, "login", IP1)           # 同 IP 换个号 —— 撞 IP 日额度
    assert e.value.code == "sms_quota_ip"
    await sc.issue(db, PHONE_CN3, "login", IP2)               # 换个 IP —— 必须放行


@pytest.mark.asyncio
async def test_unreachable_send_still_counts_against_the_daily_cap(db, monkeypatch):
    """超时/连不上 ⇒ 不知道阿里收没收 ⇒ 保守占一格额度（阿里国际短信按**提交**计费）。"""
    monkeypatch.setattr(sc.settings, "SMS_DAILY_CAP_INTL", 1)
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P(raise_=sc.sms.SmsUnreachable("超时")))
    with pytest.raises(sc.sms.SmsUnreachable):
        await sc.issue(db, PHONE_INTL, "login", IP1)
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P())
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, PHONE_INTL2, "login", IP2)
    assert e.value.code == "sms_capacity"


@pytest.mark.asyncio
async def test_rejected_send_does_not_count_against_the_daily_cap(db, monkeypatch):
    """供应商**明确拒收**（HTTP 200 + Code != OK）⇒ 确定未计费 ⇒ 不占日额度。

    把它算进去的代价不是多花钱，是**免费**：格式合法但必被拒的号要多少有多少，
    3 个 IP × 20 次就能把国际额度打满一整天，之后 send-code 对所有人 503 sms_capacity，
    而攻击者和我们都没花一分钱。行本身留着（per-IP / per-phone 照数），只撤"占额度"这一位。
    """
    monkeypatch.setattr(sc.settings, "SMS_DAILY_CAP_INTL", 1)
    monkeypatch.setattr(sc.sms, "get_provider",
                        lambda: _P(raise_=sc.sms.SmsRejected("MOBILE_NUMBER_ILLEGAL")))
    with pytest.raises(sc.sms.SmsRejected):
        await sc.issue(db, PHONE_INTL, "login", IP1)
    rejected = db.query(models_db.SmsChallenge).filter_by(phone_e164=PHONE_INTL).one()
    assert rejected.provider_charged is False
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P())
    assert await sc.issue(db, PHONE_INTL2, "login", IP2)      # 额度没被那次拒收吃掉


@pytest.mark.asyncio
async def test_domestic_and_intl_caps_are_independent(db, monkeypatch):
    """两个独立计数器，互不借用。两个 cap 都设成 1 才判得了 —— 只压低国际那个的话，
    共用一个计数器的实现也会绿。"""
    monkeypatch.setattr(sc.settings, "SMS_DAILY_CAP_INTL", 1)
    monkeypatch.setattr(sc.settings, "SMS_DAILY_CAP_CN", 1)
    await sc.issue(db, PHONE_INTL, "login", IP1)
    await sc.issue(db, PHONE_CN, "login", IP2)                # 国内额度没被国际那条吃掉
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, PHONE_CN2, "login", IP3)           # 国内这格确实已经满了
    assert e.value.code == "sms_capacity"


def test_verify_takes_challenge_id_not_phone():
    """spec §2.2：verify 若收手机号，任何人可拿别人的号打满失败次数，
    零成本远程锁死任意用户的登录，受害者手机上一条短信都不会响。"""
    sig = inspect.signature(sc.verify_and_consume)
    assert "challenge_id" in sig.parameters
    assert "phone" not in sig.parameters and "phone_e164" not in sig.parameters


@pytest.mark.asyncio
async def test_verify_consumes_once_only(db):
    cid = await sc.issue(db, PHONE_CN, "login", IP1)
    code = _last_code()
    assert sc.verify_and_consume(db, cid, code, "login") == PHONE_CN
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, code, "login")
    assert e.value.code == "challenge_consumed"


def test_verify_rejects_an_unknown_challenge_id(db):
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, "no-such-challenge", "123456", "login")
    assert e.value.code == "challenge_not_found"


@pytest.mark.asyncio
async def test_wrong_code_counts_attempts_and_locks_the_challenge(db, monkeypatch):
    monkeypatch.setattr(sc.settings, "SMS_MAX_ATTEMPTS", 3)
    cid = await sc.issue(db, PHONE_CN, "login", IP1)
    for _ in range(3):
        with pytest.raises(sc.ChallengeInvalid) as e:
            sc.verify_and_consume(db, cid, _wrong_code(), "login")
        assert e.value.code == "challenge_code_mismatch"
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, _last_code(), "login")  # 正确的码也不认了
    assert e.value.code == "challenge_locked"


@pytest.mark.asyncio
async def test_purpose_mismatch_is_rejected(db):
    """拿 login 的码去改密码 —— 必须拒。"""
    cid = await sc.issue(db, PHONE_CN, "login", IP1)
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, _last_code(), "set_password")
    assert e.value.code == "challenge_purpose_mismatch"


@pytest.mark.asyncio
async def test_expired_challenge_is_rejected(db):
    cid = await sc.issue(db, PHONE_CN, "login", IP1)
    _advance_expiry(db, cid, seconds=-1)
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, _last_code(), "login")
    assert e.value.code == "challenge_expired"


@pytest.mark.asyncio
async def test_expiry_uses_the_real_offset_of_an_aware_expires_at(db):
    """`verify_and_consume` 里那处时区比较。造法同 created_at 那条（见它的 docstring）。

    这一行的**真实时刻是 10 分钟前**（已过期）；无守卫的 `.replace(tzinfo=utc)`
    会把 +08:00 的墙上时间读成"7 小时 50 分之后"⇒ 判成没过期、放行一个早该失效的码。
    """
    cid = await sc.issue(db, PHONE_CN, "login", IP1)
    row = sc._row_by_cid(db, cid)
    row.expires_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).astimezone(
        timezone(timedelta(hours=8))
    )
    db.flush()
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, _last_code(), "login")
    assert e.value.code == "challenge_expired"
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_challenge.py -q`

Expected: FAIL —— 收集期就红，20 条一条都跑不到：

```
ERROR tests/web_ui/test_sms_challenge.py - ModuleNotFoundError: No module named 'katrain.web.core.sms_challenge'
```

- [ ] **Step 3: 写最小实现**

```python
# katrain/web/core/sms_challenge.py
"""验证码的发放与核销。**三种限流与日额度全部从 sms_challenges 表数 SQL。**

不用进程内字典的理由（F5）：重启即清零。`billing.py:58` 那个 defaultdict 就是这个形状，
而且它是"失败计数"不是"冷却"。

**这里的原子性到哪为止 —— 别把这段读成"已经解决了"**：额度是
`SELECT count(*)` 判、`INSERT` 落，两步之间没有锁、没有条件 UPDATE、也没有唯一约束。
所以**跨重启成立，跨 worker 不成立**：多进程下 N 个并发请求会读到同一个 `submitted` 值
并全部放行，`SMS_DAILY_CAP_*` 这个需求里叫"硬闸"的东西退化成建议值。今天恰好安全，
只因为线上是单进程、且 count 与 commit 之间没有 `await` —— 两个都是会过期的前提，
失效表现同样是"限流变松，没有任何报错"。**改 `--workers` 之前必须先把日额度换成条件
UPDATE**：仓里已有正确形状 `core/quota.py:79-89`（`UPDATE ... WHERE used + :n <= allowance`
+ `rowcount == 1`）。

三个时间口径，别混：
  * 写进 SQL 比较的值一律用 aware（SQLite 存时丢掉 tz 得到 UTC 墙上时间，PG 是真 timestamptz，
    两边都对）；
  * 从库里读回来再做 Python 减法的值，一律先过 `_as_utc()`；
  * "今天"按东八区切（用户在的时区），见 `today_start()`。
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from katrain.web.core import models_db, sms
from katrain.web.core.config import settings
from katrain.web.core.phone import is_domestic

logger = logging.getLogger(__name__)

SHANGHAI = timezone(timedelta(hours=8))


class RateLimited(Exception):
    def __init__(self, code: str, retry_after_sec: int | None = None):
        super().__init__(code)
        self.code = code
        self.retry_after_sec = retry_after_sec


class ChallengeInvalid(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _as_utc(dt: datetime) -> datetime:
    """把库里读回来的时间统一成 aware UTC。

    **不许写成无守卫的 `.replace(tzinfo=timezone.utc)`**：SQLite 读回 naive
    （所以单测怎么写都绿），PostgreSQL + psycopg2 读回的是**带会话时区偏移的 aware 值**，
    `.replace()` 会把真实偏移直接抹掉 ⇒ 生产上 elapsed 变负数，
    **每个用户第一次取码就被判 sms_cooldown、retry_after≈28860 秒**。
    仓里既有的两处正确写法：`ai_ladder_ranked.py:1236-1238`、`endpoints/ai_ladder.py:218-219`。
    """
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _row_by_cid(db, challenge_id: str):
    return db.query(models_db.SmsChallenge).filter_by(challenge_id=challenge_id).one_or_none()


def today_start() -> datetime:
    """"今天"的起点，按东八区切，返回 aware UTC。

    **公开名**：Task 7 给 `/auth/register` 挂日限流时要用同一个 day0。
    跨模块拿一个下划线开头的名字，会在下一次改名时静默失效。
    """
    now = datetime.now(SHANGHAI)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _count(db):
    return db.query(func.count(models_db.SmsChallenge.id))


async def issue(db, phone_e164: str, purpose: str, client_ip: str) -> str:
    """发一条码，返回 challenge_id。

    顺序是刻意的：**先查所有额度，再落行，再交给供应商**。
    落行时 `provider_charged=True, delivered_ok=False` —— "已提交、还没证明发出去"：
    崩在 commit 与 send 之间时，留下的行只吃一格日额度（保守，符合"按提交计费"），
    不会给一个根本没收到短信的用户起 60 秒冷却。
    """
    C = models_db.SmsChallenge
    intl = not is_domestic(phone_e164)
    now = datetime.now(timezone.utc)
    day0 = today_start()

    # 1) 同号冷却。
    #    **键是手机号，跨 purpose**：purpose 是不鉴权端点 send-code 的请求体字段、调用方全控；
    #    算进键里的话同一个号同一分钟能收 3 条，直接踩穿运营商"同签名对同号 1 条/分钟"的流控
    #    (requirements §2.10)，用户拿到的是我们解释不了的运营商侧失败。
    #    **判据必须在 SQL 里**：要找的是"最近一次**成功**发送"。先 order_by 取最新一行、
    #    再在 Python 里看 delivered_ok，问的是"最近一次发送，失败就当没有冷却"——
    #    只要最新那行失败，5 秒前那条成功的就被跳过了。
    last_delivered = (
        db.query(C)
        .filter(C.phone_e164 == phone_e164, C.delivered_ok.is_(True))
        .order_by(C.created_at.desc())
        .first()
    )
    if last_delivered is not None:
        elapsed = (now - _as_utc(last_delivered.created_at)).total_seconds()
        if elapsed < settings.SMS_COOLDOWN_SEC:
            raise RateLimited("sms_cooldown", int(settings.SMS_COOLDOWN_SEC - elapsed) + 1)

    # 2) 同号小时 / 日上限。这两个数**不看成功与否**：一个号被反复要码本身就是要拦的事。
    per_phone = _count(db).filter(C.phone_e164 == phone_e164)
    if per_phone.filter(C.created_at >= now - timedelta(hours=1)).scalar() >= settings.SMS_PHONE_HOURLY:
        raise RateLimited("sms_quota_phone")
    if per_phone.filter(C.created_at >= day0).scalar() >= settings.SMS_PHONE_DAILY:
        raise RateLimited("sms_quota_phone")

    # 3) per-IP 日上限。client_ip 由调用方给（T7 用 client_ip_for_ratelimit，不是 request.client.host）。
    if _count(db).filter(C.client_ip == client_ip, C.created_at >= day0).scalar() >= settings.SMS_IP_DAILY:
        raise RateLimited("sms_quota_ip")

    # 4) 全站日额度。分母是**已提交条数**（阿里国际短信按提交计费、运营商回执失败照收），
    #    国内国际两个独立计数器，互不借用。
    cap = settings.SMS_DAILY_CAP_INTL if intl else settings.SMS_DAILY_CAP_CN
    submitted = _count(db).filter(
        C.provider_charged.is_(True), C.is_intl == intl, C.created_at >= day0
    ).scalar()
    if submitted >= cap:
        logger.error("[sms] 日额度打满 %s/%s (intl=%s) —— 被刷穿的表现是'今天怎么没人能注册'",
                     submitted, cap, intl)
        raise RateLimited("sms_capacity")
    if submitted >= int(cap * 0.8):
        logger.error("[sms] 日额度已用 %s/%s (intl=%s)", submitted, cap, intl)

    # 5) 发新码作废该号该用途的全部未消费旧码（spec §1.1）。
    #    **这里的键是 (号, 用途)，与上面冷却的键(只有号)不同，是有意的**：冷却保护的是
    #    那部手机不被运营商流控打回；作废回答的是"哪一个码对这个用途还有效"。
    (db.query(C)
       .filter(C.phone_e164 == phone_e164, C.purpose == purpose, C.consumed_at.is_(None))
       .update({"consumed_at": now}, synchronize_session=False))

    code = f"{secrets.randbelow(1000000):06d}"
    cid = secrets.token_urlsafe(32)
    row = C(
        challenge_id=cid,
        phone_e164=phone_e164,
        purpose=purpose,
        code_hash=_hash(code),        # 只存 hash，明文码只活在这个函数的局部变量里
        attempts=0,
        provider_charged=True,        # 已向供应商提交 ⇒ 占一格日额度
        delivered_ok=False,           # 还没证明发出去 ⇒ 先不起冷却
        is_intl=intl,
        client_ip=client_ip,
        expires_at=now + timedelta(seconds=settings.SMS_CODE_TTL_SEC),
    )
    db.add(row)
    db.commit()

    # 注意这里是 `sms.get_provider()`（模块属性，调用时才解析），不是
    # `from katrain.web.core.sms import get_provider` —— 后者拿的是导入时的绑定，
    # 测试打的桩就打不进来了。
    try:
        await sms.get_provider().send(phone_e164, code, is_intl=intl)
    except sms.SmsRejected:
        # 明确拒收（HTTP 200 + Code != OK）⇒ 阿里确定没计费 ⇒ 不占日额度。
        # 不这样做的代价不是多花钱，是**免费**：格式合法但必被拒的号要多少有多少，
        # 几个 IP 就能把国际额度打满一整天，攻击者和我们都不花一分钱。
        # 行本身留着 —— per-IP / per-phone 两个计数照数它，这才是拒收的成本所在。
        row.provider_charged = False
        db.commit()
        raise
    # SmsUnreachable（超时/连不上）不在这里捕：不知道阿里收没收 ⇒ 保守让这一行继续
    # 占一格日额度；它的 delivered_ok 仍是 False ⇒ 不会起冷却。

    row.delivered_ok = True
    db.commit()
    return cid


def verify_and_consume(db, challenge_id: str, code: str, purpose: str) -> str:
    """核销。**只收 challenge_id，不收手机号**（spec §2.2）：收手机号的话，任何人都能拿
    别人的号打满失败次数，零成本远程锁死任意用户的登录，而受害者手机上一条短信都不会响。
    返回该 challenge 的手机号。"""
    row = _row_by_cid(db, challenge_id)
    now = datetime.now(timezone.utc)
    if row is None:
        raise ChallengeInvalid("challenge_not_found")
    if row.purpose != purpose:
        raise ChallengeInvalid("challenge_purpose_mismatch")
    if row.consumed_at is not None:
        raise ChallengeInvalid("challenge_consumed")
    if _as_utc(row.expires_at) <= now:
        raise ChallengeInvalid("challenge_expired")
    if row.attempts >= settings.SMS_MAX_ATTEMPTS:
        raise ChallengeInvalid("challenge_locked")
    if not secrets.compare_digest(row.code_hash, _hash(code)):
        row.attempts += 1
        db.commit()
        raise ChallengeInvalid("challenge_code_mismatch")
    row.consumed_at = now
    db.commit()
    return row.phone_e164
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_challenge.py -q`
Expected: PASS（20 条）

- [ ] **Step 5: 变异验证十条防线**

逐条改掉、跑一次、确认**只有**指名的用例变红，然后改回来：

| 改哪一处 | 改成什么 | 应该红的用例 |
|---|---|---|
| 第 5 步"作废旧码"的 `db.query(C)...update(...)` | 整段删掉 | `test_issuing_a_new_code_invalidates_the_old_one` |
| `verify_and_consume` 的 `row.attempts += 1` + 紧跟的 `db.commit()` | 两行删掉 | `test_wrong_code_counts_attempts_and_locks_the_challenge` |
| `except sms.SmsRejected:` 里的 `row.provider_charged = False` + `db.commit()` | 两行删掉（拒收也占额度） | `test_rejected_send_does_not_count_against_the_daily_cap` |
| 第 1 步冷却查询的 filter | 加回 `C.purpose == purpose` | `test_cooldown_ignores_purpose` |
| 第 1 步冷却查询的 filter | 去掉 `C.delivered_ok.is_(True)`，改成在 `if last_delivered is not None and last_delivered.delivered_ok:` 里判 | `test_cooldown_survives_a_newer_failed_send` |
| `_as_utc` 的函数体 | 改成无守卫的 `return dt.replace(tzinfo=timezone.utc)` | `test_as_utc_tags_naive_and_converts_aware`、`test_cooldown_uses_the_real_offset_of_an_aware_created_at`、`test_expiry_uses_the_real_offset_of_an_aware_expires_at`（**3 条**） |
| 建行时的 `delivered_ok=False` | 改成 `delivered_ok=True` | `test_provider_failure_does_not_start_the_phone_cooldown` |
| 在 `except sms.SmsRejected:` 之前插一个 `except sms.SmsUnreachable:` 分支，同样把 `provider_charged` 置 False | —— | `test_unreachable_send_still_counts_against_the_daily_cap` |
| 第 4 步日额度查询的 filter | 去掉 `C.is_intl == intl` | `test_domestic_and_intl_caps_are_independent` |
| 第 3 步 per-IP 查询的 filter | 去掉 `C.client_ip == client_ip` | `test_two_different_ips_do_not_share_the_ip_bucket` |

**这十条是写计划时实跑过的**（隔离脚本：本实现逐字照搬，只把 T1/T4/T5 换成最小替身；
SQLAlchemy 2.0.46 + 内存 SQLite + `asyncio_mode=auto`）。结果如表：每一条只有指名的
用例变红、其余全绿；不变异时 20 条全绿。**接进真仓后仍要照跑一遍** —— 那边的
`models_db.SmsChallenge` 是 T4 的真模型，`sms.SmsRejected` 是 T5 的真异常类。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/core/sms_challenge.py tests/web_ui/test_sms_challenge.py
git commit -m "feat(sms): 验证码发放与核销 —— 冷却/限流/日额度全部从库里数

verify 只收 challenge_id 不收手机号:收手机号的话任何人可以拿别人的号打满
失败次数,零成本远程锁死任意用户的登录,而受害者手机上一条短信都不会响。

冷却的键是**手机号**,跨 purpose:purpose 是不鉴权端点的请求体字段、调用方全控,
算进键里的话同一个号同一分钟能收 3 条,直接踩穿运营商'同号 1 条/分钟'的流控 ——
用户拿到的是我们解释不了的运营商侧失败。判据落在 SQL 里(delivered_ok.is_(True)),
不是取最新一行再看它成没成功:那样只要最新那行失败,5 秒前那条成功的就被跳过。

日额度的分母是**已提交**不是已送达(阿里按提交计费、回执失败照收),但两种失败要分开:
超时/连不上占额度(不知道收没收,保守),明确拒收不占(确定未计费) —— 算进去的话,
格式合法但必被拒的号要多少有多少,几个 IP 就能免费把国际通道打满一整天。

时间比较一律走 _as_utc 守卫:无守卫的 .replace(tzinfo=utc) 只在 SQLite(读回 naive)
上是对的,PG 读回带会话时区偏移的 aware 值,抹掉偏移会让 elapsed 变负 ⇒
每个用户第一次取码就被判冷却,而单测一条都不红。

十条防线各配一次变异验证。额度的原子性只到单进程为止(count 与 insert 之间无锁),
改 workers 前必须先换成 quota.try_consume 那种条件 UPDATE —— 已写进模块 docstring。"
```

---

### Task 7: `POST /auth/phone/send-code` + 给 `/auth/register` 补真 per-IP 限流

**Files:**
- Create: `tests/web_ui/test_phone_endpoints.py`
- Modify: `katrain/web/core/models_db.py`（`users` 加 `signup_ip` 一列）
- Modify: `katrain/web/core/auth.py`（`create_user` 收 `signup_ip`）
- Modify: `katrain/web/api/v1/endpoints/auth.py`（新端点 + `_guard_phone_endpoint` + register 限流）
- Modify: `katrain/web/models.py`（`SendCodeRequest`）
- Modify: `tests/web_ui/conftest.py`（本轨道所有 HTTP 用例共用的夹具，Task 8/9/10 都从这里取）

**Interfaces:**
- Consumes:
  - `sms_challenge.issue(db, phone_e164: str, purpose: str, client_ip: str) -> str`（T6，async）
  - `sms_challenge.RateLimited`（`.code: str`、`.retry_after_sec: int | None`）（T6）
  - `sms.SmsProviderError` 及其两个子类 `sms.SmsRejected` / `sms.SmsUnreachable`（T5，接口契约）
  - `client_ip_for_ratelimit(request: Request) -> str`（T2）
  - `normalize_e164(raw: str, default_region_cc: str = "86") -> str`（T1，失败抛 `ValueError`）
  - **`settings.REGISTER_IP_DAILY: int = 10`（跨 Task 依赖：由 Task 5 在 `config.py` 的
    `Settings` 类体与 `__init__` 的 `data.setdefault(...)` **两处**声明，与 `SMS_*`、
    `TRUSTED_PROXY_HOPS` 同一段）。** 本 Task 只读它，不在这里加字段、`git add` 也不含
    `config.py`。Step 3 第 0 步有一条前置校验命令，没过就回 Task 5 补，别在这里补。
- Produces:
  - `POST /api/v1/auth/phone/send-code` → `200 {"challenge_id": str, "cooldown_sec": int}`
  - `endpoints/auth.py :: _guard_phone_endpoint(request: Request) -> None`（Task 8/9/10 三个端点共用，
    加上本 Task 自己的 send-code 端点，四个手机端点共用同一道盒子闸，见 3255 行）
  - `endpoints/auth.py :: VALID_PURPOSES = {"login", "bind", "set_password"}`
  - `models_db.User.signup_ip`（`String(64)`、`nullable=True`；**不进 `_to_dict`**）
  - `UserRepository.create_user(username, hashed_password, signup_ip: Optional[str] = None)`
  - **`tests/web_ui/conftest.py` 里的夹具，Task 8/9/10 直接用，不许各自再发明一份**：
    `sms_outbox`（记码的 provider 替身，`.last_code`、`.fail_with`）、`phone_app`、
    `phone_db`、`phone_client`、`phone_auth_client`、`phone_board_app`、`phone_board_client`、
    `remote_spy`、`phone_strict_client`、`send_code`（async callable）

**这是全站第一个"不鉴权还花钱"的端点**（spec §2.3）：每一条防线都要有一条会红的用例。

- [ ] **Step 1: 写失败的测试**

先把夹具写进 `tests/web_ui/conftest.py`（**追加在文件末尾**；该文件现在只有 kivy 打桩，
没有 `import pytest`，所以下面第一行要带上）。所有第三方与本仓 import 都放在函数体内 ——
这个 conftest 在 `tests/web_ui/` 下每一次收集都会被 import，放模块顶层等于给全目录
90 多个文件强加一次 `katrain.web.server` 的导入。

```python
# ── 追加到 tests/web_ui/conftest.py 末尾 ────────────────────────────────
# P3 手机绑定/验证码登录（superpowers/tracks/phone-login）共用夹具。
# Task 7/8/9/10 的 HTTP 用例全部从这里取，不要在各自的测试文件里再造一份。
import pytest


class SmsOutbox(list):
    """发出去的码。**必须打这个桩**：`sms.get_provider()` 在默认配置
    （`SMS_PROVIDER=""`）下直接抛 `SmsProviderError`，不打桩的话每一次
    send-code 都走 502 分支，断言 200/429 的用例一条也不可能绿。
    """

    fail_with = None          # 置上一个异常实例，下一次 send 就抛它

    @property
    def last_code(self) -> str:
        assert self, "还没有发出过任何一条码"
        return self[-1]["code"]


@pytest.fixture
def sms_outbox(monkeypatch):
    from katrain.web.core import sms as sms_module

    box = SmsOutbox()

    class _RecordingProvider(sms_module.SmsProvider):
        async def send(self, phone_e164, code, is_intl):
            if box.fail_with is not None:
                raise box.fail_with
            box.append({"phone": phone_e164, "code": code, "is_intl": is_intl})

    monkeypatch.setattr(sms_module, "get_provider", lambda: _RecordingProvider())
    return box


@pytest.fixture
def phone_app(tmp_path, monkeypatch, sms_outbox):
    """server 模式 + 独立 SQLite。照 tests/web_ui/test_billing_api.py:22 那个形状。

    用 httpx.ASGITransport 驱动（见 phone_client）⇒ **不跑 lifespan**，
    所以 `_lifespan_server` 不会覆盖 app.state.user_repo，也不会有
    `app.state.remote_client`（server 模式本来就该没有）。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from katrain.web.core import models_db
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.config import settings
    from katrain.web.core.db import get_db
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'phone.db'}", connect_args={"check_same_thread": False}
    )
    models_db.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = create_app(enable_engine=False)
    app.state.user_repo = SQLAlchemyUserRepository(SessionLocal)

    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.state.phone_test_session_factory = SessionLocal
    yield app
    engine.dispose()


@pytest.fixture
def phone_db(phone_app):
    """用例直接查库用的 session —— 与端点走的是**同一个 engine**。"""
    session = phone_app.state.phone_test_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
async def phone_client(phone_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=phone_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def phone_auth_client(phone_app):
    """已登录的普通账号 alice / oldpw123456，**没有绑手机号**。"""
    from httpx import ASGITransport, AsyncClient

    from katrain.web.core.auth import get_password_hash

    phone_app.state.user_repo.create_user(
        username="alice", hashed_password=get_password_hash("oldpw123456")
    )
    async with AsyncClient(transport=ASGITransport(app=phone_app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/auth/login", json={"username": "alice", "password": "oldpw123456"})
        assert r.status_code == 200, r.text
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield ac


@pytest.fixture
def phone_board_app(phone_app, monkeypatch):
    """非 strict 的盒子：有 remote_client，KATRAIN_BOX_SSO 关。"""
    from unittest.mock import AsyncMock, MagicMock

    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    remote = MagicMock()
    remote.register = AsyncMock(return_value={"id": 1, "username": "u0"})
    phone_app.state.remote_client = remote
    return phone_app


@pytest.fixture
def remote_spy(phone_board_app):
    return phone_board_app.state.remote_client


@pytest.fixture
async def phone_board_client(phone_board_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=phone_board_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def phone_strict_client(phone_app, monkeypatch):
    """strict 盒子：strict_box_sso_enabled() == True（mode=board 且 KATRAIN_BOX_SSO=1）。"""
    from httpx import ASGITransport, AsyncClient

    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    async with AsyncClient(transport=ASGITransport(app=phone_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def send_code():
    """发一条码并返回 challenge_id。**Task 8/9/10 用的就是这一个**
    （旧计划里那个没有定义体的 `_send_and_get_cid` 已作废）。"""

    async def _send(client, phone: str, purpose: str, **kwargs) -> str:
        r = await client.post(
            "/api/v1/auth/phone/send-code", json={"phone": phone, "purpose": purpose}, **kwargs
        )
        assert r.status_code == 200, r.text
        return r.json()["challenge_id"]

    return _send
```

再写测试文件：

```python
# tests/web_ui/test_phone_endpoints.py
"""P3：send-code / phone-login / bind 三个手机端点。夹具全部来自 tests/web_ui/conftest.py。"""

SEND = "/api/v1/auth/phone/send-code"
REGISTER = "/api/v1/auth/register"


async def test_send_code_needs_no_authentication(phone_client):
    """注册/找回密码时用户手上还没有 token —— 这个端点必须不鉴权。"""
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 200, r.text


async def test_send_code_rejects_a_malformed_phone(phone_client):
    r = await phone_client.post(SEND, json={"phone": "abc", "purpose": "login"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "bad_phone"


async def test_send_code_rejects_an_unknown_purpose(phone_client):
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "steal"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "bad_purpose"


async def test_send_code_second_call_for_the_same_phone_is_429_not_200(phone_client):
    """spec §3.1：任何一种超限都不许返 200。"""
    first = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert first.status_code == 200, first.text
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "sms_cooldown"
    assert r.json()["detail"]["retry_after_sec"] > 0
    assert r.headers["Retry-After"] == str(r.json()["detail"]["retry_after_sec"])


async def test_send_code_response_is_identical_whether_or_not_the_phone_has_an_account(
    phone_client, phone_app, phone_db, monkeypatch
):
    """**同一个手机号**，一次在"没绑过任何账号"的状态、一次在"已绑账号"的状态，
    响应必须一模一样 —— 否则这个不鉴权端点就是账号枚举器。

    旧版这条用例有两个洞：`set(a.json()) == set(b.json())` 只比键（多一个
    `registered` 布尔照样绿），而且两次调用换了手机号 ⇒ 唯一该被控住的变量没控住。
    """
    from katrain.web.core import models_db
    from katrain.web.core.auth import get_password_hash
    from katrain.web.core.config import settings

    # 冷却不是这条要测的东西，而同一个号连打两次必然撞上它 ⇒ 关掉，好让变量只剩"绑没绑"。
    monkeypatch.setattr(settings, "SMS_COOLDOWN_SEC", 0)
    phone = "13800138000"

    a = await phone_client.post(SEND, json={"phone": phone, "purpose": "login"})

    phone_app.state.user_repo.create_user(
        username="owner", hashed_password=get_password_hash("pw123456")
    )
    u = phone_db.query(models_db.User).filter_by(username="owner").one()
    u.phone_e164 = "+86" + phone
    phone_db.commit()

    b = await phone_client.post(SEND, json={"phone": phone, "purpose": "login"})

    assert a.status_code == b.status_code == 200, (a.text, b.text)
    # 键集**恒定且穷尽**：多出任何一个字段（registered / exists / user_id …）这里当场红
    assert set(a.json()) == set(b.json()) == {"challenge_id", "cooldown_sec"}
    # 值也必须一样。challenge_id 是随机串，当然不同 —— 单独断言它不同，
    # 免得有人把它改成"手机号的哈希"这种同样会泄露的东西。
    assert {k: v for k, v in a.json().items() if k != "challenge_id"} == {
        k: v for k, v in b.json().items() if k != "challenge_id"
    }
    assert a.json()["challenge_id"] != b.json()["challenge_id"]


async def test_send_code_response_never_carries_the_code(phone_client, sms_outbox):
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 200, r.text
    code = sms_outbox.last_code
    assert len(code) == 6 and code.isdigit()
    assert code not in r.text


async def test_provider_failure_is_502_not_200(phone_client, sms_outbox):
    from katrain.web.core import sms

    sms_outbox.fail_with = sms.SmsUnreachable("供应商超时")
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "sms_provider_failed"


async def test_daily_capacity_exhausted_is_503_not_429(phone_client, monkeypatch):
    """日总量打满是**服务端自己容量到顶**，跟这个用户快不快无关。
    给一个今天一条码都没取过的人返 429，是在撒谎说这是他的错。"""
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "SMS_DAILY_CAP_CN", 0)
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["code"] == "sms_capacity"
    # 字段恒在（没有理由时为 None），不要"有理由才有字段"
    assert "retry_after_sec" in detail and detail["retry_after_sec"] is None


async def test_send_code_records_the_forwarded_client_ip_not_the_peer(phone_client, phone_db):
    """**端点交给限流器的必须是 client_ip_for_ratelimit(request)，不是 request.client.host。**

    Task 2 只证明那个函数本身对，Task 6 只证明 issue() 按传进来的值分桶 ——
    端点写成 `ip = request.client.host` 的话那两套仍然全绿，而那正是 F10 那个缺陷本身。
    这条断言看的是**落到 challenge 行上的那个值**：ASGITransport 的对端恒为
    127.0.0.1，所以拿错值时这里会是两个 "127.0.0.1"。
    """
    from katrain.web.core import models_db

    await phone_client.post(
        SEND, json={"phone": "13800138001", "purpose": "login"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    await phone_client.post(
        SEND, json={"phone": "13800138002", "purpose": "login"},
        headers={"X-Forwarded-For": "198.51.100.7"},
    )

    ips = [
        row.client_ip
        for row in phone_db.query(models_db.SmsChallenge)
        .order_by(models_db.SmsChallenge.id)
        .all()
    ]
    assert ips == ["203.0.113.9", "198.51.100.7"]


async def test_the_ip_daily_cap_is_per_client_ip(phone_client, monkeypatch):
    """行为侧的同一条：换一个客户端 IP 必须重新有配额。
    只断言"限流会拦"的用例在"全站一个桶"的世界里也是绿的。"""
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "SMS_IP_DAILY", 1)
    a = {"X-Forwarded-For": "203.0.113.9"}
    b = {"X-Forwarded-For": "198.51.100.7"}

    r1 = await phone_client.post(SEND, json={"phone": "13800138001", "purpose": "login"}, headers=a)
    assert r1.status_code == 200, r1.text
    r2 = await phone_client.post(SEND, json={"phone": "13800138002", "purpose": "login"}, headers=a)
    assert r2.status_code == 429 and r2.json()["detail"]["code"] == "sms_quota_ip"
    r3 = await phone_client.post(SEND, json={"phone": "13800138003", "purpose": "login"}, headers=b)
    assert r3.status_code == 200, "换了客户端 IP 还被拦 ⇒ 全站一个桶"


# ---- 盒子四答（spec §2.6 / F6：四个端点每一个都要显式回答，一个都不能漏） ----
async def test_send_code_403_on_strict_box(phone_strict_client):
    r = await phone_strict_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 403


async def test_send_code_503_on_board_and_does_not_forward(phone_board_client, remote_spy):
    r = await phone_board_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    # remote_spy 是 MagicMock：`assert_not_called()` 只管它**自己**没被调用，
    # 管不住 `remote_client.send_phone_code(...)` 这种子调用。mock_calls 管得住。
    assert remote_spy.mock_calls == []


# ---- 顺带补的已知缺口：/auth/register 至今零限流 ----
def test_signup_ip_column_migrates_onto_an_existing_users_table(tmp_path):
    """`users` 加列走的是 add_missing_columns 那条零手写 DDL 的路（F1/F2）。
    只测 create_all 证明不了生产上会不会加列。"""
    from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect

    from katrain.web.core import migrations

    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    md = MetaData()
    Table(
        "users",
        md,
        Column("id", Integer, primary_key=True),
        Column("username", String, unique=True),
        Column("hashed_password", String),
    )
    md.create_all(eng)

    migrations.add_missing_columns(eng)

    assert "signup_ip" in {c["name"] for c in inspect(eng).get_columns("users")}
    eng.dispose()


async def test_register_records_the_forwarded_ip_and_keeps_it_out_of_the_user_dict(
    phone_client, phone_app, phone_db
):
    """记的是可信 IP，而且**不进 `_to_dict`** —— `_to_dict` 是显式白名单
    （core/auth.py:323），进去了就会随 `User` 漏进 /auth/me、/users/online、
    /api/v1/social 每一个回 User 的响应。"""
    from katrain.web.core import models_db

    r = await phone_client.post(
        REGISTER, json={"username": "a0", "password": "pw123456"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert r.status_code == 200, r.text
    assert phone_db.query(models_db.User).filter_by(username="a0").one().signup_ip == "203.0.113.9"
    assert "signup_ip" not in phone_app.state.user_repo.get_user_by_username("a0")
    assert "signup_ip" not in r.json()


async def test_register_is_rate_limited_per_client_ip(phone_client, monkeypatch):
    """per-IP，不是全站每日上限：后者是一个任何匿名脚本几秒就能扳下的
    "今天全站关闭注册"开关，且没有绕过口。最后一句才是这条用例存在的理由。"""
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "REGISTER_IP_DAILY", 2)
    a = {"X-Forwarded-For": "203.0.113.9"}
    b = {"X-Forwarded-For": "198.51.100.7"}

    for i in range(2):
        r = await phone_client.post(
            REGISTER, json={"username": f"a{i}", "password": "pw123456"}, headers=a
        )
        assert r.status_code == 200, r.text

    blocked = await phone_client.post(
        REGISTER, json={"username": "a9", "password": "pw123456"}, headers=a
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "register_ip_daily"

    other_ip = await phone_client.post(
        REGISTER, json={"username": "b0", "password": "pw123456"}, headers=b
    )
    assert other_ip.status_code == 200, "换了 IP 还被拦 ⇒ 这是全站闸不是 per-IP 闸"


async def test_register_on_a_board_is_forwarded_without_touching_the_local_cap(
    phone_board_client, remote_spy, monkeypatch
):
    """盒子上的注册原样转发给云端。限流挂在**转发分支之后**，
    否则盒子会先在本地库上数一遍，凭空多一个故障面（D-U3「盒子什么都不改」）。
    REGISTER_IP_DAILY=0 ⇒ 本地闸只要跑到就必然 429，所以这条 200 是硬证据。"""
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "REGISTER_IP_DAILY", 0)
    r = await phone_board_client.post(
        REGISTER, json={"username": "u0", "password": "pw123456"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert r.status_code == 200, r.text
    assert remote_spy.register.await_count == 1
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q`

Expected: FAIL —— `16 failed`。三种红因，逐条对得上：
- 12 条 send-code 用例：路由不存在 ⇒ `assert 404 == 200`（或 `KeyError: 'detail'`）。
- `test_signup_ip_column_migrates_onto_an_existing_users_table`：
  `AssertionError`（`signup_ip` 不在列集合里，模型上还没有这一列）。
- `test_register_records_the_forwarded_ip_and_keeps_it_out_of_the_user_dict`：
  `AttributeError: 'User' object has no attribute 'signup_ip'`。
- `test_register_is_rate_limited_per_client_ip` / `..._on_a_board_is_forwarded_...`：
  `ValueError: "Settings" object has no field "REGISTER_IP_DAILY"` —— 若 Task 5 已按
  Interfaces 声明了该字段，则改为 `assert 200 == 429`（限流还没挂上）。

- [ ] **Step 3: 写最小实现**

**Step 3.0 —— 两条前置校验，先跑再写代码：**

第一条校 Task 5 的产出，第二条校 **Task 6** 的产出（不是本 Task 自己改过名之后的自检 ——
本 Task 从不改 `sms_challenge.py`，这条 grep 只是确认「要调用的那个公开名真的已经在那儿」）：

```bash
grep -n "REGISTER_IP_DAILY" katrain/web/core/config.py     # 必须 2 处命中（Settings 字段 + __init__ 装配）
grep -c "today_start" katrain/web/core/sms_challenge.py   # 应为 3；_today_start 应为 0
```

第一条不到 2 处 ⇒ 回 Task 5 补上并由 **Task 5 的提交**带上 `config.py`；本 Task 不动 config.py。
第二条：Task 6 落的**已经是公开名** `today_start`，`_today_start` 零命中。
⚠️ **数字在 2026-09-10 修正为 3**：写计划时算的是「1 处定义 + `issue()` 里 1 处调用」，
漏了模块 docstring 里那句「见 `today_start()`」。照原来的 2 跑会把一个完好的 Task 6
误判成没做完 —— 判据（公开名在、私有名不在）本身是对的，错的只是那个计数。
**本 Task 不改名，只调用** —— 跨模块不拿私有名是接口契约的口径。

**① `katrain/web/core/models_db.py`** —— `User` 类里 `avatar_url` 之后加一列：

```python
    # 注册来源 IP（per-IP 注册限流的键）。**不进 `_to_dict`** —— 那是显式白名单，
    # 进去了就会随 `User` 漏进 /auth/me、/users/online、/api/v1/social。
    # nullable 且无 scalar default ⇒ migrations._default_clause 返 None，
    # 拼出 `ALTER TABLE "users" ADD COLUMN "signup_ip" VARCHAR(64)`，两个方言都过。
    signup_ip = Column(String(64), nullable=True)
```

**② `katrain/web/core/auth.py`** —— `UserRepository`（ABC）与 `SQLAlchemyUserRepository`
的 `create_user` 各加一个**带默认值的关键字参数**（`grep -rn 'create_user(' katrain tests`
列出的其余约 40 个调用点因此一行都不用改）：

```python
    # UserRepository(ABC) :: create_user
    @abstractmethod
    def create_user(
        self, username: str, hashed_password: str, signup_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        pass

    # SQLAlchemyUserRepository :: create_user —— 只改签名和构造行两处
    def create_user(
        self, username: str, hashed_password: str, signup_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            db_user = models_db.User(
                username=username, hashed_password=hashed_password, signup_ip=signup_ip
            )
            ...
```

`_to_dict`（`core/auth.py:323`）**不动**。

**③ `katrain/web/core/sms_challenge.py`** —— **不动**。`today_start` 由 Task 6 产出，本 Task 只 import 调用。

**④ `katrain/web/models.py`** —— 加请求体：

```python
class SendCodeRequest(BaseModel):
    phone: str
    purpose: str            # login | bind | set_password
```

**⑤ `katrain/web/api/v1/endpoints/auth.py`** —— 顶部 import 段（现在只有 logging / typing /
httpx / fastapi / jose / pydantic / core.auth 三个符号 / core.box_sso / config / db.get_db /
models.User,UserInDB / sqlalchemy.orm.Session）补四行：

```python
from sqlalchemy import func

from katrain.web.core import models_db, sms, sms_challenge
from katrain.web.core.client_ip import client_ip_for_ratelimit
from katrain.web.core.phone import normalize_e164
```

`models.py` 那一行改成 `from katrain.web.models import SendCodeRequest, User, UserInDB`。

新端点（`_guard_phone_endpoint` 是 Task 8/9/10 共用的，加上本 Task 自己的 send-code，
四个手机端点共用，写在 `router` 定义之后）：

```python
VALID_PURPOSES = {"login", "bind", "set_password"}


def _guard_phone_endpoint(request: Request) -> None:
    """四个手机端点共用的盒子闸（spec §2.6）。

    strict 盒子：云端账号体系的事，盒子上没有入口 ⇒ 403，与 /login /register 同形。
    board 非 strict：**不转发**。remote_client 是逐方法手写的，加转发方法等于给盒子
    多开几个故障面；而盒子是共用触摸设备，在上面输手机号收码是最差的绑定场景。
    """
    if strict_box_sso_enabled():
        raise HTTPException(status_code=403, detail={"code": "phone_disabled_on_device",
                                       "message": "请在 modelstella.com 上完成手机号相关操作"})
    if getattr(request.app.state, "remote_client", None) is not None:
        raise HTTPException(
            status_code=503,
            detail={"code": "need_online_phone",
                    "message": "请在 modelstella.com 登录后绑定手机号"},
        )


@router.post("/phone/send-code")
async def send_phone_code(request: Request, body: SendCodeRequest, db: Session = Depends(get_db)):
    _guard_phone_endpoint(request)
    if body.purpose not in VALID_PURPOSES:
        raise HTTPException(status_code=400, detail={"code": "bad_purpose"})
    try:
        phone = normalize_e164(body.phone)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_phone"})

    # **不要用 request.client.host**（F10：生产上它对所有用户恒为 172.20.0.1）。
    ip = client_ip_for_ratelimit(request)
    try:
        cid = await sms_challenge.issue(db, phone, body.purpose, ip)
    except sms_challenge.RateLimited as e:
        # 字段恒在（没有理由时为 None），不要"有理由才有字段" ——
        # 后者逼前端写 `'retry_after_sec' in x` 而不是 `x.retry_after_sec`。
        detail = {"code": e.code, "retry_after_sec": e.retry_after_sec}
        headers = {}
        if e.retry_after_sec is not None:
            headers["Retry-After"] = str(e.retry_after_sec)
        # **日总量打满是 503 不是 429**：那是服务端自己容量到顶，跟这个用户快不快无关。
        raise HTTPException(
            status_code=503 if e.code == "sms_capacity" else 429,
            detail=detail, headers=headers or None,
        )
    except sms.SmsProviderError:
        # **502 而不是 503，是刻意与上面那条区分开的。** 日额度打满要等到明天（我们自己的闸），
        # 供应商抖动几秒后就该重试。合成一个码，前端只能给一句含糊的"稍后再试"。
        raise HTTPException(status_code=502, detail={"code": "sms_provider_failed"})

    # **响应对"这个号有没有账号"必须一模一样** —— 多一个字段这里就是账号枚举器。
    return {"challenge_id": cid, "cooldown_sec": settings.SMS_COOLDOWN_SEC}
```

**⑥ 给 `/auth/register` 挂真 per-IP 限流** —— 插在 `# Server mode: local registration`
（`endpoints/auth.py:347`）之后、`repo.create_user(...)` 之前：

```python
    # Server mode: local registration
    from katrain.web.core.auth import get_password_hash

    # /auth/register 至今零限流。P3 建了 per-IP 限流器就给它用上。
    # **位置在 remote_client 转发分支之后**：盒子上的注册原样转发给云端，
    # 不许先在本地库上数一遍 —— 那是给盒子凭空多开一个故障面（D-U3）。
    # 日界与短信额度共用 sms_challenge.today_start()（东八区零点换算成 UTC）；
    # SQLite 的 CURRENT_TIMESTAMP 与 PG 的 now() 存的都是 UTC，两边比的都是 UTC。
    ip = client_ip_for_ratelimit(request)
    signups_today = (
        db.query(func.count(models_db.User.id))
        .filter(
            models_db.User.signup_ip == ip,
            models_db.User.created_at >= sms_challenge.today_start(),
        )
        .scalar()
    )
    if signups_today >= settings.REGISTER_IP_DAILY:
        raise HTTPException(status_code=429, detail={"code": "register_ip_daily"})

    repo = request.app.state.user_repo
    try:
        user_dict = repo.create_user(
            username=register_data.username,
            hashed_password=get_password_hash(register_data.password),
            signup_ip=ip,
        )
        ...
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q`
Expected: PASS（16 条）

再跑一次上游三个 Task 的文件，确认改名与签名改动没有把它们打红：

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_challenge.py tests/web_ui/test_client_ip.py tests/web_ui/test_auth_api.py tests/web_ui/test_board_auth.py tests/web_ui/test_billing_api.py -q`
Expected: PASS（全部）

- [ ] **Step 5: 变异验证**

逐条改坏、确认对应用例**当场变红**，再改回来（每一行都改回去之后重跑一次 Step 4）：

| 改坏什么 | 应该红的用例 |
|---|---|
| `send_phone_code` 里 `ip = client_ip_for_ratelimit(request)` 改成 `ip = request.client.host` | `test_send_code_records_the_forwarded_client_ip_not_the_peer`、`test_the_ip_daily_cap_is_per_client_ip` |
| 返回行改成 `{"challenge_id": cid, "cooldown_sec": settings.SMS_COOLDOWN_SEC, "registered": False}` | `test_send_code_response_is_identical_whether_or_not_the_phone_has_an_account`（键集那一句） |
| 注释掉 `_guard_phone_endpoint(request)` | `test_send_code_403_on_strict_box`、`test_send_code_503_on_board_and_does_not_forward` |
| 把 register 那段限流从 `# Server mode: local registration` 之后挪到 `strict_box_sso_enabled()` 检查之后 | `test_register_on_a_board_is_forwarded_without_touching_the_local_cap` |
| 限流查询去掉 `models_db.User.signup_ip == ip` 这一条 filter（退成全站每日上限） | `test_register_is_rate_limited_per_client_ip` 的最后一句 |
| `create_user(..., signup_ip=ip)` 改回 `create_user(...)`（不传） | `test_register_records_the_forwarded_ip_and_keeps_it_out_of_the_user_dict` |

- [ ] **Step 6: 提交**

```bash
# F12：跑 pytest 会改掉这个 kiosk fixture，提交前先还原，免得它混进来
git checkout -- katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json 2>/dev/null || true
git status --porcelain
git add katrain/web/core/models_db.py katrain/web/core/auth.py \
        katrain/web/api/v1/endpoints/auth.py katrain/web/models.py \
        tests/web_ui/conftest.py tests/web_ui/test_phone_endpoints.py
git commit -m "feat(auth): POST /auth/phone/send-code(不鉴权)+ /auth/register 补真 per-IP 限流

全站第一个'不鉴权还花钱'的端点,每条防线各一条会红的用例。
两条不显眼但要紧的:同一个手机号在'已绑/未绑'两种状态下的响应体与状态码必须
一模一样(键集写成穷尽的,多一个字段当场红),任何超限都不许返 200。

限流键用 client_ip_for_ratelimit,并有一条断言看**落到 challenge 行上的那个 IP**:
只测'限流会拦'的用例在 request.client.host 的世界里也是绿的(F10)。

/auth/register 改成真 per-IP:users 加 signup_ip 一列(走 add_missing_columns 那条
零手写 DDL 的路),不做全站每日上限 —— 后者是一个任何匿名脚本几秒就能扳下的
'今天全站关闭注册'开关且没有绕过口。限流挂在 remote_client 转发分支**之后**,
盒子上的注册一个字节不变。signup_ip 不进 _to_dict(白名单),所以不外泄。

盒子四答抽成 _guard_phone_endpoint,四个手机端点共用:strict 403、board 503
need_online 且**不转发**。"
```

---

---

### Task 8: `POST /auth/phone/login`（只登录，不注册）

**Files:**
- Modify: `katrain/web/core/auth.py`（`UserRepository.get_by_phone` + `_to_dict` 加 `phone_bound`）
- Modify: `katrain/web/models.py`（pydantic `User.phone_bound` + `PhoneLoginRequest`）
- Modify: `katrain/web/api/v1/endpoints/auth.py`（`POST /phone/login`）
- Modify: `tests/web_ui/conftest.py`（加 `bound_user` 夹具）
- Test: `tests/web_ui/test_phone_endpoints.py`（追加）

**Interfaces:**
- Consumes:
  - `sms_challenge.verify_and_consume(db, challenge_id, code, purpose) -> str`（T6，同步，返 `phone_e164`）
  - `sms_challenge.ChallengeInvalid`（`.code: str`）（T6）
  - `_guard_phone_endpoint(request)`、Task 7 在 `tests/web_ui/conftest.py` 落的全部夹具
    （`phone_app` / `phone_db` / `phone_client` / `phone_board_client` / `phone_strict_client` /
    `remote_spy` / `sms_outbox` / `send_code`）
- Produces:
  - `POST /api/v1/auth/phone/login` → `200 {"access_token": str, "token_type": "bearer"}`
  - `UserRepository.get_by_phone(phone_e164: str) -> Optional[Dict[str, Any]]`
    （ABC + `SQLAlchemyUserRepository` 两处；**取会话一律 `self.session_factory()`**）
  - `_to_dict` 多一行 `"phone_bound": user_obj.phone_e164 is not None`
  - pydantic `User.phone_bound: bool = False` —— **Task 11/12 的所有闸都读这一个**，
    不读 `phone_e164`、不用 `getattr` 兜底
  - `tests/web_ui/conftest.py :: bound_user` 夹具（Task 9/10 也用它）

**口径（接口契约"三条口径"第 2 条）：只加布尔 `phone_bound`，不把 `phone_e164` 加进
pydantic `User` 或 `_to_dict`。** 原始号只由 `repo.get_phone_e164(user_id)` 单点取
（Task 10 落）。灌原始号会让它随 `User` 泄进每一个回 `User` 的响应。

- [ ] **Step 1: 写失败的测试**

先给 `tests/web_ui/conftest.py` 追加一个夹具（接在 Task 7 那批后面）：

```python
@pytest.fixture
def bound_user(phone_app):
    """一个**已绑手机号**的账号。绑定直接写库 —— Task 9 才有 bind 端点，
    Task 8 不该依赖它。"""
    from katrain.web.core import models_db
    from katrain.web.core.auth import get_password_hash

    phone_app.state.user_repo.create_user(
        username="bound", hashed_password=get_password_hash("pw123456")
    )
    session = phone_app.state.phone_test_session_factory()
    try:
        u = session.query(models_db.User).filter_by(username="bound").one()
        u.phone_e164 = "+8613800138000"
        session.commit()
    finally:
        session.close()
    return {
        "username": "bound",
        "password": "pw123456",
        "phone": "13800138000",
        "phone_e164": "+8613800138000",
    }
```

再追加到 `tests/web_ui/test_phone_endpoints.py`：

```python
LOGIN = "/api/v1/auth/phone/login"
ME = "/api/v1/auth/me"


async def test_phone_login_issues_a_token_for_a_bound_user(
    phone_client, sms_outbox, send_code, bound_user
):
    cid = await send_code(phone_client, bound_user["phone"], "login")
    r = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": sms_outbox.last_code})
    assert r.status_code == 200, r.text
    assert r.json()["token_type"] == "bearer"

    me = await phone_client.get(
        ME, headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    )
    assert me.status_code == 200, me.text
    assert me.json()["username"] == bound_user["username"]   # JWT 的 sub 是 username（F4）
    # `phone_bound` 必须真的从库里长出来。pydantic 默认值是 False ⇒ `_to_dict` 漏了
    # 那一行、或 models.User 少了那个字段时，失败方向是**所有人都"没绑手机"**，
    # 而不是报错 —— Task 11/12 的闸会静默地对每个人关上。这一句就是盯它的。
    assert me.json()["phone_bound"] is True
    # 原始号不许随 User 外溢（接口契约口径 2）
    assert "phone_e164" not in me.json()
    assert bound_user["phone"] not in me.text


async def test_phone_login_on_an_unbound_phone_is_404_not_a_silent_signup(
    phone_client, phone_db, sms_outbox, send_code
):
    """本轮**不做**手机注册（见计划开头那节收窄说明）：注册仍需用户名，
    没有用户名就建不了号。未绑号必须给一条能走的路，不许静默建号。"""
    from katrain.web.core import models_db

    cid = await send_code(phone_client, "13900139000", "login")
    r = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": sms_outbox.last_code})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "phone_not_bound"
    # 没有静默建号：库里一个 user 行都不该多出来
    assert phone_db.query(models_db.User).count() == 0


async def test_phone_login_rejects_a_bind_purpose_challenge(
    phone_client, sms_outbox, send_code, bound_user
):
    """拿绑定用的码去登录 —— 必须拒。端点写死 purpose="login"。"""
    cid = await send_code(phone_client, bound_user["phone"], "bind")
    r = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": sms_outbox.last_code})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "challenge_purpose_mismatch"


async def test_phone_login_challenge_is_single_use(
    phone_client, sms_outbox, send_code, bound_user
):
    cid = await send_code(phone_client, bound_user["phone"], "login")
    code = sms_outbox.last_code
    first = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": code})
    assert first.status_code == 200, first.text
    second = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": code})
    assert second.status_code == 400
    assert second.json()["detail"]["code"] == "challenge_consumed"


def test_repo_get_by_phone_reports_phone_bound_and_keeps_the_raw_number_out(
    phone_app, bound_user
):
    """`_to_dict`（core/auth.py:323）是显式白名单，全仓只有这一个生产实现，
    加字段只此一处。两个方向都要钉住：绑了的必须 True（漏了那一行的表现是
    静默 False，不是报错），原始号必须**不在**里面（口径 2）。"""
    repo = phone_app.state.user_repo

    d = repo.get_by_phone(bound_user["phone_e164"])
    assert d is not None
    assert d["username"] == bound_user["username"]
    assert d["phone_bound"] is True
    assert "phone_e164" not in d

    # 端点真正读的是 get_user_by_username 那条路（get_user_from_token → User(**user_dict)），
    # 所以同一条断言在那条路上再钉一次。
    assert repo.get_user_by_username(bound_user["username"])["phone_bound"] is True
    assert repo.get_by_phone("+8613900139000") is None


async def test_me_reports_phone_bound_false_for_an_unbound_account(phone_auth_client):
    """诚实的默认方向：没绑就是 False，字段必须存在（不是缺席）。"""
    r = await phone_auth_client.get(ME)
    assert r.status_code == 200, r.text
    assert r.json()["phone_bound"] is False


async def test_phone_login_403_on_strict_box(phone_strict_client):
    r = await phone_strict_client.post(LOGIN, json={"challenge_id": "x", "code": "123456"})
    assert r.status_code == 403


async def test_phone_login_503_on_board_and_does_not_forward(phone_board_client, remote_spy):
    r = await phone_board_client.post(LOGIN, json={"challenge_id": "x", "code": "123456"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    assert remote_spy.mock_calls == []
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q`

Expected: FAIL —— `8 failed, 16 passed`（Task 7 的 16 条仍绿）。红因：
- 5 条打 `/api/v1/auth/phone/login` 的：路由不存在 ⇒ `assert 404 == 200` /
  `assert 404 == 400` / `assert 404 == 403` / `assert 404 == 503`。
- `test_repo_get_by_phone_reports_phone_bound_and_keeps_the_raw_number_out`：
  `AttributeError: 'SQLAlchemyUserRepository' object has no attribute 'get_by_phone'`。
- `test_me_reports_phone_bound_false_for_an_unbound_account`：`KeyError: 'phone_bound'`。
- `test_phone_login_issues_a_token_for_a_bound_user` 里 `/auth/me` 那句同样是
  `KeyError: 'phone_bound'`（这条本来就先在路由那一步红）。

- [ ] **Step 3: 写最小实现**

**① `katrain/web/core/auth.py`** —— `UserRepository`（ABC）加抽象方法，
`SQLAlchemyUserRepository`（**类名就是这个大小写，`core/auth.py:94`**）加实现。
**取会话一律 `self.session_factory()`；这个类上没有 `_session`**（全类 12 处都这么写，
见 `:112/:191/:210/:220`）：

```python
    # UserRepository(ABC)
    @abstractmethod
    def get_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        pass

    # SQLAlchemyUserRepository
    def get_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            user = (
                session.query(models_db.User)
                .filter(models_db.User.phone_e164 == phone_e164)
                .first()
            )
            return self._to_dict(user) if user else None
        finally:
            session.close()
```

`_to_dict`（`core/auth.py:323`）里 `"created_at"` 之后加一行 —— **只加这个布尔**：

```python
            # 发言闸/免费额度闸只需要"绑没绑"这一个布尔。原始号不进这里：
            # 它会随 pydantic `User` 泄进每一个回 User 的响应（models.py:189 的
            # `OnlineUser` 收窄注释正是为防这类外溢）。要原始号走 get_phone_e164()。
            "phone_bound": user_obj.phone_e164 is not None,
```

**② `katrain/web/models.py`** —— pydantic `User` 的 `created_at` 之后加一个字段，
并加请求体：

```python
    # 所有闸一律读这个布尔（Task 11 的免费额度、Task 12 的发言）。
    # 有默认值 ⇒ 属性必然存在 ⇒ 闸里直接 `current_user.phone_bound`，
    # 不用 getattr 兜底：getattr 会把"字段没加上"这个错误掩盖成"所有人都被拒"。
    phone_bound: bool = False


class PhoneLoginRequest(BaseModel):
    challenge_id: str
    code: str
```

`endpoints/auth.py` 顶部那行 import 补上：
`from katrain.web.models import PhoneLoginRequest, SendCodeRequest, User, UserInDB`。

**③ `katrain/web/api/v1/endpoints/auth.py`** —— 端点接在 `send_phone_code` 之后：

```python
@router.post("/phone/login")
async def phone_login(request: Request, body: PhoneLoginRequest, db: Session = Depends(get_db)):
    _guard_phone_endpoint(request)
    try:
        # purpose 写死 "login"：绑定用的码不能拿来登录。
        phone = sms_challenge.verify_and_consume(db, body.challenge_id, body.code, "login")
    except sms_challenge.ChallengeInvalid as e:
        raise HTTPException(status_code=400, detail={"code": e.code})

    user = request.app.state.user_repo.get_by_phone(phone)
    if user is None:
        # 本轮不做手机注册（见 plan 开头的收窄说明）。给一条能走的路，不静默建号。
        raise HTTPException(
            status_code=404,
            detail={"code": "phone_not_bound",
                    "message": "这个手机号还没有绑定账号。请先用用户名密码登录，再到设置里绑定。"},
        )
    return {
        "access_token": create_access_token(data={"sub": user["username"]}),
        "token_type": "bearer",
    }
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q`
Expected: PASS（24 条）

`_to_dict` 与 pydantic `User` 是全仓共用的，回归面要单独跑一遍：

Run: `./.venv/bin/python -m pytest tests/web_ui/test_auth_api.py tests/web_ui/test_social_api.py tests/web_ui/test_billing_api.py tests/web_ui/test_board_auth.py tests/web_ui/test_box_sso.py tests/web_ui/test_signup_grant.py tests/web_ui/test_account_subject_contract.py -q`
Expected: PASS（全部）

- [ ] **Step 5: 变异验证**

| 改坏什么 | 应该红的用例 |
|---|---|
| 删掉 `_to_dict` 里 `"phone_bound": ...` 那一行 | `test_repo_get_by_phone_reports_phone_bound_and_keeps_the_raw_number_out`（`KeyError`）、`test_phone_login_issues_a_token_for_a_bound_user`（`/auth/me` 那句变成 False） |
| 删掉 pydantic `User.phone_bound` 字段 | `test_phone_login_issues_a_token_for_a_bound_user`、`test_me_reports_phone_bound_false_for_an_unbound_account`（都 `KeyError: 'phone_bound'` —— pydantic v2 `extra='ignore'` 会把 `_to_dict` 里的值静默丢掉） |
| `_to_dict` 里改成 `"phone_e164": user_obj.phone_e164` | `test_repo_..._keeps_the_raw_number_out`、`test_phone_login_issues_a_token_for_a_bound_user`（`me.text` 那句） |
| `verify_and_consume(..., "login")` 的第 4 个实参改成 `"bind"` | `test_phone_login_issues_a_token_for_a_bound_user`、`test_phone_login_challenge_is_single_use`（证明这个字面量真的在被检查，不是摆设） |
| 删掉 `if user is None:` 那条 404 短路 | `test_phone_login_on_an_unbound_phone_is_404_not_a_silent_signup`（`user["username"]` 对 None 取下标 ⇒ 500） |
| 注释掉 `_guard_phone_endpoint(request)` | `test_phone_login_403_on_strict_box`、`test_phone_login_503_on_board_and_does_not_forward` |

- [ ] **Step 6: 提交**

```bash
git checkout -- katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json 2>/dev/null || true
git status --porcelain
git add katrain/web/core/auth.py katrain/web/api/v1/endpoints/auth.py katrain/web/models.py \
        tests/web_ui/conftest.py tests/web_ui/test_phone_endpoints.py
git commit -m "feat(auth): POST /auth/phone/login —— 只登录,未绑号返 404 给出路

本轮不做手机注册(D-U2 让注册契约保持不变 ⇒ 没有用户名就建不了号)。
未绑号返 404 phone_not_bound 并在 message 里给出可走的路,不静默建号,
并有一条断言证明库里没多出 user 行。

_to_dict 只加布尔 phone_bound,**不加 phone_e164**:后者会随 pydantic User
泄进每一个回 User 的响应(/auth/me、/users/online、/api/v1/social)。
原始号将由 repo.get_phone_e164(user_id) 单点取。
Task 11/12 的闸一律读 current_user.phone_bound,不用 getattr 兜底 ——
getattr 会把'字段没加上'掩盖成'所有人都被拒'。

pydantic 默认值 False 的失败方向是静默的(所有人都'没绑手机'),所以
/auth/me 的 phone_bound is True 和仓储那条各钉了一次,并配了变异记录。"
```

---

### Task 9: `POST /auth/phone/bind`（鉴权，**不做自助换绑**）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py`
- Modify: `katrain/web/core/auth.py`
- Test: `tests/web_ui/test_phone_bind.py`（新建，自带夹具，不依赖别的测试文件）

**Interfaces:**
- Consumes:
  - Task 1：`katrain.web.core.phone.mask_e164(e164: str) -> str`（`"+8613800138000"` → `"+86 138****8000"`）
  - Task 6：`sms_challenge.verify_and_consume(db, challenge_id: str, code: str, purpose: str) -> str`（返手机号；失败抛 `ChallengeInvalid(code: str)`）
  - Task 7：`_guard_phone_endpoint(request: Request) -> None`（`endpoints/auth.py` 模块级；strict 盒子 403、board 非 strict 503 `need_online_phone` 且不转发）、`POST /api/v1/auth/phone/send-code`
  - Task 8：`POST /api/v1/auth/phone/login`、`models.PhoneLoginRequest{challenge_id: str, code: str}`、`SQLAlchemyUserRepository.get_by_phone(phone_e164) -> Optional[Dict]`、`_to_dict` 里的 `"phone_bound"`、pydantic `User.phone_bound: bool = False`
- Produces:
  - `POST /api/v1/auth/phone/bind` → `200 {"phone_masked": str}`；`409 {"code": "phone_taken"}`；`409 {"code": "already_bound"}`
  - `UserRepository.bind_phone(user_id: int, phone_e164: str) -> str`，返回值恰好三种：`"ok"` / `"phone_taken"` / `"already_bound"`（接口契约的唯一真源）。Task 10 与 Task 11 都不调它，只有本端点调。

**为什么必须拒绝换绑**（这不是保守，是本轮两条论证的前提）：
计划里「一号一账号」的经济论证、以及 Task 11「未绑号在触碰 quota 之前短路」的正确性，
两处都明写以「不存在解绑路径」为前提。**换绑同时就是旧号的解绑**：
手上有 3 张卡时，`acct1` 绑 A 领一份免费复盘 → `acct1` 改绑 B（A 空出）→ `acct2` 绑 A 领第二份
→ `acct2` 改绑 C（A 再空出）……每轮释放一个号给新账号，免费复盘份数不受卡数限制。
合规侧同样破：用 A 号发言之后改绑 B，仓里没有 `retired_phones`（需求 §1.2 明确不做），
发言与实名主体的对应关系当场丢失。**所以「已绑号的账号再绑一个新号」返 409，不返 200。**

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_bind.py
"""绑定手机号。**已绑号的账号不许再绑第二个号** —— 那是一条自助换绑路径。

夹具形状照抄 tests/web_ui/test_billing_api.py:20-50：独立 sqlite +
`AsyncClient(ASGITransport(app))`。**刻意不用 TestClient**：它会跑 lifespan，
而 `_lifespan_server` 无条件用全局 `SessionLocal` 重建六个 repo 再覆盖
`app.state`（tests/conftest.py 顶部那段长注释记了完整链路）—— 注入在前、覆盖在后，
那样写下去的行会落进开发机真库并被 conftest 的写闸拦住。
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db

SEND = "/api/v1/auth/phone/send-code"
BIND = "/api/v1/auth/phone/bind"
PHONE_LOGIN = "/api/v1/auth/phone/login"


class _Capture:
    """记下发出去的码的假供应商。`ConsoleProvider` 只 print，测试读不到。"""

    def __init__(self):
        self.codes = []

    async def send(self, phone_e164, code, is_intl):
        self.codes.append(code)


@pytest.fixture
def sms(monkeypatch):
    from katrain.web.core import sms as sms_module

    cap = _Capture()
    monkeypatch.setattr(sms_module, "get_provider", lambda: cap)
    return cap


@pytest.fixture
def app(tmp_path, monkeypatch, sms):
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'phone_bind.db'}")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    application = create_app(enable_engine=False)
    application.state.session_factory = TestSessionLocal
    application.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = _override_get_db
    try:
        yield application
    finally:
        engine.dispose()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _make_user(app, username, password="pw123456", phone=None):
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    app.state.user_repo.create_user(username, CryptContext(schemes=["bcrypt"], deprecated="auto").hash(password))
    session = app.state.user_repo.session_factory()
    try:
        u = session.query(models_db.User).filter_by(username=username).one()
        if phone is not None:
            u.phone_e164 = phone
            session.commit()
        return u.id
    finally:
        session.close()


async def _auth(client, username, password="pw123456"):
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _cid(client, phone, purpose):
    r = await client.post(SEND, json={"phone": phone, "purpose": purpose})
    assert r.status_code == 200, r.text
    return r.json()["challenge_id"]


async def test_bind_requires_auth(client):
    r = await client.post(BIND, json={"challenge_id": "x", "code": "000000"})
    assert r.status_code == 401


async def test_bind_sets_phone_and_returns_masked(app, client, sms):
    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "bind")
    r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["phone_masked"] == "+86 138****8000"
    assert "13800138000" not in r.text, "原始号不许整串回给前端"
    me = await client.get("/api/v1/auth/me", headers=h)
    assert me.json()["phone_bound"] is True


async def test_bind_consumes_the_challenge_before_checking_uniqueness(app, client, sms):
    """**核销在前、查唯一性在后。** 反过来这个端点就是号码枚举器：
    任何登录用户可逐个探测「这个号有没有账号」。核销在前意味着
    你必须先控制这个号，才配知道它被占了。"""
    _make_user(app, "owner", phone="+8613800138000")
    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "bind")

    r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "phone_taken"

    r2 = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r2.status_code == 400
    assert r2.json()["detail"]["code"] == "challenge_consumed", "失败那次也必须把码核销掉"


async def test_bind_rejects_a_login_purpose_challenge(app, client, sms):
    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "login")
    r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "challenge_purpose_mismatch"


async def test_rebinding_a_different_number_is_refused(app, client, sms, monkeypatch):
    """已绑号的账号再绑一个新号 = **自助换绑**，必须拒。

    换绑就是旧号的解绑：3 张卡可以轮流释放号码给新账号，免费复盘份数不受卡数限制；
    而 Task 11 那条「未绑号不建桶」的短路，正确性也建在「没有解绑路径」上。
    """
    monkeypatch.setattr(settings, "SMS_COOLDOWN_SEC", 0)  # 一条用例里要给两个号各发两次码
    _make_user(app, "binder")
    h = await _auth(client, "binder")

    cid1 = await _cid(client, "13800138000", "bind")
    first = await client.post(BIND, json={"challenge_id": cid1, "code": sms.codes[-1]}, headers=h)
    assert first.status_code == 200, first.text

    cid2 = await _cid(client, "13900139000", "bind")
    r = await client.post(BIND, json={"challenge_id": cid2, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "already_bound"

    # 库里那一列一个字节都没动：旧号仍然登得进这个账号，新号仍然没有账号。
    # 断在这里而不是断 `phone_bound is True` —— 后者在换绑成功时也是 True，量不出东西。
    old = await _cid(client, "13800138000", "login")
    r_old = await client.post(PHONE_LOGIN, json={"challenge_id": old, "code": sms.codes[-1]})
    assert r_old.status_code == 200, r_old.text
    new = await _cid(client, "13900139000", "login")
    r_new = await client.post(PHONE_LOGIN, json={"challenge_id": new, "code": sms.codes[-1]})
    assert r_new.status_code == 404
    assert r_new.json()["detail"]["code"] == "phone_not_bound"


async def test_rebinding_the_same_number_is_idempotent(app, client, sms, monkeypatch):
    """同号重复绑定返 200 —— 刷新页面/网络重试不该看到一个红色的 409。"""
    monkeypatch.setattr(settings, "SMS_COOLDOWN_SEC", 0)
    _make_user(app, "binder")
    h = await _auth(client, "binder")

    cid1 = await _cid(client, "13800138000", "bind")
    assert (await client.post(BIND, json={"challenge_id": cid1, "code": sms.codes[-1]}, headers=h)).status_code == 200

    cid2 = await _cid(client, "13800138000", "bind")
    r = await client.post(BIND, json={"challenge_id": cid2, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["phone_masked"] == "+86 138****8000"


async def test_bind_is_unreachable_on_a_strict_box(app, client, sms, monkeypatch):
    """strict 盒子上这条路不通，而且**什么都没发生**。

    **注意断的是 401 不是 403。** strict 模式下 `resolve_http_token`
    只认 `sb_go_token` cookie、Bearer 头被忽略（core/box_sso.py:72-75），
    于是 `Depends(get_current_user)` 在函数体之前就把请求挡了，
    `_guard_phone_endpoint` 的 403 根本轮不到。把断言写成 403，
    断的是一件不会发生的事 —— 那条用例红了也说明不了任何问题。
    真正守住 `_guard_phone_endpoint` 被调用的是下一条（board 503）。
    """
    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "bind")

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 401

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    me = await client.get("/api/v1/auth/me", headers=h)
    assert me.json()["phone_bound"] is False, "盒子上那次请求不许留下任何绑定"


async def test_bind_503_on_board_and_does_not_forward(app, client, sms, monkeypatch):
    """非 strict 盒子：503 `need_online_phone`，**且一个远端方法都不调**。

    这一条是唯一守着 `_guard_phone_endpoint(request)` 真被调用的断言 ——
    把那行删掉，它当场变红。
    """
    from unittest.mock import MagicMock

    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "bind")

    remote = MagicMock()
    app.state.remote_client = remote
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    try:
        r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    finally:
        app.state.remote_client = None
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    assert remote.method_calls == [], "盒子上这条路不转发，一个远端方法都不许调"
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_bind.py -q`
Expected: FAIL — 8 failed。全部因为 `POST /api/v1/auth/phone/bind` 路由还不存在而拿到
`404 Not Found`（`test_bind_requires_auth` 期望 401、其余期望 200/409/400/401/503，一条都对不上）。

- [ ] **Step 3: 写最小实现**

`katrain/web/core/auth.py`：

1. 模块顶部第 3 行改成（**原来只有 `datetime, timedelta`，没有 `timezone`**）：

```python
from datetime import datetime, timedelta, timezone
```

2. `UserRepository(ABC)` 加抽象方法（放在 `get_user_by_id` 之后）：

```python
    @abstractmethod
    def bind_phone(self, user_id: int, phone_e164: str) -> str:
        """返回 "ok" | "phone_taken" | "already_bound"。三个字符串是契约，不许换。"""
```

3. `SQLAlchemyUserRepository` 加实现（注意：取会话一律 `self.session_factory()`，
   全类 12 处都这么写；**没有** `self._session()`。`IntegrityError` 在函数体内 import，
   与既有 `create_user`（core/auth.py:202）同形）：

```python
    def bind_phone(self, user_id: int, phone_e164: str) -> str:
        """绑号。

        三个返回值：
          "ok"            —— 绑上了（含「本来就绑着同一个号」这种幂等重试）
          "already_bound" —— 这个账号已经绑着**另一个**号。**不覆盖** ——
                             覆盖就是一条自助换绑路径，而换绑同时是旧号的解绑，
                             「一号一账号」的经济论证与 Task 11 那条短路都建在
                             「不存在解绑路径」上。
          "phone_taken"   —— 这个号被别人占了。靠唯一索引兜底，不靠「先查后写」
                             那条竞态（两个请求同时到达时先查后写都会判成没占）。
        """
        from sqlalchemy.exc import IntegrityError

        session = self.session_factory()
        try:
            u = session.query(models_db.User).filter_by(id=user_id).one()
            if u.phone_e164 is not None:
                return "ok" if u.phone_e164 == phone_e164 else "already_bound"
            u.phone_e164 = phone_e164
            u.phone_verified_at = datetime.now(timezone.utc)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return "phone_taken"
            return "ok"
        finally:
            session.close()
```

`katrain/web/api/v1/endpoints/auth.py`：

1. 导入行补 `mask_e164`（Task 7 已经引进了 `normalize_e164`）：

```python
from katrain.web.core.phone import normalize_e164, mask_e164
```

2. 端点：

```python
@router.post("/phone/bind")
async def bind_phone(
    request: Request,
    body: PhoneLoginRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """把手机号绑到当前账号上。**先核销验证码，再查号码归属。**

    反过来这个端点就是号码枚举器 —— 任何登录用户可逐个探测「这个号有没有账号」。
    核销在前意味着你必须先控制这个号，才配知道它被占了。
    """
    _guard_phone_endpoint(request)
    try:
        phone = sms_challenge.verify_and_consume(db, body.challenge_id, body.code, "bind")
    except sms_challenge.ChallengeInvalid as e:
        raise HTTPException(status_code=400, detail={"code": e.code})

    outcome = request.app.state.user_repo.bind_phone(current_user.id, phone)
    if outcome == "phone_taken":
        raise HTTPException(
            status_code=409,
            detail={"code": "phone_taken",
                    "message": "这个手机号已经有账号了。可以直接用验证码登录那个账号。"},
        )
    if outcome == "already_bound":
        # **不做自助换绑。** 换绑就是旧号的解绑，而「一号一账号」的经济论证与
        # Task 11 那条「未绑号不建桶」的短路都以「不存在解绑路径」为前提。
        raise HTTPException(
            status_code=409,
            detail={"code": "already_bound",
                    "message": "这个账号已经绑定了手机号。换绑请联系客服。"},
        )
    return {"phone_masked": mask_e164(phone)}
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_bind.py -q`
Expected: PASS（8 条）

- [ ] **Step 5: 变异验证**（三处，每处改完跑一次再改回来）

| 变异 | 命令 | 必须变红的用例 |
|---|---|---|
| 把 `bind_phone` 里 `if u.phone_e164 is not None:` 那两行删掉（回到无条件覆盖） | `pytest tests/web_ui/test_phone_bind.py -q` | `test_rebinding_a_different_number_is_refused` |
| 把端点里「先核销、再 `bind_phone`」两步对调（先 `bind_phone` 再 `verify_and_consume`） | 同上 | `test_bind_consumes_the_challenge_before_checking_uniqueness` |
| 注释掉端点第一行 `_guard_phone_endpoint(request)` | 同上 | `test_bind_503_on_board_and_does_not_forward` |

三次都确认红了，再逐一改回来，最后重跑一次 Step 4 确认 8 条全绿。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/api/v1/endpoints/auth.py \
        katrain/web/core/auth.py \
        tests/web_ui/test_phone_bind.py
git commit -m "feat(auth): POST /auth/phone/bind —— 先核销验证码再查归属，已绑号拒绝换绑

顺序是防线不是风格:反过来这个端点就是号码枚举器,任何登录用户可逐个探测
'这个号有没有账号'。核销在前意味着你必须先控制这个号,才配知道它被占了。

**不做自助换绑**:换绑同时就是旧号的解绑 —— 3 张卡可以轮流把号释放给新账号,
免费复盘份数不受卡数限制;发言与实名主体的对应关系也当场丢失(仓里没有
retired_phones,需求 §1.2 明确不做)。而'一号一账号'的经济论证与 Task 11
那条'未绑号不建桶'的短路,两处都以'不存在解绑路径'为前提。
已绑另一个号 -> 409 already_bound;同号重绑 -> 200 幂等。

仓储 bind_phone 返 'ok'|'phone_taken'|'already_bound'(接口契约);
号被占靠唯一索引兜底,不靠先查后写那条竞态。
strict 盒子那条用例断的是 401 不是 403 —— strict 模式下 Bearer 头被忽略,
get_current_user 在函数体之前就挡了,_guard_phone_endpoint 轮不到;
真正守着那道闸的是 board 503 那条。

配了三次变异验证:去掉换绑守卫 / 对调核销顺序 / 拿掉盒子闸,各自当场变红。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GGNBSL4QhRA2vCDcZL83oF"
```

---

---

### Task 10: `POST /auth/set-password`（U5）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py`
- Modify: `katrain/web/core/auth.py`
- Modify: `katrain/web/models.py`
- Test: `tests/web_ui/test_set_password.py`（新建，自带夹具）

**Interfaces:**
- Consumes：
  - Task 6：`sms_challenge.verify_and_consume(db, challenge_id, code, purpose) -> str`、`sms_challenge.ChallengeInvalid`
  - Task 7：`_guard_phone_endpoint(request) -> None`、`POST /api/v1/auth/phone/send-code`
  - Task 8：pydantic `User.phone_bound: bool = False`（`models.py`）
  - 既有：`katrain.web.core.auth.get_password_hash(password: str) -> str`（core/auth.py:19）
- Produces：
  - `POST /api/v1/auth/set-password` → `200 {"ok": True}`
  - `models.SetPasswordRequest{challenge_id: str, code: str, new_password: str}`
  - `UserRepository.set_password_hash(user_id: int, hashed: str) -> None`
  - `UserRepository.get_phone_e164(user_id: int) -> Optional[str]`
  - **给 Task 17 的文案（必须在成功页上说出来）**：
    `auth:set_password_other_devices` 默认值
    `'密码已经改好了。已经登录的设备不会被强制退出，最长 90 天内仍可继续使用。'`
    —— 见下面 `test_old_access_and_refresh_tokens_survive_the_password_change` 的理由。

**为什么做**（已核实）：全仓 `hashed_password` 唯一写入点是 `core/auth.py:194 create_user`，
没有任何改密码/重置端点，也没有邮箱列 ⇒ **今天一个用户忘了密码，这个系统里没有任何人能帮他。**
手机验证码登录只让他「进得来」；口令是**上盒子的唯一路**（kiosk 登录页只有用户名与密码两个控件），
所以还得有一个端点让他「把口令修好」，否则他会被永久挡在自己买的那台设备之外。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_set_password.py
"""改密码：要验证码、不要当前密码。

「忘了密码的人给不出当前密码」是个死结，验证码解开它；而且比只验当前密码更强 ——
会话被劫持的攻击者拿不到手机，改不了密码。

夹具形状与 tests/web_ui/test_phone_bind.py 一致（都照抄 test_billing_api.py:20-50）：
独立 sqlite + `AsyncClient(ASGITransport(app))`，不跑 lifespan。
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db

SEND = "/api/v1/auth/phone/send-code"
SET = "/api/v1/auth/set-password"


class _Capture:
    def __init__(self):
        self.codes = []

    async def send(self, phone_e164, code, is_intl):
        self.codes.append(code)


@pytest.fixture
def sms(monkeypatch):
    from katrain.web.core import sms as sms_module

    cap = _Capture()
    monkeypatch.setattr(sms_module, "get_provider", lambda: cap)
    return cap


@pytest.fixture
def app(tmp_path, monkeypatch, sms):
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'set_password.db'}")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    application = create_app(enable_engine=False)
    application.state.session_factory = TestSessionLocal
    application.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = _override_get_db
    try:
        yield application
    finally:
        engine.dispose()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _make_user(app, username, password="pw123456", phone=None):
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    app.state.user_repo.create_user(username, CryptContext(schemes=["bcrypt"], deprecated="auto").hash(password))
    session = app.state.user_repo.session_factory()
    try:
        u = session.query(models_db.User).filter_by(username=username).one()
        if phone is not None:
            u.phone_e164 = phone
            session.commit()
        return u.id
    finally:
        session.close()


async def _login(client, username, password):
    return await client.post("/api/v1/auth/login", json={"username": username, "password": password})


async def _auth(client, username, password="pw123456"):
    r = await _login(client, username, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _cid(client, phone, purpose):
    r = await client.post(SEND, json={"phone": phone, "purpose": purpose})
    assert r.status_code == 200, r.text
    return r.json()["challenge_id"]


async def test_set_password_requires_auth(client):
    r = await client.post(SET, json={"challenge_id": "x", "code": "000000", "new_password": "pw87654321"})
    assert r.status_code == 401


async def test_sets_password_and_the_old_one_stops_working(app, client, sms):
    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    h = await _auth(client, "pwuser", "oldpw123456")
    cid = await _cid(client, "13800138000", "set_password")

    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 200, r.text
    assert (await _login(client, "pwuser", "newpw123456")).status_code == 200
    assert (await _login(client, "pwuser", "oldpw123456")).status_code == 401


async def test_challenge_phone_must_match_the_current_users_phone(app, client, sms):
    """少了这一步，一个人可以拿**自己号上的码**去改**别人的**密码。

    这里的 challenge 是给受害者的号发的（现实里攻击者拿不到那个码；
    测试里假供应商看得见，所以能把这条防线单独量出来）。
    """
    _make_user(app, "victim", password="vpw123456", phone="+8613900139000")
    _make_user(app, "attacker", password="apw123456", phone="+8613800138000")
    h = await _auth(client, "attacker", "apw123456")
    cid = await _cid(client, "13900139000", "set_password")  # 受害者的号

    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "hax12345678"}, headers=h)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "challenge_phone_mismatch"
    assert (await _login(client, "victim", "vpw123456")).status_code == 200, "受害者的密码不许被改动"


async def test_unbound_user_gets_phone_unbound_not_a_generic_error(app, client, sms):
    _make_user(app, "nophone", password="pw123456")
    h = await _auth(client, "nophone")
    cid = await _cid(client, "13800138000", "set_password")
    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "phone_unbound"


async def test_rejects_a_login_purpose_challenge(app, client, sms):
    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    h = await _auth(client, "pwuser", "oldpw123456")
    cid = await _cid(client, "13800138000", "login")
    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "challenge_purpose_mismatch"


async def test_old_access_and_refresh_tokens_survive_the_password_change(app, client, sms):
    """**已知限制，不是缺陷 —— 但期限是 90 天，不是 7 天。**

    JWT 载荷只有 sub/exp/type，没有密码版本位；`/auth/refresh`
    （endpoints/auth.py:288-310）只验签名 + 用户名存在，**不看密码改没改**，
    而 `REFRESH_TOKEN_EXPIRE_DAYS = 90`（core/config.py:74）⇒ 手上有 refresh token
    的人在改密码之后还能**连续换发 90 天**，不是 access token 那 7 天
    （`ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*7`，config.py:73）。

    这条与用户直觉相反，而轨道上写着「状态必须诚实」⇒ 把 90 说成 7 是给用户
    一个错的安全承诺。所以：这里钉住现状，UI 上照 Produces 里那句文案说出来。
    """
    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    login = await _login(client, "pwuser", "oldpw123456")
    old_access = login.json()["access_token"]
    old_refresh = login.json()["refresh_token"]
    h = {"Authorization": f"Bearer {old_access}"}

    cid = await _cid(client, "13800138000", "set_password")
    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 200, r.text

    assert (await client.get("/api/v1/auth/me", headers=h)).status_code == 200, "旧 access token 仍然有效"
    again = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert again.status_code == 200, "旧 refresh token 仍能换发新 access token —— 这才是那 90 天"


async def test_set_password_is_unreachable_on_a_strict_box(app, client, sms, monkeypatch):
    """strict 盒子上这条路不通，而且**什么都没发生**。

    断的是 401 不是 403：strict 模式下 Bearer 头被忽略、只认 `sb_go_token` cookie
    （core/box_sso.py:72-75），`Depends(get_current_user)` 在函数体之前就挡了。
    守着 `_guard_phone_endpoint` 真被调用的是下一条（board 503）。
    """
    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    h = await _auth(client, "pwuser", "oldpw123456")
    cid = await _cid(client, "13800138000", "set_password")

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 401

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    assert (await _login(client, "pwuser", "oldpw123456")).status_code == 200, "盒子上那次请求不许改到密码"


async def test_set_password_503_on_board_and_does_not_forward(app, client, sms, monkeypatch):
    """非 strict 盒子：503 `need_online_phone`，**且一个远端方法都不调**。

    Task 7/8/9 三个端点各有这一条，Task 10 原来没有 ——
    于是代码里 `_guard_phone_endpoint(request)` 虽然调了，却没有任何断言守着它：
    哪天有人把它挪到 `verify_and_consume` 之后或删掉，全套仍绿。
    """
    from unittest.mock import MagicMock

    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    h = await _auth(client, "pwuser", "oldpw123456")
    cid = await _cid(client, "13800138000", "set_password")

    remote = MagicMock()
    app.state.remote_client = remote
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    try:
        r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    finally:
        app.state.remote_client = None
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    assert remote.method_calls == []
    assert (await _login(client, "pwuser", "oldpw123456")).status_code == 200, "被闸挡住时密码不许被改"
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_set_password.py -q`
Expected: FAIL — 8 failed。全部因为 `POST /api/v1/auth/set-password` 路由不存在而拿到 `404`。

- [ ] **Step 3: 写最小实现**

`katrain/web/models.py` 加请求体（放在 `PhoneLoginRequest` 旁边）：

```python
class SetPasswordRequest(BaseModel):
    challenge_id: str
    code: str
    new_password: str
    # **本轮不加最短长度校验**：`/auth/register` 今天也没有，
    # 在这里单加一条会让「改密码」比「注册」更严，是两套口径。
    # 要加就两处一起加，那是另一件事。
```

`katrain/web/core/auth.py`：`UserRepository(ABC)` 与 `SQLAlchemyUserRepository` 各加两个方法。
**取会话一律 `self.session_factory()`**（全类 12 处都这么写，没有 `self._session()`）：

```python
    # UserRepository(ABC)
    @abstractmethod
    def get_phone_e164(self, user_id: int) -> Optional[str]:
        ...

    @abstractmethod
    def set_password_hash(self, user_id: int, hashed: str) -> None:
        ...

    # SQLAlchemyUserRepository
    def get_phone_e164(self, user_id: int) -> Optional[str]:
        """原始号的**唯一**取用点。

        它不进 `_to_dict`、不进 pydantic `User` —— 灌进去会随 `User` 泄进
        每一个回 `User` 的响应（`models.py:189` 的 `OnlineUser` 收窄注释
        正是为防这类外溢）。闸一律读 `phone_bound` 那个布尔。
        """
        session = self.session_factory()
        try:
            u = session.query(models_db.User).filter_by(id=user_id).one_or_none()
            return u.phone_e164 if u is not None else None
        finally:
            session.close()

    def set_password_hash(self, user_id: int, hashed: str) -> None:
        """`create_user`(:194) 之外的**第二个** `hashed_password` 写入点。"""
        session = self.session_factory()
        try:
            session.query(models_db.User).filter_by(id=user_id).update({"hashed_password": hashed})
            session.commit()
        finally:
            session.close()
```

`katrain/web/api/v1/endpoints/auth.py`：导入行补 `get_password_hash`（既有那行只导了三个）：

```python
from katrain.web.core.auth import verify_password, get_password_hash, create_access_token, create_refresh_token
```

端点：

```python
@router.post("/set-password")
async def set_password(
    request: Request,
    body: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """改密码。**要验证码，不要当前密码。**

    解开「忘密码的人给不出当前密码」这个死结，同时比只验当前密码更强：
    会话被劫持的攻击者拿不到手机，改不了密码。

    **为什么有了手机验证码登录还要这个端点**：手机登录让人「进得来」，
    这个端点让人「把口令修好」。少了它，忘了密码的用户可以用验证码登录网页版，
    但永远无法恢复口令登录 —— 而口令登录是上盒子的唯一路
    （kiosk 登录页只有用户名与密码两个控件）⇒ 他会被永久挡在自己买的那台设备之外。

    **已知限制**：JWT 没有密码版本位，`/auth/refresh`(:288) 也只验签名 + 用户名存在，
    而 `REFRESH_TOKEN_EXPIRE_DAYS = 90` ⇒ 改密码踢不掉已签发的凭据，**最长 90 天**。
    UI 必须把这句说出来（`auth:set_password_other_devices`）。
    """
    _guard_phone_endpoint(request)
    # `phone_bound` 是 Task 8 加进 pydantic `User` 与 `_to_dict` 的字段，直接读。
    # 不再多查一次库（原计划那次 `repo.get_by_username(...)` 的方法名在仓储上也不存在，
    # 真名是 `get_user_by_username`）。
    if not current_user.phone_bound:
        raise HTTPException(
            status_code=400,
            detail={"code": "phone_unbound", "message": "改密码需要先绑定手机号。"},
        )
    try:
        phone = sms_challenge.verify_and_consume(db, body.challenge_id, body.code, "set_password")
    except sms_challenge.ChallengeInvalid as e:
        raise HTTPException(status_code=400, detail={"code": e.code})

    repo = request.app.state.user_repo
    # 少了这一步，一个人可以拿自己号上的码去改别人的密码。
    # 核销在比对之前：`verify_and_consume` 是取该 challenge 手机号的唯一途径，
    # 而攻击者本来就拿不到受害者号上的码，所以这个顺序不多开任何面。
    if phone != repo.get_phone_e164(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "challenge_phone_mismatch"})

    repo.set_password_hash(current_user.id, get_password_hash(body.new_password))
    return {"ok": True}
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_set_password.py -q`
Expected: PASS（8 条）

- [ ] **Step 5: 变异验证**（三处）

| 变异 | 命令 | 必须变红的用例 |
|---|---|---|
| 注释掉 `_guard_phone_endpoint(request)` | `pytest tests/web_ui/test_set_password.py -q` | `test_set_password_503_on_board_and_does_not_forward` |
| 删掉 `if phone != repo.get_phone_e164(...)` 那两行 | 同上 | `test_challenge_phone_must_match_the_current_users_phone` |
| 把 `if not current_user.phone_bound:` 换成 `if not getattr(current_user, "phone_e164", None):` | 同上 | `test_sets_password_and_the_old_one_stops_working`（**已绑号的人也被判 `phone_unbound`** —— pydantic `User` 上没有 `phone_e164`，`extra='ignore'` 把它静默丢掉，getattr 恒为 None。这就是接口契约口径 1 禁止 getattr 的原因） |

三次都确认红了再改回来，最后重跑 Step 4 确认 8 条全绿。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/api/v1/endpoints/auth.py \
        katrain/web/core/auth.py \
        katrain/web/models.py \
        tests/web_ui/test_set_password.py
git commit -m "feat(auth): POST /auth/set-password —— 鉴权 + 验证码,不做免鉴权 reset

决定性事实:全仓 hashed_password 唯一写入点是 create_user,没有任何改密码端点,
也没有邮箱列 ⇒ 今天一个用户忘了密码,这个系统里没有任何人能帮他。
而口令登录是上盒子的唯一路(kiosk 登录页只有用户名与密码两个控件),
所以'能用验证码登录网页版'不构成替代。

不做免鉴权 reset-password:验证码登录本身已经是完整的'忘密码也能进'出路;
reset 失败会改掉受害者的密码,攻击面严格更大,防线却是同一套。

必须有的一步:校验 challenge 的手机号 == 当前用户的手机号,
否则一个人可以拿自己号上的码去改别人的密码。

已知限制钉了一条断言,**期限是 90 天不是 7 天**:JWT 没有密码版本位,
/auth/refresh 只验签名 + 用户名存在、不看密码改没改,而
REFRESH_TOKEN_EXPIRE_DAYS = 90 ⇒ 手上有 refresh token 的人改密码后
仍能连续换发 90 天。把 90 说成 7 是给用户一个错的安全承诺,
所以断言与 UI 文案都按 90 天写。

补上 Task 7/8/9 都有而这里原来缺的盒子答复用例(board 503 + 不转发),
否则 _guard_phone_endpoint 被谁挪走删掉都不会红。
闸一律读 current_user.phone_bound,不用 getattr —— 配了一次变异证明
换成 getattr(...,'phone_e164') 会让已绑号的人也被判 phone_unbound。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GGNBSL4QhRA2vCDcZL83oF"
```

---

---

### Task 11: 免费额度的手机闸（**money path，最要紧的一个 Task**）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/billing.py`
- Modify: `katrain/web/api/v1/endpoints/reports.py`
- Modify: `tests/web_ui/test_billing_api.py`（本 Task 会打红它 1 条，一并改）
- Modify: `tests/web_ui/test_report_charging.py`（本 Task 会打红它 2 条，一并改）
- Test: `tests/web_ui/test_phone_quota_gate.py`（新建，自带夹具）

**Interfaces:**
- Consumes：Task 8 的 pydantic `User.phone_bound: bool = False` 与 `_to_dict` 里的
  `"phone_bound": user_obj.phone_e164 is not None`
- Produces：
  - `GET /api/v1/billing/quota` 的 `free_weekly` 多一格：`{"used": int, "allowance": int, "blocked_reason": str | None}`，
    未绑号时 `{"used": 0, "allowance": 0, "blocked_reason": "phone_required"}`
  - `POST /api/v1/reports/` 的 402 `detail` 多一格：`"free_weekly_blocked": "phone_unbound" | None`
  - 两个键名不同是**两条不同响应上的两个字段**，Task 13-15 分别读：`/quota` 读
    `free_weekly.blocked_reason`，402 读 `detail.free_weekly_blocked`。本轮不合并。

**机制**（亲验 `katrain/web/core/quota.py:47-77`）：`_ensure_bucket` **只在行不存在时**
写 `allowance`，`peek` 取的是**桶上的快照**（`peek` 的 docstring 明写）⇒ 拿 `allowance=0`
去 `peek` 一个未绑号用户，**当周就开出一个 `allowance=0` 的桶，该用户当周绑了手机也永远拿不到额度**。
⇒ **在触碰 quota 之前短路，一行桶都不建。**

**两条不同的库接缝**（夹具必须同时接住，否则本 Task 唯一要防的假绿就发生了）：
`GET /billing/quota` 的会话来自 `get_db`（`core/db.py:46`，模块级 `SessionLocal`）；
`POST /reports/` 的会话来自 `get_report_db`（`reports.py:127`，`app.state.report_session_factory`）。
两边不接到同一个库时 `db.query(QuotaBucket).count() == 0` **无论实现对错都绿**。

**`POST /reports/` 会先 404**：`reports.py:247-256` 先按 `UserGame.id == task.user_game_id AND
UserGame.user_id == current_user.id` 查，查不到直接 `404 "Game not found"`，**在计费之前**。
所以每条打 `/reports/` 的用例都要先真建一行 `UserGame`（走 `POST /api/v1/user-games/`，
跟 `test_report_charging.py:141-153` 的 `app_with_game` 同一条路）。另外
`ReportTaskCreate.user_game_id` 是 `str`（reports.py:72），传 `1` 会 422 —— 必须用建出来的那个 id。
路径带尾斜杠 `/api/v1/reports/`：不带的话 httpx 默认不跟随 307，拿到的是重定向不是 200。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_quota_gate.py
"""每周免费复盘只发给已绑手机的人，**且未绑号时一行桶都不建**。

`quota._ensure_bucket`(quota.py:47-77) 只在行不存在时写 allowance，`peek` 取桶上的快照
⇒ 拿 allowance=0 去 peek 一个未绑号用户，当周就开出一个 allowance=0 的桶，
该用户当周绑了手机也永远拿不到额度。所以在触碰 quota 之前短路。

不只是「少建一行」：两种写法编码的是**不同的事实**。「没有桶」= 没资格（权限事实）；
「allowance=0 的桶」= 有资格但额度为零（额度事实）。把前者写成后者，将来做
「付费会员每周 3 次 / 免费用户 1 次 / 未绑手机 0 次」时就分不出后两者了 ——
而它们该有完全不同的引导文案。

夹具接线照抄 tests/web_ui/test_report_charging.py:57-95（那份是仓里唯一同时接住
两条库接缝的先例）。
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db

QUOTA = "/api/v1/billing/quota"
REPORTS = "/api/v1/reports/"
SGF_3_MOVES = "(;GM[1]FF[4]SZ[19];B[pd];W[dp];B[pq])"


@pytest.fixture
def app(tmp_path, monkeypatch):
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository
    from katrain.web.core.user_game_repo import UserGameAnalysisRepository, UserGameRepository
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'quota_gate.db'}")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "BILLING_ENFORCED", False)  # 默认值，用例各自改

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    application = create_app(enable_engine=False)
    application.state.session_factory = TestSessionLocal
    application.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)
    application.state.game_repo = GameRepository(TestSessionLocal)
    application.state.user_game_repo = UserGameRepository(TestSessionLocal)
    application.state.user_game_analysis_repo = UserGameAnalysisRepository(TestSessionLocal)
    # **两条接缝都要接，而且接到同一个库**：
    #   GET /billing/quota -> get_db（core/db.py:46，模块级 SessionLocal）
    #   POST /reports/     -> get_report_db（reports.py:127，app.state.report_session_factory）
    # 少接一条，下面 `db.query(QuotaBucket).count() == 0` 数的就是另一个库 ——
    # 那正是本 Task 唯一要防的假绿。
    application.state.report_session_factory = TestSessionLocal

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = _override_get_db
    application.state._TestSessionLocal = TestSessionLocal
    try:
        yield application
    finally:
        engine.dispose()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def db(app):
    session = app.state._TestSessionLocal()
    yield session
    session.close()


def _make_user(app, username, password="pw123456", phone=None, credits=10_000):
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    app.state.user_repo.create_user(username, CryptContext(schemes=["bcrypt"], deprecated="auto").hash(password))
    session = app.state._TestSessionLocal()
    try:
        u = session.query(models_db.User).filter_by(username=username).one()
        u.credits = credits
        if phone is not None:
            u.phone_e164 = phone
        session.commit()
        return u.id
    finally:
        session.close()


def _bind_phone(app, username, phone="+8613800138000"):
    from katrain.web.core import models_db

    session = app.state._TestSessionLocal()
    try:
        session.query(models_db.User).filter_by(username=username).update({"phone_e164": phone})
        session.commit()
    finally:
        session.close()


async def _auth(client, username, password="pw123456"):
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _make_game(client, headers) -> str:
    r = await client.post(
        "/api/v1/user-games/",
        json={"sgf_content": SGF_3_MOVES, "source": "import", "move_count": 3},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def test_unbound_user_quota_reports_blocked_reason(app, client):
    _make_user(app, "nophone")
    h = await _auth(client, "nophone")
    fw = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert fw["allowance"] == 0
    assert fw["blocked_reason"] == "phone_required"


async def test_bound_user_quota_has_no_blocked_reason(app, client):
    _make_user(app, "hasphone", phone="+8613800138000")
    h = await _auth(client, "hasphone")
    fw = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert fw["allowance"] == settings.FREE_WEEKLY_REPORTS
    assert fw["blocked_reason"] is None


async def test_quota_does_create_a_bucket_for_a_bound_user(app, client, db):
    """**正对照，本组第一条。**

    没有它，下一条的 `count() == 0` 证明不了任何事 —— 桶可能只是建在了另一个库里
    （/quota 走 get_db、POST /reports 走 get_report_db，两条接缝）。
    这条证明本文件的 `db` 夹具确实看得见 /quota 那一路的写。
    """
    from katrain.web.core import models_db

    _make_user(app, "hasphone", phone="+8613800138000")
    h = await _auth(client, "hasphone")
    assert (await client.get(QUOTA, headers=h)).status_code == 200
    assert db.query(models_db.QuotaBucket).count() == 1


async def test_quota_does_not_create_a_bucket_for_an_unbound_user(app, client, db):
    """**这条是本 Task 存在的理由。**

    建了 allowance=0 的桶，该用户当周绑了手机也永远拿不到额度 ——
    而「绑定当场生效」那条用例在没跨周的测试里看不出来。所以直接断言桶行不存在。
    """
    from katrain.web.core import models_db

    _make_user(app, "nophone")
    h = await _auth(client, "nophone")
    assert (await client.get(QUOTA, headers=h)).status_code == 200
    assert db.query(models_db.QuotaBucket).count() == 0


async def test_binding_takes_effect_in_the_same_week(app, client):
    _make_user(app, "later")
    h = await _auth(client, "later")
    await client.get(QUOTA, headers=h)          # 先看一眼（就是会诱发建桶的那个动作）
    _bind_phone(app, "later")
    fw = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert fw["allowance"] == settings.FREE_WEEKLY_REPORTS, "当周绑定必须当场生效"
    assert fw["blocked_reason"] is None


async def test_unbound_user_report_does_not_consume_free_quota(app, client, db, monkeypatch):
    """未绑号 ⇒ 免费额度那条分支根本不走，直接进扣费路径。"""
    from katrain.web.core import models_db

    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)
    _make_user(app, "nophone", credits=10_000)
    h = await _auth(client, "nophone")
    gid = await _make_game(client, h)

    r = await client.post(REPORTS, json={"user_game_id": gid, "report_type": "normal"}, headers=h)
    assert r.status_code == 200, r.text
    task = db.query(models_db.ReportTask).one()
    assert task.free_grant_period is None, "未绑号不许走免费额度"
    assert task.charge_ref is not None, "那就必须走扣费 —— 两条路总得走了一条"
    assert db.query(models_db.QuotaBucket).count() == 0


async def test_402_says_phone_not_just_no_money(app, client, monkeypatch):
    """把「你还没绑手机」伪装成「你没钱」违反 spec §3.1 状态诚实。"""
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)
    _make_user(app, "broke", credits=0)
    h = await _auth(client, "broke")
    gid = await _make_game(client, h)

    r = await client.post(REPORTS, json={"user_game_id": gid, "report_type": "normal"}, headers=h)
    assert r.status_code == 402
    assert r.json()["detail"]["free_weekly_blocked"] == "phone_unbound"


async def test_402_for_a_bound_user_says_nothing_about_the_phone(app, client, monkeypatch):
    """**负对照**：这个字段不许是个常量。已绑号的人没钱，就只是没钱。"""
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 0)
    _make_user(app, "brokebound", credits=0, phone="+8613800138000")
    h = await _auth(client, "brokebound")
    gid = await _make_game(client, h)

    r = await client.post(REPORTS, json={"user_game_id": gid, "report_type": "normal"}, headers=h)
    assert r.status_code == 402
    assert r.json()["detail"]["free_weekly_blocked"] is None


async def test_billing_gate_off_is_unchanged_for_everyone(app, client, db, monkeypatch):
    """**正对照**：BILLING_ENFORCED=False 时整段早退（reports.py:277-289），
    根本不碰 quota ⇒ 本轮改动对今天的生产零用户可见回归。"""
    from katrain.web.core import models_db

    monkeypatch.setattr(settings, "BILLING_ENFORCED", False)
    _make_user(app, "nophone")
    h = await _auth(client, "nophone")
    gid = await _make_game(client, h)

    r = await client.post(REPORTS, json={"user_game_id": gid, "report_type": "normal"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert db.query(models_db.QuotaBucket).count() == 0
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_quota_gate.py -q`
Expected: FAIL — **7 failed, 2 passed**。逐条：

| 用例 | 现在 |
|---|---|
| `test_unbound_user_quota_reports_blocked_reason` | 红 —— `KeyError: 'blocked_reason'` |
| `test_bound_user_quota_has_no_blocked_reason` | 红 —— 同上 |
| `test_quota_does_create_a_bucket_for_a_bound_user` | **绿**（正对照，改动前后都必须绿） |
| `test_quota_does_not_create_a_bucket_for_an_unbound_user` | 红 —— 今天谁来都建桶，`count()` 是 1 |
| `test_binding_takes_effect_in_the_same_week` | 红 —— `KeyError: 'blocked_reason'` |
| `test_unbound_user_report_does_not_consume_free_quota` | 红 —— 今天走了免费分支：`free_grant_period` 有值、`charge_ref` 为 None、桶是 1 |
| `test_402_says_phone_not_just_no_money` | 红 —— `KeyError: 'free_weekly_blocked'` |
| `test_402_for_a_bound_user_says_nothing_about_the_phone` | 红 —— 同上 |
| `test_billing_gate_off_is_unchanged_for_everyone` | **绿**（正对照） |

- [ ] **Step 3: 写最小实现**

**(a) `katrain/web/api/v1/endpoints/billing.py`** 的 `get_quota`（:106-111），把 `quota.peek(...)`
那两行与 `free_weekly` 那一行换成：

```python
    # **未绑手机的用户绝不能触碰 quota。**
    # quota._ensure_bucket 在第一次触碰时就把 allowance 快照钉死在桶行上
    # (quota.py:56-57；peek 的 docstring 明写「限额取桶上的快照」)。
    # 拿 allowance=0 去 peek 一个未绑号用户 ⇒ 当周开出一个 allowance=0 的桶,
    # 该用户当周绑了手机也永远拿不到额度。所以在这里短路,一行桶都不建。
    #
    # 不只是「少建一行」:这两种写法编码的是**不同的事实**。
    # 「没有桶」= 没资格(权限事实);「allowance=0 的桶」= 有资格但额度为零(额度事实)。
    # 把前者写成后者,将来做「付费会员每周 3 次 / 免费用户 1 次 / 未绑手机 0 次」时
    # 就分不出后两者了 —— 而它们该有完全不同的引导文案。
    #
    # ⚠️ **这条短路的正确性有一个前提:不存在「解绑手机」的路径。**
    # Task 9 的 bind_phone 对已绑号的账号返 "already_bound" 而不是覆盖,
    # 本轮也不建解绑端点,所以自洽。若哪天加了解绑,要回来重看这里:
    # 那时一个 used=1 的桶行会在 /quota 上突然变得不可见。
    if current_user.phone_bound:
        used, allowance = quota.peek(
            db, current_user.id, "free_report:week", allowance=settings.FREE_WEEKLY_REPORTS
        )
        blocked_reason = None
    else:
        used, allowance, blocked_reason = 0, 0, "phone_required"
    return {
        "credits": billing.get_balance(db, current_user.id),
        # blocked_reason 是必需的:没有它,前端分不出 allowance:0(没绑手机)
        # 与 used:1,allowance:1(本周已用完) —— 违反 spec §3.1 状态诚实。
        "free_weekly": {"used": used, "allowance": allowance, "blocked_reason": blocked_reason},
        # …以下 estimates / billing_enforced / billing_online 三行原样不动
```

**(b) `katrain/web/api/v1/endpoints/reports.py`** 免费额度分支的条件（:324）加一项：

```python
    if task.report_type == "normal" and settings.FREE_WEEKLY_REPORTS > 0 and current_user.phone_bound:
```

**(c) 同文件** 402 的 `detail`（:346-352）加一格：

```python
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "insufficient_credits",
                    "need": cost,
                    "have": billing.get_balance(db, current_user.id),
                    # 未绑号时说清楚:否则我们在把「你还没绑手机」伪装成「你没钱」。
                    "free_weekly_blocked": None if current_user.phone_bound else "phone_unbound",
                },
            )
```

**(d) 本轮会打红的三条既有用例，在同一个提交里改掉**（不改的话 Task 16 的
「新增失败为空」不可能通过，而把它们加进基线等于退役三条真断言）：

`tests/web_ui/test_billing_api.py`：`_make_user` 加一个可选参数，`test_quota_endpoint_shape`
给用户绑上号并把精确 dict 比较补齐一格（**保留精确比较** —— 它顺带守着「不许多出别的键」）：

```python
# _make_user 签名与函数体（:53-66）
async def _make_user(app, username, password="pw", is_admin=False, credits=0, phone=None):
    ...
        u.is_admin = is_admin
        u.credits = credits
        if phone is not None:
            u.phone_e164 = phone          # ← 新增这两行
        s.commit()

# test_quota_endpoint_shape（:149 起）
    await _make_user(app, "quotauser", credits=500, phone="+8613800138000")
    ...
    # 免费周额度自 P3 起只发给已绑手机的人（endpoints/billing.py 的短路），
    # 所以这个用户先绑上号；未绑号那一档的形状由
    # tests/web_ui/test_phone_quota_gate.py 覆盖。
    assert b["free_weekly"] == {"used": 0, "allowance": 1, "blocked_reason": None}
```

`tests/web_ui/test_report_charging.py`：加一个 helper，并在两条走免费分支的用例开头调用它：

```python
def _bind_phone(user, phone: str = "+8613800138000") -> None:
    """给这个用户绑一个手机号。

    免费周额度自 P3 起只发给已绑号的人（reports.py 的免费分支多了一项
    `current_user.phone_bound`）。本文件其余用例把 FREE_WEEKLY_REPORTS 调到 0
    只测积分路径，不受影响；下面两条是**专测免费分支**的，不绑号的话它们
    量到的是扣费路径 —— 断言会红，而且红的原因与它们要证的事情无关。
    """
    from katrain.web.core import models_db

    db = _session_factory()
    try:
        db.query(models_db.User).filter_by(id=user.id).update({"phone_e164": phone})
        db.commit()
    finally:
        db.close()
```

- `test_first_report_of_the_week_is_free_second_is_charged`：在
  `monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)` 之后加一行 `_bind_phone(user)`。
- `test_free_report_records_its_period_not_a_charge_ref`：同样位置加一行 `_bind_phone(user)`。

- [ ] **Step 4: 跑，确认它绿**

Run:
```
./.venv/bin/python -m pytest tests/web_ui/test_phone_quota_gate.py \
                            tests/web_ui/test_billing_api.py \
                            tests/web_ui/test_report_charging.py -q
```
Expected: PASS（24 条 = 新增 9 + test_billing_api 8 + test_report_charging 7）

再跑一次相邻的两个文件确认没有波及（它们只直接调 `quota`，不经端点）：

Run: `./.venv/bin/python -m pytest tests/web_ui/test_free_weekly.py tests/web_ui/test_report_reaper.py tests/web_ui/test_report_retry_authorization.py -q`
Expected: PASS（全绿，条数与改动前一致）

- [ ] **Step 5: 变异验证（这个 Task 必做）**

把 `billing.py` 的短路改成「看起来等价」的那种写法：

```python
    used, allowance = quota.peek(db, current_user.id, "free_report:week",
                                 allowance=settings.FREE_WEEKLY_REPORTS if current_user.phone_bound else 0)
    blocked_reason = None if current_user.phone_bound else "phone_required"
```

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_quota_gate.py -q`
Expected: FAIL — `test_quota_does_not_create_a_bucket_for_an_unbound_user` 与
`test_binding_takes_effect_in_the_same_week` **两条同时红**（前者数到 1 个桶，
后者拿到 allowance=0 —— 因为桶行上的快照已经被钉死）。改回短路。

**这次变异就是这个 Task 的全部价值**：它证明「看起来等价的两种写法」里有一种是坏的。

再做一次第二个变异：把 `reports.py` 免费分支条件里的 `and current_user.phone_bound` 删掉。
Expected: FAIL — `test_unbound_user_report_does_not_consume_free_quota` 与
`test_402_says_phone_not_just_no_money` 变红。改回来，重跑 Step 4 确认 24 条全绿。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/api/v1/endpoints/billing.py \
        katrain/web/api/v1/endpoints/reports.py \
        tests/web_ui/test_phone_quota_gate.py \
        tests/web_ui/test_billing_api.py \
        tests/web_ui/test_report_charging.py
git commit -m "feat(billing): 每周免费复盘闸在'已绑手机'上,且在触碰 quota 之前短路

亲验 quota.py:47-77:_ensure_bucket 只在行不存在时写 allowance,peek 取快照
⇒ 拿 allowance=0 去 peek 一个未绑号用户,当周就开出一个 allowance=0 的桶,
该用户当周绑了手机也永远拿不到额度。所以短路,一行桶都不建。

配了变异验证:换成'allowance=0 表达式'那种写法,
'不建桶'与'绑定当周生效'两条同时变红 —— 两种看起来等价的写法里有一种是坏的。

blocked_reason 是必需的:没有它前端分不出'没绑手机'与'本周已用完'。
402 加 free_weekly_blocked,否则我们在把'你还没绑手机'伪装成'你没钱';
另配一条负对照钉住它不是常量(已绑号的人没钱就只是没钱)。

一并改掉本轮打红的三条既有用例(而不是把它们加进基线,那等于退役三条真断言):
  test_billing_api.py 的 /quota 精确 dict 比较 —— 补一格并给该用户绑号;
  test_report_charging.py 两条专测免费分支的用例 —— 加 _bind_phone(user)。
新增用例的夹具同时接住两条库接缝(get_db 与 report_session_factory 指同一个库),
并先用一条正对照证明这个 db 看得见 /quota 的写,否则那句 count()==0 不成立为证据。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GGNBSL4QhRA2vCDcZL83oF"
```

---

---

### Task 12: 发言闸（实名义务的正确落点）

**Files:**
- Modify: `katrain/web/server.py`（对局聊天，WS）
- Modify: `katrain/web/api/v1/endpoints/live.py`（直播评论）
- Modify: `tests/web_ui/test_game_termination_and_chat_identity.py`（`_make_user` 加手机号参数）
- Test: `tests/web_ui/test_posting_requires_phone.py`（新建，自带夹具）

**Interfaces:**
- Consumes：**Task 8 必须已经落地** ——
  `katrain/web/models.py` 的 pydantic `User` 上有 `phone_bound: bool = False`，
  且 `katrain/web/core/auth.py:323` 的 `_to_dict` 里有
  `"phone_bound": user_obj.phone_e164 is not None`。少任何一半，两处闸都恒判「未绑」。
- Produces：WS 错误帧 `{"type": "error", "code": "chat_requires_phone"}`；
  `POST /api/v1/live/matches/{match_id}/comments` → `403 {"code": "comment_requires_phone"}`

**依据**：《网络安全法》二十六条约束的是**为用户提供信息发布、即时通讯服务**，
不是「有账号」⇒ 正确落点是**未绑手机不得发言**，而不是关掉注册（D-U2）。

**两处闸读的是同一个属性，因为它们拿到的是同一个对象。**
WS 里的 `current_user`（`server.py:2769`）与 live.py 里 `Depends(get_current_user)` 拿到的
**是同一个 pydantic `User`** —— 两处都出自 `get_user_from_token`
（`endpoints/auth.py:106-125`，末行 `return User(**user_dict)`）。
而那个模型（`models.py:176-186`）**没有 `phone_e164`**，pydantic v2 默认 `extra='ignore'`
会把 `_to_dict` 里的原始号静默丢掉 ⇒ 写 `getattr(current_user, "phone_e164", None)`
的话它**恒为 None，所有人（含已绑号）都发不了言**。
所以两处一律写 `if not current_user.phone_bound:`，**直接属性访问、不用 getattr**：
字段有默认值 ⇒ 属性必然存在；用 getattr 兜底会掩盖「字段没加上」这个错误，
而它的失败方向是全站禁言。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_posting_requires_phone.py
"""未绑手机不得发言（对局聊天 + 直播评论）。

闸读 `current_user.phone_bound` —— Task 8 加进 pydantic `User` 与 `_to_dict` 的那个布尔。
**不读 `phone_e164`、不用 getattr**：WS 的 `current_user` 与 live.py 的
`Depends(get_current_user)` 是同一个 pydantic `User`（都出自 auth.py:125
`return User(**user_dict)`），那个模型上没有 `phone_e164`，
`extra='ignore'` 会把它静默丢掉 ⇒ getattr 恒为 None ⇒ 所有人都发不了言。

WS 用例必须用 `TestClient`（httpx 的 AsyncClient 不做 WebSocket），
而 TestClient **会跑 lifespan** ⇒ `app.state.session_factory` 必须在进它之前设好，
否则 `_lifespan_server` 会用全局 SessionLocal 重建六个 repo 覆盖掉注入，
写落进开发机真库并被 tests/conftest.py 的写闸拦住。整套接线照抄
tests/web_ui/test_game_termination_and_chat_identity.py:38-92。
"""
import threading
import uuid
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base
from katrain.web.server import create_app

COMMENTS = "/api/v1/live/matches/m1/comments"


@pytest.fixture
def app(tmp_path, monkeypatch):
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'posting.db'}")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # live.py 的 create_comment 用的是**模块级** SessionLocal
    # （函数体内 `from katrain.web.core.db import SessionLocal`，不走 Depends）
    # ⇒ 只能在这里换掉，否则评论会写进开发机真库并被 conftest 的闸拦住。
    monkeypatch.setattr("katrain.web.core.db.SessionLocal", Session)

    application = create_app(enable_engine=False)
    application.state.session_factory = Session          # ← 这一行才是真正生效的那处
    application.state.user_repo = SQLAlchemyUserRepository(Session)
    application.state.game_repo = GameRepository(Session)
    application.state._TestSessionLocal = Session
    try:
        yield application
    finally:
        engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


class _StubStatus:
    value = "live"


class _StubMatch:
    status = _StubStatus()


class _StubCache:
    async def get_match(self, match_id):
        return _StubMatch() if match_id == "m1" else None


class _StubLiveService:
    cache = _StubCache()


@pytest.fixture
def live_service(app):
    """`Depends(get_live_service)` 在函数体之前就要解析出来，没有它整条路是 503 ——
    那样「403」和「这个端点本来就不通」分不开。"""
    from katrain.web.api.v1.endpoints.live import get_live_service

    app.dependency_overrides[get_live_service] = lambda: _StubLiveService()
    yield app
    app.dependency_overrides.pop(get_live_service, None)


def _make_user(app, username, phone=None):
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    app.state.user_repo.create_user(username, CryptContext(schemes=["bcrypt"], deprecated="auto").hash("password"))
    session = app.state._TestSessionLocal()
    try:
        u = session.query(models_db.User).filter_by(username=username).one()
        if phone is not None:
            u.phone_e164 = phone
            session.commit()
        return u.id
    finally:
        session.close()


def _token(client, username: str) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _inject_session(app):
    """把一个**无人认领**的会话直接塞进 session manager。

    三个 id 全 None ⇒ `guard_session_reader`(server.py:811) 早退，
    任何登录用户都连得上 —— 本组用例要的正是「第三方也在房间里」。
    conftest 把 `katrain.web.interface` 整个换成了 MagicMock，所以走 HTTP 真开一局
    不会执行到 WebKaTrain；沿用本目录既有做法手工构造一个够真的 session
    （tests/web_ui/test_game_termination_and_chat_identity.py:102-133）。
    """
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.user_id = None
    session.player_b_id = None
    session.player_w_id = None
    session.mode = "play"
    session.game_type = "free"
    session.lock = threading.Lock()
    session.sockets = set()
    session.last_access = 0.0
    session.last_state = {"end_result": None}
    session.pending_count_request = None
    session.pending_count_timestamp = None
    session.game_ended = False

    katrain = MagicMock()
    katrain.game_type = "free"
    katrain.get_sgf.return_value = "(;FF[4]SZ[19];B[pd])"
    katrain.get_state.return_value = {"end_result": None}
    katrain.game.end_result = None
    session.katrain = katrain

    app.state.session_manager._sessions[session.session_id] = session
    return session


def _await(ws, *wanted: str, limit: int = 20) -> dict:
    """读到第一个 type 命中 `wanted` 的帧。

    这条 socket 一连上就会推 `game_update` 与 `spectator_count`（server.py:2799/2815），
    别人进出房间时还会再来 `spectator_count`，所以「收下一帧」不等于「收我等的那一帧」。
    写死跳过前 N 帧的话，哪天多播一条无关广播，红的会是这些测试而不是被改坏的东西。
    """
    for _ in range(limit):
        frame = ws.receive_json()
        if frame.get("type") in wanted:
            return frame
    raise AssertionError(f"{limit} 帧之内没等到 {wanted}")


def test_chat_from_an_unbound_user_gets_an_error_not_silence(app, client):
    """照抄 server.py 里已有的口径：说一句而不是静默丢弃 ——
    静默丢弃时发言的人看不出自己没发出去。

    读的是**发送方自己那条 socket**：广播会回到发送方，所以闸没生效时这里
    收到的是一条 `chat` 帧（当场红），而不是永远等不到帧（挂住）。
    """
    _make_user(app, "nophone")
    session = _inject_session(app)
    with client.websocket_connect(f"/ws/{session.session_id}?token={_token(client, 'nophone')}") as ws:
        ws.send_json({"type": "chat", "text": "hello"})
        frame = _await(ws, "chat", "error")
    assert frame == {"type": "error", "code": "chat_requires_phone"}


def test_chat_from_a_bound_user_is_broadcast(app, client):
    """**正对照。** 没有它，「拒绝生效」和「聊天整个坏了」是同一个观测值。

    这条同时是「闸不许读 phone_e164」的检出点：换成
    `getattr(current_user, "phone_e164", None)` 它当场红。
    """
    _make_user(app, "bound", phone="+8613800138000")
    session = _inject_session(app)
    with client.websocket_connect(f"/ws/{session.session_id}?token={_token(client, 'bound')}") as ws:
        ws.send_json({"type": "chat", "text": "hello"})
        frame = _await(ws, "chat", "error")
    assert frame["type"] == "chat"
    assert frame["text"] == "hello"
    assert frame["from_name"] == "bound"


def test_an_unbound_users_message_never_reaches_a_third_party(app, client):
    """光有错误回执不够 —— 得确认它真的没广播出去。

    **不能写成 `assert not _has_pending(observer)`**：广播是 fire-and-forget
    （session.py:257-268，`create_task` / `run_coroutine_threadsafe`，请求处理这边
    从不 await 它）⇒ 闸拆掉之后泄漏的那帧很可能「还没送到」就被读成「没有」= 假绿；
    反方向也坏 —— 观战者一连上就先收到 `game_update` 与 `spectator_count`
    （server.py:2799/2815），不排掉的话它恒为 True = 恒红。

    改成**带同步点的顺序断言**：先等到未绑号那句被明确拒绝（同步点，证明服务端
    已经处理完那条消息），再让一个已绑号的人发一句哨兵，然后把第三方的帧排到
    第一条 `type=="chat"` —— 那一条必须是哨兵。闸拆掉时它会是 `"leak"`，当场红；
    而且没有时序运气成分：两次广播由同一个事件循环按 `create_task` 的创建顺序跑，
    泄漏的那帧一定排在哨兵之前。
    """
    _make_user(app, "nophone")
    _make_user(app, "bound", phone="+8613800138000")
    session = _inject_session(app)
    base = f"/ws/{session.session_id}?token="

    with client.websocket_connect(base + _token(client, "bound")) as third_party:
        with client.websocket_connect(base + _token(client, "nophone")) as muted:
            muted.send_json({"type": "chat", "text": "leak"})
            refused = _await(muted, "chat", "error")
            assert refused.get("code") == "chat_requires_phone", refused   # ← 同步点
        third_party.send_json({"type": "chat", "text": "sentinel-42"})
        first_chat = _await(third_party, "chat")

    assert first_chat["text"] == "sentinel-42", "第三方收到的第一条聊天不是哨兵 —— 未绑号那句漏出去了"


def test_live_comment_from_an_unbound_user_is_403(live_service, client):
    _make_user(live_service, "nophone")
    r = client.post(
        COMMENTS,
        json={"content": "hi"},
        headers={"Authorization": f"Bearer {_token(client, 'nophone')}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "comment_requires_phone"


def test_live_comment_from_a_bound_user_succeeds(live_service, client):
    """**正对照。** 否则「403」与「这条端点本来就不通」是同一个观测值。"""
    _make_user(live_service, "bound", phone="+8613800138000")
    r = client.post(
        COMMENTS,
        json={"content": "hi"},
        headers={"Authorization": f"Bearer {_token(client, 'bound')}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "hi"
    assert r.json()["username"] == "bound"
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_posting_requires_phone.py -q`
Expected: FAIL — **3 failed, 2 passed**：

| 用例 | 现在 |
|---|---|
| `test_chat_from_an_unbound_user_gets_an_error_not_silence` | 红 —— 今天照常广播，收到的是 `{"type": "chat", …}` |
| `test_chat_from_a_bound_user_is_broadcast` | **绿**（正对照） |
| `test_an_unbound_users_message_never_reaches_a_third_party` | 红 —— 同步点那句 `refused.get("code")` 拿到 None（收到的是 chat 帧） |
| `test_live_comment_from_an_unbound_user_is_403` | 红 —— 今天返 200 |
| `test_live_comment_from_a_bound_user_succeeds` | **绿**（正对照） |

- [ ] **Step 3: 写最小实现**

**(a) `katrain/web/server.py`** 的 chat 分支，紧跟现有的 `if current_user is None:` 那三行之后
（`server.py:2823-2826`），插进去：

```python
                    # 实名义务约束的是「提供信息发布/即时通讯服务」(网安法二十六条),
                    # 不是「有账号」—— 所以闸在这里,不在注册。
                    # 口径与上面那条一致:说一句,不静默丢弃。
                    #
                    # 读 `phone_bound` **不用 getattr**:这里的 current_user 与
                    # live.py 里 Depends(get_current_user) 拿到的是**同一个** pydantic
                    # User —— 两处都出自 endpoints/auth.py:125 `return User(**user_dict)`。
                    # 那个模型上没有 `phone_e164`,pydantic v2 默认 extra='ignore'
                    # 会把 _to_dict 里的原始号静默丢掉 ⇒ 写 getattr(...,"phone_e164")
                    # 恒为 None,**所有人(含已绑号)都发不了言**。
                    # 字段有默认值 ⇒ 属性必然存在,缺了应该当场响,而不是静默全站禁言。
                    if not current_user.phone_bound:
                        await websocket.send_json({"type": "error", "code": "chat_requires_phone"})
                        continue
```

**(b) `katrain/web/api/v1/endpoints/live.py`** 的 `create_comment`（:588），
函数体**第一件事**（在 `from … import` 与查 match 之前）：

```python
    # 未绑手机不得发言。闸在发言不在注册(网安法二十六条约束的是「提供信息发布服务」)。
    # 与 server.py 的对局聊天读**同一个属性**:两处的 current_user 是同一个 pydantic User。
    if not current_user.phone_bound:
        raise HTTPException(
            status_code=403,
            detail={"code": "comment_requires_phone",
                    "message": "发表评论需要先绑定手机号。"},
        )
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_posting_requires_phone.py -q`
Expected: PASS（5 条）

再确认没有波及既有的聊天契约用例：

Run: `./.venv/bin/python -m pytest tests/web_ui/test_game_termination_and_chat_identity.py -q`
Expected: **FAIL** —— 该文件里四条走聊天的用例（`test_the_client_cannot_choose_who_it_speaks_as`、
`test_over_length_chat_is_rejected_not_truncated`、`test_malformed_chat_gets_a_code_not_silence`
参数化 3 条、`test_a_well_formed_chat_still_goes_through`）用的 `alice/bob` 都没绑号，
新闸在 `chat_text_required` 等判断**之前**，所以它们会先拿到 `chat_requires_phone`。

**这不是「顺带打红的既有测试」，是本 Task 的一部分**，在同一个提交里改：
给 `tests/web_ui/test_game_termination_and_chat_identity.py` 的 `_make_user` 加一个手机号参数，
并让四条聊天用例建的用户都带上号 ——

```python
def _make_user(app, name: str, phone: str | None = None):
    """P3 起未绑手机不得发言（server.py 的 chat 闸）⇒ 走聊天的用例必须建带号的用户，
    否则它们量到的是新闸，而不是各自要证的那件事（冒名/超长/畸形/正对照）。"""
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    unique = f"{name}-{uuid.uuid4().hex[:8]}"
    hashed = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("password")
    user = app.state.user_repo.create_user(unique, hashed)
    if phone is not None:
        session = app.state.user_repo.session_factory()
        try:
            session.query(models_db.User).filter_by(id=user["id"]).update({"phone_e164": phone})
            session.commit()
        finally:
            session.close()
    return user["id"], unique
```

四条聊天用例里的建号调用改成带号（终结守卫那几条不走聊天，不用动）：
- `test_the_client_cannot_choose_who_it_speaks_as`：`_make_user(app, "alice", phone="+8613800138000")`
- `test_over_length_chat_is_rejected_not_truncated`：同上
- `test_malformed_chat_gets_a_code_not_silence`：同上
- `test_a_well_formed_chat_still_goes_through`：同上

改完重跑：

Run: `./.venv/bin/python -m pytest tests/web_ui/test_posting_requires_phone.py tests/web_ui/test_game_termination_and_chat_identity.py -q`
Expected: PASS（全绿；`test_game_termination_and_chat_identity.py` 的条数与改动前一致）

- [ ] **Step 5: 变异验证**

| 变异 | 命令 | 必须变红的用例 |
|---|---|---|
| 把 `server.py` 的 `if not current_user.phone_bound:` 换成 `if not getattr(current_user, "phone_e164", None):` | `pytest tests/web_ui/test_posting_requires_phone.py -q` | `test_chat_from_a_bound_user_is_broadcast`（**已绑号的人也被禁言** —— 这正是原计划踩进去的那个坑） |
| 把 `server.py` 那两行整个删掉 | 同上 | `test_chat_from_an_unbound_user_gets_an_error_not_silence` 与 `test_an_unbound_users_message_never_reaches_a_third_party` 同时红 |
| 把 `live.py` 那段 403 删掉 | 同上 | `test_live_comment_from_an_unbound_user_is_403` |

三次都确认红了再改回来，最后重跑 Step 4 的两条命令确认全绿。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/server.py \
        katrain/web/api/v1/endpoints/live.py \
        tests/web_ui/test_posting_requires_phone.py \
        tests/web_ui/test_game_termination_and_chat_identity.py
git commit -m "feat(auth): 未绑手机不得发言(对局聊天 + 直播评论)

实名义务约束的是'提供信息发布/即时通讯服务'(网安法二十六条),不是'有账号'
⇒ 闸的正确落点是发言,不是注册。这也是 D-U2 保持注册契约不变的依据之一。

两处闸读同一个属性 current_user.phone_bound,**直接访问不用 getattr**:
WS 的 current_user 与 live.py 里 Depends(get_current_user) 拿到的是同一个
pydantic User(都出自 endpoints/auth.py:125 return User(**user_dict)),
而那个模型上没有 phone_e164、pydantic v2 extra='ignore' 会静默丢掉它 ⇒
写 getattr(...,'phone_e164') 恒为 None,所有人(含已绑号)都发不了言。
配了一次变异专门钉这条:换成 getattr 后'已绑号能发言'当场红。

聊天那条照抄同一处已有的口径:说一句而不是静默丢弃 ——
静默丢弃时发言的人看不出自己没发出去。
'没广播出去'那条不写成'队列里没有东西'(广播是 fire-and-forget,泄漏的帧
可能还没送到就被读成没有 = 假绿;而观战者连上就有两帧 = 恒红),
改成带同步点的顺序断言:第三方收到的第一条 chat 必须是哨兵。

同一个提交里改掉 test_game_termination_and_chat_identity.py 的四条聊天用例
(给它们的用户绑号)—— 新闸在 chat_text_required 之前,不改的话它们量到的
是新闸而不是各自要证的那件事。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GGNBSL4QhRA2vCDcZL83oF"
```

---

### Task 13: 前端 API 与 AuthContext（共享领土）

**Files:**
- Modify: `katrain/web/ui/src/api.ts`（**共享领土**）
- Modify: `katrain/web/ui/src/context/AuthContext.tsx`（**共享领土**）
- Test: `katrain/web/ui/src/api.phone.test.ts`（新建）
- Test: `katrain/web/ui/src/context/AuthContext.phone.test.tsx`（新建）

**Interfaces:**
- Consumes: 后端 Task 7/8/9/10 的四个端点：
  `POST /api/v1/auth/phone/send-code {phone, purpose}` → `{challenge_id, cooldown_sec}`；
  `POST /api/v1/auth/phone/login {challenge_id, code}` → `{access_token, token_type}`；
  `POST /api/v1/auth/phone/bind {challenge_id, code}`（鉴权）→ `{phone_masked}`；
  `POST /api/v1/auth/set-password {challenge_id, code, new_password}`（鉴权）→ `{"ok": true}`。
  失败一律 `{"detail": {"code": str, "message"?: str, "retry_after_sec"?: int}}`。
  Task 8 已把 `phone_bound: bool` 加进 pydantic `User` ⇒ `GET /api/v1/auth/me` 带这一格。
- Produces（后面三个 Task 全部按这些确切签名调用）：
  ```ts
  // src/api.ts —— 挂在既有的 export const API 上
  API._phonePost(path: string, body: Record<string, unknown>, auth?: boolean): Promise<any>
  API.sendPhoneCode(phone: string, purpose: 'login' | 'bind' | 'set_password'): Promise<SendCodeResponse>
  API.loginByPhone(challengeId: string, code: string): Promise<PhoneLoginResponse>
  API.bindPhone(challengeId: string, code: string): Promise<BindPhoneResponse>
  API.setPassword(challengeId: string, code: string, newPassword: string): Promise<void>
  // 同文件导出的类型
  export interface SendCodeResponse { challenge_id: string; cooldown_sec: number }
  export interface PhoneLoginResponse { access_token: string; token_type: string }
  export interface BindPhoneResponse { phone_masked: string }

  // src/context/AuthContext.tsx —— useAuth() 的返回值上新增两项
  loginByPhone(challengeId: string, code: string): Promise<void>
  refreshUser(): Promise<void>
  // 并给该文件里那个本地 interface User 加一格：phone_bound: boolean
  ```

⚠️ **两个文件都在共享领土**，kiosk 包也会吃进去 ⇒ `npm run build` 与 `npm run build:kiosk-2d`
都要绿（Global Constraint 12）。**`API.register` 与 `API.login` 一个字节不动**（D-U2 注册契约不变）
——`src/components/RegisterDialog.tsx` 与 `ZenModeApp` 因此不受影响，并配一条断言钉住它。

⚠️ **鉴权头必须用 `api.ts:297` 那个模块级 `authHeaders(token?)`，不要另写一个。**
仓里**没有** `API._authHeader`（`grep -rn '_authHeader' katrain/web/ui/src` 零命中），
照着写会让 `tsc -b` 当场挂；而"自己再补一个"会绕过 `api.ts:279/298` 那一档
（`const isStrictBoxKiosk = __KIOSK_2D_ONLY__ && VITE_BOX_SSO_STRICT === 'true'` 时
`authHeaders` 返回 `{}`，注释原话「严格盒端…这里绝不能自己造 Bearer 头」）。
本 Task 的第 7 条用例就是钉这一档的，Step 5 有对应变异。

⚠️ **本 worktree 没有 `node_modules`**（`ls katrain/web/ui/node_modules` 不存在，主仓有）。
前端第一条命令之前先装依赖，否则 `npx vitest` 会去网上现拉一个版本不对的包：

```bash
cd katrain/web/ui && npm ci
```

- [ ] **Step 1: 写失败的测试**

```ts
// src/api.phone.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { API } from './api';

// 三档构建里各跑一遍的门控，照抄同目录 src/context/AuthContext.test.tsx:41-47 的现成写法。
const isKioskBuild = __KIOSK_2D_ONLY__;
const isStrictBoxKiosk = isKioskBuild && import.meta.env.VITE_BOX_SSO_STRICT === 'true';
const nonStrictIt = isStrictBoxKiosk ? it.skip : it;
const strictKioskIt = isStrictBoxKiosk ? it : it.skip;

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);

const headersOf = (init?: RequestInit) => (init?.headers ?? {}) as Record<string, string>;

describe('手机验证码四个 API', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // localStorage 在严格盒端那一档也要有值 —— 否则「不带 Authorization」那条断言
    // 会因为压根没 token 而假绿。
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (k: string) => (k === 'token' ? 'stored-token' : null),
        setItem: () => {}, removeItem: () => {}, clear: () => {},
      },
    });
  });

  it('sendPhoneCode 打到 send-code，并把 purpose 一起送出去', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ challenge_id: 'c1', cooldown_sec: 60 }));
    await API.sendPhoneCode('+8613800138000', 'login');
    const [url, init] = f.mock.calls[0];
    expect(url).toBe('/api/v1/auth/phone/send-code');
    expect(JSON.parse(init!.body as string)).toEqual({ phone: '+8613800138000', purpose: 'login' });
  });

  it('loginByPhone 只送 challenge_id 与 code —— 不送手机号', async () => {
    // spec §2「verify 只收 challenge_id 不收手机号」的前端一半：
    // 前端多送一个 phone，后端哪天顺手信了它，验证码就和号解耦了。
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ access_token: 't', token_type: 'bearer' }));
    await API.loginByPhone('c1', '123456');
    const body = JSON.parse((f.mock.calls[0][1] as RequestInit).body as string);
    expect(body).toEqual({ challenge_id: 'c1', code: '123456' });
    expect(Object.keys(body)).not.toContain('phone');
  });

  it('限流时把后端的 code 与 retry_after_sec 原样抛出去，不吞成通用错误', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ detail: { code: 'sms_cooldown', retry_after_sec: 42 } }, 429));
    await expect(API.sendPhoneCode('+8613800138000', 'login')).rejects.toMatchObject({
      code: 'sms_cooldown', retryAfterSec: 42, status: 429,
    });
  });

  it('register 的请求体没有被改动 —— 共享领土，ZenModeApp / RegisterDialog 也在用', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() => jsonResponse({}));
    await API.register('u', 'p');
    expect(f.mock.calls[0][0]).toBe('/api/v1/auth/register');
    expect(JSON.parse((f.mock.calls[0][1] as RequestInit).body as string))
      .toEqual({ username: 'u', password: 'p' });
  });

  nonStrictIt('bindPhone 带鉴权头（它是鉴权端点）', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ phone_masked: '+86 138****8000' }));
    await API.bindPhone('c1', '123456');
    expect(headersOf(f.mock.calls[0][1] as RequestInit).Authorization).toBe('Bearer stored-token');
  });

  it('sendPhoneCode 不带鉴权头 —— 它是不鉴权端点，递 token 只是多一个外泄面', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ challenge_id: 'c1', cooldown_sec: 60 }));
    await API.sendPhoneCode('+8613800138000', 'login');
    expect(headersOf(f.mock.calls[0][1] as RequestInit).Authorization).toBeUndefined();
  });

  strictKioskIt('严格盒端下 bindPhone 也不造 Bearer 头 —— 身份只走 HttpOnly cookie', async () => {
    // 这条是本 Task 唯一挡得住「自己再写一个 _authHeader」的闸：
    // 手搓的助手不会有 api.ts:298 那句 `if (isStrictBoxKiosk) return {}`，
    // 于是 localStorage 里那个陈旧 token 会被塞进请求，把盒端的 cookie 契约压过去。
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ phone_masked: '+86 138****8000' }));
    await API.bindPhone('c1', '123456');
    expect(headersOf(f.mock.calls[0][1] as RequestInit).Authorization).toBeUndefined();
  });
});
```

```tsx
// src/context/AuthContext.phone.test.tsx
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

// 夹具形状照抄同目录 AuthContext.test.tsx:1-47（fetch 假体 + localStorage 假体 + 三档门控）。
global.fetch = vi.fn();
const store: Record<string, string> = {};
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v; },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
  },
});
const mockFetch = vi.mocked(global.fetch);

const isKioskBuild = __KIOSK_2D_ONLY__;
const isStrictBoxKiosk = isKioskBuild && import.meta.env.VITE_BOX_SSO_STRICT === 'true';
const nonStrictIt = isStrictBoxKiosk ? it.skip : it;
const strictKioskIt = isStrictBoxKiosk ? it : it.skip;

const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: async () => body } as Response);
const notOk = (status = 401) => Promise.resolve({ ok: false, status, json: async () => ({}) } as Response);

const mountAuth = async () => {
  const hook = renderHook(() => useAuth(), { wrapper: AuthProvider });
  await waitFor(() => expect(hook.result.current.isLoading).toBe(false));
  return hook;
};

describe('AuthContext 手机验证码登录', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
  });

  nonStrictIt('loginByPhone 成功后：存 token、拉到 user、isAuthenticated 为 true', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/auth/phone/login')) return ok({ access_token: 'tok', token_type: 'bearer' });
      if (url.includes('/auth/me')) return ok({ id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: true });
      return notOk();
    });
    const { result } = await mountAuth();
    await act(async () => { await result.current.loginByPhone('c1', '123456'); });
    expect(window.localStorage.getItem('token')).toBe('tok');
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.phone_bound).toBe(true);
  });

  nonStrictIt('/auth/me 失败时不写 token、不置 user —— 半截登录不许伪装成成功', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/auth/phone/login')) return ok({ access_token: 'tok', token_type: 'bearer' });
      return notOk();          // 含挂载时那次 /auth/me 与登录后那次
    });
    const { result } = await mountAuth();
    await act(async () => {
      await expect(result.current.loginByPhone('c1', '123456')).rejects.toThrow();
    });
    expect(window.localStorage.getItem('token')).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  nonStrictIt('refreshUser 重新拉 /auth/me，把 phone_bound 的新值带进来', async () => {
    // 绑定成功后免费额度文案要当场翻面（Task 16），靠的就是这一步。
    window.localStorage.setItem('token', 'tok');
    let bound = false;
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/auth/me')) {
        return ok({ id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: bound });
      }
      return notOk();
    });
    const { result } = await mountAuth();
    expect(result.current.user?.phone_bound).toBe(false);
    bound = true;
    await act(async () => { await result.current.refreshUser(); });
    expect(result.current.user?.phone_bound).toBe(true);
  });

  strictKioskIt('严格盒端不允许直接登录 —— loginByPhone 与 login 同一条口径', async () => {
    // D-U3「盒子什么都不改」：盒端身份是云端账号经 box_sso_bootstrap 交下来的，
    // 本地再开一条发码登录会造出第二个身份来源。
    mockFetch.mockImplementation(() => notOk());
    const { result } = await mountAuth();
    await expect(result.current.loginByPhone('c1', '123456')).rejects.toThrow(/strict box/i);
  });
});
```

- [ ] **Step 2: 跑，确认它红**

```bash
cd katrain/web/ui
npx vitest run src/api.phone.test.ts src/context/AuthContext.phone.test.tsx
```
Expected: FAIL —
`src/api.phone.test.ts` → **5 failed / 1 passed / 1 skipped**：四条 `TypeError: API.sendPhoneCode is not a function`
（第 2 条是 `API.loginByPhone is not a function`）、第 5 条 `API.bindPhone is not a function`；
第 4 条「register 的请求体没有被改动」**天生就绿**（它守的是"别动它"，实现前后都该绿）；
第 7 条按门控 skip。
`AuthContext.phone.test.tsx` → **3 failed / 1 skipped**：
`TypeError: result.current.loginByPhone is not a function` ×2 与 `... .refreshUser is not a function` ×1。

- [ ] **Step 3: 写最小实现**

`src/api.ts`——在 `register`（:465-476）**之后**追加，`register`/`login` 不动。
类型放在文件里既有的 interface 区（`ApiError` 附近）：

```ts
export interface SendCodeResponse { challenge_id: string; cooldown_sec: number }
export interface PhoneLoginResponse { access_token: string; token_type: string }
export interface BindPhoneResponse { phone_masked: string }
```

```ts
  /** 手机相关端点共用的 POST。
   *
   *  后端的失败码要**原样带到 UI** —— 吞成通用错误的话用户看到"操作失败"，
   *  而我们已经知道是"还需等待 42 秒"。
   *
   *  `auth` 只对 bind / set-password 为 true：send-code 与 phone/login 是**不鉴权**端点，
   *  给它们递 token 没有用处，只是多一个外泄面。
   *
   *  鉴权头走本文件 :297 那个模块级 `authHeaders()`，**不要另写一个**：
   *  :279/:298 那句 `if (isStrictBoxKiosk) return {}` 是严格盒端"绝不能自己造 Bearer 头"
   *  的唯一落点，复制一份等于在共享领土里把这条规矩绕过去。
   */
  _phonePost: async (path: string, body: Record<string, unknown>, auth = false): Promise<any> => {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(auth ? authHeaders() : {}) },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      let detail: { code?: string; message?: string; retry_after_sec?: number } = {};
      try {
        const parsed = await response.json();
        if (parsed && typeof parsed.detail === "object" && parsed.detail !== null) detail = parsed.detail;
      } catch { /* 非 JSON 响应（网关 502 之类），detail 保持空 */ }
      const err = new Error(detail.message || `请求失败 ${response.status}`) as Error & {
        code?: string; retryAfterSec?: number; status?: number;
      };
      err.code = detail.code;
      err.retryAfterSec = detail.retry_after_sec;
      err.status = response.status;
      throw err;
    }
    return response.json();
  },

  sendPhoneCode: (phone: string, purpose: 'login' | 'bind' | 'set_password'): Promise<SendCodeResponse> =>
    API._phonePost("/api/v1/auth/phone/send-code", { phone, purpose }),

  loginByPhone: (challengeId: string, code: string): Promise<PhoneLoginResponse> =>
    API._phonePost("/api/v1/auth/phone/login", { challenge_id: challengeId, code }),

  bindPhone: (challengeId: string, code: string): Promise<BindPhoneResponse> =>
    API._phonePost("/api/v1/auth/phone/bind", { challenge_id: challengeId, code }, true),

  setPassword: (challengeId: string, code: string, newPassword: string): Promise<void> =>
    API._phonePost("/api/v1/auth/set-password",
      { challenge_id: challengeId, code, new_password: newPassword }, true),
```

`src/context/AuthContext.tsx`：

1. 本地 `interface User`（:5-11）加一格 —— 没有它，`user.phone_bound` 在 TS 下过不去：
   ```ts
       phone_bound: boolean;
   ```
   （只加这个布尔。原始号由后端 `repo.get_phone_e164` 单点取，永不进 `/auth/me`。）
2. `AuthContextType` 加两项：`loginByPhone: (challengeId: string, code: string) => Promise<void>;`
   与 `refreshUser: () => Promise<void>;`
3. 实现照 `login`（:88-124）的形状：
   ```tsx
       // 与 login 同一条口径：**先把用户资料拉到再返回**，确保 isAuthenticated 在
       // navigate 之前已为 true（:105-108 记的那次"要点两次"就是这么来的）。
       const loginByPhone = async (challengeId: string, code: string) => {
           if (isStrictBoxKiosk) {
               throw new Error('Direct login is disabled in strict box mode');
           }
           const data = await API.loginByPhone(challengeId, code);
           const newToken = data.access_token;
           const meRes = await fetch('/api/v1/auth/me', {
               headers: { Authorization: `Bearer ${newToken}` },
           });
           if (!meRes.ok) {
               throw new Error('Login failed');
           }
           const userData = await meRes.json();
           localStorage.setItem('token', newToken);
           setUser(userData);
           setToken(newToken);
       };

       // 绑定手机成功后要让 user.phone_bound 当场翻面（Task 16 的免费额度文案与
       // 侧栏入口都读它）。严格盒端没有 Bearer，靠同源 cookie，所以头是可选的。
       const refreshUser = useCallback(async () => {
           const stored = isStrictBoxKiosk ? null : localStorage.getItem('token');
           const res = await fetch('/api/v1/auth/me', {
               headers: stored ? { Authorization: `Bearer ${stored}` } : undefined,
           });
           if (res.ok) setUser(await res.json());
       }, []);
   ```
4. Provider 的 `value` 加 `loginByPhone, refreshUser`。

- [ ] **Step 4: 跑，确认它绿**

```bash
cd katrain/web/ui
npx vitest run src/api.phone.test.ts src/context/AuthContext.phone.test.tsx
```
Expected: PASS —— `api.phone.test.ts` 6 passed / 1 skipped（严格盒端那条按门控跳过），
`AuthContext.phone.test.tsx` 3 passed / 1 skipped。合计 **9 passed, 2 skipped**。

再跑严格盒端那一档（把上面跳过的两条真正跑起来）：

```bash
cd katrain/web/ui
VITE_KIOSK_2D_ONLY=true VITE_BOX_SSO_STRICT=true npx vitest run \
  src/api.phone.test.ts src/context/AuthContext.phone.test.tsx
```
Expected: PASS —— `api.phone.test.ts` 6 passed / 1 skipped（这次跳过的是 `nonStrictIt` 那条），
`AuthContext.phone.test.tsx` 1 passed / 3 skipped。合计 **7 passed, 4 skipped**。

- [ ] **Step 5: 变异验证（本 Task 的防线就是这一条）**

把 `_phonePost` 里的 `...(auth ? authHeaders() : {})` 换成手搓的一份：

```ts
      headers: { "Content-Type": "application/json",
                 ...(auth ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {}) },
```

再跑上面那条**严格盒端**命令。Expected: FAIL ——
`严格盒端下 bindPhone 也不造 Bearer 头` 变红（收到 `Bearer stored-token`，期望 `undefined`）。
默认那一档仍然全绿 ⇒ 证明**只有严格盒端那次运行**挡得住这个改法。改回 `authHeaders()`，重跑两条命令确认恢复。

- [ ] **Step 6: 两个构建都要绿**（共享领土的硬要求）

```bash
cd katrain/web/ui
npm run build && npm run build:kiosk-2d
```
Expected: 两个都退出 0；`build:kiosk-2d` 链着的 `verify:kiosk-2d` 也要 0。
（`npm run build` = `tsc -b && vite build`，`tsconfig.app.json` 的 `include` 是 `src` ⇒
`api.ts` 与 `AuthContext.tsx` 都会被类型检查；测试文件被 `exclude` 掉，不在其中。）

- [ ] **Step 7: 提交**

```bash
git status --porcelain
# F12：跑 pytest 会改掉这个 fixture，先还原，别让它混进本次提交
git checkout -- katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
git add katrain/web/ui/src/api.ts \
        katrain/web/ui/src/context/AuthContext.tsx \
        katrain/web/ui/src/api.phone.test.ts \
        katrain/web/ui/src/context/AuthContext.phone.test.tsx
git commit -m "feat(ui): 手机验证码四个 API + loginByPhone/refreshUser

鉴权头走 api.ts:297 已有的模块级 authHeaders(),没有另写一个 ——
:298 那句 if (isStrictBoxKiosk) return {} 是严格盒端'绝不能自己造 Bearer 头'
的唯一落点。配了一条只在 VITE_BOX_SSO_STRICT=true 那一档才跑的用例钉住它,
变异实跑:换成手搓的 Bearer 头后,默认那档全绿、严格那档当场红。

send-code 与 phone/login 是不鉴权端点,_phonePost 的 auth 参数默认 false,
只有 bind / set-password 递 token。

API.register 一个字节不动(D-U2 注册契约不变)⇒ 共享的 RegisterDialog 与
ZenModeApp 不受影响,配了一条断言钉住它的 URL 与请求体。

api.ts 与 AuthContext.tsx 都在共享领土 ⇒ 两个构建都跑过。"
```

---

---

### Task 14: 登录框第三种模式 + 区号选择器 + i18n 登记

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/auth/CountryCodeSelect.tsx`
- Create: `katrain/web/ui/src/galaxy/components/auth/__tests__/renderLoginModal.tsx`（测试装配助手，Task 15/15.5 复用）
- Modify: `katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx`
- Modify: `scripts/batch_translate_galaxy.py`
- Modify: `katrain/i18n/locales/{en,cn,tw,jp,ko,de,es,fr,ru,tr,ua}/LC_MESSAGES/katrain.po`（11 本）
- Test: `katrain/web/ui/src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx`

**Interfaces:**
- Consumes: Task 13 的 `API.sendPhoneCode(phone, purpose)` 与 `useAuth().loginByPhone(challengeId, code)`
- Produces:
  ```tsx
  // CountryCodeSelect.tsx
  export const COMMON_COUNTRY_CODES: { cc: string; label: string }[]
  export default function CountryCodeSelect(props: {
    value: string; onChange: (cc: string) => void; disabled?: boolean;
  }): JSX.Element
  // __tests__/renderLoginModal.tsx
  export const renderLoginModal: (props?: { open?: boolean; onClose?: () => void }) => RenderResult
  // LoginModal.tsx 内部类型（不导出，但 Task 15/15.5 的实现要按它写）
  type LoginMode = 'login' | 'register' | 'phone'
  ```

⚠️ **裸 `render(<LoginModal open onClose={...} />)` 跑不起来**：LoginModal:14-15 一进来就调
`useSettings()`（`SettingsContext.tsx:12-18` 无 Provider 时 `throw`）与 `useAuth()`
（`AuthContext.tsx:153-157` 同形）。同目录 `AuthRequiredDialog.tsx:53-55` 的注释已经写过这个坑。
所以本 Task 先落一个 `renderLoginModal()` 助手（`MemoryRouter` + 真 `SettingsProvider`），
`AuthContext` 用 `vi.mock` 换成可变 `authFixture` —— 形状照抄
`src/galaxy/pages/report/ReportsPage.test.tsx:12-37`。

⚠️ **i18n 默认值一律中文**（Global Constraint 8）。同一个文件里的旧键写英文默认值，**是反例**。
本 Task 顺带把触碰到的旧键（`auth:err_fill_all`/`auth:err_pass_mismatch`/`auth:register_btn`/
`auth:login_btn`/`auth:cancel_btn`/`auth:username`/`auth:password`/`auth:confirm_password`/
`auth:switch_to_login`/`auth:switch_to_register`/`auth:register_title`/`auth:success_register`/
`auth:err_failed`）的默认值改成中文。11 本 `.po` 里的 msgstr **不动**（英/日/韩用户看的是 msgstr）。

- [ ] **Step 1: 写失败的测试**

```tsx
// src/galaxy/components/auth/__tests__/renderLoginModal.tsx
//
// 不是测试文件（文件名不匹配 vitest 的 **/*.test.tsx），但**会被 tsc -b 检查**
// （tsconfig.app.json 的 include 是 src、exclude 只排掉 *.test.ts(x)）——
// 这正好是我们要的：LoginModal 的 props 改了这里会先红。
import { render, type RenderResult } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SettingsProvider } from '../../../../context/SettingsContext';
import LoginModal from '../LoginModal';

/** LoginModal 自己调 useSettings()/useAuth()，两个 hook 没有 Provider 时都直接抛
 *  （SettingsContext.tsx:12-18 / AuthContext.tsx:153-157）。AuthContext 由各测试文件
 *  自己 vi.mock（vi.mock 必须写在测试文件里才会被提升），这里只装 Settings 与 Router。 */
export const renderLoginModal = (
  props: { open?: boolean; onClose?: () => void } = {},
): RenderResult =>
  render(
    <MemoryRouter>
      <SettingsProvider>
        <LoginModal open={props.open ?? true} onClose={props.onClose ?? (() => {})} />
      </SettingsProvider>
    </MemoryRouter>,
  );
```

```tsx
// src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx
import { screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { readFileSync } from 'node:fs';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { API } from '../../../../api';
import { renderLoginModal } from './renderLoginModal';

/* 登录态做成可变 fixture —— 手法与 ReportsPage.test.tsx:24-37 同源。
   useAuth 没有 Provider 时会抛，所以这里整个换掉。 */
let authFixture: {
  user: null;
  isAuthenticated: boolean;
  isLoading: boolean;
  token: null;
  login: ReturnType<typeof vi.fn>;
  loginByPhone: ReturnType<typeof vi.fn>;
  refreshUser: ReturnType<typeof vi.fn>;
  logout: ReturnType<typeof vi.fn>;
};

function resetAuth() {
  authFixture = {
    user: null, isAuthenticated: false, isLoading: false, token: null,
    login: vi.fn().mockResolvedValue(undefined),
    loginByPhone: vi.fn().mockResolvedValue(undefined),
    refreshUser: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
  };
}
resetAuth();

vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

/* MUI Select 的 combobox 没有 labelId 接线，getByRole('combobox', {name}) 解析不出可访问名；
   label 文本又同时出现在缺口边框的 <legend> 里。取法照抄
   src/galaxy/pages/AiSetupPage.test.tsx:143-148 那个现成助手。 */
const comboboxForLabel = (text: string): HTMLElement => {
  const label = screen.getAllByText(text).find((el) => el.tagName === 'LABEL');
  if (!label) throw new Error(`No <label> found with text "${text}"`);
  return within(label.closest('.MuiFormControl-root') as HTMLElement).getByRole('combobox');
};

const toPhoneMode = () => fireEvent.click(screen.getByText('验证码登录'));

/* 「填号 + 点获取验证码」只写这一处：Task 15 会给发码按钮加上"必须先勾同意项"
   这个前置条件，那时**只改这个助手一行**，所有用到它的用例一起跟上。
   （散在五条用例里各写一遍，Task 15 就要改五处，漏一处红一条。） */
const requestCode = (phone = '13800138000') => {
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: phone } });
  fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
};

const fillCodeFlow = async (phone = '13800138000', code = '123456') => {
  requestCode(phone);
  await waitFor(() => expect(API.sendPhoneCode).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: code } });
  fireEvent.click(screen.getByRole('button', { name: '登录' }));
};

describe('LoginModal 手机验证码模式', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetAuth();
    /* SettingsProvider 挂载即 i18n.loadTranslations → API.getTranslations → fetch。
       喂一份空字典：i18n.t(key, 默认值) 于是恒返默认值，下面的中文字面量才能命中
       （i18n.ts:52 `this.translations[key] || defaultText || key`）。
       手法同 GalaxySidebar.test.tsx:41。 */
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('默认是密码模式，能切到验证码模式', () => {
    renderLoginModal();
    expect(screen.getByLabelText('用户名')).toBeInTheDocument();
    toPhoneMode();
    expect(screen.getByLabelText('手机号')).toBeInTheDocument();
    expect(screen.queryByLabelText('密码')).toBeNull();
    expect(screen.queryByLabelText('用户名')).toBeNull();
  });

  it('验证码模式的必填校验说的是手机号，不再被"请填写全部字段"短路', () => {
    /* 旧守卫是 LoginModal.tsx:27 的 `if (!username || !password)` —— 验证码模式下
       两个都空，提交当场短路。这条用例就是钉那一处（review #27）。 */
    renderLoginModal();
    toPhoneMode();
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    expect(screen.getByText('请填写手机号')).toBeInTheDocument();
    expect(screen.queryByText('请填写全部字段')).toBeNull();
  });

  it('发码按钮在倒计时期间禁用并显示剩余秒数', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderLoginModal();
    toPhoneMode();
    requestCode();
    await waitFor(() => expect(screen.getByRole('button', { name: /60 秒/ })).toBeDisabled());
  });

  it('成功文案是"已提交发送"不是"已发送到您的手机"', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderLoginModal();
    toPhoneMode();
    requestCode();
    // 我们没有回执，不知道有没有到 —— 说"已发送到您的手机"是在替运营商担保。
    await waitFor(() => expect(screen.getByText(/已提交发送/)).toBeInTheDocument());
    expect(screen.queryByText(/已发送到您的手机/)).toBeNull();
  });

  it('限流时显示后端给的具体原因，不显示通用"操作失败"', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockRejectedValue(
      Object.assign(new Error('x'), { code: 'sms_cooldown', retryAfterSec: 42, status: 429 }));
    renderLoginModal();
    toPhoneMode();
    requestCode();
    await waitFor(() => expect(screen.getByText(/还需等待 42 秒/)).toBeInTheDocument());
    expect(screen.queryByText(/操作失败/)).toBeNull();
  });

  it('未绑号的 404 给出可走的路，不是干巴巴的失败', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    authFixture.loginByPhone.mockRejectedValue(
      Object.assign(new Error('x'), { code: 'phone_not_bound', status: 404 }));
    renderLoginModal();
    toPhoneMode();
    await fillCodeFlow();
    await waitFor(() => expect(screen.getByText(/还没有绑定账号/)).toBeInTheDocument());
    expect(screen.getByText(/绑定手机号/)).toBeInTheDocument();   // 指得出下一步去哪
  });

  it('区号选择器默认 +86，改成 +81 后取的是 +81 拼出来的号', async () => {
    const send = vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderLoginModal();
    toPhoneMode();
    expect(comboboxForLabel('国家/地区')).toHaveTextContent('+86');
    const user = userEvent.setup();
    await user.click(comboboxForLabel('国家/地区'));
    await user.click(screen.getByRole('option', { name: /\+81/ }));
    requestCode('9012345678');
    // 断言落在"发出去的号"上，不落在"下拉里显示什么"上 —— 后者选中了也可能没接进去。
    await waitFor(() => expect(send).toHaveBeenCalledWith('+819012345678', 'login'));
  });

  it('"忘记密码？"切到验证码登录，不跳独立重置流程', () => {
    renderLoginModal();
    fireEvent.click(screen.getByText('忘记密码？'));
    expect(screen.getByLabelText('手机号')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeInTheDocument();
  });

  it('切回密码模式再切回来，手机号/验证码/倒计时全部复位', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderLoginModal();
    toPhoneMode();
    requestCode();
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    await waitFor(() => expect(screen.getByRole('button', { name: /60 秒/ })).toBeDisabled());
    fireEvent.click(screen.getByText('密码登录'));
    toPhoneMode();
    // 上一位用户的手机号不许留在框里，倒计时也不许还在跑。
    expect(screen.getByLabelText('手机号')).toHaveValue('');
    expect(screen.getByLabelText('验证码')).toHaveValue('');
    expect(screen.getByRole('button', { name: '获取验证码' })).not.toBeDisabled();
  });

  it('本轮新增的每个文案键都有中文默认值', () => {
    /* 正判，不是反判：反判（"扫出所有英文默认值"）必须维护一份旧键豁免名单，
       而同一个 Task 又要求把触碰到的旧键改成中文，两条指令互相打架（review #39/#55）。
       这里只管本轮显式列出的这批键，旧键完全不在射程内。
       两种引号 + 模板串都认；`\bt\(` 同时命中 `i18n.t(` 与解构出来的 `t(`。 */
    const NEW_KEYS = [
      'auth:switch_to_phone', 'auth:switch_to_password', 'auth:forgot_password',
      'auth:phone', 'auth:country_code', 'auth:sms_code', 'auth:get_code',
      'auth:resend_after', 'auth:code_submitted', 'auth:err_phone_required',
      'auth:err_code_required', 'auth:err_phone_not_bound', 'auth:err_cooldown',
      'auth:seconds',
    ];
    const src = [
      new URL('../LoginModal.tsx', import.meta.url),
      new URL('../CountryCodeSelect.tsx', import.meta.url),
    ].map((u) => readFileSync(u, 'utf8')).join('\n');

    const missing: string[] = [];
    const notChinese: string[] = [];
    for (const key of NEW_KEYS) {
      const m = src.match(new RegExp(`\\bt\\(\\s*(['"\`])${key}\\1\\s*,\\s*(['"\`])([\\s\\S]*?)\\2`));
      if (!m) { missing.push(key); continue; }
      if (!/[一-龥]/.test(m[3])) notChinese.push(`${key} => ${m[3]}`);
    }
    expect({ missing, notChinese }).toEqual({ missing: [], notChinese: [] });
  });
});
```

- [ ] **Step 2: 跑，确认它红**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx`
Expected: FAIL（10 条全红）——前 9 条是
`TestingLibraryElementError: Unable to find an element with the text: 验证码登录`
（"忘记密码？"那条是 `... the text: 忘记密码？`），第 10 条是
`ENOENT: no such file or directory, open '.../auth/CountryCodeSelect.tsx'`。
**注意红因已经不是"Provider 缺失当场抛"**——助手把 Provider 装上了，红在该红的地方。

- [ ] **Step 3: 写实现**

**(3a) `CountryCodeSelect.tsx`（新建，不引第三方国家库）**

```tsx
import { MenuItem, TextField } from '@mui/material';
import { i18n } from '../../../i18n';
import { useTranslation } from '../../../hooks/useTranslation';

/** 区号短名单。**不引第三方国家库**（与后端"零新增依赖"同一条约束）：
 *  我们只需要拼出 E.164，真正的号段合法性由运营商说了算，
 *  后端 `normalize_e164` 还会再判一次。 */
export const COMMON_COUNTRY_CODES: { cc: string; label: string }[] = [
  { cc: '+86', label: '中国大陆' }, { cc: '+852', label: '中国香港' },
  { cc: '+853', label: '中国澳门' }, { cc: '+886', label: '中国台湾' },
  { cc: '+1', label: '美国/加拿大' }, { cc: '+81', label: '日本' },
  { cc: '+82', label: '韩国' }, { cc: '+65', label: '新加坡' },
  { cc: '+44', label: '英国' }, { cc: '+61', label: '澳大利亚' },
];

interface Props { value: string; onChange: (cc: string) => void; disabled?: boolean }

const CountryCodeSelect = ({ value, onChange, disabled }: Props) => {
  useTranslation();   // 订阅语言切换，否则换语言时这一块不重渲染
  return (
    <TextField
      select
      margin="dense"
      label={i18n.t('auth:country_code', '国家/地区')}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      sx={{ minWidth: 150 }}
    >
      {COMMON_COUNTRY_CODES.map((c) => (
        <MenuItem key={c.cc} value={c.cc}>{`${c.cc} ${c.label}`}</MenuItem>
      ))}
    </TextField>
  );
};

export default CountryCodeSelect;
```

**(3b) `LoginModal.tsx`：`isRegister` 的 11 处逐一改掉**

`grep -in isregister LoginModal.tsx` → 9 行 11 处（`grep -o` 计数 = 11）。
**一处都不许漏**，尤其第 2 行那道守卫：

| # | 现在（行号） | 改成 |
|---|---|---|
| 1 | :16 `const [isRegister, setIsRegister] = useState(false)`（2 处） | `type LoginMode = 'login' \| 'register' \| 'phone';` + `const [mode, setMode] = useState<LoginMode>('login')`；另加 `cc`(默认 `'+86'`)、`phone`、`smsCode`、`challengeId`、`cooldown` 五个 state |
| 2 | **:27 `if (!username \|\| !password)`**（不含 isRegister，但同属这条改动面） | 按 mode 分支：`login`/`register` 仍查用户名+密码（文案改中文 `请填写全部字段`）；`phone` 查 `!phone` → `请填写手机号`、`!smsCode` → `请填写验证码`。**漏了这处，"未绑号 404"那条用例永远绿不了** |
| 3 | :32 `if (isRegister && password !== confirmPassword)` | `if (mode === 'register' && password !== confirmPassword)` |
| 4 | :39 `if (isRegister) {` | 三支：`if (mode === 'phone') { await loginByPhone(challengeId, smsCode); } else if (mode === 'register') { …register+login… } else { …login… }` |
| 5 | :53 `setIsRegister(false)`（成功后 500ms 的复位） | `setMode('login')`，并把 `phone`/`smsCode`/`challengeId`/`cooldown` 一起清掉（cooldown 清 0 会让下面那个 `useEffect` 自己 `clearTimeout`）。**不清 = 下次打开对话框带着上一位用户的手机号和一个还在跑的倒计时** |
| 6 | :65 `setIsRegister(!isRegister)`（2 处） | 二值取反在三模式下没有意义。换成 `const switchTo = (next: LoginMode) => { setMode(next); setError(''); setSuccessMsg(''); setPassword(''); setConfirmPassword(''); setPhone(''); setSmsCode(''); setChallengeId(''); setCooldown(0); }` |
| 7 | :75 标题三元 | `{mode === 'register' ? i18n.t('auth:register_title', '注册账号') : i18n.t('auth:login_title', '登录智星盒')}`——**登录与验证码两模式共用一个标题**，否则标题里的"验证码登录"会和切换链接的同名文本撞在一起 |
| 8 | :103 `{isRegister && (确认密码框)}` | `{mode === 'register' && (确认密码框)}`；并把用户名/密码两个框整体包进 `{mode !== 'phone' && (…)}`，另加 `{mode === 'phone' && (区号+手机号+获取验证码+验证码)}` |
| 9 | :119 底部链接三元 | 三支：`login` → 三个链接「验证码登录」`switchTo('phone')`、「忘记密码？」`switchTo('phone')`、「还没有账号？注册」`switchTo('register')`；`register` → 「已有账号？登录」`switchTo('login')`；`phone` → 「密码登录」`switchTo('login')` |
| 10 | :126 提交按钮文案三元 | `mode === 'register' ? '注册' : '登录'`（`phone` 与 `login` 同文案，测试按 `{ name: '登录' }` 取） |

**14 个新键各自落在哪**（第 10 条用例逐个查它们，键名写错 = `missing` 非空 = 红）：

| 键 | 默认值 | 落点 |
|---|---|---|
| `auth:switch_to_phone` | `验证码登录` | `login` 模式底部链接 |
| `auth:switch_to_password` | `密码登录` | `phone` 模式底部链接 |
| `auth:forgot_password` | `忘记密码？` | `login` 模式底部链接 |
| `auth:phone` | `手机号` | 手机号 TextField 的 label |
| `auth:country_code` | `国家/地区` | `CountryCodeSelect` 的 label |
| `auth:sms_code` | `验证码` | 验证码 TextField 的 label |
| `auth:get_code` | `获取验证码` | 发码按钮（未倒计时） |
| `auth:resend_after` | `秒后可重发` | 发码按钮（倒计时中，前面拼秒数） |
| `auth:code_submitted` | `验证码已提交发送，请查收短信` | 发码成功的 Alert |
| `auth:err_phone_required` | `请填写手机号` | `phone` 模式守卫 |
| `auth:err_code_required` | `请填写验证码` | `phone` 模式守卫 |
| `auth:err_phone_not_bound` | `这个手机号还没有绑定账号。请先用用户名密码登录，再到左下角「设置 → 绑定手机号」绑定。` | 404 的映射 |
| `auth:err_cooldown` | `验证码发送太频繁，还需等待` | 429 的映射（后面拼秒数） |
| `auth:seconds` | `秒` | 429 映射的尾巴 |

另外两处**不含 `isRegister` 但必须一起改**（review #27 第 4 条）：
- :99 与 :112 现有的 `onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}` —— 手机号与验证码两格也要有。
- 倒计时：
  ```tsx
      // setTimeout 而不是 setInterval：每一跳都自己取消，切模式/卸载时 cooldown 归 0
      // 就再也不排下一跳，不会有"关掉对话框后仍在跑的计时器"。
      useEffect(() => {
          if (cooldown <= 0) return;
          const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
          return () => clearTimeout(id);
      }, [cooldown]);
  ```

发码与错误映射（新增，写在 `handleSubmit` 旁边）：

```tsx
    const fullPhone = `${cc}${phone.trim()}`;

    const handleSendCode = async () => {
        setError(''); setSuccessMsg('');
        if (!phone.trim()) { setError(i18n.t('auth:err_phone_required', '请填写手机号')); return; }
        try {
            const res = await API.sendPhoneCode(fullPhone, 'login');
            setChallengeId(res.challenge_id);
            setCooldown(res.cooldown_sec);
            // 我们拿不到运营商回执 ⇒ 只敢说"已提交发送"。说"已发送到您的手机"
            // 是在替运营商担保一件我们不知道的事(spec §2.3 状态诚实)。
            setSuccessMsg(i18n.t('auth:code_submitted', '验证码已提交发送，请查收短信'));
        } catch (err) { setError(describeError(err)); }
    };

    /** 后端的失败码 → 用户能照着做的一句话。吞成"操作失败"时我们其实已经知道
     *  是"还需等待 42 秒"，那是主动把已知信息扔掉。 */
    const describeError = (err: unknown): string => {
        const e = err as { code?: string; retryAfterSec?: number; message?: string };
        if (e?.code === 'sms_cooldown' || e?.code === 'sms_quota_ip') {
            return `${i18n.t('auth:err_cooldown', '验证码发送太频繁，还需等待')} ${e.retryAfterSec ?? 60} ${i18n.t('auth:seconds', '秒')}`;
        }
        if (e?.code === 'phone_not_bound') {
            return i18n.t('auth:err_phone_not_bound',
                '这个手机号还没有绑定账号。请先用用户名密码登录，再到左下角「设置 → 绑定手机号」绑定。');
        }
        /* 后端把**全部**失败都发成 {code}，且**不带 message**（Task 7-10 的
         * `HTTPException(400, detail={"code": e.code})`）。所以这张表必须覆盖后端会发的
         * 每一个码 —— 漏掉的那个会落到下面的兜底，而兜底在没有 message 时造出的是
         * 「请求失败 400」。**最高频的一次失败就是验证码填错**，它绝不能长这样。 */
        const BY_CODE: Record<string, string> = {
            challenge_code_mismatch: i18n.t('auth:err_code_mismatch', '验证码不对，请检查后重填'),
            challenge_expired:       i18n.t('auth:err_code_expired', '验证码已过期，请重新获取'),
            challenge_consumed:      i18n.t('auth:err_code_used', '这个验证码已经用过了，请重新获取'),
            challenge_locked:        i18n.t('auth:err_code_locked', '错误次数太多，请重新获取验证码'),
            challenge_not_found:     i18n.t('auth:err_code_not_found', '验证码已失效，请重新获取'),
            challenge_purpose_mismatch: i18n.t('auth:err_code_purpose', '验证码用途不对，请重新获取'),
            bad_phone:               i18n.t('auth:err_bad_phone', '手机号格式不对，请检查区号与号码'),
            bad_purpose:             i18n.t('auth:err_bad_purpose', '请求有误，请刷新页面重试'),
            sms_quota_phone:         i18n.t('auth:err_quota_phone', '这个号码今天的验证码已达上限，请明天再试或联系客服'),
            sms_capacity:            i18n.t('auth:err_capacity', '短信通道今日已达上限，请稍后再试，或改用密码登录'),
            sms_provider_failed:     i18n.t('auth:err_provider', '发送失败，请重试'),
            phone_taken:             i18n.t('auth:err_phone_taken', '这个号已经有账号了，可以直接用验证码登录那个账号'),
            already_bound:           i18n.t('auth:err_already_bound', '你的账号已经绑过手机号了。换号请联系客服'),
            phone_unbound:           i18n.t('auth:err_phone_unbound', '请先绑定手机号'),
            phone_disabled_on_device: i18n.t('auth:err_on_device', '请在 modelstella.com 上完成手机号相关操作'),
            need_online_phone:       i18n.t('auth:err_need_online', '请在 modelstella.com 上完成手机号相关操作'),
        };
        if (e?.code && BY_CODE[e.code]) return BY_CODE[e.code];
        return e?.message || i18n.t('auth:err_failed', '操作失败');
    };
```

发码按钮：

```tsx
    <Button onClick={handleSendCode} disabled={loading || cooldown > 0} sx={{ flex: 'none' }}>
        {cooldown > 0
            ? `${cooldown} ${i18n.t('auth:resend_after', '秒后可重发')}`
            : i18n.t('auth:get_code', '获取验证码')}
    </Button>
```

手机号/验证码两格的 label 用 `i18n.t('auth:phone', '手机号')` 与 `i18n.t('auth:sms_code', '验证码')`。

- [ ] **Step 4: 跑，确认它绿**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx`
Expected: PASS（10 条）

- [ ] **Step 5: 变异验证**

两条，逐条跑、跑完各自还原：

| 改动 | 期望变红的用例 |
|---|---|
| 把 `handleSubmit` 的守卫改回 `if (!username \|\| !password) { setError(…'请填写全部字段'); return; }` | `验证码模式的必填校验说的是手机号…` 与 `未绑号的 404 给出可走的路` 两条 |
| 把 `i18n.t('auth:get_code', '获取验证码')` 的默认值改成双引号包的英文 `"Get code"` | `本轮新增的每个文案键都有中文默认值`（`notChinese` 非空）。**这一条是必做的**：旧闸只吃单引号，而文件里唯一那条英文默认值（:119 `auth:switch_to_register`）恰好是双引号 ⇒ 旧闸对现成的反例是瞎的 |

- [ ] **Step 6: 把新键写进 11 本 `.po`**

不做这一步，英/日/韩/俄等 10 种语言的用户在登录框看到的是整段中文
（`i18n.ts:52` 的语义是"键不在字典里就回默认值"），与需求 §0.3「所有国家的手机号都要支持」正好顶上。
按项目 CLAUDE.md 的 i18n 工作流（**目录码是 `cn` 不是 `zh`、`jp` 不是 `ja`**）：

```bash
# 1) 把本 Task 那 14 个 auth:* 键加进 scripts/batch_translate_galaxy.py 的 GALAXY_TRANSLATIONS，
#    每个键 11 个语言各一条（格式照抄该文件里现成的 "grade:brilliant" 那一段）
./.venv/bin/python scripts/batch_translate_galaxy.py
# 2) 只该动这 14 个键 —— 脚本会把它认识的所有键都写一遍，先看差异范围
git diff --stat katrain/i18n/locales
git diff katrain/i18n/locales | grep '^+msgid' | sort -u
# 3) 重生成 .mo（*.mo 在 .gitignore:43 里，不进提交，只为本机跑得起来）
uv run python i18n.py
```
Expected: `git diff` 里新增的 `msgid` **只有本 Task 那 14 个**。多出别的说明脚本把某些旧条目
改回了它自己的版本 —— 把那些 hunk 逐个 `git checkout -p` 掉再继续。

- [ ] **Step 7: 两个构建 + 全量前端单测**

```bash
cd katrain/web/ui && npm test 2>&1 | tail -30
npm run build && npm run build:kiosk-2d
```
Expected: `npm test` 的失败集合与 `superpowers/tracks/phone-login/test-baseline-frontend.txt` 记的**基线一致**
（比的是**失败用例名字集合仍为空集**，不是条数）；两个构建各退出 0。
本 Task 只动 galaxy 文件，kiosk 包吃不到，但 `tsc -b` 是全 `src` 的，所以两个构建都得跑。

- [ ] **Step 8: 提交**

```bash
git status --porcelain
git checkout -- katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
git add katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx \
        katrain/web/ui/src/galaxy/components/auth/CountryCodeSelect.tsx \
        katrain/web/ui/src/galaxy/components/auth/__tests__/renderLoginModal.tsx \
        katrain/web/ui/src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx \
        scripts/batch_translate_galaxy.py \
        katrain/i18n/locales/en/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/cn/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/tw/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/jp/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ko/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/de/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/es/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/fr/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ru/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/tr/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ua/LC_MESSAGES/katrain.po
git commit -m "feat(ui): 登录框加验证码登录模式 + 区号选择器 + 11 本 .po 登记

isRegister 是 9 行 11 处,不是一句话。最要命的是 handleSubmit 第一道守卫
if (!username || !password) —— 验证码模式下两个都空,提交当场短路成
'请填写全部字段',配了一条用例专钉这一处。toggleMode 的二值取反改成显式
switchTo,成功后的复位把手机号/验证码/challenge/倒计时一起清掉。

'忘记密码?'切到验证码登录,不跳独立重置流程 —— 验证码登录本身就是完整的
'忘密码也能进'出路,再做一个免鉴权 reset 是同一件事实现两遍。

三条文案是判据不是措辞:成功说'已提交发送'不说'已发送到您的手机'
(我们没有回执);限流显示后端给的具体秒数不显示'操作失败';未绑号的 404
指得出下一步去哪。

中文默认值那条闸重写成正判(显式列 14 个新键、两种引号都认、扫本 Task 的
两个文件),旧键不进射程。变异实跑:把 auth:get_code 的默认值改成双引号包的
英文当场变红 —— 旧闸只吃单引号,对文件里现成那条双引号英文默认值是瞎的。

新键同时写进 11 本 .po,否则英/日/韩/俄用户在登录框看到整段中文。"
```

---

---

### Task 15: 隐私政策页与手机号收集的单独同意

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/auth/PhoneConsent.tsx`
- Create: `katrain/web/ui/src/galaxy/pages/PrivacyPage.tsx`
- Create: `katrain/web/ui/src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx`
- Create: `katrain/web/ui/src/galaxy/pages/__tests__/PrivacyPage.test.tsx`
- Modify: `katrain/web/ui/src/legal/privacy.ts`（补手机号那一段 + 导出路由常量）
- Modify: `katrain/web/ui/src/GalaxyApp.tsx`（加 `privacy` 路由）
- Modify: `katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx`（挂同意项 + 闸住发码按钮）
- Modify: `katrain/web/ui/src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx`
  （Task 14 产出的测试文件；发码按钮多了 `!consent` 前置条件，`requestCode` 助手补一行勾选同意框）
- Modify: `scripts/batch_translate_galaxy.py` + 11 本 `.po`
- Test: 见上面两个测试文件

**Interfaces:**
- Consumes: Task 14 的 `renderLoginModal()` 助手与 `mode === 'phone'` 分支
- Produces:
  ```tsx
  // src/legal/privacy.ts
  export const PRIVACY_PATH = '/galaxy/privacy'     // PhoneConsent 的 href 与路由测试共用这一个字面量
  export const PRIVACY_TITLE: string                // 已有
  export const PRIVACY_CONTENT: string              // 已有，本 Task 补进手机号那一段
  // src/galaxy/components/auth/PhoneConsent.tsx
  export default function PhoneConsent(props: {
    checked: boolean; onChange: (v: boolean) => void; disabled?: boolean;
  }): JSX.Element        // 外层带 data-testid="phone-consent"
  // src/galaxy/pages/PrivacyPage.tsx
  export default function PrivacyPage(): JSX.Element
  ```

**为什么单独一个 Task**：手机号是个人信息，收集前要**告知**并取得**单独同意**
（《个人信息保护法》十四条/十七条：同意必须在充分知情前提下自愿、明确作出）。
「单独」的操作含义是：**不能与"同意服务条款"打包在一个勾选里，也不能默认勾上。**

⚠️ **`/privacy` 今天不存在，而且不是 404**：`AppRouter.tsx:36-49` 只有 `/kiosk/*`、`/galaxy/*`、
`/record`、`/*`，非 strict 构建下 `/*` 落到 `ZenModeApp`（:46-47）⇒ 点《隐私政策》打开的是**禅模式棋盘**。
一个打开是棋盘的隐私政策链接比没有链接更糟：它看起来像做到了告知义务。

⚠️ **路由落在 `GalaxyApp.tsx` 的路由表里，不落在 `AppRouter.tsx`。** 原因是 D-U3「盒子什么都不改」：
`AppRouter.tsx:44-48` 在严格盒端那一档是 `<Route path="/*" element={<Navigate to="/kiosk" replace />} />`，
往它前面插一条 `/privacy` 会**改掉盒子的路由行为**（盒上访问 `/privacy` 从"跳回 kiosk"变成"渲染政策页"）。
放进 galaxy 路由表则两个包各管各的，且 `LoginModal` 的全部消费者
（`AuthRequiredDialog` / `GalaxySidebar` / `AiSetupPage` / `ReportsPage`）都在 galaxy 下 —— 链接到得了。
即便如此，Step 6 仍然跑两个构建：`tsc -b` 是全 `src` 的。

⚠️ **这一项只做前端的告知与同意闸，不做后端的同意留痕**（那要一张表和一份留存期限策略，本轮不做）。
⇒ **同意状态只挡住提交按钮，不构成可举证的合规记录。不要在任何地方声称它是。** 写进收尾清单。

⚠️ **告知主体名**：`requirements.md §2.10` 已查证【智星盒】不是企业全称的子集（能用的是【万智星】），
而 PIPL 十七条要告知的是**个人信息处理者的名称**。默认文案用 `万智星`（与 `SMS_SIGN_NAME` 同源），
**上线前由 Fan 定稿法定主体全称**——与收尾第 9 条并列交回。

- [ ] **Step 1: 写失败的测试**

```tsx
// src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx
import { screen, fireEvent } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PRIVACY_PATH } from '../../../../legal/privacy';
import { renderLoginModal } from './renderLoginModal';

let authFixture: Record<string, unknown>;
function resetAuth() {
  authFixture = {
    user: null, isAuthenticated: false, isLoading: false, token: null,
    login: vi.fn(), loginByPhone: vi.fn(), refreshUser: vi.fn(), logout: vi.fn(),
  };
}
resetAuth();
vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

const toPhoneMode = () => fireEvent.click(screen.getByText('验证码登录'));
const consentBox = () => screen.getByRole('checkbox', { name: /隐私政策/ }) as HTMLInputElement;

describe('手机号收集的告知与单独同意', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetAuth();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('验证码模式下同意项默认**不**勾选', () => {
    renderLoginModal();
    toPhoneMode();
    expect(consentBox().checked).toBe(false);
  });

  it('未勾选时「获取验证码」不可点 —— 不许先发了码再问', () => {
    renderLoginModal();
    toPhoneMode();
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeDisabled();
  });

  it('勾上之后才可点', () => {
    renderLoginModal();
    toPhoneMode();
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(consentBox());
    expect(screen.getByRole('button', { name: '获取验证码' })).not.toBeDisabled();
  });

  it('同意项是**单独**的 —— 不与服务条款合并成一个勾选', () => {
    renderLoginModal();
    toPhoneMode();
    const label = consentBox().closest('label')!.textContent!;
    // 「我已阅读并同意《服务条款》和《隐私政策》」这种打包写法不合格
    expect(label).not.toMatch(/服务条款|用户协议/);
  });

  it('明写收集什么、干什么用 —— 只给一个链接不算告知', () => {
    renderLoginModal();
    toPhoneMode();
    const text = screen.getByTestId('phone-consent').textContent!;
    expect(text).toMatch(/手机号/);
    expect(text).toMatch(/身份验证|登录/);
  });

  it('密码登录模式下不出现这个同意项 —— 那里不收集手机号', () => {
    renderLoginModal();
    expect(screen.queryByTestId('phone-consent')).toBeNull();
  });

  it('切走再切回来，同意状态复位成未勾 —— 上一位用户的同意不替下一位作数', () => {
    renderLoginModal();
    toPhoneMode();
    fireEvent.click(consentBox());
    expect(consentBox().checked).toBe(true);
    fireEvent.click(screen.getByText('密码登录'));
    toPhoneMode();
    expect(consentBox().checked).toBe(false);
  });

  it('链接指向的就是路由表里那条路径，且默认文案是中文', () => {
    renderLoginModal();
    toPhoneMode();
    const link = screen.getByRole('link', { name: /隐私政策/ }) as HTMLAnchorElement;
    // 断言落在 href 与常量的相等上；"这条路径真的渲染政策页"由 PrivacyPage.test.tsx 证。
    expect(link.getAttribute('href')).toBe(PRIVACY_PATH);

    const NEW_KEYS = ['auth:phone_consent', 'auth:privacy_policy'];
    const src = readFileSync(new URL('../PhoneConsent.tsx', import.meta.url), 'utf8');
    const bad: string[] = [];
    for (const key of NEW_KEYS) {
      const m = src.match(new RegExp(`\\bt\\(\\s*(['"\`])${key}\\1\\s*,\\s*(['"\`])([\\s\\S]*?)\\2`));
      if (!m || !/[一-龥]/.test(m[3])) bad.push(key);
    }
    expect(bad).toEqual([]);
  });
});
```

```tsx
// src/galaxy/pages/__tests__/PrivacyPage.test.tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SettingsProvider } from '../../../context/SettingsContext';
import { PRIVACY_PATH, PRIVACY_CONTENT } from '../../../legal/privacy';
import GalaxyApp from '../../../GalaxyApp';

/* 判据落在**路由**上，不落在链接文本上：grep 一个自己刚写进去的 href="/privacy"
   必然命中、必然报绿，它量的是链接不是可达性（review #26）。
   这里把 GalaxyApp 挂在它在生产里的同一个挂载点 /galaxy/* 下（AppRouter.tsx:38），
   路由表少了那一条时，GalaxyApp 的 `*` 会把它 Navigate 回 /galaxy，断言当场红。 */
const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <SettingsProvider>
        <Routes>
          <Route path="/galaxy/*" element={<GalaxyApp />} />
        </Routes>
      </SettingsProvider>
    </MemoryRouter>,
  );

describe('隐私政策页', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('PRIVACY_PATH 这条路由渲染的是政策页，不是别的页面', () => {
    renderAt(PRIVACY_PATH);
    expect(screen.getByTestId('privacy-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /隐私/ })).toBeInTheDocument();
  });

  it('政策正文写了手机号：收集、用途、存储期限、撤回与删除', () => {
    // 仓里原有的正文一个字没提手机号（只有用户名/对弈记录/设备信息/操作日志），
    // 而本轮开始收手机号了 —— 不补这一段，同意项指向的是一份不覆盖它的文本。
    expect(PRIVACY_CONTENT).toMatch(/手机号/);
    expect(PRIVACY_CONTENT).toMatch(/身份验证|登录验证/);
    expect(PRIVACY_CONTENT).toMatch(/撤回/);
    expect(PRIVACY_CONTENT).toMatch(/删除|注销/);
  });

  it('政策页在 MainLayout 之外 —— 外链打开时用户按定义还没登录', () => {
    /* 断言落在 MainLayout 自己那个容器上（MainLayout.tsx:24 `data-testid="galaxy-main"`），
       **不落在侧栏上**：jsdom 没有 matchMedia，MUI 的 useMediaQuery 一律回落 false
       ⇒ useGalaxySidebar 判成 'mobile' ⇒ 侧栏本来就不渲染，拿它当判据是恒绿的。 */
    renderAt(PRIVACY_PATH);
    expect(screen.queryByTestId('galaxy-main')).toBeNull();
  });
});
```

- [ ] **Step 2: 跑，确认它红**

```bash
cd katrain/web/ui
npx vitest run src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx \
               src/galaxy/pages/__tests__/PrivacyPage.test.tsx
```
Expected: FAIL —— 两个文件都在**收集阶段**就报错，不是逐条失败：
`PhoneConsent.test.tsx` → `SyntaxError: The requested module '/src/legal/privacy.ts' does not
provide an export named 'PRIVACY_PATH'`；
`PrivacyPage.test.tsx` → 同一条（它也 import 了 `PRIVACY_PATH`）。

先只做 (3a) 那一行 `export const PRIVACY_PATH`，再跑一次，这时才是逐条的真红因：
`PhoneConsent.test.tsx` 7 failed / 1 passed
（`Unable to find an accessible element with the role "checkbox" and name /隐私政策/`；
唯一先绿的是「密码登录模式下不出现这个同意项」——它守的是"别越权显示"，实现前后都该绿，
留着是防实现时把 mode 条件写反）；
`PrivacyPage.test.tsx` 3 failed
（前两条 `Unable to find an element by: [data-testid="privacy-page"]`，
第三条 `expect(PRIVACY_CONTENT).toMatch(/手机号/)` 失败——仓里那份正文一个字没提手机号）。

- [ ] **Step 3: 写实现**

**(3a) `src/legal/privacy.ts`**：加一个导出、正文补一节。

```ts
/** 政策页的路由路径。PhoneConsent 的 href 与 PrivacyPage 的路由测试共用这一个字面量 ——
 *  两边各写一份字符串时，改了一边不会有人告诉你另一边坏了。
 *  路径在 galaxy 下而不是站点根：根路由表 AppRouter.tsx 两个包都吃，
 *  往它里面加路由会改掉严格盒端的 `/*` → /kiosk 兜底（D-U3 盒子什么都不改）。 */
export const PRIVACY_PATH = '/galaxy/privacy';
```

`PRIVACY_CONTENT` 的「一、关于如何收集用户的个人信息」下加第 5 条，「四、关于信息存储」下加一条：

```
5、手机号：用于身份验证与登录（短信验证码登录、账号绑定、找回密码），以及依法履行
真实身份信息核验义务。您可以选择不提供手机号，此时仍可使用用户名与密码登录，
但无法使用验证码登录、每周免费复盘额度与发表评论功能。我们不会将您的手机号用于
营销推送，也不会向任何无关第三方提供。
```
```
4、手机号自您绑定之日起保存至账号注销后 30 日内删除或匿名化。您可以随时通过
应用内渠道联系我们撤回对手机号的同意并要求删除，撤回不影响撤回前基于同意
已进行的处理。
```
（正文是法律文本，**只有中文**，不进 `.po`、不做机器翻译 —— 写进收尾清单。）

**(3b) `src/galaxy/pages/PrivacyPage.tsx`（新建）**

```tsx
import { Box, Container, Typography } from '@mui/material';
import { PRIVACY_CONTENT, PRIVACY_TITLE } from '../../legal/privacy';

/** 公开政策页：**不挂在 MainLayout 下**，因为它是从登录框外链打开的，
 *  此时用户按定义还没登录，不该被导航壳与登录守卫拦一道。 */
const PrivacyPage = () => (
  <Box data-testid="privacy-page" sx={{ height: '100%', overflowY: 'auto', bgcolor: 'background.default' }}>
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h5" component="h1" sx={{ mb: 3 }}>{PRIVACY_TITLE}</Typography>
      {/* 正文是一整段带换行的纯文本，用 pre-wrap 保形，不做 Markdown 解析 */}
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9 }}>
        {PRIVACY_CONTENT}
      </Typography>
    </Container>
  </Box>
);

export default PrivacyPage;
```

**(3c) `src/GalaxyApp.tsx`**：在 `<Routes>` 里、`<Route element={<MainLayout />}>` **之前**加一行
（静态段 `privacy` 胜过 MainLayout 里那条 `*` 兜底）：

```tsx
          <Routes>
            {/* 隐私政策独立于 MainLayout：外链打开的公开页，不要求登录、不套导航壳。 */}
            <Route path="privacy" element={<PrivacyPage />} />
            <Route element={<MainLayout />}>
```
并在文件顶部 `import PrivacyPage from './galaxy/pages/PrivacyPage';`。

**(3d) `PhoneConsent.tsx`（新建）**

```tsx
import { Box, Checkbox, FormControlLabel, Link, Typography } from '@mui/material';
import { i18n } from '../../../i18n';
import { useTranslation } from '../../../hooks/useTranslation';
import { PRIVACY_PATH } from '../../../legal/privacy';

/** 手机号收集的告知与**单独**同意。
 *
 * 「单独」的操作含义:不与"同意服务条款"打包成一个勾选,且**默认不勾**。
 * 打包或默认勾上的同意在合规上等于没取得。
 *
 * 只给一个《隐私政策》链接不算告知 —— 收什么、干什么用要写在眼前这一行里。
 *
 * ⚠️ 主体名："智星盒"不是企业全称的子集(requirements §2.10),PIPL 十七条要告知的是
 * 个人信息处理者的**名称**。这里用与短信签名同源的"万智星",**上线前由 Fan 定稿法定全称**。
 */
interface Props { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }

const PhoneConsent = ({ checked, onChange, disabled }: Props) => {
  useTranslation();
  return (
    <Box data-testid="phone-consent" sx={{ mt: 1 }}>
      <FormControlLabel
        control={
          <Checkbox
            checked={checked}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
            inputProps={{ 'aria-label': i18n.t('auth:privacy_policy', '《隐私政策》') }}
          />
        }
        label={
          <Typography variant="body2">
            {i18n.t('auth:phone_consent', '我同意万智星收集我的手机号，用于身份验证与登录。')}
            {' '}
            <Link href={PRIVACY_PATH} target="_blank" rel="noopener noreferrer">
              {i18n.t('auth:privacy_policy', '《隐私政策》')}
            </Link>
          </Typography>
        }
      />
    </Box>
  );
};

export default PhoneConsent;
```

（`inputProps.aria-label` 是让 `getByRole('checkbox', { name: /隐私政策/ })` 取得到 —— MUI 的
可访问名默认来自 label 文本，那一整段太长且含链接，直接给 checkbox 一个稳定的名字。）

**(3e) `LoginModal.tsx`**：
- 新增 `const [consent, setConsent] = useState(false);`
- `mode === 'phone'` 的区块末尾渲染 `<PhoneConsent checked={consent} onChange={setConsent} disabled={loading} />`
- 发码按钮 `disabled={loading || cooldown > 0 || !consent}`
- Task 14 那个 `switchTo` 与成功后的复位里**各加一句 `setConsent(false)`**
  ——**同意状态只在本次会话内有效，不持久化**（持久化就要谈留存期限，本轮不做）。

**(3f) Task 14 的测试助手补一行**（发码按钮多了前置条件，它是唯一要改的地方）：

```tsx
// src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx 里的 requestCode
const requestCode = (phone = '13800138000') => {
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: phone } });
  fireEvent.click(screen.getByRole('checkbox', { name: /隐私政策/ }));   // ← Task 15 加的这一行
  fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
};
```

- [ ] **Step 4: 跑，确认它绿**

```bash
cd katrain/web/ui
npx vitest run src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx \
               src/galaxy/pages/__tests__/PrivacyPage.test.tsx
```
Expected: PASS —— `PhoneConsent.test.tsx` 8 条，`PrivacyPage.test.tsx` 3 条，合计 **11 条**。
顺带 Task 14 那 10 条也要仍然绿（(3f) 那一行就是为它们补的）：

```bash
npx vitest run src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx
```
Expected: PASS（10 条）。**如果没做 (3f)，红的会是那 6 条走 `requestCode` 的用例**
（第 3/4/5/7/9 条直接用它，第 6 条经 `fillCodeFlow` 用它）
（按钮被 `!consent` 禁着，`API.sendPhoneCode` 永远没被调，`waitFor` 超时）——
那不是回归，是本 Task 给按钮加了新前置条件，改助手一处即可。

- [ ] **Step 5: 变异验证**

三条，逐条跑、各自还原：

| 改动 | 期望变红的用例 |
|---|---|
| `useState(false)` → `useState(true)` | `验证码模式下同意项默认**不**勾选` 与 `切走再切回来，同意状态复位成未勾` |
| 发码按钮去掉 `\|\| !consent` | `未勾选时「获取验证码」不可点` |
| 把 `GalaxyApp.tsx` 里那行 `<Route path="privacy" …>` 注释掉 | `PRIVACY_PATH 这条路由渲染的是政策页` 与 `政策页不要求登录`（GalaxyApp 的 `*` 把它 Navigate 回 /galaxy）。**这一条必做**：它证明判据落在路由上而不是链接文本上——同样的改动下，"grep href" 那种写法是全绿的 |

- [ ] **Step 6: 新键写进 11 本 `.po` + 两个构建**

```bash
# auth:phone_consent / auth:privacy_policy 两个键，11 语言各一条
./.venv/bin/python scripts/batch_translate_galaxy.py
git diff katrain/i18n/locales | grep '^+msgid' | sort -u     # 只该出现这两个
uv run python i18n.py
cd katrain/web/ui && npm test 2>&1 | tail -30
npm run build && npm run build:kiosk-2d
```
Expected: 新增 msgid 恰好两个；`npm test` 失败集合与基线一致；两个构建各退出 0。
（政策**正文**只有中文，不进 `.po` —— 法律文本不做机器翻译，写进收尾清单。）

- [ ] **Step 7: 提交**

```bash
git status --porcelain
git checkout -- katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
git add katrain/web/ui/src/galaxy/components/auth/PhoneConsent.tsx \
        katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx \
        katrain/web/ui/src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx \
        katrain/web/ui/src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx \
        katrain/web/ui/src/galaxy/pages/PrivacyPage.tsx \
        katrain/web/ui/src/galaxy/pages/__tests__/PrivacyPage.test.tsx \
        katrain/web/ui/src/legal/privacy.ts \
        katrain/web/ui/src/GalaxyApp.tsx \
        scripts/batch_translate_galaxy.py \
        katrain/i18n/locales/en/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/cn/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/tw/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/jp/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ko/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/de/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/es/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/fr/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ru/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/tr/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ua/LC_MESSAGES/katrain.po
git commit -m "feat(ui): 隐私政策页 + 手机号收集的单独同意

'单独'的操作含义是不与服务条款打包、且默认不勾 —— 打包或默认勾上的同意
在合规上等于没取得,所以这两条各有一条断言。只给一个链接不算告知,
收什么/干什么用要写在眼前那一行里,也有断言。

/privacy 之前**根本不存在**,而且落到的不是 404 是禅模式棋盘
(AppRouter.tsx:46-47 的 /* → ZenModeApp)。这轮建了真路由,判据落在
路由上而不是链接文本上:变异实跑,注释掉那条 Route 时两条用例当场红,
而'grep href' 那种写法在同样的改动下是全绿的。

路由加在 GalaxyApp 的表里、不加在 AppRouter:根表两个包都吃,往它里面插
一条会改掉严格盒端 /* → /kiosk 的兜底(D-U3 盒子什么都不改)。

正文用仓里已有的 src/legal/privacy.ts 当唯一真源(此前零 importer),
把手机号那一节补进去 —— 原文一个字没提手机号,而我们这轮开始收它了。

本轮**只做前端的告知与同意闸,没有后端留痕**(那要一张表和一份留存期限策略)
⇒ 同意状态只挡住提交按钮,不构成可举证的合规记录,已写进收尾清单。
告知主体名暂用与短信签名同源的'万智星',法定全称待 Fan 定稿。"
```

---

---

### Task 16: 绑定手机的用户入口（侧栏设置 + 复盘额度文案 + 发言被拒回执）

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/auth/BindPhoneDialog.tsx`
- Create: `katrain/web/ui/src/galaxy/components/billing/FreeQuotaNotice.tsx`
- Create: `katrain/web/ui/src/galaxy/components/auth/__tests__/BindPhoneDialog.test.tsx`
- Create: `katrain/web/ui/src/galaxy/components/billing/__tests__/FreeQuotaNotice.test.tsx`
- Create: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.bindPhone.test.tsx`
- Create: `katrain/web/ui/src/galaxy/hooks/live/useComments.phone.test.tsx`
- Modify: `katrain/web/ui/src/api.ts`（**共享领土**，加 `getBillingQuota`）
- Modify: `katrain/web/ui/src/api/live.ts`（**共享领土**，失败对象带上 `status`/`code`）
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx`（设置菜单加绑定入口）
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx`（右栏挂免费额度提示）
- Modify: `katrain/web/ui/src/galaxy/hooks/live/useComments.ts`（403 映射成可行动的一句话）
- Modify: `scripts/batch_translate_galaxy.py` + 11 本 `.po`

**Interfaces:**
- Consumes: Task 13 的 `API.bindPhone(challengeId, code)`、`API.sendPhoneCode(phone, 'bind')`、
  `useAuth().refreshUser()`、`useAuth().user.phone_bound`；
  Task 14 的 `CountryCodeSelect`；Task 15 的 `PhoneConsent`；
  Task 11 的 `GET /api/v1/billing/quota` → `free_weekly: { used, allowance, blocked_reason }`；
  Task 12 的 `POST /api/v1/live/matches/{id}/comments` → `403 {detail:{code:'comment_requires_phone'}}`
- Produces:
  ```ts
  // src/api.ts
  export interface FreeWeeklyQuota { used: number; allowance: number; blocked_reason: string | null }
  export interface BillingQuota {
    credits: number; free_weekly: FreeWeeklyQuota;
    billing_enforced: boolean; billing_online: boolean;
  }
  API.getBillingQuota(): Promise<BillingQuota>
  ```
  ```tsx
  // BindPhoneDialog.tsx
  export default function BindPhoneDialog(props: { open: boolean; onClose: () => void }): JSX.Element
  // FreeQuotaNotice.tsx  —— 自带绑定对话框，调用方只放一个 <FreeQuotaNotice />
  export default function FreeQuotaNotice(): JSX.Element | null
  ```

**为什么补这个 Task**（review #9 / #21 / #57）：现在 `API.bindPhone` / `API.setPassword` 是
**共享领土里的零调用者死代码**；后端 Task 11/12 做的 `blocked_reason` / `free_weekly_blocked` /
`comment_requires_phone` **一个读者都没有**；而 Task 18 的验收第 4 项
（「设置里绑定手机 → 复盘页免费额度文案改变」）**无从执行**。三条实测：
`grep -rn 'v1/billing' katrain/web/ui/src` 零命中；`grep -rn 'bindPhone' katrain/web/ui/src` 零命中；
`grep -rn 'chat_requires_identity' katrain/web/ui/src` 零命中（后端 `server.py:2825` 早就在发这个码，
而 `useGameSession.ts:83-130` 的 `onmessage` **没有 `msg.type === 'error'` 这一支**）。
不补这个 Task，Task 11/12 就是"把免费额度和发言权从所有存量账号手里收走，而屏幕上没有任何出路"。

**落点是仓里现成的，不是新发明的：**
- **绑定入口** → `GalaxySidebar.tsx:92-108` 底部账号区那个已存在的「设置」`<Menu>`
  （今天只有语言列表）。galaxy **没有设置页**（`ls src/galaxy/pages` 里没有 Settings/Profile），
  这个菜单就是"设置"在本产品里的实体。⇒ Task 18 的验收文案要写成「侧栏『设置』菜单」而不是「设置页」。
- **免费额度文案** → `ReportsPage.tsx:441` 右栏 `railBody` 里 `report:page_hint` 那句提示的**下一行**。
- **发言被拒** → `CommentSection.tsx:100-105` 已经在渲染 `useComments` 的 `error`，
  映射写在 `useComments.postComment` 的 catch 里。

⚠️ **对局聊天（`chat_requires_phone`）本轮没有读者，这是事实不是遗漏**：
`grep -rn 'chatMessages\|sendChat' katrain/web/ui/src | grep -v '\.test\.'` 只有
`useGameSession.ts` 自己三行 —— **前端根本没有任何组件渲染对局聊天**。
因此不给它造一个只为接错误码的假 UI（那是同一类死代码的第二次）。
写进收尾清单：「对局聊天在前端没有 UI，Task 12 的 `chat_requires_phone` 与既有的
`chat_requires_identity` 一样，目前只对第三方客户端可见」。

⚠️ **`api.ts` 与 `api/live.ts` 都在共享领土** ⇒ 两个构建都要绿。

- [ ] **Step 1: 写失败的测试**

```tsx
// src/galaxy/components/auth/__tests__/BindPhoneDialog.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { readFileSync } from 'node:fs';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SettingsProvider } from '../../../../context/SettingsContext';
import { API } from '../../../../api';
import BindPhoneDialog from '../BindPhoneDialog';

let authFixture: { user: { id: number; username: string; phone_bound: boolean } | null;
                   refreshUser: ReturnType<typeof vi.fn> };
function resetAuth(bound = false) {
  authFixture = {
    user: { id: 1, username: 'u', phone_bound: bound },
    refreshUser: vi.fn().mockResolvedValue(undefined),
  };
}
resetAuth();
vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

const renderDialog = (onClose = vi.fn()) => {
  const r = render(
    <MemoryRouter><SettingsProvider>
      <BindPhoneDialog open onClose={onClose} />
    </SettingsProvider></MemoryRouter>,
  );
  return { ...r, onClose };
};

const consentBox = () => screen.getByRole('checkbox', { name: /隐私政策/ });

describe('BindPhoneDialog', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetAuth();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('同意项默认不勾，未勾时不能发码 —— 与登录框同一条口径', () => {
    renderDialog();
    expect((consentBox() as HTMLInputElement).checked).toBe(false);
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeDisabled();
  });

  it('发码用的 purpose 是 bind，不是 login', async () => {
    // purpose 走错，后端 verify_and_consume 会以 challenge_purpose_mismatch 拒掉，
    // 而用户看到的是一句莫名其妙的失败。
    const send = vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderDialog();
    fireEvent.click(consentBox());
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(send).toHaveBeenCalledWith('+8613800138000', 'bind'));
  });

  it('绑定成功后刷新用户资料并关闭 —— 额度文案要当场翻面', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    const bind = vi.spyOn(API, 'bindPhone').mockResolvedValue({ phone_masked: '+86 138****8000' });
    const { onClose } = renderDialog();
    fireEvent.click(consentBox());
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(API.sendPhoneCode).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: '绑定' }));
    await waitFor(() => expect(bind).toHaveBeenCalledWith('c1', '123456'));
    // 不刷新的话，user.phone_bound 还是 false，复盘页文案和侧栏入口都不会变。
    await waitFor(() => expect(authFixture.refreshUser).toHaveBeenCalled());
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('号被别人占了时说清楚是哪一种失败，并指出可走的路', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    vi.spyOn(API, 'bindPhone').mockRejectedValue(
      Object.assign(new Error('x'), { code: 'phone_taken', status: 409 }));
    renderDialog();
    fireEvent.click(consentBox());
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(API.sendPhoneCode).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: '绑定' }));
    await waitFor(() => expect(screen.getByText(/已被其他账号绑定/)).toBeInTheDocument());
    expect(screen.getByText(/验证码登录/)).toBeInTheDocument();   // 指出那个号可以直接登录
    expect(authFixture.refreshUser).not.toHaveBeenCalled();
  });

  it('本 Task 新增的每个文案键都有中文默认值', () => {
    /* 与 Task 14 第 10 条同一条闸，射程换成本 Task 触碰的四个文件。
       `\bt\(` 同时命中 `i18n.t(`（BindPhoneDialog / FreeQuotaNotice / useComments）
       与解构出来的 `t(`（GalaxySidebar）——同一件事的两种写法，判据不能只认一种。 */
    const NEW_KEYS = [
      'auth:bind_phone', 'auth:bind_btn', 'auth:phone_bound_already', 'auth:err_phone_taken',
      'report:free_quota_phone_required', 'report:free_quota_remaining_prefix',
      'report:free_quota_remaining_suffix', 'report:free_quota_used_up',
      'report:free_quota_unavailable', 'live:comment_requires_phone',
    ];
    const src = [
      new URL('../BindPhoneDialog.tsx', import.meta.url),
      new URL('../../billing/FreeQuotaNotice.tsx', import.meta.url),
      new URL('../../layout/GalaxySidebar.tsx', import.meta.url),
      new URL('../../../hooks/live/useComments.ts', import.meta.url),
    ].map((u) => readFileSync(u, 'utf8')).join('\n');

    const missing: string[] = [];
    const notChinese: string[] = [];
    for (const key of NEW_KEYS) {
      const m = src.match(new RegExp(`\\bt\\(\\s*(['"\`])${key}\\1\\s*,\\s*(['"\`])([\\s\\S]*?)\\2`));
      if (!m) { missing.push(key); continue; }
      if (!/[一-龥]/.test(m[3])) notChinese.push(`${key} => ${m[3]}`);
    }
    expect({ missing, notChinese }).toEqual({ missing: [], notChinese: [] });
  });
});
```

```tsx
// src/galaxy/components/billing/__tests__/FreeQuotaNotice.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SettingsProvider } from '../../../../context/SettingsContext';
import { API } from '../../../../api';
import FreeQuotaNotice from '../FreeQuotaNotice';

let authFixture: { user: { id: number; username: string; phone_bound: boolean } | null;
                   refreshUser: ReturnType<typeof vi.fn> };
function setBound(bound: boolean) {
  authFixture = { user: { id: 1, username: 'u', phone_bound: bound }, refreshUser: vi.fn() };
}
setBound(false);
vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

const quota = (free: { used: number; allowance: number; blocked_reason: string | null }) => ({
  credits: 0, free_weekly: free, billing_enforced: true, billing_online: true,
});

const renderNotice = () => render(
  <MemoryRouter><SettingsProvider><FreeQuotaNotice /></SettingsProvider></MemoryRouter>,
);

describe('FreeQuotaNotice', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setBound(false);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('未绑号（blocked_reason=phone_required）：说得出为什么没有额度，并给得出入口', async () => {
    vi.spyOn(API, 'getBillingQuota').mockResolvedValue(
      quota({ used: 0, allowance: 0, blocked_reason: 'phone_required' }));
    renderNotice();
    await waitFor(() => expect(screen.getByText(/绑定手机号后可享每周免费复盘/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: '绑定手机号' })).toBeInTheDocument();
    // allowance=0 不是"这周用完了" —— 把没资格说成额度耗尽，用户会等到下周（spec §3.1 状态诚实）
    expect(screen.queryByText(/已用完/)).toBeNull();
  });

  it('已绑号且还有额度：报剩余次数', async () => {
    setBound(true);
    vi.spyOn(API, 'getBillingQuota').mockResolvedValue(
      quota({ used: 0, allowance: 1, blocked_reason: null }));
    renderNotice();
    await waitFor(() => expect(screen.getByText(/本周剩余 1 次免费复盘/)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: '绑定手机号' })).toBeNull();
  });

  it('已绑号但本周用完：说"已用完"，不说"去绑手机"', async () => {
    setBound(true);
    vi.spyOn(API, 'getBillingQuota').mockResolvedValue(
      quota({ used: 1, allowance: 1, blocked_reason: null }));
    renderNotice();
    await waitFor(() => expect(screen.getByText(/本周免费复盘次数已用完/)).toBeInTheDocument());
  });

  it('取不到额度时说"取不到"，不装成 0 次也不装成有额度', async () => {
    vi.spyOn(API, 'getBillingQuota').mockRejectedValue(new Error('boom'));
    renderNotice();
    await waitFor(() => expect(screen.getByText(/额度信息暂时取不到/)).toBeInTheDocument());
  });

  it('绑定之后当场重新取数、文案翻面 —— 这就是 Task 18 验收第 4 项', async () => {
    const get = vi.spyOn(API, 'getBillingQuota')
      .mockResolvedValueOnce(quota({ used: 0, allowance: 0, blocked_reason: 'phone_required' }))
      .mockResolvedValueOnce(quota({ used: 0, allowance: 1, blocked_reason: null }));
    const { rerender } = renderNotice();
    await waitFor(() => expect(screen.getByText(/绑定手机号后可享每周免费复盘/)).toBeInTheDocument());
    setBound(true);      // BindPhoneDialog 成功后 refreshUser() 造成的那次翻面
    rerender(
      <MemoryRouter><SettingsProvider><FreeQuotaNotice /></SettingsProvider></MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/本周剩余 1 次免费复盘/)).toBeInTheDocument());
    expect(get).toHaveBeenCalledTimes(2);
  });
});
```

```tsx
// src/galaxy/components/layout/GalaxySidebar.bindPhone.test.tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../../../context/AuthContext';
import { SettingsProvider } from '../../../context/SettingsContext';
import { useGameNavigation } from '../../context/GameNavigationContext';
import type { GalaxySidebarState } from './useGalaxySidebar';
import GalaxySidebar from './GalaxySidebar';

// 夹具形状照抄同目录 GalaxySidebar.test.tsx:10-42（同一组 vi.mock + state() 工厂）。
vi.mock('../../../context/AuthContext', async (importOriginal) => ({
  ...await importOriginal<object>(), useAuth: vi.fn(),
}));
vi.mock('../../context/GameNavigationContext', () => ({ useGameNavigation: vi.fn() }));
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }),
}));

const state = (): GalaxySidebarState => ({
  mode: 'wide-docked', dockedWidth: 240, dockedExpanded: true, overlayOpen: false,
  toggle: vi.fn(), closeOverlay: vi.fn(), toggleButtonRef: { current: null },
});

const renderSidebar = () => render(
  <MemoryRouter><SettingsProvider><GalaxySidebar sidebarState={state()} /></SettingsProvider></MemoryRouter>,
);

const openSettings = () => fireEvent.click(screen.getByRole('button', { name: 'Settings' }));

describe('GalaxySidebar 绑定手机入口', () => {
  beforeEach(() => {
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation: vi.fn() } as never);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() },
    });
  });

  it('已登录未绑号：设置菜单里有「绑定手机号」，点开出绑定对话框', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: false },
      logout: vi.fn(), refreshUser: vi.fn(),
    } as never);
    renderSidebar();
    openSettings();
    fireEvent.click(screen.getByRole('menuitem', { name: '绑定手机号' }));
    expect(screen.getByRole('dialog', { name: '绑定手机号' })).toBeInTheDocument();
  });

  it('已绑号：只报状态、不再给绑定入口（本轮不做换绑/解绑）', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: true },
      logout: vi.fn(), refreshUser: vi.fn(),
    } as never);
    renderSidebar();
    openSettings();
    expect(screen.getByText('手机号已绑定')).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: '绑定手机号' })).toBeNull();
  });

  it('未登录：设置菜单里根本没有这一项 —— 没有账号就没有可绑的对象', () => {
    vi.mocked(useAuth).mockReturnValue({ user: null, logout: vi.fn(), refreshUser: vi.fn() } as never);
    renderSidebar();
    openSettings();
    expect(screen.queryByRole('menuitem', { name: '绑定手机号' })).toBeNull();
    expect(screen.queryByText('手机号已绑定')).toBeNull();
  });
});
```

```tsx
// src/galaxy/hooks/live/useComments.phone.test.tsx
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LiveAPI } from '../../../api/live';
import { useComments } from './useComments';

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok', isAuthenticated: true }),
}));

describe('useComments 未绑手机被拒', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(LiveAPI, 'getComments').mockResolvedValue({ comments: [], total: 0 } as never);
  });

  const mount = async () => {
    const hook = renderHook(() => useComments('m1', true, { pollInterval: 0 }));
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
    return hook;
  };

  it('403 comment_requires_phone → 一句能照着做的中文，不是裸的 Request failed 403', async () => {
    /* 今天这条路是静默的同族形状:后端 server.py:2825 早就在发 chat_requires_identity,
       前端一个读者都没有。评论这条至少会把原始报错串糊到 Alert 里 ——
       用户看到 `Request failed 403: {"detail":{"code":"comment_requires_phone"}}`。 */
    vi.spyOn(LiveAPI, 'createComment').mockRejectedValue(
      Object.assign(new Error('Request failed 403: {"detail":{"code":"comment_requires_phone"}}'),
        { status: 403, code: 'comment_requires_phone' }));
    const { result } = await mount();
    await act(async () => { await result.current.postComment('hi'); });
    expect(result.current.error).toMatch(/绑定手机号/);
    expect(result.current.error).not.toMatch(/Request failed/);
  });

  it('别的失败不被误伤，仍然原样报出来', async () => {
    vi.spyOn(LiveAPI, 'createComment').mockRejectedValue(
      Object.assign(new Error('Request failed 500: boom'), { status: 500 }));
    const { result } = await mount();
    await act(async () => { await result.current.postComment('hi'); });
    expect(result.current.error).toMatch(/Request failed 500/);
  });
});
```

- [ ] **Step 2: 跑，确认它红**

```bash
cd katrain/web/ui
npx vitest run src/galaxy/components/auth/__tests__/BindPhoneDialog.test.tsx \
               src/galaxy/components/billing/__tests__/FreeQuotaNotice.test.tsx \
               src/galaxy/components/layout/GalaxySidebar.bindPhone.test.tsx \
               src/galaxy/hooks/live/useComments.phone.test.tsx
```
Expected: FAIL —— 两种形状，别当成"15 条全红"：

- `BindPhoneDialog.test.tsx` 与 `FreeQuotaNotice.test.tsx` **在收集阶段整文件报错**
  （`Error: Failed to resolve import "../BindPhoneDialog"` /
  `"../FreeQuotaNotice"`），vitest 记成 2 个 suite 级错误，不是 4+5 条用例失败。
- `GalaxySidebar.bindPhone.test.tsx`：2 failed / 1 passed
  （`Unable to find a "menuitem" with the name: 绑定手机号`、
  `Unable to find an element with the text: 手机号已绑定`；第三条「未登录」**这时就是绿的**——
  它守的是"别越权显示"，实现前后都该绿，留着是防实现时把 `user &&` 那个条件写掉）。
- `useComments.phone.test.tsx`：1 failed / 1 passed
  （`expected 'Request failed 403: {"detail":…}' to match /绑定手机号/`；第二条同样是天生绿的守门条）。

⇒ 这一步的真实计数：**2 个文件收集失败（合计 5 + 5 条用例一条都没跑）+ 3 failed + 2 passed**。

（红这一步会有噪声：没有路由的 GalaxyApp/侧栏在 jsdom 里会打几次 stub 过的 fetch，
控制台可能有 `console.error`。判读只看上面那几条断言，不看控制台。）

- [ ] **Step 3: 写最小实现**

**(3a) `src/api.ts`（共享领土）**——加类型与一个 GET：

```ts
export interface FreeWeeklyQuota {
  used: number;
  allowance: number;
  /** 'phone_required' = 没绑手机所以没有资格；null = 有资格。
   *  它与 allowance:0 编码的是**不同的事实**：没资格 vs 有资格但额度为零。
   *  少了它，前端分不出"还没绑号"和"这周用完了"，只能二选一地猜错一半人。 */
  blocked_reason: string | null;
}
export interface BillingQuota {
  credits: number;
  free_weekly: FreeWeeklyQuota;
  billing_enforced: boolean;
  billing_online: boolean;
}
```
```ts
  getBillingQuota: async (): Promise<BillingQuota> => {
    const response = await fetch("/api/v1/billing/quota", { headers: authHeaders() });
    if (!response.ok) throw new ApiError(response.status, `Request failed ${response.status}`);
    return response.json();
  },
```

**(3b) `src/api/live.ts`（共享领土）**——`apiPostAuth` 的失败对象带上 `status`/`code`，
**message 一个字不改**（既有的文本断言照旧有效）：

```ts
  if (!response.ok) {
    const body = await response.text();
    // 报错串保持原样（别处有按文本断言的用例）；另挂两格结构化字段，
    // 好让调用方按 code 分支，而不是去正则匹配这串 JSON。
    const err = new Error(`Request failed ${response.status}: ${body}`) as Error & {
      status?: number; code?: string;
    };
    err.status = response.status;
    try { err.code = JSON.parse(body)?.detail?.code; } catch { /* 非 JSON 响应 */ }
    throw err;
  }
```

**(3c) `BindPhoneDialog.tsx`（新建）**——复用 `CountryCodeSelect` + `PhoneConsent`：

```tsx
import { useEffect, useState } from 'react';
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField } from '@mui/material';
import { API } from '../../../api';
import { useAuth } from '../../../context/AuthContext';
import { i18n } from '../../../i18n';
import { useTranslation } from '../../../hooks/useTranslation';
import CountryCodeSelect from './CountryCodeSelect';
import PhoneConsent from './PhoneConsent';

/** 绑定手机号。与登录框的验证码区块是同一套控件、同一条同意口径，
 *  差别只有两处：purpose 是 'bind'（走错的话后端以 challenge_purpose_mismatch 拒掉，
 *  而用户只看到一句莫名其妙的失败），成功后要 refreshUser() 让 user.phone_bound 翻面
 *  —— 免费额度文案与本入口自身都读它。 */
const BindPhoneDialog = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
  useTranslation();
  const { refreshUser } = useAuth();
  const [cc, setCc] = useState('+86');
  const [phone, setPhone] = useState('');
  const [smsCode, setSmsCode] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [consent, setConsent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  // 关掉即复位：下一次打开不许带着上一位用户的号、上一次的 challenge、还在跑的倒计时。
  useEffect(() => {
    if (open) return;
    setPhone(''); setSmsCode(''); setChallengeId('');
    setConsent(false); setCooldown(0); setError(''); setSuccessMsg('');
  }, [open]);

  const describeError = (err: unknown): string => {
    const e = err as { code?: string; retryAfterSec?: number; message?: string };
    if (e?.code === 'phone_taken') {
      return i18n.t('auth:err_phone_taken',
        '这个手机号已被其他账号绑定。你可以直接用「验证码登录」进入那个账号。');
    }
    if (e?.code === 'sms_cooldown' || e?.code === 'sms_quota_ip') {
      return `${i18n.t('auth:err_cooldown', '验证码发送太频繁，还需等待')} ${e.retryAfterSec ?? 60} ${i18n.t('auth:seconds', '秒')}`;
    }
    return e?.message || i18n.t('auth:err_failed', '操作失败');
  };

  const handleSendCode = async () => {
    setError(''); setSuccessMsg('');
    if (!phone.trim()) { setError(i18n.t('auth:err_phone_required', '请填写手机号')); return; }
    try {
      const res = await API.sendPhoneCode(`${cc}${phone.trim()}`, 'bind');
      setChallengeId(res.challenge_id);
      setCooldown(res.cooldown_sec);
      setSuccessMsg(i18n.t('auth:code_submitted', '验证码已提交发送，请查收短信'));
    } catch (err) { setError(describeError(err)); }
  };

  const handleBind = async () => {
    setError('');
    if (!smsCode.trim()) { setError(i18n.t('auth:err_code_required', '请填写验证码')); return; }
    setLoading(true);
    try {
      await API.bindPhone(challengeId, smsCode.trim());
      await refreshUser();      // 不刷新 = 额度文案与本入口都还停在旧状态
      onClose();
    } catch (err) {
      setError(describeError(err));
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, p: 1, minWidth: 360 } }}>
      <DialogTitle>{i18n.t('auth:bind_phone', '绑定手机号')}</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {successMsg && <Alert severity="success" sx={{ mb: 2 }}>{successMsg}</Alert>}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
          <CountryCodeSelect value={cc} onChange={setCc} disabled={loading} />
          <TextField
            margin="dense" fullWidth variant="outlined" disabled={loading}
            label={i18n.t('auth:phone', '手机号')}
            value={phone} onChange={(e) => setPhone(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleBind()}
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
          <TextField
            margin="dense" fullWidth variant="outlined" disabled={loading}
            label={i18n.t('auth:sms_code', '验证码')}
            value={smsCode} onChange={(e) => setSmsCode(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleBind()}
          />
          <Button onClick={handleSendCode} disabled={loading || cooldown > 0 || !consent} sx={{ flex: 'none' }}>
            {cooldown > 0
              ? `${cooldown} ${i18n.t('auth:resend_after', '秒后可重发')}`
              : i18n.t('auth:get_code', '获取验证码')}
          </Button>
        </Box>
        <PhoneConsent checked={consent} onChange={setConsent} disabled={loading} />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={loading}>{i18n.t('auth:cancel_btn', '取消')}</Button>
        <Button onClick={handleBind} variant="contained" disabled={loading}>
          {i18n.t('auth:bind_btn', '绑定')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default BindPhoneDialog;
```

**(3d) `FreeQuotaNotice.tsx`（新建）**

```tsx
import { useCallback, useEffect, useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import { API, type BillingQuota } from '../../../api';
import { useAuth } from '../../../context/AuthContext';
import { i18n } from '../../../i18n';
import { useTranslation } from '../../../hooks/useTranslation';
import BindPhoneDialog from '../auth/BindPhoneDialog';

/** 复盘页的免费额度提示。**判据取自服务端的 blocked_reason，不取本地的 user.phone_bound**：
 *  额度归属是服务端的事实，本地那格只是它的一份缓存。本地拿来当**刷新触发器**用
 *  （绑定成功 → refreshUser → phone_bound 翻面 → 这里重新取数），不当判据。 */
const FreeQuotaNotice = () => {
  useTranslation();
  const { user } = useAuth();
  const [quota, setQuota] = useState<BillingQuota | null>(null);
  const [failed, setFailed] = useState(false);
  const [bindOpen, setBindOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setQuota(await API.getBillingQuota());
      setFailed(false);
    } catch {
      // 取不到就说取不到。装成 0 次会让用户等到下周，装成有额度会让他在生成时才撞墙。
      setQuota(null);
      setFailed(true);
    }
  }, []);

  // 先取出来再进依赖数组：react-hooks 的 exhaustive-deps 对可选链表达式会报
  // "complex expression in dependency array"。
  const phoneBound = user?.phone_bound;
  useEffect(() => { void load(); }, [load, phoneBound]);

  if (failed) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {i18n.t('report:free_quota_unavailable', '免费额度信息暂时取不到')}
      </Typography>
    );
  }
  if (!quota) return null;

  const { used, allowance, blocked_reason: blocked } = quota.free_weekly;
  const remaining = Math.max(0, allowance - used);

  return (
    <Box sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <Typography variant="body2" color="text.secondary">
        {blocked === 'phone_required'
          ? i18n.t('report:free_quota_phone_required', '绑定手机号后可享每周免费复盘')
          : remaining > 0
            ? `${i18n.t('report:free_quota_remaining_prefix', '本周剩余')} ${remaining} ${i18n.t('report:free_quota_remaining_suffix', '次免费复盘')}`
            : i18n.t('report:free_quota_used_up', '本周免费复盘次数已用完')}
      </Typography>
      {blocked === 'phone_required' && (
        <Button size="small" variant="outlined" onClick={() => setBindOpen(true)}>
          {i18n.t('auth:bind_phone', '绑定手机号')}
        </Button>
      )}
      <BindPhoneDialog open={bindOpen} onClose={() => setBindOpen(false)} />
    </Box>
  );
};

export default FreeQuotaNotice;
```

**(3e) `ReportsPage.tsx`**：`railBody` 里 `report:page_hint` 那段 `<Typography>`（约 :447-449）
**之后**插入 `<FreeQuotaNotice />`，并在顶部加
`import FreeQuotaNotice from '../../components/billing/FreeQuotaNotice';`。
（只挂已登录支；未登录支那块不挂——那里连账号都还没有，`/billing/quota` 会 401。）

**这一处的"真的挂上了"由 Task 18 在真浏览器里证**：`FreeQuotaNotice` 自己的 5 条用例
是单独渲染这个组件跑的，证不了它被挂进了 `ReportsPage`。别在这里补一条"渲染 ReportsPage
看看有没有"的用例——那要把 ReportsPage 那一整套 mock 再抄一遍，而 Task 18 第 4 项
本来就要走这条路。⇒ **Task 18 第 4 项不许跳过**，跳了这一半就没人证。

**(3f) `GalaxySidebar.tsx`**：设置 `<Menu>`（:97-108）里语言列表**之后**加一段，
并在 `<LoginModal .../>` 旁挂上对话框：

```tsx
          {user && <Divider sx={{ my: 0.5 }} />}
          {user && !user.phone_bound && (
            <MenuItem onClick={() => { setBindOpen(true); setSettingsAnchorEl(null); }} sx={{ minWidth: 160, gap: 1 }}>
              <PhoneIphoneIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              <ListItemText primary={t('auth:bind_phone', '绑定手机号')} />
            </MenuItem>
          )}
          {/* 已绑号只报状态，不给"换绑/解绑" —— 本轮没做那条路径，
              而 Task 11 的额度短路（不建 allowance=0 的桶）正是以"不存在解绑"为前提的。 */}
          {user && user.phone_bound && (
            <Box sx={{ px: 2, py: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {t('auth:phone_bound_already', '手机号已绑定')}
              </Typography>
            </Box>
          )}
```
配套：`const [bindOpen, setBindOpen] = useState(false);`、
`import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';`、
`import BindPhoneDialog from '../auth/BindPhoneDialog';`、
以及 `<BindPhoneDialog open={bindOpen} onClose={() => setBindOpen(false)} />`。

**(3g) `useComments.ts`**：`postComment` 的 catch 按 code 分支：

```ts
      } catch (err) {
        // 后端 403 的 detail.code 现在由 api/live.ts 挂在错误对象上。
        // 不分支的话用户看到的是 `Request failed 403: {"detail":{...}}` ——
        // 报错串里其实写着原因，只是没人翻译给他。
        const code = (err as { code?: string } | null)?.code;
        if (code === 'comment_requires_phone') {
          setError(i18n.t('live:comment_requires_phone',
            '发表评论需要先绑定手机号。请在左下角「设置 → 绑定手机号」完成绑定。'));
        } else {
          setError(err instanceof Error ? err.message : 'Failed to post comment');
        }
        return false;
      }
```
顶部加 `import { i18n } from '../../../i18n';`。
（这是 hook 不是组件，`i18n.t` 不带 `useTranslation` 订阅——错误串在事件发生那一刻定型，
而渲染它的 `CommentSection.tsx:26` 已经调了 `useTranslation()`。）

- [ ] **Step 4: 跑，确认它绿**

```bash
cd katrain/web/ui
npx vitest run src/galaxy/components/auth/__tests__/BindPhoneDialog.test.tsx \
               src/galaxy/components/billing/__tests__/FreeQuotaNotice.test.tsx \
               src/galaxy/components/layout/GalaxySidebar.bindPhone.test.tsx \
               src/galaxy/hooks/live/useComments.phone.test.tsx
```
Expected: PASS（15 条：5 + 5 + 3 + 2）

- [ ] **Step 5: 变异验证**

五条，逐条跑、各自还原：

| 改动 | 期望变红的用例 |
|---|---|
| `FreeQuotaNotice` 改成只看 `remaining`（删掉 `blocked === 'phone_required'` 那一支） | `未绑号（blocked_reason=phone_required）…`（会掉进"已用完"那一支）。这条证明 Task 11 的 `blocked_reason` **真的有读者**，不是白加的字段 |
| `handleSendCode` 里 `'bind'` 改回 `'login'` | `发码用的 purpose 是 bind，不是 login` |
| `handleBind` 里去掉 `await refreshUser()` | `绑定成功后刷新用户资料并关闭`；连带 `绑定之后当场重新取数、文案翻面` 在真浏览器里也会失效（Task 18 第 4 项） |
| `useComments` 的 catch 去掉 code 分支 | `403 comment_requires_phone → 一句能照着做的中文` |
| `GalaxySidebar` 的条件 `!user.phone_bound` 改成 `user.phone_bound` | `已登录未绑号…` 与 `已绑号：只报状态…` 两条 |

- [ ] **Step 6: 新键写进 11 本 `.po` + 全量单测 + 两个构建**

本 Task 新增的键：`auth:bind_phone`、`auth:bind_btn`、`auth:phone_bound_already`、
`auth:err_phone_taken`、`report:free_quota_phone_required`、`report:free_quota_remaining_prefix`、
`report:free_quota_remaining_suffix`、`report:free_quota_used_up`、`report:free_quota_unavailable`、
`live:comment_requires_phone`（10 个）。

```bash
./.venv/bin/python scripts/batch_translate_galaxy.py
git diff katrain/i18n/locales | grep '^+msgid' | sort -u    # 只该出现这 10 个
uv run python i18n.py
cd katrain/web/ui && npm test 2>&1 | tail -40
npm run build && npm run build:kiosk-2d
```
Expected: 新增 msgid 恰好 10 个；
`npm test` 的**失败用例名字集合**与 `superpowers/tracks/phone-login/test-baseline-frontend.txt` 一致（仍为空集）
（`ReportsPage.test.tsx` 的 18 条已登录支现在会多渲染一个 `FreeQuotaNotice`，它在 jsdom 里取不到
额度、走"取不到"那一支多出一行文字——那些用例按 testid 与具体文本断言，不该受影响；
**万一有一条红了，它就是本 Task 造成的，不许算进既有噪声**）；两个构建各退出 0。

- [ ] **Step 7: 提交**

```bash
git status --porcelain
git checkout -- katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json
git add katrain/web/ui/src/api.ts \
        katrain/web/ui/src/api/live.ts \
        katrain/web/ui/src/galaxy/components/auth/BindPhoneDialog.tsx \
        katrain/web/ui/src/galaxy/components/auth/__tests__/BindPhoneDialog.test.tsx \
        katrain/web/ui/src/galaxy/components/billing/FreeQuotaNotice.tsx \
        katrain/web/ui/src/galaxy/components/billing/__tests__/FreeQuotaNotice.test.tsx \
        katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx \
        katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.bindPhone.test.tsx \
        katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx \
        katrain/web/ui/src/galaxy/hooks/live/useComments.ts \
        katrain/web/ui/src/galaxy/hooks/live/useComments.phone.test.tsx \
        scripts/batch_translate_galaxy.py \
        katrain/i18n/locales/en/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/cn/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/tw/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/jp/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ko/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/de/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/es/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/fr/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ru/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/tr/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ua/LC_MESSAGES/katrain.po
git commit -m "feat(ui): 绑定手机的用户入口 + 免费额度文案 + 评论被拒回执

补上之前整条链上缺的那一半:API.bindPhone 原本是共享领土里的零调用者死代码,
后端的 blocked_reason / comment_requires_phone 一个读者都没有,
而 Task 18 的验收第 4 项(绑定手机 → 免费额度文案改变)无从执行。

三个落点都是仓里现成的,不是新发明的页面:
- 绑定入口挂在侧栏账号区那个已存在的「设置」菜单(galaxy 没有设置页,
  ls src/galaxy/pages 可查);
- 免费额度文案挂在复盘页右栏 page_hint 的下一行;
- 评论被拒挂在 CommentSection 已经在渲染的那条 error 上。

额度文案的判据取服务端的 blocked_reason,不取本地的 user.phone_bound ——
后者只当刷新触发器。变异实跑:删掉 blocked_reason 那一支,未绑号会掉进
'本周已用完',把'没资格'说成'额度耗尽',用户会等到下周。

对局聊天没有前端 UI(chatMessages/sendChat 零消费者),所以本轮不给
chat_requires_phone 造一个只为接错误码的假界面,已写进收尾清单。

api.ts 与 api/live.ts 在共享领土 ⇒ 两个构建都跑过;live.ts 的报错串
一个字没改,只多挂了 status/code 两格,既有按文本断言的用例不受影响。"
```

---

---

### Task 17: 改密码入口 + 402 的「没绑手机」文案（补两个没有读者的后端产出）

**为什么单独一个 Task**：查出来两处后端做完却没有任何读者——
`POST /auth/set-password`（Task 10 整条）与 `POST /reports` 402 里的 `free_weekly_blocked`（Task 11）。
`API.setPassword` 是共享领土里的零调用者死代码。

**Task 10 力保下来的理由只有在有入口时才成立**：忘了密码的用户能用验证码登录网页版，
但**口令登录是上盒子的唯一路**（kiosk 登录页只有用户名与密码两个控件）——
没有改密码入口，他就被永久挡在自己买的那台设备之外。

**Files:**
- Modify: `katrain/web/ui/src/galaxy/components/auth/BindPhoneDialog.tsx`（加 `purpose` 参数，复用同一个壳）
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx`（设置菜单加一项）
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx`（402 的文案）
- Modify: `scripts/batch_translate_galaxy.py`
- Modify: `katrain/i18n/locales/{en,cn,tw,jp,ko,de,es,fr,ru,tr,ua}/LC_MESSAGES/katrain.po`（11 本）
- Test: `katrain/web/ui/src/galaxy/components/auth/__tests__/SetPasswordDialog.test.tsx`
- Test: `katrain/web/ui/src/galaxy/pages/report/__tests__/ReportsPage.phone402.test.tsx`

**Interfaces:**
- Consumes: `API.setPassword(challengeId, code, newPassword)`（Task 13）、
  `API.sendPhoneCode(phone, 'set_password')`（Task 13）、
  `BindPhoneDialog`（Task 16）、402 的 `detail.free_weekly_blocked`（Task 11）
- Produces: 无（叶子 Task）

- [ ] **Step 1: 写失败的测试**

```tsx
// src/galaxy/components/auth/__tests__/SetPasswordDialog.test.tsx
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsProvider } from '../../../../context/SettingsContext';
import { API } from '../../../../api';
import BindPhoneDialog from '../BindPhoneDialog';

let authFixture = { token: 't', isAuthenticated: true, user: { id: 1, username: 'u', phone_bound: true } };
vi.mock('../../../../context/AuthContext', () => ({
  useAuth: () => authFixture,
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const renderDlg = (purpose: 'bind' | 'set_password') =>
  render(
    <MemoryRouter>
      <SettingsProvider>
        <BindPhoneDialog open purpose={purpose} onClose={() => {}} />
      </SettingsProvider>
    </MemoryRouter>,
  );

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('改密码对话框（与绑定共用一个壳，只换 purpose）', () => {
  it('purpose=set_password 时多一个新密码输入框，绑定模式下没有', () => {
    renderDlg('set_password');
    expect(screen.getByLabelText('新密码')).toBeTruthy();
    cleanup();
    renderDlg('bind');
    expect(screen.queryByLabelText('新密码')).toBeNull();
  });

  it('发码时带的 purpose 是 set_password，不是 bind', async () => {
    const spy = vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderDlg('set_password');
    [...document.querySelectorAll('input[type=checkbox]')].forEach((c) => fireEvent.click(c));
    fireEvent.click(screen.getByText('获取验证码'));
    await waitFor(() => expect(spy).toHaveBeenCalledWith(expect.any(String), 'set_password'));
  });

  it('已绑号的用户不需要重填手机号 —— 号码框是只读的掩码', () => {
    renderDlg('set_password');
    const el = screen.getByLabelText('手机号') as HTMLInputElement;
    expect(el.readOnly).toBe(true);
    expect(el.value).toMatch(/\*{4}/);
  });

  it('未绑手机的用户拿到的是「先去绑定」，不是一个填不了的表单', () => {
    authFixture = { ...authFixture, user: { ...authFixture.user, phone_bound: false } };
    renderDlg('set_password');
    expect(screen.getByText(/先绑定手机号/)).toBeTruthy();
    expect(screen.queryByText('获取验证码')).toBeNull();
    authFixture = { ...authFixture, user: { ...authFixture.user, phone_bound: true } };
  });

  it('成功后把「其它设备上的登录不会掉」这句说出来', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    vi.spyOn(API, 'setPassword').mockResolvedValue(undefined as never);
    renderDlg('set_password');
    [...document.querySelectorAll('input[type=checkbox]')].forEach((c) => fireEvent.click(c));
    fireEvent.click(screen.getByText('获取验证码'));
    await waitFor(() => screen.getByLabelText('验证码'));
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    fireEvent.change(screen.getByLabelText('新密码'), { target: { value: 'newpw123456' } });
    fireEvent.click(screen.getByText('确定'));
    // 这不是客套话:改密码**踢不掉**已签发的 token,而 refresh token 是 90 天。
    // 用户以为改完就安全了 —— 不说出来就是给他一个错的安全承诺。
    await waitFor(() => expect(screen.getByText(/其它设备.*不会.*退出|最长 90 天/)).toBeTruthy());
  });

  it('purpose=set_password 时不渲染同意勾选框，也不要求勾选就能发验证码', async () => {
    /* 裁定:set_password 的前置就是这个号已经绑在这个账号上(未绑号已经改成引导去绑),
       收集手机号的同意在绑定那一刻已经给过 —— 再问一次是为已经持有的数据要同意。 */
    const spy = vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderDlg('set_password');
    expect(screen.queryByRole('checkbox')).toBeNull();
    fireEvent.click(screen.getByText('获取验证码'));
    await waitFor(() => expect(spy).toHaveBeenCalled());
  });

  it('本 Task 新增的每个文案键都有中文默认值', () => {
    /* 与 Task 14/16 同一条闸，射程换成本 Task 触碰的两个文件。
       `\bt\(` 同时命中 `i18n.t(` 与解构出来的 `t(`。 */
    const NEW_KEYS = [
      'auth:set_password_other_devices', 'auth:report_402_phone', 'auth:report_402_credits',
    ];
    const src = [
      new URL('../BindPhoneDialog.tsx', import.meta.url),
      new URL('../../../pages/report/ReportsPage.tsx', import.meta.url),
    ].map((u) => readFileSync(u, 'utf8')).join('\n');

    const missing: string[] = [];
    const notChinese: string[] = [];
    for (const key of NEW_KEYS) {
      const m = src.match(new RegExp(`\\bt\\(\\s*(['"\`])${key}\\1\\s*,\\s*(['"\`])([\\s\\S]*?)\\2`));
      if (!m) { missing.push(key); continue; }
      if (!/[一-龥]/.test(m[3])) notChinese.push(`${key} => ${m[3]}`);
    }
    expect({ missing, notChinese }).toEqual({ missing: [], notChinese: [] });
  });
});
```

```tsx
// src/galaxy/pages/report/__tests__/ReportsPage.phone402.test.tsx
// 402 的 detail.free_weekly_blocked === 'phone_unbound' 时,
// 文案必须是「绑定手机号可每周免费复盘一局」而不是只弹充值。
// 判据:把 free_weekly_blocked 那一支删掉,这条当场变红。
it('402 且 free_weekly_blocked=phone_unbound 时给的是绑定引导，不是只弹充值', async () => {
  mockCreateReport.mockRejectedValue(Object.assign(new Error(''), {
    status: 402,
    detail: { code: 'insufficient_credits', free_weekly_blocked: 'phone_unbound' },
  }));
  renderReportsPage();
  fireEvent.click(await screen.findByText('生成复盘'));
  await waitFor(() => expect(screen.getByText(/绑定手机号.*每周免费/)).toBeTruthy());
});

it('402 但已绑手机时不出现绑定引导（只是真的没钱）', async () => {
  mockCreateReport.mockRejectedValue(Object.assign(new Error(''), {
    status: 402,
    detail: { code: 'insufficient_credits', free_weekly_blocked: null },
  }));
  renderReportsPage();
  fireEvent.click(await screen.findByText('生成复盘'));
  await waitFor(() => expect(screen.getByText(/余额不足|充值/)).toBeTruthy());
  expect(screen.queryByText(/绑定手机号.*每周免费/)).toBeNull();
});
```

- [ ] **Step 2: 跑，确认它红**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/components/auth/__tests__/SetPasswordDialog.test.tsx src/galaxy/pages/report/__tests__/ReportsPage.phone402.test.tsx`
Expected: FAIL — `BindPhoneDialog` 不接受 `purpose` prop、也没有 `requireConsent` 分支、
i18n 键还没登记（7 条全红）；402 两条红在找不到文案。

- [ ] **Step 3: 写最小实现**

`BindPhoneDialog` 加 `purpose: 'bind' | 'set_password'`（默认 `'bind'`）：
- `set_password` 时手机号框只读、值取 `mask` 后的号（来自 `/auth/me` 的派生字段或绑定时的返回），
  多渲染一个「新密码」框，提交调 `API.setPassword`；
- `set_password` 且 `!user.phone_bound` ⇒ 整个表单换成一句「先绑定手机号」+ 一个跳到绑定的按钮；
- 成功文案带上那句 90 天，用
  `i18n.t('auth:set_password_other_devices', '密码已经改好了。已经登录的设备不会被强制退出，最长 90 天内仍可继续使用。')`
  （默认值与 Task 10 Produces 里给的原文一致）。

**同一个壳还要处理同意闸**（裁定：`set_password` 的前置就是这个号已经绑在这个账号上——
未绑号 Step 3 上一条已经改成引导去绑——收集手机号的同意在绑定那一刻已经给过，
再问一次是为已经持有的数据要同意，所以这个模式下不渲染同意区、也不拿 `!consent` 卡发码按钮）：
`BindPhoneDialog` 再加一个 `requireConsent?: boolean`（默认 `true`），`purpose='set_password'` 时传 `false`：
`{requireConsent && <PhoneConsent checked={consent} onChange={setConsent} disabled={loading} />}`，
发码按钮的 `disabled` 从 `!consent` 改成 `(requireConsent && !consent)`。
`purpose='bind'` 时不传这个新 prop、走默认值 `true`——Task 16 的 `BindPhoneDialog.test.tsx` 不用改，
它测的正是默认值这条路径，Step 6 的 `npx vitest run` 会把它当回归一起跑绿。

`GalaxySidebar` 的设置菜单在「绑定手机号」下面加「修改密码」，`purpose='set_password'` 打开同一个对话框。

`ReportsPage` 的 402 分支读 `detail.free_weekly_blocked`：

```tsx
// 402 有两种,用户该做的事完全不同:没绑手机 → 去绑(一步就有免费额度);
// 真没钱 → 去充值。合成一句"余额不足"是把前者的出路藏起来。
const blocked = (err as { detail?: { free_weekly_blocked?: string | null } })?.detail?.free_weekly_blocked;
setError(blocked === 'phone_unbound'
  ? i18n.t('auth:report_402_phone', '绑定手机号可每周免费复盘一局。到左下角「设置 → 绑定手机号」。')
  : i18n.t('auth:report_402_credits', '余额不足，请先充值。'));
```

- [ ] **Step 4: 跑，确认它绿**

Run: 同 Step 2
Expected: PASS（9 条）

- [ ] **Step 5: 变异验证**

| 拆掉什么 | 应该红的用例 |
|---|---|
| `purpose` 传参（写死 `'bind'`） | 发码 purpose 那条 |
| `!user.phone_bound` 那一支 | 未绑手机那条 |
| 成功文案里的 90 天那句 | 成功文案那条 |
| 402 里 `free_weekly_blocked` 那一支 | 402 两条同时红 |
| `requireConsent` 判断（发码按钮永远卡 `!consent`，PhoneConsent 永远渲染） | 不渲染同意勾选框那条 |
| 把 `i18n.t('auth:report_402_phone', …)` 的默认值改成双引号包的英文 | `本 Task 新增的每个文案键都有中文默认值`（`notChinese` 非空） |

- [ ] **Step 6: 新键进 11 本 `.po` + 两个构建**

本 Task 新增的键：`auth:set_password_other_devices`、`auth:report_402_phone`、
`auth:report_402_credits`（3 个）。

```bash
./.venv/bin/python scripts/batch_translate_galaxy.py
git diff katrain/i18n/locales | grep '^+msgid' | sort -u    # 只该出现这 3 个
uv run python i18n.py
cd katrain/web/ui && npx vitest run && npm run build && npm run build:kiosk-2d
```
Expected: 新增 msgid 恰好 3 个；`npx vitest run` 的失败用例名字集合与
`superpowers/tracks/phone-login/test-baseline-frontend.txt` 一致（仍为空集）；两个构建各退出 0。

- [ ] **Step 7: 提交**

```bash
git status --porcelain   # 先还原 engine_game_state.json（Global Constraint #11）
git add katrain/web/ui/src/galaxy/components/auth/BindPhoneDialog.tsx \
        katrain/web/ui/src/galaxy/components/auth/__tests__/SetPasswordDialog.test.tsx \
        katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx \
        katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx \
        katrain/web/ui/src/galaxy/pages/report/__tests__/ReportsPage.phone402.test.tsx \
        scripts/batch_translate_galaxy.py \
        katrain/i18n/locales/en/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/cn/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/tw/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/jp/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ko/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/de/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/es/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/fr/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ru/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/tr/LC_MESSAGES/katrain.po \
        katrain/i18n/locales/ua/LC_MESSAGES/katrain.po
git commit -m "feat(ui): 改密码入口 + 402 的「没绑手机」文案

补两处后端做完却没有任何读者的产出:/auth/set-password 整条(Task 10)与
402 的 free_weekly_blocked(Task 11)。API.setPassword 原本是共享领土里的
零调用者死代码。

Task 10 当初力保下来的理由只有在有入口时才成立:忘了密码的用户能用验证码
登录网页版,但口令登录是上盒子的唯一路 —— 没有改密码入口,他就被永久挡在
自己买的那台设备之外。

402 有两种,用户该做的事完全不同:没绑手机 → 去绑(一步就有免费额度);
真没钱 → 去充值。合成一句「余额不足」是把前者的出路藏起来。

成功文案必须说「其它设备上的登录最长 90 天不会掉」:改密码踢不掉已签发的
token,而 refresh token 是 90 天 —— 不说出来就是给用户一个错的安全承诺。

set_password 模式不重复要求同意:前置就是这个号已经绑在这个账号上,收集手机号
的同意在绑定那一刻已经给过。BindPhoneDialog 加 requireConsent(默认 true),
只有 set_password 传 false;bind 路径走默认值不受影响,Task 16 的
BindPhoneDialog.test.tsx 不用改。

三个新键(auth:set_password_other_devices / auth:report_402_phone /
auth:report_402_credits)同时写进 11 本 .po,否则非中文用户在这两处看到
的是整段中文,与需求 §0.3「所有国家的手机号都要支持」顶上。"
```

---

### Task 18: 真浏览器验收 + 基线比对 + 两个构建 + 部署前置

**Files:**
- Create: `tests/web_ui/test_compose_declares_sms_provider.py`
- Create: `superpowers/tracks/phone-login/verification.md`

（`docker-compose.yml` 那一行由 Task 5 落，本 Task 不再重复改它 —— 只断言它在、并对它做变异验证。）

**Interfaces:**
- Consumes:
  - Task 5：`assert_sms_provider_is_configured(mode: str, provider: str, allow_console: bool = False) -> None`
    （接在 `server.py:176` 的 `assert_secret_key_is_safe(...)` 紧邻下一行）、`settings.SMS_PROVIDER`
    （env `KATRAIN_SMS_PROVIDER`）、以及 Task 5 为 console 开的那个显式放行开关
    （env `KATRAIN_SMS_ALLOW_CONSOLE`，默认关、生产不设）
  - Task 7：`POST /api/v1/auth/phone/send-code`（JSON `{"phone","purpose"}` → `{"challenge_id","cooldown_sec"}`）
  - Task 8：`POST /api/v1/auth/phone/login`；未绑号时返 `{"code":"phone_not_bound"}` 那一支
  - Task 9：`POST /api/v1/auth/phone/bind`（鉴权）
  - Task 8：pydantic `User.phone_bound: bool`（`/api/v1/auth/register` 的响应体里就能看见）
  - Task 11：`GET /api/v1/billing/quota` → `free_weekly.blocked_reason`（`"phone_required"` / `None`）
  - Task 12：对局 WS 的 `{"type":"error","code":"chat_requires_phone"}`
  - Task 14/15：登录框第三种模式（「验证码登录」）、`PhoneConsent` 里指向隐私政策页的链接
  - Task 16（绑定手机的用户入口）：galaxy 侧边栏账号区的绑定入口、`BindPhoneDialog`、
    `ReportsPage` 对 `free_weekly.blocked_reason` 的读取
- Produces:
  - `superpowers/tracks/phone-login/verification.md`（收尾清单里「本轮无 UI / 未验」那几条引用它取证）
  - `tests/web_ui/test_compose_declares_sms_provider.py::test_web_service_declares_the_sms_provider_env`
    等 3 条，守住「合并后测试机还起得来」

**这个 Task 为什么排在最后而不是可选**：Task 5 的 fail-fast 闸让 `KATRAIN_SMS_PROVIDER`
为空的服务端**拒绝启动**，而这个变量今天在两台线上机器上都没设。Step 8–10 不是收尾装饰，
是这条分支能不能合的前置条件。

- [ ] **Step 1: 先跑 Task 11 主动改动的那三条，确认它们的新状态是绿的**

Task 11 把 `free_weekly` 的形状和「未绑号不走免费分支」落地之后，会**主动弄红三条今天绿的
测试**（review-findings [50] 点名）。这三条必须由 Task 11 自己改好；在基线比对之前先单独跑一遍，
把它们从「基线噪声」里摘出来 —— 否则下一步的 `comm` 一旦吐出这三个名字，最省事的做法就是
把它们塞进 `test-baseline.txt`，那等于一次退役三条真断言。

```bash
cd /Users/fan/Repositories/katrain-phone-login
./.venv/bin/python -m pytest \
  "tests/web_ui/test_billing_api.py::test_quota_endpoint_shape" \
  "tests/web_ui/test_report_charging.py::test_first_report_of_the_week_is_free_second_is_charged" \
  "tests/web_ui/test_report_charging.py::test_free_report_records_its_period_not_a_charge_ref" \
  -q
```
Expected: PASS（3 条）。

红了就回 Task 11，**不要动 `test-baseline.txt`**。三条各自该变成什么样：
`test_quota_endpoint_shape` 的整字典相等要改成子集比对 + 显式 `blocked_reason is None`；
`test_report_charging.py` 那两条的 `app_with_game` / `_make_user` 夹具要给用户绑上号
（它们建用户走的是 `SQLAlchemyUserRepository`，`phone_e164` 是 NULL，不绑号就走不到免费分支）。

- [ ] **Step 2: 全量 pytest 与分支基线比对**

```bash
cd /Users/fan/Repositories/katrain-phone-login
./.venv/bin/python -m pytest tests -q 2>&1 | tee /tmp/pytest-phone-after.log | tail -3
grep -E '^(FAILED|ERROR) tests/' /tmp/pytest-phone-after.log \
  | sed -E 's/^(FAILED|ERROR) //; s/ - .*$//' | LC_ALL=C sort -u > /tmp/after.txt
LC_ALL=C sort -u superpowers/tracks/phone-login/test-baseline.txt > /tmp/base.txt
comm -23 /tmp/after.txt /tmp/base.txt
git diff --stat -- superpowers/tracks/phone-login/test-baseline.txt
```
Expected: `comm -23` **输出为空**（新增失败为零）；`git diff --stat` 也**为空**
（基线文件在这条分支上一个字节都不许改 —— 改它就是把新增失败洗成既有噪声）。

两边都要 `LC_ALL=C sort` 再比：`test-baseline.txt` 当初是在 `en_US.UTF-8` collation 下排的
（`LC_ALL=C sort -c` 当场报 `disorder`，实测在第 35 行），直接拿它当 `comm` 的第二个操作数，
两边 collation 不一致会吐出**假的新增失败**。

比的是**失败名字集合**不是条数 —— 条数相同也可能是「修好一条、弄坏一条」。

**`tests/conftest.py` 在这一轮被改过**（Task 5）：它注入 `os.environ.setdefault("KATRAIN_SMS_PROVIDER",
"aliyun")`，并把两个凭据 env（`KATRAIN_SMS_ACCESS_KEY_ID` / `KATRAIN_SMS_ACCESS_KEY_SECRET`）强制清空
（不是 `setdefault`，是直接赋空串 —— 防止漏打桩的用例拿开发机/线上机器 shell 里可能存在的真凭据真的发短信）。
**不注入 `KATRAIN_SMS_ALLOW_CONSOLE`**：闸禁止 server 模式用 `console`，让 pytest 进程跑 `console`
等于整套测试从不走生产形状那条路，还要求测试进程设一个**生产绝不许存在**的放行开关。
没有这一改，闸接进 `_lifespan_server` 之后所有建 app 的用例会集体红，这次比对根本跑不到底。确认它在：

```bash
grep -n "KATRAIN_SMS_PROVIDER\|KATRAIN_SMS_ALLOW_CONSOLE" tests/conftest.py
```
Expected: `KATRAIN_SMS_PROVIDER` 命中，且注入方式是 `os.environ.setdefault(...)`、值是
`"aliyun"`（不是给某个 settings 实例赋值 —— `test_lobby_api.py` / `test_social_api.py` 会
`importlib.reload(config)`，打在旧实例上的补丁 reload 之后就没了）；
`KATRAIN_SMS_ALLOW_CONSOLE` 在 `tests/conftest.py` 里**零命中**（pytest 进程不需要、也不该有这个开关）。

- [ ] **Step 3: 两个前端构建 + 全量 vitest**

```bash
cd /Users/fan/Repositories/katrain-phone-login/katrain/web/ui
npm run build && npm run build:kiosk-2d
npx vitest run 2>&1 | tail -20
```
Expected: 两个构建都退出 0（`build:kiosk-2d` 链着的 `verify:kiosk-2d` 也要 0）；vitest `0 failed`。

两个都要跑：本轮碰的 `src/api.ts`、`src/context/AuthContext.tsx` 是**共享领土**，kiosk 包也吃；
`build` 与 `build:kiosk-2d` 的 outDir 不同（`../static` vs `../static-kiosk-2d`，
`vite.config.ts:37`），先后顺序不互相覆盖。`npm run build` 的产物就是 Step 4/5 要跑的那份 —— 
所以这一步必须排在真浏览器验收之前，`python -m katrain --ui web` 复用已有 dist、不会自己重建。

vitest 红了：前端没有基线文件，所以判据取保守的那一侧 ——
`git log --oneline --name-only origin/develop..HEAD -- 'katrain/web/ui/src/**'` 列出本轮碰过的前端文件，
红的那条只要 import 链上有其中任何一个（`api.ts` / `AuthContext.tsx` 尤其要当心，
半个前端都 import 它们），就当作**本轮造成的**，不许推给既有噪声。

- [ ] **Step 4: 起本地验收服务**

`KATRAIN_SMS_PROVIDER` 现在**不能只填 `console`**：Task 5 的闸在 `server` 模式下拒绝裸 console
（否则验证码会印进生产日志，谁能读日志谁就能登任何人的账号）。两条路只有一条能走：

- ❌ **`KATRAIN_MODE=board` 不行**，四个理由都是硬的：
  ⓪ `server.py:104-109` 的 `lifespan` 在 board 模式下走 `_lifespan_board`、**根本不进
     `_lifespan_server`** ⇒ 闸压根没执行。用它"绕过"闸，等于把验收挪到一条没有闸的路上，
     而验收要证的恰恰是有闸那条能跑；
  ① `server.py:853` 会改去 serve `static-kiosk-2d/`，那份包里**根本没有 galaxy**
     （`AppRouter.tsx` 的 `/galaxy/*` 在 `__KIOSK_2D_ONLY__` 下被 DCE 掉），验收要走的登录框、
     复盘页一个都不在；
  ② `_lifespan_board` 无条件建 `RemoteAPIClient`（`server.py:446`）⇒ `app.state.remote_client`
     非 None，`/auth/register`、四个手机端点全部转发或 503
     （Task 7–10 的 `*_503_on_board_and_does_not_forward` 守的就是这个）；
  ③ `config.py:194` 会把 `DATABASE_URL` 强拉回本地 sqlite，验的不再是服务端那条路。
- ✅ **本地绕法：显式打开 console 放行开关**（`KATRAIN_SMS_ALLOW_CONSOLE=1`）。
  **这不是 `tests/conftest.py` 走的那条路** —— pytest 进程注入的是 `KATRAIN_SMS_PROVIDER=aliyun`
  且不设放行开关（见 Step 2）；本机验收起的是一个**真服务进程**（`python -m katrain --ui web`），
  这里改用 `console` + 放行开关是为了能在服务端日志里**读到验证码**（`aliyun` 空凭据只会 502，
  拿不到码，V1–V4 那几项走不下去）。两条路服务的目的不同，并存不矛盾：pytest 要证的是「闸接在
  生产路径上、且默认拒 console」；这里要的是「本机能人工走一遍完整流程」。
  （测试进程的 `KATRAIN_MODE` 默认就是 `"server"`，`config.py:83/174`）。

先探一下闸放不放行，**不要靠猜变量名**：

```bash
cd /Users/fan/Repositories/katrain-phone-login
KATRAIN_SMS_PROVIDER=console KATRAIN_SMS_ALLOW_CONSOLE=1 \
KATRAIN_SECRET_KEY=acceptance-only-secret-key-0123456789abcdef \
./.venv/bin/python - <<'PY'
from katrain.web.core.config import assert_sms_provider_is_configured, settings
assert_sms_provider_is_configured(settings.KATRAIN_MODE, settings.SMS_PROVIDER, settings.SMS_ALLOW_CONSOLE)
print("mode=", settings.KATRAIN_MODE, "provider=", settings.SMS_PROVIDER)
PY
```
Expected: 打印 `mode= server provider= console`，不抛异常。
抛 `RuntimeError` 就先确认第三个实参传了 `settings.SMS_ALLOW_CONSOLE`、且 `KATRAIN_SMS_ALLOW_CONSOLE=1`
确实在这个进程的环境里 —— 开关名字本来就是对的（Task 5 落的就叫这个），错的通常是这一行没把它传进去。

起服务（后台跑，日志落盘；`--log-level info`；`--disable-engine` 免得等一个本机没有的 KataGo）：

```bash
mkdir -p /tmp/phone-acc
cp ~/.katrain/config.json /tmp/phone-acc/katrain-config.bak 2>/dev/null || true   # 退出时会被改写
cd /Users/fan/Repositories/katrain-phone-login
KATRAIN_SMS_PROVIDER=console KATRAIN_SMS_ALLOW_CONSOLE=1 \
KATRAIN_SECRET_KEY=acceptance-only-secret-key-0123456789abcdef \
KATRAIN_DATABASE_URL=sqlite:////tmp/phone-acc/acc.sqlite3 \
./.venv/bin/python -m katrain --ui web --host 127.0.0.1 --port 8099 \
  --disable-engine --log-level info > /tmp/phone-acc/server.log 2>&1 &
echo $! > /tmp/phone-acc/server.pid
curl -sf --retry 30 --retry-delay 1 --retry-connrefused http://127.0.0.1:8099/health
```
Expected: `/health` 返 200。

三件事是刻意的：**换端口 8099**（别撞开发机上跑着的 8001）、**换库到 `/tmp`**
（验收要注册账号、要写 `sms_challenges`，不许污染工作区的 `db.sqlite3`）、
**备份 `~/.katrain/config.json`**（本地 `--ui web` 退出时会改写它）。

造两个账号 —— 一个全程不绑号，一个用来验绑定：

```bash
for u in acc_unbound acc_bind; do
  curl -s -X POST http://127.0.0.1:8099/api/v1/auth/register \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$u\",\"password\":\"pw-acceptance-$u\"}" ; echo
done
```
Expected: 两条都返回 JSON user 对象，且**各含 `"phone_bound": false`**。
这一行顺带就是 Task 8 的落地证据：`phone_bound` 没进 pydantic `User` 的话它根本不会出现在响应里
（pydantic v2 默认 `extra='ignore'`，`_to_dict` 里多给的键会被静默丢掉）。

若 Step 5 的 V5 里 `POST /api/session` 返 503，去掉 `--disable-engine` 重起一次
（本机不需要真 KataGo，会话建得起来就够）。

- [ ] **Step 5: 真浏览器逐项走**

用 gstack 的 `/browse`（项目规定：所有网页浏览走它，不用 `mcp__claude-in-chrome__*`）。

```bash
_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
B="$HOME/.claude/skills/gstack/browse/dist/browse"
[ -n "$_ROOT" ] && [ -x "$_ROOT/.claude/skills/gstack/browse/dist/browse" ] && B="$_ROOT/.claude/skills/gstack/browse/dist/browse"
$B viewport 1280x900
```

点按钮一律用 `$B js` 按文案找元素再 `.click()`，不用写死的 CSS 选择器 —— Task 14/15 的
markup 由它们自己定，验收不该绑在别人的类名上。

**V1 切到验证码登录、发码、按钮变倒计时**

```bash
$B goto http://127.0.0.1:8099/galaxy/play
$B js "[...document.querySelectorAll('button')].find(b=>/登录|Sign In/.test(b.textContent)).click(); 'ok'"
$B js "[...document.querySelectorAll('button,a')].find(b=>b.textContent.includes('验证码登录')).click(); 'ok'"
$B js "const i=[...document.querySelectorAll('input')].find(x=>/手机|phone/i.test(x.placeholder+x.name+(x.labels?.[0]?.textContent||''))); if(i) i.focus(); 'found='+!!i"
$B type 13800138000
$B js "[...document.querySelectorAll('input[type=checkbox]')].forEach(c=>{if(!c.checked)c.click()}); 'consent-ticked'"
$B js "[...document.querySelectorAll('button')].find(b=>/获取验证码/.test(b.textContent)).click(); 'ok'"
$B js "await new Promise(r=>setTimeout(r,1200)); const b=[...document.querySelectorAll('button')].find(x=>/获取验证码|秒/.test(x.textContent)); JSON.stringify({label:b.textContent.trim(), disabled:b.disabled})"
```
Expected: 第 4 条打印 `found=true`；最后一条的 `disabled` 为 `true` 且 `label` 里含数字
（倒计时已经在跑）。区号控件默认显示 `+86`（`$B text | grep -c '+86'` ≥ 1）。

**V2 服务端日志里是掩码不是明文**

```bash
grep -a '\[SMS console\]' /tmp/phone-acc/server.log | tail -1
grep -ac '13800138000' /tmp/phone-acc/server.log
CODE=$(grep -ao 'code=[0-9]\{6\}' /tmp/phone-acc/server.log | tail -1 | cut -d= -f2); echo "CODE=$CODE"
```
Expected: 第一条形如 `[SMS console] to=+86 138****8000 intl=False code=123456`；
第二条 **`0`** —— 整份日志里不存在连续的 11 位号（掩码 `+86 138****8000` 里没有这个子串）；
第三条打印出 6 位 `CODE`。

第二条是这一项真正的断言：把 `mask_e164(...)` 换成裸 `phone_e164` 它立刻变成非 0。

**V3 60 秒内再点「获取验证码」→ 屏上是「还需等待 N 秒」**

```bash
$B js "const b=[...document.querySelectorAll('button')].find(x=>/获取验证码|秒/.test(x.textContent)); b.disabled=false; b.click(); 'ok'"
$B js "await new Promise(r=>setTimeout(r,1200)); document.body.innerText" > /tmp/phone-acc/v3.txt
grep -Ec '等待|[0-9]+ ?秒' /tmp/phone-acc/v3.txt
grep -Ec '操作失败|Operation failed|Request failed|\[object Object\]' /tmp/phone-acc/v3.txt
```
Expected: 第二条 ≥ 1（提示里说得出还要等多久）；第三条 **`0`**。

（脚本里手工把按钮 `disabled` 掀掉，是为了绕过前端倒计时、逼后端那条 429 `sms_cooldown`
真的走一遍 —— 前端禁用按钮只是体面，后端不挡才是漏洞。）

**V4 未绑号提交 → 屏上是一条可走的路，不是 "Operation failed"**

```bash
$B js "const i=[...document.querySelectorAll('input')].filter(x=>x.type!=='checkbox').pop(); i.focus(); 'ok'"
$B type $CODE
$B js "[...document.querySelectorAll('input[type=checkbox]')].forEach(c=>{if(!c.checked)c.click()}); 'consent-ok'"
$B js "document.body.innerText" > /tmp/phone-acc/v4-before.txt
$B js "[...document.querySelectorAll('button')].find(b=>/^(登录|提交|确定)/.test(b.textContent.trim())).click(); 'ok'"
$B js "await new Promise(r=>setTimeout(r,1200)); document.body.innerText" > /tmp/phone-acc/v4-after.txt
diff /tmp/phone-acc/v4-before.txt /tmp/phone-acc/v4-after.txt | grep -c '^>.*绑定'
grep -Ec '操作失败|Operation failed|Request failed|\[object Object\]' /tmp/phone-acc/v4-after.txt
```
Expected: 第一条 ≥ 1；第二条 **`0`**。

判据落在 **diff 里新出现的那一行**上，不是整页 `grep -c '绑定'` —— 同意勾选那行文案本来就可能带
「绑定」二字，整页数一定 ≥ 1，那样这一项无论实现对错都绿。新出现的含「绑定」的文本才是提交结果，
它必须说清下一步是**先用密码登录再绑号**，而不是一句 "Operation failed"。

**V5 未绑号发言被拒，且拿得到回执**

对局聊天在前端**没有任何入口**（`ChatPanel.tsx` 零 importer、`sendChat` 只有测试消费者），
所以这一项不在屏幕上验，改在**同一条生产通道**上验：登录后的浏览器里开一个真会话、
用真 token 连真 WS、发一条真 chat 帧。先记录「没有入口」这个事实（它会过期，过期了这一项就要改回屏上验）：

```bash
cd /Users/fan/Repositories/katrain-phone-login/katrain/web/ui
grep -rn "ChatPanel" src | grep -v "components/game/ChatPanel.tsx"
grep -rn "sendChat" src | grep -v "\.test\." | grep -v "hooks/useGameSession.ts"
```
Expected: 两条都**零命中**（exit 1）。有命中说明有人把聊天 UI 挂上去了，这一项当场改成屏上验。

```bash
$B goto http://127.0.0.1:8099/galaxy/play
$B js "localStorage.clear(); 'cleared'"
$B js "const r=await fetch('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'acc_unbound',password:'pw-acceptance-acc_unbound'})}); const j=await r.json(); localStorage.setItem('token', j.access_token); 'login='+r.status"
cat > /tmp/phone-acc/ws.js <<'JS'
(async () => {
  const token = localStorage.getItem('token');
  const r = await fetch('/api/session', { method: 'POST', headers: { Authorization: 'Bearer ' + token } });
  if (!r.ok) return 'SESSION_FAILED ' + r.status;
  const sid = (await r.json()).session_id;
  const ws = new WebSocket(`ws://${location.host}/ws/${sid}?token=${encodeURIComponent(token)}`);
  const frames = [];
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej('ws-error'); });
  ws.onmessage = (e) => frames.push(JSON.parse(e.data));
  ws.send(JSON.stringify({ type: 'chat', text: 'leak' }));
  await new Promise((res) => setTimeout(res, 1500));
  ws.close();
  return JSON.stringify(frames.filter((f) => f.type === 'error' || f.type === 'chat'));
})()
JS
$B goto http://127.0.0.1:8099/galaxy/play
$B eval /tmp/phone-acc/ws.js
```
Expected: `[{"type":"error","code":"chat_requires_phone"}]` —— 恰好一帧 error，**且一帧 `type:"chat"` 都没有**。

只留 `error` / `chat` 两种帧是刻意的：连上就会先推 `game_update`（`server.py:2800`）和
`spectator_count`（`server.py:2815`），拿「队列里有没有东西」判广播漏没漏一定会假绿/假红。

**V6 密码登录 → 侧边栏绑定入口 → 复盘页额度文案当场变**

```bash
$B goto http://127.0.0.1:8099/galaxy/play
$B js "localStorage.clear(); 'cleared'"
$B goto http://127.0.0.1:8099/galaxy/report
$B js "[...document.querySelectorAll('button')].find(b=>/登录|Sign In/.test(b.textContent)).click(); 'ok'"
$B js "const [u,p]=[...document.querySelectorAll('input')]; u.focus(); 'ok'"
$B type acc_bind
$B js "const p=[...document.querySelectorAll('input')].find(x=>x.type==='password'); p.focus(); 'ok'"
$B type pw-acceptance-acc_bind
$B js "[...document.querySelectorAll('button')].find(b=>/^(登录|Sign In)/.test(b.textContent.trim())).click(); 'ok'"
$B network --clear
$B goto http://127.0.0.1:8099/galaxy/report
$B js "await new Promise(r=>setTimeout(r,1500)); document.body.innerText" > /tmp/phone-acc/quota-before.txt
$B network | grep -c 'billing/quota'
$B js "const r=await fetch('/api/v1/billing/quota',{headers:{Authorization:'Bearer '+localStorage.getItem('token')}}); JSON.stringify((await r.json()).free_weekly)"
```
Expected: `billing/quota` 的请求计数 ≥ 1（**这是本项的硬判据**：改动前这个端点在整个前端零消费者，
`blocked_reason` 是个没人读的字段；这一行证明复盘页真的去读了它）；
最后一行打印 `{"used":0,"allowance":0,"blocked_reason":"phone_required"}`。

然后从侧边栏账号区走绑定（用第二个号 13800138001，走一遍完整的发码→填码）：

```bash
# 入口在侧栏那个**已存在的**「设置」<Menu> 里：菜单没展开时 menuitem 不在 DOM,
# find 会返回 undefined、.click() 抛 TypeError。所以先展开。
$B js "[...document.querySelectorAll('button,[role=button]')].find(b=>/设置|Settings/.test(b.textContent)).click(); 'menu-opened'"
$B js "await new Promise(r=>setTimeout(r,300)); [...document.querySelectorAll('[role=menuitem],button,a,li')].find(b=>/绑定手机/.test(b.textContent)).click(); 'ok'"
$B js "const i=[...document.querySelectorAll('input')].find(x=>/手机|phone/i.test(x.placeholder+x.name+(x.labels?.[0]?.textContent||''))); i.focus(); 'ok'"
$B type 13800138001
$B js "[...document.querySelectorAll('input[type=checkbox]')].forEach(c=>{if(!c.checked)c.click()}); 'consent-ticked'"
$B js "[...document.querySelectorAll('button')].find(b=>/获取验证码/.test(b.textContent)).click(); 'ok'"
CODE2=$(grep -ao 'code=[0-9]\{6\}' /tmp/phone-acc/server.log | tail -1 | cut -d= -f2); echo "CODE2=$CODE2"
$B js "const i=[...document.querySelectorAll('input')].filter(x=>x.type!=='checkbox').pop(); i.focus(); 'ok'"
$B type $CODE2
$B js "[...document.querySelectorAll('button')].find(b=>/^(绑定|确定|提交)/.test(b.textContent.trim())).click(); 'ok'"
$B goto http://127.0.0.1:8099/galaxy/report
$B js "await new Promise(r=>setTimeout(r,1500)); document.body.innerText" > /tmp/phone-acc/quota-after.txt
diff /tmp/phone-acc/quota-before.txt /tmp/phone-acc/quota-after.txt
$B js "const r=await fetch('/api/v1/billing/quota',{headers:{Authorization:'Bearer '+localStorage.getItem('token')}}); JSON.stringify((await r.json()).free_weekly)"
```
Expected: `diff` **非空**（文案确实变了，**同一周内**）；最后一行打印
`{"used":0,"allowance":1,"blocked_reason":null}`；`quota-after.txt` 里含「本周」。

绑定当周立即生效，是 Task 11「触碰 quota 之前短路、一行桶都不建」那条实现的用户可见证据 ——
换成「拿 allowance=0 去 peek」那种写法，这里的 `allowance` 会是 0 而且再也回不去。

**V7 《隐私政策》链接真的到得了政策页，不是禅模式棋盘**

```bash
$B goto http://127.0.0.1:8099/galaxy/play
$B js "[...document.querySelectorAll('button')].find(b=>/登录|Sign In/.test(b.textContent)).click(); 'ok'"
$B js "[...document.querySelectorAll('button,a')].find(b=>b.textContent.includes('验证码登录')).click(); 'ok'"
HREF=$($B js "const a=[...document.querySelectorAll('a')].find(x=>/隐私/.test(x.textContent)); a? new URL(a.getAttribute('href'), location.origin).href : 'NONE'")
echo "HREF=$HREF"
$B goto "$HREF"
$B text > /tmp/phone-acc/privacy.txt
grep -c '智星盒隐私策略' /tmp/phone-acc/privacy.txt
grep -c '手机号' /tmp/phone-acc/privacy.txt
```
Expected: `HREF` 不是 `NONE`；`智星盒隐私策略`（`src/legal/privacy.ts` 的 `PRIVACY_TITLE`）命中 ≥ 1；
`手机号` 命中 ≥ 1。

判据故意落在**渲染出来的正文**上而不是链接文本上：`/privacy` 在改动前不是 404 而是落到禅模式棋盘
（`AppRouter.tsx` 的 `/*` → `ZenModeApp`），只 grep `href="/privacy"` 会被自己刚写的那行命中、恒绿。
第二条 grep 守的是「政策正文里真的写了收手机号」—— 仓里那份 4.3KB 正文原本一个字没提手机号。

- [ ] **Step 6: 承重实测**（登录框长高了 —— 这条链变了）

```bash
cat > /tmp/phone-acc/loadbearing.js <<'JS'
(() => {
  const paper = document.querySelector('[role="dialog"]');
  const content = paper && paper.querySelector('.MuiDialogContent-root');
  if (!paper || !content) return 'NOT_OPEN';
  const btns = [...paper.querySelectorAll('button')];
  const submit = btns.find((b) => /登录|提交|确定/.test(b.textContent)) || btns[btns.length - 1];
  const before = content.scrollTop;
  content.scrollTop = 9999;
  const after = content.scrollTop;
  return JSON.stringify({
    vh: window.innerHeight,
    contentClient: content.clientHeight,
    contentScroll: content.scrollHeight,
    overflows: content.scrollHeight > content.clientHeight,
    scrolledFrom: before,
    scrolledTo: after,
    paperBottom: Math.round(paper.getBoundingClientRect().bottom),
    submitBottom: submit ? Math.round(submit.getBoundingClientRect().bottom) : null,
  });
})()
JS
$B viewport 430x640
$B goto http://127.0.0.1:8099/galaxy/play
$B js "[...document.querySelectorAll('button')].find(b=>/登录|Sign In/.test(b.textContent)).click(); 'ok'"
$B js "[...document.querySelectorAll('button,a')].find(b=>b.textContent.includes('验证码登录')).click(); 'ok'"
$B js "[...document.querySelectorAll('button')].find(b=>/^(登录|提交|确定)/.test(b.textContent.trim())).click(); 'ok'"   # 空表单提交,把错误条也撑进去
$B eval /tmp/phone-acc/loadbearing.js
```

**先看 `overflows`。**
- `overflows === true` → 状态造出来了，继续读下面三条。
- `overflows === false` → **这一步还没做完**，不是「通过」。换成移动端软键盘弹起后的可视高度档
  再来一次：`$B viewport 430x420`，重跑最后一条 `$B eval`。这一档下 `overflows` 必须为 `true`；
  还是 false，就把错误态、区号下拉展开一起造上，直到它真的溢出为止 —— 装得下的数据量下量出来的数字一概不算。

Expected（在 `overflows === true` 的那一档上，四条同时成立）：
1. `overflows === true`
2. `scrolledTo > 0`（滚轮真能推动 —— 「能不能滚」永远归这一关）
3. `paperBottom <= vh`（对话框自己没被推出视口；否则滚的是页面不是对话框）
4. `submitBottom !== null && submitBottom <= vh`（提交按钮够得到 —— 这是真正会伤到用户的那一格）

具体像素只记录进 `verification.md`、不作判据；判据是上面四条关系式。
滚的那个盒子是 `.MuiDialogContent-root` 不是 `[role="dialog"]`：MUI `Dialog` 默认 `scroll="paper"`，
Paper 拿 `max-height: calc(100% - 64px)` 且 `display:flex`，`overflow-y:auto` 挂在 DialogContent 上。
量错盒子的话 Paper 的 `scrollHeight === clientHeight` 恒成立，这一关会静默报绿。

- [ ] **Step 7: 停服务并还原**

```bash
kill "$(cat /tmp/phone-acc/server.pid)" 2>/dev/null || true
cp /tmp/phone-acc/katrain-config.bak ~/.katrain/config.json 2>/dev/null || true
cd /Users/fan/Repositories/katrain-phone-login && git status --porcelain
```

用记下来的 PID，不用 `pkill -f '…8099'`：`-f` 匹配的是整条命令行，
而发起匹配的那层 shell 自己的命令行里也含这个串（这个坑本仓踩过一次，见 RK3562 那条记录）。
Expected: `git status` 里**没有** `~/.katrain/config.json` 之外的意外改动；
若出现 `katrain/config.json`（跑 pytest 会改写仓里这份）或 `engine_game_state.json`（F12），
`git checkout -- <该文件>` 还原，**不要 add**。

- [ ] **Step 8: 部署前置 —— 断言 Task 5 落的那一行确实在**

Task 5 的 fail-fast 让 `KATRAIN_SMS_PROVIDER` 为空的服务端**拒绝启动**，而这个变量今天两台线上
机器都没设。仓库根的 `docker-compose.yml` 是**测试机那半**的操作数，闸就建在这里。

**这一行本身由 Task 5 落**（`katrain-web.environment` 里紧跟 `KATRAIN_SECRET_KEY` 那行之后）。
本 Task 不重复加它，也不是 TDD 的红灯步骤 —— 这里只负责把「它确实在」接成一条会一直守着的测试。

```python
# tests/web_ui/test_compose_declares_sms_provider.py
"""合并之后测试机还得起得来：SMS fail-fast 闸拒绝空 KATRAIN_SMS_PROVIDER 启动。

⚠️ 这三条只守**仓库根**的 docker-compose.yml —— 那份只服务测试机（home-ubuntu）。
生产（ucloud）读的是 release 分支独有的 deploy/ucloud/compose.yml + /etc/katrain/ucloud.env，
develop 的 deploy/ 下只有 minio/，本仓拿不到那半操作数 ⇒ 生产那一半不可能由任何本仓测试证明，
只能靠 Step 10 里在容器上回显 env 的实测。**不要把这三条的绿读成「两台都配好了」。**

katrain-cron 不需要这个变量：Dockerfile.cron 只 `COPY katrain/cron/`，容器里根本没有
katrain/web/server.py，那条 lifespan 不会跑（Step 10 有一条实测钉住这个前提）。
"""
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
ENV_NAME = "KATRAIN_SMS_PROVIDER"


def _web_env() -> list:
    doc = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    return list(doc["services"]["katrain-web"]["environment"])


def test_web_service_declares_the_sms_provider_env():
    names = [str(e).split("=", 1)[0] for e in _web_env()]
    assert ENV_NAME in names, (
        f"docker-compose.yml 的 katrain-web 没有 {ENV_NAME} —— "
        "合并后这台机器会在 _lifespan_server 的闸上拒绝启动"
    )


def test_it_fails_loudly_instead_of_defaulting_to_empty():
    """用 `${VAR:?...}`：compose 当场拒绝，比把空串喂进闸再在 lifespan 里抛更早、话更清楚。

    写成 `${VAR:-}` 的话容器会带着空 provider 起来 —— 那正是闸要挡的状态，
    等于把 fail-fast 推迟到应用层，日志里只剩一条 traceback。
    """
    line = next(str(e) for e in _web_env() if str(e).split("=", 1)[0] == ENV_NAME)
    assert ":?" in line, f"{ENV_NAME} 必须写成 ${{{ENV_NAME}:?...}} 形式，实际是：{line}"


def test_the_env_name_matches_what_config_actually_reads():
    """闸只看得见字面量：compose 写一个名字、config.py 读另一个名字，两边各自都"对"。"""
    src = (REPO / "katrain/web/core/config.py").read_text(encoding="utf-8")
    assert re.search(rf"os\.getenv\(\s*[\"']{ENV_NAME}[\"']", src), (
        f"config.py 没有从 {ENV_NAME} 读 —— compose 里配了也白配"
    )
```

Run: `./.venv/bin/python -m pytest tests/web_ui/test_compose_declares_sms_provider.py -q`
Expected: **PASS（3 条）**。Task 5 已经把这一行加进了 `docker-compose.yml` 的
`katrain-web.environment`（紧跟 `KATRAIN_SECRET_KEY` 那行之后，`:?` 形式），
`config.py` 也已经在读它 —— 这里不是 TDD 的红灯步骤，是确认性断言。
三条里有任何一条红，回 Task 5 核对它实际落的内容，不要在这里改断言迁就。

- [ ] **Step 9: 变异验证 —— 证明这三条测试真的守得住**

**不新增任何 env 行**（那一行是 Task 5 落的，本 Task 只验证它、不重复加）。
Step 8 的断言只证明「今天是对的」，没有变异验证的话它可能是一条恒真式 ——
比如断言条件写错、`_web_env()` 解析错了 key 却凑巧不报错。这一格不许省。

逐条改坏、跑测试、确认变红、立刻还原（`git checkout -- <该文件>`）：

| 变异 | 具体操作 | 期待变红的用例 | 还原命令 |
|---|---|---|---|
| 删掉 Task 5 加的那一行 | 编辑 `docker-compose.yml`，删掉 `katrain-web.environment` 里的 `KATRAIN_SMS_PROVIDER=${KATRAIN_SMS_PROVIDER:?...}` 那一行 | `test_web_service_declares_the_sms_provider_env`、`test_it_fails_loudly_instead_of_defaulting_to_empty` | `git checkout -- docker-compose.yml` |
| 把那行的 `:?...` 改成 `:-`（默认值形式，任意内容） | 编辑同一行 | 只 `test_it_fails_loudly_instead_of_defaulting_to_empty` | `git checkout -- docker-compose.yml` |
| 把 `config.py` 里 `os.getenv("KATRAIN_SMS_PROVIDER", ...)` 的字面量改成 `"KATRAIN_SMS_VENDOR"` | 编辑 `katrain/web/core/config.py` | 只 `test_the_env_name_matches_what_config_actually_reads` | `git checkout -- katrain/web/core/config.py` |

三次都实际跑一遍并确认红的正是那几条（不多不少），再改回去。跑完这一步后
`git status --porcelain -- docker-compose.yml katrain/web/core/config.py` 必须为空 ——
这两个文件在本 Task 里只被临时改坏又还原，不进最终提交。

- [ ] **Step 10: 部署前置 —— 两台机器的 env 必须在合并前配好**

顺序按 Fan 2026-08-31 的裁定：**先 home-ubuntu（测试，`go.sailorvoyage.top`），再 ucloud-v100
（生产，`modelstella.com`）**。

**取值定死：两台都填 `KATRAIN_SMS_PROVIDER=aliyun`，凭据留空。** 后果现在就说清楚，不留给部署当天：
`get_provider()` 造得出 `AliyunProvider`，服务起得来；但 `send()` 拿空凭据去打 dysmsapi 一定失败
（网络通就是 `Code != OK` 的 `SmsRejected`，不通就是 `SmsUnreachable`），
**`/auth/phone/send-code` 对每个用户都是 502**。所以在阿里云签名报备下来之前，
前端「验证码登录」入口该不该露出来，是产品决定 —— 写进收尾清单交回 Fan，本 Task 不替他定。

**两台都绝不许填 `console`**：那等于把验证码印进容器日志，谁能读日志谁就能登任何人的账号。
Task 5 的闸本来就挡它，`KATRAIN_SMS_ALLOW_CONSOLE` 只在本机验收开。

先探真正生效的是哪份 compose（**照探测结果改，不要照记忆改**）：

```bash
CF=$(ssh home-ubuntu "docker inspect katrain-web --format '{{index .Config.Labels \"com.docker.compose.project.config_files\"}}'")
echo "CONFIG_FILES=$CF"
ssh home-ubuntu "docker exec katrain-web sh -lc 'echo SMS=[\$KATRAIN_SMS_PROVIDER]'"
```
Expected: `CONFIG_FILES` 是一个绝对路径 —— 这台机器的部署目录同时是开发/训练 checkout，
磁盘上的 compose 和正在跑的 stack 曾经对不上过，所以这一步不能省，**后面所有命令都用 `$CF`，
不用「我记得是哪个目录」**；第二条在配好之前打印 `SMS=[]`（空），
**这就是「今天两台都没设」的取证，先留档再动手**。

按 `$CF` 那份文件配好它同目录的 `.env`（填 `KATRAIN_SMS_PROVIDER=aliyun`）与 compose，然后：

```bash
ssh home-ubuntu "cd \$(dirname $CF) && docker compose -f $CF up -d katrain-web && docker compose -f $CF logs --tail=40 katrain-web"
ssh home-ubuntu "docker exec katrain-web sh -lc 'echo SMS=[\$KATRAIN_SMS_PROVIDER]'"
curl -sf https://go.sailorvoyage.top/health && echo OK
ssh home-ubuntu "docker exec katrain-cron python -c 'import katrain.web.server' 2>&1 | tail -1"
```
Expected: 日志里没有 `RuntimeError`、`Application startup complete`；
第二条打印 `SMS=[aliyun]`；`/health` 200；
最后一条打印 `ModuleNotFoundError: No module named 'katrain.web'`
（钉住「cron 不吃这条闸」这个前提 —— 哪天 `Dockerfile.cron` 改成 `COPY . /app`，这一行会变，
那时 cron 也得配上，否则它会跟着拒绝启动）。

加一个 env 变量算配置变更，`docker compose up -d katrain-web` 会**重建**这个容器
（几十秒不可用）；KataGo 引擎是另一组服务，不受影响。

**不许加 `--remove-orphans`**：这台机器的磁盘 compose 与正在跑的 stack 对不上过
（2026-08-05 实测：文件里没有 minio，跑着的 stack 有），加上它会把教学媒体的对象存储一起删掉。
**`config_files` 标签可能是逗号分隔的多份**（生产就是 `compose.yml` + `compose.production.yml`
两份），那时每一份都要各给一个 `-f`，别只喂第一份。

生产同形，主机换 `ucloud-v100`，容器名/compose 文件/env 文件一律以 `docker inspect` 的
`config_files` 标签和 `docker exec … env` 的回显为准 —— 生产读的那份 compose **不在本仓**
（develop 的 `deploy/` 下只有 `minio/`），Step 8 的三条测试对它一个字都证明不了。

**这一步的输出是两条实测回显（两台各一条 `SMS=[aliyun]`），贴进 `verification.md`。
拿不到这两条 ⇒ 这条分支不许合。**

- [ ] **Step 11: 把证据写进 track**

新建 `superpowers/tracks/phone-login/verification.md`，逐项记：Step 5 的 V1–V7（每项一段命令回显
或截图）、Step 6 的四条关系式与当时的像素读数、Step 10 的两条 `SMS=[aliyun]` 回显。

**没有读数的那几项不许标"已验"**，按事实写成两类：
- 「本轮无 UI」：对局聊天回执（后端已就绪，前端零入口，见 V5 的两条 grep）；
- 「本轮不可验」：真短信通道（没有凭据、没实发过一条）。

两条都同时进收尾清单 —— 只写在 `verification.md` 里，交回给 Fan 的风险面就是不全的。

- [ ] **Step 12: 提交**

```bash
cd /Users/fan/Repositories/katrain-phone-login
git status --porcelain
git add tests/web_ui/test_compose_declares_sms_provider.py \
        superpowers/tracks/phone-login/verification.md
git commit -m "test(phone-login): 真浏览器验收 + 基线比对零新增失败 + 部署前置

基线比的是失败名字集合不是条数,且两边都 LC_ALL=C sort 再 comm ——
test-baseline.txt 当初按 en_US collation 排的,直接比会吐出假的新增失败。
Task 11 主动改动的三条(test_quota_endpoint_shape / 两条 report_charging)
先单独跑绿再进比对:那是我们自己改的,不是基线噪声,更不许塞进基线文件。

承重实测:验证码模式让登录框长高。判据先看 overflows —— 不成立说明状态没造出来,
这一步没做完,压到 430x420(软键盘弹起后的可视高度)再造。量的是
.MuiDialogContent-root 不是 [role=dialog]:MUI 默认 scroll=paper,
overflow-y 挂在 DialogContent 上,量错盒子这一关会静默报绿。

部署前置:fail-fast 闸会让 KATRAIN_SMS_PROVIDER 为空的服务端拒绝启动,
而这个变量今天两台线上机器都没设。Task 5 已经加了根 compose 那一行 \${...:?},
本 Task 补三条测试 + 变异验证守着它 —— 但那只是测试机那半,生产读的 compose 不在本仓,
靠容器里 env 回显取证。取值定死 aliyun(空凭据):服务起得来,send-code 一律 502,
这一条交回 Fan 定何时露出入口。"
```
Expected: 提交里**只有这两个文件**（`docker-compose.yml` 不在其中 —— 它是 Task 5 的
产出，本 Task 只对它做了变异验证并已还原）。`git status` 里若还留着 `katrain/config.json`
（跑 pytest 会改写仓里这份）或 `engine_game_state.json`（F12），一律不 add。

---

## 收尾：本轮明确没做、要交回给 Fan 的

1. **真短信通道没开。** `aliyun` 提供方按文档实现并有签名向量的单测，但**没有凭据、没有实发过一条**。
   国内签名报备要 5–10 个工作日且不承诺时效，**是这条路的关键路径且它不在代码里**。
   补充事实：签名 **6 个月无发送记录会失效**。
2. **（已定）`SMS_DAILY_CAP_INTL` = 50** —— 见下第 16 条。
3. **不做自助换绑与解绑**（走人工客服直接改库）。这是"一号一账号"论证的**必要前提**——
   有换绑就有"A 号绑账号1拿一份，解绑再绑账号2拿第二份"。
   **上量后要补自助换绑时，必须同时补「旧号 N 天内不可再注册」，否则这个前提当场失效。**
4. **手机丢了 = 账号丢了**（没有邮箱、密保、人工申诉）。
5. **改密码踢不掉已签发的 token，最长 90 天。** access token 是 7 天，但
   `REFRESH_TOKEN_EXPIRE_DAYS = 90` 且 `/auth/refresh` 只验签名 + 用户名存在、
   **不看密码改没改** ⇒ 持有 refresh token 的人改完密码仍能连续换发长达 90 天。
   Task 17 要求把这句在改密码成功页上说出来 —— 不说就是给用户一个错的安全承诺。
6. **不做手机注册**（见开头收窄说明）。
7. **`billing.py:5-10` 的模块头注释说反话**（写着 balance 会 fall through 到远程，实际直接 503），
   非本轮修，已记。
8. **同意没有后端留痕**（Task 15 只做了前端的告知与同意闸）。要成为可举证的合规记录，
   还需要一张同意记录表 + 留存期限策略。**不要对外声称本轮已具备该记录。**
9. **`/privacy` 页的内容归属未定**：Task 15 只保证链接可达，页面里到底写了什么
   （存储期限、如何撤回、如何删除）需要 Fan 或法务定稿。

10. **F12：跑 pytest 会改掉 `engine_game_state.json`**，非本轨道缺陷，已记，本轨道靠"不用 `git add -A`"规避。

11. **日额度只在单进程下是硬闸**：`SELECT count(*)` 与 `INSERT` 之间无锁，多进程下并发会全部放行。
    今天安全只因单进程部署。**改 `--workers` 之前必须先把它换成 `quota.try_consume` 那种条件 UPDATE**，
    否则那一天 `SMS_DAILY_CAP_*` 从硬闸退化成建议值，而且不会有任何报错。
12. **`sms_challenges` 明文长期保存手机号，且没有保留期与清理任务。** 本轮不做清理，
    保留期多久要 Fan 定（个人信息的存储期限是隐私政策里要写明的一项）。
13. **没有"拒收次数"的独立计数器**：供应商明确拒收的请求不计入日额度（否则攻击者能用
    一定被拒的号零成本打满），但也就没人数它 —— 有人拿一堆废号刷时我们看不见。
14. **对局聊天没有前端 UI**（`chatMessages` / `sendChat` 零消费者），所以本轮不给
    `chat_requires_phone` 造一个只为接错误码的假界面。后端的闸是真的，用户看不见而已。
15. **部署前置（会让服务起不来，不是可选项）**：`KATRAIN_SMS_PROVIDER` 今天两台线上机器
    **都没设**，而新的 fail-fast 闸在 server 模式下会拒绝启动。合并前必须先在
    home-ubuntu 与 ucloud-v100 两边的 compose env 里配上（本轮没有凭据 ⇒ 配 `aliyun` +
    空凭据即可起来，发码会 502，这是诚实的不可用）。顺序照既定规矩：先测试环境再生产。
16. **`SMS_DAILY_CAP_INTL` 定为 50**（此前 requirements §3 D-U4 表里标着"⚠️ 待核 100"，
    现作废）。取低的那个，理由是国际号是最贵的攻击面，封顶要比国内低一个量级而不是低三成。
17. **`sms_challenges` 的建表与 `users` 两列的迁移只在 SQLite 上验证过。** 生产是
    PostgreSQL，本机没有 PG 实例，所以"PG 上 `ALTER TABLE ADD COLUMN` 不带 UNIQUE、
    `CREATE UNIQUE INDEX` 保留唯一性"这一条只能在 PG 上证。部署到 home-ubuntu 测试
    环境后应当在真 PG 上跑一次 `add_missing_columns()` + `create_missing_indexes()`
    并核对 `\d users` / `\d sms_challenges`。
