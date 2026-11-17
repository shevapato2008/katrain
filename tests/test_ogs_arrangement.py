"""Focused contract checks for the local-only OGS arrangement assembler."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def assembler():
    path = Path(__file__).parents[1] / "scripts/tutorials/ogs_arrangement.py"
    assert path.exists(), "OGS arrangement assembler is not implemented"
    spec = importlib.util.spec_from_file_location("ogs_arrangement", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def inputs():
    lessons = [
        {
            "id": f"lesson-{i}",
            "course_code": f"1.{i + 1}",
            "title": f"练习{i}",
            "chapter_id": "chapter-1",
            "chapter_number": 1,
            "chapter_title": "入门知识",
            "step_count": 1,
            "source_url": "https://online-go.com/learn-to-play-go/lesson-0",
        }
        for i in range(248)
    ]
    unit = {
        "id": "U_TEST",
        "book_id": 11,
        "catalog_id": "intro-up",
        "book_title": "入门书",
        "chapter": "第一章",
        "section": "气与提子",
        "pdf_pages": [1, 5],
        "pdf": "/tmp/入门书.pdf",
    }
    clips = []
    for i in range(1931):
        clips.append(
            {
                "id": 20000 + i,
                "book_id": 11,
                "catalog_id": "intro-up",
                "book_title": "入门书",
                "page": 2,
                "figure_label": "图一",
                "book_text": "紧住最后一气，提走白棋。",
                "narration": "请紧住最后一口气。",
                "narration_sha256": "a" * 64,
                "board_sha256": "b" * 64,
                "source_identity": {"source_pointer": "/chapters/0", "image_sha256": "c" * 64},
                "audio": {"asset": "audio.mp3", "sha256": "d" * 64, "duration_ms": 12340},
                "profiles": {
                    profile: {
                        "asset": f"tutorial_assets/intro-up/media/{i:032x}/video-2d-{profile}.mp4",
                        "sha256": "e" * 64,
                        "width": width,
                        "height": height,
                        "duration_ms": 12367,
                        "timing_status": "complete",
                    }
                    for profile, width, height in [("kiosk-7-v1", 1024, 600), ("galaxy-4k-v1", 3840, 2160)]
                },
                "duration_seconds": 999,  # Intentionally wrong: derive from the actual MP4 metadata.
                "source_units": ["U_TEST"],
                "admin_url": f"http://127.0.0.1:18012/admin?book=11&page=2&figure={20000 + i}&filter=all",
                "context_flags": [],
            }
        )
    decisions = [
        {
            "lesson_id": lesson["id"],
            "course_code": lesson["course_code"],
            "goal": "找到最后一口气并提子。",
            "intro": "先观察白棋的气。",
            "practice_bridge": "进入练习后紧住最后一气。",
            "clips": [
                {
                    "figure_id": 20000,
                    "role": "概念",
                    "focus": "最后一气",
                    "rationale": "展示提子的条件。",
                    "source_unit": "U_TEST",
                }
            ],
            "coverage_notes": ["交互练习负责实际落子。"],
        }
        for lesson in lessons
    ]
    baseline = {f"lesson-{i}": [20000] for i in range(14)}
    identity = {"database_name": "katrain_db", "system_identifier": "test-pinned-id"}
    return {
        "outline": {"lessons": lessons, "source_units": {"U_TEST": unit}, "source_content_sha256": "ogs-content"},
        "goals": {
            "lessons": [
                {**x, "topic_summary": "紧气提子", "steps": [{"step": 1, "instruction": "提走白棋。"}]} for x in lessons
            ]
        },
        "video_index": {"clips": clips, "identity": identity, "captured_at": "2026-11-17T10:00:00Z"},
        "capture": {"clips": copy.deepcopy(clips), "identity": identity, "captured_at": "2026-11-17T10:00:00Z"},
        "proof": {
            "environment": "TEST",
            "clips": 1931,
            "identity": identity,
            "source_board_audio_asset_pins_matched": True,
        },
        "final_report": {
            "current_complete_figures": 1931,
            "scope_exclusions": [{"figure_id": 9000 + i} for i in range(15)],
        },
        "contract": {
            "schema_version": 1,
            "baseline_playlists": baseline,
            "role_values": ["概念", "示范", "对照", "巩固"],
        },
        "baseline_manifest": {
            "playlists": copy.deepcopy(baseline),
            "clips": [{"id": 20000, "title": "认识最后一口气"}],
        },
        "chapter_documents": [{"schema_version": 1, "chapter_number": 1, "lessons": decisions}],
    }


def test_assembles_exact_ids_actual_duration_sources_and_honest_status(assembler, inputs):
    track, manifest = assembler.assemble(**inputs)
    assert len(track["lessons"]) == len(manifest["playlists"]) == 248
    assert manifest["schema_version"] == 1
    assert manifest["release_id"] == "ogs-full-test-20261117"
    assert manifest["language"] == "zh-cn"
    assert manifest["clips"][0]["duration"] == 12.367
    assert track["lessons"][0]["duration_seconds"] == 12.367
    source = track["lessons"][0]["clips"][0]["source"]
    assert source["chapter"] == "第一章" and source["section"] == "气与提子"
    assert source["pdf_url"].endswith(".pdf#page=2")
    assert track["publication"]["test"] == "prepared_not_published"
    assert track["publication"]["prod"] == "existing_14_unchanged"
    assert manifest["clips"][0]["profiles"]["kiosk-7-v1"]["url"].startswith(
        "https://go.sailorvoyage.top/media/tutorial_assets/"
    )
    assert "poster_url" not in manifest["clips"][0]
    assert manifest["playlists"]["lesson-0"] == inputs["baseline_manifest"]["playlists"]["lesson-0"]


@pytest.mark.parametrize("problem", ["missing", "unknown", "duplicate"])
def test_rejects_nonexact_lesson_coverage(assembler, inputs, problem):
    rows = inputs["chapter_documents"][0]["lessons"]
    if problem == "missing":
        rows.pop()
    elif problem == "unknown":
        rows[-1]["lesson_id"] = "not-in-ogs"
    else:
        rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(ValueError, match="lesson.*coverage|duplicate lesson"):
        assembler.assemble(**inputs)


@pytest.mark.parametrize("problem", ["empty", "duplicate", "excluded", "unknown", "source", "role", "course_code"])
def test_rejects_invalid_editorial_references(assembler, inputs, problem):
    row = inputs["chapter_documents"][0]["lessons"][-1]
    if problem == "empty":
        row["clips"] = []
    elif problem == "duplicate":
        row["clips"] *= 2
    elif problem in {"excluded", "unknown"}:
        row["clips"][0]["figure_id"] = 9000 if problem == "excluded" else 99999
    elif problem == "source":
        row["clips"][0]["source_unit"] = "invented"
    elif problem == "role":
        row["clips"][0]["role"] = "随便选"
    else:
        row["course_code"] = "9.999"
    with pytest.raises(ValueError):
        assembler.assemble(**inputs)


@pytest.mark.parametrize(
    "problem",
    ["profile", "asset", "duration", "stale_board", "stale_audio", "stale_asset", "stale_source", "stale_narration"],
)
def test_rejects_incomplete_or_stale_current_media(assembler, inputs, problem):
    clip = inputs["video_index"]["clips"][0]
    if problem == "profile":
        del clip["profiles"]["kiosk-7-v1"]
    elif problem == "asset":
        clip["profiles"]["kiosk-7-v1"]["asset"] = "tutorial_assets/../old.mp4?token=secret"
    elif problem == "duration":
        clip["profiles"]["kiosk-7-v1"]["duration_ms"] = 0
    elif problem == "stale_board":
        clip["board_sha256"] = "0" * 64
    elif problem == "stale_audio":
        clip["audio"]["sha256"] = "0" * 64
    elif problem == "stale_source":
        clip["source_identity"]["image_sha256"] = "0" * 64
    elif problem == "stale_narration":
        clip["narration_sha256"] = "0" * 64
    else:
        clip["profiles"]["galaxy-4k-v1"][
            "asset"
        ] = "tutorial_assets/intro-up/media/ffffffffffffffffffffffffffffffff/video-2d-galaxy-4k-v1.mp4"
    # Missing/invalid current data must fail its own check, not merely a pin mismatch.
    if problem in {"profile", "asset", "duration"}:
        inputs["capture"]["clips"][0] = copy.deepcopy(clip)
    reason = {"profile": "profile", "asset": "asset path", "duration": "video duration"}.get(problem, "stale clip")
    with pytest.raises(ValueError, match=reason):
        assembler.assemble(**inputs)


def test_rejects_changed_baseline_order(assembler, inputs):
    row = inputs["chapter_documents"][0]["lessons"][0]
    row["clips"].append({**row["clips"][0], "figure_id": 20001})
    with pytest.raises(ValueError, match="baseline"):
        assembler.assemble(**inputs)


def test_manifest_keeps_accepted_titles_and_uses_first_editorial_focus(assembler, inputs):
    rows = inputs["chapter_documents"][0]["lessons"]
    rows[-2]["clips"][0].update(figure_id=20001, focus="先紧外气")
    rows[-1]["clips"][0].update(figure_id=20001, focus="复用到杀气练习")
    track, manifest = assembler.assemble(**inputs)
    titles = {clip["id"]: clip["title"] for clip in manifest["clips"]}
    assert titles[20000] == "认识最后一口气"
    assert titles[20001] == "先紧外气"
    assert manifest["clips"][1]["book"] == "入门书" and manifest["clips"][1]["page"] == 2
    assert track["lessons"][-1]["clips"][0]["source"]["book_title"] == "入门书"


def test_rejects_unpinned_index_file(assembler, inputs, tmp_path):
    (tmp_path / "video-index.json").write_text(json.dumps(inputs["video_index"]))
    (tmp_path / "capture-proof.json").write_text(json.dumps({**inputs["proof"], "index_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="checksum"):
        assembler.load_pinned_index(tmp_path)


def test_outputs_review_table_and_manifest_without_eager_media(assembler, inputs, tmp_path):
    inputs["chapter_documents"][0]["lessons"][0]["intro"] = "观察 <script>alert(1)</script>"
    track, manifest = assembler.assemble(**inputs)
    paths = assembler.write_artifacts(track, manifest, tmp_path, tmp_path / "review")
    assert set(paths) == {"json", "csv", "html", "manifest"}
    html = paths["html"].read_text()
    assert html.count('class="lesson-row"') == 248
    assert 'id="chapter"' in html and 'id="source"' in html and 'id="search"' in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert 'preload="none"' in html
    assert "autoplay" not in html and ".play()" not in html and "fetch(" not in html
    assert track["publication"]["test"] == "prepared_not_published"
    assert "正式环境尚未发布" in html
    assert "第一章" in html and "气与提子" in html
    assert '<span class="pdf-page">入门书 · PDF 2</span>' in html
    assert 'class="pdf-local-link"' in html and 'class="pdf-http-note" hidden' in html
    assert "PDF页码已列，可从原书/管理后台核对" in html
    assert "location.protocol" in html and "http:" in html and "https:" in html
    assert len(paths["csv"].read_text(encoding="utf-8-sig").splitlines()) == 249
    assert json.loads(paths["manifest"].read_text()) == manifest
