import pytest

from katrain.web.kifu.round_names import display_round_name


@pytest.mark.parametrize(
    ("lang", "final", "semi", "quarter", "round_three"),
    [
        ("en", "Final", "Semifinal", "Quarterfinal", "Round 3"),
        ("cn", "决赛", "半决赛", "四分之一决赛", "第3轮"),
        ("tw", "決賽", "準決賽", "八強賽", "第3輪"),
        ("jp", "決勝", "準決勝", "準々決勝", "第3回戦"),
        ("ko", "결승", "준결승", "8강", "3라운드"),
        ("de", "Finale", "Halbfinale", "Viertelfinale", "Runde 3"),
        ("es", "Final", "Semifinal", "Cuartos de final", "Ronda 3"),
        ("fr", "Finale", "Demi-finale", "Quart de finale", "Tour 3"),
        ("ru", "Финал", "Полуфинал", "Четвертьфинал", "Раунд 3"),
        ("tr", "Final", "Yarı final", "Çeyrek final", "3. tur"),
        ("ua", "Фінал", "Півфінал", "Чвертьфінал", "Раунд 3"),
    ],
)
def test_common_rounds_in_every_supported_language(lang, final, semi, quarter, round_three):
    assert display_round_name("Final", lang) == final
    assert display_round_name("Semi-final", lang) == semi
    assert display_round_name("Quarterfinal", lang) == quarter
    assert display_round_name("Round 3", lang) == round_three


def test_chinese_round_inputs_and_unknown_values():
    assert display_round_name("半决赛", "en") == "Semifinal"
    assert display_round_name("决赛", "jp") == "決勝"
    assert display_round_name("第 12 轮", "en") == "Round 12"
    assert display_round_name("Game 3", "cn") == "Game 3"
    assert display_round_name("Final, Game 3", "cn") == "Final, Game 3"
    assert display_round_name("第3", "en") == "第3"
    assert display_round_name("Round 3轮", "en") == "Round 3轮"
    assert display_round_name("Final", "xx") == "Final"
    assert display_round_name(None, "en") is None
