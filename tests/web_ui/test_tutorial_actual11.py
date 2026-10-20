"""Finite actual-size contract, using saved p148-f01 local setup (31B/30W)."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from katrain.core.sgf_parser import SGF
from katrain.web.tutorials.models import StrictBoardPayload
from katrain.web.tutorials.recognition_catalog_import import normalize_payload
from katrain.web.tutorials.sgf_export import diagram_sgf

P148 = {
    "schema_version": 2,
    "unknown_stones": [],
    "source_region": {"col": 0, "row": 0, "cols": 11, "rows": 11, "confirmed": False},
    "replay": {"status": "needs_calibration", "initial": None, "moves": []},
    "viewport": {"col": 0, "row": 0, "cols": 11, "rows": 11},
    "size": 11,
    "stones": {
        "B": [
            [4, 0],
            [4, 1],
            [5, 1],
            [6, 1],
            [4, 2],
            [6, 2],
            [7, 2],
            [2, 3],
            [3, 3],
            [6, 3],
            [0, 4],
            [1, 4],
            [4, 4],
            [5, 4],
            [3, 5],
            [5, 5],
            [0, 6],
            [1, 6],
            [2, 6],
            [5, 6],
            [2, 7],
            [3, 7],
            [5, 7],
            [6, 7],
            [9, 7],
            [6, 8],
            [7, 8],
            [9, 8],
            [5, 9],
            [7, 9],
            [8, 9],
        ],
        "W": [
            [1, 0],
            [3, 1],
            [7, 1],
            [8, 1],
            [1, 2],
            [2, 2],
            [3, 2],
            [5, 2],
            [8, 2],
            [0, 3],
            [1, 3],
            [7, 3],
            [6, 4],
            [7, 4],
            [6, 5],
            [3, 6],
            [4, 6],
            [6, 6],
            [9, 6],
            [1, 7],
            [7, 7],
            [8, 7],
            [1, 8],
            [2, 8],
            [3, 8],
            [4, 8],
            [5, 8],
            [2, 9],
            [4, 9],
            [6, 9],
        ],
    },
    "labels": {},
    "letters": {},
    "shapes": {},
}


def test_actual11_saved_setup_normalizes_and_exports_without_replay():
    payload = deepcopy(P148)
    figure = {"result": {"complete": True, "payload": payload}}
    assert StrictBoardPayload.model_validate(payload).model_dump(exclude_unset=True) == payload
    assert normalize_payload(figure) == payload
    assert payload["source_region"]["confirmed"] is False
    assert payload["replay"] == {"status": "needs_calibration", "initial": None, "moves": []}
    sgf = diagram_sgf(payload, metadata={"figure_id": "p148-f01", "version_kind": "candidate"})
    tree = SGF.parse_sgf(sgf)
    assert tree.properties["SZ"] == ["11"]
    for color, count in (("B", 31), ("W", 30)):
        expected = {chr(97 + c) + chr(97 + r) for c, r in payload["stones"][color]}
        assert len(expected) == count
        assert set(tree.properties["A" + color]) == expected
    assert not tree.children


def test_actual11_rejects_coordinate11_and_preserves_full19():
    outside = deepcopy(P148)
    outside["stones"]["B"].append([11, 10])
    with pytest.raises(ValidationError):
        StrictBoardPayload.model_validate(outside)
    full19 = deepcopy(P148)
    full19["size"] = 19
    full19["viewport"] = {"col": 0, "row": 0, "cols": 19, "rows": 19}
    full19["source_region"] = {**full19["viewport"], "confirmed": False}
    full19["stones"]["B"].append([18, 18])
    assert StrictBoardPayload.model_validate(full19).model_dump(exclude_unset=True) == full19
    assert SGF.parse_sgf(diagram_sgf(full19, metadata={"figure_id": 1, "version_kind": "current"})).properties[
        "SZ"
    ] == ["19"]
