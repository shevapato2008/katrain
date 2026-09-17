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
    class FakeCapture:
        def __init__(self, auto_exposure=3.0, exposure=100.0):
            import cv2

            self.opened = True
            self.values = {
                cv2.CAP_PROP_AUTO_EXPOSURE: auto_exposure,
                cv2.CAP_PROP_EXPOSURE: exposure,
                cv2.CAP_PROP_FRAME_WIDTH: 1280.0,
                cv2.CAP_PROP_FRAME_HEIGHT: 720.0,
                cv2.CAP_PROP_FOURCC: 0.0,
            }
            self.control_writes = []
            self.failed_writes = set()
            self.get_calls = []
            self.readback_overrides = {}

        def isOpened(self):
            return self.opened

        def release(self):
            self.opened = False

        def set(self, prop, value):
            import cv2

            if prop in (cv2.CAP_PROP_AUTO_EXPOSURE, cv2.CAP_PROP_EXPOSURE):
                self.control_writes.append((prop, value))
            if (prop, value) in self.failed_writes:
                return False
            self.values[prop] = value
            return True

        def get(self, prop):
            self.get_calls.append(prop)
            if prop in self.readback_overrides:
                return self.readback_overrides[prop]
            return self.values.get(prop, 0.0)

    @staticmethod
    def open_with_captures(monkeypatch, cam, captures):
        from katrain.vision import camera as camera_module

        queue = iter(captures)
        monkeypatch.setattr(camera_module.cv2, "VideoCapture", lambda _arg: next(queue))
        monkeypatch.setattr(cam, "_reader_loop", lambda: None)

    def test_hbv_camera_uses_native_v4l2_exposure_modes(self):
        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CAMERA_AUTO_EXPOSURE_ON

        assert CAMERA_AUTO_EXPOSURE_MANUAL == 1.0
        assert CAMERA_AUTO_EXPOSURE_ON == 3.0

    def test_pending_controls_applied_and_verified(self):
        from unittest.mock import MagicMock, patch

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        cam = CameraManager(device_id=0)
        cap = MagicMock()
        cap.set.return_value = True
        cap.get.side_effect = [1.0, 800.0]
        cam._cap = cap
        cam.request_controls(exposure=800.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        assert cam.controls_effective is True

    def test_open_caches_native_control_readbacks(self, monkeypatch):
        from katrain.vision.camera import CameraManager

        cap = self.FakeCapture(auto_exposure=3.0, exposure=432.0)
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [cap])

        assert cam.open() is True
        assert cam.initial_exposure == 432.0
        assert cam.current_auto_exposure == 3.0
        assert cam.current_exposure == 432.0
        get_count = len(cap.get_calls)
        assert cam.current_auto_exposure == 3.0
        assert cam.current_exposure == 432.0
        assert len(cap.get_calls) == get_count
        cam.close()

    def test_open_configuration_does_not_report_a_runtime_control_result(self, monkeypatch):
        from katrain.vision.camera import CameraManager

        cap = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        cam = CameraManager(device_id=0, warmup_seconds=0, lock_exposure=True, exposure=200.0)
        self.open_with_captures(monkeypatch, cam, [cap])

        assert cam.open() is True
        assert cam.controls_effective is None
        cam.close()

    def test_runtime_control_readbacks_are_cached(self):
        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        cap = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        cam = CameraManager(device_id=0)
        cam._cap = cap

        cam.request_controls(exposure=800.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()

        assert cam.current_auto_exposure == CAMERA_AUTO_EXPOSURE_MANUAL
        assert cam.current_exposure == 800.0
        get_count = len(cap.get_calls)
        assert cam.current_auto_exposure == CAMERA_AUTO_EXPOSURE_MANUAL
        assert cam.current_exposure == 800.0
        assert len(cap.get_calls) == get_count

    def test_successful_manual_controls_are_replayed_on_reopen(self, monkeypatch):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        first = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        reopened = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [first, reopened])
        assert cam.open() is True
        cam.request_controls(exposure=800.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()

        assert cam.open() is True

        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_MANUAL) in reopened.control_writes
        assert (cv2.CAP_PROP_EXPOSURE, 800.0) in reopened.control_writes
        assert cam.current_auto_exposure == CAMERA_AUTO_EXPOSURE_MANUAL
        assert cam.current_exposure == 800.0
        cam.close()

    def test_successful_hardware_auto_mode_is_replayed_on_reopen(self, monkeypatch):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_ON, CameraManager

        first = self.FakeCapture(auto_exposure=1.0, exposure=100.0)
        reopened = self.FakeCapture(auto_exposure=1.0, exposure=50.0)
        cam = CameraManager(device_id=0, warmup_seconds=0, lock_exposure=True)
        self.open_with_captures(monkeypatch, cam, [first, reopened])
        assert cam.open() is True
        cam.request_controls(auto_exposure=CAMERA_AUTO_EXPOSURE_ON)
        cam._apply_pending_controls()

        assert cam.open() is True

        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_ON) in reopened.control_writes
        assert (cv2.CAP_PROP_AUTO_EXPOSURE, 1.0) not in reopened.control_writes
        assert cam.current_auto_exposure == CAMERA_AUTO_EXPOSURE_ON
        cam.close()

    def test_failed_runtime_request_does_not_replace_replay_state(self, monkeypatch):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        first = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        reopened = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [first, reopened])
        assert cam.open() is True
        cam.request_controls(exposure=600.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        first.failed_writes.add((cv2.CAP_PROP_EXPOSURE, 800.0))
        cam.request_controls(exposure=800.0)
        cam._apply_pending_controls()
        assert cam.controls_effective is False

        assert cam.open() is True

        assert (cv2.CAP_PROP_EXPOSURE, 600.0) in reopened.control_writes
        assert (cv2.CAP_PROP_EXPOSURE, 800.0) not in reopened.control_writes
        assert cam.current_exposure == 600.0
        cam.close()

    def test_auto_success_and_exposure_failure_preserve_the_replay_snapshot(self, monkeypatch):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CAMERA_AUTO_EXPOSURE_ON, CameraManager

        first = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        reopened = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [first, reopened])
        assert cam.open() is True
        cam.request_controls(exposure=600.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        first.failed_writes.add((cv2.CAP_PROP_EXPOSURE, 800.0))

        cam.request_controls(exposure=800.0, auto_exposure=CAMERA_AUTO_EXPOSURE_ON)
        cam._apply_pending_controls()

        assert cam.controls_effective is False
        assert cam.current_auto_exposure == CAMERA_AUTO_EXPOSURE_ON
        assert cam.current_exposure == 600.0
        assert cam.open() is True
        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_MANUAL) in reopened.control_writes
        assert (cv2.CAP_PROP_EXPOSURE, 600.0) in reopened.control_writes
        cam.close()

    def test_auto_failure_and_exposure_success_preserve_the_replay_snapshot(self, monkeypatch):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CAMERA_AUTO_EXPOSURE_ON, CameraManager

        first = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        reopened = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [first, reopened])
        assert cam.open() is True
        cam.request_controls(exposure=600.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        first.failed_writes.add((cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_ON))

        cam.request_controls(exposure=800.0, auto_exposure=CAMERA_AUTO_EXPOSURE_ON)
        cam._apply_pending_controls()

        assert cam.controls_effective is False
        assert cam.current_auto_exposure == CAMERA_AUTO_EXPOSURE_MANUAL
        assert cam.current_exposure == 800.0
        assert cam.open() is True
        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_MANUAL) in reopened.control_writes
        assert (cv2.CAP_PROP_EXPOSURE, 600.0) in reopened.control_writes
        cam.close()

    def test_manual_only_with_nonfinite_exposure_preserves_the_replay_snapshot(self, monkeypatch):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CAMERA_AUTO_EXPOSURE_ON, CameraManager

        first = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        reopened = self.FakeCapture(auto_exposure=1.0, exposure=50.0)
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [first, reopened])
        assert cam.open() is True
        cam.request_controls(exposure=600.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        cam.request_controls(auto_exposure=CAMERA_AUTO_EXPOSURE_ON)
        cam._apply_pending_controls()
        first.values[cv2.CAP_PROP_EXPOSURE] = float("nan")

        cam.request_controls(auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()

        assert cam.controls_effective is False
        assert cam.current_auto_exposure == CAMERA_AUTO_EXPOSURE_MANUAL
        assert cam.current_exposure is None
        assert cam.open() is True
        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_ON) in reopened.control_writes
        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_MANUAL) not in reopened.control_writes
        cam.close()

    def test_reopen_verifies_replay_writes_and_readbacks_without_losing_snapshot(self, monkeypatch):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        first = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        rejected = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        rejected.failed_writes.add((cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_MANUAL))
        mismatched = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        mismatched.readback_overrides[cv2.CAP_PROP_AUTO_EXPOSURE] = 3.0
        recovered = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        unavailable = self.FakeCapture()
        unavailable.opened = False
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [first, rejected, mismatched, recovered, unavailable])
        assert cam.open() is True
        cam.request_controls(exposure=600.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        assert cam.controls_effective is True

        assert cam.open() is True
        assert cam.controls_effective is False
        assert cam.open() is True
        assert cam.controls_effective is False
        assert cam.open() is True
        assert cam.controls_effective is True
        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_MANUAL) in recovered.control_writes
        assert (cv2.CAP_PROP_EXPOSURE, 600.0) in recovered.control_writes

        assert cam.open() is False
        assert cam.controls_effective is None

    def test_older_batch_cannot_publish_effectiveness_over_a_newer_request(self):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        cap = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        cam = CameraManager(device_id=0)
        cam._cap = cap
        original_set = cap.set
        enqueued_newer_request = False

        def interleaved_set(prop, value):
            nonlocal enqueued_newer_request
            result = original_set(prop, value)
            if prop == cv2.CAP_PROP_AUTO_EXPOSURE and not enqueued_newer_request:
                enqueued_newer_request = True
                cam.request_controls(exposure=700.0)
            return result

        cap.set = interleaved_set
        cam.request_controls(exposure=600.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)

        cam._apply_pending_controls()

        assert cam.current_auto_exposure == CAMERA_AUTO_EXPOSURE_MANUAL
        assert cam.current_exposure == 600.0
        assert cam.controls_effective is None

        cam._apply_pending_controls()
        assert cam.current_exposure == 700.0
        assert cam.controls_effective is True

    def test_native_manual_readback_tolerance_replays_canonical_mode_and_exposure(self, monkeypatch):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        first = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        first.readback_overrides[cv2.CAP_PROP_AUTO_EXPOSURE] = 1.005
        reopened = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        reopened.readback_overrides[cv2.CAP_PROP_AUTO_EXPOSURE] = 1.005
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [first, reopened])
        assert cam.open() is True
        cam.request_controls(exposure=600.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        assert cam.controls_effective is True

        assert cam.open() is True

        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_MANUAL) in reopened.control_writes
        assert (cv2.CAP_PROP_EXPOSURE, 600.0) in reopened.control_writes
        assert cam.current_auto_exposure == 1.005
        assert cam.controls_effective is True
        cam.close()

    @pytest.mark.parametrize("invalid_controls", [{"auto_exposure": float("inf")}, {"exposure": float("inf")}])
    def test_nonfinite_target_is_rejected_without_touching_camera_or_snapshot(self, monkeypatch, invalid_controls):
        import cv2

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        first = self.FakeCapture(auto_exposure=3.0, exposure=100.0)
        reopened = self.FakeCapture(auto_exposure=3.0, exposure=50.0)
        cam = CameraManager(device_id=0, warmup_seconds=0)
        self.open_with_captures(monkeypatch, cam, [first, reopened])
        assert cam.open() is True
        cam.request_controls(exposure=600.0, auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        writes_before_invalid_request = list(first.control_writes)

        cam.request_controls(**invalid_controls)
        cam._apply_pending_controls()

        assert cam.controls_effective is False
        assert first.control_writes == writes_before_invalid_request
        assert cam.open() is True
        assert (cv2.CAP_PROP_AUTO_EXPOSURE, CAMERA_AUTO_EXPOSURE_MANUAL) in reopened.control_writes
        assert (cv2.CAP_PROP_EXPOSURE, 600.0) in reopened.control_writes
        cam.close()

    def test_readback_mismatch_marks_ineffective(self):
        from unittest.mock import MagicMock

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        cam = CameraManager(device_id=0)
        cap = MagicMock()
        cap.set.return_value = True
        cap.get.return_value = 0.0  # platform ignored the write (macOS behavior)
        cam._cap = cap
        cam.request_controls(exposure=800.0)
        cam._apply_pending_controls()
        assert cam.controls_effective is False

    def test_manual_auto_exposure_readback_is_verified(self):
        from unittest.mock import MagicMock

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        cam = CameraManager(device_id=0)
        cap = MagicMock()
        cap.set.return_value = True
        cap.get.return_value = 3.0  # driver stayed in auto mode
        cam._cap = cap
        cam.request_controls(auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        assert cam.controls_effective is False

    def test_native_v4l2_manual_readback_is_accepted(self):
        from unittest.mock import MagicMock

        from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, CameraManager

        cam = CameraManager(device_id=0)
        cap = MagicMock()
        cap.set.return_value = True
        cap.get.return_value = 1.0  # native V4L2 exposure_auto=1 (manual)
        cam._cap = cap
        cam.request_controls(auto_exposure=CAMERA_AUTO_EXPOSURE_MANUAL)
        cam._apply_pending_controls()
        assert cam.controls_effective is True

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
