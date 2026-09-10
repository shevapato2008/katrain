r"""每周免费复盘只发给已绑手机的人，**且未绑号时一行桶都不建**。

`quota._ensure_bucket` 只在**行不存在时**才 `QuotaBucket(..., allowance=allowance)`，
`peek` 的 docstring 明写「限额取桶上的快照」⇒ 拿 allowance=0 去 peek 一个未绑号用户，
当周就开出一个 allowance=0 的桶，该用户当周绑了手机也永远拿不到额度。
所以在触碰 quota 之前短路。

不只是「少建一行」：两种写法编码的是**不同的事实**。「没有桶」= 没资格（权限事实）；
「allowance=0 的桶」= 有资格但额度为零（额度事实）。把前者写成后者，将来做
「付费会员每周 3 次 / 免费用户 1 次 / 未绑手机 0 次」时就分不出后两者了 ——
而它们该有完全不同的引导文案。

全仓只有两处会建桶（2026-09-10 实测 `grep -rn "quota\." katrain/`）：
`billing.get_quota` 的 `quota.peek` 与 `reports.create_report_task` 的 `quota.try_consume`。
`report_reaper` 走的 `quota.release` 是裸 UPDATE，不建行；`quota.period_key` 是纯函数。
所以**两点短路是穷尽的**，不存在第三个要堵的口子。

夹具形状取自同轨道的 tests/web_ui/test_phone_bind.py 与 test_set_password.py
（tmp_path + monkeypatch，不用还原全局 settings），另加 `/user-games/` 与 `/reports/`
需要的四个 state。**不要**把它写成「照抄 test_report_charging.py，那是唯一同时接住
两条接缝的先例」—— 那句话是假的：全仓 7 个测试文件设了 `report_session_factory`。

本文件不写 `@pytest.mark.asyncio`：pyproject.toml 里 `asyncio_mode = "auto"`。
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
    #   GET /billing/quota -> get_db（core/db.py 的模块级 SessionLocal）
    #   POST /reports/     -> get_report_db（`getattr(state, "report_session_factory",
    #                        SessionLocal)` —— 漏接不会报错，会**静默**退回模块级库）
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


async def test_bound_user_quota_has_no_blocked_reason(app, client, monkeypatch):
    # **把「有额度可发」写成前提，不要读环境值**：`FREE_WEEKLY_REPORTS` 没有 env 开关，
    # 哪天有人把默认值改成 0（config.py 里那条开闸指令要求的正是这个），
    # `== settings.FREE_WEEKLY_REPORTS` 会退化成 `0 == 0` —— 空断言，而且照样绿。
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)
    _make_user(app, "hasphone", phone="+8613800138000")
    h = await _auth(client, "hasphone")
    fw = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert fw["allowance"] == 1
    assert fw["blocked_reason"] is None


async def test_quota_does_create_a_bucket_for_a_bound_user(app, client, db):
    """**正对照，本组第一条。它守的是夹具接线，不是实现** —— 别读成后者。

    没有它，下一条的 `count() == 0` 证明不了任何事：桶可能只是建在了另一个库里
    （/quota 走 get_db、POST /reports 走 get_report_db，两条接缝）。这条证明本文件的
    `db` 夹具确实看得见 /quota 那一路的写。实测：对实现变异它几乎零杀伤，
    独有的杀伤全在「漏接一条接缝」那一侧。

    ⚠️ 它的价值只在**模块级 `SessionLocal` 可达**的环境（CI 的 sqlite 默认值）里兑现。
    本机 `katrain/config.json` 把 DATABASE_URL 指向连不上的 postgresql://localhost:5432，
    于是漏接 override 时会先炸在 psycopg2 上 —— 看着像有人守，其实守它的是一个连不上的库。
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


async def test_binding_takes_effect_in_the_same_week(app, client, monkeypatch):
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)  # 同上：别读环境值，见上一条注释
    _make_user(app, "later")
    h = await _auth(client, "later")
    await client.get(QUOTA, headers=h)          # 先看一眼（就是会诱发建桶的那个动作）
    _bind_phone(app, "later")
    fw = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert fw["allowance"] == 1, "当周绑定必须当场生效"
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


async def test_402_does_not_blame_the_phone_for_a_deep_report(app, client, monkeypatch):
    """**深度复盘对谁都不免费** ⇒ 未绑号的人在这里被 402，绑了号也还是 402。

    免费分支的条件有**三项**（`report_type == "normal"` / `FREE_WEEKLY_REPORTS > 0` /
    `phone_bound`），`free_weekly_blocked` 只抄其中一项就会说假话：用户照着这个字段
    去发短信、绑号、再试一次 —— 拿到的是同一个 402。这和 `/retry` 那处**不加**这个键
    是同一条判据（「绑了手机就能过」这句话在这里不成立），只是回头量了自己。
    """
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)
    _make_user(app, "deepbroke", credits=0)
    h = await _auth(client, "deepbroke")
    gid = await _make_game(client, h)

    r = await client.post(REPORTS, json={"user_game_id": gid, "report_type": "deep"}, headers=h)
    assert r.status_code == 402
    assert r.json()["detail"]["free_weekly_blocked"] is None, "深度复盘本来就不免费，别赖手机"


async def test_402_does_not_blame_the_phone_when_free_quota_is_off(app, client, monkeypatch):
    """`FREE_WEEKLY_REPORTS=0` 是**开闸当天的官方配置**（config.py 那条警告），
    此时免费额度对谁都不发 ⇒ 同样不许把 402 归因到手机上。"""
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 0)
    _make_user(app, "offbroke", credits=0)
    h = await _auth(client, "offbroke")
    gid = await _make_game(client, h)

    r = await client.post(REPORTS, json={"user_game_id": gid, "report_type": "normal"}, headers=h)
    assert r.status_code == 402
    assert r.json()["detail"]["free_weekly_blocked"] is None, "额度功能整个关着，绑号也没用"


async def test_quota_does_not_blame_the_phone_when_free_quota_is_off(app, client, monkeypatch):
    """同一把尺子量 `/quota`：额度关着时，未绑号与已绑号拿到的东西一模一样（都是 0），
    只对前者显示「去绑手机」就是让他白跑一趟。"""
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 0)
    _make_user(app, "nophone")
    h = await _auth(client, "nophone")
    fw = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert fw["allowance"] == 0
    assert fw["blocked_reason"] is None, "额度关着不是手机的问题"


async def test_no_bucket_is_pinned_while_free_quota_is_off(app, client, db, monkeypatch):
    """**配置轴上的同一个失效模式** —— 本 Task 只修了手机那根轴，这条守另一根。

    `FREE_WEEKLY_REPORTS=0` 时给已绑号用户 peek 一次，就会开出一个 allowance=0 的桶；
    运维随后把它改成 1（P3 落地开闸就是这个动作），该用户当周再复盘时
    `used + 1 <= allowance` 拿的是钉死的旧快照 0 ⇒ 要等下个 ISO 周才领得到。
    所以 `/quota` 的短路判据必须与 `reports.py` 免费分支**同形**：额度关着时也不建桶。
    """
    from katrain.web.core import models_db

    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 0)
    _make_user(app, "hasphone", phone="+8613800138000")
    h = await _auth(client, "hasphone")
    assert (await client.get(QUOTA, headers=h)).status_code == 200
    assert db.query(models_db.QuotaBucket).count() == 0, "额度关着时看一眼不该钉死本周的桶"

    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)  # 运维开闸
    fw = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert fw["allowance"] == 1, "开闸必须当周生效，不能等下个 ISO 周"


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
    """**正对照**：BILLING_ENFORCED=False 时 `if not settings.BILLING_ENFORCED:` 整段早退，
    未绑号用户建复盘的行为与本轮改动前逐字相同（生产该值默认就是 False）。

    **判据是「没动钱」，不是「返回了 200」。** 早先只断言 200/pending/零桶那一版，
    在「把手机闸过度应用到早退条件上」的变异下**一次都不红**：未绑号用户掉进扣费臂、
    `billing.reserve` 因为夹具给了满额积分而成功，照样 200/pending/零桶。
    所以余额与 `charge_ref` 这两句才是这条用例的本体。

    覆盖范围只到 `POST /reports/` 这一条路。`/billing/quota` 的响应形状**确实**变了
    （未绑号从 `{used:0, allowance:1}` 变成 `{0, 0, "phone_required"}`），那是本轮
    有意为之、且与总闸无关 —— 由 `test_unbound_user_quota_reports_blocked_reason`
    与 `test_quota_says_phone_even_while_the_billing_gate_is_off` 两条各自守着。
    """
    from katrain.web.core import models_db

    monkeypatch.setattr(settings, "BILLING_ENFORCED", False)
    _make_user(app, "nophone", credits=10_000)
    h = await _auth(client, "nophone")
    gid = await _make_game(client, h)

    r = await client.post(REPORTS, json={"user_game_id": gid, "report_type": "normal"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert db.query(models_db.QuotaBucket).count() == 0
    task = db.query(models_db.ReportTask).one()
    assert task.charge_ref is None, "闸关着时不许授权扣费"
    assert task.free_grant_period is None, "闸关着时也不该消费免费额度"
    assert db.query(models_db.User).filter_by(username="nophone").one().credits == 10_000, "一分钱都不许动"


async def test_quota_says_phone_even_while_the_billing_gate_is_off(app, client, monkeypatch):
    """**钉住一个有意的裁定**（复审里有两个视角想把它改掉，理由是实测不成立的）。

    `blocked_reason` 解释的是**它自己那个对象里的那几个数**，所以它为真当且仅当
    「绑上号会让这几个数变」。总闸关着时绑号仍会让 `allowance` 从 0 变成 N
    （下面就量这件事）⇒ `phone_required` 是真话，**不要**把 `BILLING_ENFORCED`
    并进 `billing.py` 那个短路条件。总闸开没开由同一份响应里的 `billing_enforced` 自己说。

    对照 `FREE_WEEKLY_REPORTS=0` 那根轴：那里绑号后 peek 拿到的还是 0、数不变，
    所以那里就**不能**说 phone_required —— 由 `test_quota_does_not_blame_the_phone_when_free_quota_is_off` 守。
    两根轴的处理不同，不是不一致，是同一把尺子量出来的两个结果。
    """
    monkeypatch.setattr(settings, "BILLING_ENFORCED", False)
    monkeypatch.setattr(settings, "FREE_WEEKLY_REPORTS", 1)
    _make_user(app, "offbound")
    h = await _auth(client, "offbound")
    before = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert before == {"used": 0, "allowance": 0, "blocked_reason": "phone_required"}

    _bind_phone(app, "offbound")
    after = (await client.get(QUOTA, headers=h)).json()["free_weekly"]
    assert after["allowance"] == 1, "绑号确实改变了这几个数 —— 所以上面那句 phone_required 不是假话"
    assert after["blocked_reason"] is None
