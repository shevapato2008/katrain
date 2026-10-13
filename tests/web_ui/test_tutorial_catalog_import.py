"""Incremental catalog imports preserve existing tutorial work and fail closed."""

import copy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core.db import Base
from katrain.web.core.models_db import (
    BoardPayloadHistory,
    TrainingSample,
    TutorialBook,
    TutorialChapter,
    TutorialFigure,
    TutorialSection,
)
from katrain.web.tutorials.catalog_sources import load_catalog


@pytest.fixture
def database():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    for model in (TutorialBook, TutorialChapter, TutorialSection, TutorialFigure, BoardPayloadHistory, TrainingSample):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine, factory
    engine.dispose()


def source(tmp_path, catalog_id="sample", *, title="曹薰铉布局技巧（第二卷）", author="曹薰铉", intro=True):
    project = tmp_path / catalog_id
    output = project / "output"
    pages = output / "pages"
    pages.mkdir(parents=True)
    figure = {
        "type": "figure_ref",
        "label": "图1",
        "title": "Original caption",
        "text": "Black to play",
        "bbox": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.8, "y_max": 0.9},
    }
    data = {
        "title": title,
        "author": author,
        "publication_year": 2001,
        "chapters": [
            {
                "chapter": "第一章",
                "title": "布局入门",
                "intro": [{"page": 1, "elements": [copy.deepcopy(figure)]}] if intro else [],
                "sections": [
                    {
                        "section": "1",
                        "title": "外势和实地",
                        "pages": [
                            {"page": 1, "elements": [{"type": "description", "text": "First context"}, figure]},
                            {"page": 2, "elements": [{"type": "description", "text": "Text only"}]},
                        ],
                    }
                ],
            }
        ],
    }
    (output / "book.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    for page in (1, 2, 3):
        (pages / f"page_{page:04d}.png").write_bytes(f"png-{catalog_id}-{page}".encode())
    catalog = tmp_path / f"catalog-{catalog_id}.json"
    entry = {
        "id": catalog_id,
        "title": title,
        "author": author,
        "modules": ["布局基础与方向"],
        "project_dir": str(project),
        "repo_metadata": {"json": str(output / "book.json")},
    }
    catalog.write_text(json.dumps({"books": [entry]}, ensure_ascii=False), encoding="utf-8")
    return load_catalog(catalog, tmp_path)[0]


def legacy(factory, *, slug="sample", title="曹熏铉布局技巧（第2卷）", author="曹熏铉"):
    with factory.begin() as session:
        book = TutorialBook(category="布局", subcategory="棋书", title=title, author=author, slug=slug, asset_dir="old")
        chapter = TutorialChapter(book=book, chapter_number="第一章", title="布局入门", order=1)
        section = TutorialSection(chapter=chapter, section_number="1", title="外势和实地", order=1)
        figure = TutorialFigure(
            section=section,
            page=1,
            figure_label="图1",
            book_text="Human corrected text",
            bbox={"manually": "adjusted"},
            board_payload={"verified": True, "stones": [1, 2]},
            recognition_debug={"review": "kept"},
            narration="Human narration",
            audio_asset="audio.wav",
            video_asset="video.mp4",
            order=1,
        )
        session.add(book)
        session.flush()
        session.add(BoardPayloadHistory(figure_id=figure.id, board_payload={"old": True}, change_type="verify"))
        session.add(
            TrainingSample(
                figure_id=figure.id,
                patch_label="A",
                local_col=1,
                local_row=1,
                global_col=1,
                global_row=1,
                patch_image_path="patch.png",
                base_type="black",
            )
        )
        return book.id, figure.id


def snapshot(engine):
    with engine.connect() as connection:
        return {
            name: [dict(row) for row in connection.execute(text(f"SELECT * FROM {name} ORDER BY id")).mappings()]
            for name in inspect(engine).get_table_names()
        }


class MemoryAssets:
    def __init__(self, fail_catalog=None):
        self.objects = {}
        self.created = []
        self.fail_catalog = fail_catalog

    def ensure_page(self, key, page, *, allow_create=True):
        from katrain.web.tutorials.catalog_import import AssetResult, CatalogImportError

        if self.fail_catalog and f"/{self.fail_catalog}/" in key and page.page == 2:
            raise CatalogImportError("upload_failed", "Injected upload failure")
        if key in self.objects:
            assert hashlib.sha256(self.objects[key]).hexdigest() == page.image_sha256
            return AssetResult(key, False)
        if not allow_create:
            raise CatalogImportError("missing_registered_asset", "Registered source asset is missing")
        self.objects[key] = page.path.read_bytes()
        self.created.append(key)
        return AssetResult(key, True)


def test_plan_is_read_only_when_provenance_tables_are_absent(database, tmp_path):
    from katrain.web.tutorials.catalog_import import plan_catalog

    engine, factory = database
    outcome = source(tmp_path)
    expected_book_id, expected_figure_id = legacy(factory)
    before = snapshot(engine)
    with factory() as session:
        result = plan_catalog(session, [outcome])[0]
    assert result.status == "existing_skipped"
    assert result.book_id == expected_book_id
    assert result.figure_mappings[0]["figure_id"] is None  # Legacy importer dropped the intro.
    assert result.figure_mappings[1]["figure_id"] == expected_figure_id
    assert result.figure_mappings[0]["reason"] == "legacy_intro_missing"
    assert snapshot(engine) == before
    assert "tutorial_source_books" not in inspect(engine).get_table_names()


def test_new_import_has_sql_null_payloads_and_repeat_adds_nothing(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog
    from katrain.web.tutorials.source_models import TutorialSourceFigure, TutorialSourcePage

    engine, factory = database
    create_source_tables(engine)
    outcome = source(tmp_path)
    assets = MemoryAssets()
    result = import_catalog(factory, [outcome], assets)[0]
    assert result.status == "new" and result.mode == "apply"
    with factory() as session:
        assert session.query(TutorialFigure).count() == 2
        assert session.query(TutorialFigure).filter(TutorialFigure.board_payload.is_(None)).count() == 2
        assert session.query(TutorialFigure).filter(TutorialFigure.recognition_debug.is_(None)).count() == 2
        assert session.query(TutorialSourceFigure).count() == 2
        assert session.query(TutorialSourcePage).count() == 3
        first_page = session.query(TutorialSourcePage).filter_by(page=1).one()
        assert [f["kind"] for f in first_page.text_fragments] == ["figure_ref", "description", "figure_ref"]
        assert all(f["source_figure_id"] for f in first_page.text_fragments if f["kind"] == "figure_ref")
        assert session.query(TutorialSourcePage).filter_by(page=3).one().text_fragments == []
    before = snapshot(engine)
    created = assets.created[:]
    repeated = import_catalog(factory, [outcome], assets)[0]
    assert repeated.status == "existing_skipped"
    assert repeated.figure_mappings == result.figure_mappings
    assert snapshot(engine) == before
    assert assets.created == created
    assert len(assets.objects) == 3


def test_registration_preserves_all_legacy_rows_including_manual_work(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog
    from katrain.web.tutorials.source_models import TutorialSourceFigure

    engine, factory = database
    book_id, figure_id = legacy(factory)
    before = snapshot(engine)
    create_source_tables(engine)
    result = import_catalog(factory, [source(tmp_path)], MemoryAssets())[0]
    assert result.status == "existing_skipped" and result.book_id == book_id
    after = snapshot(engine)
    assert all(after[name] == rows for name, rows in before.items())
    with factory() as session:
        links = session.query(TutorialSourceFigure).order_by(TutorialSourceFigure.id).all()
        assert [link.figure_id for link in links] == [None, figure_id]
        assert links[0].match_reason == "legacy_intro_missing"


def test_failed_upload_rolls_back_that_book_and_continues(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog
    from katrain.web.tutorials.source_models import TutorialSourceBook

    engine, factory = database
    create_source_tables(engine)
    outcomes = [source(tmp_path, "bad"), source(tmp_path, "good", title="A different book")]
    assets = MemoryAssets(fail_catalog="bad")
    results = import_catalog(factory, outcomes, assets)
    assert [r.status for r in results] == ["failed", "new"]
    assert results[0].orphan_asset_keys == [assets.created[0]]
    with factory() as session:
        assert session.query(TutorialBook).count() == 1
        assert session.query(TutorialSourceBook).one().catalog_id == "good"


@pytest.mark.parametrize("change", ["json", "png"])
def test_registered_source_changes_require_reconciliation_without_writes(database, tmp_path, change):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog, plan_catalog

    engine, factory = database
    create_source_tables(engine)
    outcome = source(tmp_path)
    assets = MemoryAssets()
    import_catalog(factory, [outcome], assets)
    before = snapshot(engine)
    created = assets.created[:]
    if change == "json":
        path = outcome.book.json_path
        data = json.loads(path.read_text())
        data["publisher"] = "New source metadata"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    else:
        outcome.book.pages[0].path.write_bytes(b"changed-png")
    changed = load_catalog(tmp_path / "catalog-sample.json", tmp_path)[0]
    with factory() as session:
        planned = plan_catalog(session, [changed])[0]
    assert planned.status == "ambiguous"
    assert planned.error["code"] == "source_reconciliation_required"
    assert import_catalog(factory, [changed], assets)[0].status == "ambiguous"
    assert snapshot(engine) == before
    assert assets.created == created


@pytest.mark.parametrize("ambiguity", ["wrong_author", "multiple", "no_slug", "wrong_hierarchy"])
def test_uncorroborated_existing_books_are_skipped(database, tmp_path, ambiguity):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog, plan_catalog

    engine, factory = database
    outcome = source(tmp_path)
    legacy(
        factory,
        author="Different author" if ambiguity == "wrong_author" else "曹薰铉",
        slug="other" if ambiguity == "no_slug" else "sample",
    )
    if ambiguity == "multiple":
        legacy(factory, slug="second")
    if ambiguity == "wrong_hierarchy":
        with factory.begin() as session:
            session.query(TutorialChapter).one().title = "Conflicting hierarchy"
    before = snapshot(engine)
    with factory() as session:
        result = plan_catalog(session, [outcome])[0]
    assert result.status == "ambiguous"
    assert result.error["code"] == "ambiguous_existing_book"
    create_source_tables(engine)
    assets = MemoryAssets()
    assert import_catalog(factory, [outcome], assets)[0].status == "ambiguous"
    assert not assets.created
    assert all(snapshot(engine)[name] == rows for name, rows in before.items())


def test_repeated_page_labels_map_only_inside_their_hierarchy(database, tmp_path):
    from katrain.web.tutorials.catalog_import import plan_catalog

    _, factory = database
    outcome = source(tmp_path, intro=False)
    first_book_id, first_figure_id = legacy(factory)
    data = json.loads(outcome.book.json_path.read_text())
    second_chapter = copy.deepcopy(data["chapters"][0])
    second_chapter.update(chapter="第二章", title="第二章标题")
    data["chapters"].append(second_chapter)
    outcome.book.json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    outcome = load_catalog(tmp_path / "catalog-sample.json", tmp_path)[0]
    with factory.begin() as session:
        chapter = TutorialChapter(book_id=first_book_id, chapter_number="第二章", title="第二章标题", order=2)
        section = TutorialSection(chapter=chapter, section_number="1", title="外势和实地", order=1)
        second_figure = TutorialFigure(section=section, page=1, figure_label="图1", order=1)
        session.add(chapter)
        session.flush()
        second_figure_id = second_figure.id
    with factory() as session:
        result = plan_catalog(session, [outcome])[0]
    assert result.status == "existing_skipped"
    assert [mapping["figure_id"] for mapping in result.figure_mappings] == [first_figure_id, second_figure_id]


def test_missing_repeated_figure_does_not_reuse_one_legacy_target(database, tmp_path):
    from katrain.web.tutorials.catalog_import import plan_catalog

    _, factory = database
    outcome = source(tmp_path, intro=False)
    legacy(factory)
    data = json.loads(outcome.book.json_path.read_text())
    elements = data["chapters"][0]["sections"][0]["pages"][0]["elements"]
    elements.append(copy.deepcopy(elements[-1]))
    outcome.book.json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    outcome = load_catalog(tmp_path / "catalog-sample.json", tmp_path)[0]
    with factory() as session:
        result = plan_catalog(session, [outcome])[0]
    assert result.status == "existing_skipped"
    assert [mapping["figure_id"] for mapping in result.figure_mappings] == [None, None]
    assert {mapping["reason"] for mapping in result.figure_mappings} == {"ambiguous_figure_candidates"}


def test_database_failure_rolls_back_and_does_not_leak_exception_secrets(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog
    from katrain.web.tutorials.source_models import TutorialSourceBook

    engine, factory = database
    create_source_tables(engine)

    @event.listens_for(factory, "before_flush")
    def reject_bad_book(session, *_):
        if any(isinstance(row, TutorialSourceBook) and row.catalog_id == "bad" for row in session.new):
            raise RuntimeError("postgresql://private-password@private-host/test")

    assets = MemoryAssets()
    results = import_catalog(
        factory, [source(tmp_path, "bad"), source(tmp_path, "good", title="Another title")], assets
    )
    assert [result.status for result in results] == ["failed", "new"]
    assert len(results[0].orphan_asset_keys) == 3
    assert "private-password" not in json.dumps(results[0].as_dict())
    assert "reconcile" in results[0].error["message"]
    assert "no database rows were committed" not in results[0].error["message"]
    with factory() as session:
        assert session.query(TutorialBook).count() == 1
        assert session.query(TutorialSourceBook).one().catalog_id == "good"


def target_settings():
    return SimpleNamespace(
        STORAGE_BACKEND="s3",
        S3_ENDPOINT_URL="https://test-s3.invalid",
        S3_BUCKET="test",
        S3_PUBLIC_BASE_URL="https://test-media.invalid",
    )


def target_expected():
    return dict(
        expected_db_system_id="123",
        expected_db_name="katrain_db",
        expected_s3_endpoint="https://test-s3.invalid",
        expected_s3_bucket="test",
        expected_media_public_base="https://test-media.invalid",
    )


@pytest.mark.parametrize(
    "mismatch",
    [
        "environment",
        "missing_identity",
        "missing_db_name",
        "local_storage",
        "endpoint",
        "bucket",
        "media",
        "sqlite",
        "database_id",
        "database_name",
    ],
)
def test_target_guard_rejects_every_mismatch_before_schema_changes(database, monkeypatch, mismatch):
    from katrain.web.tutorials.catalog_import import CatalogImportError, verify_apply_target

    engine, factory = database
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "prod" if mismatch == "environment" else "test")
    settings = target_settings()
    expected = target_expected()
    if mismatch == "missing_identity":
        expected["expected_db_system_id"] = None
    if mismatch == "missing_db_name":
        expected["expected_db_name"] = None
    if mismatch == "local_storage":
        settings.STORAGE_BACKEND = "local"
    if mismatch in {"endpoint", "bucket", "media"}:
        setattr(
            settings,
            {"endpoint": "S3_ENDPOINT_URL", "bucket": "S3_BUCKET", "media": "S3_PUBLIC_BASE_URL"}[mismatch],
            "wrong",
        )
    session = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(
            dialect=SimpleNamespace(name="sqlite" if mismatch == "sqlite" else "postgresql")
        ),
        execute=lambda statement: SimpleNamespace(
            scalar_one=lambda: (
                ("other_database" if mismatch == "database_name" else "katrain_db")
                if "current_database" in str(statement)
                else ("456" if mismatch == "database_id" else "123")
            )
        ),
    )
    with pytest.raises(CatalogImportError):
        verify_apply_target(session, settings, **expected)
    assert "tutorial_source_books" not in inspect(engine).get_table_names()


def test_target_guard_reads_the_live_postgres_identifier(monkeypatch):
    from katrain.web.tutorials.catalog_import import verify_apply_target

    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    statements = []

    def execute(statement):
        statements.append(str(statement))
        return SimpleNamespace(scalar_one=lambda: "katrain_db" if "current_database" in str(statement) else "123")

    session = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")), execute=execute
    )
    assert verify_apply_target(session, target_settings(), **target_expected())["database_system_id"] == "123"
    assert statements == ["SELECT system_identifier::text FROM pg_control_system()", "SELECT current_database()"]


class StorageError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.puts = []
        self.reads = []
        self.race = None

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise StorageError("404")
        data, metadata = self.objects[Key]
        return {"ContentLength": len(data), "Metadata": metadata, "ETag": '"' + hashlib.md5(data).hexdigest() + '"'}

    def get_object(self, *, Bucket, Key):
        self.reads.append(Key)
        return {"Body": io.BytesIO(self.objects[Key][0])}

    def put_object(self, **kwargs):
        self.puts.append({key: value for key, value in kwargs.items() if key != "Body"})
        key = kwargs["Key"]
        if self.race is not None:
            self.objects[key] = self.race
            self.race = None
        if key in self.objects:
            raise StorageError("PreconditionFailed")
        data = kwargs["Body"].read()
        import base64

        if base64.b64encode(hashlib.md5(data).digest()).decode() != kwargs["ContentMD5"]:
            raise StorageError("BadDigest")
        self.objects[key] = (data, kwargs["Metadata"])


def test_s3_uses_conditional_create_and_server_checked_md5(tmp_path):
    from katrain.web.tutorials.catalog_import import S3PageAssets, page_asset_key

    outcome = source(tmp_path)
    page = outcome.book.pages[0]
    key = page_asset_key(outcome.book, page)
    client = FakeS3()
    store = S3PageAssets(client=client, bucket="test")
    assert store.ensure_page(key, page).created
    assert client.puts[0]["IfNoneMatch"] == "*"
    assert client.puts[0]["Metadata"]["sha256"] == page.image_sha256
    assert not store.ensure_page(key, page).created
    assert len(client.puts) == 1


@pytest.mark.parametrize("race", [False, True])
def test_s3_reuses_only_checksum_identical_bytes_even_without_trusted_metadata(tmp_path, race):
    from katrain.web.tutorials.catalog_import import CatalogImportError, S3PageAssets, page_asset_key

    outcome = source(tmp_path)
    page = outcome.book.pages[0]
    key = page_asset_key(outcome.book, page)
    client = FakeS3()
    if race:
        client.race = (page.path.read_bytes(), {})
    else:
        client.objects[key] = (page.path.read_bytes(), {"sha256": "untrusted"})
    store = S3PageAssets(client=client, bucket="test")
    assert not store.ensure_page(key, page).created
    assert client.reads == [key]
    original = (b"different existing bytes", {})
    client.objects[key] = original
    with pytest.raises(CatalogImportError, match="different bytes"):
        store.ensure_page(key, page)
    assert client.objects[key] == original


def test_missing_registered_s3_asset_and_source_mutation_fail_closed(tmp_path):
    from katrain.web.tutorials.catalog_import import CatalogImportError, S3PageAssets, page_asset_key

    outcome = source(tmp_path)
    page = outcome.book.pages[0]
    key = page_asset_key(outcome.book, page)
    client = FakeS3()
    store = S3PageAssets(client=client, bucket="test")
    with pytest.raises(CatalogImportError, match="missing"):
        store.ensure_page(key, page, allow_create=False)
    assert not client.puts
    page.path.write_bytes(b"mutated during import")
    with pytest.raises(CatalogImportError, match="upload failed"):
        store.ensure_page(key, page)
    assert not client.objects


def test_commentary_aliases_and_null_page_links_keep_original_captions(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog
    from katrain.web.tutorials.source_models import TutorialSourceFigure, TutorialSourcePage

    engine, factory = database
    legacy(factory)
    create_source_tables(engine)
    outcome = source(tmp_path)
    data = json.loads(outcome.book.json_path.read_text())
    data["chapters"][0]["sections"][0]["pages"][0]["elements"][-1]["commentary_refs"] = [
        {"type": "figure_ref", "page": 1, "element_index": 0, "label": "Alias"}
    ]
    outcome.book.json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    outcome = load_catalog(tmp_path / "catalog-sample.json", tmp_path)[0]
    result = import_catalog(factory, [outcome], MemoryAssets())[0]
    assert result.status == "existing_skipped"
    assert result.commentary_aliases[0]["to_source_figure_id"] == outcome.book.figures[0].source_figure_id
    assert result.commentary_aliases[0]["figure_id"] is None
    with factory() as session:
        figure = session.query(TutorialSourceFigure).filter(TutorialSourceFigure.figure_id.is_not(None)).one()
        assert (
            figure.source_metadata["commentary_refs"][0]["source_figure_id"] == outcome.book.figures[0].source_figure_id
        )
        assert figure.source_metadata["commentary_refs"][0]["figure_id"] is None
        fragment = session.query(TutorialSourcePage).filter_by(page=1).one().text_fragments[0]
        assert fragment["figure_id"] is None
        assert fragment["original_caption"] == {"label": "图1", "title": "Original caption", "text": "Black to play"}


def test_authoritative_version_conflict_is_not_inferred_from_a_slug_year(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, plan_catalog
    from katrain.web.tutorials.source_models import TutorialSourceBook

    engine, factory = database
    book_id, _ = legacy(factory)
    outcome = source(tmp_path)
    outcome.book.source_metadata["legacy_slug_candidates"] = ["sample"]
    outcome.book.source_metadata["directory_year_hints"] = [1997]
    with factory() as session:
        accepted = plan_catalog(session, [outcome])[0]
    assert accepted.status == "existing_skipped"
    assert "legacy_year_is_hint" in {warning["code"] for warning in accepted.warnings}
    create_source_tables(engine)
    with factory.begin() as session:
        session.add(
            TutorialSourceBook(
                source_namespace="other",
                catalog_id="known-old-version",
                book_id=book_id,
                source_json_sha256="0" * 64,
                assets_manifest_sha256="1" * 64,
                source_metadata={"identity": {"publication_year": 1997}},
                matching_evidence={},
            )
        )
    with factory() as session:
        refused = plan_catalog(session, [outcome])[0]
    assert refused.status == "ambiguous"
    assert refused.matching_evidence["candidates"][0]["authoritative_version_conflicts"] == ["publication_year"]


def test_catalog_duplicate_is_an_alias_and_reports_are_private(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog, write_catalog_reports
    from katrain.web.tutorials.catalog_sources import SourceError, SourceOutcome
    from katrain.web.tutorials.source_models import TutorialSourceBook

    engine, factory = database
    create_source_tables(engine)
    outcome = source(tmp_path)
    alias = SourceOutcome(
        "alias", error=SourceError("duplicate_source", "Same canonical source"), duplicate_of="sample"
    )
    assets = MemoryAssets()
    results = import_catalog(factory, [outcome, alias], assets)
    assert [result.status for result in results] == ["new", "existing_skipped"]
    assert results[1].book_id == results[0].book_id
    with factory() as session:
        assert session.query(TutorialBook).count() == session.query(TutorialSourceBook).count() == 1
    directory = tmp_path / "reports"
    report = write_catalog_reports(directory, results)
    assert report["mode"] == "apply"
    assert report["summary"] == {"new": 1, "existing_skipped": 1}
    assert len(json.loads((directory / "catalog-report.json").read_text())["outcomes"]) == 2
    assert directory.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in directory.iterdir())
    assert len(assets.created) == 3


def test_cli_defaults_to_read_only_dry_run_and_rejects_sqlite_apply(tmp_path, monkeypatch):
    from scripts import import_tutorial_catalog as command

    outcome = source(tmp_path)
    db_path = tmp_path / "cli.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    for model in (TutorialBook, TutorialChapter, TutorialSection, TutorialFigure):
        model.__table__.create(engine)
    monkeypatch.setattr(command.settings, "DATABASE_URL", f"sqlite:///{db_path}")
    for name, value in vars(target_settings()).items():
        monkeypatch.setattr(command.settings, name, value)
    arguments = [
        "--catalog",
        str(tmp_path / "catalog-sample.json"),
        "--source-root",
        str(tmp_path),
        "--report-dir",
        str(tmp_path / "cli-reports"),
    ]
    assert command.main(arguments) == 0
    report = json.loads((tmp_path / "cli-reports" / "catalog-report.json").read_text())
    assert report["mode"] == "dry_run" and report["outcomes"][0]["proposed_new"]
    assert "tutorial_source_books" not in inspect(engine).get_table_names()
    assert not (tmp_path / "data").exists()
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    arguments += [
        "--apply",
        "--expected-db-system-id",
        "123",
        "--expected-db-name",
        "katrain_db",
        "--expected-s3-endpoint",
        "https://test-s3.invalid",
        "--expected-s3-bucket",
        "test",
        "--expected-media-public-base",
        "https://test-media.invalid",
    ]
    assert command.main(arguments) == 2
    assert "tutorial_source_books" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.execute(select(TutorialBook.id)).all() == []
    engine.dispose()


@pytest.mark.parametrize("fallback_fails", [False, True])
def test_cli_report_failure_preserves_completed_book_results(tmp_path, monkeypatch, capsys, fallback_fails):
    from scripts import import_tutorial_catalog as command
    from katrain.web.tutorials.catalog_import import CatalogResult

    outcome = source(tmp_path)
    completed = CatalogResult("sample", "new", mode="apply", book_id=123, source_book_id=456)
    monkeypatch.setattr(command.settings, "DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(command, "verify_apply_target", lambda *args, **kwargs: {"database_name": "katrain_db"})
    monkeypatch.setattr(command, "create_source_tables", lambda *_: None)
    monkeypatch.setattr(command, "S3PageAssets", lambda: object())
    monkeypatch.setattr(command, "import_catalog", lambda *args: [completed])
    captured = []

    def report_writer(directory, results, **kwargs):
        captured.append(results)
        if len(captured) == 1 or fallback_fails:
            raise OSError("private-report-exception-content")

    monkeypatch.setattr(command, "write_catalog_reports", report_writer)
    arguments = [
        "--catalog",
        str(tmp_path / "catalog-sample.json"),
        "--source-root",
        str(tmp_path),
        "--report-dir",
        str(tmp_path / "reports"),
        "--apply",
        "--expected-db-system-id",
        "123",
        "--expected-db-name",
        "katrain_db",
        "--expected-s3-endpoint",
        "https://test-s3.invalid",
        "--expected-s3-bucket",
        "test",
        "--expected-media-public-base",
        "https://test-media.invalid",
    ]
    assert command.main(arguments) == 2
    assert len(captured) == 2
    assert all(results == [completed] for results in captured)
    output = capsys.readouterr()
    assert "private-report-exception-content" not in output.out + output.err
    assert "report_write_failed" in output.err
    summary = json.loads(output.out)
    assert summary["completed_books"] == [
        {"catalog_id": "sample", "status": "new", "book_id": 123, "source_book_id": 456}
    ]


def test_planning_an_unrelated_new_book_does_not_load_existing_figure_payloads(database, tmp_path):
    from katrain.web.tutorials.catalog_import import plan_catalog

    engine, factory = database
    legacy(factory)
    outcome = source(tmp_path, "new", title="An unrelated new title")
    queries = []

    @event.listens_for(engine, "before_cursor_execute")
    def record(_, __, statement, *___):
        queries.append(statement)

    with factory() as session:
        assert plan_catalog(session, [outcome])[0].status == "new"
    assert not any("FROM tutorial_figures" in statement for statement in queries)


def test_identity_normalizes_numeric_volume_and_upper_volume_forms():
    from katrain.web.tutorials.catalog_import import _title_identity, normalize_identity

    assert _title_identity("棋书（上册）") == _title_identity("棋书（上）")
    assert _title_identity("棋书（第四卷）") == _title_identity("棋书（四）")
    assert normalize_identity("第二版") == normalize_identity("第2版")


def test_registered_actual_identity_prevents_duplicate_curated_display_titles(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog, plan_catalog

    engine, factory = database
    create_source_tables(engine)
    first = source(tmp_path, "first")
    first.book.title = "First catalog display title"
    assert import_catalog(factory, [first], MemoryAssets())[0].status == "new"
    second = source(tmp_path, "second")
    second.book.title = "Second catalog display title"
    with factory() as session:
        result = plan_catalog(session, [second])[0]
    assert result.status == "ambiguous"
    assert result.matching_evidence["candidates"][0]["registered_actual_identity_matches"]


def test_corroborated_book_identity_survives_section_title_edits_with_null_mapping(database, tmp_path):
    from katrain.web.tutorials.catalog_import import plan_catalog

    _, factory = database
    book_id, _ = legacy(factory)
    with factory.begin() as session:
        session.query(TutorialSection).one().title = "Manually changed old section title"
    with factory() as session:
        result = plan_catalog(session, [source(tmp_path, intro=False)])[0]
    assert result.status == "existing_skipped" and result.book_id == book_id
    assert result.figure_mappings[0]["figure_id"] is None
    assert result.figure_mappings[0]["reason"] == "legacy_section_missing"
    warning = next(warning for warning in result.warnings if warning["code"] == "legacy_hierarchy_drift")
    assert warning["conflicts"][0]["code"] == "section_identity_conflict"


def test_failed_upload_orphans_are_reused_on_a_successful_retry(database, tmp_path):
    from katrain.web.tutorials.catalog_import import create_source_tables, import_catalog

    engine, factory = database
    create_source_tables(engine)
    outcome = source(tmp_path, "bad")
    assets = MemoryAssets(fail_catalog="bad")
    failed = import_catalog(factory, [outcome], assets)[0]
    first_key = failed.orphan_asset_keys[0]
    first_bytes = assets.objects[first_key]
    assets.fail_catalog = None
    assert import_catalog(factory, [outcome], assets)[0].status == "new"
    assert assets.created.count(first_key) == 1
    assert assets.objects[first_key] == first_bytes
    assert len(assets.objects) == 3
