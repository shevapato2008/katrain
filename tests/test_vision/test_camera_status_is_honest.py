"""`WorkerStatus.camera_ready` must actually reflect the camera, across BOTH camera shapes.

`InProcessAdapter._camera` is duck-typed across two incompatible shapes
(`worker_inprocess.py::_publish_status`):

  - `CameraHub.is_connected` (`katrain/web/core/camera_hub.py:63`) is a METHOD. This is
    what `VisionService` injects for the physical-board path (`vision/service.py:45`).
  - `CameraManager.is_connected` (`katrain/vision/camera.py:184-188`) is a `@property`
    returning a plain bool. This is what `InProcessAdapter` falls back to whenever no
    camera is injected (`camera=None` -> `worker_inprocess.py:161`), e.g. desktop runs
    and every test that doesn't inject a fake.

Round 1 of this fix only handled the method shape: `self._camera.is_connected` was read
as a bare ATTRIBUTE, so it was always truthy against `CameraHub` (a bound method object)
regardless of the camera's actual state — the "unplug the camera -> status goes honest
immediately" acceptance criterion (gomoku physical-board plan, Task 17 (6)) could not
pass. Calling `self._camera.is_connected` unconditionally fixes that shape but breaks
the `CameraManager` shape (`TypeError: 'bool' object is not callable`). Both shapes are
pinned here so neither regression can land silently again.
"""

import numpy as np
import pytest


class _MethodCamera:
    """Mimics CameraHub: `is_connected` is a bound METHOD, not an attribute."""

    def __init__(self, connected: bool):
        self._connected = connected

    def is_connected(self) -> bool:
        return self._connected


class _PropertyCamera:
    """Mimics CameraManager: `is_connected` is a `@property` returning a plain bool."""

    def __init__(self, connected: bool):
        self._connected = connected

    @property
    def is_connected(self) -> bool:
        return self._connected


def _inprocess_worker(camera):
    from unittest.mock import patch

    from katrain.vision.worker_inprocess import InProcessAdapter

    # StoneDetector.__init__ eagerly loads a model; patch it out so construction doesn't
    # need a real model file (same pattern as test_worker_commands.py::_inprocess_worker).
    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"board_size": 19}, camera=camera)
    # Isolate the camera-honesty question from the unrelated geometry-lock gate: with
    # `_require_geometry` left True (the default whenever a camera is injected) and no
    # geometry set, `recognition_ready` is pinned False regardless of camera state.
    adapter._require_geometry = False
    return adapter


@pytest.mark.parametrize("camera_cls", [_MethodCamera, _PropertyCamera], ids=["method_shaped", "property_shaped"])
@pytest.mark.parametrize("connected", [True, False])
def test_publish_status_reads_both_camera_shapes_honestly(camera_cls, connected):
    worker = _inprocess_worker(camera_cls(connected))

    worker._publish_status(np.zeros((19, 19), dtype=int))

    # A bare `assert ... is connected` would also pass if `_publish_status` raised and
    # something upstream swallowed it into a falsy default — pin the concrete values so
    # a wrong-value failure and a crash cannot be confused for each other.
    assert worker._status.camera_ready is connected, (
        f"camera_ready={worker._status.camera_ready!r} for {camera_cls.__name__}(connected={connected})"
    )
    assert worker._status.recognition_ready is connected
    assert worker._status.camera_status == ("connected" if connected else "disconnected")


def test_camera_dropout_makes_status_honest_without_reconstructing_the_worker():
    """The acceptance criterion itself: unplug mid-session -> next publish goes honest.

    Uses the method-shaped (CameraHub) fake -- the physical-board path this criterion is
    actually about.
    """
    camera = _MethodCamera(connected=True)
    worker = _inprocess_worker(camera)
    worker._publish_status(np.zeros((19, 19), dtype=int))
    assert worker._status.camera_ready is True

    camera._connected = False  # camera unplugged; same object, same worker
    worker._publish_status(np.zeros((19, 19), dtype=int))

    assert worker._status.camera_ready is False
    assert worker._status.recognition_ready is False
    assert worker._status.camera_status == "disconnected"
