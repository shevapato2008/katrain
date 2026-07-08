import numpy as np

from katrain.vision.temporal import FrameAverager


def frame(value, shape=(4, 4, 3)):
    return np.full(shape, value, dtype=np.uint8)


class TestFrameAverager:
    def test_cold_start_first_frame_returned_unchanged(self):
        avg = FrameAverager(8)
        out = avg.add(frame(100))
        assert np.array_equal(out, frame(100))

    def test_partial_buffer_averages_available_frames(self):
        avg = FrameAverager(8)
        avg.add(frame(10))
        out = avg.add(frame(20))
        assert np.all(out == 15)

    def test_rolling_window_evicts_oldest(self):
        avg = FrameAverager(2)
        avg.add(frame(10))
        avg.add(frame(20))
        out = avg.add(frame(30))  # 10 evicted -> mean(20, 30)
        assert np.all(out == 25)

    def test_reset_restarts_from_next_frame(self):
        avg = FrameAverager(8)
        avg.add(frame(0))
        avg.add(frame(0))
        avg.reset()
        out = avg.add(frame(200))
        assert np.all(out == 200)

    def test_shape_change_auto_resets(self):
        # Geometry re-lock can change the warp out-size; the old buffer is another scene.
        avg = FrameAverager(8)
        avg.add(frame(0, shape=(4, 4, 3)))
        out = avg.add(frame(200, shape=(6, 6, 3)))
        assert out.shape == (6, 6, 3)
        assert np.all(out == 200)

    def test_n_one_is_passthrough(self):
        avg = FrameAverager(1)
        f = frame(37)
        assert avg.add(f) is f

    def test_rounding_is_nearest_not_truncation(self):
        avg = FrameAverager(2)
        avg.add(frame(1))
        out = avg.add(frame(2))  # mean 1.5 -> 2
        assert np.all(out == 2)

    def test_noise_reduction(self):
        rng = np.random.default_rng(7)
        avg = FrameAverager(8)
        base = np.full((32, 32, 3), 128.0)
        outs = []
        for _ in range(8):
            noisy = np.clip(base + rng.normal(0, 8, base.shape), 0, 255).astype(np.uint8)
            outs.append(avg.add(noisy))
        residual = outs[-1].astype(float) - base
        assert residual.std() < 8 / 2  # >= 2x noise reduction with an 8-deep buffer

    def test_worker_config_carries_frame_average(self):
        from katrain.vision.config_service import VisionServiceConfig

        assert VisionServiceConfig().to_worker_config()["frame_average"] == 8
        assert VisionServiceConfig(frame_average=4).to_worker_config()["frame_average"] == 4
