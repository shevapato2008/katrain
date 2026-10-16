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


@dataclass
class RecognitionInput:
    source_json_sha256: str
    figures: list[RecognitionFigure]
    references: dict[str, dict]
    pages: list[dict]
    source_hashes: dict[str, str]


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

    def as_dict(self):
        value = asdict(self)
        value["counts"] = dict(Counter(row["status"] for row in self.rows))
        value["counts"].update(results=len(self.rows), baseline_references=len(self.baseline), pages=len(self.pages))
        return value


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _references(book):
    by_page = defaultdict(list)

    def walk(value, pointer="", page=None):
        if isinstance(value, dict):
            page = value.get("page", page)
            if value.get("type") == "figure_ref":
                if type(page) is not int or page < 1:
                    raise RecognitionImportError("canonical reference has invalid page")
                by_page[page].append((pointer, value))
            for key, child in value.items():
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


def load_recognition(results_path, book_json_path, *, index_path=None, accepted_first100_path=None):
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
    if any(not isinstance(ident, str) or not re.fullmatch(r"p\d{3}-f\d+", ident) for ident in ids) or len(
        set(ids)
    ) != len(ids):
        raise RecognitionImportError("missing/duplicate/invalid physical recognition id")
    page_map = {page["page"]: page for page in pages}
    if len(page_map) != len(pages):
        raise RecognitionImportError("duplicate page outcome")
    refs = _references(book)
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
            or int(figure["id"][1:4]) != page
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


def create_recognition_table(bind):
    """Explicit CLI guard must run first; create only this one new evidence table."""
    TutorialRecognitionCandidate.__table__.create(bind, checkfirst=True)


def _source(db, batch, catalog_id, *, lock=False):
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
        pages=copy.deepcopy(batch.pages),
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
            "error": item.error,
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
        if reason:
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
    ]
    with (directory / "recognition-figure-map.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(value.get("rows", []))
