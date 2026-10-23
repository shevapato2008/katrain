"""Read OGS provenance and export each exercise as an independent SGF."""

from collections import Counter
import copy
import io
import json
from pathlib import PurePosixPath
import zipfile

from sqlalchemy import select

from katrain.core.sgf_parser import SGFNode
from katrain.web.core.models_db import TutorialChapter, TutorialFigure, TutorialSection
from katrain.web.tutorials.ogs_import import SLUG
from katrain.web.tutorials.ogs_models import TutorialOgsStep

LICENSE_NOTICE = "OGS / Online-Go.com contributors · AGPL-3.0. Source and translation revisions are preserved. Adapted for TEST tutorial import; commercial authorization scope remains unconfirmed."


def screenshot_output(value):
    if value is None:
        return None
    key = value["image_path"]
    if not key.startswith(f"tutorial_assets/{SLUG}/") or "\\" in key or ".." in PurePosixPath(key).parts or ":" in key:
        raise ValueError("Invalid OGS screenshot storage key")
    return {k: value[k] for k in ("image_path", "language", "width", "height")}


def course_index(db, book, course):
    rows = db.execute(
        select(TutorialOgsStep.payload["exercise"]["kind"].as_string(), TutorialOgsStep.screenshot).where(
            TutorialOgsStep.course_id == course.id
        )
    ).all()
    kinds = Counter(kind for kind, _ in rows)
    return {
        "book_id": book.id,
        "title": book.title,
        "source": course.catalog["source"],
        "languages": course.catalog["languages"],
        "chapters": course.catalog["chapters"],
        "lessons": course.catalog["lessons"],
        "counts": {
            "chapters": len(course.catalog["chapters"]),
            "lessons": len(course.catalog["lessons"]),
            "steps": len(rows),
            "languages": len(course.catalog["languages"]),
            "screenshots": sum(value is not None for _, value in rows),
            "exercise_kinds": dict(kinds),
            "unsupported": kinds.get("unsupported", 0),
        },
        "license_notice": LICENSE_NOTICE,
    }


def public_course_index(db, book, course, language):
    """Expose the selected locale and navigation facts without translation maps."""
    index = course_index(db, book, course)
    lessons = course.catalog["lessons"]

    def translated(item, key):
        return item.get("translations", {}).get(language, {}).get(
            key, item.get("translations", {}).get("en", {}).get(key, item.get(key, ""))
        )

    return {
        "book_id": index["book_id"],
        "title": index["title"],
        "source": {key: index["source"][key] for key in ("repository", "commit", "locale_version", "license")},
        "languages": index["languages"],
        "chapters": [
            {
                "id": chapter["id"],
                "number": chapter["number"],
                "title": translated(chapter, "title"),
                "lesson_count": sum(lesson["chapter_id"] == chapter["id"] for lesson in lessons),
                "step_count": sum(
                    lesson["step_count"] for lesson in lessons if lesson["chapter_id"] == chapter["id"]
                ),
            }
            for chapter in index["chapters"]
        ],
        "lessons": [
            {
                "id": lesson["id"],
                "chapter_id": lesson["chapter_id"],
                "order": lesson["order"],
                "course_code": lesson["course_code"],
                "route": lesson["route"],
                "title": translated(lesson, "title"),
                "subtext": translated(lesson, "subtext"),
                "step_count": lesson["step_count"],
                "first_page": lesson["first_page"],
            }
            for lesson in lessons
        ],
        "counts": index["counts"],
        "license_notice": index["license_notice"],
    }


def step_output(book_id, step, language):
    payload = copy.deepcopy(step.payload)
    translations = payload.pop("translations")
    selected = translations.get(language)
    effective = language if selected is not None else "en"
    text = copy.deepcopy(translations[effective])
    if effective != language:
        text["fallback"] = True
    screenshot = screenshot_output(step.screenshot)
    return {
        **payload,
        "book_id": book_id,
        "figure_id": step.figure_id,
        "locale": {"requested": language, "effective": effective, "text": text},
        "screenshot": screenshot,
        "screenshot_status": "ready" if screenshot else "pending",
    }


def public_step_output(book_id, step, language):
    """Keep provenance evidence in admin/export while retaining playable data."""
    output = step_output(book_id, step, language)
    keys = (
        "book_id",
        "figure_id",
        "source_id",
        "source_url",
        "lesson_id",
        "step",
        "page",
        "size",
        "initial_player",
        "stones",
        "letters",
        "shapes",
        "viewport",
        "exercise",
        "locale",
        "screenshot",
        "screenshot_status",
    )
    return {key: output[key] for key in keys}


def step_sgf(step, source):
    """SGFNode handles escaping and variations; OGS coordinates are top-left."""
    payload = step.payload

    def coord(point):
        return "" if point is None else chr(97 + point[0]) + chr(97 + point[1])

    english = payload["translations"]["en"]
    root = SGFNode(
        properties={
            "FF": 4,
            "GM": 1,
            "CA": "UTF-8",
            "SZ": payload["size"],
            "PL": payload["initial_player"],
            "GN": english["title"],
            "SO": payload["source_url"],
            "CP": source["license"],
            "C": f"{english['instruction']}\nSource: {payload['source_id']}\nExercise: {json.dumps(payload['exercise'], ensure_ascii=False)}\nIssues: {json.dumps(payload['issues'], ensure_ascii=False)}",
        }
    )
    for color in ("B", "W"):
        root.set_property("A" + color, [coord(p) for p in payload["stones"][color]])
    root.set_property(
        "LB",
        [f"{coord([int(v) for v in key.split(',')])}:{value}" for key, value in payload.get("letters", {}).items()],
    )
    for shape, property_name in {"triangle": "TR", "square": "SQ", "cross": "MA", "circle": "CR"}.items():
        root.set_property(
            property_name,
            [
                coord([int(v) for v in key.split(",")])
                for key, value in payload.get("shapes", {}).items()
                if value == shape
            ],
        )
    tree = payload["exercise"].get("tree")

    def flags(node):
        return f"OGS correct={str(node.get('correct', False)).lower()}; wrong={str(node.get('wrong', False)).lower()}"

    def add_children(parent, node, color):
        for child in node.get("children", []):
            created = SGFNode(parent=parent, properties={color: coord(child["point"]), "C": flags(child)})
            add_children(created, child, "W" if color == "B" else "B")

    if tree:
        root.set_property("C", root.get_property("C") + "\n" + flags(tree))
        add_children(root, tree, payload["initial_player"])
    return root.sgf()


def export_zip(db, book, course):
    rows = db.execute(
        select(TutorialOgsStep, TutorialFigure.section_id, TutorialSection.chapter_id)
        .join(TutorialFigure, TutorialOgsStep.figure_id == TutorialFigure.id)
        .join(TutorialSection, TutorialFigure.section_id == TutorialSection.id)
        .join(TutorialChapter, TutorialSection.chapter_id == TutorialChapter.id)
        .where(TutorialOgsStep.course_id == course.id, TutorialChapter.book_id == book.id)
        .order_by(TutorialOgsStep.page)
    ).all()
    source_bundle = copy.deepcopy(course.catalog)
    source_bundle["steps"] = []
    index = {"book_id": book.id, "source": course.catalog["source"], "license_notice": LICENSE_NOTICE, "steps": []}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for step, section_id, chapter_id in rows:
            path = f"sgf/{step.page:04d}.sgf"
            archive.writestr(path, step_sgf(step, course.catalog["source"]))
            payload = copy.deepcopy(step.payload)
            if step.screenshot:
                payload["screenshot"] = {
                    "path": step.screenshot["image_path"],
                    **{key: step.screenshot[key] for key in ("sha256", "language", "width", "height")},
                }
            source_bundle["steps"].append(payload)
            index["steps"].append(
                {
                    "source_id": step.source_id,
                    "lesson_id": step.payload["lesson_id"],
                    "page": step.page,
                    "book_id": book.id,
                    "chapter_id": chapter_id,
                    "section_id": section_id,
                    "figure_id": step.figure_id,
                    "sgf_path": path,
                }
            )
        archive.writestr("source.json", json.dumps(source_bundle, ensure_ascii=False, indent=2))
        archive.writestr("index.json", json.dumps(index, ensure_ascii=False, indent=2))
        archive.writestr("LICENSE", course.catalog["source"]["license_text"])
        archive.writestr(
            "README.txt",
            LICENSE_NOTICE
            + "\nSource repository: "
            + course.catalog["source"]["repository"]
            + "\nSource revision: "
            + course.source_commit
            + "\nChanges: normalized same-color setup duplicates; mapped tutorial identities; exported each exercise separately. Raw source evidence and all translations are in source.json.\n",
        )
    return output.getvalue()
