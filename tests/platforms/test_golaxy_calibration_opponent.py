import sys, importlib
from pathlib import Path
import httpx, pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"))
adapters = importlib.import_module("adapters")
from katrain.core.ladder import get_rung, LadderRung

TOKEN = "tok"


def mk(h):
    return httpx.AsyncClient(transport=httpx.MockTransport(h))


def test_golaxy_move_takes_rung_not_raw_int():
    # signature must not accept a bare level int -> display_elo can't be passed as wire
    import inspect

    sig = inspect.signature(adapters.golaxy_move)
    assert "rung" in sig.parameters and "level" not in sig.parameters


def test_display_elo_unreachable_as_wire():
    # a rung's display_elo (e.g. 4000 for 星阵3星) is never used as the wire level
    r = get_rung(39)  # 星阵3星: api_level 3300, display_elo 4000
    assert r.golaxy_api_level == 3300 and r.display_elo == 4000


@pytest.mark.asyncio
async def test_golaxy_move_decodes_and_rejects_bad_api_level():
    seen = {}

    def h(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 72, "prob": 0.2}})

    val = await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(18), token=TOKEN)  # 1级=1100
    assert isinstance(val, int) and "level=1100" in seen["url"]
    bad = LadderRung(
        rung=1,
        golaxy_level_name="x",
        golaxy_api_level=4000,
        display_elo=4000,
        ref_rank="",
        rank_name="测试",
        net="b18",
        mechanism="net_search",
        human_sl_profile=None,
        max_visits=1,
        human_sl_params={},
        backend_hint="server",
        root_policy_temperature=1.0,
    )  # api_level=4000 (a display Elo)
    with pytest.raises(Exception):
        await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=bad, token=TOKEN)


@pytest.mark.asyncio
async def test_golaxy_move_unknown_coord_is_terminal():
    def h(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 99999, "prob": 0.0}})

    # pre-smoke (no codes): any out-of-board reply is UNVERIFIED "terminal", never scored
    assert await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(18), token=TOKEN) == "terminal"


@pytest.mark.asyncio
async def test_golaxy_move_classifies_verified_pass_and_resign():
    def h(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 361, "prob": 0.0}})

    # smoke-verified codes: 361 (out-of-board on 19x19) == pass here
    assert await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(18), token=TOKEN, pass_code=361) == "pass"

    def h2(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": -1, "prob": 0.0}})

    assert (
        await adapters.golaxy_move(mk(h2), moves_golaxy=[], rung=get_rung(18), token=TOKEN, resign_code=-1) == "resign"
    )


@pytest.mark.asyncio
async def test_invalid_sentinels_never_score_ordinary_replies():
    # An IN-BOARD 'code' (e.g. 100) must be rejected so a normal move (coord 100) is NOT misread as
    # resign/pass. And equal pass==resign codes are ambiguous -> both dropped (R5-H2).
    def h(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 100, "prob": 0.5}})

    assert (
        await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(18), token=TOKEN, resign_code=100) == 100
    )  # in-board resign_code dropped -> plain move

    def h2(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 361, "prob": 0.0}})

    assert (
        await adapters.golaxy_move(
            mk(h2), moves_golaxy=[], rung=get_rung(18), token=TOKEN, pass_code=361, resign_code=361
        )
        == "terminal"
    )  # equal -> neither trusted


@pytest.mark.asyncio
async def test_our_move_sends_shared_query_and_returns_gold_wire():
    seen = {}

    def h(req):
        import json

        seen["body"] = json.loads(req.content)
        hp = [0.0] * (19 * 19 + 1)
        hp[(19 - 3 - 1) * 19 + 3] = 1.0  # D4
        return httpx.Response(200, json={"humanPolicy": hp})

    val = await adapters.our_move(
        mk(h), "http://x:8000", moves_golaxy=[], rung=get_rung(1), board_size=19, komi=7.5, rules="chinese"
    )
    assert seen["body"]["maxVisits"] == 1
    assert seen["body"]["overrideSettings"]["humanSLProfile"] == "rank_20k"
    assert seen["body"]["overrideSettings"]["reportAnalysisWinratesAs"] == "BLACK"
    assert "maxTime" not in seen["body"]
    assert val == 288  # D4 gold-standard wire (proves no mirror)


@pytest.mark.asyncio
async def test_our_move_degraded_humansl_returns_unavailable():
    # humanSL rung 1 but response lacks humanPolicy -> our_move must return "unavailable"
    # (NOT a silent search move). The harness turns this into inconclusive_engine.
    def h(req):
        return httpx.Response(200, json={"moveInfos": [{"move": "Q16", "order": 0}]})

    val = await adapters.our_move(mk(h), "http://x:8000", moves_golaxy=[], rung=get_rung(1))
    assert val == "unavailable"


@pytest.mark.asyncio
async def test_adjudicate_missing_score_inconclusive():
    def h(req):
        return httpx.Response(200, json={"rootInfo": {}})

    score, settled = await adapters.adjudicate(mk(h), "http://x:8000", moves_golaxy=[288], visits=50)
    assert score is None and settled is False


def test_load_engine_wide_root_noise_from_config():
    assert adapters.load_engine_wide_root_noise({"wide_root_noise": 0.07, "max_visits": 50}) == 0.07


@pytest.mark.asyncio
async def test_smoke_probe_records(monkeypatch):
    smoke = importlib.import_module("run_smoke")

    def h(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 72, "prob": 0.2}})

    rec = await smoke.probe_level(mk(h), rung=get_rung(18), token=TOKEN)  # 1级
    assert rec["ok"] and rec["coord"] == 72 and rec["elapsed_s"] >= 0
