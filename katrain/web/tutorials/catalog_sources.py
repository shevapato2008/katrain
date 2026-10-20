"""Read curriculum catalog sources without database access or source mutations.

Physical diagrams are direct elements of chapter intro or section page records.
Nested commentary refs are links, not additional physical diagrams. Per-page
ordinals span all fragments; fragment-local array indexes are never stable IDs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

SOURCE_NAMESPACE = "curriculum"
MODULE_CATEGORIES = {
    "入门、规则与第一盘棋": "入门",
    "棋形与手筋": "中盘",
    "死活": "中盘",
    "对杀与局部计算": "中盘",
    "布局基础与方向": "布局",
    "定式理解与选择": "布局",
    "中盘攻击": "中盘",
    "防守、治孤与腾挪": "中盘",
    "打入、侵消与破空": "中盘",
    "厚势、模样与全局平衡": "中盘",
    "弃子、转换与取舍": "中盘",
    "劫争": "中盘",
    "形势判断与胜负策略": "中盘",
    "官子": "官子",
    "打谱、实战分析与复盘": "中盘",
    "让子棋与教学对局": "中盘",
    "分级练习与阶段测评": "中盘",
    "古谱与围棋文化": "中盘",
    "进阶死活与综合技巧": "中盘",
}
CATEGORY_OVERRIDES = {
    "guanzi": ("官子", "官子谱 retains its catalog memberships and is classified as an endgame reference."),
}
_PAGE_NAME = re.compile(r"page_(\d{3,4})\.png\Z")


class SourceError(ValueError):
    """One source failed validation; callers must report it instead of importing a subset."""

    def __init__(self, code: str, message: str, pointer: str | None = None):
        self.code = code
        self.message = message
        self.pointer = pointer
        super().__init__(f"{code}: {message}" + (f" at {pointer}" if pointer else ""))

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "pointer": self.pointer}


@dataclass
class SourceFigure:
    source_figure_id: str
    pointer: str
    page: int
    chapter_pointer: str
    section_pointer: str
    label: str
    title: str
    text: str
    bbox: dict[str, float]
    ordinal: int
    source_element_index: int
    explicit_source_element_index: bool
    raw_metadata: dict[str, Any]
    page_context_text: str = ""
    commentary_refs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SourceSection:
    number: str
    title: str
    pointer: str
    order: int
    synthetic: bool
    raw_metadata: dict[str, Any]
    figures: list[SourceFigure] = field(default_factory=list)


@dataclass
class SourceChapter:
    number: str
    title: str
    pointer: str
    order: int
    raw_metadata: dict[str, Any]
    sections: list[SourceSection] = field(default_factory=list)


@dataclass
class SourcePage:
    page: int
    path: Path
    image_sha256: str
    image_md5: str
    size_bytes: int
    text_fragments: list[dict[str, Any]] = field(default_factory=list)
    page_context_text: str = ""


@dataclass
class SourceBook:
    catalog_id: str
    category: str
    modules: list[str]
    title: str
    author: str | None
    translator: str | None
    project_dir: Path
    json_path: Path
    pages_dir: Path
    source_json_sha256: str
    assets_manifest_sha256: str
    source_metadata: dict[str, Any]
    chapters: list[SourceChapter]
    pages: list[SourcePage]
    figures: list[SourceFigure]


@dataclass
class SourceOutcome:
    catalog_id: str
    book: SourceBook | None = None
    error: SourceError | None = None
    duplicate_of: str | None = None


def legacy_slugify(text: str) -> str:
    """The existing importer spelling, usable as evidence but never proof of a match."""
    return re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", text.lower())).strip("-") or "book"


def _text(value: Any, name: str, pointer: str, limit: int | None = None, *, nullable: bool = False):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise SourceError("invalid_field", f"{name} must be a string", pointer)
    if limit is not None and len(value) > limit:
        raise SourceError("field_too_long", f"{name} has {len(value)} characters; database limit is {limit}", pointer)
    return value


def _object(value: Any, pointer: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceError("invalid_structure", "Expected an object", pointer)
    return value


def _array(value: Any, pointer: str) -> list:
    if not isinstance(value, list):
        raise SourceError("invalid_structure", "Expected an array", pointer)
    return value


def _page_number(value: Any, pointer: str) -> int:
    if type(value) is not int or value < 0:
        raise SourceError("invalid_page", "Source page must be a nonnegative integer", pointer)
    return value


def _guard(path: Path, source_root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(source_root):
        raise SourceError("outside_source_root", f"Resolved path leaves source root: {path}")
    return resolved


def _resolve_path(value: str, source_root: Path, original_root: Path, *, relative_base: Path | None = None) -> Path:
    path = Path(_text(value, "source path", "catalog"))
    if path.is_absolute():
        # Relocate declared absolute paths before resolving symlinks in the copied tree.
        if path.is_relative_to(original_root):
            path = source_root / path.relative_to(original_root)
    else:
        path = (relative_base or source_root) / path
    return _guard(path, source_root)


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError("unreadable_source", f"Cannot read JSON {path}: {exc}") from exc
    return _object(value, str(path)), raw


def _source_paths(entry: dict, source_root: Path, original_root: Path) -> tuple[Path, Path, Path]:
    project_value = entry.get("project_dir")
    project = _resolve_path(project_value, source_root, original_root) if project_value else None
    declared = []
    repo = _object(entry.get("repo_metadata", {}), "catalog/repo_metadata")
    if repo.get("json"):
        declared.append(repo["json"])
    for item in _array(entry.get("files", []), "catalog/files"):
        item = _object(item, "catalog/files")
        if str(item.get("path", "")).lower().endswith(".json"):
            declared.append(item["path"])
    if not declared and project is not None:
        declared.append(str(project / "output/book.json"))
    if not declared:
        raise SourceError("missing_json_path", "No book JSON path declared")
    paths = {_resolve_path(value, source_root, original_root, relative_base=project) for value in declared}
    if len(paths) != 1:
        raise SourceError("conflicting_json_paths", "Declared book JSON paths resolve to different sources")
    json_path = paths.pop()
    if project is None:
        project = json_path.parent.parent
    if not json_path.is_relative_to(project):
        raise SourceError("conflicting_project_path", "Book JSON is outside its declared project directory")
    pages_dir = _guard(json_path.parent / "pages", source_root)
    return project, json_path, pages_dir


def _pages(pages_dir: Path, source_root: Path) -> tuple[dict[int, SourcePage], str]:
    if not pages_dir.is_dir():
        raise SourceError("missing_page_assets", f"Page directory is missing: {pages_dir}")
    pages = {}
    manifest = []
    for path in sorted(pages_dir.iterdir()):
        if path.suffix.lower() != ".png":
            continue
        match = _PAGE_NAME.fullmatch(path.name)
        if not match:
            raise SourceError("unsupported_page_filename", f"Expected page_000.png or page_0000.png, got {path.name}")
        checked = _guard(path, source_root)
        sha = hashlib.sha256()
        md5 = hashlib.md5(usedforsecurity=False)
        size = 0
        try:
            with checked.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    sha.update(chunk)
                    md5.update(chunk)
                    size += len(chunk)
        except OSError as exc:
            raise SourceError("unreadable_page_asset", f"Cannot read {path}: {exc}") from exc
        page = int(match[1])
        if page in pages:
            raise SourceError("duplicate_page_asset", f"Multiple PNG filenames identify source page {page}")
        pages[page] = SourcePage(page, path, sha.hexdigest(), md5.hexdigest(), size)
        manifest.append(
            {"page": page, "filename": path.name, "size_bytes": size, "sha256": sha.hexdigest(), "md5": md5.hexdigest()}
        )
    if not pages:
        raise SourceError("missing_page_assets", f"No source page PNGs found: {pages_dir}")
    encoded = json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return pages, hashlib.sha256(encoded).hexdigest()


def _bbox(value: Any, pointer: str) -> dict[str, float]:
    value = _object(value, pointer + "/bbox")
    coordinates = {}
    for key in ("x_min", "y_min", "x_max", "y_max"):
        number = value.get(key)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise SourceError("invalid_bbox", f"{key} must be a finite number", pointer)
        coordinates[key] = number
    if not (
        0 <= coordinates["x_min"] < coordinates["x_max"] <= 1 and 0 <= coordinates["y_min"] < coordinates["y_max"] <= 1
    ):
        raise SourceError("invalid_bbox", "Figure bbox must be a nonempty normalized rectangle", pointer)
    return coordinates


def _recursive_figure_pointers(value: Any, pointer: str = "", *, commentary: bool = False):
    """Independent traversal detects physical figures in unsupported structures."""
    if isinstance(value, dict):
        if value.get("type") == "figure_ref":
            yield pointer, commentary
        for key, nested in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from _recursive_figure_pointers(
                nested, pointer + "/" + escaped, commentary=commentary or key == "commentary_refs"
            )
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _recursive_figure_pointers(nested, f"{pointer}/{index}", commentary=commentary)


def _parse_book(entry: dict, project: Path, json_path: Path, pages_dir: Path, source_root: Path) -> SourceBook:
    data, raw = _read_json(json_path)
    catalog_id = _text(entry.get("id"), "catalog id", "catalog/id", 128)
    modules = _array(entry.get("modules", []), "catalog/modules")
    if not modules or any(not isinstance(module, str) for module in modules):
        raise SourceError("unknown_category", "At least one recognized primary module is required")
    category_override = None
    if catalog_id in CATEGORY_OVERRIDES:
        category, category_override = CATEGORY_OVERRIDES[catalog_id]
    else:
        category = MODULE_CATEGORIES.get(modules[0])
        if category is None:
            raise SourceError("unknown_category", f"Unknown primary catalog module: {modules[0]}")
    # The human catalog carries the audited author correction; embedded repo_metadata is only a snapshot.
    title = _text(entry.get("title") or data.get("title"), "title", "/title", 256)
    author = _text(entry.get("author", data.get("author")), "author", "/author", 128, nullable=True)
    translator = _text(data.get("translator"), "translator", "/translator", 128, nullable=True)
    for name, limit in (("title", 256), ("author", 128), ("translator", 128)):
        if name in data:
            _text(data[name], name, "/" + name, limit, nullable=name != "title")
    pages, manifest_sha256 = _pages(pages_dir, source_root)
    chapters = []
    figures = []
    physical_per_page = Counter()
    by_element = defaultdict(list)

    def parse_pages(records, pointer, chapter, section):
        for page_index, record in enumerate(_array(records, pointer)):
            record_pointer = f"{pointer}/{page_index}"
            record = _object(record, record_pointer)
            page_number = _page_number(record.get("page"), record_pointer + "/page")
            if page_number not in pages:
                raise SourceError("missing_page_asset", f"No PNG for source page {page_number}", record_pointer)
            page = pages[page_number]
            elements = _array(record.get("elements"), record_pointer + "/elements")
            indexes = record.get("source_element_indices")
            if indexes is not None:
                indexes = _array(indexes, record_pointer + "/source_element_indices")
                if len(indexes) != len(elements) or any(type(i) is not int or i < 0 for i in indexes):
                    raise SourceError(
                        "invalid_source_indexes", "Source indexes must align with every page element", record_pointer
                    )
            for index, element in enumerate(elements):
                element_pointer = f"{record_pointer}/elements/{index}"
                element = _object(element, element_pointer)
                kind = element.get("type")
                if kind not in {"description", "figure_ref"}:
                    raise SourceError("unsupported_element", f"Unknown page element type: {kind}", element_pointer)
                text = _text(element.get("text", ""), "element text", element_pointer)
                fragment = {
                    "kind": kind,
                    "text": text,
                    "pointer": element_pointer,
                    "chapter_pointer": chapter.pointer,
                    "chapter_number": chapter.number,
                    "chapter_title": chapter.title,
                    "section_pointer": section.pointer,
                    "section_number": section.number,
                    "section_title": section.title,
                    "page_record_pointer": record_pointer,
                    "page_metadata": {k: v for k, v in record.items() if k != "elements"},
                    "raw_metadata": element,
                }
                if kind == "figure_ref":
                    physical_per_page[page_number] += 1
                    ordinal = physical_per_page[page_number]
                    source_index = indexes[index] if indexes is not None else index
                    suffix = f"se{source_index}" if indexes is not None else f"o{ordinal}"
                    source_id = f"{SOURCE_NAMESPACE}:{catalog_id}:p{page_number}:{suffix}"
                    _text(source_id, "source figure id", element_pointer, 256)
                    figure = SourceFigure(
                        source_id,
                        element_pointer,
                        page_number,
                        chapter.pointer,
                        section.pointer,
                        _text(element.get("label", ""), "figure_label", element_pointer, 32),
                        _text(element.get("title", ""), "figure title", element_pointer),
                        text,
                        _bbox(element.get("bbox"), element_pointer),
                        ordinal,
                        source_index,
                        indexes is not None,
                        element,
                    )
                    section.figures.append(figure)
                    figures.append(figure)
                    by_element[(page_number, source_index)].append(figure)
                    fragment.update(source_figure_id=source_id, label=figure.label, title=figure.title)
                page.text_fragments.append(fragment)

    for chapter_index, raw_chapter in enumerate(_array(data.get("chapters"), "/chapters")):
        pointer = f"/chapters/{chapter_index}"
        raw_chapter = _object(raw_chapter, pointer)
        chapter = SourceChapter(
            _text(raw_chapter.get("chapter", str(chapter_index + 1)), "chapter_number", pointer, 32),
            _text(raw_chapter.get("title", ""), "chapter title", pointer, 256),
            pointer,
            chapter_index + 1,
            {k: v for k, v in raw_chapter.items() if k not in {"intro", "sections"}},
        )
        intro = _array(raw_chapter.get("intro", []), pointer + "/intro")
        sections = _array(raw_chapter.get("sections", []), pointer + "/sections")
        # Preserve introductory text as well as introductory diagrams even when normal sections exist.
        if intro or not sections:
            section = SourceSection(
                chapter.number,
                chapter.title,
                pointer + "/intro",
                1,
                True,
                {"synthetic": True, "chapter": raw_chapter.get("chapter"), "title": chapter.title},
            )
            chapter.sections.append(section)
            parse_pages(intro, section.pointer, chapter, section)
        for section_index, raw_section in enumerate(sections):
            section_pointer = f"{pointer}/sections/{section_index}"
            raw_section = _object(raw_section, section_pointer)
            section = SourceSection(
                _text(raw_section.get("section", str(section_index + 1)), "section_number", section_pointer, 32),
                _text(raw_section.get("title", ""), "section title", section_pointer, 256),
                section_pointer,
                len(chapter.sections) + 1,
                False,
                {k: v for k, v in raw_section.items() if k != "pages"},
            )
            chapter.sections.append(section)
            parse_pages(raw_section.get("pages", []), section_pointer + "/pages", chapter, section)
        chapters.append(chapter)

    independent = {pointer for pointer, commentary in _recursive_figure_pointers(data) if not commentary}
    parsed = {figure.pointer for figure in figures}
    if independent != parsed:
        unknown = sorted(independent - parsed)
        raise SourceError(
            "unsupported_figure_structure",
            f"Recursive physical figure count {len(independent)} differs from parsed count {len(parsed)}",
            unknown[0] if unknown else None,
        )
    ids = [figure.source_figure_id for figure in figures]
    if len(set(ids)) != len(ids):
        raise SourceError(
            "duplicate_figure_identity", "Explicit source indexes identify more than one physical diagram"
        )
    for page in pages.values():
        page.page_context_text = "\n".join(
            fragment["text"]
            for fragment in page.text_fragments
            if fragment["kind"] == "description" and fragment["text"]
        )
    for figure in figures:
        figure.page_context_text = pages[figure.page].page_context_text
        for ref in _array(figure.raw_metadata.get("commentary_refs", []), figure.pointer + "/commentary_refs"):
            ref = _object(ref, figure.pointer + "/commentary_refs")
            linked = dict(ref)
            if ref.get("type") == "figure_ref":
                targets = by_element.get((ref.get("page"), ref.get("element_index")), [])
                if len(targets) != 1:
                    raise SourceError(
                        "unresolved_commentary_ref",
                        "Commentary figure ref must resolve to one physical diagram",
                        figure.pointer + "/commentary_refs",
                    )
                linked["source_figure_id"] = targets[0].source_figure_id
            figure.commentary_refs.append(linked)
    original_metadata = {k: v for k, v in data.items() if k != "chapters"}
    directory_year_hints = [int(year) for year in re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", project.name)]
    warnings = []
    publication_year = data.get("publication_year")
    if (
        publication_year is not None
        and directory_year_hints
        and str(publication_year) not in {str(year) for year in directory_year_hints}
    ):
        warnings.append(
            {
                "code": "directory_year_differs",
                "publication_year": publication_year,
                "directory_year_hints": directory_year_hints,
                "message": "Original JSON publication year is retained; directory years are hints.",
            }
        )
    metadata = {
        "source_namespace": SOURCE_NAMESPACE,
        "catalog_id": catalog_id,
        "catalog": entry,
        "original_metadata": original_metadata,
        "modules": modules,
        "category": category,
        "category_override": category_override,
        "project_dir": str(project),
        "json_path": str(json_path),
        "directory_year_hints": directory_year_hints,
        "warnings": warnings,
        "pages_dir": str(pages_dir),
        "physical_figure_count": len(figures),
        "recursive_physical_figure_count": len(independent),
        "identity": {
            name: data[name]
            for name in (
                "title",
                "author",
                "translator",
                "volume",
                "publication_year",
                "publication_date",
                "edition",
                "isbn",
                "publisher",
            )
            if name in data
        },
        "legacy_slug_candidates": list(dict.fromkeys([catalog_id, legacy_slugify(project.name)])),
    }
    return SourceBook(
        catalog_id,
        category,
        list(modules),
        title,
        author,
        translator,
        project,
        json_path,
        pages_dir,
        hashlib.sha256(raw).hexdigest(),
        manifest_sha256,
        metadata,
        chapters,
        sorted(pages.values(), key=lambda page: page.page),
        figures,
    )


def load_catalog(
    catalog_path: str | Path, source_root: str | Path, original_source_root: str | Path | None = None
) -> list[SourceOutcome]:
    """Return an outcome for every catalog book, including validation failures and duplicates.

    source_root is the allowed curriculum directory. original_source_root identifies
    the former curriculum directory when the catalog still declares absolute paths.
    All JSON and page paths are checked after symlink resolution. No DB is imported.
    """
    source_root = Path(source_root).resolve()
    catalog_path = _guard(Path(catalog_path), source_root)
    original_root = Path(original_source_root).absolute() if original_source_root else catalog_path.parent
    catalog, _ = _read_json(catalog_path)
    outcomes = []
    seen_json = {}
    seen_ids = set()
    for index, entry in enumerate(_array(catalog.get("books"), "/books")):
        catalog_id = entry.get("id", f"entry-{index}") if isinstance(entry, dict) else f"entry-{index}"
        outcome = SourceOutcome(str(catalog_id))
        try:
            entry = _object(entry, f"/books/{index}")
            _text(entry.get("id"), "catalog id", f"/books/{index}/id", 128)
            if catalog_id in seen_ids:
                raise SourceError("duplicate_catalog_id", f"Catalog id is repeated: {catalog_id}")
            seen_ids.add(catalog_id)
            project, json_path, pages_dir = _source_paths(entry, source_root, original_root)
            if json_path in seen_json:
                outcome.duplicate_of = seen_json[json_path]
                raise SourceError("duplicate_source", f"Same canonical JSON as catalog book {outcome.duplicate_of}")
            seen_json[json_path] = catalog_id
            outcome.book = _parse_book(entry, project, json_path, pages_dir, source_root)
        except SourceError as exc:
            outcome.error = exc
        outcomes.append(outcome)
    return outcomes
