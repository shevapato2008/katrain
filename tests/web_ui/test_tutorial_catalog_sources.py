import hashlib
import json

import pytest
from sqlalchemy import UniqueConstraint


def _source(tmp_path, data, *, catalog_id="sample", modules=None, page_numbers=(1, 2, 3)):
    root = tmp_path / "curriculum"
    project = root / "sample-book"
    output = project / "output"
    pages = output / "pages"
    pages.mkdir(parents=True)
    book_json = output / "book.json"
    book_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    for page in page_numbers:
        (pages / f"page_{page:04d}.png").write_bytes(b"png-bytes-" + str(page).encode())
    entry = {
        "id": catalog_id,
        "title": "Catalog title",
        "author": "Catalog author",
        "modules": modules or ["布局基础与方向"],
        "project_dir": str(project),
        "repo_metadata": {"json": str(book_json)},
        "files": [{"kind": "仓库 JSON", "path": str(book_json)}],
    }
    catalog = root / "catalog.json"
    catalog.write_text(json.dumps({"books": [entry]}, ensure_ascii=False), encoding="utf-8")
    return root, project, catalog, entry


def _figure(label="图1", **extra):
    return {
        "type": "figure_ref",
        "label": label,
        "title": "Caption",
        "text": "Black to play",
        "bbox": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.8, "y_max": 0.9},
        **extra,
    }


def _book(chapters=None):
    return {
        "title": "Actual title",
        "author": "Actual author",
        "publication_year": 2001,
        "isbn": "123456",
        "chapters": chapters if chapters is not None else [],
    }


def _load(catalog, root, **kwargs):
    from katrain.web.tutorials.catalog_sources import load_catalog

    return load_catalog(catalog, root, **kwargs)


def test_intro_precedes_sections_and_page_fragments_preserve_text_and_identity(tmp_path):
    data = _book(
        [
            {
                "chapter": "第一章",
                "title": "Chapter title",
                "intro": [
                    {"page": 1, "elements": [{"type": "description", "text": "Intro text"}, _figure()]},
                ],
                "sections": [
                    {
                        "section": "1",
                        "title": "Section title",
                        "pages": [
                            {"page": 1, "elements": [_figure(), {"type": "description", "text": "Section context"}]},
                            {"page": 2, "elements": [{"type": "description", "text": "Text only"}]},
                        ],
                    }
                ],
            }
        ]
    )
    root, _, catalog, _ = _source(tmp_path, data)
    result = _load(catalog, root)[0]
    assert result.error is None
    book = result.book
    chapter = book.chapters[0]
    assert [s.synthetic for s in chapter.sections] == [True, False]
    assert [s.order for s in chapter.sections] == [1, 2]
    assert [f.source_figure_id for f in book.figures] == ["curriculum:sample:p1:o1", "curriculum:sample:p1:o2"]
    assert book.figures[0].pointer == "/chapters/0/intro/0/elements/1"
    assert [f.ordinal for f in book.figures] == [1, 2]
    assert book.figures[0].bbox == data["chapters"][0]["intro"][0]["elements"][1]["bbox"]
    assert [p.page for p in book.pages] == [1, 2, 3]
    page = book.pages[0]
    assert page.page_context_text == "Intro text\nSection context"
    assert [f["kind"] for f in page.text_fragments] == ["description", "figure_ref", "figure_ref", "description"]
    assert page.text_fragments[1]["source_figure_id"] == book.figures[0].source_figure_id
    assert page.text_fragments[2]["section_title"] == "Section title"
    assert book.pages[1].page_context_text == "Text only"
    assert book.pages[2].text_fragments == []
    assert book.pages[2].page_context_text == ""
    assert page.image_sha256 == hashlib.sha256(page.path.read_bytes()).hexdigest()
    assert page.image_md5 == hashlib.md5(page.path.read_bytes()).hexdigest()
    assert book.source_json_sha256 == hashlib.sha256(book.json_path.read_bytes()).hexdigest()
    assert book.source_metadata["original_metadata"]["publication_year"] == 2001
    assert book.source_metadata["original_metadata"]["isbn"] == "123456"
    json.dumps(book.source_metadata)


def test_explicit_indexes_and_commentary_are_links_to_physical_figures(tmp_path):
    data = _book(
        [
            {
                "chapter": "1",
                "title": "",
                "intro": [],
                "sections": [
                    {
                        "section": "1",
                        "title": "",
                        "pages": [
                            {
                                "page": 1,
                                "source_element_indices": [8, 13],
                                "elements": [
                                    _figure(commentary_refs=[{"type": "figure_ref", "page": 1, "element_index": 13}]),
                                    _figure(),
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    )
    root, _, catalog, _ = _source(tmp_path, data)
    result = _load(catalog, root)[0]
    assert result.error is None
    assert len(result.book.figures) == 2
    first, second = result.book.figures
    assert first.source_figure_id == "curriculum:sample:p1:se8"
    assert second.source_figure_id == "curriculum:sample:p1:se13"
    assert first.commentary_refs[0]["source_figure_id"] == second.source_figure_id
    assert first.raw_metadata["commentary_refs"][0] == {"type": "figure_ref", "page": 1, "element_index": 13}


def test_relocation_deduplicates_declared_paths_and_hashes_are_path_independent(tmp_path):
    root, project, catalog, entry = _source(tmp_path, _book())
    before = _load(catalog, root)[0].book
    old_root = str(root)
    relocated = tmp_path / "relocated"
    root.rename(relocated)
    result = _load(relocated / "catalog.json", relocated, original_source_root=old_root)[0]
    assert result.error is None
    assert result.book.project_dir == relocated / project.name
    assert result.book.assets_manifest_sha256 == before.assets_manifest_sha256
    assert result.book.source_json_sha256 == before.source_json_sha256


def test_catalog_duplicates_report_one_outcome_per_entry(tmp_path):
    root, _, catalog, entry = _source(tmp_path, _book())
    second = {**entry, "id": "duplicate"}
    catalog.write_text(json.dumps({"books": [entry, second]}), encoding="utf-8")
    outcomes = _load(catalog, root)
    assert len(outcomes) == 2
    assert outcomes[0].error is None
    assert outcomes[1].duplicate_of == "sample"
    assert outcomes[1].error.code == "duplicate_source"


def test_preserves_actual_three_digit_page_filenames(tmp_path):
    root, project, catalog, _ = _source(tmp_path, _book())
    for image in (project / "output/pages").glob("*.png"):
        image.rename(image.with_name(f"page_{int(image.stem.split('_')[-1]):03d}.png"))
    result = _load(catalog, root)[0]
    assert result.error is None
    assert result.book.pages[0].path.name == "page_001.png"


def test_realpath_guard_rejects_page_symlink_outside_root(tmp_path):
    root, project, catalog, _ = _source(tmp_path, _book())
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    image = project / "output/pages/page_0001.png"
    image.unlink()
    image.symlink_to(outside)
    result = _load(catalog, root)[0]
    assert result.book is None
    assert result.error.code == "outside_source_root"


@pytest.mark.parametrize(
    "catalog_id,modules,expected",
    [
        ("intro", ["入门、规则与第一盘棋", "对杀与局部计算"], "入门"),
        ("guanzi", ["进阶死活与综合技巧"], "官子"),
        ("game", ["打谱、实战分析与复盘"], "中盘"),
    ],
)
def test_categories_follow_primary_module_and_keep_memberships(tmp_path, catalog_id, modules, expected):
    root, _, catalog, _ = _source(tmp_path, _book(), catalog_id=catalog_id, modules=modules)
    book = _load(catalog, root)[0].book
    assert book.category == expected
    assert book.modules == modules
    if catalog_id == "guanzi":
        assert book.source_metadata["category_override"]


@pytest.mark.parametrize(
    "data,code",
    [
        (
            _book([{"chapter": "1", "intro": [], "sections": [], "unhandled": [_figure()]}]),
            "unsupported_figure_structure",
        ),
        (
            _book([{"chapter": "1", "intro": [{"page": 1, "elements": [{"type": "diagram"}]}], "sections": []}]),
            "unsupported_element",
        ),
        (
            _book([{"chapter": "1", "intro": [{"page": 99, "elements": [_figure()]}], "sections": []}]),
            "missing_page_asset",
        ),
        (
            _book([{"chapter": "1", "intro": [{"page": 1, "elements": [_figure("x" * 33)]}], "sections": []}]),
            "field_too_long",
        ),
    ],
)
def test_unsupported_or_incomplete_source_reports_error(tmp_path, data, code):
    root, _, catalog, _ = _source(tmp_path, data)
    result = _load(catalog, root)[0]
    assert result.book is None
    assert result.error.code == code


def test_catalog_corrected_identity_preserves_raw_and_snapshot_metadata(tmp_path):
    root, _, catalog, entry = _source(tmp_path, _book(), catalog_id="intro-up")
    entry["author"] = "李昌镐（著）"
    entry["repo_metadata"]["author"] = "曹薰铉, 李昌镐"
    catalog.write_text(json.dumps({"books": [entry]}, ensure_ascii=False), encoding="utf-8")
    book = _load(catalog, root)[0].book
    assert book.author == "李昌镐（著）"
    assert book.source_metadata["original_metadata"]["author"] == "Actual author"
    assert book.source_metadata["catalog"]["repo_metadata"]["author"] == "曹薰铉, 李昌镐"


def test_publication_year_remains_authoritative_over_directory_hint(tmp_path):
    root, project, catalog, entry = _source(tmp_path, _book())
    moved = project.with_name("sample-book-1997")
    project.rename(moved)
    entry["project_dir"] = str(moved)
    entry["repo_metadata"]["json"] = str(moved / "output/book.json")
    entry["files"][0]["path"] = entry["repo_metadata"]["json"]
    catalog.write_text(json.dumps({"books": [entry]}), encoding="utf-8")
    book = _load(catalog, root)[0].book
    assert book.source_metadata["identity"]["publication_year"] == 2001
    assert book.source_metadata["directory_year_hints"] == [1997]
    assert book.source_metadata["warnings"][0]["code"] == "directory_year_differs"


def test_source_models_have_isolated_tables_and_one_to_one_figure_constraints():
    from katrain.web.core.db import Base
    from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage

    assert TutorialSourceBook.metadata is Base.metadata
    assert TutorialSourceBook.__tablename__ == "tutorial_source_books"
    assert TutorialSourcePage.__tablename__ == "tutorial_source_pages"
    assert next(iter(TutorialSourceBook.__table__.c.book_id.foreign_keys)).column.table.name == "tutorial_books"
    assert next(iter(TutorialSourceFigure.__table__.c.figure_id.foreign_keys)).column.table.name == "tutorial_figures"
    uniques = {
        tuple(c.name for c in constraint.columns)
        for constraint in TutorialSourceFigure.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("source_book_id", "source_figure_id") in uniques
    assert ("source_book_id", "figure_id") in uniques
    assert TutorialSourceFigure.__table__.c.figure_id.nullable
