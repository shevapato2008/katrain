"""Single source of truth for YOLO detection classes.

Order is load-bearing: it IS the YOLO class-id order. black=0, white=1,
led_red=2, led_green=3. Red LED guides the next BLACK move; green LED guides
the next WHITE move (see manifest led_point.color).
"""

CLASS_NAMES: list[str] = ["black", "white", "led_red", "led_green"]

NAME_TO_ID: dict[str, int] = {name: i for i, name in enumerate(CLASS_NAMES)}
ID_TO_NAME: dict[int, str] = {i: name for i, name in enumerate(CLASS_NAMES)}

# Board-stone classes (everything else is guidance, not a stone on the board).
STONE_CLASS_IDS: frozenset[int] = frozenset({NAME_TO_ID["black"], NAME_TO_ID["white"]})

# manifest led_point.color (the color about to be played) -> LED class id.
LED_COLOR_TO_CLASS: dict[str, int] = {
    "black": NAME_TO_ID["led_red"],
    "white": NAME_TO_ID["led_green"],
}
