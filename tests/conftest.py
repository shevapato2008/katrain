"""测试进程不许写开发机的真实数据库。

2026-08-23 实测：全套 3300 个用例里有**五个文件**会往 `settings.DATABASE_URL`
指着的那个真库里写：

  写 users / user_games —— 每跑一轮 19 个 `alice-/bob-/mallory-<8hex>` 用户 + 6 局
    tests/web_ui/test_game_termination_and_chat_identity.py
    tests/test_local_play_recording.py
  经 `init_db()` → `backfill_ai_ladder_decisions` 对**真实账本表**发
  `UPDATE ai_ladder_game_ledger SET counted = TRUE …`
    tests/test_local_play_setup.py
    tests/web_ui/test_ladder_injection.py
    tests/web_ui/test_ai_ladder_api.py

外加 34 张表全部由 `init_db()` 建出来。发现时库里已积了 646 个测试用户 / 662 行
（真实账号只剩 16 个）、230 行 user_games。

**「两个文件」是这条闸推翻的第一个结论。** 我先用 SQL 探针只监听
`INSERT INTO users|user_games` 两张表，量出「只有两个文件」；闸监听全部写语句、
全部表，一上来就多抓出三个 —— 而它们写的是账本，比建用户严重。
**探针把判据选窄了，闸没有。** 同族陷阱还有一个：失败名字集合 diff 只暴露
「新变红」的，`test_local_play_setup.py` 本来就红（401）又同时在污染，
在 diff 里完全不可见，只有闸看得见。**权威名单是闸的输出，不是 diff。**

**根因不是「夹具忘了清理」，是注入点被生命周期无条件覆盖。**
`tests/web_ui/test_game_termination_and_chat_identity.py` 的 fixture 该做的全做了：
自己的 `tmp_path` 库、自己的 engine、`create_all` 绑自己的 engine、
`app.state.user_repo` 注入、`finally` 还原 `settings.DATABASE_URL`。可
`TestClient(app)` 会跑 lifespan，而 `_lifespan_server` 无条件用全局 `SessionLocal`
重建 6 个 repo 再覆盖 `app.state`（`katrain/web/server.py`）—— 注入发生在
`TestClient` 之前，覆盖发生在之后。那个 tmp 库从头到尾一行没写过，
**而测试一直是绿的**：断言只看 HTTP 行为，数据落哪儿都自洽。

修法是给两支 lifespan 各开一条接缝：`app.state.session_factory`。没人设 → 退回
全局 `SessionLocal`，生产行为逐字不变。`SQLAlchemyUserRepository.init_db()` 同时
改成用自己 `session_factory` 的 bind（原来它写死抓全局 engine，于是调用方注入了
也白注入）。

这条闸的判据落在**实际发出的 SQL** 上，不落在源码文本上：在 SQLAlchemy 的
`Engine` 类级事件上挂监听，凡是写语句命中「会话开始时解析出来的那个
DATABASE_URL」，当场抛错并指名是哪个用例。源码文本判不了这件事 —— 上面那个
fixture 逐行读都是对的。

**为什么是「拦住」不是「跑完删干净」**：删干净要求每一条路径都记得删，漏一条就
静默复发（这正是过去 500 多行的由来）；拦住只要求一处正确，而且漏网的时候是红的。
"""

import os
import tempfile

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine, make_url

# --- 测试进程必须拿一个合规的 SECRET_KEY -------------------------------------
#
# `create_app()` 会调 `assert_secret_key_is_safe()`，服务端模式下拒绝以仓库里那个
# 字面量默认值启动（那是个公开已知的 JWT 签名密钥，任何人都能拿它伪造任意用户）。
# 测试如果不注入，所有建 app 的用例会集体红。
#
# **注入点选环境变量，不是给某个 settings 实例赋值**：`test_lobby_api.py` /
# `test_social_api.py` 会 `importlib.reload(config)`，那会重新执行模块顶层、
# 造出一个**全新的 Settings 实例**；给旧实例打的补丁在 reload 之后就没了。
# 而 `Settings` 的装配每次都读 `os.getenv`，所以环境变量能穿过 reload —— 已实测。
#
# 这样测试走的是**和生产同一条路**（真的带着一个合规密钥启动），而不是给闸开后门。
# 不要改成「测试时跳过这个闸」：那样闸在测试里就是死的，将来谁把它改坏都不会红。
os.environ.setdefault(
    "KATRAIN_SECRET_KEY",
    "pytest-only-secret-key-not-for-any-deployment-0123456789",
)

from katrain.web.core.config import settings

# 会话开始时解析出来的那一个。tests/conftest.py 在**任何测试模块导入之前**执行，
# 所以后面那些在模块导入期改写 `settings.DATABASE_URL` / `os.environ` 的文件
# （test_billing_api / test_reports_api / test_social_api / test_ai_game_autosave …）
# 都影响不到这里取到的值 —— 闸守的始终是开发机自己那个库。
_PROTECTED_URL = str(settings.DATABASE_URL)

_WRITE_VERBS = frozenset({"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE", "REPLACE", "UPSERT"})

_current_test = {"id": "<收集 / 模块导入阶段>"}


def _identity(url) -> tuple:
    """把 URL 归一成可比较的身份。

    不能直接比字符串：SQLAlchemy 2.0 的 `str(engine.url)` 会把密码打码成
    `***`，与 config 里读到的原串永远不相等 —— 那样闸会静默失效并报绿。
    """
    u = make_url(url) if isinstance(url, str) else url
    driver = u.drivername.split("+", 1)[0]
    database = u.database or ""
    if driver == "sqlite" and database:
        database = os.path.realpath(database)
    return (driver, u.host, u.port, database)


def _temp_roots() -> set:
    """本机所有算「临时目录」的根，全部 realpath 过。

    只用 `tempfile.gettempdir()` 是不够的：macOS 上它返回 per-user 的
    `/var/folders/…/T`，而 `/tmp`（realpath 后是 `/private/tmp`）同样是临时目录。
    第一版只比 `gettempdir()`，于是 `/private/tmp/...` 下的库被判成了「真库」——
    方向偏严、不会假绿，但注释说的分支从来没真正执行过。
    """
    candidates = {tempfile.gettempdir(), os.environ.get("TMPDIR") or "", "/tmp", "/var/tmp"}
    return {os.path.realpath(c) for c in candidates if c}


def _is_ephemeral(url) -> bool:
    """一次性库不设防：内存库，或落在系统临时目录下的 sqlite 文件。

    这条让「把 KATRAIN_DATABASE_URL 指到临时 sqlite 再跑」这种取证/调试用法
    不会被自己的闸挡住，同时不给真库开任何口子 —— 真库要么是 PostgreSQL，
    要么是仓库/家目录里的 sqlite，都不在临时目录下。
    """
    u = make_url(url) if isinstance(url, str) else url
    if u.drivername.split("+", 1)[0] != "sqlite":
        return False
    if not u.database or u.database == ":memory:":
        return True
    real = os.path.realpath(u.database)
    return any(real.startswith(root + os.sep) for root in _temp_roots())


_PROTECTED = _identity(_PROTECTED_URL)
_ARMED = not _is_ephemeral(_PROTECTED_URL)


def pytest_report_header(config):
    if _ARMED:
        driver, host, port, database = _PROTECTED
        where = f"{driver}://{host or ''}{':' + str(port) if port else ''}/{database}"
        return f"real-db write guard: ARMED on {where}"
    return f"real-db write guard: 未武装（{_PROTECTED_URL} 是一次性库）"


def pytest_runtest_setup(item):
    _current_test["id"] = item.nodeid


def pytest_runtest_teardown(item, nextitem):
    _current_test["id"] = f"{item.nodeid}（teardown 之后 / 下一个用例之前）"


@pytest.fixture
def isolated_session_factory(tmp_path):
    """一次性库 + 绑上去的 sessionmaker。

    用法 —— 必须在进 `TestClient(app)` / 触发 lifespan **之前**设：

        app.state.session_factory = isolated_session_factory

    只设 `app.state.user_repo` 不管用：`_lifespan_server` / `_lifespan_board` 会把
    `app.state` 上的全部六个 repo 无条件重建覆盖掉。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # 延迟导入：放模块级会在**任何**一次 pytest 启动时就把全局 engine 建出来。
    from katrain.web.core import models_db  # noqa: F401  —— 让 Base.metadata 装齐
    from katrain.web.core.db import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'isolated.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    try:
        yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    finally:
        engine.dispose()


@event.listens_for(Engine, "before_cursor_execute")
def _forbid_writes_to_the_real_db(conn, cursor, statement, parameters, context, executemany):
    if not _ARMED:
        return
    if _identity(conn.engine.url) != _PROTECTED:
        return
    head = statement.lstrip()[:16].split(None, 1)
    if not head or head[0].upper() not in _WRITE_VERBS:
        return
    raise RuntimeError(
        "测试往开发机的真实数据库写了。\n"
        f"  用例   : {_current_test['id']}\n"
        f"  目标库 : {_PROTECTED[0]}://{_PROTECTED[1] or ''}/{_PROTECTED[3]}\n"
        f"  语句   : {' '.join(statement.split())[:160]}\n"
        "\n"
        "多半是走到了全局 `katrain.web.core.db.SessionLocal`。测试要用自己的库，\n"
        "就在进 `TestClient(app)` / 触发 lifespan **之前**设 `app.state.session_factory`：\n"
        "\n"
        "    engine = create_engine(f'sqlite:///{tmp_path}/x.db', connect_args={'check_same_thread': False})\n"
        "    Base.metadata.create_all(bind=engine)\n"
        "    app.state.session_factory = sessionmaker(bind=engine)\n"
        "\n"
        "只设 `app.state.user_repo` 不管用 —— lifespan 会把它连同另外 5 个 repo 一起覆盖掉。"
    )


# ──────────────────────────────────────────────────────────────────────────────
# katrain/config.json 是**提交进仓的源文件**，但测试会把它改掉。
#
# `KaTrainBase(force_package_config=True)` 会把 _config_store 指向包内的
# katrain/config.json，于是任何 update_config / save_config 都直接写进工作区的
# 那个文件。tests/web_ui/test_settings_snapshot.py 就这么干：它把
# trainer/eval_thresholds 写成 [0.5, 1.0, 2.0, 4.0, 8.0, 16.0] 并落盘。
#
# 后果不是「测试之间互相污染」这么轻——它会**静默改写一个被提交的源文件**：
#   * 这大概就是仓里那份升序 eval_thresholds 的由来（升序会让 evaluation_class
#     的六级梯子塌成两级，见 tests/test_move_grade.py）；
#   * 本次实修那个方向时，它把修好的值吃掉过两次，每次都只表现为
#     `git diff` 里多出一段看起来与本次改动无关的 diff。
#
# 这里在会话结束时把文件恢复原样，并说清楚是谁动的。根治要让
# force_package_config 的实例写到临时文件去，那是另一件事。
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _restore_packaged_config_json():
    # 按用例恢复，不是按会话。按会话恢复挡不住**会话内的顺序耦合**：
    # 先跑的用例把 eval_thresholds 写成升序，后跑的断言就读到脏值，
    # 表现为「换个 -k 顺序结果就不一样」。
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "katrain", "config.json")
    try:
        with open(path, "rb") as f:
            before = f.read()
    except OSError:
        yield
        return
    yield
    try:
        with open(path, "rb") as f:
            after = f.read()
    except OSError:
        return
    if after != before:
        with open(path, "wb") as f:
            f.write(before)
        print(
            "\n[conftest] 测试改写了被提交的 katrain/config.json，已恢复。"
            "\n           写它的是 force_package_config=True 的实例上的 update_config/save_config"
            "\n           （tests/web_ui/test_settings_snapshot.py 是已知的一处）。"
        )
