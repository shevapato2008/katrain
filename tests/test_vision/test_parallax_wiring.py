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

    def test_a_non_value_error_from_a_broken_file_is_still_off_at_warning(self, tmp_path):
        """Deeply nested JSON raises RecursionError out of json.loads; attach_parallax must not let that
        abort server startup -- the config comes back unchanged and the fault is logged at WARNING."""
        path = parallax_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("[" * 100000)
        original = VisionServiceConfig()
        cfg, level, msg = attach_parallax(original, tmp_path, "gen-now")
        assert cfg == original and level == logging.WARNING and "invalid calibration file" in msg

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


class TestFullChain:
    """Tool -> file -> attach_parallax -> InProcessAdapter's geometry-lock extractor -> corrected cell.
    Nothing else in the suite exercises the whole path end to end (final review finding 4)."""

    def test_calibrated_file_corrects_detections_through_the_locked_extractor(self, tmp_path):
        from unittest.mock import patch

        from katrain.vision.stone_detector import Detection
        from katrain.vision.tools.calibrate_parallax import GridOffset, decide_and_write
        from katrain.vision.worker_inprocess import InProcessAdapter
        from tests.test_vision.board_state_corpus import IMG, grid_to_px
        from tests.test_vision.parallax_synth import H_MM, detected_grid
        from tests.test_vision.test_calibrate_parallax import _frames

        aligned = GridOffset(0.0, 0.0, 19, 19)
        out_path = parallax_path(tmp_path)
        verdict, calib = decide_and_write(
            _frames(jitter=0.01),
            grid_offsets={"start": aligned, "end": aligned},
            out_path=out_path,
            stone_set="ver9-22x7",
            camera_height_mm=H_MM,
            geometry_generation="gen-1",
            fitted_at="2026-09-22T10:00:00+08:00",
            dry_run=False,
        )
        assert verdict.ok, verdict.reasons

        cfg, level, msg = attach_parallax(VisionServiceConfig(), tmp_path, "gen-1")
        assert cfg.parallax is not None and level == logging.INFO and "parallax on" in msg

        # The camera sits beyond row 18 (parallax_synth NADIR_GRID ~= (9.0, 19.6)): a consistent fx/fy
        # swap in the fit would still land a low residual on the near-symmetric 17-point pattern, so the
        # orientation of the fitted nadir itself must be checked, not only the residual.
        assert calib.nadir_fy > 18
        assert abs(calib.nadir_fx - 9) < 1

        with patch("katrain.vision.worker_inprocess.StoneDetector"):
            adapter = InProcessAdapter(cfg.to_worker_config(), camera=None)
        extractor = adapter._state_extractor_locked
        assert extractor.parallax is not None

        wrong = []
        for r in range(1, 6):  # rows the on-board 8mm-outward pattern (handoff.md step 2A) targets
            for c in range(19):
                fx, fy = detected_grid(c, r, outward_cells=0.35)
                x, y = grid_to_px(extractor.config, fx, fy, img=IMG)
                det = Detection(x_center=x, y_center=y, class_id=0, confidence=0.9)
                if extractor._grid_cell(det, IMG, IMG) != (r, c):
                    wrong.append((r, c))
        assert wrong == []


class TestBoardDeltaDiagnostics:
    """P2 (narrowed 2026-09-22): each board change shows the nearby detection's parallax shift and a *
    when the correction moved it to a different intersection; 0.00 and no * when off."""

    def _log(self, parallax, caplog):
        import numpy as np

        from katrain.vision.board_state import BoardStateExtractor
        from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
        from katrain.vision.stone_detector import Detection
        from katrain.vision.worker_inprocess import InProcessAdapter
        from tests.test_vision.board_state_corpus import IMG, grid_to_px
        from tests.test_vision.parallax_synth import K_TRUE, NADIR_GRID

        cfg = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
        a = InProcessAdapter.__new__(InProcessAdapter)
        a._geometry = object()  # geometry-lock path -> _active_extractor() is the locked one
        a._state_extractor = BoardStateExtractor(BoardConfig())
        a._state_extractor_locked = BoardStateExtractor(
            cfg, parallax=ParallaxParams(*NADIR_GRID, K_TRUE) if parallax else None
        )
        before = np.zeros((19, 19), dtype=int)
        before[5][5] = 2
        after = np.zeros((19, 19), dtype=int)
        after[1][9] = 1
        x, y = grid_to_px(cfg, 9.0, 0.40)  # raw rounds to row 0; corrected (0.598) rounds to row 1
        with caplog.at_level(logging.INFO, logger="katrain.vision.worker_inprocess"):
            a._log_board_delta(before, after, [Detection(x_center=x, y_center=y, class_id=0, confidence=0.9)], IMG, IMG)
        (line,) = [r.getMessage() for r in caplog.records if r.getMessage().startswith("board delta:")]
        return line

    def test_on_shows_raw_to_corrected_shift_and_rescue_marker(self, caplog):
        line = self._log(True, caplog)
        assert "'(1,9)B~B0.90@0.40 pl0.20* (0.40,9.00)>(0.60,9.00)'" in line
        assert "'(5,5)W~none'" in line

    def test_off_shows_zero_shift_and_no_marker(self, caplog):
        line = self._log(False, caplog)
        assert "'(1,9)B~B0.90@0.60 pl0.00 (0.40,9.00)>(0.40,9.00)'" in line
        assert "*" not in line
