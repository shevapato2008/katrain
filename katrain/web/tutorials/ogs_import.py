"""Append one pinned OGS course. Planning performs no DDL or object writes."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import threading
from types import SimpleNamespace

from sqlalchemy import inspect, select, text

from katrain.web.core.models_db import TutorialBook, TutorialChapter, TutorialFigure, TutorialSection
from katrain.web.tutorials.catalog_import import CatalogImportError
from katrain.web.tutorials.models import StrictBoardPayload
from katrain.web.tutorials.ogs_models import TutorialOgsCourse, TutorialOgsStep

SLUG = "ogs-learn-to-play-go"
TITLE = "OGS 围棋入门与基础练习"
SOURCE_COMMIT = "1c1c2b82d027f7c307ab25886112cf0a6baf680a"
LOCALE_VERSION = "5304fd731af8856a16d198d506111d61"
OGS_TABLES = (TutorialOgsCourse.__table__, TutorialOgsStep.__table__)
_IMPORT_LOCK = threading.Lock()


class OgsImportError(CatalogImportError):
    pass


def _require(condition, message):
    if not condition:
        raise OgsImportError("invalid_bundle", message)


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _point(point, size):
    _require(
        isinstance(point, list) and len(point) == 2 and all(type(n) is int and 0 <= n < size for n in point),
        "Point outside board",
    )


def board_payload(step):
    """Canonical setup; duplicate same-color evidence stays intact in raw_source."""
    stones = {color: [] for color in ("B", "W")}
    occupied = {}
    for color in stones:
        for point in step["stones"].get(color, []):
            _point(point, step["size"])
            previous = occupied.get(tuple(point))
            _require(previous in (None, color), "Initial setup has opposite-color collision")
            if previous is None:
                stones[color].append(point)
                occupied[tuple(point)] = color
    payload = {
        "schema_version": 2,
        "size": step["size"],
        "stones": stones,
        "unknown_stones": [],
        "letters": step.get("letters", {}),
        "shapes": step.get("shapes", {}),
        "replay": {
            "status": "needs_calibration",
            "initial": {
                "stones": stones,
                "unknown_stones": [],
                "known_region": None,
                "to_play": step["initial_player"],
                "letters": step.get("letters", {}),
                "shapes": step.get("shapes", {}),
            },
            "moves": [],
        },
    }
    if step.get("viewport") is not None:
        payload["viewport"] = step["viewport"]
    try:
        return StrictBoardPayload.model_validate(payload).model_dump(exclude_unset=True)
    except (TypeError, ValueError) as exc:
        raise OgsImportError("invalid_board", "Invalid source board payload") from exc


def validate_bundle(bundle, *, require_full=False):
    """Validate pure JSON before any database write, keeping original evidence."""
    _require(isinstance(bundle, dict) and bundle.get("schema_version") == 1, "Expected bundle schema_version=1")
    result = copy.deepcopy(bundle)
    source = result.get("source", {})
    _require(
        source.get("commit") == SOURCE_COMMIT and source.get("locale_version") == LOCALE_VERSION,
        "Unexpected OGS source or locale version",
    )
    _require(
        all(isinstance(source.get(key), str) and source[key] for key in ("repository", "license", "license_text")),
        "Missing source provenance/license",
    )
    if require_full or "content_sha256" in source:
        declared = source.get("content_sha256")
        _require(
            isinstance(declared, str) and re.fullmatch(r"[0-9a-f]{64}", declared),
            "Missing or invalid declared source content checksum",
        )
        _require(declared == _digest(_content(result)), "Declared source content checksum mismatch")
    languages = result.get("languages", [])
    _require(
        isinstance(languages, list)
        and len(languages) == len(set(languages))
        and "en" in languages
        and all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9-]{1,24}", v) for v in languages),
        "Invalid language list",
    )
    chapters, lessons, steps = (result.get(key, []) for key in ("chapters", "lessons", "steps"))
    _require(
        all(isinstance(value, list) and value for value in (chapters, lessons, steps)),
        "Course hierarchy must not be empty",
    )
    chapter_ids = [c["id"] for c in chapters]
    lesson_ids = [l["id"] for l in lessons]
    _require(
        len(set(chapter_ids)) == len(chapter_ids) and len(set(lesson_ids)) == len(lesson_ids),
        "Duplicate hierarchy source identity",
    )
    for chapter in chapters:
        _require(
            isinstance(chapter.get("title"), str)
            and "number" in chapter
            and isinstance(chapter.get("translations"), dict),
            "Invalid chapter",
        )
    for lesson in lessons:
        _require(
            lesson.get("chapter_id") in chapter_ids
            and lesson.get("route") == lesson["id"]
            and type(lesson.get("order")) is int
            and lesson["order"] > 0
            and isinstance(lesson.get("translations"), dict),
            "Invalid lesson",
        )
    source_ids, pages, per_lesson = set(), set(), {key: [] for key in lesson_ids}
    for step in steps:
        _require(
            step.get("lesson_id") in per_lesson and type(step.get("step")) is int and step["step"] > 0,
            "Invalid step identity",
        )
        _require(
            step.get("source_id") == f"ogs-learning:{step['lesson_id']}:{step['step']}"
            and step["source_id"] not in source_ids
            and len(step["source_id"]) <= 256,
            "Duplicate or invalid source_id",
        )
        _require(
            type(step.get("page")) is int and step["page"] > 0 and step["page"] not in pages,
            "Duplicate or invalid page",
        )
        _require(
            step.get("size") in (9, 13, 19)
            and step.get("initial_player") in ("B", "W")
            and isinstance(step.get("stones"), dict)
            and set(step["stones"]) == {"B", "W"},
            "Invalid initial board",
        )
        _require(
            isinstance(step.get("source_url"), str)
            and step["source_url"].startswith("https://online-go.com/learn-to-play-go/"),
            "Invalid source URL",
        )
        _require(
            isinstance(step.get("raw_source"), dict) and isinstance(step.get("issues"), list),
            "Missing raw source evidence",
        )
        translations = step.get("translations", {})
        _require(
            isinstance(translations, dict) and "en" in translations and set(translations) <= set(languages),
            "Invalid step translations",
        )
        for value in translations.values():
            _require(
                isinstance(value, dict)
                and isinstance(value.get("title"), str)
                and isinstance(value.get("instruction"), str),
                "Invalid translated text",
            )
        exercise = step.get("exercise", {})
        _require(
            exercise.get("kind") in {"puzzle", "choice", "pass", "remove", "finish", "unsupported"},
            "Unknown exercise kind",
        )

        def validate_tree(node, depth=0):
            _require(
                isinstance(node, dict)
                and depth <= 200
                and type(node.get("correct")) is bool
                and type(node.get("wrong")) is bool
                and isinstance(node.get("children"), list),
                "Invalid answer tree",
            )
            if node.get("point") is not None:
                _point(node["point"], step["size"])
            for child in node["children"]:
                validate_tree(child, depth + 1)

        if exercise["kind"] == "puzzle":
            validate_tree(exercise.get("tree"))
            _require(exercise["tree"].get("point") is None, "Puzzle root must be a setup node")
        if exercise["kind"] == "choice":
            choices = exercise.get("choices", [])
            values = [c.get("value") for c in choices]
            _require(
                choices
                and all(isinstance(v, str) for v in values)
                and len(set(values)) == len(values)
                and exercise.get("correct_choice") in values,
                "Invalid choice exercise",
            )
        for point in exercise.get("remove_targets", []):
            _point(point, step["size"])
        screenshot = step.get("screenshot")
        if screenshot:
            path = screenshot.get("path", "")
            _require(
                isinstance(path, str)
                and path
                and not PurePosixPath(path).is_absolute()
                and ".." not in PurePosixPath(path).parts
                and "\\" not in path
                and ":" not in path,
                "Invalid screenshot relative path",
            )
            _require(
                re.fullmatch(r"[0-9a-f]{64}", screenshot.get("sha256", ""))
                and all(type(screenshot.get(k)) is int and 0 < screenshot[k] <= 20000 for k in ("width", "height"))
                and screenshot.get("language") in languages,
                "Invalid screenshot metadata",
            )
        board_payload(step)
        source_ids.add(step["source_id"])
        pages.add(step["page"])
        per_lesson[step["lesson_id"]].append(step)
    _require(pages == set(range(1, len(steps) + 1)), "Source pages must be contiguous")
    for lesson in lessons:
        items = per_lesson[lesson["id"]]
        _require(
            len(items) == lesson.get("step_count")
            and {s["step"] for s in items} == set(range(1, len(items) + 1))
            and min(s["page"] for s in items) == lesson.get("first_page"),
            "Lesson step range mismatch",
        )
    if require_full:
        _require(
            (len(chapters), len(lessons), len(steps), len(languages)) == (7, 248, 3551, 32),
            "Full course requires 7 chapters, 248 lessons, 3551 steps and 32 languages",
        )
        for item in [*chapters, *lessons, *steps]:
            _require(set(item["translations"]) == set(languages), "Full course must preserve all 32 translations")
    return result


def _content(bundle):
    result = copy.deepcopy(bundle)
    result["source"].pop("content_sha256", None)
    for step in result["steps"]:
        step.pop("screenshot", None)
    return result


def _mappings(db, course):
    rows = db.execute(
        select(TutorialOgsStep, TutorialFigure, TutorialSection, TutorialChapter)
        .join(TutorialFigure, TutorialOgsStep.figure_id == TutorialFigure.id)
        .join(TutorialSection, TutorialFigure.section_id == TutorialSection.id)
        .join(TutorialChapter, TutorialSection.chapter_id == TutorialChapter.id)
        .where(TutorialOgsStep.course_id == course.id)
        .order_by(TutorialOgsStep.page)
    ).all()
    if any(chapter.book_id != course.book_id for _, _, _, chapter in rows):
        raise OgsImportError("identity_conflict", "Registered OGS figure belongs to another book")
    return [
        {
            "source_id": step.source_id,
            "source_chapter_id": next(
                l["chapter_id"] for l in course.catalog["lessons"] if l["id"] == step.payload["lesson_id"]
            ),
            "lesson_id": step.payload["lesson_id"],
            "page": step.page,
            "book_id": course.book_id,
            "chapter_id": chapter.id,
            "section_id": section.id,
            "figure_id": figure.id,
        }
        for step, figure, section, chapter in rows
    ]


def _plan(db, bundle):
    counts = {
        "chapters": len(bundle["chapters"]),
        "lessons": len(bundle["lessons"]),
        "figures": len(bundle["steps"]),
        "new_figures": 0,
        "screenshots_added": 0,
        "languages": len(bundle["languages"]),
    }
    result = {
        "status": "new",
        "mode": "dry_run",
        "book_id": None,
        "counts": counts,
        "mappings": [],
        "steps": [
            {"source_id": s["source_id"], "page": s["page"], "status": "new", "issues": s["issues"]}
            for s in bundle["steps"]
        ],
        "conflicts": [],
        "created_asset_keys": [],
    }
    book = db.scalar(select(TutorialBook).where(TutorialBook.slug == SLUG))
    tables = set(inspect(db.connection()).get_table_names())
    course = (
        db.scalar(select(TutorialOgsCourse).where(TutorialOgsCourse.book_id == book.id))
        if book and TutorialOgsCourse.__tablename__ in tables
        else None
    )
    if book and not course:
        result.update(status="conflict", book_id=book.id)
        result["conflicts"].append(
            {"code": "unowned_slug", "message": "Existing book slug has no OGS identity; refusing takeover"}
        )
        return result
    if course is None:
        counts["new_figures"] = len(bundle["steps"])
        return result
    result.update(status="unchanged", book_id=book.id, mappings=_mappings(db, course))
    registered = {
        step.source_id: step
        for step in db.scalars(select(TutorialOgsStep).where(TutorialOgsStep.course_id == course.id))
    }
    for item, status in zip(bundle["steps"], result["steps"]):
        original = registered.get(item["source_id"])
        content = {k: v for k, v in item.items() if k != "screenshot"}
        if original is None or original.content_sha256 != _digest(content):
            result["conflicts"].append({"code": "source_content_changed", "source_id": item["source_id"]})
            status["status"] = "conflict"
        elif (
            item.get("screenshot")
            and original.screenshot
            and original.screenshot["sha256"] != item["screenshot"]["sha256"]
        ):
            result["conflicts"].append({"code": "screenshot_changed", "source_id": item["source_id"]})
            status["status"] = "conflict"
        elif item.get("screenshot") and original.screenshot is None:
            status["status"] = "screenshot_pending"
            counts["screenshots_added"] += 1
        else:
            status["status"] = "unchanged"
    if course.content_sha256 != _digest(_content(bundle)) or len(registered) != len(bundle["steps"]):
        if not result["conflicts"]:
            result["conflicts"].append({"code": "catalog_content_changed"})
    if result["conflicts"]:
        result["status"] = "conflict"
    elif counts["screenshots_added"]:
        result["status"] = "enrichment"
    return result


def plan_ogs_course(db, bundle, *, require_full=False):
    return _plan(db, validate_bundle(bundle, require_full=require_full))


def create_ogs_tables(bind):
    """Caller must verify TEST target first; never initialize unrelated metadata."""
    for table in OGS_TABLES:
        table.create(bind, checkfirst=True)


def _attach_screenshot(step, screenshot_root, asset_store, result):
    if not step.get("screenshot"):
        return None
    _require(
        screenshot_root is not None and asset_store is not None,
        "Screenshots require an explicit source root and immutable asset store",
    )
    metadata = step["screenshot"]
    root = Path(screenshot_root).resolve()
    path = (root / metadata["path"]).resolve()
    _require(path.is_relative_to(root) and path.is_file(), "Screenshot leaves source root or is missing")
    data = path.read_bytes()
    _require(hashlib.sha256(data).hexdigest() == metadata["sha256"], "Screenshot checksum mismatch")
    from PIL import Image

    with Image.open(path) as image:
        _require(
            image.format == "PNG" and image.size == (metadata["width"], metadata["height"]),
            "Screenshot dimensions/format mismatch",
        )
    key = f"tutorial_assets/{SLUG}/{metadata['language']}/{metadata['sha256']}.png"
    asset = asset_store.ensure_page(
        key,
        SimpleNamespace(
            path=path, image_sha256=metadata["sha256"], image_md5=hashlib.md5(data).hexdigest(), size_bytes=len(data)
        ),
    )
    if asset.created:
        result["created_asset_keys"].append(key)
    return {
        "image_path": key,
        "sha256": metadata["sha256"],
        "language": metadata["language"],
        "width": metadata["width"],
        "height": metadata["height"],
    }


def import_ogs_course(session_factory, bundle, *, screenshot_root=None, asset_store=None, require_full=False):
    """One atomic course transaction. Caller verifies target and creates only OGS tables."""
    bundle = validate_bundle(bundle, require_full=require_full)
    result = {"mode": "apply", "created_asset_keys": []}
    try:
        return _apply_course(session_factory, bundle, screenshot_root, asset_store, result)
    except Exception as exc:
        error = (
            exc
            if isinstance(exc, CatalogImportError)
            else OgsImportError("ogs_import_failed", "OGS course transaction failed; reconcile before retrying")
        )
        result.update(
            status="failed", orphan_asset_keys=list(result.get("created_asset_keys", [])), error=error.as_dict()
        )
        for step in result.get("steps", []):
            step["status"] = "transaction_failed"
        error.report = result
        if error is exc:
            raise
        raise error from exc


def _apply_course(session_factory, bundle, screenshot_root, asset_store, result):
    with _IMPORT_LOCK, session_factory.begin() as db:
        if db.get_bind().dialect.name == "postgresql":
            lock_key = int.from_bytes(hashlib.sha256(SLUG.encode()).digest()[:8], "big", signed=True)
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        result.update(_plan(db, bundle))
        result["mode"] = "apply"
        if result["status"] == "conflict":
            return result
        if result["status"] == "new":
            book = TutorialBook(
                category="入门",
                subcategory="网页交互教程",
                title=TITLE,
                author="Online-Go.com contributors",
                slug=SLUG,
                asset_dir=f"tutorial_assets/{SLUG}",
            )
            chapters = {
                c["id"]: TutorialChapter(
                    book=book,
                    chapter_number=str(c["number"]),
                    title=c.get("translations", {}).get("zh-cn", {}).get("title", c["title"]),
                    order=i,
                )
                for i, c in enumerate(bundle["chapters"], 1)
            }
            sections = {
                l["id"]: TutorialSection(
                    chapter=chapters[l["chapter_id"]],
                    section_number=l["course_code"],
                    title=l.get("translations", {}).get("zh-cn", {}).get("title", l["title"]),
                    order=l["order"],
                )
                for l in bundle["lessons"]
            }
            figures = {}
            for step in bundle["steps"]:
                translated = step["translations"].get("zh-cn", step["translations"]["en"])
                figures[step["source_id"]] = TutorialFigure(
                    section=sections[step["lesson_id"]],
                    page=step["page"],
                    figure_label=f"Step {step['step']}",
                    book_text=translated["instruction"],
                    board_payload=board_payload(step),
                    order=step["step"],
                )
            db.add(book)
            db.flush()
            course = TutorialOgsCourse(
                book_id=book.id,
                source_commit=bundle["source"]["commit"],
                locale_version=bundle["source"]["locale_version"],
                content_sha256=_digest(_content(bundle)),
                catalog={k: copy.deepcopy(v) for k, v in bundle.items() if k != "steps"},
            )
            db.add(course)
            db.flush()
            for step in bundle["steps"]:
                figure = figures[step["source_id"]]
                content = {k: copy.deepcopy(v) for k, v in step.items() if k != "screenshot"}
                # Normalize the displayed setup while keeping the exact raw source and digest.
                content["stones"] = board_payload(step)["stones"]
                screenshot = _attach_screenshot(step, screenshot_root, asset_store, result)
                if screenshot:
                    figure.page_image_path = screenshot["image_path"]
                    result["counts"]["screenshots_added"] += 1
                db.add(
                    TutorialOgsStep(
                        course_id=course.id,
                        source_id=step["source_id"],
                        page=step["page"],
                        figure_id=figure.id,
                        content_sha256=_digest({k: v for k, v in step.items() if k != "screenshot"}),
                        payload=content,
                        screenshot=screenshot,
                    )
                )
            db.flush()
            result.update(status="imported", book_id=book.id, mappings=_mappings(db, course))
            for item in result["steps"]:
                item["status"] = "imported"
        elif result["status"] == "enrichment":
            course = db.scalar(select(TutorialOgsCourse).where(TutorialOgsCourse.book_id == result["book_id"]))
            rows = {
                s.source_id: s
                for s in db.scalars(select(TutorialOgsStep).where(TutorialOgsStep.course_id == course.id))
            }
            for step, status in zip(bundle["steps"], result["steps"]):
                registered = rows[step["source_id"]]
                if status["status"] != "screenshot_pending":
                    continue
                screenshot = _attach_screenshot(step, screenshot_root, asset_store, result)
                registered.screenshot = screenshot
                figure = db.get(TutorialFigure, registered.figure_id)
                if not figure.page_image_path:
                    figure.page_image_path = screenshot["image_path"]
                status["status"] = "screenshot_added"
            result["status"] = "enriched"
        return result
