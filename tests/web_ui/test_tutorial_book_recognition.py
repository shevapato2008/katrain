"""Offline tests for the catalog-bound runner; never contact a model or database."""

from collections import Counter
import importlib.util
import json
import multiprocessing
from pathlib import Path
import time

from PIL import Image
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/recognize_tutorial_book.py"


def load_runner():
    assert SCRIPT.exists(), "generic recognition runner is not implemented"
    spec = importlib.util.spec_from_file_location("generic_book_recognition", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "collection"
    book = root / "books/fixture"
    pages = book / "output/pages"
    pages.mkdir(parents=True)
    images = [Image.new("RGB", (80, 100), "white") for _ in range(12)]
    pdf = book / "fixture.pdf"
    images[0].save(pdf, save_all=True, append_images=images[1:])
    for number in range(2, 13):
        images[number - 1].save(pages / f"page_{number:03d}.png")
    ref = {
        "type": "figure_ref",
        "label": "1图",
        "text": "capture note",
        "bbox": {"x_min": 0.1, "y_min": 0.1, "x_max": 0.9, "y_max": 0.8},
    }
    linked = dict(ref, page=11)
    first = dict(ref, commentary_refs=[linked])
    data = {
        "title": "fixture",
        "author": "author",
        "chapters": [
            {
                "intro": [{"page": 2, "elements": [first]}],
                "sections": [
                    {"pages": [{"page": 11, "elements": [{"type": "description", "text": "page context"}, ref]}]}
                ],
            }
        ],
    }
    book_json = book / "output/book.json"
    book_json.write_text(json.dumps(data))
    catalog = root / "curriculum/catalog.json"
    catalog.parent.mkdir()
    catalog.write_text(
        json.dumps(
            {
                "books": [
                    {
                        "id": "fixture",
                        "title": "fixture",
                        "project_dir": str(book),
                        "files": [{"path": str(pdf)}, {"path": str(book_json)}],
                        "repo_metadata": {"json": str(book_json), "pdfs": [str(pdf)]},
                    }
                ]
            }
        )
    )
    return root, book, catalog, pdf, book_json


def runner(source, tmp_path, cls=None):
    module = load_runner()
    return (cls or module.BookRunner)("fixture", source[2], tmp_path / "recognition", source_root=source[0])


def test_prepare_full_pdf_missing_pages_and_physical_pointers(source, tmp_path):
    value = runner(source, tmp_path)
    existing = {p: p.read_bytes() for p in (source[1] / "output/pages").glob("*.png")}
    value.prepare()
    data = json.loads((value.output / "source.json").read_text())
    assert data["pdf_pages"] == 12
    assert data["baseline_references"] == 2
    assert data["pages"][1]["reference_pointers"] == ["/chapters/0/intro/0/elements/0"]
    assert data["pages"][10]["reference_pointers"] == ["/chapters/0/sections/0/pages/0/elements/1"]
    assert Path(data["pages"][0]["input_image"]).is_relative_to(value.output / "assets/pages")
    assert not (source[1] / "output/pages/page_001.png").exists()
    assert all(p.read_bytes() == original for p, original in existing.items())
    assert len(data["sources"]) == 2


def test_recursive_reference_walk_excludes_commentary_and_escapes_pointer():
    module = load_runner()
    data = {
        "a/b~": [{"page": 3, "nested": {"type": "figure_ref", "commentary_refs": [{"type": "figure_ref", "page": 4}]}}]
    }
    refs, _ = module.physical_references(data)
    assert list(refs) == [3]
    assert refs[3][0][0] == "/a~1b~0/0/nested"


def fake_runner_class(module, calls):
    class FakeRunner(module.BookRunner):
        def launch(self, directory, images, prompt, schema, root, ids):
            stage = directory.relative_to(self.output / "raw").parts[0]
            calls.append((stage, list(ids)))
            if root == "pages":
                pages = {p["id"]: p for p in module.read(self.output / "source.json")["pages"]}
                response = []
                for ident in ids:
                    found = []
                    for index, ref in enumerate(pages[ident]["references"], 1):
                        if stage == "detect" and ident == "p011":
                            continue  # The independent recheck must recover it.
                        found.append(
                            dict(
                                label=ref["label"],
                                ref_index=index,
                                grid_bbox=[100, 100, 900, 800],
                                input_bbox=[50, 50, 950, 950],
                                caption="whole caption",
                                notes="",
                            )
                        )
                    response.append(dict(id=ident, figures=found, unrepresented_references=[], notes="checked"))
                return {"pages": response}, {"attempts": 1, "elapsed_seconds": 0}
            return {
                "figures": [
                    dict(
                        id=ident,
                        cols=12,
                        rows=17,
                        origin_col=7,
                        origin_row=2,
                        origin_confidence=0.8,
                        black=["0,0"],
                        white=[],
                        unknown_stones=["1,1"],
                        labels=["0,0=7"],
                        marks=[],
                        inferences=[dict(at="0,0", value="7", basis="text", reason="printed")],
                        uncertainties=[dict(at="1,1", reason="color", candidates=["B", "W"])],
                        notes="ko note",
                    )
                    for ident in ids
                ]
            }, {"attempts": 1, "elapsed_seconds": 0}

    return FakeRunner


def test_ten_page_pipeline_accumulates_tail_and_resume_without_model(source, tmp_path):
    module, calls = load_runner(), []
    value = runner(source, tmp_path, fake_runner_class(module, calls))
    value.run_all()
    result = module.read(value.output / "results.json")
    assert result["summary"]["pages_recognized_validated"] == 12
    assert result["summary"]["completed"] == 2
    assert len(result["page_outcomes"]) == 12
    assert result["page_outcomes"][0]["status"] == "complete"
    assert result["page_outcomes"][0]["zero_diagrams"] is True
    figure = result["figures"][0]
    payload = figure["result"]["payload"]
    assert payload["schema_version"] == 2
    assert payload["stones"]["B"] == [[7, 2]]
    assert payload["unknown_stones"] == [{"point": [8, 3], "color": None}]
    assert payload["source_region"]["confirmed"] is False
    assert payload["replay"]["status"] == "needs_calibration"
    assert figure["result"]["uncertainties"][0]["cell"] == "8,3"
    assert figure["model_response"]["uncertainties"][0]["at"] == "1,1"
    events = [json.loads(line) for line in (value.output / "progress.jsonl").read_text().splitlines()]
    batches = [event for event in events if event["stage"] == "checkpoint"]
    assert [event["range"] for event in batches] == [[1, 10], [11, 12]]
    assert batches[0]["validated_pages"] == 10
    assert batches[-1]["tail"] is True
    assert ("recheck", ["p011"]) in calls
    old_count, old_figures = len(calls), result["figures"]
    value.run_all()
    assert len(calls) == old_count
    assert module.read(value.output / "results.json")["figures"] == old_figures
    resumed = [json.loads(line) for line in (value.output / "progress.jsonl").read_text().splitlines()]
    assert all(event["reused_batch"] for event in resumed[len(events) :] if event["stage"] == "checkpoint")
    index = module.read(value.output / "recognition-index.json")
    assert result["recognition_index_sha256"] == module.digest(value.output / "recognition-index.json")
    assert index["content_sha256"] == module.canonical_hash({k: v for k, v in index.items() if k != "content_sha256"})


def test_source_change_refused_before_resume(source, tmp_path):
    value = runner(source, tmp_path)
    value.prepare()
    source[4].write_text(source[4].read_text() + " ")
    with pytest.raises(ValueError, match="source.*changed"):
        value.prepare()


def test_frozen_ishida_is_rejected_by_generic_entry(source, tmp_path):
    module = load_runner()
    with pytest.raises(ValueError, match="frozen|专用"):
        module.BookRunner("ishida-judgement", source[2], tmp_path / "recognition", source_root=source[0])


def test_unexplained_reference_after_recheck_fails_page_only(source, tmp_path):
    module, calls = load_runner(), []
    base = fake_runner_class(module, calls)

    class Unexplained(base):
        def launch(self, directory, images, prompt, schema, root, ids):
            response, metrics = super().launch(directory, images, prompt, schema, root, ids)
            if directory.relative_to(self.output / "raw").parts[0] == "recheck":
                response["pages"][0]["figures"] = []
            return response, metrics

    value = runner(source, tmp_path, Unexplained)
    summary = value.run_all()
    assert summary["pages_recognized_validated"] == 11
    assert summary["failed_pages"] == 1
    result = module.read(value.output / "results.json")
    assert result["page_outcomes"][10]["status"] == "failed"
    assert "unexplained" in result["page_outcomes"][10]["detection_error"]
    assert result["figures"][0]["id"] == "p002-f01"


def test_success_cache_validated_and_reused(source, tmp_path):
    module, calls = load_runner(), []
    value = runner(source, tmp_path, fake_runner_class(module, calls))
    value.prepare()
    page = module.read(value.output / "source.json")["pages"][1]
    args = (
        "detect",
        "p002",
        [{"id": "p002", "image": page["input_image"]}],
        value.detect_prompt([page]),
        module.DETECTION_SCHEMA,
        "pages",
        ["p002"],
    )
    value.invoke(*args)
    value.invoke(*args)
    assert len(calls) == 1


def test_failed_board_retry_keeps_detected_ids_and_completed_finals(source, tmp_path, monkeypatch):
    module, calls = load_runner(), []
    base = fake_runner_class(module, calls)

    class FailsOnce(base):
        failed = False

        def launch(self, directory, images, prompt, schema, root, ids):
            if root == "figures" and ids == ["p002-f01"] and not self.failed:
                self.failed = True
                raise RuntimeError("bounded request failed")
            return super().launch(directory, images, prompt, schema, root, ids)

    value = runner(source, tmp_path, FailsOnce)
    assert value.run_all()["failed_pages"] == 1
    accepted = module.read(value.output / "results.json")["figures"][-1]
    detected = sum(stage in ("detect", "recheck") for stage, _ in calls)
    assemble = value.assemble

    def interrupt_assemble(_):
        raise RuntimeError("interrupted before aggregate checkpoint")

    monkeypatch.setattr(value, "assemble", interrupt_assemble)
    with pytest.raises(RuntimeError, match="interrupted"):
        value.run_all()
    monkeypatch.setattr(value, "assemble", assemble)
    assert value.run_all()["failed_pages"] == 0
    assert sum(stage in ("detect", "recheck") for stage, _ in calls) == detected
    figures = module.read(value.output / "results.json")["figures"]
    assert [figure["id"] for figure in figures] == ["p002-f01", "p011-f01"]
    assert figures[-1] == accepted


def test_resume_after_index_published_before_results(source, tmp_path, monkeypatch):
    module, calls = load_runner(), []
    value = runner(source, tmp_path, fake_runner_class(module, calls))
    value.end = 10
    value.run_all()
    write = module.write

    def interrupted_write(path, data):
        if Path(path).name == "results.json" and data["summary"]["completed"] == 2:
            raise RuntimeError("interrupted after index publication")
        return write(path, data)

    value.end = 12
    monkeypatch.setattr(module, "write", interrupted_write)
    with pytest.raises(RuntimeError, match="index publication"):
        value.run_all()
    monkeypatch.setattr(module, "write", write)
    count = len(calls)
    assert value.run_all()["pages_recognized_validated"] == 12
    assert len(calls) == count


def slot_worker(script, lock_dir, active, maximum):
    spec = importlib.util.spec_from_file_location("slot_runner", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with module.request_slot(Path(lock_dir)):
        with active.get_lock():
            active.value += 1
            maximum.value = max(maximum.value, active.value)
        time.sleep(0.15)
        with active.get_lock():
            active.value -= 1


def test_request_slots_limit_across_processes(tmp_path):
    load_runner()
    context = multiprocessing.get_context("fork")
    active, maximum = context.Value("i", 0), context.Value("i", 0)
    processes = [
        context.Process(target=slot_worker, args=(str(SCRIPT), str(tmp_path), active, maximum)) for _ in range(5)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    assert maximum.value == 3


def test_book_writer_lock_refuses_second_writer(source, tmp_path):
    first, second = runner(source, tmp_path), runner(source, tmp_path)
    with first.writer_lock():
        with pytest.raises(RuntimeError, match="writer"):
            with second.writer_lock():
                pass


def test_recognition_binds_tight_target_caption_and_full_page(source, tmp_path):
    module = load_runner()
    value = runner(source, tmp_path)
    data = value.prepare()
    page = data["pages"][1]
    state = value.crop_page(
        page,
        dict(
            notes="one board",
            unrepresented_references=[],
            figures=[
                dict(
                    label="1图",
                    ref_index=1,
                    grid_bbox=[100, 100, 400, 400],
                    input_bbox=[50, 50, 950, 950],
                    caption="capture note",
                    notes="upper left board",
                )
            ],
        ),
    )
    images, prompt = module.recognition_inputs(state["figures"], value.output)
    assert len(images) == 3
    assert [image["id"].split(":")[-1] for image in images] == ["target-grid", "caption-context", "full-page"]
    with Image.open(images[0]["image"]) as target, Image.open(images[1]["image"]) as caption:
        assert target.width < caption.width and target.height < caption.height
    assert "target_grid_image" in prompt and "caption_context_image" in prompt and "full_page_image" in prompt
    assert "upper left board" in prompt and "capture note" in prompt
