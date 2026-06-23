from types import SimpleNamespace

from katrain.vision.tools.train_model import build_train_kwargs, LED_SAFE_AUG


def _args(**over):
    base = dict(
        data="d.yaml", epochs=1, imgsz=640, batch=8, name="n", patience=10, device="cpu", cache=True, augment="led-safe"
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_led_safe_zeroes_hue_and_sets_key_aug():
    kw = build_train_kwargs(_args())
    assert kw["hsv_h"] == 0.0  # hue is the LED class signal — never jitter
    assert kw["copy_paste"] == 0.0  # no-op on bbox labels (needs segments) — must NOT be relied on
    assert kw["close_mosaic"] == 15
    assert kw["mixup"] == 0.0 and kw["degrees"] == 0.0 and kw["flipud"] == 0.0
    assert kw["fliplr"] == 0.5
    assert kw["data"] == "d.yaml" and kw["imgsz"] == 640 and kw["cache"] is True


def test_default_augment_leaves_ultralytics_defaults():
    kw = build_train_kwargs(_args(augment="default"))
    assert "hsv_h" not in kw  # no override → ultralytics defaults apply
    assert kw["data"] == "d.yaml"


def test_led_safe_aug_constant_is_hue_locked():
    assert LED_SAFE_AUG["hsv_h"] == 0.0
