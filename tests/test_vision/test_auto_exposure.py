import numpy as np
import pytest

from katrain.vision.auto_exposure import BrightnessStats, ExposureController, meter_brightness


def board_image(level, size=200, margin_frac=0.05):
    img = np.full((size, size, 3), level, dtype=np.uint8)
    return img


class TestMeterBrightness:
    def test_uniform_levels(self):
        assert meter_brightness(board_image(140)).median == pytest.approx(140, abs=2)
        assert meter_brightness(board_image(40)).median == pytest.approx(40, abs=2)

    def test_median_ignores_small_glare_spot(self):
        img = board_image(140)
        img[80:100, 80:100] = 255  # small blown patch
        stats = meter_brightness(img)
        assert stats.median == pytest.approx(140, abs=2)  # median unmoved
        assert stats.clip_frac > 0.005  # but the clip guard sees it

    def test_margin_is_excluded(self):
        # bright margin ring around a dark grid region must not lift the reading
        img = np.full((200, 200, 3), 250, dtype=np.uint8)
        pad = int(round(200 * 1.0 / 20))
        img[pad : 200 - pad, pad : 200 - pad] = 60
        stats = meter_brightness(img, margin_cells=1.0)
        assert stats.median == pytest.approx(60, abs=2)

    def test_grayscale_input_supported(self):
        img = np.full((200, 200), 100, dtype=np.uint8)
        assert meter_brightness(img).median == pytest.approx(100, abs=2)


def stats(median, clip=0.0, shadow=0.0):
    return BrightnessStats(median=median, clip_frac=clip, shadow_frac=shadow)


def controller(**kw):
    defaults = dict(target_lo=120.0, target_hi=170.0, eval_interval=2.0, holdoff=2.0, confirm_evals=2)
    defaults.update(kw)
    c = ExposureController(**defaults)
    c.seed(1000.0)
    return c


class TestExposureController:
    def test_in_band_never_acts(self):
        c = controller()
        for t in range(0, 100, 3):
            assert c.update(stats(145), float(t)) is None

    def test_single_out_of_band_eval_does_not_act(self):
        c = controller()
        assert c.update(stats(60), 0.0) is None  # streak 1 of 2

    def test_second_consecutive_low_eval_raises_exposure(self):
        c = controller()
        assert c.update(stats(60), 0.0) is None
        new = c.update(stats(60), 3.0)
        assert new is not None and new > 1000.0

    def test_correction_is_damped_and_quantized(self):
        c = controller(damping=0.6)
        c.update(stats(60), 0.0)
        new = c.update(stats(60), 3.0)
        # full correction 145/60=2.42x; damped 2.42^0.6=1.70x -> 1700, flicker-quantized to 100s
        assert new == pytest.approx(1700, abs=100)
        assert new % 100 == 0

    def test_high_median_lowers_exposure(self):
        c = controller()
        c.update(stats(230), 0.0)
        new = c.update(stats(230), 3.0)
        assert new is not None and new < 1000.0

    def test_direction_flip_restarts_confirmation(self):
        c = controller()
        c.update(stats(60), 0.0)  # low, streak 1
        assert c.update(stats(230), 3.0) is None  # flipped to high -> streak restarts
        assert c.update(stats(230), 6.0) is not None  # high confirmed

    def test_holdoff_suppresses_next_action(self):
        c = controller(holdoff=5.0)
        c.update(stats(60), 0.0)
        assert c.update(stats(60), 3.0) is not None  # acts at t=3
        assert c.update(stats(60), 6.0) is None  # inside holdoff
        assert c.update(stats(60), 9.0) is None  # streak rebuilding after holdoff
        assert c.update(stats(60), 12.0) is not None  # confirmed again

    def test_eval_interval_throttles_sampling(self):
        c = controller(eval_interval=2.0)
        assert c.update(stats(60), 0.0) is None
        assert c.update(stats(60), 0.5) is None  # ignored: too soon, streak NOT advanced
        assert c.update(stats(60), 1.0) is None
        assert c.update(stats(60), 2.5) is not None  # second real evaluation

    def test_clip_guard_forces_step_down_with_in_band_median(self):
        c = controller()
        c.update(stats(145, clip=0.05), 0.0)
        new = c.update(stats(145, clip=0.05), 3.0)
        assert new is not None and new < 1000.0

    def test_exposure_clamped_to_max(self):
        c = controller(max_exposure=1500.0)
        c.update(stats(20), 0.0)
        new = c.update(stats(20), 3.0)
        assert new == 1500.0

    def test_no_action_when_already_pinned_at_clamp(self):
        c = controller(max_exposure=1000.0)  # seeded exactly at max
        c.update(stats(20), 0.0)
        assert c.update(stats(20), 3.0) is None  # clamp -> same value -> no actuation

    def test_unseeded_controller_uses_seed_default(self):
        c = ExposureController(confirm_evals=1, seed_exposure=300.0)
        new = c.update(stats(60), 0.0)
        assert new is not None and new > 300.0

    def test_band_position(self):
        c = controller()
        assert c.band_position(stats(145)) == "ok"
        assert c.band_position(stats(60)) == "low"
        assert c.band_position(stats(230)) == "high"
        assert c.band_position(stats(145, clip=0.05)) == "high"  # glare counts as over


class TestCameraRuntimeControls:
    def test_pending_controls_applied_and_verified(self):
        from unittest.mock import MagicMock, patch

        from katrain.vision.camera import CameraManager

        cam = CameraManager(device_id=0)
        cap = MagicMock()
        cap.set.return_value = True
        cap.get.return_value = 800.0
        cam._cap = cap
        cam.request_controls(exposure=800.0, auto_exposure=0.25)
        cam._apply_pending_controls()
        assert cam.controls_effective is True

    def test_readback_mismatch_marks_ineffective(self):
        from unittest.mock import MagicMock

        from katrain.vision.camera import CameraManager

        cam = CameraManager(device_id=0)
        cap = MagicMock()
        cap.set.return_value = True
        cap.get.return_value = 0.0  # platform ignored the write (macOS behavior)
        cam._cap = cap
        cam.request_controls(exposure=800.0)
        cam._apply_pending_controls()
        assert cam.controls_effective is False

    def test_no_pending_is_noop(self):
        from katrain.vision.camera import CameraManager

        cam = CameraManager(device_id=0)
        cam._apply_pending_controls()
        assert cam.controls_effective is None


class TestConfigPlumbing:
    def test_worker_config_carries_ae_fields(self):
        from katrain.vision.config_service import VisionServiceConfig

        wc = VisionServiceConfig().to_worker_config()
        assert wc["auto_exposure"] == "software"
        assert wc["ae_target_lo"] == 120.0
        assert wc["ae_target_hi"] == 170.0
        wc = VisionServiceConfig(auto_exposure="off", ae_target="100-140").to_worker_config()
        assert wc["auto_exposure"] == "off"
        assert wc["ae_target_lo"] == 100.0
        assert wc["ae_target_hi"] == 140.0
