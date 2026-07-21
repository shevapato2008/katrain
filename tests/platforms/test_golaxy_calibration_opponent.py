import sys, importlib
from pathlib import Path
from types import SimpleNamespace
from types import MappingProxyType
import httpx, pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"))
adapters = importlib.import_module("adapters")
from katrain.core.ladder import get_rung, LadderRung

TOKEN = "tok"


def health_snapshot():
    return adapters.retain_health_snapshot(
        {
            "capability_schema": 1,
            "katago_version": "KataGo v1.16.3",
            "default_model": "b28",
            "models": {
                alias: {
                    "running": True,
                    "model_path": f"/models/{alias}.bin.gz",
                    "model_sha256": f"{alias}-sha",
                    "model_sha256_verified": True,
                    "has_human_model": True,
                    "human_model_path": "/models/human.bin.gz",
                    "human_model_sha256": "human-sha",
                    "human_model_sha256_verified": True,
                }
                for alias in ("b18", "b28")
            },
        }
    )


def attestation(alias="b28", **changes):
    value = {
        "selected_model": alias,
        "model_path": f"/models/{alias}.bin.gz",
        "model_sha256": f"{alias}-sha",
        "human_model_path": "/models/human.bin.gz",
        "human_model_sha256": "human-sha",
        "katago_version": "KataGo v1.16.3",
    }
    value.update(changes)
    return value


def mk(h):
    return httpx.AsyncClient(transport=httpx.MockTransport(h))


def test_retained_health_snapshot_is_deeply_immutable():
    snapshot = health_snapshot()
    assert isinstance(snapshot, MappingProxyType)
    with pytest.raises(TypeError):
        snapshot["models"]["b28"]["running"] = False


def test_golaxy_move_takes_rung_not_raw_int():
    # signature must not accept a bare level int -> display_elo can't be passed as wire
    import inspect

    sig = inspect.signature(adapters.golaxy_move)
    assert "rung" in sig.parameters and "level" not in sig.parameters


def test_calibration_anchors_require_a_golaxy_counterpart():
    calibration = importlib.import_module("run_calibration")

    assert calibration.parse_anchors("26:2,36:1") == [(26, 2), (36, 1)]
    for rung_n in (1, 25, 37):
        with pytest.raises(ValueError, match="Golaxy counterpart"):
            calibration.parse_anchors(f"{rung_n}:1")


def test_smoke_rungs_all_have_golaxy_counterparts():
    smoke = importlib.import_module("run_smoke")

    configured = smoke.LEVEL_PROBE_RUNGS + [rung_n for rung_n, _games in smoke.SMOKE_ANCHORS]
    assert configured
    assert all(26 <= rung_n <= 36 and get_rung(rung_n).golaxy_api_level is not None for rung_n in configured)


def test_display_elo_unreachable_as_wire():
    # a rung's display_elo (e.g. 4000 for 星阵3星) is never used as the wire level
    r = get_rung(36)  # 超职业 ↔ 星阵3星: api_level 3300, display_elo 4000
    assert r.golaxy_api_level == 3300 and r.display_elo == 4000


@pytest.mark.asyncio
async def test_golaxy_move_decodes_and_rejects_bad_api_level():
    seen = {}

    def h(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 72, "prob": 0.2}})

    val = await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(33), token=TOKEN)  # 9段=3000
    assert isinstance(val, int) and "level=3000" in seen["url"]
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
    assert await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(33), token=TOKEN) == "terminal"


@pytest.mark.asyncio
async def test_golaxy_move_classifies_verified_pass_and_resign():
    def h(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 361, "prob": 0.0}})

    # smoke-verified codes: 361 (out-of-board on 19x19) == pass here
    assert await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(33), token=TOKEN, pass_code=361) == "pass"

    def h2(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": -1, "prob": 0.0}})

    assert (
        await adapters.golaxy_move(mk(h2), moves_golaxy=[], rung=get_rung(33), token=TOKEN, resign_code=-1) == "resign"
    )


@pytest.mark.asyncio
async def test_invalid_sentinels_never_score_ordinary_replies():
    # An IN-BOARD 'code' (e.g. 100) must be rejected so a normal move (coord 100) is NOT misread as
    # resign/pass. And equal pass==resign codes are ambiguous -> both dropped (R5-H2).
    def h(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 100, "prob": 0.5}})

    assert (
        await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(33), token=TOKEN, resign_code=100) == 100
    )  # in-board resign_code dropped -> plain move

    def h2(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 361, "prob": 0.0}})

    assert (
        await adapters.golaxy_move(
            mk(h2), moves_golaxy=[], rung=get_rung(33), token=TOKEN, pass_code=361, resign_code=361
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
        mk(h),
        "http://x:8000",
        moves_golaxy=[],
        rung=get_rung(1),
        board_size=19,
        komi=7.5,
        rules="chinese",
        capabilities=health_snapshot(),
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

    val = await adapters.our_move(
        mk(h), "http://x:8000", moves_golaxy=[], rung=get_rung(1), capabilities=health_snapshot()
    )
    assert val == "unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "wrapper",
    [
        None,
        attestation(selected_model="b18"),
        attestation(model_path="/models/wrong.bin.gz"),
        attestation(model_sha256="wrong-sha"),
        attestation(human_model_sha256="wrong-human-sha"),
        attestation(katago_version="KataGo v0.old"),
    ],
)
async def test_our_move_search_rejects_missing_or_drifted_attestation(wrapper):
    def h(req):
        body = {"moveInfos": [{"move": "Q16", "order": 0}]}
        if wrapper is not None:
            body["_wrapper"] = wrapper
        return httpx.Response(200, json=body)

    assert (
        await adapters.our_move(
            mk(h), "http://x:8000", moves_golaxy=[], rung=get_rung(32), capabilities=health_snapshot()
        )
        == "unavailable"
    )


@pytest.mark.asyncio
async def test_our_move_search_accepts_complete_attestation_and_routes_b28():
    seen = {}

    def h(req):
        import json

        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={"moveInfos": [{"move": "Q16", "order": 0}], "_wrapper": attestation()},
        )

    value = await adapters.our_move(
        mk(h), "http://x:8000", moves_golaxy=[], rung=get_rung(32), capabilities=health_snapshot()
    )
    assert seen["body"]["overrideSettings"]["model"] == "b28"
    assert value == 72


@pytest.mark.asyncio
async def test_adjudicate_missing_score_inconclusive():
    def h(req):
        return httpx.Response(200, json={"rootInfo": {}})

    score, settled = await adapters.adjudicate(
        mk(h), "http://x:8000", moves_golaxy=[288], visits=50, capabilities=health_snapshot()
    )
    assert score is None and settled is False


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", [None, attestation(model_sha256="wrong")])
async def test_adjudicate_routes_b28_and_rejects_bad_attestation(wrapper):
    seen = {}

    def h(req):
        import json

        seen["body"] = json.loads(req.content)
        body = {"rootInfo": {"scoreLead": 12.0}, "ownership": [1.0] * 361}
        if wrapper is not None:
            body["_wrapper"] = wrapper
        return httpx.Response(200, json=body)

    assert await adapters.adjudicate(mk(h), "http://x:8000", moves_golaxy=[], capabilities=health_snapshot()) == (
        None,
        False,
    )
    assert seen["body"]["overrideSettings"]["model"] == "b28"


class _AsyncClientContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


@pytest.mark.asyncio
async def test_run_calibration_fetches_health_once_and_passes_same_snapshot(monkeypatch, tmp_path):
    calibration = importlib.import_module("run_calibration")
    snapshot = health_snapshot()
    fetched = []
    received = []

    async def fetch(client, base_url):
        fetched.append((client, base_url))
        return snapshot

    async def run_anchor(*_args, **kwargs):
        received.append(kwargs["capabilities"])
        return {"rung": 26}

    monkeypatch.setattr(calibration.httpx, "AsyncClient", _AsyncClientContext)
    monkeypatch.setattr(calibration.adapters, "fetch_health_snapshot", fetch)
    monkeypatch.setattr(calibration, "run_anchor", run_anchor)
    monkeypatch.setattr(calibration, "load_token", lambda _name: "token")
    monkeypatch.setattr(calibration, "resolve_wide_root_noise", lambda _value: 0.04)
    monkeypatch.setattr(calibration, "load_smoke_codes", lambda _path: (None, None, {}))
    args = SimpleNamespace(
        anchors="26:1,28:1",
        token_env="TOKEN",
        wide_root_noise=None,
        out=str(tmp_path),
        smoke_report=None,
        base_url="http://engine",
        throttle=0,
        move_throttle=0,
        visits_override=None,
    )

    assert await calibration.main_async(args) == 0
    assert len(fetched) == 1
    assert received == [snapshot, snapshot]


@pytest.mark.asyncio
async def test_run_smoke_fetches_health_once_and_passes_same_snapshot(monkeypatch, tmp_path):
    smoke = importlib.import_module("run_smoke")
    snapshot = health_snapshot()
    fetched = []
    received = []

    async def fetch(client, base_url):
        fetched.append((client, base_url))
        return snapshot

    async def run_anchor(*_args, **kwargs):
        received.append(kwargs["capabilities"])
        return {
            "golaxy_move_timing_s": [],
            "our_move_timing_s": [],
            "golaxy_terminal_rate": 0.0,
            "games": [],
            "golaxy_level_name": "x",
            "games_played": 0,
        }

    monkeypatch.setattr(smoke.httpx, "AsyncClient", _AsyncClientContext)
    monkeypatch.setattr(smoke.adapters, "fetch_health_snapshot", fetch)
    monkeypatch.setattr(smoke, "run_smoke_anchor", run_anchor)
    monkeypatch.setattr(smoke, "run_level_probes", lambda *_args: _async_value([]))
    monkeypatch.setattr(smoke, "load_token", lambda _name: "token")
    monkeypatch.setattr(smoke, "resolve_wide_root_noise", lambda _value: 0.04)
    args = SimpleNamespace(
        token_env="TOKEN",
        wide_root_noise=None,
        out=str(tmp_path),
        base_url="http://engine",
        games_per_anchor=1,
        throttle=0,
    )

    assert await smoke.main_async(args) == 0
    assert len(fetched) == 1
    assert received == [snapshot, snapshot]


async def _async_value(value):
    return value


def test_load_engine_wide_root_noise_from_config():
    assert adapters.load_engine_wide_root_noise({"wide_root_noise": 0.07, "max_visits": 50}) == 0.07


@pytest.mark.asyncio
async def test_smoke_probe_records(monkeypatch):
    smoke = importlib.import_module("run_smoke")

    def h(req):
        return httpx.Response(200, json={"code": "0", "msg": "", "data": {"coord": 72, "prob": 0.2}})

    rec = await smoke.probe_level(mk(h), rung=get_rung(33), token=TOKEN)  # 9段
    assert rec["ok"] and rec["coord"] == 72 and rec["elapsed_s"] >= 0
