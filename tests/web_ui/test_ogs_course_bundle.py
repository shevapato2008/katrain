"""Bounded OGS extraction and Python consumer checks; no database or network."""

import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
EXPORTER = ROOT / "scripts/ogs/export_course.mjs"
RESEARCH = Path(
    os.environ.get("OGS_RESEARCH_ROOT", Path.home() / ".local/share/smartbox-admin/ogs-learn-to-play-research-20261019")
)


def node_json(code):
    script = f"import * as exporter from {json.dumps(EXPORTER.as_uri())};\n{code}"
    result = subprocess.run(["node", "--input-type=module", "-e", script], text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def test_coordinate_formats_tree_flags_and_pass():
    result = node_json("""
      console.log(JSON.stringify({
        sgf: exporter.decodeMoves('hppq', 19, 19),
        pretty: exporter.decodeMoves('H4J3', 19, 19),
        pass: exporter.decodeMoves('..', 9, 9),
        tree: exporter.makeMoveTree(['a1b1c1', 'a1b2'], ['a1c1', ''], 9, 9),
        multiPass: exporter.makeMoveTree(['..aa..'], ['aabb'], 9, 9),
      }));
    """)
    assert result["sgf"] == [[7, 15], [15, 16]]
    assert result["pretty"] == [[7, 15], [8, 16]]
    assert result["pass"] == [None]
    tree = result["tree"]
    assert tree["point"] is None and tree["wrong"] is True
    assert len(tree["children"]) == 1
    assert len(tree["children"][0]["children"]) == 3
    assert tree["children"][0]["children"][0]["children"][0]["correct"]
    assert result["multiPass"]["children"][0]["point"] is None
    assert result["multiPass"]["children"][0]["children"][0]["children"][0] == {
        "point": None,
        "correct": True,
        "wrong": False,
        "children": [],
    }


def test_same_color_dedup_and_opposite_color_collision():
    result = node_json("""
      const duplicate = exporter.normalizeStones({black:'aaaa', white:'bb'}, 9, 9);
      let collision = false;
      try { exporter.normalizeStones({black:'aa', white:'aa'}, 9, 9); } catch { collision = true; }
      console.log(JSON.stringify({duplicate, collision}));
    """)
    assert result["duplicate"] == {"B": [[0, 0]], "W": [[1, 1]]}
    assert result["collision"] is True


def test_content_hash_excludes_screenshots():
    result = node_json("""
      const a = {schema_version:1, source:{commit:'abc'}, steps:[{page:1}]};
      const b = structuredClone(a); b.steps[0].screenshot = {path:'x.png', captured_at:'later'};
      b.source.content_sha256 = 'old';
      console.log(JSON.stringify([exporter.contentHash(a), exporter.contentHash(b)]));
    """)
    assert result[0] == result[1]


@pytest.fixture(scope="module")
def course(tmp_path_factory):
    if not (RESEARCH / "ogs-upstream/src/views/LearningHub/sections.ts").exists():
        pytest.skip("Set OGS_RESEARCH_ROOT to the private pinned source/catalog research directory")
    out = tmp_path_factory.mktemp("ogs-course") / "course.json"
    env = dict(os.environ)
    if "OGS_TYPESCRIPT_MODULE" not in env:
        candidate = Path.home() / "Repositories/katrain-admin-console/katrain/web/ui/node_modules/typescript"
        if candidate.exists():
            env["OGS_TYPESCRIPT_MODULE"] = str(candidate)
    subprocess.run(
        [
            "node", str(EXPORTER), "--source-root", str(RESEARCH / "ogs-upstream"),
            "--catalog-root", str(RESEARCH), "--output", str(out),
        ],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(out.read_text()), json.loads(out.with_name("coverage.json").read_text())


def test_full_registered_source_coverage(course):
    bundle, report = course
    assert bundle["schema_version"] == 1
    counts = (len(bundle["chapters"]), len(bundle["lessons"]), len(bundle["steps"]), len(bundle["languages"]))
    assert counts == (7, 248, 3551, 32)
    assert Counter(step["exercise"]["kind"] for step in bundle["steps"]) == {
        "puzzle": 3028, "choice": 520, "pass": 1, "remove": 1, "finish": 1,
    }
    assert [step["page"] for step in bundle["steps"]] == list(range(1, 3552))
    assert len({step["source_id"] for step in bundle["steps"]}) == 3551
    assert report["unsupported"] == []
    assert report["counts"]["message_keys"] == 883
    assert sum(language["missing"] for language in report["languages"].values()) == 0
    assert bundle["source"]["content_sha256"] == report["content_sha256"]
    unhashed = json.loads(json.dumps(bundle))
    del unhashed["source"]["content_sha256"]
    canonical = json.dumps(unhashed, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    expected_hash = hashlib.sha256(canonical).hexdigest()
    assert expected_hash == bundle["source"]["content_sha256"]
    assert len(bundle["source"]["license_text"]) > 30000
    for lesson in bundle["lessons"]:
        assert bundle["steps"][lesson["first_page"] - 1]["lesson_id"] == lesson["id"]
    for step in bundle["steps"]:
        assert set(step["translations"]) == set(bundle["languages"])
        assert step["source_url"].endswith(f'/{step["step"] - 1}')
        assert step["initial_player"] in ("B", "W")
        assert set(map(tuple, step["stones"]["B"])).isdisjoint(map(tuple, step["stones"]["W"]))


def test_four_frozen_examples_and_multibranch_source(course):
    bundle, _ = course
    steps = {step["source_id"]: step for step in bundle["steps"]}
    capture = steps["ogs-learning:capture_stone:1"]
    assert capture["stones"] == {"B": [[0, 7]], "W": [[0, 8]]}
    assert capture["exercise"]["tree"]["children"][0]["point"] == [1, 8]
    assert capture["translations"]["ja"]["instruction"] == "黒番で白を取りましょう。"
    assert capture["translations"]["zh-cn"]["instruction"] == "黑方先行。请提掉这颗被标记的白子。"
    opening = steps["ogs-learning:bl4-opening-4:1"]
    assert opening["size"] == 19 and opening["initial_player"] == "W"
    assert opening["viewport"] == {"col": 0, "row": 9, "cols": 19, "rows": 10}
    assert opening["letters"] == {"7,15": "A", "7,16": "B", "8,16": "C"}
    assert opening["exercise"]["tree"]["children"][0]["point"] == [7, 15]
    liberties = steps["ogs-learning:count-liberties:1"]
    assert liberties["exercise"]["correct_choice"] == "3"
    assert [choice["value"] for choice in liberties["exercise"]["choices"]] == ["3", "4", "6"]
    removal = steps["ogs-learning:ending-the-game:2"]
    assert removal["exercise"]["remove_targets"] == [[5, 0], [5, 1], [6, 1], [7, 1]]
    anomaly = steps["ogs-learning:bl3-joseki-1:4"]
    assert anomaly["exercise"]["tree"]["wrong"] and "root_wrong_answer" in anomaly["issues"]
    assert steps["ogs-learning:bl;3-skills-5:1"]["source_url"].endswith("/bl%3B3-skills-5/0")
    assert steps["ogs-learning:rules-intro:1"]["size"] == 9
    assert steps["ogs-learning:rules-intro:1"]["initial_player"] == "B"
    puzzle_trees = [step["exercise"]["tree"] for step in bundle["steps"] if step["exercise"]["kind"] == "puzzle"]
    assert max(len(node["children"]) for tree in puzzle_trees for node in walk_tree(tree)) > 2
    assert max(depth(tree) for tree in puzzle_trees) == 26


def walk_tree(node):
    yield node
    for child in node["children"]:
        yield from walk_tree(child)


def depth(node):
    return max((1 + depth(child) for child in node["children"]), default=0)
