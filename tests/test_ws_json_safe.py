"""Regression: the /ws/vision send path must tolerate numpy in any event payload.

A numpy int64 in an ILLEGAL_CHANGE payload crashed WebSocket.send_json and silently
killed the vision socket (kiosk froze at "已匹配 0/17"). _json_safe is the boundary
guard so a numpy value in ANY event type can never take the socket down again.
"""

import json

import numpy as np

from katrain.web.server import _json_safe


def test_json_safe_converts_numpy_scalars_arrays_and_nested_tuples():
    payload = {
        "type": "illegal_change",
        "data": {
            "positions": [(np.int64(6), np.int64(17), 1)],  # the exact shape from the live crash
            "conf": np.float64(0.97),
        },
        "arr": np.array([1, 2, 3]),
        "flag": np.bool_(True),
    }
    safe = _json_safe(payload)
    json.dumps(safe)  # must not raise
    assert safe["data"]["positions"] == [[6, 17, 1]]
    assert safe["data"]["conf"] == 0.97
    assert safe["arr"] == [1, 2, 3]
    assert safe["flag"] is True


def test_json_safe_passes_through_plain_python():
    payload = {"type": "setup_progress", "data": {"matched": 0, "missing": [[1, 2]], "extra": []}}
    assert _json_safe(payload) == payload
