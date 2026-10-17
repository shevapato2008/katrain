#!/usr/bin/env python3
"""Catalog-bound GPT whole-page/whole-diagram recognition, with no database writes.

``prepare`` only inventories sources and renders missing PDF pages. ``all`` runs
complete ten-PDF-page slices and appends JSON progress to progress.jsonl/stdout.
Validated final figures and successful request caches are reused on continuation.
"""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

from PIL import Image

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))
_spec = importlib.util.spec_from_file_location(
    "ishida_recognition_helpers", APP_ROOT / "scripts/recognize_ishida_remaining.py"
)
shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shared)

from katrain.web.tutorials.recognition_catalog_import import normalize_payload

read, write, digest, canonical_hash = shared.read, shared.write, shared.digest, shared.canonical_hash
MODEL, REASONING = shared.MODEL, shared.REASONING
BOARD_SCHEMA, DETECTION_SCHEMA = shared.BOARD_SCHEMA, shared.DETECTION_SCHEMA
COLLECTION = shared.COLLECTION
DEFAULT_CATALOG = COLLECTION / "curriculum/catalog.json"
DEFAULT_OUTPUT_ROOT = COLLECTION / "curriculum/recognition-comparison/curriculum-gpt61sol-v1"
# Every book/process uses these same three OS locks, irrespective of output path.
LOCK_ROOT = Path(tempfile.gettempdir()) / "katrain-tutorial-gpt61sol"
FORMAT = "catalog-gpt-recognition-v1"


@contextmanager
def request_slot(directory=LOCK_ROOT / "requests"):
    """Hold one of exactly three process-wide request slots until launch exits."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    handles = [(directory / f"slot-{number}.lock").open("a+") for number in range(3)]
    acquired = None
    try:
        while acquired is None:
            for handle in handles:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = handle
                    break
                except BlockingIOError:
                    continue
            if acquired is None:
                time.sleep(0.1)
        yield
    finally:
        if acquired is not None:
            fcntl.flock(acquired, fcntl.LOCK_UN)
        for handle in handles:
            handle.close()


def physical_references(book):
    """Keep exact JSON pointers; linked commentary diagrams are not physical refs."""
    refs, descriptions = defaultdict(list), defaultdict(list)

    def walk(value, pointer="", page=None):
        if isinstance(value, dict):
            page = value.get("page", page)
            if value.get("type") == "figure_ref":
                if type(page) is not int or page < 1:
                    raise ValueError(f"physical figure has invalid PDF page at {pointer}")
                refs[page].append((pointer, value))
            elif value.get("type") == "description" and value.get("text") and type(page) is int:
                descriptions[page].append(value["text"])
            for key, nested in value.items():
                if key != "commentary_refs":
                    escaped = key.replace("~", "~0").replace("/", "~1")
                    walk(nested, f"{pointer}/{escaped}", page)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                walk(nested, f"{pointer}/{index}", page)

    walk(book)
    for values in refs.values():
        values.sort(
            key=lambda pair: (
                int(pair[1].get("bbox", {}).get("y_min", 0) * 1000) // 60,
                pair[1].get("bbox", {}).get("x_min", 0),
            )
        )
    return refs, descriptions


def catalog_paths(catalog_path, catalog_id, source_root):
    """Resolve only the selected catalog source, never an arbitrary --book-dir."""
    entries = [entry for entry in read(catalog_path)["books"] if entry["id"] == catalog_id]
    if len(entries) != 1:
        raise ValueError("catalog id must identify exactly one book")
    entry = entries[0]
    root = Path(source_root).resolve()

    def resolve(value):
        path = Path(value)
        if path.is_absolute() and path.is_relative_to(COLLECTION) and root != COLLECTION:
            path = root / path.relative_to(COLLECTION)
        elif not path.is_absolute():
            path = root / path
        path = path.resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"source path unavailable or outside source root: {path}")
        return path

    metadata = entry.get("repo_metadata", {})
    jsons = {resolve(item["path"]) for item in entry.get("files", []) if str(item.get("path", "")).endswith(".json")}
    if metadata.get("json"):
        jsons.add(resolve(metadata["json"]))
    pdfs = {
        resolve(item["path"]) for item in entry.get("files", []) if str(item.get("path", "")).lower().endswith(".pdf")
    }
    pdfs.update(resolve(value) for value in metadata.get("pdfs", []))
    if len(jsons) != 1 or len(pdfs) != 1:
        raise ValueError("catalog source requires one unambiguous PDF and book JSON")
    return entry, jsons.pop(), pdfs.pop()


def recognition_inputs(figures, output):
    """Bind one whole target grid; caption/neighboring diagrams remain context only."""
    images, context = [], []
    for figure in figures:
        bbox = figure["grid_bbox"]
        with Image.open(figure["input_image"]) as image:
            width, height = image.size
            pixels = [
                max(0, int(bbox[0] * width / 1000) - 5),
                max(0, int(bbox[1] * height / 1000) - 5),
                min(width, int(bbox[2] * width / 1000) + 5),
                min(height, int(bbox[3] * height / 1000) + 5),
            ]
            target = Path(output) / "assets/targets" / (figure["id"] + ".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            image.crop(pixels).save(target)
        first = len(images) + 1
        images.extend(
            [
                dict(id=figure["id"] + ":target-grid", image=str(target)),
                dict(id=figure["id"] + ":caption-context", image=str(Path(output) / figure["crop"])),
                dict(id=figure["id"] + ":full-page", image=figure["input_image"]),
            ]
        )
        context.append(
            dict(
                id=figure["id"],
                target_grid_image=first,
                caption_context_image=first + 1,
                full_page_image=first + 2,
                grid_bbox_on_full_page=bbox,
                target_position_notes=figure.get("detection_notes", ""),
                caption=figure["label"],
                detected_full_caption=figure.get("caption", ""),
                existing_book_json_figure_text=figure["text"],
                complete_parsed_page_context=figure["page_context"],
            )
        )
    prompt = shared.LEGACY.recognition_prompt([]).removesuffix("[]")
    prompt = prompt.replace(
        "Each image has one printed diagram. Return exactly one result per supplied id.",
        "For each ID transcribe ONLY target_grid_image, showing the entire designated Go grid (not intersection patches). "
        "caption_context_image contains its printed caption and notes; full_page_image supplies source context. "
        "Those context images may contain NEIGHBORING diagrams: never transcribe their grids/stones as the target. "
        "Use the explicit image indices and grid_bbox_on_full_page to bind each target. "
        "Read all relevant capture/ko/recapture footnotes from caption and full-page context. "
        "If the target grid is incomplete or ambiguous, retain uncertainties instead of extending it or inventing stones. "
        "Return exactly one result per supplied ID.",
    )
    return images, prompt + json.dumps(context, ensure_ascii=False)


class BookRunner(shared.Runner):
    def __init__(
        self,
        catalog_id,
        catalog=DEFAULT_CATALOG,
        output=None,
        *,
        source_root=COLLECTION,
        start=1,
        end=None,
        workers=1,
        timeout=600,
        attempts=2,
    ):
        if catalog_id == "ishida-judgement":
            raise ValueError(
                "ishida-judgement uses its frozen dedicated recognition flow; generic recognition is disabled"
            )
        if workers not in (1, 2) or not 1 <= attempts <= 2 or not 1 <= timeout <= 600:
            raise ValueError("workers must be 1..2, timeout 1..600 and attempts 1..2")
        self.catalog_id = catalog_id
        self.catalog = Path(catalog).resolve()
        self.entry, self.book_json, self.pdf = catalog_paths(self.catalog, catalog_id, source_root)
        self.book = self.book_json.parent.parent
        self.output = Path(output or DEFAULT_OUTPUT_ROOT / catalog_id).resolve()
        if self.output == self.book or self.book in self.output.parents or self.output in self.book.parents:
            raise ValueError("recognition output must be separate from source book")
        for protected in (shared.DEFAULT_OLD, shared.DEFAULT_OUTPUT):
            if self.output == protected.resolve() or protected.resolve() in self.output.parents:
                raise ValueError("legacy final output is immutable; choose a separate output")
        self.start, self.end = start, end
        self.workers, self.timeout, self.attempts = workers, timeout, attempts

    @contextmanager
    def writer_lock(self):
        directory = LOCK_ROOT / "books"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (hashlib.sha256(str(self.book_json).encode()).hexdigest() + ".lock")
        with path.open("a+") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another writer is already processing this source book") from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def event(self, stage, **values):
        value = dict(stage=stage, catalog_id=self.catalog_id, timestamp=time.strftime("%Y-%m-%d %H:%M:%S %z"), **values)
        self.output.mkdir(parents=True, exist_ok=True)
        line = json.dumps(value, ensure_ascii=False)
        with (self.output / "progress.jsonl").open("a") as stream:
            stream.write(line + "\n")
            stream.flush()
        print(line, flush=True)

    def validate_sources(self, data):
        expected = {str(self.pdf): digest(self.pdf), str(self.book_json): digest(self.book_json)}
        if data.get("format") != FORMAT or data.get("catalog_id") != self.catalog_id or data.get("sources") != expected:
            raise ValueError("catalog/source identity changed; use a new output dataset")
        for page in data["pages"]:
            if not Path(page["input_image"]).is_file() or digest(page["input_image"]) != page["page_sha256"]:
                raise ValueError(f"source page image changed: {page['id']}")

    def prepare(self):
        path = self.output / "source.json"
        if path.exists():
            data = read(path)
            self.validate_sources(data)
            self.end = self.end or data["pdf_pages"]
            self.check_range(data["pdf_pages"])
            return data
        if (self.output / "results.json").exists():
            raise ValueError("existing final without generic source identity is immutable")
        info = subprocess.run(["pdfinfo", str(self.pdf)], check=True, capture_output=True, text=True).stdout
        match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
        if not match:
            raise ValueError("cannot determine complete PDF page count")
        total = int(match[1])
        self.end = self.end or total
        self.check_range(total)
        book = read(self.book_json)
        source_hashes = {str(self.pdf): digest(self.pdf), str(self.book_json): digest(self.book_json)}
        refs, descriptions = physical_references(book)
        if set(refs) - set(range(1, total + 1)):
            raise ValueError("canonical references point outside complete PDF page range")
        pages = []
        existing = {}
        for image_path in sorted((self.book_json.parent / "pages").glob("page_*.png")):
            number = re.fullmatch(r"page_(\d{3,})\.png", image_path.name)
            if number:
                number = int(number[1])
                if number in existing:
                    raise ValueError("duplicate source image for one PDF page")
                existing[number] = image_path.resolve()
        for number in range(1, total + 1):
            image_path = existing.get(number)
            rendered = image_path is None
            if rendered:
                image_path = self.output / "assets/pages" / f"page_{number:03d}.png"
                if not image_path.exists():
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run(
                        [
                            "pdftoppm",
                            "-f",
                            str(number),
                            "-l",
                            str(number),
                            "-r",
                            "120",
                            "-singlefile",
                            "-png",
                            str(self.pdf),
                            str(image_path.with_suffix("")),
                        ],
                        check=True,
                        capture_output=True,
                    )
            with Image.open(image_path) as image:
                width, height = image.size
            ordered = refs[number]
            pages.append(
                dict(
                    page=number,
                    id=f"p{number:03d}",
                    input_image=str(image_path),
                    page_sha256=digest(image_path),
                    width=width,
                    height=height,
                    source=quote(os.path.relpath(image_path, self.output)),
                    rendered_missing_source=rendered,
                    render_provenance=(
                        dict(
                            pdf=str(self.pdf),
                            pdf_sha256=source_hashes[str(self.pdf)],
                            pdf_page=number,
                            renderer="pdftoppm",
                            dpi=120,
                        )
                        if rendered
                        else None
                    ),
                    references=[pair[1] for pair in ordered],
                    reference_pointers=[pair[0] for pair in ordered],
                    descriptions=descriptions[number],
                    figure_ids=[],
                )
            )
        data = dict(
            format=FORMAT,
            catalog_id=self.catalog_id,
            title=self.entry.get("title") or book["title"],
            author=self.entry.get("author", book.get("author")),
            translator=book.get("translator"),
            model=MODEL,
            reasoning=REASONING,
            pdf_pages=total,
            baseline_references=sum(map(len, refs.values())),
            pages=pages,
            sources=source_hashes,
        )
        write(path, data)
        self.event(
            "prepare",
            pdf_pages=total,
            baseline_references=data["baseline_references"],
            rendered_missing_pages=sum(page["rendered_missing_source"] for page in pages),
            workers=self.workers,
            model=MODEL,
            reasoning=REASONING,
            requested_range=[self.start, self.end],
        )
        return data

    def check_range(self, total):
        if not (1 <= self.start <= self.end <= total):
            raise ValueError("requested page range is outside PDF")

    def launch(self, *args):
        with request_slot():
            return super().launch(*args)

    def invoke(self, kind, stem, images, prompt, schema, root, ids):
        for ident in ids:
            match = re.fullmatch(r"p(\d{3,})(?:-f\d+)?", ident)
            if not match or not self.start <= int(match[1]) <= self.end:
                raise ValueError("model request outside selected PDF range")
        # The legacy schema reuses STRING/INTEGER dicts across fields. JSON copy
        # deliberately breaks those aliases before constraining only the ID.
        schema = json.loads(json.dumps(schema))
        schema["properties"][root]["items"]["properties"]["id"]["enum"] = ids
        hashes = [dict(id=item["id"], sha256=digest(item["image"])) for item in images]
        # Include the v2 conversion contract in addition to the model response schema.
        key = canonical_hash(dict(request=shared.cache_key(prompt, schema, hashes), payload_contract=2))
        directory = self.output / "raw" / kind / stem / key
        meta_path, result_path = directory / "meta.json", directory / "result.json"

        def validate(value):
            shared.validate_response(value, root, ids, schema)
            self.check_reference_indices(value, root)
            if kind == "recheck":
                pages = {page["id"]: page for page in read(self.output / "source.json")["pages"]}
                for page in value["pages"]:
                    covered = {figure["ref_index"] for figure in page["figures"]}
                    explained = {
                        item["ref_index"] for item in page["unrepresented_references"] if item["reason"].strip()
                    }
                    missing = set(range(1, len(pages[page["id"]]["references"]) + 1)) - covered - explained
                    if missing:
                        raise ValueError(
                            f"{page['id']}: unexplained canonical references after recheck: {sorted(missing)}"
                        )
            if root == "figures":
                for board in value[root]:
                    normalize_payload(dict(result=shared.convert_new(board)))

        if meta_path.exists() and result_path.exists():
            meta, value = read(meta_path), read(result_path)
            validate(value)
            if meta.get("cache_key") == key and meta.get("result_sha256") == digest(result_path):
                self.event("request_cached", kind=kind, ids=ids, cache_key=key)
                return value, meta
        directory.mkdir(parents=True, exist_ok=True)
        write(directory / "schema.json", schema)
        (directory / "prompt.txt").write_text(prompt)
        value, metrics = self.launch(directory, images, prompt, schema, root, ids)
        validate(value)
        write(result_path, value)
        meta = dict(
            cache_key=key,
            model=MODEL,
            reasoning=REASONING,
            image_sha256=hashes,
            schema_sha256=canonical_hash(schema),
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            result_sha256=digest(result_path),
            payload_contract=2,
            **metrics,
        )
        write(meta_path, meta)
        self.event("request_complete", kind=kind, ids=ids, cache_key=key, **metrics)
        return value, meta

    def jobs(self, stage, jobs, schema, root):
        checkpoint = dict(jobs=[], failures=[], model=MODEL)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(
                    self.invoke, stage, job["stem"], job["images"], job["prompt"], schema, root, job["ids"]
                ): job
                for job in jobs
            }
            for future in as_completed(futures):
                job = futures[future]
                try:
                    response, meta = future.result()
                    checkpoint["jobs"].append(
                        dict(stem=job["stem"], ids=job["ids"], response=response, cache_key=meta["cache_key"])
                    )
                except Exception as error:
                    failure = dict(ids=job["ids"], error=f"{type(error).__name__}: {error}")
                    checkpoint["failures"].append(failure)
                    self.event("request_failed", kind=stage, **failure)
        return checkpoint

    def state_path(self, page):
        return self.output / "page-state" / f"p{page:03d}.json"

    def crop_page(self, page, outcome):
        page = deepcopy(page)
        page.update(
            detection_status="complete",
            detection_notes=outcome["notes"],
            unrepresented_references=outcome["unrepresented_references"],
            detected_count=len(outcome["figures"]),
        )
        figures = []
        found = sorted(outcome["figures"], key=lambda f: (f["grid_bbox"][1] // 60, f["grid_bbox"][0]))
        with Image.open(page["input_image"]) as image:
            for rank, located in enumerate(found, 1):
                ident = f"p{page['page']:03d}-f{rank:02d}"
                box = located["input_bbox"]
                pixels = [
                    max(0, int(box[0] * page["width"] / 1000) - 5),
                    max(0, int(box[1] * page["height"] / 1000) - 5),
                    min(page["width"], int(box[2] * page["width"] / 1000) + 5),
                    min(page["height"], int(box[3] * page["height"] / 1000) + 5),
                ]
                destination = self.output / "assets/figures" / f"{ident}.png"
                destination.parent.mkdir(parents=True, exist_ok=True)
                image.crop(pixels).save(destination)
                index = located["ref_index"]
                ref = page["references"][index - 1] if index else {}
                figures.append(
                    dict(
                        id=ident,
                        page=page["page"],
                        label=located["label"] or ref.get("label", ident),
                        ref_index=index,
                        source_pointer=page["reference_pointers"][index - 1] if index else None,
                        title=ref.get("title", ""),
                        text=ref.get("text", ""),
                        page_context="\n\n".join(
                            page["descriptions"] + [f.get("text", "") for f in page["references"]]
                        ),
                        caption=located["caption"],
                        grid_bbox=located["grid_bbox"],
                        input_bbox=located["input_bbox"],
                        bbox=dict(zip(("x_min", "y_min", "x_max", "y_max"), [x / 1000 for x in located["grid_bbox"]])),
                        bbox_pixels=pixels,
                        crop=str(destination.relative_to(self.output)),
                        crop_sha256=digest(destination),
                        input_image=page["input_image"],
                        full_page_sha256=page["page_sha256"],
                        detection_notes=located["notes"],
                    )
                )
        page["figure_ids"] = [figure["id"] for figure in figures]
        return dict(page=page, figures=figures)

    def detect_prompt(self, pages, previous=None):
        return super().detect_prompt(pages, previous) + (
            "\nWhite gutters, teaching subdivisions or broken grid lines alone do not make separate diagrams. "
            "A single board divided to teach corners, sides and center remains ONE complete teaching diagram. "
            "Split only when independent board boundaries, independent positions/captions or prose establish separate diagrams."
        )

    def process_batch(self, pages):
        states, pending = {}, []
        for page in pages:
            path = self.state_path(page["page"])
            if path.exists():
                states[page["id"]] = read(path)
            if states.get(page["id"], {}).get("page", {}).get("detection_status") != "complete":
                pending.append(page)
        groups = [pending[i : i + 4] for i in range(0, len(pending), 4)]
        jobs = [
            dict(
                stem="-".join(p["id"] for p in group),
                ids=[p["id"] for p in group],
                images=[dict(id=p["id"], image=p["input_image"]) for p in group],
                prompt=self.detect_prompt(group),
            )
            for group in groups
        ]
        detected = self.jobs("detect", jobs, DETECTION_SCHEMA, "pages")
        found = {p["id"]: p for job in detected["jobs"] for p in job["response"]["pages"]}
        failures = {ident: failure["error"] for failure in detected["failures"] for ident in failure["ids"]}
        recheck_jobs = []
        for page in pending:
            prior = found.get(page["id"])
            if prior is not None and set(range(1, len(page["references"]) + 1)) - {
                f["ref_index"] for f in prior["figures"]
            }:
                recheck_jobs.append(
                    dict(
                        stem=page["id"],
                        ids=[page["id"]],
                        images=[dict(id=page["id"], image=page["input_image"])],
                        prompt=self.detect_prompt([page], [prior]),
                    )
                )
        rechecked = self.jobs("recheck", recheck_jobs, DETECTION_SCHEMA, "pages")
        found.update({p["id"]: p for job in rechecked["jobs"] for p in job["response"]["pages"]})
        failures.update({ident: failure["error"] for failure in rechecked["failures"] for ident in failure["ids"]})
        for page in pending:
            if page["id"] not in found or page["id"] in failures:
                state = dict(
                    page=dict(
                        page,
                        detection_status="failed",
                        detection_error=failures.get(page["id"], "detection unavailable"),
                    ),
                    figures=[],
                )
            else:
                state = self.crop_page(page, found[page["id"]])
            states[page["id"]] = state
            # Once allocated, physical IDs/crops are frozen, even across failed board retries.
            write(self.state_path(page["page"]), state)
        figures = [
            figure
            for state in states.values()
            for figure in state["figures"]
            if not figure.get("result", {}).get("complete")
        ]
        groups = [figures[i : i + 2] for i in range(0, len(figures), 2)]
        jobs = []
        for group in groups:
            images, prompt = recognition_inputs(group, self.output)
            jobs.append(
                dict(stem="-".join(f["id"] for f in group), ids=[f["id"] for f in group], images=images, prompt=prompt)
            )
        boards = self.jobs("board", jobs, BOARD_SCHEMA, "figures")
        responses = {board["id"]: (board, job) for job in boards["jobs"] for board in job["response"]["figures"]}
        errors = {ident: failure["error"] for failure in boards["failures"] for ident in failure["ids"]}
        for state in states.values():
            for figure in state["figures"]:
                if figure.get("result", {}).get("complete"):
                    continue
                if figure["id"] not in responses:
                    figure["result"] = dict(complete=False, error=errors.get(figure["id"], "recognition unavailable"))
                    figure["needs_review"] = True
                    continue
                board, job = responses[figure["id"]]
                result = shared.convert_new(board)
                result["payload"] = normalize_payload(dict(result=result))
                result["replay_status"] = "needs_calibration"
                figure.update(
                    result=result,
                    model_response=deepcopy(board),
                    needs_review=True,
                    recognition_provenance=dict(
                        model=MODEL,
                        reasoning=REASONING,
                        cache_key=job["cache_key"],
                        batch=job["stem"],
                        input_crop_sha256=figure["crop_sha256"],
                        target_grid_sha256=digest(self.output / "assets/targets" / (figure["id"] + ".png")),
                        full_page_sha256=figure["full_page_sha256"],
                        coordinate_conversion="local_to_full_board_once",
                    ),
                )
            write(self.state_path(state["page"]["page"]), state)

    def assemble(self, source):
        self.validate_sources(source)
        data = deepcopy(source)
        figures, outcomes = [], []
        for index, page in enumerate(data["pages"]):
            path = self.state_path(page["page"])
            state = read(path) if path.exists() else dict(page=page, figures=[])
            data["pages"][index] = state["page"]
            figures.extend(state["figures"])
            failed = [
                dict(id=f["id"], error=f["result"].get("error"))
                for f in state["figures"]
                if not f.get("result", {}).get("complete")
            ]
            detected = state["page"].get("detection_status") == "complete"
            status = "complete" if detected and not failed else "failed" if path.exists() else "not_requested"
            outcomes.append(
                dict(
                    page=page["page"],
                    status=status,
                    detection_status=state["page"].get("detection_status", "not_requested"),
                    detected=len(state["figures"]),
                    zero_diagrams=detected and not state["figures"],
                    notes=state["page"].get("detection_notes", ""),
                    detection_error=state["page"].get("detection_error"),
                    recognition_errors=failed,
                )
            )
        data.update(figures=figures, page_outcomes=outcomes)
        coverage = shared.coverage_report(data["pages"], figures)
        summary = dict(
            pdf_pages=data["pdf_pages"],
            pages_detected=sum(p["detection_status"] == "complete" for p in outcomes),
            pages_recognized_validated=sum(p["status"] == "complete" for p in outcomes),
            figures=len(figures),
            completed=sum(f.get("result", {}).get("complete") is True for f in figures),
            failed_pages=sum(p["status"] == "failed" for p in outcomes),
            pending_pages=sum(p["status"] == "not_requested" for p in outcomes),
            baseline_references=data["baseline_references"],
            uncertain_figures=sum(bool(f.get("result", {}).get("uncertainties")) for f in figures),
            inferred_figures=sum(bool(f.get("result", {}).get("inferences")) for f in figures),
            coverage_missing=len(coverage["missing"]),
        )
        data["summary"] = summary
        index = dict(
            catalog_id=self.catalog_id,
            pdf_pages=data["pdf_pages"],
            baseline_references=data["baseline_references"],
            source_hashes=data["sources"],
            figures={
                f["id"]: dict(
                    page=f["page"],
                    ref_index=f["ref_index"],
                    source_pointer=f["source_pointer"],
                    figure_sha256=canonical_hash(f),
                    reused_final=False,
                )
                for f in figures
            },
        )
        index["content_sha256"] = canonical_hash(index)
        # Preserve the index referenced by each atomic results checkpoint. A
        # process can stop between publishing the public index and results.
        archived_index = self.output / "indexes" / f"{index['content_sha256']}.json"
        write(archived_index, index)
        data["recognition_index_content_sha256"] = index["content_sha256"]
        write(self.output / "recognition-index.json", index)
        data["recognition_index_sha256"] = digest(self.output / "recognition-index.json")
        write(self.output / "results.json", data)
        write(self.output / "coverage.json", dict(**coverage, page_outcomes=outcomes))
        write(
            self.output / "audit.json",
            dict(
                catalog_id=self.catalog_id,
                sources=data["sources"],
                summary=summary,
                sources_unchanged=True,
                usage_from_saved_codex_events=self.usage(),
                accuracy_note="Model transcription and contract validation only; no human review or complete replay claimed.",
            ),
        )
        return data

    def check_existing_final(self):
        path = self.output / "results.json"
        if not path.exists():
            return
        data = read(path)
        self.validate_sources(data)
        index_path = self.output / "recognition-index.json"
        if not index_path.exists() or digest(index_path) != data.get("recognition_index_sha256"):
            content_hash = data.get("recognition_index_content_sha256", "")
            if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
                raise ValueError("immutable final recognition index changed")
            index_path = self.output / "indexes" / f"{content_hash}.json"
            if not index_path.exists() or digest(index_path) != data.get("recognition_index_sha256"):
                raise ValueError("immutable final recognition index changed")
        index = read(index_path)
        for figure in data["figures"]:
            if canonical_hash(figure) != index["figures"].get(figure["id"], {}).get("figure_sha256"):
                raise ValueError("immutable final figure changed")
            if figure.get("result", {}).get("complete"):
                state = read(self.state_path(figure["page"]))
                existing = next((f for f in state["figures"] if f["id"] == figure["id"]), None)
                if existing != figure:
                    raise ValueError("immutable final differs from page checkpoint")
                if normalize_payload(figure) != figure["result"]["payload"]:
                    raise ValueError("final payload is not explicit schema v2")
                if digest(self.output / figure["crop"]) != figure["crop_sha256"]:
                    raise ValueError("immutable final crop changed")

    def run_all(self):
        with self.writer_lock():
            source = self.prepare()
            self.check_existing_final()
            previous = self.output / "results.json"
            completed_pages = (
                {outcome["page"] for outcome in read(previous)["page_outcomes"] if outcome["status"] == "complete"}
                if previous.exists()
                else set()
            )
            pages = [page for page in source["pages"] if self.start <= page["page"] <= self.end]
            data = None
            for offset in range(0, len(pages), 10):
                batch = pages[offset : offset + 10]
                reused_batch = all(page["page"] in completed_pages for page in batch)
                self.process_batch(batch)
                data = self.assemble(source)
                failures = [outcome for outcome in data["page_outcomes"] if outcome["status"] == "failed"]
                self.event(
                    "checkpoint",
                    range=[batch[0]["page"], batch[-1]["page"]],
                    reused_batch=reused_batch,
                    tail=len(batch) < 10,
                    validated_pages=data["summary"]["pages_recognized_validated"],
                    pdf_pages=source["pdf_pages"],
                    independent_figures=data["summary"]["completed"],
                    uncertain_figures=data["summary"]["uncertain_figures"],
                    failed_pages=[failure["page"] for failure in failures],
                    failures=failures,
                    pending_pages=data["summary"]["pending_pages"],
                    import_status="not_imported",
                )
            return data["summary"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "all"))
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--source-root", type=Path, default=COLLECTION)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--workers", type=int, default=1, choices=(1, 2))
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--attempts", type=int, default=2)
    args = parser.parse_args()
    value = BookRunner(
        args.catalog_id,
        args.catalog,
        args.output_dir,
        source_root=args.source_root,
        start=args.start_page,
        end=args.end_page,
        workers=args.workers,
        timeout=args.timeout,
        attempts=args.attempts,
    )
    if args.stage == "prepare":
        with value.writer_lock():
            value.prepare()
        return 0
    summary = value.run_all()
    return int(summary["failed_pages"] > 0 or summary["pending_pages"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
