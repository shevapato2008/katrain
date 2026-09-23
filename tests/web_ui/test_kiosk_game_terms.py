"""kiosk 那条端点上的 fail-closed:让子局不许再带贴目,`color` 只认黑白。

前端已经保证了(`kiosk/utils/setupOptions.ts` 的 `resolveGameTerms`),这里是第二道。
第二道值不值得写,判据是**它挡住的缺陷在用户那里看不看得出来**:
判胜负的那个数落进棋谱,错了不报错、不降级,一局棋照常下完、照常判出一个结果来。

改版前的真事故:前端在 `handicap > 0` 时只把贴目那一组从屏上换掉,`komi` state 不动
(缺省 6.5)且照样发出去 ⇒ 中国规则让 2 子实际是「白 +2(KataGo 的 `WHB_N` 自动加)
+ 6.5 目」,正是屏上那段说明警告的「补两遍」。
"""

import pytest

from katrain.web.server import _kiosk_game_terms


class TestHandicapZeroesKomi:
    def test_让子局归零(self):
        # 白方的补偿由 KataGo 自己加,komi 再写一遍就补两遍
        assert _kiosk_game_terms({"handicap": 2, "komi": 6.5}, 6.5, "japanese") == (2, 0.0, "japanese")
        assert _kiosk_game_terms({"handicap": 9, "komi": 7.5}, 7.5, "chinese") == (9, 0.0, "chinese")

    def test_已经是_0_的不动(self):
        assert _kiosk_game_terms({"handicap": 4, "komi": 0}, 6.5, "chinese")[1] == 0.0

    @pytest.mark.parametrize("ha", [0, 1])
    def test_不摆子的两档不归零(self, ha):
        """判据是 `>= 2` 不是 `> 0`。

        `HA[1]` 不摆子,KataGo 的补偿判据也是 `blackTurnAdvantage <= 1 → 0`
        (`KataGo/cpp/game/boardhistory.cpp:397-399`);而「让先」在 kiosk 的枚举里是
        **独立一档**(handicap=0 / komi=0),由前端的 `resolveGameTerms` 决定,
        不该由「让子兜底」这条规则管 —— 混进来就是两条规则争同一个值。
        """
        assert _kiosk_game_terms({"handicap": ha, "komi": 6.5}, 6.5, "japanese")[1] == 6.5

    def test_倒贴那一档的负贴目不许被当成让子归零(self):
        assert _kiosk_game_terms({"handicap": 0, "komi": -7.5}, 7.5, "chinese")[1] == -7.5

    def test_缺字段时走缺省(self):
        assert _kiosk_game_terms({}, 6.5, "japanese") == (0, 6.5, "japanese")
        assert _kiosk_game_terms({}, 7.5, "chinese") == (0, 7.5, "chinese")

    def test_handicap_是_None_时当成_0(self):
        # 前端某一版送了 null 的话,`int(None)` 会炸 —— 这条守的是那个
        assert _kiosk_game_terms({"handicap": None, "komi": 6.5}, 6.5, "japanese") == (0, 6.5, "japanese")
