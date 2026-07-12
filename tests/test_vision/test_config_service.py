import pytest

from katrain.vision.config_service import VisionServiceConfig, parse_ae_target


class TestParseAeTarget:
    def test_band_form(self):
        assert parse_ae_target("120-170") == (120.0, 170.0)

    def test_bare_scalar_default_reproduces_default_band(self):
        # The crash case: a bare scalar like "145" used to blow up split("-") unpacking.
        assert parse_ae_target("145") == (120.0, 170.0)

    def test_bare_scalar_lower(self):
        assert parse_ae_target("100") == (75.0, 125.0)

    def test_bare_scalar_upper_clamp(self):
        assert parse_ae_target("250") == (225.0, 255.0)

    @pytest.mark.parametrize("value", ["170-120", "150-150"])
    def test_band_lo_not_less_than_hi_raises(self, value):
        with pytest.raises(ValueError):
            parse_ae_target(value)

    @pytest.mark.parametrize("value", ["", "abc", "1-2-3", "12-ab", "-5"])
    def test_malformed_raises(self, value):
        with pytest.raises(ValueError):
            parse_ae_target(value)


class TestVisionServiceConfigToWorkerConfig:
    def test_bare_scalar_end_to_end(self):
        cfg = VisionServiceConfig(ae_target="145")
        worker_cfg = cfg.to_worker_config()
        assert worker_cfg["ae_target_lo"] == 120.0
        assert worker_cfg["ae_target_hi"] == 170.0

    def test_band_end_to_end(self):
        cfg = VisionServiceConfig(ae_target="130-160")
        worker_cfg = cfg.to_worker_config()
        assert worker_cfg["ae_target_lo"] == 130.0
        assert worker_cfg["ae_target_hi"] == 160.0
