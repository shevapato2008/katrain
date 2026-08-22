"""会话清理不许把服务挂住。

2026-08-22 本机抓到现行：web 服务一小时内两次「进程还在、端口还听着、
对所有请求不回话」。`sample <pid>` 采下来的栈是决定性的 ——
主线程（uvloop 事件循环）停在 `lock_PyThread_acquire_lock`，
25 个线程里 18 个的栈上都有同一把锁，没有一个停在阻塞 `read()` 上。
那是一条**锁队列**，不是「换页慢」（我一开始把换页排在第一位，采到栈之后排除了）。

链路是三段叠起来的：

    _cleanup_loop（跑在事件循环上）
      → cleanup_expired() 持 SessionManager._lock
        → KataGoEngine.shutdown() 里三个 t.join() **没有超时**

三段各修一处，**少改任何一处，另外两处都还能把服务挂住**：

  1. 别在事件循环上做   → `server.py` 改成 `await asyncio.to_thread(...)`
  2. 别持着锁做         → `session.py` 锁内只 pop，关引擎放锁外
  3. 别无限等           → `engine.py` 的 join / wait 都有上界，超时记日志

下面三条各守一段。判据都落在**行为**上（另一条线程能不能进来、
调用多久返回、跑在哪个线程），不落在源码文本上。
"""

import asyncio
import threading
import time

import pytest

from katrain.core.engine import KataGoEngine
from katrain.web.server import _cleanup_loop
from katrain.web.session import SessionManager


class _SlowShutdown:
    """把 `session.katrain.shutdown` 换成一个卡住的实现，模拟 KataGo 不肯退。"""

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def __call__(self, *args, **kwargs):
        self.entered.set()
        self.release.wait(timeout=10)
        self.finished.set()


def _call_with_deadline(fn, deadline):
    """在另一条线程上调用 fn，最多等 deadline 秒。返回 (是否按时返回, 结果)。"""
    box = {}

    def run():
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001 - 测试里要把异常也带回来
            box["error"] = exc

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=deadline)
    return (not t.is_alive()), box


def test_cleanup_does_not_hold_the_manager_lock_while_shutting_engines_down():
    """一个关不掉的引擎不许挡住其他请求取会话。

    改之前：`_cleanup_locked` 在**锁内**调 `session.katrain.shutdown()`，
    于是每一个要这把锁的请求（get_session / create_session / remove_session）
    都排在那个卡住的 shutdown 后面 —— 服务对所有请求无响应。

    变异记录（2026-08-22 实跑）：把 `cleanup_expired` 改回
    `with self._lock: ... session.katrain.shutdown()` → 本条红，
    `get_session` 在 2 秒内没有返回。
    """
    manager = SessionManager(session_timeout=1, enable_engine=False)

    doomed = manager.create_session()
    alive = manager.create_session()

    slow = _SlowShutdown()
    doomed.katrain.shutdown = slow
    doomed.last_access = 0.0  # 立刻算过期
    alive.touch()

    sweeper = threading.Thread(target=manager.cleanup_expired, daemon=True)
    sweeper.start()
    assert slow.entered.wait(timeout=5), "清理线程没有走到 shutdown，用例前提不成立"

    # shutdown 还卡着的这段时间里，另一条线程必须能照常拿到锁。
    on_time, box = _call_with_deadline(lambda: manager.get_session(alive.session_id), deadline=2.0)
    assert on_time, "shutdown 卡住时 get_session 也被挡住了 —— 关引擎还在锁内"
    assert box.get("value") is alive

    # 新建会话同样不许被挡住（它走的是同一把锁）。
    on_time, box = _call_with_deadline(manager.create_session, deadline=5.0)
    assert on_time, "shutdown 卡住时 create_session 也被挡住了"

    slow.release.set()
    sweeper.join(timeout=5)
    assert slow.finished.is_set()
    # 过期的那个确实被摘掉了 —— 免得「没挡住」是因为压根没清理。
    with pytest.raises(KeyError):
        manager.get_session(doomed.session_id)


def test_engine_shutdown_gives_up_on_a_thread_that_never_exits():
    """`t.join()` 必须有上界，否则调用方永远回不来。

    这里不启真的 KataGo：`shutdown` 是个叶子方法，把它需要的几个属性摆好就能测。
    超时值调小到 50ms，测的是**有没有上界**，不是那个具体秒数。

    变异记录（2026-08-22 实跑）：把 `t.join(timeout=...)` 改回 `t.join()`
    → 本条挂死，被 pytest 的 deadline 判红。
    """
    engine = object.__new__(KataGoEngine)
    engine.SHUTDOWN_JOIN_TIMEOUT = 0.05
    engine.SHUTDOWN_REAP_TIMEOUT = 0.05
    engine.katago_process = None

    logged = []
    engine.katrain = type("_Log", (), {"log": lambda self, msg, level=None: logged.append(str(msg))})()

    stuck = threading.Event()
    never_exits = threading.Thread(target=lambda: stuck.wait(timeout=30), daemon=True, name="stuck-analysis")
    never_exits.start()
    engine.write_stdin_thread = never_exits
    engine.analysis_thread = None
    engine.stderr_thread = None

    started = time.monotonic()
    engine.shutdown()
    elapsed = time.monotonic() - started

    assert elapsed < 2.0, f"shutdown 等了 {elapsed:.1f}s —— join 没有上界"
    assert any("did not exit" in line for line in logged), "放弃等待时必须记一条日志，不能悄悄跳过"
    stuck.set()


def test_engine_shutdown_reaps_a_child_that_ignores_sigterm():
    """`terminate()` 之后必须 `wait()`，否则留下僵尸子进程（本机确实看到过一个）。

    变异记录（2026-08-22 实跑）：删掉 `process.wait(...)` / `process.kill()` 那一段
    → 本条红（`killed` 为 False、`waited` 为空）。
    """
    import subprocess

    class _StubbornChild:
        def __init__(self):
            self.terminated = False
            self.killed = False
            self.waited = []

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            self.waited.append(timeout)
            if not self.killed:
                raise subprocess.TimeoutExpired(cmd="katago", timeout=timeout)
            return 0

    child = _StubbornChild()
    engine = object.__new__(KataGoEngine)
    engine.SHUTDOWN_JOIN_TIMEOUT = 0.05
    engine.SHUTDOWN_REAP_TIMEOUT = 0.05
    engine.katago_process = child
    engine.write_stdin_thread = None
    engine.analysis_thread = None
    engine.stderr_thread = None
    logged = []
    engine.katrain = type("_Log", (), {"log": lambda self, msg, level=None: logged.append(str(msg))})()

    engine.shutdown()

    assert child.terminated, "没有先发 SIGTERM"
    assert child.killed, "SIGTERM 被无视之后没有 kill —— 子进程会留成僵尸"
    assert len(child.waited) >= 2, "kill 之后也必须再 wait 一次把它收掉"
    assert any("ignoring" in line or "ignored" in line for line in logged)


@pytest.mark.asyncio
async def test_cleanup_sweep_runs_off_the_event_loop(monkeypatch):
    """清理必须跑在别的线程上 —— 它是同步的，还会关子进程。

    改之前 `_cleanup_loop` 里是裸的 `manager.cleanup_expired()`，
    整段活儿都在事件循环线程上，它一慢，服务对所有请求就没有响应。

    变异记录（2026-08-22 实跑）：把 `await asyncio.to_thread(...)` 改回
    `manager.cleanup_expired()` → 本条红（两个线程 id 相同）。
    """
    loop_thread_id = threading.get_ident()
    seen = {}

    class _Manager:
        def cleanup_expired(self):
            seen["thread"] = threading.get_ident()

    real_sleep = asyncio.sleep

    async def instant_sleep(_seconds):
        await real_sleep(0)

    monkeypatch.setattr("katrain.web.server.asyncio.sleep", instant_sleep)

    task = asyncio.create_task(_cleanup_loop(_Manager()))
    for _ in range(200):
        if "thread" in seen:
            break
        await real_sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert "thread" in seen, "一轮清理都没跑到"
    assert seen["thread"] != loop_thread_id, "清理跑在事件循环线程上 —— 它一慢，整个服务就没有响应"
