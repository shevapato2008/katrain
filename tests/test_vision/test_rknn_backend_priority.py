"""RKNN `init_runtime()` 会把**调用它的线程**的 nice 改成 -19(NPU 驱动在内核里改,
走 ioctl 不走 setpriority,strace 过滤 setpriority 看不见)。katrain 在主线程上 load,
⇒ 主线程与之后它建的所有线程(视觉循环、MJPEG 推流)都以 -19 跑,标定收尾时把
Chromium 饿住 6–8 s,点「返回」排队连退出 katrain(2026-09-21 RK3562 实测,
A/B:-19 冻结 5788/8292 ms,调回 0 后 ≤799 ms)。

这里的 nice 是**假的输入**(普通用户降不了 nice),断言的是 load() 的恢复逻辑。
"""

import json
import os
import sys
import types

from katrain.vision.inference.rknn_backend import RknnBackend


def _fake_rknnlite(state):
    class FakeRKNNLite:
        def load_rknn(self, _path):
            return 0

        def init_runtime(self):
            state["nice"] = -19  # 驱动干的事
            return 0

        def release(self):
            pass

    api = types.ModuleType("rknnlite.api")
    api.RKNNLite = FakeRKNNLite
    pkg = types.ModuleType("rknnlite")
    pkg.api = api
    return pkg, api


def test_load_restores_thread_nice_after_init_runtime(tmp_path, monkeypatch):
    model = tmp_path / "m.rknn"
    model.write_bytes(b"x")
    (tmp_path / "m.meta.json").write_text(json.dumps({"imgsz": 640}))

    state = {"nice": 0}
    pkg, api = _fake_rknnlite(state)
    monkeypatch.setitem(sys.modules, "rknnlite", pkg)
    monkeypatch.setitem(sys.modules, "rknnlite.api", api)
    monkeypatch.setattr(os, "getpriority", lambda which, who: state["nice"])

    def fake_setpriority(which, who, value):
        assert (which, who) == (os.PRIO_PROCESS, 0)  # 0 = 调用线程自己,不碰别的线程
        state["nice"] = value

    monkeypatch.setattr(os, "setpriority", fake_setpriority)

    RknnBackend().load(str(model))

    assert state["nice"] == 0
