import logging
from unittest.mock import patch

from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.parallax import ParallaxParams
from katrain.vision.parallax_store import (
    BOARD_GO_19,
    ParallaxCalibration,
    attach_parallax,
    parallax_path,
    save_parallax,
)

PARAMS = {"nadir_fx": 9.02, "nadir_fy": 19.58, "k": 0.98969}


def _calib():
    return ParallaxCalibration(
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
        geometry_generation="gen-fit",
        fitted_at="2026-09-22T10:00:00+08:00",
    )


class TestVisionServiceConfig:
    def test_parallax_defaults_off_and_reaches_the_worker_config(self):
        assert VisionServiceConfig().to_worker_config()["parallax"] is None
        assert VisionServiceConfig(parallax=PARAMS).to_worker_config()["parallax"] == PARAMS


class TestInProcessAdapter:
    def _adapter(self, config):
        from katrain.vision.worker_inprocess import InProcessAdapter

        with patch("katrain.vision.worker_inprocess.StoneDetector"):
            return InProcessAdapter(config, camera=None)

    def test_only_the_geometry_lock_extractor_gets_parallax(self):
        a = self._adapter({"parallax": PARAMS})
        assert a._state_extractor_locked.parallax == ParallaxParams(**PARAMS)
        assert a._state_extractor.parallax is None  # BoardFinder warp: different grid basis

    def test_no_parallax_key_means_off(self):
        a = self._adapter({})
        assert a._state_extractor_locked.parallax is None and a._state_extractor.parallax is None


class TestAttachParallax:
    def test_without_hardware_vision_dir_it_is_off(self):
        cfg, level, msg = attach_parallax(VisionServiceConfig(parallax=PARAMS), None, None)
        assert cfg.parallax is None and level == logging.INFO and "parallax off" in msg

    def test_uncalibrated_dir_is_off_at_info(self, tmp_path):
        cfg, level, msg = attach_parallax(VisionServiceConfig(), tmp_path, "gen-now")
        assert cfg.parallax is None and level == logging.INFO and "not calibrated" in msg

    def test_broken_file_is_off_at_warning(self, tmp_path):
        path = parallax_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("{broken")
        cfg, level, msg = attach_parallax(VisionServiceConfig(), tmp_path, "gen-now")
        assert cfg.parallax is None and level == logging.WARNING and "invalid calibration file" in msg

    def test_valid_file_turns_it_on_and_logs_provenance(self, tmp_path):
        save_parallax(parallax_path(tmp_path), _calib())
        cfg, level, msg = attach_parallax(VisionServiceConfig(), tmp_path, "gen-now")
        assert cfg.parallax == PARAMS and level == logging.INFO
        for needle in (
            "parallax on",
            "go-19x19",
            "ver9-22x7",
            "k=0.989690",
            "fit_generation=gen-fit",
            "current_generation=gen-now",
        ):
            assert needle in msg, needle

    def test_it_returns_a_new_config_and_leaves_the_input_alone(self, tmp_path):
        original = VisionServiceConfig()
        save_parallax(parallax_path(tmp_path), _calib())
        cfg, _, _ = attach_parallax(original, tmp_path, None)
        assert original.parallax is None and cfg is not original
