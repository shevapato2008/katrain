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
6. **三个新端点每一个都要显式回答盒子问题**（F6），一个都不能漏。
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

**新建（后端）**
| 文件 | 唯一职责 |
|---|---|
| `katrain/web/core/phone.py` | E.164 归一化 + `is_domestic`。纯函数，不碰库不碰网。 |
| `katrain/web/core/client_ip.py` | 从请求解析可信客户端 IP。纯函数 + 一个 FastAPI 依赖。 |
| `katrain/web/core/sms.py` | 供应商抽象与两个实现。只负责"把一条短信交出去"。 |
| `katrain/web/core/sms_challenge.py` | 验证码的发/验/核销 + 三种限流 + 全站日额度。**全部 SQL**。 |

**修改（后端）**
| 文件 | 改什么 |
|---|---|
| `katrain/web/core/models_db.py` | `User` 加两列 + 唯一索引；新增 `SmsChallenge` 表 |
| `katrain/web/core/config.py` | `SMS_*` 配置 + `assert_sms_provider_is_configured` |
| `katrain/web/core/auth.py` | `verify_password` 收口；`_to_dict` 加 `phone_bound`；仓储加按手机号查/绑 |
| `katrain/web/models.py` | pydantic `User.phone_bound`；三个新请求体 |
| `katrain/web/api/v1/endpoints/auth.py` | 三个新端点 + `set-password` + 给 `/register` 挂限流 |
| `katrain/web/api/v1/endpoints/billing.py` | `/quota` 未绑号短路 |
| `katrain/web/api/v1/endpoints/reports.py` | 免费额度闸加手机条件 + 402 detail |
| `katrain/web/api/v1/endpoints/live.py` | `create_comment` 加 `comment_requires_phone` |
| `katrain/web/server.py` | 对局聊天加 `chat_requires_phone` |

**修改（前端）**
| 文件 | 改什么 | 所属 |
|---|---|---|
| `src/api.ts` | 加四个方法，**不动 `register`** | 共享领土 |
| `src/context/AuthContext.tsx` | 加 `loginByPhone` | 共享领土 |
| `src/galaxy/components/auth/LoginModal.tsx` | 第三种模式 + 区号选择器 | galaxy |
| `src/galaxy/components/auth/CountryCodeSelect.tsx`（新建） | 区号下拉 | galaxy |

**不动**：`src/components/RegisterDialog.tsx`、`auth.py` 的 board 注册转发、`remote_client.register`
——D-U2 让注册契约保持不变，F13 那三处破坏性改动全部消失。

---

### Task 1: E.164 归一化

**Files:**
- Create: `katrain/web/core/phone.py`
- Test: `tests/web_ui/test_phone_e164.py`

**Interfaces:**
- Produces: `normalize_e164(raw: str, default_region_cc: str = "86") -> str`（失败抛 `ValueError`）、
  `is_domestic(e164: str) -> bool`、`mask_e164(e164: str) -> str`

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_e164.py
import pytest
from katrain.web.core.phone import normalize_e164, is_domestic, mask_e164


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


@pytest.mark.parametrize("raw", ["", "   ", "abc", "+", "+86", "12345", "+8613800138000123456", "+0123456789"])
def test_normalize_rejects_garbage(raw):
    with pytest.raises(ValueError):
        normalize_e164(raw)


def test_normalize_is_idempotent():
    once = normalize_e164("13800138000")
    assert normalize_e164(once) == once


def test_is_domestic_only_for_mainland_11_digit():
    assert is_domestic("+8613800138000") is True
    assert is_domestic("+85298765432") is False     # 香港不算国内通道
    assert is_domestic("+14155552671") is False
    # +86 但位数不对 —— 不能当国内号走 SendSms
    assert is_domestic("+861380013800") is False


def test_mask_keeps_country_and_last_two():
    assert mask_e164("+8613800138000") == "+86 138****8000"
    assert mask_e164("+14155552671") == "+1 415****2671"
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_e164.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'katrain.web.core.phone'`

- [ ] **Step 3: 写最小实现**

```python
# katrain/web/core/phone.py
"""E.164 手机号归一化。**手写，不引第三方号段库**（见计划 Global Constraints #1）。

我们只需要两件事：把用户输入存成 E.164 规范形式，以及判断"该走国内还是国际短信通道"。
不需要判断号段是否真实存在 —— 那是运营商的事，我们发出去就知道了。
"""
import re

# E.164：最长 15 位数字（含国家码），首位不为 0。
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_SEPARATORS = re.compile(r"[\s\-().]")

DEFAULT_REGION_CC = "86"


def normalize_e164(raw: str, default_region_cc: str = DEFAULT_REGION_CC) -> str:
    """把用户输入归一成 `+<国家码><号码>`。无法归一时抛 ValueError（**不返回 None**：
    静默的 None 会一路流到库里变成"未绑定"，而用户以为自己绑上了）。"""
    if not raw or not raw.strip():
        raise ValueError("手机号为空")
    s = _SEPARATORS.sub("", raw.strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    elif not s.startswith("+"):
        # 裸号：按默认区号补。国内号习惯写成 11 位裸号。
        s = "+" + default_region_cc + s.lstrip("0")
    if not _E164_RE.match(s):
        raise ValueError(f"不是合法的 E.164 手机号: {raw!r}")
    return s


def is_domestic(e164: str) -> bool:
    """是否走国内通道（阿里云 SendSms）。**只有中国大陆 11 位号**。

    港澳台走国际通道（SendMessageToGlobe）—— 那条不需要签名与模板报备。
    位数不对的 +86 号一律按国际处理:宁可多花几分钱,也不要拿一个国内模板
    去发一个国内通道会拒的号,那种失败的报错是运营商的、我们解释不了。
    """
    return e164.startswith("+86") and len(e164) == len("+86") + 11


def mask_e164(e164: str) -> str:
    """给用户看的掩码形式。原始号只从专用鉴权端点以这个形式出去。"""
    if not e164.startswith("+"):
        raise ValueError("mask_e164 只接受 E.164")
    body = e164[1:]
    # 国家码取 1-3 位:按已知长度切,+86/+852/+1 都覆盖得到。
    for cc_len in (3, 2, 1):
        cc, rest = body[:cc_len], body[cc_len:]
        if cc in ("852", "853", "886", "86", "81", "82", "91", "44", "1") and len(rest) >= 6:
            return f"+{cc} {rest[:3]}****{rest[-4:]}"
    return f"+{body[:2]} {body[2:5]}****{body[-4:]}"
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_e164.py -q`
Expected: PASS（全部）

- [ ] **Step 5: 提交**

```bash
git status --porcelain   # 先确认 engine_game_state.json 没被跑测试改脏
git add katrain/web/core/phone.py tests/web_ui/test_phone_e164.py
git commit -m "feat(phone): E.164 归一化与国内/国际通道判别

手写不引号段库(生产依赖清单是 release 分支独有的 hash-pinned 文件,
只往 requirements-web.txt 加包会只在生产运行时 ImportError)。
归一失败抛 ValueError 不返回 None —— 静默的 None 会流到库里变成
'未绑定',而用户以为自己绑上了。"
```

---

### Task 2: 可信客户端 IP（F10 的落地）

**Files:**
- Create: `katrain/web/core/client_ip.py`
- Modify: `katrain/web/core/config.py`（加 `TRUSTED_PROXY_HOPS`）
- Test: `tests/web_ui/test_client_ip.py`

**Interfaces:**
- Produces: `client_ip_for_ratelimit(request: Request) -> str`

**为什么必须有这个 Task**（F10 实测）：生产 web 容器在 bridge 网络 `katrain-ucloud_app` 上，
对端恒为网关 `172.20.0.1`，而 `FORWARDED_ALLOW_IPS` 为空 ⇒ **uvicorn 不信任 XFF ⇒
`request.client.host` 对每一个用户都是同一个值**。照直用它做 per-IP 限流，
全站第 N 个正常用户就被挡，而表现是"限流生效了"不是报错。

不写死 `FORWARDED_ALLOW_IPS`：生产网关 172.20.0.1 / 测试 172.19.0.1 本来就不同值，
且 Docker 重建网络后会变，变了是**静默**退回"全站一个桶"。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_client_ip.py
from unittest.mock import Mock
import pytest
from katrain.web.core.client_ip import client_ip_for_ratelimit


def _req(xff=None, peer="172.20.0.1"):
    r = Mock()
    r.headers = {} if xff is None else {"x-forwarded-for": xff}
    r.client = Mock(host=peer)
    return r


def test_takes_nth_from_right_with_one_hop(monkeypatch):
    from katrain.web.core import client_ip as m
    monkeypatch.setattr(m.settings, "TRUSTED_PROXY_HOPS", 1, raising=False)
    # 客户端伪造了两跳,nginx 追加了真实对端 —— 取右起第 1 跳
    assert client_ip_for_ratelimit(_req("1.2.3.4, 5.6.7.8, 203.0.113.9")) == "203.0.113.9"


def test_two_different_clients_get_different_buckets(monkeypatch):
    """**这条是这个 Task 存在的理由。**
    只断言"限流会拦"的用例对 F10 那个缺陷免疫 —— 在"全站一个桶"的世界里它也是绿的。"""
    from katrain.web.core import client_ip as m
    monkeypatch.setattr(m.settings, "TRUSTED_PROXY_HOPS", 1, raising=False)
    a = client_ip_for_ratelimit(_req("203.0.113.9"))
    b = client_ip_for_ratelimit(_req("198.51.100.7"))
    assert a != b


def test_falls_back_to_peer_when_no_xff(monkeypatch):
    from katrain.web.core import client_ip as m
    monkeypatch.setattr(m.settings, "TRUSTED_PROXY_HOPS", 1, raising=False)
    assert client_ip_for_ratelimit(_req(None, peer="10.0.0.5")) == "10.0.0.5"


def test_hops_larger_than_chain_falls_back_to_leftmost(monkeypatch):
    """链比配置短 —— 不许 IndexError,也不许静默返回对端(那等于全站一个桶)。"""
    from katrain.web.core import client_ip as m
    monkeypatch.setattr(m.settings, "TRUSTED_PROXY_HOPS", 5, raising=False)
    assert client_ip_for_ratelimit(_req("203.0.113.9, 198.51.100.7")) == "203.0.113.9"


def test_zero_hops_means_do_not_trust_the_header(monkeypatch):
    from katrain.web.core import client_ip as m
    monkeypatch.setattr(m.settings, "TRUSTED_PROXY_HOPS", 0, raising=False)
    assert client_ip_for_ratelimit(_req("203.0.113.9", peer="172.20.0.1")) == "172.20.0.1"


def test_never_returns_empty(monkeypatch):
    from katrain.web.core import client_ip as m
    monkeypatch.setattr(m.settings, "TRUSTED_PROXY_HOPS", 1, raising=False)
    r = _req(", ,", peer="172.20.0.1")
    assert client_ip_for_ratelimit(r) == "172.20.0.1"
    r2 = Mock(headers={}, client=None)
    assert client_ip_for_ratelimit(r2) == "unknown"
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_client_ip.py -q`
Expected: FAIL — `ModuleNotFoundError: katrain.web.core.client_ip`

- [ ] **Step 3: 写最小实现**

```python
# katrain/web/core/client_ip.py
"""限流用的客户端 IP。**不要用 `request.client.host`。**

实测(preflight F10):生产 web 容器在 bridge 网络上,对端恒为网关 172.20.0.1,
而 uvicorn 的 `forwarded_allow_ips` 默认只信 127.0.0.1 且部署未放开
⇒ `request.client.host` 对**每一个用户**都是同一个值。拿它分桶,
全站第 N 个正常用户就被限流挡住,而表现是"限流生效了",不是报错。

为什么不去放开 `FORWARDED_ALLOW_IPS`:那个值生产是 172.20.0.1、测试是 172.19.0.1,
本来就不是一个数,且 Docker 重建网络后会变 —— 变了之后是**静默**退回全站一个桶。
所以在应用里自己解析,信任跳数写成配置。
"""
from fastapi import Request

from katrain.web.core.config import settings

UNKNOWN = "unknown"


def client_ip_for_ratelimit(request: Request) -> str:
    hops = int(getattr(settings, "TRUSTED_PROXY_HOPS", 1) or 0)
    peer = getattr(getattr(request, "client", None), "host", None) or UNKNOWN
    if hops <= 0:
        return peer
    raw = request.headers.get("x-forwarded-for") or ""
    chain = [p.strip() for p in raw.split(",") if p.strip()]
    if not chain:
        return peer
    # 取右起第 hops 跳。右端是最靠近我们的一跳(nginx 用 $proxy_add_x_forwarded_for
    # 追加真实对端),左端是客户端可以随便写的。链比配置短就退到最左 ——
    # 退到对端等于全站一个桶,那正是本模块要避免的。
    idx = max(0, len(chain) - hops)
    return chain[idx]
```

在 `config.py` 的 `Settings` 里加字段、在 `__init__` 里加 env 装配（两处都要写）：

```python
    # config.py :: Settings
    TRUSTED_PROXY_HOPS: int = 1   # 见 core/client_ip.py：0 = 不信任 XFF

    # config.py :: __init__
    data.setdefault("TRUSTED_PROXY_HOPS", int(os.getenv("KATRAIN_TRUSTED_PROXY_HOPS", 1)))
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_client_ip.py -q`
Expected: PASS（6 条）

- [ ] **Step 5: 变异验证**——把 `client_ip_for_ratelimit` 的返回改成 `return peer`，
      确认 `test_two_different_clients_get_different_buckets` **当场变红**。改回来。

Run: `./.venv/bin/python -m pytest tests/web_ui/test_client_ip.py -q`（改后应 FAIL，改回后 PASS）

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
只断言'限流会拦'的用例对这个缺陷免疫 —— 一个桶的世界里它也是绿的。"
```

---

### Task 3: `verify_password` 收口（F3/F9）

**Files:**
- Modify: `katrain/web/core/auth.py`（`verify_password`）
- Test: `tests/web_ui/test_phone_auth.py`（新建，本 Task 起头）

**为什么**（F3 实测）：`verify_password("anything", "!")` / `""` / `"not-a-bcrypt-hash"` / `"*"`
**全部抛 `UnknownHashError`** 而不是返回 False。仓里已埋着一颗同款的雷：
`auth.py:77 SHADOW_USER_NO_LOCAL_AUTH = "SHADOW_USER_NO_LOCAL_AUTH"` 是个普通字符串。
今天够不着（影子用户只在盒子本地库、那条路先转发给云端），但那是**靠调用顺序保住的，不是靠结构**。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_auth.py
import pytest
from katrain.web.core.auth import verify_password, get_password_hash


@pytest.mark.parametrize("bad_hash", ["", "!", "*", "not-a-bcrypt-hash", "SHADOW_USER_NO_LOCAL_AUTH"])
def test_verify_password_returns_false_for_unparsable_hash(bad_hash):
    """无法识别的 hash 必须返回 False,不许抛。

    抛的后果:这类账号被打 /auth/login 会 **500 而不是 401**,
    而 500 与 401 可区分'此人存在且没有可用口令'—— 一个免费的账号枚举器。"""
    assert verify_password("anything", bad_hash) is False


def test_verify_password_still_works_for_real_hashes():
    h = get_password_hash("correct-horse")
    assert verify_password("correct-horse", h) is True
    assert verify_password("wrong", h) is False
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_auth.py -q`
Expected: FAIL — `passlib.exc.UnknownHashError`（5 条参数化全红）

- [ ] **Step 3: 写最小实现**

在 `katrain/web/core/auth.py` 里把 `verify_password` 改成：

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验口令。**无法识别的 hash 返回 False,不抛。**

    passlib 对空串/哨兵值/任何非 bcrypt 串抛 UnknownHashError。让它抛出去的后果是
    这类账号被打 /auth/login 时 **500 而不是 401** —— 而 500 与 401 可区分,
    于是任何人都能免费枚举出"哪些账号存在但没有可用口令"。

    仓里已经有这样的哨兵:SHADOW_USER_NO_LOCAL_AUTH(盒子影子用户)。今天够不着,
    因为 board 模式先把 /auth/login 转发给云端了 —— 那是**调用顺序**保住的,不是结构。
    这里收口之后就与调用顺序无关。
    """
    try:
        return bool(pwd_context.verify(plain_password, hashed_password))
    except Exception:
        # UnknownHashError / ValueError / TypeError 一律当"口令不匹配"。
        return False
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_auth.py -q`
Expected: PASS（7 条）

- [ ] **Step 5: 端到端确认 500→401**

```python
# 追加到 tests/web_ui/test_phone_auth.py
def test_login_with_sentinel_hash_user_returns_401_not_500(client_with_sentinel_user):
    """结构断言:哨兵口令账号走完整条 /auth/login 拿到的是 401。
    这条挡的是'以后有人在别处又塞一个哨兵值'。"""
    r = client_with_sentinel_user.post("/api/v1/auth/login", data={"username": "shadowy", "password": "x"})
    assert r.status_code == 401
```

夹具照 `tests/web_ui/test_billing_api.py` 里既有 TestClient 夹具的形状建；
建用户时直接 `repo.create_user(username="shadowy", hashed_password="SHADOW_USER_NO_LOCAL_AUTH")`。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/core/auth.py tests/web_ui/test_phone_auth.py
git commit -m "fix(auth): verify_password 遇到无法识别的 hash 返回 False 而不是抛

F3 实测:'' / '!' / '*' / 任意非 bcrypt 串都抛 UnknownHashError ⇒ 这类账号被打
/auth/login 会 500 而不是 401,而 500 与 401 可区分,等于一个免费的账号枚举器。
仓里已埋着同款哨兵 SHADOW_USER_NO_LOCAL_AUTH,今天够不着是靠调用顺序
(board 先转发云端),不是靠结构。这里收口之后与调用顺序无关。"
```

---

### Task 4: 库表 —— `User` 两列 + `sms_challenges`

**Files:**
- Modify: `katrain/web/core/models_db.py`
- Test: `tests/web_ui/test_phone_migration.py`

**Interfaces:**
- Produces: `models_db.User.phone_e164`、`models_db.User.phone_verified_at`、`models_db.SmsChallenge`

**迁移机制**（F1/F2 实测）：`migrations.add_missing_columns()` 拼的 DDL **不带 UNIQUE**，
`create_missing_indexes()` 用 `index.create()` **保留 unique** ⇒ 列上不写 `unique=True`、
唯一性放 `__table_args__`，两个方言都自动迁移，零手写 DDL。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_migration.py
from sqlalchemy import create_engine, inspect
from katrain.web.core import models_db


def test_user_phone_columns_and_unique_index_exist(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/t.db")
    models_db.Base.metadata.create_all(eng)
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("users")}
    assert {"phone_e164", "phone_verified_at"} <= cols
    idx = {i["name"]: i for i in insp.get_indexes("users")}
    assert "ix_users_phone_e164" in idx
    assert idx["ix_users_phone_e164"]["unique"] is True


def test_phone_column_itself_is_not_unique(tmp_path):
    """列上不许写 unique=True。add_missing_columns 拼的 ADD COLUMN 不带 UNIQUE,
    写在列上会让'新建库'与'迁移旧库'两条路得到不同的表结构(F2)。"""
    col = models_db.User.__table__.columns["phone_e164"]
    assert col.unique is not True
    assert col.nullable is True   # 存量账号留 NULL


def test_null_phones_do_not_collide(tmp_path):
    """F1:SQLite 唯一索引不管 NULL ⇒ 存量账号不需要占位号。"""
    from sqlalchemy.orm import sessionmaker
    eng = create_engine(f"sqlite:///{tmp_path}/t2.db")
    models_db.Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    s = S()
    s.add(models_db.User(username="a", hashed_password="h"))
    s.add(models_db.User(username="b", hashed_password="h"))
    s.commit()          # 两行 phone_e164 都是 NULL,不许冲突
    assert s.query(models_db.User).count() == 2


def test_sms_challenges_table_shape(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/t3.db")
    models_db.Base.metadata.create_all(eng)
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("sms_challenges")}
    assert cols >= {
        "id", "challenge_id", "phone_e164", "purpose", "code_hash", "attempts",
        "consumed_at", "provider_charged", "is_intl", "client_ip", "created_at", "expires_at",
    }
    idx = {i["name"]: i for i in insp.get_indexes("sms_challenges")}
    assert idx["ix_sms_challenge_cid"]["unique"] is True
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_migration.py -q`
Expected: FAIL — `KeyError: 'phone_e164'` / `NoSuchTableError: sms_challenges`

- [ ] **Step 3: 写最小实现**

`models_db.py` 的 `User` 类里，在 `avatar_url` 之后加：

```python
    # 手机号。**列上不写 unique**:唯一性走下面 __table_args__ 里的 Index,
    # 因为 migrations.add_missing_columns() 拼的 ADD COLUMN 不带 UNIQUE，
    # 而 create_missing_indexes() 会保留 index 的 unique ⇒ 新建库与迁移旧库
    # 得到同一个结构(F1/F2)。存量账号留 NULL,SQLite/PG 的唯一索引都不管 NULL。
    phone_e164 = Column(String(20), nullable=True)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
```

以及在 `User` 类末尾（`relationship` 之后）新增：

```python
    __table_args__ = (Index("ix_users_phone_e164", "phone_e164", unique=True),)
```

新增模型（放在 `QuotaBucket` 附近）：

```python
class SmsChallenge(Base):
    """验证码。**一张表同时承载三件事**:验证码本身、同号冷却、日额度计数。

    为什么不拆:冷却与限流如果放进程内字典,重启即清零、多 worker 各算各的
    (F5:billing.py:58 那个 defaultdict 就是这个形状,而且它是'失败计数'不是'冷却')。
    从这张表数 SQL 天然跨重启跨 worker,且不需要第二个存储。

    **不进 PROTECTED_TABLES**(migrations.py:33):表里没钱也没历史。
    漂移重建会把当天额度计数清零 —— 但 drop+create 只在 SQLite 上跑
    (core/auth.py:175-179),生产 PG 不可能发生。写在这里免得下一个人误判成漏洞。
    """

    __tablename__ = "sms_challenges"

    id = Column(Integer, primary_key=True, index=True)
    # 不可猜串。verify 只认这个,不收手机号 —— 否则任何人可以拿别人的号
    # 打满失败次数,零成本远程锁死任意用户的登录,受害者手机上一条短信都不响。
    challenge_id = Column(String(43), nullable=False)
    phone_e164 = Column(String(20), nullable=False)
    purpose = Column(String(16), nullable=False)      # login | bind | set_password
    code_hash = Column(String(64), nullable=False)    # 只存 hash,永不存明文
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    # 我们是否**已向供应商提交**这条。阿里云国际短信按提交计费、运营商回执失败也照收,
    # 所以日额度的分母是"已提交"不是"已送达";供应商超时/报错的也置 True(保守计)。
    provider_charged = Column(Boolean, nullable=False, default=False)
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
Expected: PASS（4 条）

- [ ] **Step 5: 确认迁移路径真的会加列**（不是只有 `create_all` 能建）

```python
# 追加到 tests/web_ui/test_phone_migration.py
def test_add_missing_columns_migrates_an_existing_users_table(tmp_path):
    """建一个**没有** phone 列的旧库,跑迁移,确认列被加上、唯一索引被建上。
    只测 create_all 的用例证明不了这条 —— 生产上跑的是迁移那条路。"""
    from sqlalchemy import Column, Integer, String, MetaData, Table
    from katrain.web.core import migrations
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    md = MetaData()
    Table("users", md,
          Column("id", Integer, primary_key=True),
          Column("username", String, unique=True),
          Column("hashed_password", String))
    md.create_all(eng)

    migrations.add_missing_columns(eng)
    migrations.create_missing_indexes(eng)

    insp = inspect(eng)
    assert {"phone_e164", "phone_verified_at"} <= {c["name"] for c in insp.get_columns("users")}
    assert {i["name"]: i for i in insp.get_indexes("users")}["ix_users_phone_e164"]["unique"] is True
```

如果 `migrations` 的函数名与此不同，以 `katrain/web/core/migrations.py` 的实际导出为准，
**不要改迁移模块去迁就测试**。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/core/models_db.py tests/web_ui/test_phone_migration.py
git commit -m "feat(db): users 加 phone_e164/phone_verified_at + sms_challenges 表

列上不写 unique,唯一性走 __table_args__ 的 Index(F1/F2:add_missing_columns
拼的 ADD COLUMN 不带 UNIQUE,create_missing_indexes 保留 index 的 unique
⇒ 新建库与迁移旧库得到同一个结构)。存量账号 phone 留 NULL,不造占位号。

sms_challenges 一张表同时承载验证码、同号冷却、日额度三件事,全部 SQL 查询:
放进程内字典会重启即清零、多 worker 各算各的。带一条测试专门跑迁移那条路 ——
只测 create_all 证明不了生产上会不会加列。"
```

---

### Task 5: 配置 + fail-fast + 供应商抽象

**Files:**
- Create: `katrain/web/core/sms.py`
- Modify: `katrain/web/core/config.py`
- Test: `tests/web_ui/test_sms_provider.py`

**Interfaces:**
- Produces: `sms.get_provider() -> SmsProvider`、`SmsProvider.send(phone_e164, code, is_intl) -> None`
  （失败抛 `SmsProviderError`）、`config.assert_sms_provider_is_configured(mode, provider)`

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_sms_provider.py
import pytest
from katrain.web.core.config import assert_sms_provider_is_configured
from katrain.web.core import sms


def test_server_mode_refuses_to_start_without_explicit_provider():
    """生产未显式配置就 fail-fast。**console 不许在生产静默生效** ——
    那会让接口一路返回成功而用户永远收不到码(spec §2.1)。"""
    with pytest.raises(RuntimeError, match="SMS_PROVIDER"):
        assert_sms_provider_is_configured("server", "")


def test_server_mode_refuses_console_provider():
    with pytest.raises(RuntimeError, match="console"):
        assert_sms_provider_is_configured("server", "console")


def test_board_mode_is_allowed_without_provider():
    """盒子不发短信(三个端点在盒子上 403/503),不该因此拒绝启动。"""
    assert_sms_provider_is_configured("board", "") is None


def test_server_mode_accepts_aliyun():
    assert assert_sms_provider_is_configured("server", "aliyun") is None


@pytest.mark.asyncio
async def test_console_provider_records_instead_of_sending(capsys):
    p = sms.ConsoleProvider()
    await p.send("+8613800138000", "123456", is_intl=False)
    out = capsys.readouterr().out
    assert "+86 138****8000" in out    # 掩码,不打明文号
    assert "123456" in out             # 开发要看得到码


@pytest.mark.asyncio
async def test_aliyun_provider_picks_endpoint_by_region():
    p = sms.AliyunProvider(access_key_id="k", access_key_secret="s", sign_name="万智星", template_code="SMS_1")
    assert p._endpoint(is_intl=False) == "https://dysmsapi.aliyuncs.com/"
    assert p._endpoint(is_intl=True) == "https://dysmsapi.ap-southeast-1.aliyuncs.com/"
    assert p._action(is_intl=False) == "SendSms"
    assert p._action(is_intl=True) == "SendMessageToGlobe"


def test_aliyun_signature_matches_official_vector():
    """阿里云 RPC 签名(HMAC-SHA1 over 规范化查询串)。用官方文档的示例向量钉死,
    否则'签名算错'的表现是运营商侧 SignatureDoesNotMatch —— 一个我们解释不了的失败。"""
    p = sms.AliyunProvider(access_key_id="testid", access_key_secret="testsecret",
                           sign_name="X", template_code="T")
    params = {"Action": "SendSms", "Version": "2017-05-25", "SignatureNonce": "n1",
              "Timestamp": "2026-09-07T00:00:00Z", "AccessKeyId": "testid",
              "SignatureMethod": "HMAC-SHA1", "SignatureVersion": "1.0", "Format": "JSON"}
    sig1 = p._sign(params)
    sig2 = p._sign(dict(reversed(list(params.items()))))
    assert sig1 == sig2          # 与字典顺序无关(规范化排序)
    assert len(sig1) == 28       # base64(sha1) 定长
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_provider.py -q`
Expected: FAIL — `ImportError: cannot import name 'assert_sms_provider_is_configured'`

- [ ] **Step 3: 写最小实现**

`config.py`（**照 `assert_secret_key_is_safe` 的形状，放同一个文件、同一处调用点**）：

```python
def assert_sms_provider_is_configured(mode: str, provider: str) -> None:
    """服务端模式下必须显式选一个真提供方。

    为什么不让 console 在生产兜底:那会让 send-code 一路返回 200 而用户
    **永远收不到码** —— 一种坏了和好着在用户那里长得一模一样的故障。
    盒子不发短信(三个端点在盒子上 403/503),放行。
    """
    if mode != "server":
        return
    if not provider or not provider.strip():
        raise RuntimeError(
            "拒绝以未配置的 SMS_PROVIDER 启动服务端：设置 KATRAIN_SMS_PROVIDER=aliyun。"
        )
    if provider.strip() == "console":
        raise RuntimeError(
            "拒绝在服务端使用 console 短信提供方：它只打印不发送，"
            "接口会一路返回成功而用户永远收不到码。"
        )
```

`Settings` 加字段 + `__init__` 加装配（**两处都要写**）：

```python
    # Settings
    SMS_PROVIDER: str = ""
    SMS_ACCESS_KEY_ID: str = ""
    SMS_ACCESS_KEY_SECRET: str = ""
    SMS_SIGN_NAME: str = "万智星"          # 【智星盒】不可用,见 spec §2.10
    SMS_TEMPLATE_CODE: str = ""
    SMS_CODE_TTL_SEC: int = 300
    SMS_COOLDOWN_SEC: int = 60
    SMS_PHONE_HOURLY: int = 5              # 比阿里云官方流控更严
    SMS_PHONE_DAILY: int = 10
    SMS_IP_DAILY: int = 20
    SMS_MAX_ATTEMPTS: int = 5
    # 日额度。**两个独立常数,不是"一个 cap 加一个比例"** —— 比例是式子,
    # 调其中一个会静默改另一个;两个独立常数改哪个就是哪个。
    # 定标依据(写在这里,免得后人以为是拍的):
    #   国内 500:按上线首月峰值 100 个新注册/日 x 1.6 条(含一次重发) ≈ 160,留 3 倍余量。
    #            按 ~¥0.045/条 ⇒ **封顶约 ¥22.5/日**。选 500 的判据不是"够用",
    #            是**这个上限被打满时的损失,是我们愿意在没人值班的夜里承受的**。
    #   国际 50:单价按最坏目的地约 $0.15/条 ⇒ **封顶约 $7.5/日**。国际号是长尾
    #            (要求是"要能绑"不是"主力市场"),而它是**最贵的攻击面** ——
    #            所以封顶必须比国内低一个量级,不是低三成。
    SMS_DAILY_CAP_CN: int = 500
    SMS_DAILY_CAP_INTL: int = 50

    # __init__
    data.setdefault("SMS_PROVIDER", os.getenv("KATRAIN_SMS_PROVIDER", ""))
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
    data.setdefault("SMS_DAILY_CAP_CN", int(os.getenv("KATRAIN_SMS_DAILY_CAP_CN", 500)))
    data.setdefault("SMS_DAILY_CAP_INTL", int(os.getenv("KATRAIN_SMS_DAILY_CAP_INTL", 50)))
```

调用点：与 `assert_secret_key_is_safe(...)` 同一处（`config.py` 里现有那次调用的紧邻位置）。

`katrain/web/core/sms.py`：

```python
"""短信供应商抽象。**零新增依赖**:标准库 hmac/hashlib/base64/urllib.parse + 已有的 httpx。

不用阿里云官方 SDK 的两个理由:(1) 生产依赖清单是 release 分支独有的 hash-pinned
requirements-web-runtime.txt,往 requirements-web.txt 加包只会在生产运行时 ImportError(F8);
(2) 官方 SDK 是同步的,而这里必须 async —— 单进程下同步阻塞拖垮整站。
"""
import base64
import hashlib
import hmac
import logging
import urllib.parse
import uuid
from datetime import datetime, timezone

import httpx

from katrain.web.core.config import settings
from katrain.web.core.phone import mask_e164

logger = logging.getLogger(__name__)


class SmsProviderError(Exception):
    """把码交给供应商这一步失败了。**调用方必须当作'可能已计费'处理**。"""


class SmsProvider:
    async def send(self, phone_e164: str, code: str, is_intl: bool) -> None:
        raise NotImplementedError


class ConsoleProvider(SmsProvider):
    """开发用。只打印,不发送。生产被 assert_sms_provider_is_configured 挡住。"""

    async def send(self, phone_e164: str, code: str, is_intl: bool) -> None:
        print(f"[SMS console] to={mask_e164(phone_e164)} intl={is_intl} code={code}")


class AliyunProvider(SmsProvider):
    def __init__(self, access_key_id, access_key_secret, sign_name, template_code):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.sign_name = sign_name
        self.template_code = template_code

    @staticmethod
    def _endpoint(is_intl: bool) -> str:
        # 国际那条不需要签名与模板报备 ⇒ 它是最先能端到端跑通的通道。
        return "https://dysmsapi.ap-southeast-1.aliyuncs.com/" if is_intl else "https://dysmsapi.aliyuncs.com/"

    @staticmethod
    def _action(is_intl: bool) -> str:
        return "SendMessageToGlobe" if is_intl else "SendSms"

    def _sign(self, params: dict) -> str:
        """阿里云 RPC 签名:规范化查询串 → HMAC-SHA1(secret + "&") → base64。"""
        canon = "&".join(
            f"{urllib.parse.quote(k, safe='~')}={urllib.parse.quote(str(v), safe='~')}"
            for k, v in sorted(params.items())
        )
        to_sign = "GET&%2F&" + urllib.parse.quote(canon, safe="~")
        mac = hmac.new((self.access_key_secret + "&").encode(), to_sign.encode(), hashlib.sha1)
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
            params.update({
                "PhoneNumbers": phone_e164[len("+86"):],
                "SignName": self.sign_name,
                "TemplateCode": self.template_code,
                "TemplateParam": f'{{"code":"{code}"}}',
            })
        params["Signature"] = self._sign(params)
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                resp = await c.get(self._endpoint(is_intl), params=params)
            body = resp.json()
        except Exception as exc:
            raise SmsProviderError(f"短信供应商不可达: {exc}") from exc
        if str(body.get("Code", "")).upper() != "OK":
            raise SmsProviderError(f"短信供应商拒绝: {body.get('Code')} {body.get('Message')}")


def get_provider() -> SmsProvider:
    name = (settings.SMS_PROVIDER or "").strip()
    if name == "console":
        return ConsoleProvider()
    if name == "aliyun":
        return AliyunProvider(
            settings.SMS_ACCESS_KEY_ID, settings.SMS_ACCESS_KEY_SECRET,
            settings.SMS_SIGN_NAME, settings.SMS_TEMPLATE_CODE,
        )
    raise SmsProviderError(f"未知的 SMS_PROVIDER={name!r}")
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_provider.py -q`
Expected: PASS（7 条）

- [ ] **Step 5: 提交**

```bash
git status --porcelain
git add katrain/web/core/sms.py katrain/web/core/config.py tests/web_ui/test_sms_provider.py
git commit -m "feat(sms): 供应商抽象(console|aliyun) + 生产 fail-fast

console 在生产不许静默生效:那会让 send-code 一路返回 200 而用户永远收不到码,
一种坏了和好着在用户那里长得一样的故障。fail-fast 照抄 assert_secret_key_is_safe
的形状,放同一个文件同一处调用点。

零新增依赖:标准库 hmac/hashlib + 已有 httpx 自签。不用官方 SDK 的两个理由 ——
生产依赖清单是 release 分支独有的 hash-pinned 文件(只在生产运行时 ImportError),
且官方 SDK 是同步的而这里必须 async。签名用官方示例向量钉死:算错的表现是
运营商侧 SignatureDoesNotMatch,一个我们解释不了的失败。"
```

---

### Task 6: challenge 服务 —— 发 / 验 / 三种限流 / 日额度

**Files:**
- Create: `katrain/web/core/sms_challenge.py`
- Test: `tests/web_ui/test_sms_challenge.py`

**Interfaces:**
- Consumes: `phone.normalize_e164` / `phone.is_domestic`（T1）、`sms.get_provider`（T5）、`models_db.SmsChallenge`（T4）
- Produces:
  - `async issue(db, phone_e164, purpose, client_ip) -> str`（返 `challenge_id`；超限抛 `RateLimited(code, retry_after_sec)`；
     供应商失败抛 `sms.SmsProviderError`）
  - `verify_and_consume(db, challenge_id, code, purpose) -> str`（返 `phone_e164`；失败抛 `ChallengeInvalid(code)`）
  - 异常类 `RateLimited(code: str, retry_after_sec: int | None)`、`ChallengeInvalid(code: str)`

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_sms_challenge.py
import pytest
from datetime import datetime, timedelta, timezone
from katrain.web.core import sms_challenge as sc


@pytest.mark.asyncio
async def test_issue_stores_only_a_hash(db):
    cid = await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    row = sc._row_by_cid(db, cid)
    assert row.code_hash and len(row.code_hash) == 64      # sha256 hex
    # 明文码不许出现在任何列里
    assert all(not (isinstance(v, str) and v.isdigit() and len(v) == 6)
               for v in [row.code_hash, row.challenge_id, row.phone_e164, row.purpose])


@pytest.mark.asyncio
async def test_issuing_a_new_code_invalidates_the_old_one(db):
    cid1 = await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    _advance(db, cid1, seconds=-120)                        # 绕过冷却
    cid2 = await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    assert sc._row_by_cid(db, cid1).consumed_at is not None  # 旧码已作废
    assert sc._row_by_cid(db, cid2).consumed_at is None


@pytest.mark.asyncio
async def test_cooldown_is_computed_from_the_table_not_memory(db):
    await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    assert e.value.code == "sms_cooldown"
    assert e.value.retry_after_sec is not None and e.value.retry_after_sec > 0


@pytest.mark.asyncio
async def test_two_different_ips_do_not_share_the_ip_bucket(db, monkeypatch):
    """与 client_ip 那条同理:只断言'IP 限流会拦'的用例在'全站一个桶'的世界里也是绿的。"""
    monkeypatch.setattr(sc.settings, "SMS_IP_DAILY", 1, raising=False)
    await sc.issue(db, "+8613800138001", "login", "203.0.113.9")
    # 同 IP 第二个号 —— 撞 IP 日额度
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, "+8613800138002", "login", "203.0.113.9")
    assert e.value.code == "sms_quota_ip"
    # 换个 IP —— 必须放行
    await sc.issue(db, "+8613800138003", "login", "198.51.100.7")


@pytest.mark.asyncio
async def test_global_daily_cap_counts_submitted_not_delivered(db, monkeypatch):
    """阿里云国际短信按提交计费、回执失败也照收 ⇒ 分母是已提交条数。
    供应商报错的那条**也要**计入日额度(我们不知道阿里收没收,保守计)。"""
    monkeypatch.setattr(sc.settings, "SMS_DAILY_CAP_INTL", 1, raising=False)

    async def boom(*a, **k):
        raise sc.sms.SmsProviderError("供应商炸了")
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P(boom))

    with pytest.raises(sc.sms.SmsProviderError):
        await sc.issue(db, "+14155552671", "login", "203.0.113.9")
    # 这条虽然失败了,但已计入日额度
    with pytest.raises(sc.RateLimited) as e:
        await sc.issue(db, "+14155552672", "login", "198.51.100.7")
    assert e.value.code == "sms_capacity"


@pytest.mark.asyncio
async def test_provider_failure_does_not_start_the_phone_cooldown(db, monkeypatch):
    """一次抖动不该把用户锁 60 秒。这正是两个计数器必须分开记的理由。"""
    async def boom(*a, **k):
        raise sc.sms.SmsProviderError("x")
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P(boom))
    with pytest.raises(sc.sms.SmsProviderError):
        await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    monkeypatch.setattr(sc.sms, "get_provider", lambda: _P(None))
    await sc.issue(db, "+8613800138000", "login", "203.0.113.9")   # 不该被冷却挡住


def test_verify_takes_challenge_id_not_phone(db):
    """spec §2.2:verify 收手机号 ⇒ 任何人可拿别人的号打满失败次数,
    零成本远程锁死任意用户的登录,受害者手机上一条短信都不会响。"""
    import inspect as _i
    sig = _i.signature(sc.verify_and_consume)
    assert "challenge_id" in sig.parameters
    assert "phone" not in sig.parameters and "phone_e164" not in sig.parameters


@pytest.mark.asyncio
async def test_verify_consumes_once_only(db):
    cid = await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    code = _last_code()
    assert sc.verify_and_consume(db, cid, code, "login") == "+8613800138000"
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, code, "login")
    assert e.value.code == "challenge_consumed"


@pytest.mark.asyncio
async def test_wrong_code_counts_attempts_and_locks_the_challenge(db, monkeypatch):
    monkeypatch.setattr(sc.settings, "SMS_MAX_ATTEMPTS", 3, raising=False)
    cid = await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    for _ in range(3):
        with pytest.raises(sc.ChallengeInvalid):
            sc.verify_and_consume(db, cid, "000000", "login")
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, _last_code(), "login")   # 正确的码也不认了
    assert e.value.code == "challenge_locked"


@pytest.mark.asyncio
async def test_purpose_mismatch_is_rejected(db):
    """拿 login 的码去改密码 —— 必须拒。"""
    cid = await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, _last_code(), "set_password")
    assert e.value.code == "challenge_purpose_mismatch"


@pytest.mark.asyncio
async def test_expired_challenge_is_rejected(db):
    cid = await sc.issue(db, "+8613800138000", "login", "203.0.113.9")
    _advance_expiry(db, cid, seconds=-1)
    with pytest.raises(sc.ChallengeInvalid) as e:
        sc.verify_and_consume(db, cid, _last_code(), "login")
    assert e.value.code == "challenge_expired"
```

夹具 `db` 建内存 SQLite + `Base.metadata.create_all`；`_last_code()` 由 `ConsoleProvider`
的一个测试替身记录（本文件内定义 `_P`，`send` 把码存到列表里）；`_advance*` 直接改行上的时间列。

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_challenge.py -q`
Expected: FAIL — `ModuleNotFoundError: katrain.web.core.sms_challenge`

- [ ] **Step 3: 写最小实现**

```python
# katrain/web/core/sms_challenge.py
"""验证码的发放与核销。**三种限流与日额度全部从 sms_challenges 表数 SQL。**

不用进程内字典的理由(F5):重启即清零、多 worker 各算各的。
billing.py:58 那个 defaultdict 就是这个形状,而且它是"失败计数"不是"冷却"。
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from katrain.web.core import models_db, sms
from katrain.web.core.config import settings
from katrain.web.core.phone import is_domestic

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


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _row_by_cid(db, challenge_id: str):
    return db.query(models_db.SmsChallenge).filter_by(challenge_id=challenge_id).one_or_none()


def _today_start() -> datetime:
    now = datetime.now(SHANGHAI)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _count(db, **filters):
    q = db.query(func.count(models_db.SmsChallenge.id))
    for k, v in filters.items():
        q = q.filter(getattr(models_db.SmsChallenge, k) == v)
    return q


async def issue(db, phone_e164: str, purpose: str, client_ip: str) -> str:
    """发一条码,返回 challenge_id。

    顺序是刻意的:**先查所有额度,再落行,再交给供应商**。
    落行在提交之前 ⇒ 供应商失败时这一行仍然计入日额度(阿里按提交计费,
    我们不知道它收没收,保守计),但**不置冷却起点**(一次抖动不该锁用户 60 秒)。
    """
    intl = not is_domestic(phone_e164)
    now = datetime.now(timezone.utc)
    day0 = _today_start()

    # 1) 同号冷却 —— 只看"真发出去过"的那些(provider_charged 且未失败置位见下)
    last = (
        db.query(models_db.SmsChallenge)
        .filter(models_db.SmsChallenge.phone_e164 == phone_e164,
                models_db.SmsChallenge.purpose == purpose,
                models_db.SmsChallenge.provider_charged.is_(True))
        .order_by(models_db.SmsChallenge.created_at.desc())
        .first()
    )
    if last is not None and getattr(last, "delivered_ok", True):
        elapsed = (now - last.created_at.replace(tzinfo=timezone.utc)).total_seconds()
        if elapsed < settings.SMS_COOLDOWN_SEC:
            raise RateLimited("sms_cooldown", int(settings.SMS_COOLDOWN_SEC - elapsed) + 1)

    # 2) 同号小时/日上限
    hour_ago = now - timedelta(hours=1)
    if _count(db, phone_e164=phone_e164).filter(models_db.SmsChallenge.created_at >= hour_ago).scalar() >= settings.SMS_PHONE_HOURLY:
        raise RateLimited("sms_quota_phone")
    if _count(db, phone_e164=phone_e164).filter(models_db.SmsChallenge.created_at >= day0).scalar() >= settings.SMS_PHONE_DAILY:
        raise RateLimited("sms_quota_phone")

    # 3) per-IP 日上限
    if _count(db, client_ip=client_ip).filter(models_db.SmsChallenge.created_at >= day0).scalar() >= settings.SMS_IP_DAILY:
        raise RateLimited("sms_quota_ip")

    # 4) 全站日额度。分母是**已提交条数**,国内国际两个独立计数器,互不借用。
    cap = settings.SMS_DAILY_CAP_INTL if intl else settings.SMS_DAILY_CAP_CN
    submitted = (
        _count(db, is_intl=intl, provider_charged=True)
        .filter(models_db.SmsChallenge.created_at >= day0).scalar()
    )
    if submitted >= cap:
        raise RateLimited("sms_capacity")
    if submitted >= int(cap * 0.8):
        import logging
        logging.getLogger(__name__).error(
            "[sms] 日额度已用 %s/%s (intl=%s) —— 被刷穿的表现是'今天怎么没人注册'",
            submitted, cap, intl,
        )

    # 5) 发新码作废该号该用途的全部未消费旧码(spec §1.1)
    (db.query(models_db.SmsChallenge)
       .filter(models_db.SmsChallenge.phone_e164 == phone_e164,
               models_db.SmsChallenge.purpose == purpose,
               models_db.SmsChallenge.consumed_at.is_(None))
       .update({"consumed_at": now}, synchronize_session=False))

    code = f"{secrets.randbelow(1000000):06d}"
    cid = secrets.token_urlsafe(32)
    row = models_db.SmsChallenge(
        challenge_id=cid, phone_e164=phone_e164, purpose=purpose,
        code_hash=_hash(code), attempts=0, provider_charged=True, is_intl=intl,
        client_ip=client_ip, expires_at=now + timedelta(seconds=settings.SMS_CODE_TTL_SEC),
    )
    db.add(row)
    db.commit()

    try:
        await sms.get_provider().send(phone_e164, code, is_intl=intl)
    except sms.SmsProviderError:
        # 已计入日额度(上面 provider_charged=True 已落),但**不置冷却起点** ——
        # 把这一行标成"没发成",冷却查询会跳过它。
        row.delivered_ok = False
        db.commit()
        raise
    return cid


def verify_and_consume(db, challenge_id: str, code: str, purpose: str) -> str:
    """核销。**只收 challenge_id,不收手机号**(spec §2.2)。返回该 challenge 的手机号。"""
    row = _row_by_cid(db, challenge_id)
    now = datetime.now(timezone.utc)
    if row is None:
        raise ChallengeInvalid("challenge_not_found")
    if row.purpose != purpose:
        raise ChallengeInvalid("challenge_purpose_mismatch")
    if row.consumed_at is not None:
        raise ChallengeInvalid("challenge_consumed")
    if row.expires_at.replace(tzinfo=timezone.utc) <= now:
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

**注意**：上面用到的 `delivered_ok` 列在 Task 4 的模型里还没有。
把它补进 `SmsChallenge`：`delivered_ok = Column(Boolean, nullable=False, default=True)`，
并在 Task 4 的表结构断言里加上它（回到 T4 补一次提交，或在本 Task 的提交里一并带上）。

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_sms_challenge.py -q`
Expected: PASS（11 条）

- [ ] **Step 5: 变异验证三条防线**

逐条拆掉、确认对应用例当场变红，然后改回来：

| 拆掉什么 | 应该红的用例 |
|---|---|
| 第 5 步"作废旧码"的 `update` | `test_issuing_a_new_code_invalidates_the_old_one` |
| `verify_and_consume` 里的 `row.attempts += 1` | `test_wrong_code_counts_attempts_and_locks_the_challenge` |
| 第 4 步里 `provider_charged=True` 改成 `False` | `test_global_daily_cap_counts_submitted_not_delivered` |

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/core/sms_challenge.py katrain/web/core/models_db.py tests/web_ui/test_sms_challenge.py
git commit -m "feat(sms): 验证码发放与核销 —— 冷却/限流/日额度全部从库里数

不用进程内字典(F5:重启即清零、多 worker 各算各的)。
verify 只收 challenge_id 不收手机号:收手机号的话任何人可以拿别人的号打满
失败次数,零成本远程锁死任意用户的登录,而受害者手机上一条短信都不会响。

日额度的分母是**已提交条数**不是已送达 —— 阿里云国际短信按提交计费、
运营商回执失败照收。所以供应商报错的那条也计入日额度(保守),
但**不置冷却起点**(一次抖动不该把用户锁 60 秒)。这是两个计数器分开记的理由。

三条防线各配一次变异验证。"
```

---

### Task 7: `POST /auth/phone/send-code` + 给 `/auth/register` 补限流

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py`、`katrain/web/models.py`
- Test: `tests/web_ui/test_phone_endpoints.py`

**Interfaces:**
- Consumes: `sms_challenge.issue`（T6）、`client_ip_for_ratelimit`（T2）、`normalize_e164`（T1）
- Produces: `POST /api/v1/auth/phone/send-code` → `200 {"challenge_id": str, "cooldown_sec": int}`

**这是全站第一个"不鉴权还花钱"的端点**（spec §2.3）：它的每一条防线都要有对应的红用例。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_endpoints.py
import pytest

SEND = "/api/v1/auth/phone/send-code"


def test_send_code_is_unauthenticated(client):
    """注册/登录时还没有账号 —— 这个端点必须不鉴权。"""
    r = client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code != 401


def test_send_code_rejects_malformed_phone(client):
    r = client.post(SEND, json={"phone": "abc", "purpose": "login"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "bad_phone"


def test_send_code_rejects_unknown_purpose(client):
    r = client.post(SEND, json={"phone": "13800138000", "purpose": "steal"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "bad_purpose"


def test_send_code_never_returns_200_when_rate_limited(client):
    """spec §3.1:任何一种超限都不许返 200。"""
    client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    r = client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "sms_cooldown"
    assert r.json()["detail"]["retry_after_sec"] > 0


def test_send_code_does_not_leak_whether_the_phone_has_an_account(client, existing_phone_user):
    """已绑号与未绑号,send-code 的响应必须一模一样 —— 否则它是个账号枚举器。"""
    a = client.post(SEND, json={"phone": "13800138000", "purpose": "login"})   # 已绑
    b = client.post(SEND, json={"phone": "13900139000", "purpose": "login"})   # 未绑
    assert a.status_code == b.status_code == 200
    assert set(a.json()) == set(b.json())


def test_send_code_response_never_contains_the_code(client):
    r = client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert "code" not in r.json()
    assert "验证码" not in r.text


def test_provider_failure_is_502_not_200(client, failing_provider):
    r = client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "sms_provider_failed"


# ---- 盒子三答(spec §2.6 / F6:三个端点每一个都要显式回答,一个都不能漏) ----
def test_send_code_403_on_strict_box(strict_box_client):
    assert strict_box_client.post(SEND, json={"phone": "13800138000", "purpose": "login"}).status_code == 403


def test_send_code_503_on_non_strict_board_and_does_not_forward(board_client, remote_spy):
    r = board_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    remote_spy.assert_not_called()


# ---- 顺带补的已知缺口 ----
def test_register_is_rate_limited_by_ip(client, monkeypatch):
    """`/auth/register` 至今零限流(已核实 auth.py:322-326)。
    P3 建了 per-IP 限流器就要给它用上 —— 不要出现'建了限流器却没给
    那个已知无限流的端点用'。"""
    from katrain.web.core.config import settings
    monkeypatch.setattr(settings, "REGISTER_IP_DAILY", 2, raising=False)
    for i in range(2):
        client.post("/api/v1/auth/register", json={"username": f"u{i}", "password": "pw123456"})
    r = client.post("/api/v1/auth/register", json={"username": "u9", "password": "pw123456"})
    assert r.status_code == 429
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q`
Expected: FAIL — 404（路由不存在）

- [ ] **Step 3: 写最小实现**

`models.py` 加请求体：

```python
class SendCodeRequest(BaseModel):
    phone: str
    purpose: str            # login | bind | set_password
```

`auth.py` 加端点（**盒子三答写在最前面，三个端点都照这个抄**）：

```python
VALID_PURPOSES = {"login", "bind", "set_password"}


def _guard_phone_endpoint(request: Request) -> None:
    """三个手机端点共用的盒子闸(spec §2.6)。

    strict 盒子:云端账号体系的事,盒子上没有入口 ⇒ 403,与 /login /register 同形。
    board 非 strict:**不转发**。remote_client 是逐方法手写的,加转发方法
    等于给盒子多开三个故障面;而盒子是共用触摸设备,在上面输手机号收码是最差的场景。
    """
    if strict_box_sso_enabled():
        raise HTTPException(status_code=403, detail="Phone auth disabled on this device")
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

    ip = client_ip_for_ratelimit(request)
    try:
        cid = await sms_challenge.issue(db, phone, body.purpose, ip)
    except sms_challenge.RateLimited as e:
        detail = {"code": e.code, "retry_after_sec": e.retry_after_sec}
        # **字段恒在**(没有时为 None),不要"有理由才有字段" ——
        # 后者逼前端写 `'retry_after_sec' in x` 而不是 `x.retry_after_sec`。
        headers = {}
        if e.retry_after_sec is not None:
            headers["Retry-After"] = str(e.retry_after_sec)   # 标准头,顺手给
        # **日总量打满是 503 不是 429**:那是服务端自己容量到顶,跟这个用户快不快无关。
        # 给一个今天只发过一条码的人返 429,是在撒谎说这是他的错。
        raise HTTPException(
            status_code=503 if e.code == "sms_capacity" else 429,
            detail=detail, headers=headers or None,
        )
    except sms.SmsProviderError:
        # **502 而不是 503,是刻意与上面那条区分开的。**
        # 两者的重试建议完全不同:日额度打满要等到明天(我们自己的闸),
        # 供应商抖动几秒后就该重试。合成同一个码,前端就只能给一句含糊的"稍后再试"。
        raise HTTPException(status_code=502, detail={"code": "sms_provider_failed"})

    # **响应对"这个号有没有账号"必须一模一样** —— 否则这个不鉴权端点就是账号枚举器。
    return {"challenge_id": cid, "cooldown_sec": settings.SMS_COOLDOWN_SEC}
```

给 `/auth/register` 挂同一个限流器（在 `register` 函数体开头、`strict_box_sso_enabled()` 检查之后）：

```python
    # /auth/register 至今零限流。P3 建了 per-IP 限流器就给它用上。
    ip = client_ip_for_ratelimit(request)
    day0 = sms_challenge._today_start()
    recent = (db.query(func.count(models_db.User.id))
                .filter(models_db.User.created_at >= day0).scalar())
    # 注:按 IP 计数需要一列记录注册来源 IP。本轮不加列 —— 用一个轻量表或
    # 复用 sms_challenges 的 client_ip 列都不合适。改为**全站每日新注册上限**:
    if recent >= settings.REGISTER_DAILY_CAP:
        raise HTTPException(status_code=429, detail={"code": "register_capacity"})
```

⚠️ **实现者注意**：上面这段把"per-IP 限流"降级成了"全站每日上限"，因为 `users` 表没有记录
注册来源 IP 的列。两个选项，**实现时二选一并在提交信息里说明选了哪个**：
(a) 给 `users` 加一列 `signup_ip`（走同一套零手写 DDL 迁移，成本一行）后做真 per-IP；
(b) 就用全站每日上限，并把测试改成断言 `register_capacity`。
**推荐 (a)**——全站上限的失败模式是"今天没人能注册"，比按 IP 拦一个刷子代价大得多。

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q`
Expected: PASS（10 条）

- [ ] **Step 5: 提交**

```bash
git status --porcelain
git add katrain/web/api/v1/endpoints/auth.py katrain/web/models.py tests/web_ui/test_phone_endpoints.py
git commit -m "feat(auth): POST /auth/phone/send-code(不鉴权)+ 给 /auth/register 补限流

全站第一个'不鉴权还花钱'的端点,每条防线各一条红用例。
两条不显眼但要紧的断言:已绑号与未绑号的响应必须一模一样(否则它是账号枚举器)、
任何超限都不许返 200。

盒子三答抽成 _guard_phone_endpoint,三个端点共用:strict 403、board 503
need_online 且**不转发**(remote_client 是逐方法手写的,加转发等于多开三个
故障面;而盒子是共用触摸设备,在上面输手机号收码是最差的绑定场景)。"
```

---

### Task 8: `POST /auth/phone/login`（只登录，不注册）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py`、`katrain/web/core/auth.py`（仓储加按手机号查）、`katrain/web/models.py`
- Test: `tests/web_ui/test_phone_endpoints.py`（追加）

**Interfaces:**
- Consumes: `sms_challenge.verify_and_consume`（T6）
- Produces: `POST /api/v1/auth/phone/login` → `200 {"access_token","token_type"}`；
  `UserRepository.get_by_phone(phone_e164) -> dict | None`

- [ ] **Step 1: 写失败的测试**

```python
# 追加到 tests/web_ui/test_phone_endpoints.py
LOGIN = "/api/v1/auth/phone/login"


def test_phone_login_issues_a_token_for_a_bound_user(client, bound_user):
    cid = _send_and_get_cid(client, bound_user["phone"], "login")
    r = client.post(LOGIN, json={"challenge_id": cid, "code": _last_code()})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    # JWT 的 sub 是 username(F4)
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["username"] == bound_user["username"]


def test_phone_login_on_unbound_phone_is_404_not_a_silent_signup(client):
    """本轮**不做**手机注册(见计划开头那节收窄说明)。
    未绑号必须给一条能走的路,不许静默建号、也不许含糊报错。"""
    cid = _send_and_get_cid(client, "13900139000", "login")
    r = client.post(LOGIN, json={"challenge_id": cid, "code": _last_code()})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "phone_not_bound"


def test_phone_login_rejects_a_bind_purpose_challenge(client, bound_user):
    """拿绑定用的码去登录 —— 必须拒。"""
    cid = _send_and_get_cid(client, bound_user["phone"], "bind")
    r = client.post(LOGIN, json={"challenge_id": cid, "code": _last_code()})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "challenge_purpose_mismatch"


def test_phone_login_challenge_is_single_use(client, bound_user):
    cid = _send_and_get_cid(client, bound_user["phone"], "login")
    code = _last_code()
    assert client.post(LOGIN, json={"challenge_id": cid, "code": code}).status_code == 200
    r2 = client.post(LOGIN, json={"challenge_id": cid, "code": code})
    assert r2.status_code == 400 and r2.json()["detail"]["code"] == "challenge_consumed"


def test_phone_login_403_on_strict_box(strict_box_client):
    assert strict_box_client.post(LOGIN, json={"challenge_id": "x", "code": "1"}).status_code == 403


def test_phone_login_503_on_board_and_does_not_forward(board_client, remote_spy):
    r = board_client.post(LOGIN, json={"challenge_id": "x", "code": "1"})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "need_online_phone"
    remote_spy.assert_not_called()
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q -k phone_login`
Expected: FAIL — 404（路由不存在）

- [ ] **Step 3: 写最小实现**

`core/auth.py` 的 `UserRepository`（ABC）与其实现各加一个方法：

```python
    # UserRepository(ABC)
    @abstractmethod
    def get_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        ...

    # SqlAlchemyUserRepository
    def get_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        session = self._session()
        try:
            u = session.query(models_db.User).filter_by(phone_e164=phone_e164).one_or_none()
            return self._to_dict(u) if u else None
        finally:
            session.close()
```

⚠️ **`UserRepository` 是 ABC，测试替身不会自动长出新方法/新字段。**
`_to_dict` 这一轮要加 `"phone_bound": user_obj.phone_e164 is not None`；
pydantic `User` 加 `phone_bound: bool = False`。**替身若不同步改，所有人都会"没绑手机"
而测试不会红**（走 pydantic 默认值 False），免费额度那条分支在测试里永远走不到。
⇒ 本 Task 要加一条专门盯这个的断言：

```python
def test_repo_to_dict_carries_phone_bound(bound_user_repo):
    """默认值 False 不许被当成真值 —— 替身没同步改时这条必须红。"""
    d = bound_user_repo.get_by_phone("+8613800138000")
    assert d is not None and d["phone_bound"] is True
```

`auth.py` 端点：

```python
class PhoneLoginRequest(BaseModel):   # 放 models.py
    challenge_id: str
    code: str


@router.post("/phone/login")
async def phone_login(request: Request, body: PhoneLoginRequest, db: Session = Depends(get_db)):
    _guard_phone_endpoint(request)
    try:
        phone = sms_challenge.verify_and_consume(db, body.challenge_id, body.code, "login")
    except sms_challenge.ChallengeInvalid as e:
        raise HTTPException(status_code=400, detail={"code": e.code})

    repo = request.app.state.user_repo
    user = repo.get_by_phone(phone)
    if user is None:
        # 本轮不做手机注册(见 plan 开头的收窄说明)。给一条能走的路,不静默建号。
        raise HTTPException(
            status_code=404,
            detail={"code": "phone_not_bound",
                    "message": "这个手机号还没有绑定账号。请先用用户名密码登录，再到设置里绑定。"},
        )
    return {"access_token": create_access_token(data={"sub": user["username"]}), "token_type": "bearer"}
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q`
Expected: PASS（全部）

- [ ] **Step 5: 提交**

```bash
git status --porcelain
git add katrain/web/api/v1/endpoints/auth.py katrain/web/core/auth.py katrain/web/models.py tests/web_ui/test_phone_endpoints.py
git commit -m "feat(auth): POST /auth/phone/login —— 只登录,未绑号返 404 给出路

本轮不做手机注册(D-U2 让注册契约保持不变 ⇒ 没有用户名就建不了号)。
未绑号返 404 phone_not_bound 并在 message 里给出可走的路,不静默建号。

UserRepository 是 ABC:_to_dict 加 phone_bound 时替身不同步改的话,
所有人都会'没绑手机'而测试不会红(走 pydantic 默认值 False)。
加了一条专门盯这个默认值的断言。"
```

---

### Task 9: `POST /auth/phone/bind`（鉴权）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py`、`katrain/web/core/auth.py`（仓储加绑定）
- Test: `tests/web_ui/test_phone_endpoints.py`（追加）

**Interfaces:**
- Produces: `POST /api/v1/auth/phone/bind` → `200 {"phone_masked": str}`；
  `UserRepository.bind_phone(user_id, phone_e164) -> bool`

- [ ] **Step 1: 写失败的测试**

```python
BIND = "/api/v1/auth/phone/bind"


def test_bind_requires_auth(client):
    assert client.post(BIND, json={"challenge_id": "x", "code": "1"}).status_code == 401


def test_bind_sets_phone_and_returns_masked(auth_client):
    cid = _send_and_get_cid(auth_client, "13800138000", "bind")
    r = auth_client.post(BIND, json={"challenge_id": cid, "code": _last_code()})
    assert r.status_code == 200
    assert r.json()["phone_masked"] == "+86 138****8000"
    assert "13800138000" not in r.text          # 原始号不许整串出去
    assert auth_client.get("/api/v1/auth/me").json()["phone_bound"] is True


def test_bind_consumes_the_challenge_before_checking_uniqueness(auth_client, phone_taken_by_someone_else):
    """**核销在前、查唯一性在后。** 反过来这个端点就是号码枚举器:
    任何登录用户可逐个探测'这个号有没有账号'。核销在前意味着
    你必须先控制这个号,才配知道它被占了。"""
    cid = _send_and_get_cid(auth_client, "13800138000", "bind")
    r = auth_client.post(BIND, json={"challenge_id": cid, "code": _last_code()})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "phone_taken"
    # 关键:即使失败,challenge 也已被核销
    r2 = auth_client.post(BIND, json={"challenge_id": cid, "code": _last_code()})
    assert r2.json()["detail"]["code"] == "challenge_consumed"


def test_bind_rejects_a_login_purpose_challenge(auth_client):
    cid = _send_and_get_cid(auth_client, "13800138000", "login")
    r = auth_client.post(BIND, json={"challenge_id": cid, "code": _last_code()})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "challenge_purpose_mismatch"


def test_bind_403_on_strict_box(strict_box_auth_client):
    assert strict_box_auth_client.post(BIND, json={"challenge_id": "x", "code": "1"}).status_code == 403


def test_bind_503_on_board_and_does_not_forward(board_auth_client, remote_spy):
    r = board_auth_client.post(BIND, json={"challenge_id": "x", "code": "1"})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "need_online_phone"
    remote_spy.assert_not_called()
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q -k bind`
Expected: FAIL — 404

- [ ] **Step 3: 写最小实现**

```python
@router.post("/phone/bind")
async def bind_phone(
    request: Request,
    body: PhoneLoginRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard_phone_endpoint(request)
    # **先核销,再查唯一性。** 反过来这个端点就是号码枚举器 ——
    # 任何登录用户可逐个探测"这个号有没有账号"。
    try:
        phone = sms_challenge.verify_and_consume(db, body.challenge_id, body.code, "bind")
    except sms_challenge.ChallengeInvalid as e:
        raise HTTPException(status_code=400, detail={"code": e.code})

    repo = request.app.state.user_repo
    if not repo.bind_phone(current_user.id, phone):
        raise HTTPException(
            status_code=409,
            detail={"code": "phone_taken",
                    "message": "这个手机号已经有账号了。可以直接用验证码登录那个账号。"},
        )
    return {"phone_masked": mask_e164(phone)}
```

仓储：

```python
    def bind_phone(self, user_id: int, phone_e164: str) -> bool:
        """绑号。号已被别人占 ⇒ 返回 False(唯一索引兜底,不靠先查后写那条竞态)。"""
        session = self._session()
        try:
            u = session.query(models_db.User).filter_by(id=user_id).one()
            u.phone_e164 = phone_e164
            u.phone_verified_at = datetime.now(timezone.utc)
            session.commit()
            return True
        except IntegrityError:
            session.rollback()
            return False
        finally:
            session.close()
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py -q`
Expected: PASS（全部）

- [ ] **Step 5: 变异验证**——把 bind 里"先核销"与"查唯一性"两步对调，确认
      `test_bind_consumes_the_challenge_before_checking_uniqueness` 变红。改回来。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/api/v1/endpoints/auth.py katrain/web/core/auth.py tests/web_ui/test_phone_endpoints.py
git commit -m "feat(auth): POST /auth/phone/bind —— 先核销验证码,再查号码唯一性

顺序是防线不是风格:反过来这个端点就是号码枚举器,任何登录用户可逐个探测
'这个号有没有账号'。核销在前意味着你必须先控制这个号,才配知道它被占了。
配了一次对调两步的变异验证。

号被占返 409 并给自助出路(直接用验证码登录那个账号),不做自助换绑 ——
有换绑就有'A 号绑账号1拿一份免费额度,解绑再绑账号2拿第二份'。"
```

---

### Task 10: `POST /auth/set-password`（U5）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py`、`katrain/web/core/auth.py`、`katrain/web/models.py`
- Test: `tests/web_ui/test_set_password.py`

**为什么做**（已核实）：全仓 `hashed_password` 唯一写入点是 `core/auth.py:194 create_user`，
没有任何改密码/重置端点，也没有邮箱列 ⇒ **今天一个用户忘了密码，这个系统里没有任何人能帮他。**

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_set_password.py
SET = "/api/v1/auth/set-password"


def test_requires_auth(client):
    assert client.post(SET, json={"challenge_id": "x", "code": "1", "new_password": "pw123456"}).status_code == 401


def test_sets_password_and_old_one_stops_working(auth_client_with_phone):
    cid = _send_and_get_cid(auth_client_with_phone, "13800138000", "set_password")
    r = auth_client_with_phone.post(SET, json={"challenge_id": cid, "code": _last_code(), "new_password": "newpw123456"})
    assert r.status_code == 200
    assert _login(client, "u", "newpw123456").status_code == 200
    assert _login(client, "u", "oldpw123456").status_code == 401


def test_challenge_phone_must_match_the_current_users_phone(auth_client_with_phone, other_users_challenge):
    """少了这一步,一个人可以拿**自己号上的码**去改**别人的**密码。"""
    r = auth_client_with_phone.post(
        SET, json={"challenge_id": other_users_challenge, "code": _last_code(), "new_password": "x1234567"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "challenge_phone_mismatch"


def test_unbound_user_gets_phone_unbound_not_a_generic_error(auth_client_no_phone):
    cid = _send_and_get_cid(auth_client_no_phone, "13800138000", "set_password")
    r = auth_client_no_phone.post(SET, json={"challenge_id": cid, "code": _last_code(), "new_password": "x1234567"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "phone_unbound"


def test_rejects_a_login_purpose_challenge(auth_client_with_phone):
    cid = _send_and_get_cid(auth_client_with_phone, "13800138000", "login")
    r = auth_client_with_phone.post(SET, json={"challenge_id": cid, "code": _last_code(), "new_password": "x1234567"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "challenge_purpose_mismatch"


def test_old_tokens_still_work_after_password_change(auth_client_with_phone):
    """**已知限制,不是缺陷。** JWT 载荷只有 sub/exp/type,没有版本位
    ⇒ 改密码踢不掉已签发的旧 token,最长 7 天。与用户直觉相反,
    所以这条要有断言钉住现状 + UI 上要说出来。"""
    tok = auth_client_with_phone.headers["Authorization"]
    cid = _send_and_get_cid(auth_client_with_phone, "13800138000", "set_password")
    auth_client_with_phone.post(SET, json={"challenge_id": cid, "code": _last_code(), "new_password": "x1234567"})
    assert client.get("/api/v1/auth/me", headers={"Authorization": tok}).status_code == 200
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_set_password.py -q`
Expected: FAIL — 404

- [ ] **Step 3: 写最小实现**

```python
class SetPasswordRequest(BaseModel):    # models.py
    challenge_id: str
    code: str
    new_password: str


@router.post("/set-password")
async def set_password(
    request: Request,
    body: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """改密码。**要验证码不要当前密码** —— 解开"忘密码的人给不出当前密码"这个死结,
    同时比只验当前密码更强:会话被劫持的攻击者拿不到手机,改不了密码。

    **为什么有了手机验证码登录还要这个端点**(两位裁决者在这条上判反,这是裁定理由):
    手机登录让人"进得来",这个端点让人"把密码修好"。少了它,一个忘了密码的用户
    可以用验证码登录网页版,但**永远无法恢复口令登录** —— 而口令登录是**上盒子的唯一路**
    (kiosk 登录页只有用户名与密码两个控件)。⇒ 他会被永久挡在自己买的那台设备之外。
    """
    _guard_phone_endpoint(request)
    repo = request.app.state.user_repo
    me = repo.get_by_username(current_user.username)
    if not me or not me.get("phone_bound"):
        raise HTTPException(status_code=400, detail={"code": "phone_unbound"})
    try:
        phone = sms_challenge.verify_and_consume(db, body.challenge_id, body.code, "set_password")
    except sms_challenge.ChallengeInvalid as e:
        raise HTTPException(status_code=400, detail={"code": e.code})
    # 少了这一步,一个人可以拿自己号上的码去改别人的密码。
    if phone != repo.get_phone_e164(current_user.id):
        raise HTTPException(status_code=403, detail={"code": "challenge_phone_mismatch"})
    repo.set_password(current_user.id, get_password_hash(body.new_password))
    return {"ok": True}
```

仓储加 `set_password(user_id, hashed)` 与 `get_phone_e164(user_id)`（ABC 与实现都要加）。

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_set_password.py -q`
Expected: PASS（6 条）

- [ ] **Step 5: 提交**

```bash
git status --porcelain
git add katrain/web/api/v1/endpoints/auth.py katrain/web/core/auth.py katrain/web/models.py tests/web_ui/test_set_password.py
git commit -m "feat(auth): POST /auth/set-password —— 鉴权 + 验证码,不做免鉴权 reset

决定性事实:全仓 hashed_password 唯一写入点是 create_user,没有任何改密码端点,
也没有邮箱列 ⇒ 今天一个用户忘了密码,这个系统里没有任何人能帮他。

不做免鉴权 reset-password:验证码登录本身已经是完整的'忘密码也能进'出路;
而 reset 失败会改掉受害者的密码,攻击面严格更大,防线却是同一套。

必须有的一步:校验 challenge 的手机号 == 当前用户的手机号,
否则一个人可以拿自己号上的码去改别人的密码。

已知限制钉了一条断言:JWT 没有版本位 ⇒ 改密码踢不掉已签发的旧 token(最长 7 天)。"
```

---

### Task 11: 免费额度的手机闸（**money path，最要紧的一个 Task**）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/billing.py`、`katrain/web/api/v1/endpoints/reports.py`
- Test: `tests/web_ui/test_phone_quota_gate.py`

**机制**（D-U1-M，本 session 亲验 `quota.py:47-77`）：`_ensure_bucket` **只在行不存在时**
写 `allowance`，`peek` 取快照 ⇒ 拿 `allowance=0` 去 peek 一个未绑号用户，
**当周就开出一个 allowance=0 的桶，该用户当周绑了手机也永远拿不到额度**。
⇒ **在触碰 quota 之前短路，一行桶都不建。**

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_phone_quota_gate.py
def test_unbound_user_quota_reports_blocked_reason(auth_client_no_phone):
    r = auth_client_no_phone.get("/api/v1/billing/quota")
    fw = r.json()["free_weekly"]
    assert fw["allowance"] == 0
    assert fw["blocked_reason"] == "phone_required"


def test_bound_user_quota_has_no_blocked_reason(auth_client_with_phone):
    fw = auth_client_with_phone.get("/api/v1/billing/quota").json()["free_weekly"]
    assert fw["blocked_reason"] is None
    assert fw["allowance"] == settings.FREE_WEEKLY_REPORTS


def test_quota_does_not_create_a_bucket_for_an_unbound_user(auth_client_no_phone, db):
    """**这条是本 Task 存在的理由。**
    建了 allowance=0 的桶,该用户当周绑了手机也永远拿不到额度 —— 而
    '绑定当场生效'那条用例在没跨周的测试里看不出来。所以直接断言桶行不存在。"""
    auth_client_no_phone.get("/api/v1/billing/quota")
    assert db.query(models_db.QuotaBucket).count() == 0


def test_binding_takes_effect_in_the_same_week(auth_client_no_phone, db):
    auth_client_no_phone.get("/api/v1/billing/quota")        # 先看一眼(会诱发建桶的那个动作)
    _bind_phone(auth_client_no_phone, "13800138000")
    fw = auth_client_no_phone.get("/api/v1/billing/quota").json()["free_weekly"]
    assert fw["allowance"] == settings.FREE_WEEKLY_REPORTS   # 当周立即生效
    assert fw["blocked_reason"] is None


def test_unbound_user_report_does_not_consume_free_quota(auth_client_no_phone, db, billing_enforced):
    """未绑号 ⇒ 免费额度那条分支根本不走,直接进扣费路径。"""
    auth_client_no_phone.post("/api/v1/reports", json={"user_game_id": 1, "report_type": "normal"})
    assert db.query(models_db.QuotaBucket).count() == 0


def test_402_says_phone_not_just_no_money(auth_client_no_phone, billing_enforced, zero_balance):
    """把'你还没绑手机'伪装成'你没钱'违反 spec §3.1。"""
    r = auth_client_no_phone.post("/api/v1/reports", json={"user_game_id": 1, "report_type": "normal"})
    assert r.status_code == 402
    assert r.json()["detail"]["free_weekly_blocked"] == "phone_unbound"


def test_billing_gate_off_is_unchanged_for_everyone(auth_client_no_phone, db):
    """BILLING_ENFORCED=False 时整段早退,根本不碰 quota(已核实 reports.py:276-289)
    ⇒ 本轮改动对今天的生产零用户可见回归。"""
    r = auth_client_no_phone.post("/api/v1/reports", json={"user_game_id": 1, "report_type": "normal"})
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert db.query(models_db.QuotaBucket).count() == 0
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_quota_gate.py -q`
Expected: FAIL — `KeyError: 'blocked_reason'`；`test_quota_does_not_create_a_bucket` 红（桶被建了）

- [ ] **Step 3: 写最小实现**

`billing.py` 的 `get_quota`，把 `quota.peek(...)` 那段换成：

```python
    # **未绑手机的用户绝不能触碰 quota。**
    # quota._ensure_bucket 在第一次触碰时就把 allowance 快照钉死在桶行上
    # (quota.py:56-57,peek 的 docstring 明写"限额取桶上的快照")。
    # 拿 allowance=0 去 peek 一个未绑号用户 ⇒ 当周开出一个 allowance=0 的桶,
    # 该用户当周绑了手机也永远拿不到额度。所以在这里短路,一行桶都不建。
    #
    # 不只是"少建一行":这两种写法编码的是**不同的事实**。
    # "没有桶" = 没资格(权限事实);"allowance=0 的桶" = 有资格但额度为零(额度事实)。
    # 把前者写成后者,将来做"付费会员每周 3 次 / 免费用户 1 次 / 未绑手机 0 次"时
    # 就分不出后两者了 —— 而它们该有完全不同的引导文案。
    #
    # ⚠️ **这条短路的正确性有一个前提:不存在"解绑手机"的路径。**
    # 本轮不建换绑/解绑(见 plan 收尾清单),所以自洽。若哪天加了解绑,
    # 要回来重看这里:那时一个 used=1 的桶行会在 /quota 上突然变得不可见。
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
        ...
```

`reports.py` 的免费额度分支，条件加一项：

```python
    if task.report_type == "normal" and settings.FREE_WEEKLY_REPORTS > 0 and current_user.phone_bound:
```

以及 402 的 detail 加一格：

```python
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "insufficient_credits",
                    ...
                    # 未绑号时说清楚:否则我们在把"你还没绑手机"伪装成"你没钱"。
                    "free_weekly_blocked": None if current_user.phone_bound else "phone_unbound",
                },
            )
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_quota_gate.py -q`
Expected: PASS（7 条）

- [ ] **Step 5: 变异验证（这个 Task 必做）**

把 `billing.py` 的短路改成 decider-2 那种写法：

```python
    used, allowance = quota.peek(db, current_user.id, "free_report:week",
                                 allowance=settings.FREE_WEEKLY_REPORTS if current_user.phone_bound else 0)
```

确认 **`test_quota_does_not_create_a_bucket_for_an_unbound_user` 与
`test_binding_takes_effect_in_the_same_week` 两条同时变红**。改回短路。

这次变异就是这个 Task 的全部价值：它证明"看起来等价的两种写法"里有一种是坏的。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/api/v1/endpoints/billing.py katrain/web/api/v1/endpoints/reports.py tests/web_ui/test_phone_quota_gate.py
git commit -m "feat(billing): 每周免费复盘闸在'已绑手机'上,且在触碰 quota 之前短路

亲验 quota.py:47-77:_ensure_bucket 只在行不存在时写 allowance,peek 取快照
⇒ 拿 allowance=0 去 peek 一个未绑号用户,当周就开出一个 allowance=0 的桶,
该用户当周绑了手机也永远拿不到额度。所以短路,一行桶都不建。

配了变异验证:换成'allowance=0 表达式'那种写法,
'不建桶'与'绑定当周生效'两条同时变红 —— 两种看起来等价的写法里有一种是坏的。

blocked_reason 是必需的:没有它前端分不出'没绑手机'与'本周已用完'。
402 加 free_weekly_blocked,否则我们在把'你还没绑手机'伪装成'你没钱'。"
```

---

### Task 12: 发言闸（实名义务的正确落点）

**Files:**
- Modify: `katrain/web/server.py`（对局聊天）、`katrain/web/api/v1/endpoints/live.py`（直播评论）
- Test: `tests/web_ui/test_posting_requires_phone.py`

**依据**：《网络安全法》二十六条约束的是**为用户提供信息发布、即时通讯服务**，
不是"有账号" ⇒ 正确落点是**未绑手机不得发言**，而不是关掉注册（D-U2）。

- [ ] **Step 1: 写失败的测试**

```python
# tests/web_ui/test_posting_requires_phone.py
def test_chat_from_unbound_user_gets_an_error_message_not_silence(ws_unbound):
    """照抄 server.py 里已有的口径:'说一句而不是静默丢弃 ——
    静默丢弃时发言的人看不出自己没发出去'。"""
    ws_unbound.send_json({"type": "chat", "text": "hello"})
    msg = ws_unbound.receive_json()
    assert msg["type"] == "error" and msg["code"] == "chat_requires_phone"


def test_chat_from_bound_user_is_broadcast(ws_bound, ws_observer):
    ws_bound.send_json({"type": "chat", "text": "hello"})
    assert ws_observer.receive_json()["text"] == "hello"


def test_unbound_user_message_is_not_broadcast_to_anyone(ws_unbound, ws_observer):
    """光有错误回执不够 —— 得确认它真的没广播出去。"""
    ws_unbound.send_json({"type": "chat", "text": "leak"})
    ws_unbound.receive_json()
    assert not _has_pending(ws_observer)


def test_live_comment_from_unbound_user_is_403(auth_client_no_phone):
    r = auth_client_no_phone.post("/api/v1/live/matches/m1/comments", json={"content": "hi"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "comment_requires_phone"


def test_live_comment_from_bound_user_succeeds(auth_client_with_phone):
    assert auth_client_with_phone.post("/api/v1/live/matches/m1/comments", json={"content": "hi"}).status_code == 200
```

- [ ] **Step 2: 跑，确认它红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_posting_requires_phone.py -q`
Expected: FAIL — 未绑号的聊天被正常广播；评论返 200

- [ ] **Step 3: 写最小实现**

`server.py` 的 chat 分支，紧跟现有的 `if current_user is None:` 之后：

```python
                    if current_user is None:
                        await websocket.send_json({"type": "error", "code": "chat_requires_identity"})
                        continue
                    # 实名义务约束的是"提供信息发布/即时通讯服务"(网安法二十六条),
                    # 不是"有账号" —— 所以闸在这里,不在注册。
                    # 口径与上面那条一致:说一句,不静默丢弃。
                    # ⚠️ 这里的 current_user 是 WS 上下文里的对象,与 live.py 里
                    # Depends(get_current_user) 拿到的 pydantic User **不是同一个类型**。
                    # 用 getattr 兜底 ⇒ 属性缺失时**所有人都发不了言**(fail-closed)。
                    # 方向是安全的,但可用性代价大 —— 实现时**必须先确认这个对象上
                    # 到底有没有 phone_e164**,不要靠 getattr 蒙混过去。
                    # 确认方法:在这一行打一次日志跑通一局对局聊天,看它是哪个类。
                    if not getattr(current_user, "phone_e164", None):
                        await websocket.send_json({"type": "error", "code": "chat_requires_phone"})
                        continue
```

`live.py` 的 `create_comment` 函数体开头：

```python
    if not getattr(current_user, "phone_bound", False):
        raise HTTPException(
            status_code=403,
            detail={"code": "comment_requires_phone",
                    "message": "发表评论需要先绑定手机号。"},
        )
```

- [ ] **Step 4: 跑，确认它绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_posting_requires_phone.py -q`
Expected: PASS（5 条）

- [ ] **Step 5: 提交**

```bash
git status --porcelain
git add katrain/web/server.py katrain/web/api/v1/endpoints/live.py tests/web_ui/test_posting_requires_phone.py
git commit -m "feat(auth): 未绑手机不得发言(对局聊天 + 直播评论)

实名义务约束的是'提供信息发布/即时通讯服务'(网安法二十六条),不是'有账号'
⇒ 闸的正确落点是发言,不是注册。这也是 D-U2 保持注册契约不变的依据之一。

聊天那条照抄同一处已有的口径:说一句而不是静默丢弃 ——
静默丢弃时发言的人看不出自己没发出去。
配一条断言确认消息真的没广播出去(光有错误回执不够)。"
```

---

### Task 13: 前端 API 与 AuthContext

**Files:**
- Modify: `katrain/web/ui/src/api.ts`（**共享领土**）、`katrain/web/ui/src/context/AuthContext.tsx`（**共享领土**）
- Test: `katrain/web/ui/src/context/__tests__/AuthContext.phone.test.tsx`

**Interfaces:**
- Produces: `API.sendPhoneCode(phone, purpose)`、`API.loginByPhone(challengeId, code)`、
  `API.bindPhone(challengeId, code)`、`API.setPassword(challengeId, code, newPassword)`；
  `useAuth().loginByPhone(challengeId, code)`

⚠️ **`api.ts` 与 `AuthContext.tsx` 都在共享领土**：本 Task 的改动 kiosk 包也会吃进去，
所以 **`npm run build` 与 `npm run build:kiosk-2d` 都要绿**。
**`API.register` 一个字节不动**（D-U2）——`src/components/RegisterDialog.tsx` 与
`ZenModeApp` 因此不受影响。

- [ ] **Step 1: 写失败的测试**

```tsx
// src/context/__tests__/AuthContext.phone.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { API } from '../../api';

describe('手机验证码 API', () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it('sendPhoneCode 把 purpose 一起送出去', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ challenge_id: 'c1', cooldown_sec: 60 }), { status: 200 }));
    await API.sendPhoneCode('13800138000', 'login');
    const [url, init] = f.mock.calls[0];
    expect(url).toBe('/api/v1/auth/phone/send-code');
    expect(JSON.parse(init!.body as string)).toEqual({ phone: '13800138000', purpose: 'login' });
  });

  it('loginByPhone 只送 challenge_id 与 code —— 不送手机号', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ access_token: 't', token_type: 'bearer' }), { status: 200 }));
    await API.loginByPhone('c1', '123456');
    const body = JSON.parse(f.mock.calls[0][1]!.body as string);
    expect(body).toEqual({ challenge_id: 'c1', code: '123456' });
    expect(Object.keys(body)).not.toContain('phone');
  });

  it('限流时把后端的 code 与 retry_after_sec 原样抛出去,不吞成通用错误', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
      JSON.stringify({ detail: { code: 'sms_cooldown', retry_after_sec: 42 } }), { status: 429 }));
    await expect(API.sendPhoneCode('13800138000', 'login')).rejects.toMatchObject({
      code: 'sms_cooldown', retryAfterSec: 42,
    });
  });

  it('register 的请求体没有被改动 —— 共享领土,ZenModeApp 也在用', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    await API.register('u', 'p');
    expect(JSON.parse(f.mock.calls[0][1]!.body as string)).toEqual({ username: 'u', password: 'p' });
  });
});
```

- [ ] **Step 2: 跑，确认它红**

Run: `cd katrain/web/ui && npx vitest run src/context/__tests__/AuthContext.phone.test.tsx`
Expected: FAIL — `API.sendPhoneCode is not a function`

- [ ] **Step 3: 写最小实现**

`api.ts` 加（**放在 `register` 之后，不动 `register`**）：

```ts
  /** 后端的失败码要原样带到 UI —— 吞成通用错误的话,用户看到"操作失败"
   *  而我们已经知道是"还需等待 42 秒"。 */
  _phonePost: async (path: string, body: Record<string, unknown>) => {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...API._authHeader() },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      let detail: any = {};
      try { detail = (await response.json()).detail ?? {}; } catch { /* 非 JSON 响应 */ }
      const err: any = new Error(detail.message || `请求失败 ${response.status}`);
      err.code = detail.code;
      err.retryAfterSec = detail.retry_after_sec;
      err.status = response.status;
      throw err;
    }
    return response.json();
  },

  sendPhoneCode: (phone: string, purpose: 'login' | 'bind' | 'set_password') =>
    API._phonePost("/api/v1/auth/phone/send-code", { phone, purpose }),

  loginByPhone: (challengeId: string, code: string) =>
    API._phonePost("/api/v1/auth/phone/login", { challenge_id: challengeId, code }),

  bindPhone: (challengeId: string, code: string) =>
    API._phonePost("/api/v1/auth/phone/bind", { challenge_id: challengeId, code }),

  setPassword: (challengeId: string, code: string, newPassword: string) =>
    API._phonePost("/api/v1/auth/set-password",
      { challenge_id: challengeId, code, new_password: newPassword }),
```

`AuthContext.tsx` 加 `loginByPhone`（照现有 `login` 的形状：拿到 token 后同样存储并拉 `/auth/me`）。

- [ ] **Step 4: 跑，确认它绿**

Run: `cd katrain/web/ui && npx vitest run src/context/__tests__/AuthContext.phone.test.tsx`
Expected: PASS（4 条）

- [ ] **Step 5: 两个构建都要绿**（共享领土的硬要求）

```bash
cd katrain/web/ui
npm run build && npm run build:kiosk-2d
```
Expected: 两个都退出 0；`build:kiosk-2d` 链着的 `verify:kiosk-2d` 也要 0。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/ui/src/api.ts katrain/web/ui/src/context/AuthContext.tsx \
        katrain/web/ui/src/context/__tests__/AuthContext.phone.test.tsx
git commit -m "feat(ui): 手机验证码四个 API + loginByPhone

api.ts 与 AuthContext 都在共享领土 ⇒ 两个构建都跑过。
**API.register 一个字节不动**(D-U2 保持注册契约不变)⇒
共享的 components/RegisterDialog.tsx 与 ZenModeApp 不受影响,
配了一条断言钉住它的请求体。

后端的失败码原样带到 UI:吞成通用错误的话用户看到'操作失败',
而我们已经知道是'还需等待 42 秒'。"
```

---

### Task 14: 登录框第三种模式 + 区号选择器 + i18n

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/auth/CountryCodeSelect.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx`
- Test: `katrain/web/ui/src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx`

⚠️ **i18n 默认值写中文**（spec §2.8）。现有 `LoginModal.tsx` 通篇写英文默认值，**是反例，别照抄**。
新增的键一律 `i18n.t('auth:xxx', '中文默认')`；顺带把本次触碰到的旧键默认值改成中文。

- [ ] **Step 1: 写失败的测试**

```tsx
// src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LoginModal from '../LoginModal';

describe('LoginModal 手机验证码模式', () => {
  it('默认是密码模式,能切到验证码模式', () => {
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    expect(screen.getByLabelText('手机号')).toBeTruthy();
    expect(screen.queryByLabelText('密码')).toBeNull();
  });

  it('发码按钮在倒计时期间禁用并显示剩余秒数', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByText('获取验证码'));
    await waitFor(() => expect(screen.getByRole('button', { name: /60 ?秒/ })).toBeDisabled());
  });

  it('成功文案是"已提交发送"不是"已发送到您的手机"', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByText('获取验证码'));
    // 我们没有回执,不知道有没有到 —— 说"已发送到您的手机"是在替运营商担保。
    await waitFor(() => expect(screen.getByText(/已提交发送/)).toBeTruthy());
    expect(screen.queryByText(/已发送到您的手机/)).toBeNull();
  });

  it('限流时显示后端给的具体原因,不显示通用"操作失败"', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockRejectedValue(
      Object.assign(new Error('x'), { code: 'sms_cooldown', retryAfterSec: 42 }));
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByText('获取验证码'));
    await waitFor(() => expect(screen.getByText(/还需等待 42 秒/)).toBeTruthy());
  });

  it('未绑号的 404 给出可走的路,不是干巴巴的失败', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    vi.spyOn(API, 'loginByPhone').mockRejectedValue(
      Object.assign(new Error('x'), { code: 'phone_not_bound', status: 404 }));
    // ...填号、填码、提交
    await waitFor(() => expect(screen.getByText(/还没有绑定账号/)).toBeTruthy());
  });

  it('区号选择器默认 +86 且能改', () => {
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    expect(screen.getByDisplayValue('+86')).toBeTruthy();
  });

  it('忘记密码切到验证码登录,不跳独立重置流程', () => {
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('忘记密码？'));
    expect(screen.getByLabelText('手机号')).toBeTruthy();
  });

  it('所有新增文案的默认值是中文', () => {
    // 反例在同一个文件里:现有键写的是英文默认值。
    const src = readFileSync('src/galaxy/components/auth/LoginModal.tsx', 'utf8');
    const defaults = [...src.matchAll(/i18n\.t\('auth:[a-z_]+',\s*'([^']*)'\)/g)].map(m => m[1]);
    const added = defaults.filter(d => /手机|验证码|等待|绑定|提交/.test(d) === false && /^[A-Za-z ?'.!]+$/.test(d));
    // 本轮新增的键必须全中文;旧键不在本条管辖内(逐个列出豁免名单)
    expect(added.filter(d => !LEGACY_ENGLISH_DEFAULTS.includes(d))).toEqual([]);
  });
});
```

- [ ] **Step 2: 跑，确认它红**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx`
Expected: FAIL — 找不到「验证码登录」

- [ ] **Step 3: 写实现**

`CountryCodeSelect.tsx`（**不引第三方国家库**，与后端同一条约束）：

```tsx
/** 区号选择器。**内置一份短名单 + 允许手输**,不引第三方国家库 ——
 *  我们只需要拼出 E.164,真正的号段合法性由运营商说了算。 */
const COMMON = [
  { cc: '+86', label: '中国大陆' }, { cc: '+852', label: '中国香港' },
  { cc: '+853', label: '中国澳门' }, { cc: '+886', label: '中国台湾' },
  { cc: '+1',  label: '美国/加拿大' }, { cc: '+81', label: '日本' },
  { cc: '+82', label: '韩国' }, { cc: '+65', label: '新加坡' },
  { cc: '+44', label: '英国' }, { cc: '+61', label: '澳大利亚' },
];
```

`LoginModal.tsx`：把 `isRegister: boolean` 换成 `mode: 'login' | 'register' | 'phone'`，
验证码模式渲染「区号 + 手机号 + 获取验证码（带倒计时）+ 验证码 + 登录」，
「忘记密码？」切到 `phone` 模式（不跳独立流程）。

- [ ] **Step 4: 跑，确认它绿**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/components/auth/__tests__/LoginModal.phone.test.tsx`
Expected: PASS（8 条）

- [ ] **Step 5: 两个构建 + 全量前端单测**

```bash
cd katrain/web/ui && npm test && npm run build && npm run build:kiosk-2d
```

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/ui/src/galaxy/components/auth/
git commit -m "feat(ui): 登录框加验证码登录模式 + 区号选择器

'忘记密码?'切到验证码登录,不跳独立重置流程 —— 验证码登录本身就是
完整的'忘密码也能进'出路,再做一个免鉴权 reset 是同一件事实现两遍。

三条文案是判据不是措辞:成功说'已提交发送'不说'已发送到您的手机'
(我们没有回执,不知道有没有到);限流显示后端给的具体原因不显示'操作失败';
未绑号的 404 给出可走的路。i18n 默认值全中文 —— 同一个文件里的旧键
写的是英文默认值,是反例。"
```

---

### Task 15: 隐私政策与独立同意（spec §1.1 的最后一项）

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/auth/PhoneConsent.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx`
- Test: `katrain/web/ui/src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx`

**为什么单独一个 Task**：手机号是个人信息，收集前要**告知**并取得**单独同意**
（《个人信息保护法》十四条/十七条的口径：同意必须是在充分知情前提下自愿、明确作出，
且处理敏感个人信息或变更用途时要取得单独同意）。「单独」的操作含义是：
**不能与"同意服务条款"打包在一个勾选里，也不能默认勾上。**

⚠️ **这一项只做前端的告知与同意闸，不做后端的同意留痕**（那要一张表、一份留存期限策略，
本轮不做，写进收尾清单）。这意味着：**同意状态只挡住提交按钮，不构成可举证的合规记录。**
不要在任何地方声称它是。

- [ ] **Step 1: 写失败的测试**

```tsx
// src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import LoginModal from '../LoginModal';

describe('手机号收集的告知与单独同意', () => {
  it('验证码模式下同意项默认**不**勾选', () => {
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    expect((screen.getByRole('checkbox', { name: /隐私政策/ }) as HTMLInputElement).checked).toBe(false);
  });

  it('未勾选时「获取验证码」不可点 —— 不许先发了码再问', () => {
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeDisabled();
  });

  it('勾上之后才可点', () => {
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /隐私政策/ }));
    expect(screen.getByRole('button', { name: '获取验证码' })).not.toBeDisabled();
  });

  it('同意项是**单独**的 —— 不与服务条款合并成一个勾选', () => {
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    const label = screen.getByRole('checkbox', { name: /隐私政策/ }).closest('label')!.textContent!;
    // 「我已阅读并同意《服务条款》和《隐私政策》」这种打包写法不合格
    expect(label).not.toMatch(/服务条款/);
  });

  it('明写收集什么、干什么用 —— 只给一个链接不算告知', () => {
    render(<LoginModal open onClose={() => {}} />);
    fireEvent.click(screen.getByText('验证码登录'));
    const text = screen.getByTestId('phone-consent').textContent!;
    expect(text).toMatch(/手机号/);
    expect(text).toMatch(/身份验证|登录/);
  });

  it('密码登录模式下不出现这个同意项 —— 那里不收集手机号', () => {
    render(<LoginModal open onClose={() => {}} />);
    expect(screen.queryByTestId('phone-consent')).toBeNull();
  });
});
```

- [ ] **Step 2: 跑，确认它红**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx`
Expected: FAIL — 找不到 `phone-consent`

- [ ] **Step 3: 写实现**

```tsx
// src/galaxy/components/auth/PhoneConsent.tsx
/** 手机号收集的告知与**单独**同意。
 *
 * 「单独」的操作含义:不与"同意服务条款"打包成一个勾选,且**默认不勾**。
 * 打包或默认勾上的同意在合规上等于没取得。
 *
 * 只给一个《隐私政策》链接不算告知 —— 收什么、干什么用要写在眼前这一行里。
 */
interface Props { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; }

const PhoneConsent = ({ checked, onChange, disabled }: Props) => (
  <Box data-testid="phone-consent" sx={{ mt: 1 }}>
    <FormControlLabel
      control={<Checkbox checked={checked} onChange={(e) => onChange(e.target.checked)} disabled={disabled} />}
      label={
        <Typography variant="body2">
          {i18n.t('auth:phone_consent', '我同意智星盒收集我的手机号，用于身份验证与登录。')}
          {' '}
          <Link href="/privacy" target="_blank" rel="noopener noreferrer">
            {i18n.t('auth:privacy_policy', '《隐私政策》')}
          </Link>
        </Typography>
      }
    />
  </Box>
);
```

`LoginModal.tsx`：`mode === 'phone'` 时渲染它，并把「获取验证码」按钮的
`disabled` 加上 `|| !consent`。**同意状态只在本次会话内有效，不持久化**
（持久化就要谈留存期限，本轮不做）。

- [ ] **Step 4: 跑，确认它绿**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/components/auth/__tests__/PhoneConsent.test.tsx`
Expected: PASS（6 条）

- [ ] **Step 5: 确认 `/privacy` 这个链接真的到得了**

```bash
grep -rn '"/privacy"\|path="privacy"' katrain/web/ui/src --include='*.tsx' | grep -v node_modules
```
**如果没有这条路由，本 Task 不算完**：一个 404 的隐私政策链接比没有链接更糟——
它看起来像做到了告知义务，实际没有。两个选项，实现时二选一：
(a) 加一个 `/privacy` 静态页（内容至少写清：收集手机号、用途是身份验证与登录、
    存储期限、如何撤回同意与删除）；
(b) 链到已有的政策页（若有），并确认它里面确实写了手机号这一项。

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add katrain/web/ui/src/galaxy/components/auth/
git commit -m "feat(ui): 手机号收集的告知与单独同意

'单独'的操作含义是不与服务条款打包、且默认不勾 —— 打包或默认勾上的同意
在合规上等于没取得,所以这两条各有一条断言。只给一个链接不算告知,
收什么/干什么用要写在眼前那一行里,也有断言。

本轮**只做前端的告知与同意闸,没有后端留痕**(那要一张表和一份留存期限策略)。
⇒ 同意状态只挡住提交按钮,不构成可举证的合规记录,已写进收尾清单。"
```

---

### Task 16: 真浏览器验收 + 基线比对 + 两个构建

**Files:** 无新增（验收 Task）

- [ ] **Step 1: 全量 pytest 与分支基线比对**

```bash
cd /Users/fan/Repositories/katrain-phone-login
./.venv/bin/python -m pytest tests -q 2>&1 | tee /tmp/pytest-phone-after.log | tail -3
grep -E '^(FAILED|ERROR) tests/' /tmp/pytest-phone-after.log \
  | sed -E 's/^(FAILED|ERROR) //; s/ - .*$//' | sort -u > /tmp/after.txt
comm -23 /tmp/after.txt superpowers/tracks/phone-login/test-baseline.txt
```
Expected: **`comm -23` 输出为空**（新增失败为零）。
比的是**失败名字集合**不是条数 —— 条数相同也可能是"修好一条、弄坏一条"。

- [ ] **Step 2: 两个前端构建**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d
```
Expected: 都退出 0（`build:kiosk-2d` 链着的 `verify:kiosk-2d` 也要 0）。

- [ ] **Step 3: 真浏览器走一遍完整流程**

用 `/browse`（项目规定：所有网页浏览走 gstack 的 `/browse`，不用 `mcp__claude-in-chrome__*`）。
本地起 `KATRAIN_SMS_PROVIDER=console python -m katrain --ui web`，从服务端日志里读验证码。

逐项确认（**jsdom 对这些无权作证**）：
1. 登录框切到「验证码登录」，区号默认 +86，输号 → 点「获取验证码」→ 按钮变倒计时且禁用。
2. 服务端日志出现 `[SMS console] to=+86 138****8000` —— **掩码不是明文**。
3. 未绑号提交 → 屏幕上出现「还没有绑定账号」那句可走的路，**不是** "Operation failed"。
4. 用密码登录一个账号 → 设置页绑定手机 → 回到复盘页，免费额度从「绑定手机号可每周免费复盘」
   变成「本周剩余 1 次」，**同一周内**。
5. 未绑号账号在对局里发一句聊天 → 屏幕上有回执，**不是石沉大海**。
6. 60 秒内再点「获取验证码」→ 屏幕上是「还需等待 N 秒」，**不是** "操作失败"。

- [ ] **Step 4: 承重结构实测**（登录框长高了 —— 这条链变了）

把浏览器窗口压到 **430×640**（最矮的常见移动档），验证码模式下：
```js
const d = document.querySelector('[role="dialog"]');
({ client: d.clientHeight, scroll: d.scrollHeight, canScroll: d.scrollHeight > d.clientHeight })
```
Expected: 内容比可视高时 `canScroll === true` 且滚轮真能推动
（`scrollTop` 从 0 推到 > 0）。**先确认 `scrollHeight > clientHeight` 真的成立**——
不成立说明状态没造出来，这一步还没做完。

- [ ] **Step 5: 把证据写进 track**

把 Step 3/4 的截图与读数写进 `superpowers/tracks/phone-login/verification.md`，
一并提交。**没有读数的那几项不许标"已验"。**

- [ ] **Step 6: 提交**

```bash
git status --porcelain
git add superpowers/tracks/phone-login/verification.md
git commit -m "test(phone-login): 真浏览器验收 + 基线比对零新增失败

比的是失败名字集合不是条数 —— 条数相同也可能是修好一条弄坏一条。
承重实测:验证码模式让登录框长高,430x640 下确认对话框真能滚
(先确认 scrollHeight > clientHeight 成立,不成立说明状态没造出来)。"
```

---

## 收尾：本轮明确没做、要交回给 Fan 的

1. **真短信通道没开。** `aliyun` 提供方按文档实现并有签名向量的单测，但**没有凭据、没有实发过一条**。
   国内签名报备要 5–10 个工作日且不承诺时效，**是这条路的关键路径且它不在代码里**。
   补充事实：签名 **6 个月无发送记录会失效**。
2. **`SMS_DAILY_CAP_INTL` 的值待定**：两个裁决者给的数不一致（100 vs 50）。按 100 落，实发前复核。
3. **不做自助换绑与解绑**（走人工客服直接改库）。这是"一号一账号"论证的**必要前提**——
   有换绑就有"A 号绑账号1拿一份，解绑再绑账号2拿第二份"。
   **上量后要补自助换绑时，必须同时补「旧号 N 天内不可再注册」，否则这个前提当场失效。**
4. **手机丢了 = 账号丢了**（没有邮箱、密保、人工申诉）。
5. **改密码踢不掉旧 token**（JWT 无版本位，最长 7 天）。
6. **不做手机注册**（见开头收窄说明）。
7. **`billing.py:5-10` 的模块头注释说反话**（写着 balance 会 fall through 到远程，实际直接 503），
   非本轮修，已记。
8. **同意没有后端留痕**（Task 15 只做了前端的告知与同意闸）。要成为可举证的合规记录，
   还需要一张同意记录表 + 留存期限策略。**不要对外声称本轮已具备该记录。**
9. **`/privacy` 页的内容归属未定**：Task 15 只保证链接可达，页面里到底写了什么
   （存储期限、如何撤回、如何删除）需要 Fan 或法务定稿。

10. **F12：跑 pytest 会改掉 `engine_game_state.json`**，非本轨道缺陷，已记，本轨道靠"不用 `git add -A`"规避。
