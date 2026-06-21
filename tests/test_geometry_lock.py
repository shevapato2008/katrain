"""Tests for geometry lock save/load + autoresearch schema compatibility.

The real empty-board calibration (auto_calibrate on camera frames) is verified on
hardware day; here we lock the persistence contract: the npz must contain EXACTLY
the 8 autoresearch session.npz arrays (confidence lives in a sidecar, never the npz).
"""

import os

import numpy as np
import pytest

from katrain.vision.geometry_lock import (
    GeometryLock,
    save_geometry_lock,
    load_geometry_lock,
    NPZ_FIELDS,
)

AUTORESEARCH_SESSION = os.path.expanduser("~/Repositories/autoresearch/board-detection/data/session.npz")


def _synth() -> GeometryLock:
    return GeometryLock(
        corners=np.array([[0, 0], [949, 0], [949, 949], [0, 949]], np.float32),
        points=np.random.rand(19, 19, 2).astype(np.float32),
        xs=np.linspace(0, 949, 19).astype(np.float32),
        ys=np.linspace(0, 949, 19).astype(np.float32),
        M=np.eye(3, dtype=np.float64),
        Minv=np.eye(3, dtype=np.float64),
        out_size=950,
        baseline=np.random.rand(19, 19, 3).astype(np.float32),
        confidence=0.91,
        nmatch=18,
        empty_black=0,
        empty_white=0,
        diag={"nmatch_x": 18, "nmatch_y": 19, "moved_px": 3.2},
    )


class TestPersistence:
    def test_npz_has_exactly_eight_fields(self, tmp_path):
        path = tmp_path / "geometry_lock.npz"
        save_geometry_lock(_synth(), path)
        with np.load(path) as d:
            assert set(d.files) == set(NPZ_FIELDS)
            assert len(d.files) == 8
            assert "confidence" not in d.files  # diagnostics never go in the npz

    def test_round_trip(self, tmp_path):
        path = tmp_path / "geometry_lock.npz"
        original = _synth()
        save_geometry_lock(original, path)
        loaded = load_geometry_lock(path)
        np.testing.assert_array_equal(loaded.corners, original.corners)
        np.testing.assert_array_almost_equal(loaded.points, original.points)
        np.testing.assert_array_almost_equal(loaded.baseline, original.baseline)
        np.testing.assert_array_equal(loaded.M, original.M)
        assert loaded.out_size == 950 and isinstance(loaded.out_size, int)
        # diagnostics restored from the sidecar
        assert loaded.confidence == 0.91
        assert loaded.nmatch == 18
        assert loaded.empty_self_check_ok is True

    def test_round_trip_accepts_numpy_scalars_in_diagnostics(self, tmp_path):
        path = tmp_path / "geometry_lock.npz"
        original = _synth()
        original.diag = {"diag_px": np.float32(123.5)}

        save_geometry_lock(original, path)

        loaded = load_geometry_lock(path)
        assert loaded.diag["diag_px"] == pytest.approx(123.5)

    def test_failed_save_preserves_existing_lock(self, tmp_path):
        path = tmp_path / "geometry_lock.npz"
        original = _synth()
        save_geometry_lock(original, path)
        replacement = _synth()
        replacement.confidence = 0.5
        replacement.diag = {"unsupported": object()}

        with pytest.raises(TypeError):
            save_geometry_lock(replacement, path)

        loaded = load_geometry_lock(path)
        assert loaded.confidence == original.confidence
        assert loaded.diag == original.diag

    def test_load_rejects_missing_field(self, tmp_path):
        path = tmp_path / "bad.npz"
        np.savez(path, corners=np.zeros((4, 2), np.float32))  # missing the rest
        with pytest.raises(ValueError):
            load_geometry_lock(path)


class TestAutoresearchCompat:
    def test_schema_matches_autoresearch_session(self):
        if not os.path.exists(AUTORESEARCH_SESSION):
            pytest.skip("autoresearch session.npz not available")
        with np.load(AUTORESEARCH_SESSION) as d:
            assert set(d.files) == set(NPZ_FIELDS)

    def test_can_load_autoresearch_session(self):
        if not os.path.exists(AUTORESEARCH_SESSION):
            pytest.skip("autoresearch session.npz not available")
        lock = load_geometry_lock(AUTORESEARCH_SESSION)
        assert lock.corners.shape == (4, 2)
        assert lock.points.shape == (19, 19, 2)
        assert lock.baseline.shape == (19, 19, 3)
