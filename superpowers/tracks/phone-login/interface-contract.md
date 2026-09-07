# P3 接口契约（**本 session 逐条读源码核实过，不是推的**）

改计划的每个人都以这份为准。与它冲突的写法一律错。

## 仓里既有的事实（核实过）

| 事实 | 位置 | 含义 |
|---|---|---|
| 仓储类叫 `SQLAlchemyUserRepository`（不是 `SqlAlchemy…`） | `core/auth.py:94` | 按错的大小写 grep 会找不到 |
| 取会话一律 `self.session_factory()`（**没有** `self._session()`） | `core/auth.py:112/191/210/220` | 全类 12 处都这么写 |
| 按用户名查叫 `get_user_by_username`（**不是** `get_by_username`） | `core/auth.py:62`(抽象) / `:210`(实现) | |
| 模块顶部 **只** `from datetime import datetime, timedelta` | `core/auth.py:3` | **没有 `timezone`**；`IntegrityError` 在 `create_user` 函数体内才 import（`:202`） |
| pydantic `User` 字段：id/uuid/username/rank/net_wins/elo_points/credits/is_admin/avatar_url/created_at | `models.py:176-186` | **没有 `phone_e164`**，pydantic v2 默认 `extra='ignore'` 会静默丢弃 |
| `_to_dict` 是显式白名单，全仓只有一个生产实现 | `core/auth.py:323` / `:94` | 加字段只此一处 |
| `hashed_password` 唯一写入点 | `core/auth.py:194` `create_user` | 没有任何改密码路径 |
| `assert_secret_key_is_safe` **定义**在 config.py:13，**唯一调用点**在 `server.py:176`（`_lifespan_server` 内） | | config.py 里**没有**调用，只有 `:6` 的一句注释 |
| `conftest.py` 用 `os.environ.setdefault("KATRAIN_SECRET_KEY", …)` 注入，并写明「不要改成测试时跳过这个闸」 | `tests/conftest.py:70` | SMS 闸照抄这个形状 |
| `/auth/login` 收 **JSON**（`login_data: LoginRequest`），不是表单 | `endpoints/auth.py:232` | 测试用 `json=` 不是 `data=` |
| `get_user_from_token` → `User(**user_dict)`；WS 与 `get_current_user` **同一个** | `endpoints/auth.py:106-125`；`server.py:2770` | 两处是同一个 pydantic `User` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` = 7 天，**`REFRESH_TOKEN_EXPIRE_DAYS = 90`** | `config.py:73-74` | `/auth/refresh` 只验签名 + 用户名存在，**不看密码改没改** |
| 前端鉴权头是模块级 `authHeaders(token?)`（**不是** `API._authHeader()`） | `ui/src/api.ts:297` | 既有代码一律 `authHeaders(token)` |
| `useAuth` / `useSettings` 没有 Provider 时**抛异常** | `AuthContext.tsx:156` / `SettingsContext.tsx:15` | 裸 `render(<LoginModal/>)` 当场炸 |
| 组件测试的现成范式：`MemoryRouter` + `SettingsProvider` + `vi.mock` 掉 AuthContext | `galaxy/pages/report/ReportsPage.test.tsx` | 照抄它 |
| 测试环境 `i18n.t(key, 默认值)` 返回**默认值**（`translations` 初值 `{}`，setup 不加载） | `ui/src/i18n.ts` | 所以测试里用中文字面量 `getByText('验证码登录')` 能命中 |
| 仓里**已有**隐私政策正文 `ui/src/legal/privacy.ts`，**零 importer、无路由**；正文一个字没提手机号 | | `/privacy` 今天落到禅模式棋盘，不是 404 |
| `LoginModal.tsx` 里 `isRegister` 分布在 8 行 11 处 | `galaxy/components/auth/LoginModal.tsx` | 含 `handleSubmit` 第一道守卫 `if (!username \|\| !password)` |
| `POST /reports` 先按 `UserGame.id AND user_id` 查，查不到 **404**，在计费之前 | `endpoints/reports.py:247-256` | 测试必须先建 UserGame 行 |
| `/billing/quota` 走 `get_db`，`POST /reports` 走 `get_report_db`（`app.state.report_session_factory`） | `core/db.py:46` / `reports.py:127` | **两条不同的库接缝**，夹具要接到同一个库 |

## 本轮要产出的名字（**唯一真源**）

```python
# katrain/web/core/phone.py
normalize_e164(raw: str, default_region_cc: str = "86") -> str      # 失败抛 ValueError
is_domestic(e164: str) -> bool
mask_e164(e164: str) -> str

# katrain/web/core/client_ip.py
client_ip_for_ratelimit(request: Request) -> str

# katrain/web/core/sms.py
class SmsProviderError(Exception): ...          # 基类
class SmsRejected(SmsProviderError): ...        # 供应商**明确拒收**(Code != OK) ⇒ 确定没计费 ⇒ **不计入日额度**
class SmsUnreachable(SmsProviderError): ...     # 超时/连不上 ⇒ 不知道收没收 ⇒ **计入日额度**
class SmsProvider:  async def send(phone_e164: str, code: str, is_intl: bool) -> None
get_provider() -> SmsProvider

# katrain/web/core/sms_challenge.py
async issue(db, phone_e164: str, purpose: str, client_ip: str) -> str        # 返 challenge_id
verify_and_consume(db, challenge_id: str, code: str, purpose: str) -> str    # 返 phone_e164
class RateLimited(Exception):    .code: str   .retry_after_sec: int | None
class ChallengeInvalid(Exception): .code: str

# katrain/web/core/config.py
assert_sms_provider_is_configured(mode: str, provider: str) -> None
# 调用点：server.py 的 _lifespan_server,紧跟 assert_secret_key_is_safe(server.py:176) 之后

# katrain/web/core/auth.py :: UserRepository(ABC) 与 SQLAlchemyUserRepository 各加
get_by_phone(phone_e164: str) -> Optional[Dict[str, Any]]
bind_phone(user_id: int, phone_e164: str) -> str    # 返 "ok" | "phone_taken" | "already_bound"
get_phone_e164(user_id: int) -> Optional[str]
set_password_hash(user_id: int, hashed: str) -> None
# _to_dict 加一行：  "phone_bound": user_obj.phone_e164 is not None

# katrain/web/models.py :: pydantic User 加
phone_bound: bool = False        # **只加这个布尔,不加 phone_e164**
```

## 三条口径（违反即错）

1. **所有闸一律读 `current_user.phone_bound`**，不读 `phone_e164`，不用 `getattr` 兜底。
   pydantic 字段有默认值 ⇒ 属性必然存在；用 `getattr` 会掩盖"字段没加上"这个错误，
   而它的失败方向是**所有人都被拒**。
2. **不把 `phone_e164` 加进 pydantic `User` 或 `_to_dict`**：发言闸只需要一个布尔，
   灌原始号会让它随 `User` 泄进任何回 `User` 的响应（`models.py:189` 的 `OnlineUser`
   收窄注释正是为防这类外溢）。原始号只由 `repo.get_phone_e164(user_id)` 单点取。
3. **时区比较不许用无守卫的 `.replace(tzinfo=utc)`**：SQLite 读回 naive（单测恒绿），
   PG 读回带会话时区偏移的 aware，`.replace()` 抹掉真实偏移 ⇒ 生产上 elapsed 变负、
   每个用户第一次取码就被判冷却。统一用：
   ```python
   def _as_utc(dt):
       return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
   ```
