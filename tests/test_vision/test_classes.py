from katrain.vision.classes import (
    CLASS_NAMES,
    NAME_TO_ID,
    ID_TO_NAME,
    STONE_CLASS_IDS,
    LED_COLOR_TO_CLASS,
)


def test_class_order_is_fixed():
    assert CLASS_NAMES == ["black", "white", "led_red", "led_green"]


def test_id_maps_round_trip():
    assert NAME_TO_ID == {"black": 0, "white": 1, "led_red": 2, "led_green": 3}
    assert ID_TO_NAME == {0: "black", 1: "white", 2: "led_red", 3: "led_green"}


def test_stone_ids_exclude_leds():
    assert STONE_CLASS_IDS == frozenset({0, 1})


def test_led_color_maps_black_to_red_white_to_green():
    # red guides the next BLACK move, green guides the next WHITE move
    assert LED_COLOR_TO_CLASS == {"black": 2, "white": 3}
