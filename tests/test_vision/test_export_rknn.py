"""Tests for the pure helpers in export_rknn.py.

Must run WITHOUT rknn-toolkit2/onnx installed: only import the module and
call the module-level pure helpers. Do NOT call export_rknn() itself here,
since it requires rknn-toolkit2.
"""

import pytest

from katrain.vision.tools.export_rknn import derive_output_basename, validate_class_order


class TestDeriveOutputBasename:
    def test_default_from_stem_and_target(self):
        assert derive_output_basename("go4_s", "rk3562", None) == "go4_s_rk3562"

    def test_explicit_out_name_overrides_default(self):
        assert derive_output_basename("go4_s_best", "rk3562", "go4_s_rk3562") == "go4_s_rk3562"

    def test_strips_trailing_rknn_extension(self):
        assert derive_output_basename("x", "rk3588", "custom.rknn") == "custom"


class TestValidateClassOrder:
    def test_canonical_order_returns_none(self):
        assert validate_class_order(["black", "white", "led_red", "led_green"]) is None

    def test_reordered_raises(self):
        with pytest.raises(ValueError):
            validate_class_order(["white", "black", "led_red", "led_green"])

    def test_missing_led_classes_raises(self):
        with pytest.raises(ValueError):
            validate_class_order(["black", "white"])

    def test_extra_class_raises(self):
        with pytest.raises(ValueError):
            validate_class_order(["black", "white", "led_red", "led_green", "extra"])

    def test_error_message_is_actionable(self):
        got = ["white", "black", "led_red", "led_green"]
        with pytest.raises(ValueError) as exc_info:
            validate_class_order(got)
        message = str(exc_info.value)
        assert str(["black", "white", "led_red", "led_green"]) in message
        assert str(got) in message
