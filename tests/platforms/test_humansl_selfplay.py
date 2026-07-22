import importlib
import json
import math
import sys
from pathlib import Path

import httpx
import pytest

from katrain.core.ladder import HUMANSL_PIKL_BASELINE


CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
selfplay = importlib.import_module("run_selfplay")


def test_player_constructs_attested_b18_humansl_search_recipe():
    label, rung, selection = selfplay.make_player("rank_9d@40")

    assert label == "rank_9d@40"
    assert rung.net == "b18"
    assert rung.mechanism == "humansl_search"
    assert rung.human_sl_profile == "rank_9d"
    assert rung.max_visits == 40
    assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
    assert rung.human_sl_params is not HUMANSL_PIKL_BASELINE
    assert selection == "search"


def test_player_gives_each_humansl_search_player_a_fresh_recipe():
    _, first, _ = selfplay.make_player("rank_5d@40")
    _, second, _ = selfplay.make_player("rank_5d@80")

    assert first.human_sl_params == second.human_sl_params == HUMANSL_PIKL_BASELINE
    assert first.human_sl_params is not second.human_sl_params


@pytest.mark.parametrize(
    ("spec", "mechanism", "net", "selection"),
    [
        ("rank_9d@1", "humansl", "humanv0", "weighted"),
        ("rank_9d@1s", "humansl", "humanv0", "argmax_human"),
        ("b28@20", "net_search", "b28", "search"),
    ],
)
def test_player_preserves_native_and_pure_search_modes(spec, mechanism, net, selection):
    _, rung, actual_selection = selfplay.make_player(spec)

    assert rung.mechanism == mechanism
    assert rung.net == net
    assert rung.human_sl_params == {}
    assert actual_selection == selection


@pytest.mark.parametrize("visits", [2, 7, 16, 32, 39])
def test_player_rejects_unsupported_humansl_search_visits(visits):
    with pytest.raises(ValueError, match=r"HumanSL search.*minimum.*40"):
        selfplay.make_player(f"rank_9d@{visits}")


def test_player_rejects_search_suffix_above_one_visit():
    with pytest.raises(ValueError, match=r"1s"):
        selfplay.make_player("rank_9d@40s")


@pytest.mark.parametrize(
    "profile",
    [
        "rank_20k",
        "rank_1k",
        "rank_1d",
        "rank_9d",
        "rank_20k_9d",
        "preaz_20k",
        "preaz_9d",
        "preaz_1d_1k",
        "proyear_1800",
        "proyear_2023",
    ],
)
def test_player_accepts_exact_katago_humansl_profile_boundaries(profile):
    _, rung, _ = selfplay.make_player(f"{profile}@40")

    assert rung.human_sl_profile == profile


@pytest.mark.parametrize(
    "profile",
    [
        "rank_0k",
        "rank_21k",
        "rank_0d",
        "rank_10d",
        "rank_09d",
        "rank_1x",
        "rank_1d_extra",
        "preaz_21k",
        "preaz_10d",
        "preaz_1d_extra_piece",
        "proyear_1799",
        "proyear_2024",
        "proyear_20x0",
        "proyear_",
    ],
)
def test_player_rejects_out_of_range_or_malformed_humansl_profiles(profile):
    with pytest.raises(ValueError, match=r"bad player profile"):
        selfplay.make_player(f"{profile}@40")


def _health_snapshot():
    return selfplay.adapters.retain_health_snapshot(
        {
            "capability_schema": 1,
            "katago_version": "KataGo v1.16.3",
            "default_model": "b28",
            "models": {
                "b18": {
                    "running": True,
                    "model_path": "/models/b18.bin.gz",
                    "model_sha256": "b18-sha",
                    "model_sha256_verified": True,
                    "has_human_model": True,
                    "human_model_path": "/models/human.bin.gz",
                    "human_model_sha256": "human-sha",
                    "human_model_sha256_verified": True,
                },
                "b28": {
                    "running": True,
                    "model_path": "/models/b28.bin.gz",
                    "model_sha256": "b28-sha",
                    "model_sha256_verified": True,
                    "has_human_model": True,
                    "human_model_path": "/models/human.bin.gz",
                    "human_model_sha256": "human-sha",
                    "human_model_sha256_verified": True,
                },
            },
        }
    )


def _attestation(**changes):
    wrapper = {
        "selected_model": "b28",
        "model_path": "/models/b28.bin.gz",
        "model_sha256": "b28-sha",
        "human_model_path": "/models/human.bin.gz",
        "human_model_sha256": "human-sha",
        "katago_version": "KataGo v1.16.3",
    }
    wrapper.update(changes)
    return wrapper


@pytest.mark.asyncio
@pytest.mark.parametrize("player_spec", ["rank_9d@1", "rank_9d@1s"])
@pytest.mark.parametrize("wrapper", [None, _attestation(human_model_sha256="drifted")])
async def test_native_humansl_selection_rejects_missing_or_drifted_attestation(player_spec, wrapper):
    _, rung, selection = selfplay.make_player(player_spec)

    def handler(request):
        body = json.loads(request.content)
        assert body["overrideSettings"].get("model") is None
        human_policy = [0.0] * (19 * 19 + 1)
        human_policy[0] = 1.0
        response = {"humanPolicy": human_policy}
        if wrapper is not None:
            response["_wrapper"] = wrapper
        return httpx.Response(200, json=response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
        )

    assert result == "unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize("player_spec", ["rank_9d@1", "rank_9d@1s"])
async def test_native_humansl_selection_accepts_full_default_model_attestation(player_spec):
    _, rung, selection = selfplay.make_player(player_spec)
    attestations = []

    def handler(_request):
        human_policy = [0.0] * (19 * 19 + 1)
        human_policy[0] = 1.0
        return httpx.Response(200, json={"humanPolicy": human_policy, "_wrapper": _attestation()})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            attestations=attestations,
            player="A",
        )

    assert result != "unavailable"
    assert attestations == [{"ply": 0, "player": "A", "identity": _attestation()}]


@pytest.mark.asyncio
async def test_humansl_search_move_records_complete_b18_attestation():
    _, rung, selection = selfplay.make_player("rank_9d@40")
    attestations = []
    b18_attestation = _attestation(
        selected_model="b18",
        model_path="/models/b18.bin.gz",
        model_sha256="b18-sha",
        wrapper_extension="preserved",
    )

    def handler(request):
        body = json.loads(request.content)
        assert body["overrideSettings"]["model"] == "b18"
        return httpx.Response(
            200,
            json={"moveInfos": [{"move": "Q16", "order": 0}], "_wrapper": b18_attestation},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            attestations=attestations,
            player="A",
        )

    assert result != "unavailable"
    assert attestations == [{"ply": 0, "player": "A", "identity": b18_attestation}]


def test_default_result_namespace_is_v2_pikl_and_legacy_namespace_is_rejected():
    args = selfplay.build_arg_parser().parse_args(["--matchups", "rank_9d@80:rank_9d@40:1"])

    assert Path(args.out).name == "selfplay_v2_pikl"
    with pytest.raises(ValueError, match=r"legacy.*selfplay_v2_pikl"):
        selfplay._validated_out_dir(Path(selfplay.__file__).parent / "results" / "selfplay")


def _players():
    return {
        "A": selfplay.make_player("rank_9d@40"),
        "B": selfplay.make_player("b28@20"),
    }


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda h: h["models"].pop("b18"), "b18"),
        (lambda h: h["models"]["b18"].update(running=False), "not running"),
        (lambda h: h["models"]["b18"].update(has_human_model=False), "human model"),
        (lambda h: h["models"]["b18"].update(human_model_sha256_verified=False), "human model"),
    ],
)
def test_capability_preflight_rejects_missing_stopped_or_nonhuman_alias(mutation, match):
    frozen = _health_snapshot()
    health = {key: value for key, value in frozen.items() if key != "models"}
    health["models"] = {name: dict(identity) for name, identity in frozen["models"].items()}
    mutation(health)

    with pytest.raises(ValueError, match=match):
        selfplay._preflight_capabilities(health, _players())


def test_capability_preflight_returns_requested_and_referee_identities():
    identities = selfplay._preflight_capabilities(_health_snapshot(), _players())

    assert identities["A"]["selected_model"] == "b18"
    assert identities["A"]["model_sha256"] == "b18-sha"
    assert identities["A"]["human_model_sha256"] == "human-sha"
    assert identities["B"]["selected_model"] == "b28"
    assert identities["referee"]["selected_model"] == "b28"


def test_fingerprint_configuration_captures_all_strength_relevant_inputs():
    players = _players()
    identities = selfplay._preflight_capabilities(_health_snapshot(), players)

    configuration = selfplay._matchup_configuration(
        players,
        identities,
        capabilities=_health_snapshot(),
        wide_root_noise=0.04,
        target_pairs=20,
        max_pair_attempts=30,
    )
    digest = selfplay._configuration_fingerprint(configuration)

    assert configuration["capability_schema"] == 1
    assert configuration["katago_version"] == "KataGo v1.16.3"
    assert configuration["players"]["A"]["identity"]["model_sha256"] == "b18-sha"
    assert configuration["players"]["A"]["identity"]["human_model_sha256"] == "human-sha"
    assert all(
        configuration["players"]["A"]["effective_overrides"][key] == value
        for key, value in HUMANSL_PIKL_BASELINE.items()
    )
    assert configuration["players"]["A"]["effective_overrides"]["humanSLProfile"] == "rank_9d"
    assert configuration["players"]["A"]["requested_main_model"] == "b18"
    assert configuration["players"]["A"]["http_effective_overrides"]["model"] == "b18"
    assert configuration["players"]["A"]["http_effective_overrides"]["wideRootNoise"] == 0.04
    assert configuration["players"]["A"]["visits"] == 40
    assert configuration["players"]["A"]["selection_algorithm_version"]
    assert configuration["wide_root_noise"] == 0.04
    assert configuration["game"] == {
        "board_size": 19,
        "komi": 7.5,
        "rules": selfplay.adapters.BaseEngine.get_rules("chinese"),
        "move_cap": 400,
    }
    assert configuration["referee"]["visits"] == 200
    assert configuration["referee"]["requested_main_model"] == "b28"
    assert configuration["referee"]["http_effective_overrides"] == {
        "model": "b28",
        "reportAnalysisWinratesAs": "BLACK",
    }
    assert configuration["adjudication_algorithm_version"]
    assert configuration["symmetry_settings"]
    assert configuration["opening_suite"]["id"]
    assert configuration["target_complete_pairs"] == 20
    assert configuration["max_pair_attempts"] == 30
    assert len(digest) == 64


@pytest.mark.parametrize(("target", "attempts"), [(True, 30), (20, False), (0, 30), (20, 0)])
def test_matchup_configuration_rejects_nonpositive_or_bool_declared_counts(target, attempts):
    players = _players()
    identities = selfplay._preflight_capabilities(_health_snapshot(), players)

    with pytest.raises(ValueError, match="plain int"):
        selfplay._matchup_configuration(
            players,
            identities,
            capabilities=_health_snapshot(),
            wide_root_noise=0.04,
            target_pairs=target,
            max_pair_attempts=attempts,
        )


def test_fingerprint_is_stable_across_mapping_insertion_order():
    first = {"outer": {"b": 2, "a": 1}, "items": [{"z": 3, "y": 2}]}
    second = {"items": [{"y": 2, "z": 3}], "outer": {"a": 1, "b": 2}}

    assert selfplay._configuration_fingerprint(first) == selfplay._configuration_fingerprint(second)


def _checkpoint_payload():
    players = _players()
    identities = selfplay._preflight_capabilities(_health_snapshot(), players)
    configuration = selfplay._matchup_configuration(
        players,
        identities,
        capabilities=_health_snapshot(),
        wide_root_noise=0.04,
        target_pairs=20,
        max_pair_attempts=30,
    )
    fingerprint = selfplay._configuration_fingerprint(configuration)
    header = {
        "record_type": "header",
        "schema": 3,
        "fingerprint": fingerprint,
        "configuration": configuration,
    }
    game = {
        "record_type": "game",
        "fingerprint": fingerprint,
        "index": 0,
        "phase": "confirm",
        "opening_id": "o001",
        "opening_moves": [],
        "pair_attempt": 0,
        "color_index": 0,
        "a_color": "B",
        "conclusive": True,
        "our_win": True,
        "result": "our_win",
        "player_a": "rank_9d@40",
        "player_b": "b28@20",
        "num_moves": 2,
        "attested_turn_count": 2,
        "black_score": 1.5,
        "end_reason": "move_cap",
        "our_color": "B",
        "ts": 1.0,
        "move_attestations": [
            {"ply": 0, "player": "A", "identity": dict(identities["A"])},
            {"ply": 1, "player": "B", "identity": dict(identities["B"])},
        ],
    }
    return configuration, fingerprint, header, game


def test_resume_accepts_schema3_header_and_matching_record_attestations(tmp_path):
    configuration, fingerprint, header, game = _checkpoint_payload()
    checkpoint = tmp_path / "match.jsonl"
    checkpoint.write_text(json.dumps(header) + "\n" + json.dumps(game) + "\n")

    assert selfplay._already_done(checkpoint, fingerprint, configuration) == 1


@pytest.mark.parametrize(("field", "value"), [("target_complete_pairs", 21), ("max_pair_attempts", 31)])
def test_resume_rejects_declared_target_or_attempt_guard_drift(tmp_path, field, value):
    configuration, fingerprint, header, _game = _checkpoint_payload()
    checkpoint = tmp_path / "match.jsonl"
    checkpoint.write_text(json.dumps(header) + "\n")
    changed = json.loads(json.dumps(configuration))
    changed[field] = value

    with pytest.raises(ValueError, match="fingerprint"):
        selfplay._already_done(checkpoint, selfplay._configuration_fingerprint(changed), changed)


@pytest.mark.parametrize("target", ["header", "record"])
def test_resume_rejects_any_header_or_record_fingerprint_mismatch(tmp_path, target):
    configuration, fingerprint, header, game = _checkpoint_payload()
    (header if target == "header" else game)["fingerprint"] = "0" * 64
    checkpoint = tmp_path / "match.jsonl"
    checkpoint.write_text(json.dumps(header) + "\n" + json.dumps(game) + "\n")

    with pytest.raises(ValueError, match="fingerprint"):
        selfplay._already_done(checkpoint, fingerprint, configuration)


def test_resume_rejects_recorded_move_attestation_drift(tmp_path):
    configuration, fingerprint, header, game = _checkpoint_payload()
    game["move_attestations"][0]["identity"]["model_sha256"] = "drifted"
    checkpoint = tmp_path / "match.jsonl"
    checkpoint.write_text(json.dumps(header) + "\n" + json.dumps(game) + "\n")

    with pytest.raises(ValueError, match="attestation"):
        selfplay._already_done(checkpoint, fingerprint, configuration)


def test_resume_rejects_game_record_missing_an_accepted_move_attestation(tmp_path):
    configuration, fingerprint, header, game = _checkpoint_payload()
    game["num_moves"] = 2
    game["move_attestations"].pop()
    checkpoint = tmp_path / "match.jsonl"
    checkpoint.write_text(json.dumps(header) + "\n" + json.dumps(game) + "\n")

    with pytest.raises(ValueError, match="every accepted move"):
        selfplay._already_done(checkpoint, fingerprint, configuration)


def test_resume_rejects_move_attestation_relabelled_to_wrong_player(tmp_path):
    configuration, fingerprint, header, game = _checkpoint_payload()
    game["move_attestations"][0]["player"] = "B"
    game["move_attestations"][0]["identity"] = dict(configuration["players"]["B"]["identity"])
    checkpoint = tmp_path / "match.jsonl"
    checkpoint.write_text(json.dumps(header) + "\n" + json.dumps(game) + "\n")

    with pytest.raises(ValueError, match="wrong player"):
        selfplay._already_done(checkpoint, fingerprint, configuration)


def _second_game(configuration, fingerprint):
    game = json.loads(json.dumps(_checkpoint_payload()[3]))
    game.update(index=1, a_color="W", our_color="W", color_index=1, our_win=False, result="our_loss", ts=2.0)
    game["move_attestations"] = [
        {"ply": 0, "player": "B", "identity": dict(configuration["players"]["B"]["identity"])},
        {"ply": 1, "player": "A", "identity": dict(configuration["players"]["A"]["identity"])},
    ]
    return game


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda games: games[1].update(index=0),
        lambda games: games[1].update(index=2),
        lambda games: games[1].update(index=1.0),
        lambda games: games.reverse(),
        lambda games: games[1].update(a_color="B"),
        lambda games: games[1].update(player_a="wrong"),
        lambda games: games[1].update(our_win="yes"),
        lambda games: games[1].update(result="fabricated"),
        lambda games: games[1].update(result=[]),
        lambda games: games[1].pop("black_score"),
        lambda games: games[1].update(ts=math.nan),
        lambda games: games[0]["move_attestations"][0].update(ply=False),
        lambda games: games[0].update(color_index=True),
        lambda games: games[0].update(pair_attempt=True),
    ],
)
def test_resume_rejects_duplicate_gap_reordered_or_corrupt_game_sequence(tmp_path, corrupt):
    configuration, fingerprint, header, first = _checkpoint_payload()
    first.update(player_a="rank_9d@40", player_b="b28@20")
    games = [first, _second_game(configuration, fingerprint)]
    corrupt(games)
    checkpoint = tmp_path / "match.jsonl"
    checkpoint.write_text("\n".join(json.dumps(record) for record in [header, *games]) + "\n")

    with pytest.raises(ValueError, match="checkpoint game"):
        selfplay._already_done(checkpoint, fingerprint, configuration)


def test_checkpoint_lock_rejects_contention_and_releases(tmp_path):
    checkpoint = tmp_path / "match.jsonl"

    with selfplay._checkpoint_lock(checkpoint):
        with pytest.raises(RuntimeError, match="locked"):
            with selfplay._checkpoint_lock(checkpoint):
                pass

    with selfplay._checkpoint_lock(checkpoint):
        pass


@pytest.mark.asyncio
async def test_self_produced_terminal_pass_record_roundtrips_on_resume(tmp_path, monkeypatch):
    calls = {"games": 0}

    async def fake_play_one_game(*, our_move, golaxy_move, adjudicate, our_color, initial_history, **_settings):
        calls["games"] += 1
        mover = our_move if our_color == "B" else golaxy_move
        assert await mover(initial_history) == "pass"
        return selfplay.GameOutcome(our_color, "our_win", True, len(initial_history), 1.5, True, "our_pass")

    monkeypatch.setattr(selfplay, "play_one_game", fake_play_one_game)
    monkeypatch.setattr(selfplay, "required_conclusive_pairs", lambda *_args, **_kwargs: 1)

    def handler(request):
        body = json.loads(request.content)
        model = body["overrideSettings"]["model"]
        return httpx.Response(
            200,
            json={
                "moveInfos": [{"move": "pass", "order": 0}],
                "_wrapper": _attestation(
                    selected_model=model,
                    model_path=f"/models/{model}.bin.gz",
                    model_sha256=f"{model}-sha",
                ),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        kwargs = dict(
            client=client,
            base_url="http://engine",
            wrn=0.04,
            out_dir=tmp_path,
            capabilities=_health_snapshot(),
        )
        await selfplay.run_matchup("rank_9d@40", "b28@20", 1, phase="screen", max_pair_attempts=1, **kwargs)
        await selfplay.run_matchup("rank_9d@40", "b28@20", 1, phase="screen", max_pair_attempts=1, **kwargs)

    assert calls["games"] == 2
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert records[1]["num_moves"] == len(records[1]["opening_moves"])
    assert records[1]["attested_turn_count"] == 1
    assert len(records[1]["move_attestations"]) == 1


@pytest.mark.asyncio
async def test_self_produced_unavailable_record_roundtrips_on_resume(tmp_path, monkeypatch):
    calls = {"games": 0}

    async def fake_play_one_game(*, our_move, golaxy_move, adjudicate, our_color, initial_history, **_settings):
        calls["games"] += 1
        assert await our_move(initial_history) == "unavailable"
        return selfplay.GameOutcome(
            our_color, "inconclusive_engine", False, len(initial_history), None, False, "our_pass"
        )

    monkeypatch.setattr(selfplay, "play_one_game", fake_play_one_game)
    monkeypatch.setattr(selfplay, "required_conclusive_pairs", lambda *_args, **_kwargs: 1)

    def handler(request):
        body = json.loads(request.content)
        assert body["boardXSize"] == selfplay.BOARD_SIZE
        assert body["boardYSize"] == selfplay.BOARD_SIZE
        assert body["komi"] == selfplay.KOMI
        assert body["rules"] == selfplay.adapters.BaseEngine.get_rules(selfplay.RULES)
        return httpx.Response(
            200,
            json={
                "moveInfos": [],
                "_wrapper": _attestation(selected_model="b18", model_path="/models/b18.bin.gz", model_sha256="b18-sha"),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        kwargs = dict(
            client=client,
            base_url="http://engine",
            wrn=0.04,
            out_dir=tmp_path,
            capabilities=_health_snapshot(),
        )
        await selfplay.run_matchup("rank_9d@40", "b28@20", 1, phase="screen", max_pair_attempts=1, **kwargs)
        await selfplay.run_matchup("rank_9d@40", "b28@20", 1, phase="screen", max_pair_attempts=1, **kwargs)

    assert calls["games"] == 2
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert records[1]["result"] == "inconclusive_engine"
    assert records[1]["attested_turn_count"] == 0


@pytest.mark.asyncio
async def test_player_move_uses_shared_board_komi_and_rules_constants(monkeypatch):
    monkeypatch.setattr(selfplay, "BOARD_SIZE", 9)
    monkeypatch.setattr(selfplay, "KOMI", 6.5)
    monkeypatch.setattr(selfplay, "RULES", "japanese")
    _, rung, selection = selfplay.make_player("rank_9d@1s")

    def handler(request):
        body = json.loads(request.content)
        assert body["boardXSize"] == body["boardYSize"] == 9
        assert body["komi"] == 6.5
        assert body["rules"] == selfplay.adapters.BaseEngine.get_rules("japanese")
        human_policy = [0.0] * (9 * 9 + 1)
        human_policy[0] = 1.0
        return httpx.Response(200, json={"humanPolicy": human_policy, "_wrapper": _attestation()})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
        )

    assert isinstance(result, int)
    assert 0 <= result < 9 * 9


def test_checkpoint_lock_selects_windows_backend_when_fcntl_is_unavailable(tmp_path, monkeypatch):
    class FakeMsvcrt:
        LK_NBLCK = 1
        LK_UNLCK = 2

        def __init__(self):
            self.calls = []

        def locking(self, fd, operation, size):
            self.calls.append((operation, size))

    fake = FakeMsvcrt()
    monkeypatch.setattr(selfplay, "_fcntl", None)
    monkeypatch.setattr(selfplay, "_msvcrt", fake)

    with selfplay._checkpoint_lock(tmp_path / "match.jsonl"):
        assert fake.calls == [(fake.LK_NBLCK, 1)]
    assert fake.calls == [(fake.LK_NBLCK, 1), (fake.LK_UNLCK, 1)]


@pytest.mark.asyncio
async def test_run_matchup_rejects_any_target_drift_from_existing_checkpoint(tmp_path, monkeypatch):
    calls = {"games": 0}

    async def fake_play_one_game(*, our_move, golaxy_move, adjudicate, our_color, initial_history, **_settings):
        calls["games"] += 1
        mover = our_move if our_color == "B" else golaxy_move
        assert await mover(initial_history) == "pass"
        return selfplay.GameOutcome(our_color, "our_win", True, len(initial_history), 1.5, True, "our_pass")

    monkeypatch.setattr(selfplay, "play_one_game", fake_play_one_game)
    monkeypatch.setattr(selfplay, "required_conclusive_pairs", lambda *_args, **_kwargs: 0)

    def handler(request):
        model = json.loads(request.content)["overrideSettings"]["model"]
        return httpx.Response(
            200,
            json={
                "moveInfos": [{"move": "pass", "order": 0}],
                "_wrapper": _attestation(
                    selected_model=model, model_path=f"/models/{model}.bin.gz", model_sha256=f"{model}-sha"
                ),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        kwargs = dict(
            client=client,
            base_url="http://engine",
            wrn=0.04,
            out_dir=tmp_path,
            capabilities=_health_snapshot(),
        )
        await selfplay.run_matchup("rank_9d@40", "b28@20", 1, **kwargs)
        with pytest.raises(ValueError, match="fingerprint"):
            await selfplay.run_matchup("rank_9d@40", "b28@20", 2, **kwargs)


def test_fresh_checkpoint_writes_schema3_header_before_append(tmp_path):
    configuration, fingerprint, _header, _game = _checkpoint_payload()
    checkpoint = tmp_path / "match.jsonl"

    assert selfplay._prepare_checkpoint(checkpoint, fingerprint, configuration) == 0
    lines = checkpoint.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "record_type": "header",
        "schema": 3,
        "fingerprint": fingerprint,
        "configuration": configuration,
    }


@pytest.mark.parametrize(
    ("wins", "games", "expected"),
    [
        (0, 1, (0.0, 0.7934506856227626)),
        (5, 10, (0.236593090512564, 0.7634069094874361)),
        (30, 40, (0.5980603857923197, 0.858128813609037)),
        (40, 40, (0.9123783988027132, 1.0)),
    ],
)
def test_wilson_interval_locked_numerical_cases(wins, games, expected):
    actual = selfplay.wilson_interval(wins, games)
    assert actual == pytest.approx(expected, abs=1e-15)


@pytest.mark.parametrize(
    ("wins", "games", "expected"),
    [(30, 40, "a_stronger"), (20, 40, "inconclusive"), (10, 40, "a_weaker")],
)
def test_classify_seam_locked_cases(wins, games, expected):
    assert selfplay.classify_seam(wins, games) == expected


def test_classify_refuses_underpowered_confirmatory_samples():
    assert selfplay.classify_seam(38, 38) == "insufficient_pairs"
    assert selfplay.classify_seam(78, 78, experiment4=True) == "insufficient_pairs"
    assert selfplay.classify_seam(40, 40, experiment4=True) == "insufficient_pairs"
    assert selfplay.classify_seam(80, 80, experiment4=True) == "a_stronger"


def test_screen_target_is_exactly_ten_complete_pairs():
    assert selfplay.required_conclusive_pairs("screen", experiment4=False) == 10
    assert selfplay.required_conclusive_pairs("confirm", experiment4=False) == 20
    assert selfplay.required_conclusive_pairs("confirm", experiment4=True) == 40
    with pytest.raises(ValueError, match="experiment-4.*confirm"):
        selfplay.required_conclusive_pairs("screen", experiment4=True)


def _paired_record(pair_attempt, color_index, *, conclusive=True, our_win=False, phase="screen", opening_id="o001"):
    return {
        "phase": phase,
        "opening_id": opening_id,
        "pair_attempt": pair_attempt,
        "color_index": color_index,
        "conclusive": conclusive,
        "our_win": our_win,
        "opening_moves": [0, 20] if opening_id == "o001" else [2, 22],
    }


def test_inconclusive_opening_pair_contributes_zero_decision_games():
    records = [
        _paired_record(0, 0, conclusive=True, our_win=True),
        _paired_record(0, 1, conclusive=False),
        _paired_record(1, 0, conclusive=True, our_win=False, opening_id="o002"),
        _paired_record(1, 1, conclusive=True, our_win=True, opening_id="o002"),
    ]

    sample = selfplay.complete_pair_sample(records, phase="screen")

    assert sample == {"complete_pairs": 1, "games": 2, "a_wins": 1, "inconclusive_pairs": 1}


def test_pair_scheduler_orders_colors_and_completes_interrupted_pair_first():
    openings = [{"id": "o001", "moves": [0, 20]}, {"id": "o002", "moves": [2, 22]}]
    records = [_paired_record(0, 0, opening_id="o001")]

    scheduled = selfplay.schedule_pair_games(records, openings, phase="screen", max_pair_attempts=2)

    assert [(s["pair_attempt"], s["opening_id"], s["color_index"], s["a_color"]) for s in scheduled] == [
        (0, "o001", 1, "W"),
        (1, "o002", 0, "B"),
        (1, "o002", 1, "W"),
    ]
    assert scheduled[0]["initial_history"] == [0, 20]


def test_pair_scheduler_rejects_phase_leakage_duplicate_color_and_attempt_overflow():
    openings = [{"id": "o001", "moves": [0, 20]}]
    with pytest.raises(ValueError, match="phase"):
        selfplay.schedule_pair_games(
            [_paired_record(0, 0, phase="confirm")], openings, phase="screen", max_pair_attempts=1
        )
    with pytest.raises(ValueError, match="duplicate"):
        selfplay.schedule_pair_games(
            [_paired_record(0, 0), _paired_record(0, 0)], openings, phase="screen", max_pair_attempts=1
        )
    with pytest.raises(ValueError, match="maximum pair attempts"):
        selfplay.schedule_pair_games([_paired_record(1, 0)], openings, phase="screen", max_pair_attempts=1)


@pytest.mark.parametrize(("field", "value"), [("color_index", True), ("pair_attempt", False)])
def test_pair_helpers_reject_bool_schema_integers(field, value):
    openings = [{"id": "o001", "moves": [0, 20]}]
    record = _paired_record(0, 0)
    record[field] = value

    with pytest.raises(ValueError, match="pair"):
        selfplay.complete_pair_sample([record], phase="screen")
    with pytest.raises(ValueError, match="pair"):
        selfplay.schedule_pair_games([record], openings, phase="screen", max_pair_attempts=1)


def test_pair_scheduler_rejects_resume_opening_history_drift():
    openings = [{"id": "o001", "moves": [0, 20]}]
    record = _paired_record(0, 0)
    record["opening_moves"] = [2, 22]

    with pytest.raises(ValueError, match="opening.*history"):
        selfplay.schedule_pair_games([record], openings, phase="screen", max_pair_attempts=1)


def test_pair_scheduler_exhausts_declared_max_attempts_without_runtime_generation():
    openings = [{"id": "o001", "moves": [0, 20]}, {"id": "o002", "moves": [2, 22]}]
    scheduled = selfplay.schedule_pair_games([], openings, phase="confirm", max_pair_attempts=5)

    assert len(scheduled) == 10
    assert [s["opening_id"] for s in scheduled[::2]] == ["o001", "o002", "o001", "o002", "o001"]
    assert [s["pair_attempt"] for s in scheduled[::2]] == list(range(5))


def _suite_payload(openings=None):
    payload = {
        "suite_id": "humansl-opening-suite-v1",
        "seed": 20260721,
        "board_size": 19,
        "openings": openings or [{"id": f"o{i:03d}", "moves": [i, 19 + i]} for i in range(1, 21)],
    }
    payload["checksum"] = selfplay.opening_suite_checksum(payload)
    return payload


def test_shipped_opening_suite_has_documented_identity_checksum_and_legal_unique_prefixes():
    suite = selfplay.load_opening_suite(selfplay.OPENING_SUITE_PATH)

    assert suite["suite_id"] == "humansl-opening-suite-v1"
    assert suite["seed"] == 20260721
    assert suite["board_size"] == 19
    assert len(suite["openings"]) >= 20
    assert len({tuple(opening["moves"]) for opening in suite["openings"]}) == len(suite["openings"])
    assert suite["checksum"] == selfplay.opening_suite_checksum(suite)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda p: p.update(suite_id="wrong"), "suite ID"),
        (lambda p: p.update(seed=None), "seed"),
        (lambda p: p["openings"][0]["moves"].__setitem__(0, 361), "bounds"),
        (lambda p: p["openings"][0].update(moves=[0, 0]), "legal"),
        (lambda p: p["openings"][1].update(moves=list(p["openings"][0]["moves"])), "unique"),
        (lambda p: p.update(checksum="0" * 64), "checksum"),
    ],
)
def test_opening_suite_loader_rejects_identity_bounds_legality_uniqueness_and_checksum(tmp_path, mutation, match):
    payload = _suite_payload()
    mutation(payload)
    if match != "checksum":
        payload["checksum"] = selfplay.opening_suite_checksum(payload)
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match=match):
        selfplay.load_opening_suite(path)


def test_cli_target_is_complete_conclusive_pairs_with_separate_attempt_guard():
    args = selfplay.build_arg_parser().parse_args(
        [
            "--matchups",
            "rank_9d@80:rank_9d@40:20",
            "--phase",
            "confirm",
            "--max-pair-attempts",
            "30",
        ]
    )

    assert selfplay.parse_matchups(args.matchups) == [("rank_9d@80", "rank_9d@40", 20)]
    assert args.phase == "confirm"
    assert args.max_pair_attempts == 30
    assert "pairs" in selfplay.build_arg_parser().format_help()


@pytest.mark.asyncio
async def test_screen_run_stops_at_exactly_ten_complete_pairs(tmp_path, monkeypatch):
    calls = []

    async def fake_game(*, our_color, initial_history, **_kwargs):
        calls.append((our_color, list(initial_history)))
        return selfplay.GameOutcome(our_color, "our_win", True, len(initial_history), 1.0, True, "move_cap")

    monkeypatch.setattr(selfplay, "play_one_game", fake_game)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(500))) as client:
        summary = await selfplay.run_matchup(
            "rank_9d@40",
            "b28@20",
            10,
            client=client,
            base_url="http://engine",
            wrn=0.04,
            out_dir=tmp_path,
            capabilities=_health_snapshot(),
            phase="screen",
            max_pair_attempts=25,
        )

    assert summary["complete_pairs"] == 10
    assert summary["decision_games"] == 20
    assert summary["pair_attempts"] == 10
    assert len(calls) == 20
    assert [color for color, _opening in calls] == ["B", "W"] * 10


@pytest.mark.asyncio
async def test_inconclusive_pair_forces_a_fresh_pair_attempt_and_max_attempts_terminates(tmp_path, monkeypatch):
    calls = 0

    async def fake_game(*, our_color, initial_history, **_kwargs):
        nonlocal calls
        calls += 1
        conclusive = calls not in {2, 3, 4}
        result = "our_win" if conclusive else "inconclusive_unsettled"
        return selfplay.GameOutcome(
            our_color,
            result,
            conclusive,
            len(initial_history),
            1.0,
            conclusive,
            "move_cap",
        )

    monkeypatch.setattr(selfplay, "play_one_game", fake_game)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(500))) as client:
        summary = await selfplay.run_matchup(
            "rank_9d@40",
            "b28@20",
            10,
            client=client,
            base_url="http://engine",
            wrn=0.04,
            out_dir=tmp_path,
            capabilities=_health_snapshot(),
            phase="screen",
            max_pair_attempts=2,
        )

    assert calls == 4
    assert summary["complete_pairs"] == 0
    assert summary["decision_games"] == 0
    assert summary["inconclusive_pairs"] == 2
    assert summary["max_attempts_reached"] is True
    assert summary["a_elo_ci95"] == [None, None]
    assert summary["classification"] == "insufficient_pairs"
    encoded = json.dumps(summary, allow_nan=False)
    assert json.loads(encoded, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))) == summary


@pytest.mark.asyncio
async def test_confirm_guard_exhaustion_never_emits_strength_classification(tmp_path, monkeypatch):
    async def fake_game(*, our_color, initial_history, **_kwargs):
        return selfplay.GameOutcome(our_color, "our_win", True, len(initial_history), 1.0, True, "move_cap")

    monkeypatch.setattr(selfplay, "play_one_game", fake_game)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(500))) as client:
        summary = await selfplay.run_matchup(
            "rank_9d@40",
            "b28@20",
            30,
            client=client,
            base_url="http://engine",
            wrn=0.04,
            out_dir=tmp_path,
            capabilities=_health_snapshot(),
            phase="confirm",
            max_pair_attempts=20,
        )

    assert summary["complete_pairs"] == 20
    assert summary["target_complete_pairs"] == 30
    assert summary["max_attempts_reached"] is True
    assert summary["classification"] == "insufficient_pairs"


@pytest.mark.asyncio
async def test_interrupted_pair_resume_runs_only_missing_color_then_continues(tmp_path, monkeypatch):
    calls = []

    async def fake_game(*, our_color, initial_history, **_kwargs):
        calls.append(our_color)
        return selfplay.GameOutcome(our_color, "our_win", True, len(initial_history), 1.0, True, "move_cap")

    monkeypatch.setattr(selfplay, "play_one_game", fake_game)
    kwargs = dict(
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(500))),
        base_url="http://engine",
        wrn=0.04,
        out_dir=tmp_path,
        capabilities=_health_snapshot(),
        phase="screen",
        max_pair_attempts=20,
    )
    try:
        await selfplay.run_matchup("rank_9d@40", "b28@20", 10, **kwargs)
        checkpoint = next(tmp_path.glob("*.jsonl"))
        lines = checkpoint.read_text().splitlines()
        checkpoint.write_text("\n".join(lines[:2]) + "\n")
        calls.clear()
        await selfplay.run_matchup("rank_9d@40", "b28@20", 10, **kwargs)
    finally:
        await kwargs["client"].aclose()

    assert calls[0] == "W"
    assert len(calls) == 19
