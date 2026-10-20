"""Offline checks for the bounded GPT continuation runner."""
import importlib.util
import json
from pathlib import Path

import pytest

MODULE = Path(__file__).parents[1] / "scripts/recognize_ishida_remaining.py"
spec = importlib.util.spec_from_file_location("ishida_remaining", MODULE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def board():
    return dict(id="p101-f01", cols=3, rows=3, origin_col=7, origin_row=8,
                origin_confidence=1, black=["1,1"], white=[], unknown_stones=["0,0"],
                labels=["1,1=41"], marks=["0,0=triangle"], inferences=[],
                uncertainties=[dict(at="0,0", reason="faint", candidates=["black", "white"])], notes="")


def test_new_local_coordinates_convert_once_and_preserve_unknowns():
    result = r.convert_new(board())
    assert result["payload"]["stones"]["B"] == [[8, 9]]
    assert result["payload"]["unknown_stones"] == [[7, 8]]
    assert result["payload"]["labels"] == {"8,9": "41"}
    assert result["uncertainties"][0]["at"] == "0,0"
    assert result["uncertainties"][0]["cell"] == "7,8"
    assert result["replay_status"] == "pending"


@pytest.mark.parametrize("change", [dict(black=["3,0"]), dict(white=["1,1"]), dict(origin_col=18)])
def test_invalid_board_geometry_is_rejected(change):
    value = board()
    value.update(change)
    with pytest.raises(ValueError):
        r.convert_new(value)


def test_response_ids_cannot_be_missing_duplicate_or_unexpected():
    for values in ([], [board(), board()], [dict(board(), id="other")]):
        with pytest.raises(ValueError):
            r.validate_response({"figures": values}, "figures", ["p101-f01"], r.BOARD_SCHEMA)


def test_cache_key_includes_reasoning_schema_prompt_and_images():
    base = r.cache_key("prompt", {"type": "object"}, [{"id": "a", "sha256": "abc"}])
    assert base != r.cache_key("prompt", {"type": "array"}, [{"id": "a", "sha256": "abc"}])
    assert base != r.cache_key("prompt", {"type": "object"}, [{"id": "a", "sha256": "xyz"}])
    assert base != r.cache_key("prompt!", {"type": "object"}, [{"id": "a", "sha256": "abc"}])
    assert base != r.cache_key("prompt", {"type": "object"}, [{"id": "a", "sha256": "abc"}], reasoning="low")


def test_cache_success_is_reused_without_launch(tmp_path, monkeypatch):
    runner = r.Runner(r.DEFAULT_BOOK, tmp_path, r.DEFAULT_OLD)
    picture = tmp_path / "input.png"
    picture.write_bytes(b"image fixture")
    payload = {"figures": [board()]}
    calls = []
    def launch(*args):
        calls.append(1)
        return payload, {"attempts": 1, "elapsed_seconds": 1}
    monkeypatch.setattr(runner, "launch", launch)
    one, first = runner.invoke("board", "batch-000", [dict(id="crop", image=str(picture))], "prompt", r.BOARD_SCHEMA, "figures", ["p101-f01"])
    monkeypatch.setattr(runner, "launch", lambda *args: pytest.fail("cached success relaunched model"))
    two, second = runner.invoke("board", "batch-000", [dict(id="crop", image=str(picture))], "prompt", r.BOARD_SCHEMA, "figures", ["p101-f01"])
    assert one == two and first["cache_key"] == second["cache_key"]
    assert calls == [1]


def test_frozen_old_final_objects_and_p92_are_content_identical():
    runner = r.Runner(r.DEFAULT_BOOK, Path("/tmp/ishida-offline-unused"), r.DEFAULT_OLD)
    old = runner.old_results()
    assert len(old["figures"]) == 266
    merged = r.merge_figures(old["figures"], [dict(id="p101-f01")])
    assert r.canonical_hash(merged[:266]) == r.canonical_hash(old["figures"])
    p92 = next(f for f in merged if f["id"] == "p092-f03")
    assert p92["result"]["payload"]["labels"]["2,18"] == "95"
    assert p92["result"]["payload"]["shapes"]["1,5"] == "triangle"
    assert p92["review_crop"].endswith("with-caption.png")
    assert "94＝白80" in p92["result"]["notes"]
    p11 = next(f for f in merged if f["id"] == "p011-f01")
    assert p11["result"]["payload"]["stones"]["B"][0] == [14, 2]


def test_coverage_tracks_split_extra_and_missing_reasons():
    pages = [dict(page=101, references=[dict(label="1图"), dict(label="2图")],
                  reference_pointers=["/one", "/two"], detection_notes="no second diagram",
                  unrepresented_references=[dict(ref_index=2, reason="prose-only reference")])]
    figures = [dict(id="p101-f01", page=101, ref_index=1),
               dict(id="p101-f02", page=101, ref_index=1),
               dict(id="p101-f03", page=101, ref_index=0, detection_notes="unlisted variation")]
    coverage = r.coverage_report(pages, figures)
    assert coverage["baseline_references"] == 2
    assert coverage["covered_references"] == 1
    assert coverage["missing"][0]["reason"] == "prose-only reference"
    assert coverage["splits"][0]["figure_ids"] == ["p101-f01", "p101-f02"]
    assert coverage["extras"][0]["figure_id"] == "p101-f03"


def test_full_caption_and_page_image_indices_are_unambiguous():
    figure = dict(id="p101-f01", label="1图", text="全文" * 6000, page_context="图下注记93=△",
                  crop="assets/figures/p101-f01.png", page=101, input_image="page.png")
    items, prompt = r.recognition_inputs([figure], Path("/output"))
    assert len(items) == 2
    assert "全文" * 6000 in prompt
    assert '"diagram_image": 1' in prompt
    assert '"full_page_image": 2' in prompt
    assert "93=△" in prompt


def test_old_pages_are_never_sent_to_model(tmp_path, monkeypatch):
    runner = r.Runner(r.DEFAULT_BOOK, tmp_path, r.DEFAULT_OLD)
    monkeypatch.setattr(runner, "launch", lambda *args: pytest.fail("old page model request"))
    with pytest.raises(ValueError, match="outside authorized"):
        runner.invoke("board", "bad", [], "prompt", r.BOARD_SCHEMA, "figures", ["p092-f03"])
