"""Pinned importer-side batch-592 guard and scoped baseline/verification."""

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuPlayerName
from katrain.web.kifu.identity import _approved_names, _qualified_name_rows
from katrain.web.kifu.name_batch import _image
from katrain.web.kifu.name_evidence import registry_sha256


p = Path("/work")
env, phase = sys.argv[1:]
assert env in {"PROD", "TEST"} and phase in {"baseline", "dry-run", "apply", "verify"}
manifest_bytes = (p / "final20-execution-proposed-manifest.json").read_bytes()
manifest = json.loads(manifest_bytes)
approval = json.loads((p / "root-final20-execution-approval.json").read_text())
assert approval["reviewer_id"] == "/root" and approval["allow_apply"] is True
assert approval["manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
assert approval["image_ids"] == manifest["required_image_ids"]
for helper, expected_sha in manifest["helper_sha256"].items():
    assert hashlib.sha256((p / helper).read_bytes()).hexdigest() == expected_sha
bundle_path = p / f"{env}-final20-bundle.json.gz"
bundle = json.loads(__import__("gzip").decompress(bundle_path.read_bytes()))
sha = registry_sha256(bundle)
assert sha == manifest[env]["bundle_sha256"] == approval["bundle_sha256"][env]
assert hashlib.sha256(bundle_path.read_bytes()).hexdigest() == manifest[env]["bundle_file_sha256"]
for kind, filename in (("inventory", f"{env}-final20-inventory.json.gz"),
                       ("evidence", f"{env}-final20-evidence.jsonl"),
                       ("registry", f"{env}-final20-registry.json")):
    assert hashlib.sha256((p / filename).read_bytes()).hexdigest() == manifest[env][f"{kind}_file_sha256"]
candidates = bundle["candidates"]
ids = [c["owner"]["id"] for c in candidates]
targets = {(c["owner"]["id"], c["lang"]) for c in candidates}
assert len(ids) == len(set(ids)) == len(targets) == 20
assert sum(c["decision_kind"] == "conventional" for c in candidates) == 18
assert sum(c["decision_kind"] == "generated" for c in candidates) == 2
assert {lang: sum(c["lang"] == lang for c in candidates) for lang in ("ko", "tw", "en")} == {"ko": 18, "tw": 1, "en": 1}

if phase in {"dry-run", "apply"}:
    from scripts.kifu_name_batch import main
    raise SystemExit(main([phase, "--bundle", str(bundle_path),
                           "--registry", str(p / f"{env}-final20-registry.json"),
                           "--inventory", str(p / f"{env}-final20-inventory.json.gz"),
                           "--evidence", str(p / f"{env}-final20-evidence.jsonl"),
                           "--database-url", os.environ["KATRAIN_DATABASE_URL"],
                           "--expected-bundle-sha256", sha]))

engine = create_engine(os.environ["KATRAIN_DATABASE_URL"], connect_args={"options": "-c default_transaction_read_only=on"})
with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
    with conn.begin():
        conn.execute(text("SET TRANSACTION READ ONLY"))
        assert conn.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        with Session(bind=conn) as db:
            names = db.query(KifuPlayerName).filter(KifuPlayerName.player_id.in_(ids)).order_by(KifuPlayerName.id).all()
            old = {str(n.id): registry_sha256(_image(conn, KifuPlayerName.__table__, n.id))
                   for n in names if (n.player_id, n.lang) not in targets}
            qualified_rows = _qualified_name_rows(db, _approved_names(db, KifuPlayerName, "player_id", ids),
                                                  KifuPlayerName, "player_id")
            qualified = {(n.player_id, n.lang): n for n, evidence in qualified_rows}
        scope = []
        for row in conn.execute(text("SELECT * FROM kifu_albums "
                                     "WHERE black_player_id = ANY(:ids) OR white_player_id = ANY(:ids) "
                                     "ORDER BY id"), {"ids": ids}).mappings():
            image = {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}
            image["sgf_utf8_sha256"] = hashlib.sha256(image.pop("sgf_content").encode("utf-8")).hexdigest()
            scope.append(image)
        slots = sum(int(row["black_player_id"] in ids) + int(row["white_player_id"] in ids) for row in scope)
        assert len(scope) == 609 and slots == 614
        scope_sha = registry_sha256(scope)
        qualified_old = sorted([[owner, lang] for owner, lang in qualified if (owner, lang) not in targets])
        complete = sorted(pid for pid in ids if {"cn", "tw", "jp", "ko", "en"} <=
                          {lang for owner, lang in qualified if owner == pid})
        if phase == "baseline":
            assert len(qualified_old) == len(qualified) == 80 and not complete
            before = {f"{pid}:{lang}": next((_image(conn, KifuPlayerName.__table__, n.id)
                                            for n in names if n.player_id == pid and n.lang == lang), None)
                      for pid, lang in targets}
            for candidate in candidates:
                key = f"{candidate['owner']['id']}:{candidate['lang']}"
                assert candidate["name_preimage_sha256"] == (registry_sha256(before[key]) if before[key] else None)
                if "target_name_preimage" in candidate["preimage_binding"]:
                    assert candidate["preimage_binding"]["target_name_preimage"] == before[key]
                else:
                    assert before[key] is None
            result = {"environment": env, "phase": phase, "bundle_sha256": sha,
                      "existing_names": old, "old_target_preimages": before,
                      "qualified_old_keys": qualified_old, "scope_sha256": scope_sha,
                      "album_count": len(scope), "game_slots": slots, "five_language_complete_player_ids": complete}
        else:
            baseline = json.loads((p / f"{env}-baseline.json").read_text())
            assert old == baseline["existing_names"] and scope_sha == baseline["scope_sha256"]
            assert qualified_old == baseline["qualified_old_keys"] and len(qualified) == 100
            for candidate in candidates:
                name = qualified[(candidate["owner"]["id"], candidate["lang"])]
                assert name.display_name == candidate["display_name"]
                assert name.decision_kind == candidate["decision_kind"]
                assert name.generation_rule_version == candidate["generation_rule_version"]
            assert len(complete) == 20
            result = {"environment": env, "phase": phase, "bundle_sha256": sha,
                      "verified_name_count": 20, "existing_names_unchanged_count": len(old),
                      "qualified_old_unchanged_count": len(qualified_old), "read_qualified_count": len(qualified),
                      "five_language_complete_player_ids": complete,
                      "complete_players_delta": len(complete) - len(baseline["five_language_complete_player_ids"]),
                      "scope_sha256": scope_sha, "album_count": len(scope), "game_slots": slots, "passed": True}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
engine.dispose()
