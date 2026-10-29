"""Four spawn workers for kifu list reads; no application/game state is copied."""

import asyncio
from concurrent.futures import ProcessPoolExecutor
import gc
import json
import logging
import multiprocessing
from multiprocessing.util import Finalize
import os
from threading import get_ident
from time import perf_counter, time

from fastapi import HTTPException


_engine = _factory = _startup_barrier = None
_GC_LOGGER = logging.getLogger("katrain_web.kifu_gc_pause")


def _gc_pause_observer():
    started = {}

    def observe(phase, info):
        generation = info["generation"]
        if phase == "start":
            started[generation] = (perf_counter(), time(), get_ident())
        elif phase == "stop":
            timing = started.pop(generation, None)
            if timing is None:
                return
            duration_ms = (perf_counter() - timing[0]) * 1000
            if duration_ms >= 20:
                metric = dict(event="kifu_gc_pause", pid=os.getpid(), thread_ident=timing[2])
                metric.update(generation=generation, start_unix_s=timing[1], duration_ms=duration_ms)
                metric.update(collected=info["collected"], uncollectable=info["uncollectable"])
                _GC_LOGGER.info(json.dumps(metric, separators=(",", ":")))

    return observe


def _initialize(database_url, policy_signature, barrier):
    global _engine, _factory, _startup_barrier
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import configure_mappers, sessionmaker
        from katrain.web.api.v1.endpoints import kifu

        configure_mappers()
        if kifu.current_policy_signature() != policy_signature:
            raise RuntimeError("Kifu reader policy mismatch")
        # Only primitives enter the child. This engine and every Session belong
        # to this spawned process; its tasks execute serially.
        _engine = create_engine(database_url, pool_size=1, max_overflow=0, pool_pre_ping=True)
        _factory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        _startup_barrier = barrier
        Finalize(None, _engine.dispose, exitpriority=10)
    except Exception:
        # ProcessPoolExecutor prints initializer failures. Do not expose a URL,
        # SQL parameters, or exception payload there.
        raise RuntimeError("Kifu reader initialization failed") from None


def _ready():
    # Holding one job in each worker forces all four to finish initialization
    # before startup succeeds, without querying or warming any player data.
    _startup_barrier.wait(timeout=30)
    return os.getpid()


def _snapshot():
    pool = _engine.pool
    return {"size": pool.size(), "checkedout": pool.checkedout(), "overflow": pool.overflow()}


def _read(params, submitted_at):
    from katrain.web.api.v1.endpoints.kifu import read_in_owned_session
    from starlette.responses import JSONResponse

    timings = {}
    reader_pool = {"worker_pid": os.getpid(), "before_read": _snapshot()}
    result = {"timings": timings, "reader_pool": reader_pool}
    try:
        model = read_in_owned_session(_factory, submitted_at=submitted_at, timings=timings, **params)
        started = perf_counter()
        # Same JSON representation and allow_nan=False behavior as the public
        # response, fully materialized while still in the reader process.
        result["body"] = JSONResponse(model.model_dump(mode="json", by_alias=True)).body
        timings["kifu_serialization"] = (perf_counter() - started) * 1000
    except HTTPException as exc:
        # HTTPException itself cannot reliably be unpickled by ProcessPool.
        result["error"] = {"status_code": exc.status_code, "detail": exc.detail, "headers": exc.headers}
    except Exception:
        result["error"] = _unavailable_detail()
    finally:
        reader_pool["after_read"] = _snapshot()
    return result


def _unavailable_detail():
    return {"status_code": 503, "detail": {"code": "kifu_reader_unavailable", "message": "Kifu reader is unavailable"}}


class KifuReadExecutor:
    def __init__(self, database_url):
        from katrain.web.kifu.prepared_read import current_policy_signature

        context = multiprocessing.get_context("spawn")
        self._pool = ProcessPoolExecutor(
            max_workers=4,
            mp_context=context,
            initializer=_initialize,
            initargs=(database_url, current_policy_signature(), context.Barrier(4)),
        )
        self.worker_pids = frozenset()
        self._closed = False
        self._slots = asyncio.Semaphore(32)
        self._gc_observer = _gc_pause_observer()

    async def start(self):
        if self._gc_observer not in gc.callbacks:
            gc.callbacks.append(self._gc_observer)
        try:
            ready = [asyncio.wrap_future(self._pool.submit(_ready)) for _ in range(4)]
            self.worker_pids = frozenset(await asyncio.wait_for(asyncio.gather(*ready), timeout=40))
            if len(self.worker_pids) != 4:
                raise RuntimeError("Kifu reader startup incomplete")
        except Exception:
            await self.close()
            raise RuntimeError("Kifu reader startup failed") from None

    async def read(self, params):
        if self._closed or not self.worker_pids:
            raise HTTPException(**_unavailable_detail())
        if self._slots.locked():
            raise HTTPException(status_code=503, detail={"code": "kifu_reader_busy", "message": "Kifu reader is busy"})
        await self._slots.acquire()
        try:
            future = self._pool.submit(_read, params, perf_counter())
        except Exception:
            self._slots.release()
            raise HTTPException(**_unavailable_detail()) from None
        # Cancellation of an HTTP waiter must not release a still-running
        # process job's admission slot. Only its concurrent Future owns it.
        loop = asyncio.get_running_loop()
        future.add_done_callback(lambda _: loop.call_soon_threadsafe(self._slots.release))
        try:
            return await asyncio.wrap_future(future)
        except Exception:
            raise HTTPException(**_unavailable_detail()) from None

    async def close(self):
        self._closed = True
        # Finish submitted read-only jobs, then each child's finalizer disposes
        # its own engine. The web process and writer work remain untouched.
        try:
            await asyncio.to_thread(self._pool.shutdown, wait=True)
        finally:
            if self._gc_observer in gc.callbacks:
                gc.callbacks.remove(self._gc_observer)
