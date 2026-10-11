"""Sync only 16 reviewed person/source URLs after native batch-595 verification."""

import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

from sqlalchemy import Column, JSON, create_engine, text
from katrain.web.core.models_db import KifuPlayer
from katrain.web.kifu.name_evidence import registry_sha256


if not __debug__:
    raise RuntimeError("pages guard assertions must be enabled")
# The pinned administrative image predates the existing database pages column.
if not hasattr(KifuPlayer, "authoritative_pages"):
    KifuPlayer.authoritative_pages = Column(JSON, nullable=False)
from katrain.web.kifu import player_pages


D = Path("/work")
env, phase = sys.argv[1:]
assert env in {"PROD", "TEST"} and phase in {"preview", "apply", "verify"}
plan_path = D / "595-pages-proposed-plan.json"
manifest_path = D / "595-closure-proposed-manifest.json"
plan = json.loads(plan_path.read_text())
manifest = json.loads(manifest_path.read_text())
assert plan["kind"] == "next16_player_pages_exact_url_plan_v1"
assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == manifest["pages_plan_sha256"]
for name, sha in manifest["helper_sha256"].items():
    assert hashlib.sha256((D / name).read_bytes()).hexdigest() == sha
module_sha = hashlib.sha256(Path(player_pages.__file__).read_bytes()).hexdigest()
assert module_sha == plan["pinned_player_pages_sha256"] == manifest["pinned_player_pages_sha256"]
bundle_path = D / f"{env}-next16-bundle.json.gz"
bundle = json.loads(gzip.decompress(bundle_path.read_bytes()))
entry = plan["environments"][env]
assert registry_sha256(bundle) == entry["bundle_sha256"] == manifest[env]["bundle_sha256"]
for kind, filename in (("bundle", f"{env}-next16-bundle.json.gz"),
                       ("evidence", f"{env}-next16-evidence.jsonl"),
                       ("registry", f"{env}-next16-registry.json")):
    assert hashlib.sha256((D / filename).read_bytes()).hexdigest() == entry[f"{kind}_file_sha256"]
verify = json.loads((D / f"{env}-verify.json").read_text())
assert verify["passed"] and verify["bundle_sha256"] == entry["bundle_sha256"]
assert verify["verified_name_count"] == verify["complete_players_delta"] == 16
assert verify["album_count"] == 158 and verify["game_slots"] == 160
rows = entry["rows"]
targets = {candidate["owner"]["id"]: candidate["lang"] for candidate in bundle["candidates"]}
ids = sorted(targets)
assert len(ids) == len(rows) == 16
assert all(rows[str(pid)]["lang"] == targets[pid] for pid in ids)
assert sum(row["source_id"] == "korea-baduk" for row in rows.values()) == 13
assert {row["source_id"] for row in rows.values()} == {
    "korea-baduk", "ret157-kifudepot-ja", "ret97-ugo-en", "ret110-taiwango-tw"}
assert all("daum.net" not in row["url"] for row in rows.values())


# Keep native page extraction and atomic merge, but exclude the researched shared
# Daum list and all other URLs outside the separately reviewed 16-page plan.
native_pages_from_evidence = player_pages.pages_from_evidence


def selected_pages(name, evidence, registry_row):
    expected = rows.get(str(name.player_id))
    if expected is None or name.lang != expected["lang"]:
        return []
    return [page for page in native_pages_from_evidence(name, evidence, registry_row)
            if all(page[key] == expected[key] for key in ("url", "source_id", "language", "role"))]


player_pages.pages_from_evidence = selected_pages


def physical_rows(conn):
    live = conn.execute(text("SELECT * FROM kifu_players WHERE id = ANY(:ids) ORDER BY id"),
                        {"ids": ids}).mappings().all()
    assert [row["id"] for row in live] == ids
    return json.loads(json.dumps([dict(row) for row in live], default=str))


def check_selected(current):
    for pid in ids:
        expected = rows[str(pid)]
        matches = [page for page in current[pid] if page.get("url") == expected["url"]]
        assert len(matches) == 1
        page = matches[0]
        assert all(page[key] == expected[key] for key in ("url", "source_id", "language", "role"))
        assert page.get("evidence_ids")


engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
try:
    if phase == "preview":
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            before = physical_rows(conn)
        report = player_pages.sync_player_pages(engine, player_ids=ids, apply=False)
        assert not report["committed"] and report["players_scanned"] == 16
        assert all(change["player_id"] in ids for change in report["changes"])
        changed = {change["player_id"]: change["after"] for change in report["changes"]}
        merged = {row["id"]: changed.get(row["id"], row["authoritative_pages"]) for row in before}
        check_selected(merged)
        result = {"environment": env, "phase": phase, "preimages": before, "preview": report}
    elif phase == "apply":
        approval = json.loads((D / "root-next16-pages-approval.json").read_text())
        preview_path = D / f"{env}-pages-preview.json"
        preview = json.loads(preview_path.read_text())
        assert approval["reviewer_id"] == "/root" and approval["allow_apply"] is True
        assert approval["manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert approval["preview_sha256"][env] == hashlib.sha256(preview_path.read_bytes()).hexdigest()
        assert preview["environment"] == env and preview["phase"] == "preview"
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            assert physical_rows(conn) == preview["preimages"]
        report = player_pages.sync_player_pages(engine, player_ids=ids, apply=True)
        assert report["committed"] and report["changes"] == preview["preview"]["changes"]
        result = {"environment": env, "phase": phase, "report": report}
    else:
        preview = json.loads((D / f"{env}-pages-preview.json").read_text())
        applied = json.loads((D / f"{env}-pages-apply.json").read_text())
        assert applied["phase"] == "apply" and applied["report"]["committed"]
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            current = physical_rows(conn)
        old = {row["id"]: row for row in preview["preimages"]}
        assert len(current) == len(old) == 16
        for row in current:
            prior = old[row["id"]]
            assert {key: value for key, value in row.items() if key != "authoritative_pages"} == {
                key: value for key, value in prior.items() if key != "authoritative_pages"}
            before_pages = {page["url"]: page for page in prior["authoritative_pages"]}
            after_pages = {page["url"]: page for page in row["authoritative_pages"]}
            assert len(before_pages) == len(prior["authoritative_pages"])
            assert len(after_pages) == len(row["authoritative_pages"])
            assert set(after_pages) - set(before_pages) == ({rows[str(row["id"])]["url"]} - set(before_pages))
            for url, page in before_pages.items():
                live = after_pages[url]
                assert {key: value for key, value in live.items() if key != "evidence_ids"} == {
                    key: value for key, value in page.items() if key != "evidence_ids"}
                assert set(page.get("evidence_ids", [])) <= set(live.get("evidence_ids", []))
        check_selected({row["id"]: row["authoritative_pages"] for row in current})
        report = player_pages.sync_player_pages(engine, player_ids=ids, apply=False)
        assert report["players_changed"] == report["pages_added"] == 0 and not report["changes"]
        result = {"environment": env, "phase": phase, "passed": True,
                  "players_checked": len(current), "report": report}
finally:
    player_pages.pages_from_evidence = native_pages_from_evidence
    engine.dispose()
print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
