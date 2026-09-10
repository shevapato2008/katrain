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
async def test_rejections_still_count_toward_the_phone_hourly_cap(db, monkeypatch):
    """**合并后生产的默认稳态**：aliyun + 空凭据 ⇒ 每一次发送都是 `SmsRejected`。

    这条稳态下另外两道闸都不响：冷却只认 `delivered_ok is True` 的行（拒收的行永远是
    False），日额度也不涨（拒收确定未计费 ⇒ `provider_charged` 被改回 False）。
    于是挡在不鉴权的 send-code 前面的**只剩 per-phone / per-IP 两个计数器** ——
    它们数的是「行的存在」、只按 `created_at` 过滤、不看结局，所以上界仍然成立。
    这条用例就是证明那个"仍然"。

    没有它，把第 2 步的计数改成只数成功行、或者随拒收一起把行删掉，都不会有任何用例变红，
    而线上表现是 send-code 变成一个**没有限流的公开端点**（每次拒收都免费）。
    上面那条 `test_rejected_send_does_not_count_against_the_daily_cap` 只断言"不占日额度"，
    在那个世界里同样是绿的 —— 两条合起来才把拒收的代价说全。
    """
    monkeypatch.setattr(sc.settings, "SMS_PHONE_HOURLY", 3)
    monkeypatch.setattr(sc.sms, "get_provider",
                        lambda: _P(raise_=sc.sms.SmsRejected("MOBILE_NUMBER_ILLEGAL")))
    for _ in range(3):                                        # 不用 _advance：拒收不起冷却
        with pytest.raises(sc.sms.SmsRejected):
            await sc.issue(db, PHONE_CN, "login", IP1)
    rows = db.query(models_db.SmsChallenge).filter_by(phone_e164=PHONE_CN).all()
    assert len(rows) == 3                                     # 行留着，这才是拒收的成本所在
    assert [r.provider_charged for r in rows] == [False, False, False]

    _SENT.clear()
    with pytest.raises(sc.RateLimited) as e:                  # 第 4 次撞小时闸
        await sc.issue(db, PHONE_CN, "login", IP1)
    assert e.value.code == "sms_quota_phone"
    assert _SENT == []                                        # 且拦在打到 provider **之前**


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
