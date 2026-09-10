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
