"""Mainland identity keys must have exactly one ASCII representation."""

import pytest

from katrain.web.core.phone import mask_phone, normalize_phone


@pytest.mark.parametrize(
    "raw",
    ["13800138000", "+8613800138000", "008613800138000", " +86 138-0013-8000 ", "0086 (138) 0013.8000"],
)
def test_domestic_spellings_share_one_key(raw):
    assert normalize_phone(raw) == "+8613800138000"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " ",
        None,
        13800138000,
        "+85213800138000",
        "+113800138000",
        "8613800138000",
        "013800138000",
        "1380013800",
        "138001380000",
        "23800138000",
        "13800138000,13900139000",
        "１3800138000",
        "+861３800138000",
        "١3800138000",
        "138\n00138000",
        "138\t00138000",
        "138\u00a000138000",
        "138/0013/8000",
        "13800138000<script>",
    ],
)
def test_invalid_input_has_a_constant_non_sensitive_error(raw):
    with pytest.raises(ValueError, match="^Invalid mainland mobile number$"):
        normalize_phone(raw)


def test_mask_is_for_validated_e164_only():
    assert mask_phone("+8613800138000") == "+86 138****8000"
    for raw in ("13800138000", "+85213800138000", "+861３800138000", None):
        with pytest.raises(ValueError, match="^Invalid mainland mobile number$"):
            mask_phone(raw)
