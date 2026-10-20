import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

from katrain.web.kifu.name_candidates import canonical_sha256


def _manifest():
    sgf = "(;FF[4]SZ[19]PB[Black]PW[White]EV[Match]DT[2026-02-01];B[aa])"
    return {
        "format": "kifu-incremental-manifest-v1",
        "publication_key": "local-1",
        "games": [
            {
                "source_key": "19x19",
                "source_item_id": "42",
                "origin_path": "data/kifu-album/19x19/42.sgf",
                "raw_sha256": sha256(sgf.encode()).hexdigest(),
                "sgf_content": sgf,
                "sgf_sha256": sha256(sgf.encode()).hexdigest(),
                "metadata": {
                    "player_black": "Black",
                    "player_white": "White",
                    "event": "Match",
                    "date_played": "2026-02-01",
                },
                "identities": {"black": None, "white": None, "event": None},
            }
        ],
        "decisions": [],
    }


def _qualified_target(request):
    return {
        "status": "checked",
        "request_sha256": canonical_sha256(request),
        "results": ["qualified"] * len(request["instructions"]),
    }


def test_receive_identity_check_is_read_only_and_publish_envelope_still_works(monkeypatch, capsys):
    from io import StringIO
    from katrain.kifu_ingest import orchestration

    request = {
        "operation": "check-identities",
        "game_count": 1,
        "instructions": [{"kind": "player", "raw": "Raw", "canonical_name": "Portable", "name_decision": False}],
    }
    engine = object()
    monkeypatch.setattr(orchestration, "_engine", lambda: engine)
    calls = []

    def check(db, value):
        assert db is engine and value == request
        calls.append("read")
        return _qualified_target(value)

    monkeypatch.setattr(orchestration, "check_identity_instructions", check)
    monkeypatch.setattr(orchestration, "publish_manifest", lambda *a, **k: pytest.fail("read operation published"))
    monkeypatch.setattr(orchestration.sys, "stdin", StringIO(json.dumps(request)))
    assert orchestration.main(["receive"]) == 0
    assert json.loads(capsys.readouterr().out) == _qualified_target(request)
    assert calls == ["read"]
    manifest = _manifest()
    digest = canonical_sha256(manifest)
    payload = {
        "manifest": manifest,
        "manifest_sha256": digest,
        "test_verification": {
            "status": "verified",
            "manifest_sha256": digest,
            "games": 1,
            "checks": [{"album_id": 7, "lang": lang} for lang in ("cn", "tw", "jp", "ko", "en")],
        },
    }
    monkeypatch.setattr(orchestration.sys, "stdin", StringIO(json.dumps(payload)))
    monkeypatch.setattr(
        orchestration, "publish_manifest", lambda db, value, **kw: calls.append("publish") or {"games": []}
    )
    assert orchestration.main(["receive"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "applied",
        "manifest_sha256": digest,
        "receipt": {"games": []},
    }
    assert calls == ["read", "publish"]


def test_receive_bad_identity_schema_never_opens_database(monkeypatch, capsys):
    from io import StringIO
    from katrain.kifu_ingest import orchestration

    monkeypatch.setattr(orchestration, "_engine", lambda: pytest.fail("invalid readonly request opened database"))
    monkeypatch.setattr(
        orchestration.sys,
        "stdin",
        StringIO(
            json.dumps({"operation": "check-identities", "game_count": True, "instructions": [], "path": "/private"})
        ),
    )
    assert orchestration.main(["receive"]) == 2
    assert json.loads(capsys.readouterr().out) == {"status": "error", "error": "identity check unavailable"}


def test_run_once_dry_run_validates_without_engine_or_publisher(tmp_path, monkeypatch, capsys):
    from katrain.kifu_ingest import orchestration

    manifest = _manifest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(orchestration, "_engine", lambda: (_ for _ in ()).throw(AssertionError("engine opened")))
    monkeypatch.setattr(
        orchestration, "publish_manifest", lambda *a, **k: (_ for _ in ()).throw(AssertionError("published"))
    )
    assert orchestration.main(["run-once", "--manifest", str(path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["manifest_sha256"] == canonical_sha256(manifest)


def test_absolute_cli_script_runs_from_other_cwd_without_pythonpath(tmp_path, monkeypatch):
    manifest = _manifest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "kifu_incremental.py"
    monkeypatch.delenv("PYTHONPATH", raising=False)
    result = subprocess.run(
        [sys.executable, "-I", str(script), "run-once", "--manifest", str(path), "--dry-run"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "validated"


def test_run_once_requires_apply_for_publication(tmp_path, monkeypatch, capsys):
    from katrain.kifu_ingest import orchestration

    manifest = _manifest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    calls = []
    monkeypatch.setattr(orchestration, "_engine", lambda: object())
    monkeypatch.setattr(
        orchestration, "publish_manifest", lambda engine, doc, **kw: calls.append((doc, kw)) or {"status": "applied"}
    )
    assert orchestration.main(["run-once", "--manifest", str(path), "--apply"]) == 0
    assert len(calls) == 1
    assert calls[0][1]["expected_manifest_sha256"] == canonical_sha256(manifest)
    assert json.loads(capsys.readouterr().out)["receipt"]["status"] == "applied"


def test_receive_rejects_hash_mismatch_before_engine(monkeypatch, capsys):
    from io import StringIO
    from katrain.kifu_ingest import orchestration

    monkeypatch.setattr(
        orchestration.sys, "stdin", StringIO(json.dumps({"manifest": _manifest(), "manifest_sha256": "0" * 64}))
    )
    monkeypatch.setattr(orchestration, "_engine", lambda: (_ for _ in ()).throw(AssertionError("engine opened")))
    assert orchestration.main(["receive"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_receive_requires_test_verification_before_engine(monkeypatch, capsys):
    from io import StringIO
    from katrain.kifu_ingest import orchestration

    manifest = _manifest()
    monkeypatch.setattr(
        orchestration.sys,
        "stdin",
        StringIO(json.dumps({"manifest": manifest, "manifest_sha256": canonical_sha256(manifest)})),
    )
    monkeypatch.setattr(orchestration, "_engine", lambda: (_ for _ in ()).throw(AssertionError("engine opened")))
    assert orchestration.main(["receive"]) == 2
    assert "verification" in json.loads(capsys.readouterr().out)["error"]


def test_receive_allows_only_numeric_19x19_sources(monkeypatch, capsys):
    from io import StringIO
    from katrain.kifu_ingest import orchestration

    manifest = _manifest()
    manifest["games"][0]["source_key"] = "other"
    digest = canonical_sha256(manifest)
    monkeypatch.setattr(
        orchestration.sys,
        "stdin",
        StringIO(
            json.dumps(
                {
                    "manifest": manifest,
                    "manifest_sha256": digest,
                    "test_verification": {"status": "verified", "manifest_sha256": digest},
                }
            )
        ),
    )
    monkeypatch.setattr(orchestration, "_engine", lambda: (_ for _ in ()).throw(AssertionError("engine opened")))
    assert orchestration.main(["receive"]) == 2
    assert "19x19" in json.loads(capsys.readouterr().out)["error"]


def test_receive_rejects_incomplete_five_language_verification(monkeypatch, capsys):
    from io import StringIO
    from katrain.kifu_ingest import orchestration

    manifest = _manifest()
    digest = canonical_sha256(manifest)
    monkeypatch.setattr(
        orchestration.sys,
        "stdin",
        StringIO(
            json.dumps(
                {
                    "manifest": manifest,
                    "manifest_sha256": digest,
                    "test_verification": {
                        "status": "verified",
                        "manifest_sha256": digest,
                        "games": 1,
                        "checks": [{"album_id": 7, "lang": "cn"}],
                    },
                }
            )
        ),
    )
    monkeypatch.setattr(orchestration, "_engine", lambda: (_ for _ in ()).throw(AssertionError("engine opened")))
    assert orchestration.main(["receive"]) == 2
    assert "five-language" in json.loads(capsys.readouterr().out)["error"]


@pytest.mark.asyncio
async def test_staged_game_with_qualified_names_prepares_without_paid_api(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration

    sgf = "(;FF[4]SZ[19]PB[Black]PW[White]EV[Match]DT[2026-02-01];B[aa])"
    path = tmp_path / "42.sgf"
    path.write_text(sgf, encoding="utf-8")

    def lookup(engine, *, player_values, event_values):
        return {
            "player": {raw: {"status": "qualified", "canonical_name": raw} for raw in player_values},
            "event": {raw: {"status": "qualified", "canonical_name": raw} for raw in event_values},
        }

    monkeypatch.setattr(orchestration, "lookup_qualified_identities", lookup)
    manifest = await orchestration.prepare_staged_game(
        {"external_id": "42", "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()},
        engine=object(),
        client=None,
        names=None,
        check_identities=_qualified_target,
    )
    assert manifest["games"][0]["identities"] == {
        "black": {"canonical_name": "Black"},
        "white": {"canonical_name": "White"},
        "event": {"canonical_name": "Match"},
    }
    assert manifest["decisions"] == []


@pytest.mark.asyncio
async def test_staged_game_needing_a_name_exits_before_network_when_key_missing(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.names import NeedsCredentials

    sgf = "(;PB[Black]PW[White]EV[Match];B[aa])"
    path = tmp_path / "42.sgf"
    path.write_text(sgf, encoding="utf-8")
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {
            "player": {"Black": {"status": "unresolved"}, "White": {"status": "qualified", "canonical_name": "White"}},
            "event": {"Match": {"status": "qualified", "canonical_name": "Match"}},
        },
    )
    monkeypatch.setattr(orchestration, "qualified_raw_player_templates", lambda *a, **k: {"templates": {}})
    monkeypatch.setattr(orchestration, "wiki_sources", lambda *a, **k: pytest.fail("network called"))

    class Names:
        key = ""

    with pytest.raises(NeedsCredentials):
        await orchestration.prepare_staged_game(
            {"external_id": "42", "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()},
            engine=object(),
            client=object(),
            names=Names(),
            check_identities=_qualified_target,
        )


@pytest.mark.asyncio
async def test_staged_game_reuses_qualified_literal_event_without_model(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration

    sgf = "(;PB[Black]PW[White]EV[Match];B[aa])"
    path = tmp_path / "42.sgf"
    path.write_text(sgf, encoding="utf-8")
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {
            "player": {raw: {"status": "qualified", "canonical_name": raw} for raw in ("Black", "White")},
            "event": {"Match": {"status": "unresolved"}},
        },
    )
    monkeypatch.setattr(
        orchestration,
        "qualified_raw_event_templates",
        lambda *a, **k: {
            "templates": {"Match": {"displays": {lang: "Match" for lang in ("cn", "tw", "jp", "ko", "en")}}}
        },
    )
    manifest = await orchestration.prepare_staged_game(
        {"external_id": "42", "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()},
        engine=object(),
        client=None,
        names=None,
        check_identities=_qualified_target,
    )
    assert manifest["decisions"] == []
    assert manifest["games"][0]["identities"]["event"] is None


def _reviewed_name_decision(kind, key, members):
    from katrain.kifu_ingest.catalog import review_content_sha256

    decision = {
        "kind": kind,
        "key": key,
        "displays": {lang: key for lang in ("cn", "tw", "jp", "ko", "en")},
        "methods": {lang: "retain_original" for lang in ("cn", "tw", "jp", "ko", "en")},
        "original_language": "en",
        "sources": [],
        "source_items": members,
        "producer": {"id": "p", "model": "m", "request_id": f"p-{key}", "at": "2026-10-01T00:00:00Z"},
    }
    decision["review"] = {
        "id": "r",
        "model": "m",
        "request_id": f"r-{key}",
        "at": "2026-10-01T00:00:01Z",
        "decision": "approve",
        "content_sha256": review_content_sha256(decision),
    }
    return decision


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_check_passed", [False, True])
@pytest.mark.parametrize(
    "local_status,target_status",
    [
        ("qualified", "unresolved"),
        ("qualified", "missing_qualified_five_languages"),
        ("missing_qualified_five_languages", "conflict"),
        ("missing_qualified_five_languages", "canonical_decision_key_mismatch"),
    ],
)
async def test_target_identity_failure_isolates_only_linked_games_before_any_model(
    tmp_path, monkeypatch, local_status, target_status, initial_check_passed
):
    from katrain.kifu_ingest import orchestration

    items = []
    for source_id, black, white in (("42", "Bad", "Shared"), ("43", "Shared", "White")):
        sgf = f"(;PB[{black}]PW[{white}]EV[NewMatch];B[aa])"
        path = tmp_path / f"{source_id}.sgf"
        path.write_text(sgf)
        items.append(
            {"external_id": source_id, "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()}
        )
    resolved = {
        "player": {
            "Bad": {"status": local_status, "canonical_name": "TEST Only"},
            "Shared": {"status": "unresolved"},
            "White": {"status": "qualified", "canonical_name": "White"},
        },
        "event": {"NewMatch": {"status": "unresolved"}},
    }
    monkeypatch.setattr(orchestration, "lookup_qualified_identities", lambda *a, **k: resolved)
    monkeypatch.setattr(orchestration, "qualified_raw_player_templates", lambda *a, **k: {"templates": {}})
    monkeypatch.setattr(orchestration, "qualified_raw_event_templates", lambda *a, **k: {"templates": {}})
    checked = []

    def target(request):
        checked.append(request)
        assert all(
            row["name_decision"] == (row["canonical_name"] != "White" and local_status != "qualified")
            for row in request["instructions"]
        )
        return {
            **_qualified_target(request),
            "results": [
                target_status if r["canonical_name"] == "TEST Only" else "qualified" for r in request["instructions"]
            ],
        }

    if initial_check_passed:
        from copy import deepcopy
        from katrain.cron.jobs.kifu_ingest import select_portable_review_items

        initial = deepcopy(resolved)
        initial["player"]["Bad"]["canonical_name"] = "Earlier Portable Name"
        records = [(item, await orchestration.derive_staged_record(item)) for item in items]
        chosen, deferred = await select_portable_review_items(
            records, initial, check_identities=target, reusable_events=set(), max_new_names=3
        )
        assert chosen == items and deferred == []

    async def wiki(*args):
        assert checked
        return {"status": "unavailable", "sources": []}

    monkeypatch.setattr(orchestration, "wiki_sources", wiki)

    class Names:
        key = "test-only"
        calls = []

        async def translate_and_review(self, kind, key, members, **kwargs):
            assert checked and all(m["source_item_id"] == "43" for m in members)
            self.calls.append((kind, key))
            return _reviewed_name_decision(kind, key, members)

    isolated, names = [], Names()
    result = await orchestration.prepare_staged_games(
        items, engine=object(), client=object(), names=names, isolated=isolated, check_identities=target
    )
    assert [g["source_item_id"] for g in result["games"]] == ["43"]
    assert len(isolated) == 1 and isolated[0][0] == "42" and target_status in isolated[0][1]
    assert set(names.calls) == {("raw_player", "Shared"), ("raw_event", "NewMatch")}
    assert all(m["source_item_id"] == "43" for d in result["decisions"] for m in d["source_items"])
    assert len(checked) == (2 if initial_check_passed else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("check_missing", [False, True])
async def test_target_identity_unavailable_defers_without_model_or_quarantine(tmp_path, monkeypatch, check_missing):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.sync import IdentityCheckUnavailable

    sgf = "(;PB[Black]PW[White]EV[Match];B[aa])"
    path = tmp_path / "42.sgf"
    path.write_text(sgf)
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {"player": {"Black": {"status": "qualified", "canonical_name": "Black"}}, "event": {}},
    )
    monkeypatch.setattr(
        orchestration, "wiki_sources", lambda *a: pytest.fail("unavailable target reached paid preparation")
    )

    def unavailable(request):
        raise IdentityCheckUnavailable("production identity check unavailable")

    isolated = []
    with pytest.raises(IdentityCheckUnavailable):
        await orchestration.prepare_staged_games(
            [{"external_id": "42", "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()}],
            engine=object(),
            client=object(),
            names=None,
            isolated=isolated,
            check_identities=None if check_missing else unavailable,
        )
    assert isolated == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", (None, "displays", "original_language", "methods"))
async def test_staged_game_preserves_qualified_raw_player_template_meaning(tmp_path, monkeypatch, fault):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.catalog import review_content_sha256
    from katrain.kifu_ingest.names import NameRejected

    sgf = "(;PB[姜勋]PW[White]EV[Match];B[aa])"
    path = tmp_path / "42.sgf"
    path.write_text(sgf, encoding="utf-8")
    item = {"external_id": "42", "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()}
    template = {
        "displays": {"cn": "姜勋", "tw": "姜勳", "jp": "姜勲", "ko": "강훈", "en": "Kang Hun"},
        "original_language": "und",
        "methods": {
            "cn": "retain_original",
            "tw": "orthographic_conversion",
            "jp": "transliteration",
            "ko": "transliteration",
            "en": "transliteration",
        },
        "sources": [],
    }
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {
            "player": {"姜勋": {"status": "unresolved"}, "White": {"status": "qualified", "canonical_name": "White"}},
            "event": {"Match": {"status": "qualified", "canonical_name": "Match"}},
        },
    )
    monkeypatch.setattr(
        orchestration, "qualified_raw_player_templates", lambda *a, **k: {"templates": {"姜勋": template}}
    )

    async def no_wiki(*args):
        return {"status": "unavailable", "sources": []}

    monkeypatch.setattr(orchestration, "wiki_sources", no_wiki)

    class Names:
        key = "test-only"

        async def translate_and_review(self, kind, key, members, *, sources, context):
            assert context == {
                f"verified_reuse_{field}": template[field] for field in ("displays", "original_language", "methods")
            }
            result = _reviewed_name_decision(kind, key, members)
            result.update(
                {
                    field: template[field].copy() if isinstance(template[field], dict) else template[field]
                    for field in ("displays", "original_language", "methods")
                }
            )
            if fault == "original_language":
                result[fault] = "ko"
            elif fault:
                result[fault]["jp"] = "姜勳" if fault == "displays" else "orthographic_conversion"
            result["review"]["content_sha256"] = review_content_sha256(result)
            return result

    isolated = []
    if fault:
        with pytest.raises(NameRejected, match="all staged games require isolated name review"):
            await orchestration.prepare_staged_games(
                [item],
                engine=object(),
                client=object(),
                names=Names(),
                isolated=isolated,
                check_identities=_qualified_target,
            )
        assert len(isolated) == 1 and isolated[0][0] == "42"
        assert "qualified reusable" in isolated[0][1]
    else:
        result = await orchestration.prepare_staged_games(
            [item],
            engine=object(),
            client=object(),
            names=Names(),
            isolated=isolated,
            check_identities=_qualified_target,
        )
        assert result["decisions"][0]["methods"] == template["methods"]
        assert result["decisions"][0]["original_language"] == "und"
        assert isolated == []


@pytest.mark.asyncio
@pytest.mark.parametrize("frozen_kind", ("raw_event", "raw_player"))
@pytest.mark.parametrize(
    "other_player_status",
    ("missing_qualified_five_languages", "different_original_languages_require_separate_review"),
)
async def test_staged_batch_isolates_frozen_raw_profile_before_any_model_call(
    tmp_path, monkeypatch, frozen_kind, other_player_status
):
    from katrain.kifu_ingest import orchestration

    raw_frozen = "Frozen"
    items = []
    for source_id in ("42", "43"):
        black = raw_frozen if frozen_kind == "raw_player" and source_id == "42" else "Shared"
        event = raw_frozen if frozen_kind == "raw_event" and source_id == "42" else "NewMatch"
        sgf = f"(;PB[{black}]PW[White]EV[{event}];B[aa])"
        path = tmp_path / f"{source_id}.sgf"
        path.write_text(sgf, encoding="utf-8")
        items.append(
            {"external_id": source_id, "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()}
        )
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {
            "player": {
                "Frozen": {"status": "unresolved"},
                "Shared": {"status": "unresolved"},
                "White": {"status": "qualified", "canonical_name": "White"},
            },
            "event": {name: {"status": "unresolved"} for name in ("Frozen", "NewMatch")},
        },
    )
    for kind in ("raw_player", "raw_event"):
        unavailable = {
            "Shared" if kind == "raw_player" else "NewMatch": (
                other_player_status if kind == "raw_player" else "missing_qualified_five_languages"
            )
        }
        if kind == frozen_kind:
            unavailable[raw_frozen] = "no_native_generated_scope_refresh"
        monkeypatch.setattr(
            orchestration,
            f"qualified_{kind}_templates",
            lambda *a, unavailable=unavailable, **k: {"templates": {}, "unavailable": unavailable},
        )

    async def no_wiki(*args):
        return {"status": "unavailable", "sources": []}

    monkeypatch.setattr(orchestration, "wiki_sources", no_wiki)

    class Names:
        key = "test-only"

        def __init__(self):
            self.generated = []

        async def translate_and_review(self, kind, key, members, *, sources, context):
            self.generated.append((kind, key, [member["source_item_id"] for member in members]))
            return _reviewed_name_decision(kind, key, members)

        async def review_existing_decision(self, *args):
            pytest.fail("unchanged surviving members must not pay for another review")

    names = Names()
    isolated = []
    manifest = await orchestration.prepare_staged_games(
        items, engine=object(), client=object(), names=names, isolated=isolated, check_identities=_qualified_target
    )

    assert [game["source_item_id"] for game in manifest["games"]] == ["43"]
    assert isolated == [("42", f"{frozen_kind} 'Frozen': no_native_generated_scope_refresh")]
    assert sorted(names.generated) == [("raw_event", "NewMatch", ["43"]), ("raw_player", "Shared", ["43"])]
    assert {member["source_item_id"] for decision in manifest["decisions"] for member in decision["source_items"]} == {
        "43"
    }
    orchestration._validated(manifest)


@pytest.mark.asyncio
@pytest.mark.parametrize("frozen_kind", ("raw_event", "raw_player"))
@pytest.mark.parametrize("names_enabled", (True, False))
async def test_staged_batch_with_only_frozen_raw_profiles_rejects_without_model_or_credentials(
    tmp_path, monkeypatch, frozen_kind, names_enabled
):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.names import NameRejected

    items = []
    for source_id in ("42", "43"):
        sgf = "(;PB[Frozen]PW[White]EV[Frozen];B[aa])"
        path = tmp_path / f"{source_id}.sgf"
        path.write_text(sgf, encoding="utf-8")
        items.append(
            {"external_id": source_id, "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()}
        )
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {
            "player": {
                name: (
                    {"status": "unresolved"}
                    if frozen_kind == "raw_player" and name == "Frozen"
                    else {"status": "qualified", "canonical_name": name}
                )
                for name in ("Frozen", "White")
            },
            "event": {
                "Frozen": (
                    {"status": "unresolved"}
                    if frozen_kind == "raw_event"
                    else {"status": "qualified", "canonical_name": "Frozen"}
                )
            },
        },
    )
    monkeypatch.setattr(
        orchestration,
        f"qualified_{frozen_kind}_templates",
        lambda *a, **k: {"templates": {}, "unavailable": {"Frozen": "no_native_generated_scope_refresh"}},
    )
    monkeypatch.setattr(orchestration, "wiki_sources", lambda *a, **k: pytest.fail("network called"))

    class Names:
        key = "test-only"

        async def translate_and_review(self, *args, **kwargs):
            pytest.fail("model called for frozen profile")

    isolated = []
    with pytest.raises(NameRejected, match="all staged games require isolated name review"):
        await orchestration.prepare_staged_games(
            items,
            engine=object(),
            client=object(),
            names=Names() if names_enabled else None,
            isolated=isolated,
            check_identities=_qualified_target,
        )
    assert isolated == [
        (source_id, f"{frozen_kind} 'Frozen': no_native_generated_scope_refresh") for source_id in ("42", "43")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("canonical_missing", [False, True])
async def test_staged_game_reviews_only_missing_name_with_finite_scope(tmp_path, monkeypatch, canonical_missing):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.catalog import review_content_sha256

    sgf = "(;PB[Black]PW[White]EV[Match];B[aa])"
    path = tmp_path / "42.sgf"
    path.write_text(sgf, encoding="utf-8")
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {
            "player": {
                "Black": (
                    {"status": "missing_qualified_five_languages", "canonical_name": "Black"}
                    if canonical_missing
                    else {"status": "unresolved"}
                ),
                "White": {"status": "qualified", "canonical_name": "White"},
            },
            "event": {"Match": {"status": "qualified", "canonical_name": "Match"}},
        },
    )
    monkeypatch.setattr(orchestration, "qualified_raw_player_templates", lambda *a, **k: {"templates": {}})

    async def fake_wiki(*args):
        return {"status": "unavailable", "sources": []}

    monkeypatch.setattr(orchestration, "wiki_sources", fake_wiki)

    class Names:
        key = "test-only"

        async def translate_and_review(self, kind, key, members, *, sources, context):
            assert (kind, key, sources, context) == ("player" if canonical_missing else "raw_player", "Black", [], None)
            decision = {
                "kind": kind,
                "key": key,
                "displays": {lang: "Black" for lang in ("cn", "tw", "jp", "ko", "en")},
                "methods": {lang: "retain_original" for lang in ("cn", "tw", "jp", "ko", "en")},
                "original_language": "en",
                "sources": [],
                "source_items": members,
                "producer": {"id": "p", "model": "m", "request_id": "1", "at": "2026-10-01T00:00:00Z"},
            }
            decision["review"] = {
                "id": "r",
                "model": "m",
                "request_id": "2",
                "at": "2026-10-01T00:00:01Z",
                "decision": "approve",
                "content_sha256": review_content_sha256(decision),
            }
            return decision

    def target(request):
        return {
            **_qualified_target(request),
            "results": [
                "missing_qualified_five_languages" if r["canonical_name"] == "Black" else "qualified"
                for r in request["instructions"]
            ],
        }

    manifest = await orchestration.prepare_staged_game(
        {"external_id": "42", "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()},
        engine=object(),
        client=object(),
        names=Names(),
        check_identities=target,
    )
    assert manifest["games"][0]["identities"]["black"] == ({"canonical_name": "Black"} if canonical_missing else None)
    assert [d["kind"] for d in manifest["decisions"]] == ["player" if canonical_missing else "raw_player"]
    assert manifest["decisions"][0]["source_items"][0]["slot"] == "black"


@pytest.mark.asyncio
async def test_staged_batch_reviews_shared_raw_player_once_for_all_members(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.catalog import review_content_sha256

    items = []
    for source_id in ("42", "43"):
        sgf = f"(;PB[Black]PW[White]EV[Match]DT[2026-02-01];B[aa])"
        path = tmp_path / f"{source_id}.sgf"
        path.write_text(sgf, encoding="utf-8")
        items.append(
            {"external_id": source_id, "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()}
        )
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {
            "player": {"Black": {"status": "unresolved"}, "White": {"status": "qualified", "canonical_name": "White"}},
            "event": {"Match": {"status": "qualified", "canonical_name": "Match"}},
        },
    )
    monkeypatch.setattr(orchestration, "qualified_raw_player_templates", lambda *a, **k: {"templates": {}})

    async def no_wiki(*args):
        return {"status": "unavailable", "sources": []}

    monkeypatch.setattr(orchestration, "wiki_sources", no_wiki)

    class Names:
        key = "test-only"
        calls = 0

        async def translate_and_review(self, kind, key, members, *, sources, context):
            self.calls += 1
            assert (kind, key) == ("raw_player", "Black")
            assert {member["source_item_id"] for member in members} == {"42", "43"}
            decision = {
                "kind": kind,
                "key": key,
                "displays": {lang: "Black" for lang in ("cn", "tw", "jp", "ko", "en")},
                "methods": {lang: "retain_original" for lang in ("cn", "tw", "jp", "ko", "en")},
                "original_language": "en",
                "sources": [],
                "source_items": members,
                "producer": {"id": "p", "model": "m", "request_id": "1", "at": "2026-10-01T00:00:00Z"},
            }
            decision["review"] = {
                "id": "r",
                "model": "m",
                "request_id": "2",
                "at": "2026-10-01T00:00:01Z",
                "decision": "approve",
                "content_sha256": review_content_sha256(decision),
            }
            return decision

    names = Names()
    manifest = await orchestration.prepare_staged_games(
        items, engine=object(), client=object(), names=names, check_identities=_qualified_target
    )
    assert names.calls == 1
    assert len(manifest["games"]) == 2
    assert len(manifest["decisions"]) == 1


@pytest.mark.asyncio
async def test_rejected_name_isolates_only_linked_games_and_rereviews_narrowed_scope(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.catalog import review_content_sha256
    from katrain.kifu_ingest.names import NameRejected

    items = []
    for source_id, black, white in (("41", "Alice", "White"), ("42", "Alice", "Bad"), ("43", "Carol", "White")):
        sgf = f"(;PB[{black}]PW[{white}]EV[Match]DT[2026-02-01];B[aa])"
        path = tmp_path / f"{source_id}.sgf"
        path.write_text(sgf, encoding="utf-8")
        items.append(
            {"external_id": source_id, "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()}
        )
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **k: {
            "player": {name: {"status": "unresolved"} for name in ("Alice", "Bad", "Carol")}
            | {"White": {"status": "qualified", "canonical_name": "White"}},
            "event": {"Match": {"status": "qualified", "canonical_name": "Match"}},
        },
    )
    monkeypatch.setattr(orchestration, "qualified_raw_player_templates", lambda *a, **k: {"templates": {}})

    async def no_wiki(*args):
        return {"status": "unavailable", "sources": []}

    monkeypatch.setattr(orchestration, "wiki_sources", no_wiki)

    class Names:
        key = "test-only"
        generated = []
        rereviewed = []

        async def translate_and_review(self, kind, key, members, *, sources, context):
            self.generated.append(key)
            if key == "Bad":
                raise NameRejected("bad name")
            decision = {
                "kind": kind,
                "key": key,
                "displays": {lang: key for lang in ("cn", "tw", "jp", "ko", "en")},
                "methods": {lang: "retain_original" for lang in ("cn", "tw", "jp", "ko", "en")},
                "original_language": "en",
                "sources": [],
                "source_items": members,
                "producer": {"id": "p", "model": "m", "request_id": f"p-{key}", "at": "2026-10-01T00:00:00Z"},
            }
            decision["review"] = {
                "id": "r",
                "model": "m",
                "request_id": f"r-{key}",
                "at": "2026-10-01T00:00:01Z",
                "decision": "approve",
                "content_sha256": review_content_sha256(decision),
            }
            return decision

        async def review_existing_decision(self, decision, members):
            self.rereviewed.append((decision["key"], [m["source_item_id"] for m in members]))
            narrowed = {**decision, "source_items": members}
            narrowed["review"] = {**decision["review"], "content_sha256": review_content_sha256(narrowed)}
            return narrowed

    names = Names()
    isolated = []
    manifest = await orchestration.prepare_staged_games(
        items,
        engine=object(),
        client=object(),
        names=names,
        isolated=isolated,
        check_identities=_qualified_target,
    )
    assert [game["source_item_id"] for game in manifest["games"]] == ["41", "43"]
    assert isolated == [("42", "bad name")]
    assert names.generated == ["Alice", "Bad", "Carol"]
    assert names.rereviewed == [("Alice", ["41"])]
    assert [d["key"] for d in manifest["decisions"]] == ["Alice", "Carol"]
