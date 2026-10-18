"""Append recognition evidence to an existing source registry, preserving current work.

The planner is read only. The writer owns one book transaction, locks the existing
catalog source and real figures, and never overwrites previously touched content.
No table creation, application startup, asset upload, or remote access occurs here.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import copy
import csv
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy import inspect, null, select

from katrain.web.admin.routers.tutorials import _cas_update
from katrain.web.core.models_db import (
    AdminAuditLog,
    BoardPayloadHistory,
    TrainingSample,
    TutorialChapter,
    TutorialFigure,
    TutorialSection,
)
from katrain.web.tutorials.catalog_import import _lock_source
from katrain.web.tutorials.catalog_sources import SOURCE_NAMESPACE
from katrain.web.tutorials.models import StrictBoardPayload
from katrain.web.tutorials.recognition_import import content_sha256, import_candidate
from katrain.web.tutorials.recognition_models import TutorialRecognitionCandidate
from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage


class RecognitionImportError(ValueError):
    """Credential-free input/provenance error suitable for a local report."""


@dataclass
class RecognitionFigure:
    raw: dict
    source_pointer: str | None
    payload: dict | None
    error: str | None = None
    pending_annotation: dict | None = None


@dataclass
class RecognitionInput:
    source_json_sha256: str
    figures: list[RecognitionFigure]
    references: dict[str, dict]
    pages: list[dict]
    source_hashes: dict[str, str]
    coverage_only_pages: list[dict] = field(default_factory=list)
    catalog_id: str | None = None
    pending_annotation: dict | None = None


@dataclass
class RecognitionReport:
    catalog_id: str
    dataset: str
    mode: str
    source_book_id: int
    book_id: int
    source_json_sha256: str
    rows: list[dict] = field(default_factory=list)
    baseline: list[dict] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)
    pending_annotation: dict | None = None

    def as_dict(self):
        value = asdict(self)
        value["counts"] = dict(Counter(row["status"] for row in self.rows))
        value["counts"].update(results=len(self.rows), baseline_references=len(self.baseline), pages=len(self.pages))
        return value


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _references(book, *, physical_only=False):
    by_page = defaultdict(list)

    def walk(value, pointer="", page=None):
        if isinstance(value, dict):
            page = value.get("page", page)
            if value.get("type") == "figure_ref":
                if type(page) is not int or page < 1:
                    raise RecognitionImportError("canonical reference has invalid page")
                by_page[page].append((pointer, value))
            for key, child in value.items():
                if physical_only and key == "commentary_refs":
                    continue
                walk(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"), page)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, pointer + "/" + str(index), page)

    walk(book)
    # Same canonical physical order as the accepted first100 and continuation runner.
    for refs in by_page.values():
        refs.sort(
            key=lambda pair: (
                int(pair[1].get("bbox", {}).get("y_min", 0) * 1000) // 60,
                pair[1].get("bbox", {}).get("x_min", 0),
            )
        )
    return by_page


def validate_p92_sentinel(figures):
    for figure in figures:
        if figure.get("id") != "p092-f03":
            continue
        result = figure.get("result") or {}
        payload = result.get("payload") or {}
        labels, notes = payload.get("labels") or {}, result.get("notes") or ""
        if (
            labels.get("2,18") != "95"
            or labels.get("0,0") != "80"
            or labels.get("1,0") != "91"
            or (payload.get("shapes") or {}).get("1,5") != "triangle"
            or any(number not in notes for number in ("93", "94", "99"))
        ):
            raise RecognitionImportError("p092-f03 corrected95/triangle/capture-note sentinel changed")


def normalize_payload(raw):
    """Wrap the FINAL full-board payload once; never offset or invent chronology."""
    result = raw.get("result") or {}
    if result.get("complete") is not True or not isinstance(result.get("payload"), dict):
        raise RecognitionImportError("recognition did not complete with a static payload")
    return _normalize_static_payload(raw)


def _normalize_static_payload(raw):
    """Validate static evidence; delivery eligibility is checked by its caller."""
    result = raw.get("result") or {}
    if not isinstance(result.get("payload"), dict):
        raise RecognitionImportError("recognition requires a static payload")
    if result.get("issues"):
        raise RecognitionImportError("recognition contains unresolved payload issues")
    payload = copy.deepcopy(result["payload"])
    # Recognizer FINAL coordinates are already global, including its unknown points.
    unknowns = payload.get("unknown_stones", [])
    payload["unknown_stones"] = [
        {"point": point, "color": None} if isinstance(point, list) else point for point in unknowns
    ]
    payload["schema_version"] = 2
    viewport = copy.deepcopy(payload.get("viewport") or result.get("viewport"))
    if not isinstance(viewport, dict):
        raise RecognitionImportError("recognition requires an explicit viewport")
    payload["viewport"] = viewport
    region = {
        "col": viewport["col"],
        "row": viewport["row"],
        "cols": viewport.get("cols", viewport.get("size")),
        "rows": viewport.get("rows", viewport.get("size")),
        "confirmed": False,
    }
    payload["source_region"] = region
    payload["replay"] = {"status": "needs_calibration", "initial": None, "moves": []}
    return StrictBoardPayload.model_validate(payload).model_dump(exclude_unset=True)


# One reviewed source exception, never a general allow-incomplete import mode.
_JOSEKI_PENDING_AUTHORITY_SHA256 = {
    "source_decision": "1ed362b1365f76c3f6268529f806d33cdd46ccc62d8ed031fd653cb0d759978c",
    "source_evidence": "681ebc5a94477a698e67a2bb6a787d10bd9e1d0429f415c35508c7279ec9464b",
    "raw_response": "ab8cc7a7b8fbf85541ff88aa988b408b540a1ad21634ec2f8df8858ee6442060",
}
_JOSEKI_PENDING_FIGURE_SHA256 = {
    "p182-f01": "b67377b630d9827183a3ead38cce716010a5b74e0adcd50b98e9fa1b0372a9da",
    "p182-f02": "6f56c6e09c5cc622ac0864e49a542e3ff2eb606ee996c09dcde51a41d9f4baa2",
}
_OWNERSHIP_HOLD = "Logical ownership unresolved; excluded from ordinary recognition retries."


def _pending_bound_file(binding, *, approved_sha256=None):
    if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
        raise RecognitionImportError("pending annotation requires an explicit file/hash binding")
    path = Path(binding["path"])
    if (
        not path.is_file()
        or file_sha256(path) != binding.get("sha256")
        or (approved_sha256 is not None and binding.get("sha256") != approved_sha256)
    ):
        raise RecognitionImportError("pending annotation file/hash differs from its bound evidence")
    return path


def _validate_pending_annotations(manifest_path, data, batch, results_path, index_path, *, dataset, expected_pdf_pages):
    """Recompute the finite exception after normal source/index checks, before any DB access."""
    manifest = _read(manifest_path)
    expected_ids = set(_JOSEKI_PENDING_FIGURE_SHA256)
    if (
        manifest.get("format") != "joseki-p182-pending-annotation-v1"
        or manifest.get("catalog_id") != "joseki"
        or data.get("catalog_id") != "joseki"
        or expected_pdf_pages != 290
        or not dataset
        or manifest.get("dataset") != dataset
        or set(manifest.get("figures", {})) != expected_ids
    ):
        raise RecognitionImportError("pending annotation catalog/dataset/exact two-figure scope mismatch")
    if (
        index_path is None
        or manifest.get("results_sha256") != file_sha256(results_path)
        or manifest.get("recognition_index_sha256") != file_sha256(index_path)
        or data.get("recognition_index_sha256") != file_sha256(index_path)
    ):
        raise RecognitionImportError("pending annotation final/index hash mismatch")
    index = _read(index_path)
    if index.get("content_sha256") != content_sha256(
        {k: v for k, v in index.items() if k != "content_sha256"}
    ) or data.get("recognition_index_content_sha256") != index.get("content_sha256"):
        raise RecognitionImportError("pending annotation index content hash mismatch")
    _pending_bound_file(
        manifest.get("source_decision"), approved_sha256=_JOSEKI_PENDING_AUTHORITY_SHA256["source_decision"]
    )
    evidence = _read(
        _pending_bound_file(
            manifest.get("source_evidence"), approved_sha256=_JOSEKI_PENDING_AUTHORITY_SHA256["source_evidence"]
        )
    )
    source_digest = evidence.get("source_manifest_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", str(source_digest)):
        raise RecognitionImportError("approved pending annotation evidence lacks its source manifest hash")
    source = _read(_pending_bound_file(manifest.get("source_manifest"), approved_sha256=source_digest))
    source_pages = source.get("pages", [])
    source_map = {p.get("page"): p for p in source_pages}
    if (
        source.get("catalog_id") != "joseki"
        or source.get("pdf_pages") != 290
        or source.get("sources") != data.get("sources")
        or len(source_pages) != 290
        or set(source_map) != set(range(1, 291))
    ):
        raise RecognitionImportError("pending annotation source inventory is incomplete")
    for page in batch.pages:
        original = source_map.get(page["page"], {})
        if any(
            page.get(k) != original.get(k) for k in ("input_image", "page_sha256", "references", "reference_pointers")
        ):
            raise RecognitionImportError("pending annotation source page binding changed")
    figures = {f.raw["id"]: f for f in batch.figures}
    if {f.raw["id"] for f in batch.figures if f.raw.get("result", {}).get("complete") is not True} != expected_ids or {
        f.raw["id"] for f in batch.figures if f.raw["page"] == 182
    } != expected_ids:
        raise RecognitionImportError("pending annotation requires exactly the two original incomplete targets")
    ledger = _read(_pending_bound_file(manifest.get("logical_coverage")))
    records = ledger.get("records", [])
    if (
        ledger.get("catalog_id") != "joseki"
        or ledger.get("logical_coverage_closed") is not False
        or ledger.get("baseline_references") != data.get("baseline_references")
        or len(records) != len(figures)
        or {r.get("id") for r in records} != set(figures)
    ):
        raise RecognitionImportError("pending annotation logical mapping differs from final targets")
    for record in records:
        item = figures[record["id"]]
        raw = item.raw
        if (
            record.get("status") != ("unresolved" if raw["id"] in expected_ids else "complete")
            or record.get("page") != raw["page"]
            or record.get("label") != raw.get("label")
            or record.get("source_pointer") != item.source_pointer
        ):
            raise RecognitionImportError("pending annotation has another incomplete logical mapping")
    metadata = {
        "manifest_path": str(Path(manifest_path).resolve()),
        "manifest_sha256": file_sha256(manifest_path),
        "manifest": copy.deepcopy(manifest),
        "dataset": dataset,
        "source_inventory_complete": True,
        "independent_figure_mapping_complete": True,
        "static_candidates_validated": len(figures),
        "pending_annotation_figures": 2,
        "recognition_complete": False,
        "logical_coverage_closed": False,
    }
    base = Path(results_path).resolve().parent
    for item in batch.figures:
        raw = item.raw
        result = raw.get("result") or {}
        ident = raw["id"]
        crop = (base / str(raw.get("crop", ""))).resolve()
        target = base / "assets/targets" / (ident + ".png")
        if (
            not crop.is_relative_to(base)
            or not crop.is_file()
            or file_sha256(crop) != raw.get("crop_sha256")
            or not target.is_file()
            or file_sha256(target) != (raw.get("recognition_provenance") or {}).get("target_grid_sha256")
        ):
            raise RecognitionImportError("pending annotation diagram asset/hash mismatch")
        if ident not in expected_ids:
            if (
                item.error
                or result.get("error")
                or raw.get("membership_status") == "unresolved"
                or raw.get("donor_completeness_status") == "unresolved"
            ):
                raise RecognitionImportError("pending annotation does not exempt other diagram errors")
            continue
        record = manifest["figures"][ident]
        if (
            content_sha256(raw) != _JOSEKI_PENDING_FIGURE_SHA256[ident]
            or record.get("figure_sha256") != content_sha256(raw)
            or record.get("payload_sha256") != content_sha256(result.get("payload"))
            or record.get("uncertainties_sha256") != content_sha256(result.get("uncertainties"))
            or raw.get("membership_status") != "unresolved"
            or result.get("complete") is not False
            or result.get("error") != _OWNERSHIP_HOLD
            or result.get("issues")
            or result.get("origin_uncertain") is not False
            or raw.get("needs_review") is not True
            or len(result.get("uncertainties", [])) != 1
        ):
            raise RecognitionImportError("pending annotation differs from the approved figure/payload/hold")
        raw_path = _pending_bound_file(
            record.get("raw_response"), approved_sha256=_JOSEKI_PENDING_AUTHORITY_SHA256["raw_response"]
        )
        position = sorted(expected_ids).index(ident)
        boards = _read(raw_path).get("figures", [])
        if (
            record.get("raw_pointer") != f"/figures/{position}"
            or record.get("raw_uncertainty_pointer") != f"/figures/{position}/uncertainties/0"
            or len(boards) != 2
            or boards[position] != raw.get("model_response")
            or len(boards[position].get("uncertainties", [])) != 1
            or record.get("raw_uncertainty_sha256") != content_sha256(boards[position]["uncertainties"][0])
        ):
            raise RecognitionImportError("pending annotation raw response/pointer changed")
        payload = _normalize_static_payload(raw)
        if payload != result["payload"]:
            raise RecognitionImportError("pending annotation requires unchanged explicit static v2 evidence")
        item.payload, item.error = payload, None
        item.pending_annotation = {
            "manifest_sha256": metadata["manifest_sha256"],
            "hold": result["error"],
            "evidence": copy.deepcopy(record),
            "recognition_complete": False,
        }
    return metadata


def _load_recognition(
    results_path,
    book_json_path,
    *,
    index_path=None,
    accepted_first100_path=None,
    physical_only=False,
    ishida_sentinel=True,
):
    """Validate all source/index/frozen evidence before opening a database transaction."""
    data, book = _read(results_path), _read(book_json_path)
    source_hash = file_sha256(book_json_path)
    hashes = data.get("sources")
    if not isinstance(hashes, dict) or not hashes:
        raise RecognitionImportError("missing source hash manifest")
    expected = hashes.get(str(Path(book_json_path))) or hashes.get(str(Path(book_json_path).resolve()))
    if expected != source_hash:
        raise RecognitionImportError("canonical book source hash mismatch")
    for path, digest in hashes.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)) or not Path(path).is_file() or file_sha256(path) != digest:
            raise RecognitionImportError("source hash manifest mismatch or unavailable source")
    figures = data.get("figures")
    pages = data.get("pages")
    if not isinstance(figures, list) or not isinstance(pages, list):
        raise RecognitionImportError("results require figures and page outcomes")
    ids = [figure.get("id") for figure in figures]
    if any(not isinstance(ident, str) or not re.fullmatch(r"p\d{3,4}-f\d+", ident) for ident in ids) or len(
        set(ids)
    ) != len(ids):
        raise RecognitionImportError("missing/duplicate/invalid physical recognition id")
    page_map = {page["page"]: page for page in pages}
    if len(page_map) != len(pages):
        raise RecognitionImportError("duplicate page outcome")
    refs = _references(book, physical_only=physical_only)
    references = {
        pointer: {"page": page, "raw": reference} for page, group in refs.items() for pointer, reference in group
    }
    pages = copy.deepcopy(pages)
    page_map = {page["page"]: page for page in pages}
    for number, page in page_map.items():
        image_path, image_hash = page.get("input_image"), page.get("page_sha256")
        if image_path:
            if not Path(image_path).is_file():
                raise RecognitionImportError("source page image unavailable for hash validation")
            actual = file_sha256(image_path)
            if image_hash is not None and image_hash != actual:
                raise RecognitionImportError("source page image hash mismatch")
            image_hash = actual
        if not re.fullmatch(r"[0-9a-f]{64}", str(image_hash)):
            raise RecognitionImportError("source page requires an immutable image hash")
        page["page_sha256"] = image_hash
        canonical = refs[number]
        if page.get("references") != [item[1] for item in canonical]:
            raise RecognitionImportError("canonical page reference order/content mismatch")
        if "reference_pointers" in page and page["reference_pointers"] != [item[0] for item in canonical]:
            raise RecognitionImportError("canonical page reference pointer mismatch")
    if set(refs) - set(page_map):
        raise RecognitionImportError("canonical references have no page outcome")
    if ishida_sentinel:
        validate_p92_sentinel(figures)
    if accepted_first100_path:
        accepted = _read(accepted_first100_path)
        old = accepted.get("figures", [])
        if len(old) != 266 or {p["page"] for p in accepted.get("pages", [])} != set(range(1, 101)):
            raise RecognitionImportError("accepted first100 must contain exactly266 final objects and100 pages")
        validate_p92_sentinel(old)
        current = dict(zip(ids, figures))
        if accepted.get("sources") != hashes or any(current.get(item["id"]) != item for item in old):
            raise RecognitionImportError("immutable accepted first266/source hashes changed")
    index = _read(index_path) if index_path else None
    if index is not None and (index.get("source_hashes") != hashes or set(index.get("figures", {})) != set(ids)):
        raise RecognitionImportError("recognition index source hashes/result identities mismatch")
    normalized = []
    for figure in figures:
        page, ref_index = figure.get("page"), figure.get("ref_index")
        if (
            type(page) is not int
            or page not in page_map
            or type(ref_index) is not int
            or not 0 <= ref_index <= len(refs[page])
            or int(figure["id"].split("-", 1)[0][1:]) != page
        ):
            raise RecognitionImportError("recognition page/reference index mismatch")
        page_hash = page_map[page]["page_sha256"]
        provenance = figure.get("recognition_provenance") or {}
        if any(
            digest != page_hash
            for digest in (figure.get("full_page_sha256"), provenance.get("full_page_sha256"))
            if digest
        ):
            raise RecognitionImportError("recognition full-page image hash mismatch")
        pointer = refs[page][ref_index - 1][0] if ref_index else None
        if index is not None:
            entry = index["figures"][figure["id"]]
            if (
                entry.get("page") != page
                or entry.get("ref_index") != ref_index
                or entry.get("source_pointer") != pointer
                or entry.get("figure_sha256") != content_sha256(figure)
            ):
                raise RecognitionImportError("recognition index content/pointer mismatch")
        try:
            payload, error = normalize_payload(figure), None
        except (ValueError, TypeError, KeyError) as exc:
            payload, error = None, f"invalid_static_candidate: {str(exc)[:1000]}"
            if not (figure.get("result") or {}).get("complete"):
                error = (
                    "recognition_failed: "
                    + str((figure.get("result") or {}).get("error") or "unfinished response")[:1000]
                )
        normalized.append(RecognitionFigure(copy.deepcopy(figure), pointer, payload, error))
    return RecognitionInput(source_hash, normalized, references, copy.deepcopy(pages), copy.deepcopy(hashes))


def load_recognition(results_path, book_json_path, *, index_path=None, accepted_first100_path=None):
    """Original Ishida loader: frozen-final and P92 checks are unchanged."""
    return _load_recognition(
        results_path, book_json_path, index_path=index_path, accepted_first100_path=accepted_first100_path
    )


def load_catalog_recognition(
    results_path,
    book_json_path,
    *,
    catalog_id,
    pdf_path,
    expected_pdf_pages,
    index_path=None,
    dataset=None,
    pending_annotation_manifest=None,
):
    """Load one complete non-Ishida PDF, retaining all coverage without weakening registered pages."""
    if catalog_id == "ishida-judgement":
        raise RecognitionImportError("Ishida requires its existing frozen first100/195-page import policy")
    data = _read(results_path)
    if not catalog_id or data.get("catalog_id") != catalog_id:
        raise RecognitionImportError("recognition catalog identity mismatch")
    if type(expected_pdf_pages) is not int or not 1 <= expected_pdf_pages <= 9999:
        raise RecognitionImportError("independently verified PDF page count required")
    if data.get("pdf_pages") != expected_pdf_pages:
        raise RecognitionImportError("recognition PDF page count mismatch")
    pdf_path = Path(pdf_path).resolve()
    if (data.get("sources") or {}).get(str(pdf_path)) != file_sha256(pdf_path):
        raise RecognitionImportError("recognition PDF source hash mismatch")
    batch = _load_recognition(
        results_path, book_json_path, index_path=index_path, physical_only=True, ishida_sentinel=False
    )
    if {p["page"] for p in batch.pages} != set(range(1, expected_pdf_pages + 1)):
        raise RecognitionImportError("recognition must retain every PDF page outcome")
    if data.get("baseline_references") != len(batch.references):
        raise RecognitionImportError("physical reference baseline mismatch")
    if index_path:
        index = _read(index_path)
        if any(index.get(k) != data.get(k) for k in ("catalog_id", "pdf_pages", "baseline_references")):
            raise RecognitionImportError("recognition index catalog/PDF identity mismatch")
    if pending_annotation_manifest is not None:
        batch.pending_annotation = _validate_pending_annotations(
            pending_annotation_manifest,
            data,
            batch,
            results_path,
            index_path,
            dataset=dataset,
            expected_pdf_pages=expected_pdf_pages,
        )
    outcomes = data.get("page_outcomes", [])
    pending_ids = {f.raw["id"] for f in batch.figures if f.pending_annotation}
    if (
        len(outcomes) != expected_pdf_pages
        or {p.get("page") for p in outcomes} != set(range(1, expected_pdf_pages + 1))
        or any(p.get("status") != ("failed" if pending_ids and p["page"] == 182 else "complete") for p in outcomes)
    ):
        raise RecognitionImportError("generic import requires all PDF pages recognized and validated")
    if pending_ids:
        outcome = next(p for p in outcomes if p["page"] == 182)
        errors = outcome.get("recognition_errors", [])
        if (
            outcome.get("detection_status") != "complete"
            or outcome.get("detection_error") is not None
            or len(errors) != 2
            or {e.get("id") for e in errors} != pending_ids
            or any(e.get("error") != _OWNERSHIP_HOLD for e in errors)
            or any(
                p.get("detection_error")
                or p.get("recognition_errors")
                or p.get("detection_status", "complete") not in ("complete", "reused_final")
                for p in outcomes
                if p["page"] != 182
            )
        ):
            raise RecognitionImportError("pending annotation page has another detection/recognition error")
    by_page = defaultdict(list)
    for figure in batch.figures:
        if figure.error:
            raise RecognitionImportError("generic import contains unvalidated diagram results")
        by_page[figure.raw["page"]].append(figure)
    for page in batch.pages:
        figures = by_page[page["page"]]
        if (
            page.get("detection_status") not in ("complete", "reused_final")
            or page.get("detected_count") != len(figures)
            or len(page.get("figure_ids", [])) != len(figures)
            or set(page.get("figure_ids", [])) != {f.raw["id"] for f in figures}
        ):
            raise RecognitionImportError("PDF page detection/recognition is not complete")
        missing = set(range(1, len(page["references"]) + 1)) - {f.raw["ref_index"] for f in figures}
        reasons = {
            item.get("ref_index")
            for item in page.get("unrepresented_references", [])
            if isinstance(item.get("reason"), str) and item["reason"].strip()
        }
        if missing - reasons:
            raise RecognitionImportError("PDF page has unexplained missing source references")
    source_images = (Path(book_json_path).resolve().parent / "pages").resolve()
    rendered_images = (Path(results_path).resolve().parent / "assets/pages").resolve()
    known_figures = {f.raw["page"] for f in batch.figures}
    registered = []
    for page in batch.pages:
        image_path = Path(page["input_image"]).resolve()
        provenance = page.get("render_provenance") or {}
        original_image = image_path.is_relative_to(source_images)
        original_exists = any((source_images / f"page_{page['page']:0{width}d}.png").exists() for width in (3, 4))
        rendered_missing = (
            page.get("rendered_missing_source") is True
            and image_path.is_relative_to(rendered_images)
            and not original_exists
            and image_path.stem in (f"page_{page['page']:03d}", f"page_{page['page']:04d}")
            and provenance.get("pdf") == str(pdf_path)
            and provenance.get("pdf_sha256") == file_sha256(pdf_path)
            and provenance.get("pdf_page") == page["page"]
            and provenance.get("renderer") == "pdftoppm"
            and provenance.get("dpi") == 120
        )
        if original_image:
            registered.append(page)
        elif (
            rendered_missing
            and page["page"] not in known_figures
            and not page["references"]
            and page.get("detection_status") in ("complete", "reused_final")
            and page.get("detected_count") == 0
            and page.get("figure_ids") == []
        ):
            # Original PNG missing: confirmed blank/cover only. Hashes were still checked above.
            batch.coverage_only_pages.append(dict(page, coverage_only=True))
        else:
            raise RecognitionImportError(
                "unregistered source page contains diagrams or unresolved coverage; register its asset first"
            )
    batch.pages = registered
    batch.catalog_id = catalog_id
    return batch


def create_recognition_table(bind):
    """Explicit CLI guard must run first; create only this one new evidence table."""
    TutorialRecognitionCandidate.__table__.create(bind, checkfirst=True)


def _source(db, batch, catalog_id, *, lock=False):
    if batch.catalog_id is not None and batch.catalog_id != catalog_id:
        raise RecognitionImportError("batch catalog identity differs from target registry")
    query = select(TutorialSourceBook).where(
        TutorialSourceBook.source_namespace == SOURCE_NAMESPACE, TutorialSourceBook.catalog_id == catalog_id
    )
    if lock:
        query = query.with_for_update()
    sources = db.scalars(query.execution_options(populate_existing=True)).all()
    if len(sources) != 1 or sources[0].source_json_sha256 != batch.source_json_sha256:
        raise RecognitionImportError("live source registry identity/hash mismatch")
    return sources[0]


def _protected(db, figure, *, training_table=False):
    if figure.board_payload is not None:
        return "existing_payload"
    if figure.recognition_debug not in (None, {}):
        return "existing_review_or_debug"
    for name in ("narration", "audio_asset", "video_asset", "video_duration_ms", "video_size_bytes"):
        if getattr(figure, name) is not None:
            return "existing_" + name
    if figure.updated_at != figure.created_at:
        return "previously_modified"
    if db.scalar(select(BoardPayloadHistory.id).where(BoardPayloadHistory.figure_id == figure.id).limit(1)):
        return "existing_history"
    if training_table and db.scalar(select(TrainingSample.id).where(TrainingSample.figure_id == figure.id).limit(1)):
        return "existing_training_review"
    return None


def _figure(db, figure_id, book_id, *, lock=False):
    query = (
        select(TutorialFigure)
        .join(TutorialSection, TutorialFigure.section_id == TutorialSection.id)
        .join(TutorialChapter, TutorialSection.chapter_id == TutorialChapter.id)
        .where(TutorialFigure.id == figure_id, TutorialChapter.book_id == book_id)
    )
    if lock:
        query = query.with_for_update(of=TutorialFigure)
    figure = db.scalar(query.execution_options(populate_existing=True))
    if figure is None:
        raise RecognitionImportError("registry/candidate target is not a real figure in its source book")
    return figure


def _supplemental_group(item, reference):
    metadata = reference.source_metadata if reference else {}
    section = metadata.get("section") or {}
    pointer = section.get("pointer")
    if not pointer and item.source_pointer:
        match = re.match(r"(/chapters/\d+/(?:sections/\d+|intro))", item.source_pointer)
        pointer = match[1] if match else item.source_pointer.rsplit("/", 1)[0]
    return pointer or f"page:{item.raw['page']}", section.get("title") or f"第{item.raw['page']}页"


def _supplemental(db, source, item, reference):
    chapter_key = f"rec-source-{source.id}"
    chapters = db.scalars(
        select(TutorialChapter).where(
            TutorialChapter.book_id == source.book_id, TutorialChapter.chapter_number == chapter_key
        )
    ).all()
    if len(chapters) > 1:
        raise RecognitionImportError("ambiguous recognition supplemental chapter")
    chapter = chapters[0] if chapters else None
    if chapter is None:
        orders = db.scalars(select(TutorialChapter.order).where(TutorialChapter.book_id == source.book_id)).all()
        chapter = TutorialChapter(
            book_id=source.book_id,
            chapter_number=chapter_key,
            title="识别补充（待校准）",
            order=max(orders, default=0) + 1,
        )
        db.add(chapter)
        db.flush()
    group, title = _supplemental_group(item, reference)
    section_key = "rec-" + hashlib.sha256(group.encode()).hexdigest()[:24]
    sections = db.scalars(
        select(TutorialSection).where(
            TutorialSection.chapter_id == chapter.id, TutorialSection.section_number == section_key
        )
    ).all()
    if len(sections) > 1:
        raise RecognitionImportError("ambiguous recognition supplemental section")
    section = sections[0] if sections else None
    if section is None:
        orders = db.scalars(select(TutorialSection.order).where(TutorialSection.chapter_id == chapter.id)).all()
        section = TutorialSection(
            chapter_id=chapter.id,
            section_number=section_key,
            title=("识别补充 · " + title)[:256],
            order=max(orders, default=0) + 1,
        )
        db.add(section)
        db.flush()
    page = db.scalar(
        select(TutorialSourcePage).where(
            TutorialSourcePage.source_book_id == source.id, TutorialSourcePage.page == item.raw["page"]
        )
    )
    if page is None:
        raise RecognitionImportError("supplemental figure requires its registered source page")
    label = item.raw.get("label") or item.raw["id"]
    if len(label) > 32:
        raise RecognitionImportError("supplemental figure label exceeds catalog limit")
    orders = db.scalars(select(TutorialFigure.order).where(TutorialFigure.section_id == section.id)).all()
    figure = TutorialFigure(
        section_id=section.id,
        page=item.raw["page"],
        figure_label=label,
        book_text=item.raw.get("text"),
        page_context_text=page.page_context_text,
        bbox=copy.deepcopy(item.raw.get("bbox")),
        page_image_path=page.page_image_path,
        board_payload=null(),
        recognition_debug=null(),
        order=max(orders, default=0) + 1,
    )
    db.add(figure)
    db.flush()
    return figure


def _run(db, batch, *, catalog_id, dataset, apply=False, actor="system:recognition-import"):
    if not dataset or len(dataset) > 128:
        raise RecognitionImportError("dataset must be a stable nonempty identity of at most128 characters")
    if batch.pending_annotation and batch.pending_annotation["dataset"] != dataset:
        raise RecognitionImportError("pending annotation dataset differs from its verified manifest")
    if apply:
        _lock_source(db, catalog_id)
    source = _source(db, batch, catalog_id, lock=apply)
    report = RecognitionReport(
        catalog_id,
        dataset,
        "apply" if apply else "dry_run",
        source.id,
        source.book_id,
        batch.source_json_sha256,
        pages=sorted(copy.deepcopy(batch.pages + batch.coverage_only_pages), key=lambda p: p["page"]),
        pending_annotation=copy.deepcopy(batch.pending_annotation),
    )
    page_query = select(TutorialSourcePage).where(TutorialSourcePage.source_book_id == source.id)
    if apply:
        page_query = page_query.with_for_update()
    live_pages = {page.page: page for page in db.scalars(page_query.execution_options(populate_existing=True))}
    for page in batch.pages:
        registered_page = live_pages.get(page["page"])
        if registered_page is None or registered_page.image_sha256 != page.get("page_sha256"):
            raise RecognitionImportError("live source page provenance/hash mismatch")
    reference_query = select(TutorialSourceFigure).where(TutorialSourceFigure.source_book_id == source.id)
    if apply:
        reference_query = reference_query.with_for_update()
    references = db.scalars(reference_query.execution_options(populate_existing=True)).all()
    by_pointer = defaultdict(list)
    for reference in references:
        by_pointer[reference.source_pointer].append(reference)
    tables = set(inspect(db.get_bind()).get_table_names())
    candidates = (
        db.scalars(
            select(TutorialRecognitionCandidate).where(TutorialRecognitionCandidate.source_book_id == source.id)
        ).all()
        if TutorialRecognitionCandidate.__tablename__ in tables
        else []
    )
    if apply and TutorialRecognitionCandidate.__tablename__ not in tables:
        raise RecognitionImportError("candidate schema missing; use explicit guarded --create-schema")
    existing = {(candidate.dataset, candidate.recognition_id): candidate for candidate in candidates}
    identities = defaultdict(set)
    used_targets = defaultdict(set)
    physical_targets = defaultdict(set)
    physical_pointers = defaultdict(set)
    for candidate in candidates:
        if candidate.source_pointer:
            identities[candidate.source_pointer].add(candidate.recognition_id)
        used_targets[candidate.source_pointer].add((candidate.recognition_id, candidate.figure_id))
        physical_targets[candidate.recognition_id].add(candidate.figure_id)
        physical_pointers[candidate.recognition_id].add(candidate.source_pointer)
    for item in batch.figures:
        if item.source_pointer and not item.error:
            identities[item.source_pointer].add(item.raw["id"])
    for item in batch.figures:
        raw, pointer = item.raw, item.source_pointer
        row = {
            "recognition_id": raw["id"],
            "page": raw["page"],
            "source_pointer": pointer,
            "canonical_source_id": None,
            "source_figure_id": None,
            "figure_id": None,
            "candidate_id": None,
            "status": "failed",
            "protected": False,
            "applied": False,
            "supplemental": False,
            "proposed_new": False,
            "error": item.pending_annotation["hold"] if item.pending_annotation else item.error,
            "pending_annotation": copy.deepcopy(item.pending_annotation),
        }
        report.rows.append(row)
        candidate = existing.get((dataset, raw["id"]))
        if candidate and candidate.source_content_sha256 != content_sha256(raw):
            raise RecognitionImportError("recognition identity has different immutable content")
        if item.error:
            continue
        matches = by_pointer[pointer] if pointer else []
        if len(matches) > 1:
            raise RecognitionImportError("live source pointer is not unique")
        reference = matches[0] if matches else None
        if reference and reference.page != raw["page"]:
            raise RecognitionImportError("live source pointer page mismatch")
        if reference:
            row.update(canonical_source_id=reference.source_figure_id, source_figure_id=reference.id)
        if candidate:
            if (
                candidate.source_content_sha256 != content_sha256(raw)
                or candidate.board_payload != item.payload
                or candidate.source_pointer != pointer
                or candidate.page != raw["page"]
            ):
                raise RecognitionImportError("recognition identity has different immutable content")
            figure = _figure(db, candidate.figure_id, source.book_id, lock=apply)
            row.update(
                figure_id=figure.id,
                candidate_id=candidate.id,
                status="existing",
                supplemental=bool(figure.section.chapter.chapter_number == f"rec-source-{source.id}"),
            )
            continue
        targets = physical_targets[raw["id"]]
        if len(targets) > 1 or (physical_pointers[raw["id"]] and physical_pointers[raw["id"]] != {pointer}):
            raise RecognitionImportError("physical recognition identity has inconsistent real targets/provenance")
        target_id = reference.figure_id if reference else None
        # Distinct physical diagrams sharing a reference never collapse onto one real figure.
        same_physical = next(iter(targets), None)
        if same_physical:
            target_id = same_physical
        elif target_id and any(target == target_id for _, target in used_targets[pointer]):
            target_id = None
        figure = _figure(db, target_id, source.book_id, lock=apply) if target_id else None
        row["supplemental"] = figure is None or figure.section.chapter.chapter_number == f"rec-source-{source.id}"
        row["proposed_new"] = figure is None
        reason = _protected(db, figure, training_table=TrainingSample.__tablename__ in tables) if figure else None
        row.update(
            figure_id=figure.id if figure else None,
            protected=bool(reason),
            protection_reason=reason,
            status="protected" if reason else ("would_create" if figure is None else "would_apply"),
        )
        if item.pending_annotation:
            row["status"] = "candidate_pending"
        if not apply:
            # Reserve this real target for the first physical result in a split group.
            if figure is not None:
                used_targets[pointer].add((raw["id"], figure.id))
            continue
        if figure is None:
            figure = _supplemental(db, source, item, reference)
            row.update(figure_id=figure.id, proposed_new=False)
        candidate = import_candidate(
            db,
            source_book_id=source.id,
            dataset=dataset,
            recognition_id=raw["id"],
            figure_id=figure.id,
            page=raw["page"],
            raw_result=raw,
            board_payload=item.payload,
            source_figure_id=reference.id if reference else None,
            source_pointer=pointer,
        )
        existing[(dataset, raw["id"])] = candidate
        used_targets[pointer].add((raw["id"], figure.id))
        physical_targets[raw["id"]].add(figure.id)
        physical_pointers[raw["id"]].add(pointer)
        row["candidate_id"] = candidate.id
        if (
            reference
            and reference.figure_id is None
            and len(identities[pointer]) == 1
            and (reference.match_reason or "").startswith(
                ("legacy_section_missing", "legacy_chapter_missing", "legacy_intro_missing", "legacy_figure_missing")
            )
        ):
            reference.figure_id = figure.id
            reference.match_reason = "recognition_supplemental_created"
            db.flush()  # CAS expires ORM state; provenance must already be in this transaction.
        # This check is under target row lock, after evidence/link insertion, in the same transaction.
        reason = _protected(db, figure, training_table=TrainingSample.__tablename__ in tables)
        row.update(protected=bool(reason), protection_reason=reason)
        if item.pending_annotation:
            row["status"] = "candidate_pending"
        elif reason:
            row["status"] = "protected"
        else:
            expected = figure.updated_at.isoformat() if figure.updated_at is not None else None
            _cas_update(
                db,
                figure,
                expected,
                {
                    "board_payload": copy.deepcopy(item.payload),
                    "recognition_debug": {
                        "applied_candidate_id": candidate.id,
                        "human_verified": False,
                        "calibration_review": {"board": None, "sequence": None},
                    },
                },
            )
            db.add(
                BoardPayloadHistory(
                    figure_id=figure.id,
                    board_payload=copy.deepcopy(item.payload),
                    changed_by=actor,
                    change_type="recognition",
                )
            )
            row.update(status="applied", applied=True)
        db.add(
            AdminAuditLog(
                actor_realm="admin",
                actor_username=actor,
                action="tutorial.recognition_import",
                target_type="tutorial_figure",
                target_id=figure.id,
                success=True,
                detail=json.dumps(
                    {
                        "dataset": dataset,
                        "recognition_id": raw["id"],
                        "candidate_id": candidate.id,
                        "status": row["status"],
                        "source_pointer": pointer,
                        "pending_annotation": item.pending_annotation,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.flush()
    represented = defaultdict(list)
    for row in report.rows:
        if row["source_pointer"]:
            represented[row["source_pointer"]].append(row["recognition_id"])
    for pointer, canonical in batch.references.items():
        matches = by_pointer[pointer]
        report.baseline.append(
            {
                "source_pointer": pointer,
                "page": canonical["page"],
                "source_figure_id": matches[0].id if len(matches) == 1 else None,
                "figure_id": matches[0].figure_id if len(matches) == 1 else None,
                "recognition_ids": represented[pointer],
                "status": "represented" if represented[pointer] else "missing_recognition",
            }
        )
    return report


def plan_recognition(db, batch, *, catalog_id, dataset):
    with db.no_autoflush:
        return _run(db, batch, catalog_id=catalog_id, dataset=dataset)


def apply_recognition(sessions, batch, *, catalog_id, dataset, actor="system:recognition-import"):
    """One source-book transaction: any CAS, evidence, or audit failure rolls back all."""
    with sessions.begin() as db:
        return _run(db, batch, catalog_id=catalog_id, dataset=dataset, apply=True, actor=actor)


def write_recognition_reports(directory, report):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    value = report.as_dict() if isinstance(report, RecognitionReport) else report
    (directory / "report.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = [
        "recognition_id",
        "page",
        "source_pointer",
        "canonical_source_id",
        "source_figure_id",
        "figure_id",
        "candidate_id",
        "status",
        "protected",
        "protection_reason",
        "applied",
        "supplemental",
        "proposed_new",
        "error",
        "pending_annotation",
    ]
    with (directory / "recognition-figure-map.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(value.get("rows", []))
