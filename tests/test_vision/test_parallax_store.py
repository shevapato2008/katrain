import json
import math

import pytest

from katrain.vision.parallax import ParallaxParams
from katrain.vision.parallax_store import (
    BOARD_GO_19,
    ParallaxCalibration,
    load_parallax,
    parallax_path,
    save_parallax,
)


def _calib(**overrides):
    values = dict(
        board=BOARD_GO_19,
        stone_set="ver9-22x7",
        nadir_fx=9.02,
        nadir_fy=19.58,
        k=0.98969,
        m=1 / 0.98969,
        h_implied_mm=339.44 * (1 - 0.98969),  # must equal camera_height_mm * (1 - k)
        camera_height_mm=339.44,
        rms_cells=0.031,
        max_resid_cells=0.07,
        n_samples=17,
        n_black=9,
        n_white=8,
        frames=30,
        geometry_generation="gen-1",
        fitted_at="2026-09-22T10:00:00+08:00",
    )
    values.update(overrides)
    return ParallaxCalibration(**values)


def test_path_is_one_file_per_board_under_the_vision_dir(tmp_path):
    assert parallax_path(tmp_path) == tmp_path / "parallax" / "go-19x19.json"


def test_save_then_load_round_trips(tmp_path):
    path = parallax_path(tmp_path)
    save_parallax(path, _calib())
    calib, reason = load_parallax(path)
    assert reason == "ok"
    assert calib == _calib()
    assert calib.params == ParallaxParams(9.02, 19.58, 0.98969)


def test_missing_file_means_not_calibrated(tmp_path):
    calib, reason = load_parallax(parallax_path(tmp_path))
    assert calib is None and reason.startswith("not calibrated")


def _write(tmp_path, data):
    path = parallax_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda d: d.update(schema=2), "schema"),
        (lambda d: d.update(board="xiangqi-9x10"), "board"),
        (lambda d: d.pop("k"), "missing"),
        (lambda d: d.update(extra=1), "unexpected"),
        (lambda d: d.update(k=math.nan), "finite"),
        (lambda d: d.update(k=True), "finite"),
        (lambda d: d.update(k=1.0), "(0, 1)"),
        (lambda d: d.update(k=1.2), "(0, 1)"),
        (lambda d: d.update(h_implied_mm=1.5), "h_implied_mm"),
        (lambda d: d.update(h_implied_mm=8.5), "h_implied_mm"),
        # k damaged alone: the stale h_implied_mm must not vouch for it
        (lambda d: d.update(k=0.5), "1/k"),
        (lambda d: d.update(k=0.985, m=1 / 0.985), "does not match"),
        # internally consistent, but the height itself is out of the window
        (lambda d: d.update(k=1 - 9 / 339.44, m=1 / (1 - 9 / 339.44), h_implied_mm=339.44 * (9 / 339.44)), "outside"),
        (lambda d: d.update(camera_height_mm=0.0), "camera_height_mm"),
        (lambda d: d.update(n_samples=-1), "n_samples"),
        (lambda d: d.update(stone_set=""), "stone_set"),
        (lambda d: d.update(geometry_generation=3), "geometry_generation"),
    ],
)
def test_invalid_file_is_refused_with_a_reason(tmp_path, mutate, needle):
    data = _calib().to_json_dict()
    mutate(data)
    calib, reason = load_parallax(_write(tmp_path, data))
    assert calib is None
    assert reason.startswith("invalid calibration file") and needle in reason


def test_unparseable_json_is_refused(tmp_path):
    calib, reason = load_parallax(_write(tmp_path, "{not json"))
    assert calib is None and reason.startswith("invalid calibration file")


def test_a_json_error_that_is_not_ValueError_still_never_raises(tmp_path):
    """A deeply nested JSON array makes json.loads raise RecursionError (not caught by the narrower
    (OSError, ValueError, TypeError)); load_parallax must still return (None, reason), never raise."""
    calib, reason = load_parallax(_write(tmp_path, "[" * 100000))
    assert calib is None
    assert reason.startswith("invalid calibration file")


def test_save_refuses_an_invalid_calibration_and_keeps_the_old_file(tmp_path):
    path = parallax_path(tmp_path)
    save_parallax(path, _calib())
    before = path.read_bytes()
    with pytest.raises(ValueError, match="h_implied_mm"):
        save_parallax(path, _calib(h_implied_mm=12.0))
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["go-19x19.json"]  # no temp file left behind


def test_save_replaces_an_existing_file(tmp_path):
    path = parallax_path(tmp_path)
    save_parallax(path, _calib())
    save_parallax(path, _calib(k=0.985, m=1 / 0.985, h_implied_mm=339.44 * (1 - 0.985)))
    assert load_parallax(path)[0].k == 0.985
