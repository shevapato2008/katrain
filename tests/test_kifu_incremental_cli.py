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
    monkeypatch.setattr(orchestration, "wiki_sources", lambda *a, **k: pytest.fail("network called"))

    class Names:
        key = ""

    with pytest.raises(NeedsCredentials):
        await orchestration.prepare_staged_game(
            {"external_id": "42", "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()},
            engine=object(),
            client=object(),
            names=Names(),
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
    )
    assert manifest["decisions"] == []
    assert manifest["games"][0]["identities"]["event"] is None


@pytest.mark.asyncio
async def test_staged_game_reviews_only_missing_raw_name_with_finite_scope(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.catalog import review_content_sha256

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

    async def fake_wiki(*args):
        return {"status": "unavailable", "sources": []}

    monkeypatch.setattr(orchestration, "wiki_sources", fake_wiki)

    class Names:
        key = "test-only"

        async def translate_and_review(self, kind, key, members, *, sources, context):
            assert (kind, key, sources, context) == ("raw_player", "Black", [], None)
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

    manifest = await orchestration.prepare_staged_game(
        {"external_id": "42", "raw_sgf_path": str(path), "raw_sha256": sha256(sgf.encode()).hexdigest()},
        engine=object(),
        client=object(),
        names=Names(),
    )
    assert manifest["games"][0]["identities"]["black"] is None
    assert [d["kind"] for d in manifest["decisions"]] == ["raw_player"]
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
    manifest = await orchestration.prepare_staged_games(items, engine=object(), client=object(), names=names)
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
    )
    assert [game["source_item_id"] for game in manifest["games"]] == ["41", "43"]
    assert isolated == [("42", "bad name")]
    assert names.generated == ["Alice", "Bad", "Carol"]
    assert names.rereviewed == [("Alice", ["41"])]
    assert [d["key"] for d in manifest["decisions"]] == ["Alice", "Carol"]
