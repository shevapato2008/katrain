import hashlib
import importlib
import json
import stat
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import httpx
import pytest


CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
pilot = importlib.import_module("temperature_pilot")
selfplay = importlib.import_module("run_selfplay")


def _valid_policy(selected_index=0):
    policy = [0.0] * 362
    policy[selected_index] = 1.0
    return policy


def _health_snapshot():
    return selfplay.adapters.retain_health_snapshot(
        {
            "capability_schema": 1,
            "katago_version": "KataGo v1.16.3",
            "default_model": "b28",
            "models": {
                "b28": {
                    "running": True,
                    "model_path": "/models/b28.bin.gz",
                    "model_sha256": "b28-sha",
                    "model_sha256_verified": True,
                    "has_human_model": True,
                    "human_model_path": "/models/human.bin.gz",
                    "human_model_sha256": "human-sha",
                    "human_model_sha256_verified": True,
                }
            },
        }
    )


def _attestation():
    return {
        "selected_model": "b28",
        "model_path": "/models/b28.bin.gz",
        "model_sha256": "b28-sha",
        "human_model_path": "/models/human.bin.gz",
        "human_model_sha256": "human-sha",
        "katago_version": "KataGo v1.16.3",
    }


def test_temperature_evidence_identity_is_canonical_and_complete():
    identity = pilot.temperature_player_identity("rank_1d", "002.000")

    assert identity.canonical_label == "rank_1d@1t2"
    assert identity.profile == "rank_1d"
    assert identity.selection == "temperature_weighted"
    assert identity.selection_algorithm == "temperature-inverse-cdf-v1"
    assert identity.temperature == "2"


@pytest.mark.asyncio
async def test_temperature_player_move_uses_audited_draw_and_appends_valid_trace(monkeypatch):
    label, rung, selection = selfplay.make_player("rank_1d@1t2.0")
    matchup_id = "rank_1d@1t1__vs__rank_1d@1t2"
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": matchup_id,
        "pair_attempt": 3,
        "color_index": 1,
        "player": "B",
    }
    history = [0, 1, 2]
    policy = [0.0] * 362
    policy[0] = 0.25
    policy[342] = 0.75
    expected_draw = pilot.derive_draw(
        manifest_sha256=context["manifest_sha256"],
        canonical_matchup_id=matchup_id,
        pair_attempt=3,
        color_index=1,
        ply=len(history),
        player="B",
    )
    expected_pick = selfplay.pick_temperature_policy(policy, (19, 19), 2.0, expected_draw)
    assert expected_draw == 9451441004411297038
    assert expected_pick == ((0, 0), 342)
    calls = []
    original_pick = selfplay.pick_temperature_policy

    def recording_pick(*args):
        calls.append(args)
        return original_pick(*args)

    monkeypatch.setattr(selfplay, "pick_temperature_policy", recording_pick)

    def handler(request):
        body = json.loads(request.content)
        assert label == "rank_1d@1t2"
        assert body["maxVisits"] == 1
        assert body["overrideSettings"].get("model") is None
        assert "human_policy_temperature" not in body["overrideSettings"]
        assert "rootPolicyTemperature" not in body["overrideSettings"]
        return httpx.Response(200, json={"humanPolicy": policy, "_wrapper": _attestation()})

    traces = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        move = await selfplay._player_move(
            client,
            "http://engine",
            history,
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            temperature_context=context,
            sampling_trace=traces,
        )

    assert calls == [(policy, (19, 19), 2.0, expected_draw)]
    assert move == 342
    assert traces == [
        pilot.build_sampling_trace(
            manifest_sha256=context["manifest_sha256"],
            canonical_matchup_id=matchup_id,
            pair_attempt=3,
            color_index=1,
            ply=len(history),
            player="B",
            temperature="2",
            draw_u64=expected_draw,
            selected_index=expected_pick[1],
            policy=policy,
        )
    ]
    assert pilot.validate_sampling_trace(
        traces[0], **{k: context[k] for k in context if k not in ("protocol_version", "player")}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context_mutation",
    [
        lambda context: context.pop("protocol_version"),
        lambda context: context.update(protocol_version="wrong"),
        lambda context: context.pop("manifest_sha256"),
        lambda context: context.update(canonical_matchup_id="not-frozen"),
        lambda context: context.update(pair_attempt=-1),
        lambda context: context.update(color_index=2),
        lambda context: context.update(player="C"),
    ],
)
async def test_temperature_player_move_fails_closed_for_incomplete_or_invalid_context(context_mutation):
    _, rung, selection = selfplay.make_player("rank_1d@1t1")
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
        "player": "A",
    }
    context_mutation(context)

    def handler(_request):
        return httpx.Response(200, json={"humanPolicy": _valid_policy(), "_wrapper": _attestation()})

    traces = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        move = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            temperature_context=context,
            sampling_trace=traces,
        )

    assert move == "unavailable"
    assert traces == []


@pytest.mark.asyncio
async def test_temperature_player_move_fails_closed_for_malformed_policy():
    _, rung, selection = selfplay.make_player("rank_1d@1t1")
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
        "player": "A",
    }

    def handler(_request):
        return httpx.Response(200, json={"humanPolicy": [1.0], "_wrapper": _attestation()})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        move = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            temperature_context=context,
            sampling_trace=[],
        )

    assert move == "unavailable"


def test_draw_has_frozen_canonical_json_sha256_and_u64_vector():
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 3,
        "color_index": 1,
    }
    encoded, digest, draw = pilot.derive_draw(**context, ply=27, player="A", include_audit=True)
    assert encoded.decode() == (
        '["humansl-temperature-pilot-v1","abababababababababababababababababababababababababababababababab",'
        '"rank_1d@1t1__vs__rank_1d@1t2",3,1,27,"A"]'
    )
    assert digest == "088d856d73d010b92d926e94e9a1a6e6bb0f7192e0410807ff56a99e1b449b9e"
    assert draw == 616295429160571065


def test_draw_rejects_matchup_ids_outside_the_exact_frozen_nine():
    with pytest.raises(ValueError, match="frozen matchup"):
        pilot.derive_draw(
            manifest_sha256="ab" * 32,
            canonical_matchup_id="rank_2d@1t1__vs__rank_2d@1t2",
            pair_attempt=0,
            color_index=0,
            ply=8,
            player="A",
        )


def test_policy_digest_has_frozen_count_and_binary64_vector_with_final_pass_entry():
    policy = [0.0] * 361 + [0.25]
    assert pilot.policy_digest(policy) == "ba08745956e76568164c75022ed57da172c75366e0607eb4a73abeddd9f0a69b"


@pytest.mark.parametrize(("index", "gtp"), [(0, "A19"), (18, "T19"), (342, "A1"), (360, "T1"), (361, "pass")])
def test_trace_uses_exact_policy_index_gtp_mapping(index, gtp):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 3,
        "color_index": 1,
    }
    policy = _valid_policy(index)
    trace = pilot.build_sampling_trace(
        **context,
        ply=27,
        player="A",
        temperature="1",
        draw_u64=pilot.derive_draw(**context, ply=27, player="A"),
        selected_index=index,
        policy=policy,
    )
    assert trace == {
        "ply": 27,
        "player": "A",
        "temperature": "1",
        "draw_u64": 616295429160571065,
        "selected_index": index,
        "selected_move": gtp,
        "policy_sha256": pilot.policy_digest(policy),
    }
    assert pilot.validate_sampling_trace(trace, **context) == trace


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda row: row.pop("ply"), "shape"),
        (lambda row: row.update(draw_u64=0), "draw"),
        (lambda row: row.update(selected_index=362), "index"),
        (lambda row: row.update(selected_move="a19"), "move"),
        (lambda row: row.update(policy_sha256="xyz"), "digest"),
    ],
)
def test_trace_validation_fails_closed_on_shape_draw_bounds_mapping_and_digest(mutation, match):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 3,
        "color_index": 1,
    }
    trace = pilot.build_sampling_trace(
        **context,
        ply=27,
        player="A",
        temperature="1",
        draw_u64=pilot.derive_draw(**context, ply=27, player="A"),
        selected_index=0,
        policy=_valid_policy(),
    )
    mutation(trace)
    with pytest.raises(ValueError, match=match):
        pilot.validate_sampling_trace(trace, **context)


@pytest.mark.parametrize("temperature", ["1.0", "01", "0.04", "10.01"])
def test_trace_rejects_noncanonical_or_out_of_range_temperature(temperature):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
    }
    with pytest.raises(ValueError, match="temperature"):
        pilot.build_sampling_trace(
            **context,
            ply=8,
            player="A",
            temperature=temperature,
            draw_u64=pilot.derive_draw(**context, ply=8, player="A"),
            selected_index=0,
            policy=_valid_policy(),
        )


@pytest.mark.parametrize(
    ("matchup_id", "player", "temperature"),
    [
        ("rank_1d@1t1__vs__rank_1d@1t2", "A", "2"),
        ("rank_1d@1t1__vs__rank_1d@1t2", "B", "1"),
        ("rank_1d@1s__vs__rank_1d@1t0.4", "A", "0.4"),
    ],
)
def test_trace_temperature_must_match_the_temperature_player_on_that_side(matchup_id, player, temperature):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": matchup_id,
        "pair_attempt": 0,
        "color_index": 0,
    }
    with pytest.raises(ValueError, match="temperature player"):
        pilot.build_sampling_trace(
            **context,
            ply=8,
            player=player,
            temperature=temperature,
            draw_u64=pilot.derive_draw(**context, ply=8, player=player),
            selected_index=0,
            policy=_valid_policy(),
        )


def test_trace_validation_rechecks_the_temperature_side_binding():
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
    }
    trace = pilot.build_sampling_trace(
        **context,
        ply=8,
        player="A",
        temperature="1",
        draw_u64=pilot.derive_draw(**context, ply=8, player="A"),
        selected_index=0,
        policy=_valid_policy(),
    )
    trace["temperature"] = "2"
    with pytest.raises(ValueError, match="temperature player"):
        pilot.validate_sampling_trace(trace, **context)


@pytest.mark.parametrize(
    ("policy", "selected_index", "match"),
    [
        ([], 0, "362"),
        ([1.0] * 361, 0, "362"),
        ([1.0] + [float("nan")] + [0.0] * 360, 0, "finite"),
        ([1.0] + [float("inf")] + [0.0] * 360, 0, "finite"),
        ([0.0] * 362, 0, "positive"),
        ([0.0, 1.0] + [0.0] * 360, 0, "selected.*positive"),
    ],
)
def test_trace_builder_rejects_malformed_or_unusable_policy(policy, selected_index, match):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
    }
    with pytest.raises(ValueError, match=match):
        pilot.build_sampling_trace(
            **context,
            ply=8,
            player="A",
            temperature="1",
            draw_u64=pilot.derive_draw(**context, ply=8, player="A"),
            selected_index=selected_index,
            policy=policy,
        )


def test_protocol_helpers_do_not_import_selfplay():
    script = (
        "import importlib,sys; "
        f"sys.path.insert(0,{str(CALIBRATION_DIR)!r}); "
        "importlib.import_module('temperature_pilot'); "
        "print('run_selfplay' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", script], check=True, text=True, capture_output=True)
    assert result.stdout.strip() == "False"


def test_ordered_matchups_and_evidence_identities_are_frozen():
    expected = []
    for profile in ("rank_1d", "rank_5d", "rank_9d"):
        expected.extend(
            [
                f"{profile}@1t1__vs__{profile}@1t2",
                f"{profile}@1t0.4__vs__{profile}@1t1",
                f"{profile}@1s__vs__{profile}@1t0.4",
            ]
        )
    assert [matchup.matchup_id for matchup in pilot.MATCHUPS] == expected
    assert all(
        (m.phase, m.target_complete_pairs, m.max_pair_attempts, m.expected_stronger) == ("screen", 10, 20, "A")
        for m in pilot.MATCHUPS
    )
    first = pilot.MATCHUPS[0]
    assert (first.a.canonical_label, first.a.profile, first.a.selection_algorithm, first.a.temperature) == (
        "rank_1d@1t1",
        "rank_1d",
        "temperature-inverse-cdf-v1",
        "1",
    )
    assert first.b.temperature == "2"
    assert (
        pilot.MATCHUPS[2].a.canonical_label,
        pilot.MATCHUPS[2].a.profile,
        pilot.MATCHUPS[2].a.selection_algorithm,
        pilot.MATCHUPS[2].a.temperature,
    ) == ("rank_1d@1s", "rank_1d", "policy-argmax-v1", None)


def test_canonical_matchup_protocol_is_deeply_immutable():
    with pytest.raises(FrozenInstanceError):
        pilot.MATCHUPS[0].matchup_id = "mutated"
    with pytest.raises(FrozenInstanceError):
        pilot.MATCHUPS[0].a.canonical_label = "mutated"


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True).stdout.strip()


def _fixture_repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for relative in pilot.RUNTIME_SOURCE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n")
    suite_path = root / pilot.OPENING_SUITE_PATH
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite = json.loads((CALIBRATION_DIR / "opening_suite_v1.json").read_text(encoding="utf-8"))
    suite_path.write_text(json.dumps(suite))
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Protocol Test")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "implementation")
    base = _git(root, "rev-parse", "HEAD")
    (root / "README").write_text("descendant\n")
    _git(root, "add", "README")
    _git(root, "commit", "-qm", "manifest parent")
    return root, base, suite


def test_manifest_binds_exact_sources_ancestry_opening_allocation_and_self_digest(tmp_path):
    root, base, suite = _fixture_repository(tmp_path)
    manifest = pilot.build_manifest(root, base)
    assert manifest["schema_version"] == 1
    assert manifest["protocol"] == "humansl-temperature-pilot-v1"
    assert manifest["implementation_base_revision"] == base
    assert tuple(manifest["runtime_sources"]) == pilot.RUNTIME_SOURCE_PATHS
    assert manifest["opening_suite"] == {
        "path": pilot.OPENING_SUITE_PATH,
        "file_sha256": hashlib.sha256((root / pilot.OPENING_SUITE_PATH).read_bytes()).hexdigest(),
        "checksum": suite["checksum"],
        "allocations": [{"attempt": i, **suite["openings"][i]} for i in range(20)],
        "cycle": False,
    }
    assert manifest["versions"] == {
        "selection": "temperature-inverse-cdf-v1",
        "draw": "temperature-draw-sha256-u64-v1",
        "referee": "b28@200",
        "adjudication": "b28-settled-score-v1",
        "symmetry": {"mode": "katago-default", "requested_symmetry": None},
        "rules": "chinese",
        "komi": "7.5",
        "move_cap": 400,
        "checkpoint_schema": 3,
    }
    assert manifest["manifest_sha256"] == pilot.canonical_digest(manifest, exclude="manifest_sha256")
    pilot.validate_manifest(manifest, root)


def test_manifest_rejects_altered_suite_even_with_a_recalculated_internal_checksum(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    suite_path = root / pilot.OPENING_SUITE_PATH
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["openings"][0]["moves"][0] += 1
    suite["checksum"] = pilot.canonical_digest(suite, exclude="checksum")
    suite_path.write_text(json.dumps(suite))
    with pytest.raises(ValueError, match="frozen opening suite"):
        pilot.build_manifest(root, base)


def test_manifest_matchups_do_not_alias_mutable_global_protocol_state(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    original_label = pilot.MATCHUPS[0].a.canonical_label
    first = pilot.build_manifest(root, base)
    first["matchups"][0]["a"]["canonical_label"] = "mutated"
    assert pilot.MATCHUPS[0].a.canonical_label == original_label
    second = pilot.build_manifest(root, base)
    assert second["matchups"][0]["a"]["canonical_label"] == original_label
    assert pilot.classify_pilot(_results([11] * 9))["status"] == "pass"


def test_manifest_creation_is_exclusive_and_validation_rejects_bound_file_drift(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    path = root / "manifest.json"
    created = pilot.create_manifest(path, root, base)
    assert json.loads(path.read_text(encoding="utf-8")) == created
    with pytest.raises(FileExistsError):
        pilot.create_manifest(path, root, base)
    (root / pilot.RUNTIME_SOURCE_PATHS[0]).write_text("drift\n")
    with pytest.raises(ValueError, match="source drift"):
        pilot.validate_manifest_file(path, root)


def test_manifest_validation_rejects_nonancestor_base_and_bad_self_digest(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    manifest = pilot.build_manifest(root, base)
    manifest["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="self-digest"):
        pilot.validate_manifest(manifest, root)

    unrelated = _git(root, "commit-tree", _git(root, "write-tree"), "-m", "unrelated")
    with pytest.raises(ValueError, match="not an ancestor"):
        pilot.build_manifest(root, unrelated)


def test_manifest_rejects_staged_only_bound_source_drift(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    relative = pilot.RUNTIME_SOURCE_PATHS[0]
    path = root / relative
    original = path.read_text()
    path.write_text("staged drift\n")
    _git(root, "add", relative)
    path.write_text(original)
    with pytest.raises(ValueError, match="source drift"):
        pilot.build_manifest(root, base)


def test_manifest_rejects_bound_source_mode_change_and_deletion(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    mode_path = root / pilot.RUNTIME_SOURCE_PATHS[0]
    mode_path.chmod(mode_path.stat().st_mode | stat.S_IXUSR)
    with pytest.raises(ValueError, match="source drift"):
        pilot.build_manifest(root, base)

    deletion_root = tmp_path / "deletion"
    deletion_root.mkdir()
    root, base, _ = _fixture_repository(deletion_root)
    (root / pilot.RUNTIME_SOURCE_PATHS[0]).unlink()
    with pytest.raises(ValueError, match="source.*missing"):
        pilot.build_manifest(root, base)


def test_manifest_rejects_committed_descendant_bound_source_drift(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    relative = pilot.RUNTIME_SOURCE_PATHS[0]
    (root / relative).write_text("committed descendant drift\n")
    _git(root, "add", relative)
    _git(root, "commit", "-qm", "change bound source")
    with pytest.raises(ValueError, match="source drift"):
        pilot.build_manifest(root, base)


def test_protocol_json_reads_are_explicit_utf8(tmp_path, monkeypatch):
    root, base, _ = _fixture_repository(tmp_path)
    manifest_path = root / "manifest.json"
    pilot.create_manifest(manifest_path, root, base)
    original_read_text = Path.read_text
    encodings = []

    def recording_read_text(path, *args, **kwargs):
        if path.suffix == ".json":
            encodings.append(kwargs.get("encoding"))
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    pilot.validate_manifest_file(manifest_path, root)
    assert encodings and set(encodings) == {"utf-8"}


@pytest.mark.parametrize(
    ("wins", "expected"),
    [
        (15, "persuasive_direction"),
        (11, "direction_supported"),
        (10, "point_tie"),
        (9, "point_inversion"),
        (5, "persuasive_inversion"),
    ],
)
def test_per_match_classification_covers_every_category(wins, expected):
    assert pilot.classify_matchup(wins, complete_pairs=10, identity_valid=True)["classification"] == expected


def _results(wins):
    return [
        {"matchup_id": matchup.matchup_id, "a_wins": score, "complete_pairs": 10, "identity_valid": True}
        for matchup, score in zip(pilot.MATCHUPS, wins)
    ]


def test_overall_pass_accepts_exactly_eight_direction_wins_with_all_profile_totals_above_30():
    summary = pilot.classify_pilot(_results([11, 11, 11, 11, 11, 11, 11, 11, 10]))
    assert summary["status"] == "pass"
    assert summary["direction_matchups"] == 8
    assert summary["profile_a_wins"] == {"rank_1d": 33, "rank_5d": 33, "rank_9d": 32}


@pytest.mark.parametrize(
    ("wins", "reason"),
    [
        ([11, 11, 11, 11, 11, 11, 11, 10, 10], "fewer_than_8_direction_matchups"),
        ([11, 11, 8, 11, 11, 11, 11, 11, 11], "profile_aggregate_not_above_30"),
        ([5, 15, 15, 15, 15, 15, 15, 15, 15], "persuasive_inversion"),
    ],
)
def test_overall_failure_branches(wins, reason):
    summary = pilot.classify_pilot(_results(wins))
    assert summary["status"] == "fail"
    assert reason in summary["reasons"]


@pytest.mark.parametrize("field,value", [("complete_pairs", 9), ("complete_pairs", 11), ("identity_valid", False)])
def test_overall_is_incomplete_for_nonexact_pair_count_or_invalid_identity(field, value):
    results = _results([11] * 9)
    results[0][field] = value
    summary = pilot.classify_pilot(results)
    assert summary["status"] == "incomplete"


def test_overall_is_incomplete_for_missing_or_noncanonical_evidence():
    assert pilot.classify_pilot(_results([11] * 8))["status"] == "incomplete"
    changed = _results([11] * 9)
    changed[0]["matchup_id"] = "swapped"
    assert pilot.classify_pilot(changed)["status"] == "incomplete"
