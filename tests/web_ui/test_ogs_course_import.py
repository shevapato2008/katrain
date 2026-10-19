"""OGS imports append stable identities and leave existing authoring intact."""

import copy
import hashlib
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from katrain.web.core.models_db import TutorialBook, TutorialChapter, TutorialFigure, TutorialSection


def sample_bundle():
    return {
        "schema_version": 1,
        "source": {
            "repository": "https://github.com/online-go/online-go.com",
            "commit": "1c1c2b82d027f7c307ab25886112cf0a6baf680a",
            "locale_version": "5304fd731af8856a16d198d506111d61",
            "license": "AGPL-3.0",
            "license_text": "GNU AFFERO GENERAL PUBLIC LICENSE",
        },
        "languages": ["en", "zh-cn", "fr"],
        "chapters": [{"id": "basics", "number": 1, "title": "Basics", "translations": {"en": {"title": "Basics"}}}],
        "lessons": [
            {
                "id": "bl;3-skills-5",
                "chapter_id": "basics",
                "order": 1,
                "course_code": "1.1",
                "route": "bl;3-skills-5",
                "title": "Moves",
                "step_count": 1,
                "first_page": 1,
                "translations": {"en": {"title": "Moves", "subtext": ""}},
            }
        ],
        "steps": [
            {
                "source_id": "ogs-learning:bl;3-skills-5:1",
                "lesson_id": "bl;3-skills-5",
                "step": 1,
                "page": 1,
                "source_url": "https://online-go.com/learn-to-play-go/bl%3B3-skills-5/0",
                "size": 9,
                "initial_player": "W",
                "stones": {"B": [[0, 0]], "W": [[1, 1], [1, 1]]},
                "letters": {"1,1": "A"},
                "shapes": {},
                "viewport": None,
                "exercise": {
                    "kind": "puzzle",
                    "tree": {
                        "point": None,
                        "correct": False,
                        "wrong": False,
                        "children": [
                            {
                                "point": [2, 2],
                                "correct": False,
                                "wrong": False,
                                "children": [{"point": None, "correct": True, "wrong": False, "children": []}],
                            },
                            {"point": [3, 3], "correct": False, "wrong": True, "children": []},
                        ],
                    },
                },
                "translations": {
                    "en": {"title": "Moves", "instruction": "White to play", "fallback": False},
                    "zh-cn": {"title": "行棋", "instruction": "白先", "fallback": False},
                },
                "raw_source": {"file": "src/Page01.tsx", "config": {"white": "bbbb"}},
                "issues": [],
            }
        ],
    }


def declare_content_hash(bundle):
    """Match the exporter's canonical JSON, excluding only hash and screenshots."""
    import json

    content = copy.deepcopy(bundle)
    content["source"].pop("content_sha256", None)
    for step in content["steps"]:
        step.pop("screenshot", None)
    bundle["source"]["content_sha256"] = hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return bundle


def test_declared_digest_rejects_changed_correct_answer_before_cli_ddl(tmp_path, monkeypatch):
    import json
    import scripts.import_ogs_course as cli

    bundle = sample_bundle()
    # The real territory:1 exercise uses choices 3/4/5 and correct answer 4.
    bundle["steps"][0]["exercise"] = {
        "kind": "choice",
        "choices": [{"value": value, "label_key": value} for value in ("3", "4", "5")],
        "correct_choice": "4",
    }
    declare_content_hash(bundle)
    bundle["steps"][0]["exercise"]["correct_choice"] = "3"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(bundle))

    def forbidden(*a, **k):
        pytest.fail("tampered source must be rejected before DB connection, DDL or uploads")

    monkeypatch.setattr(cli, "create_engine", forbidden)
    monkeypatch.setattr(cli, "create_ogs_tables", forbidden)
    monkeypatch.setattr(cli, "S3PageAssets", forbidden)
    report_dir = tmp_path / "report"
    args = ["--bundle", str(path), "--report-dir", str(report_dir), "--apply"]
    for key, value in cli.EXPECTED_TARGET.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    assert cli.main(args) == 2
    report = json.loads((report_dir / "ogs-import.json").read_text())
    assert report["error"]["message"] == "Declared source content checksum mismatch"


def test_declared_digest_allows_same_version_screenshot_enrichment(database, tmp_path):
    from PIL import Image
    from katrain.web.tutorials.catalog_import import LocalPageAssets
    from katrain.web.tutorials.ogs_import import create_ogs_tables, import_ogs_course

    engine, sessions = database
    create_ogs_tables(engine)
    bundle = declare_content_hash(sample_bundle())
    assert import_ogs_course(sessions, bundle)["status"] == "imported"
    image = tmp_path / "source.png"
    Image.new("RGB", (8, 9)).save(image)
    bundle["steps"][0]["screenshot"] = {
        "path": "source.png",
        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "width": 8,
        "height": 9,
        "language": "zh-cn",
    }
    assert (
        import_ogs_course(
            sessions, bundle, screenshot_root=tmp_path, asset_store=LocalPageAssets(tmp_path / "objects")
        )["status"]
        == "enriched"
    )


@pytest.fixture
def database():
    engine = create_engine("sqlite://")
    for model in (TutorialBook, TutorialChapter, TutorialSection, TutorialFigure):
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine, sessions
    engine.dispose()


def test_dry_run_is_read_only_and_apply_is_idempotent(database):
    from katrain.web.tutorials.ogs_import import create_ogs_tables, import_ogs_course, plan_ogs_course
    from katrain.web.tutorials.ogs_models import TutorialOgsStep

    engine, sessions = database
    before = inspect(engine).get_table_names()
    with sessions() as db:
        assert plan_ogs_course(db, sample_bundle())["status"] == "new"
    assert inspect(engine).get_table_names() == before
    create_ogs_tables(engine)
    result = import_ogs_course(sessions, sample_bundle())
    assert result["status"] == "imported"
    assert result["counts"]["new_figures"] == 1
    repeated = import_ogs_course(sessions, sample_bundle())
    assert repeated["status"] == "unchanged"
    assert repeated["counts"]["new_figures"] == 0
    assert repeated["mappings"] == result["mappings"]
    with sessions() as db:
        figure = db.get(TutorialFigure, result["mappings"][0]["figure_id"])
        assert figure.board_payload["stones"]["W"] == [[1, 1]]
        assert figure.board_payload["replay"]["status"] == "needs_calibration"
        assert figure.board_review is None and figure.narration is None and figure.audio_asset is None
        assert db.scalar(select(TutorialOgsStep)).payload["raw_source"]["config"]["white"] == "bbbb"


def test_source_conflict_and_slug_takeover_do_not_modify_existing(database):
    from katrain.web.tutorials.ogs_import import create_ogs_tables, import_ogs_course

    engine, sessions = database
    create_ogs_tables(engine)
    result = import_ogs_course(sessions, sample_bundle())
    figure_id = result["mappings"][0]["figure_id"]
    with sessions.begin() as db:
        figure = db.get(TutorialFigure, figure_id)
        figure.board_payload = {"human": True}
        figure.board_review = {"reviewer": "admin"}
        figure.narration = "Human explanation"
        figure.audio_asset = "human.wav"
    changed = sample_bundle()
    changed["steps"][0]["translations"]["en"]["instruction"] = "Changed"
    assert import_ogs_course(sessions, changed)["status"] == "conflict"
    assert import_ogs_course(sessions, sample_bundle())["status"] == "unchanged"
    with sessions() as db:
        figure = db.get(TutorialFigure, figure_id)
        assert (figure.board_payload, figure.board_review, figure.narration, figure.audio_asset) == (
            {"human": True},
            {"reviewer": "admin"},
            "Human explanation",
            "human.wav",
        )
    with sessions.begin() as db:
        # A pre-existing book may never be silently adopted by the OGS importer.
        from katrain.web.tutorials.ogs_models import TutorialOgsCourse

        db.delete(db.scalar(select(TutorialOgsCourse)))
    assert import_ogs_course(sessions, sample_bundle())["status"] == "conflict"


def test_opposite_color_collision_is_rejected(database):
    from katrain.web.tutorials.ogs_import import OgsImportError, plan_ogs_course

    _, sessions = database
    bundle = sample_bundle()
    bundle["steps"][0]["stones"]["W"].append([0, 0])
    with sessions() as db, pytest.raises(OgsImportError, match="opposite"):
        plan_ogs_course(db, bundle)


def test_same_version_screenshot_enrichment_preserves_human_media(database, tmp_path):
    from katrain.web.tutorials.ogs_import import create_ogs_tables, import_ogs_course
    from katrain.web.tutorials.ogs_models import TutorialOgsStep
    from katrain.web.tutorials.catalog_import import LocalPageAssets
    from PIL import Image

    engine, sessions = database
    create_ogs_tables(engine)
    result = import_ogs_course(sessions, sample_bundle())
    figure_id = result["mappings"][0]["figure_id"]
    with sessions.begin() as db:
        db.get(TutorialFigure, figure_id).page_image_path = "tutorial_assets/human.png"
    image = tmp_path / "one.png"
    Image.new("RGB", (8, 9)).save(image)
    bundle = sample_bundle()
    bundle["steps"][0]["screenshot"] = {
        "path": "one.png",
        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "width": 8,
        "height": 9,
        "language": "zh-cn",
    }
    assets = LocalPageAssets(tmp_path / "objects")
    enriched = import_ogs_course(sessions, bundle, screenshot_root=tmp_path, asset_store=assets)
    assert enriched["status"] == "enriched"
    with sessions() as db:
        assert db.get(TutorialFigure, figure_id).page_image_path == "tutorial_assets/human.png"
        screenshot = db.scalar(select(TutorialOgsStep)).screenshot
        assert screenshot["image_path"].startswith("tutorial_assets/ogs-learn-to-play-go/")
    assert import_ogs_course(sessions, bundle, screenshot_root=tmp_path, asset_store=assets)["status"] == "unchanged"
    bundle["steps"][0]["screenshot"]["sha256"] = "b" * 64
    assert import_ogs_course(sessions, bundle, screenshot_root=tmp_path, asset_store=assets)["status"] == "conflict"


def test_cli_rejects_unpinned_target_before_ddl_or_upload(monkeypatch, tmp_path):
    from scripts.import_ogs_course import main

    report = tmp_path / "report"
    assert (
        main(
            [
                "--bundle",
                str(tmp_path / "missing.json"),
                "--report-dir",
                str(report),
                "--apply",
                "--expected-db-system-id",
                "1",
                "--expected-db-name",
                "other",
                "--expected-s3-endpoint",
                "https://wrong",
                "--expected-s3-bucket",
                "wrong",
                "--expected-media-public-base",
                "https://wrong",
            ]
        )
        == 2
    )


def test_asset_failure_rolls_back_course_and_reports_created_objects(database, tmp_path):
    from katrain.web.tutorials.ogs_import import OgsImportError, create_ogs_tables, import_ogs_course
    from katrain.web.tutorials.catalog_import import AssetResult
    from PIL import Image

    engine, sessions = database
    create_ogs_tables(engine)
    bundle = sample_bundle()
    second = copy.deepcopy(bundle["steps"][0])
    second.update(source_id="ogs-learning:bl;3-skills-5:2", step=2, page=2)
    bundle["steps"].append(second)
    bundle["lessons"][0]["step_count"] = 2
    image = tmp_path / "one.png"
    Image.new("RGB", (8, 9)).save(image)
    for step in bundle["steps"]:
        step["screenshot"] = {
            "path": "one.png",
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "width": 8,
            "height": 9,
            "language": "zh-cn",
        }

    class FailingAssets:
        calls = 0

        def ensure_page(self, key, page):
            self.calls += 1
            if self.calls == 2:
                raise OgsImportError("asset_upload_failed", "Simulated immutable upload failure")
            return AssetResult(key, True)

    with pytest.raises(OgsImportError) as failure:
        import_ogs_course(sessions, bundle, screenshot_root=tmp_path, asset_store=FailingAssets())
    assert failure.value.report["status"] == "failed"
    assert len(failure.value.report["orphan_asset_keys"]) == 1
    with sessions() as db:
        assert db.scalar(select(TutorialBook)) is None


def test_cli_default_is_read_only_and_does_not_initialize_or_upload(tmp_path, monkeypatch):
    import json
    import scripts.import_ogs_course as cli
    from katrain.web.tutorials.ogs_import import validate_bundle, plan_ogs_course

    url = f"sqlite:///{tmp_path / 'read-only.sqlite'}"
    engine = create_engine(url)
    for model in (TutorialBook, TutorialChapter, TutorialSection, TutorialFigure):
        model.__table__.create(engine)
    path = tmp_path / "course.json"
    path.write_text(json.dumps(sample_bundle()))
    monkeypatch.setattr(cli, "settings", SimpleNamespace(DATABASE_URL=url))
    # The public CLI still enforces full cardinality; this isolates its read-only execution.
    monkeypatch.setattr(cli, "validate_bundle", lambda bundle, **k: validate_bundle(bundle))
    monkeypatch.setattr(cli, "plan_ogs_course", lambda db, bundle, **k: plan_ogs_course(db, bundle))

    def forbidden(*a, **k):
        pytest.fail("dry-run must not initialize tables or access object storage")

    monkeypatch.setattr(cli, "create_ogs_tables", forbidden)
    monkeypatch.setattr(cli, "S3PageAssets", forbidden)
    before = inspect(engine).get_table_names()
    assert cli.main(["--bundle", str(path), "--report-dir", str(tmp_path / "report")]) == 0
    assert inspect(engine).get_table_names() == before
    engine.dispose()
