"""Append catalog tutorials and provenance without changing existing tutorial work.

Planning never creates tables or accesses an asset store. The command line entry
point verifies the TEST PostgreSQL/storage identity before creating the three
provenance tables or calling ``import_catalog``. Each book has its own transaction.
"""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
import copy
import csv
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Protocol
import unicodedata
from urllib.parse import quote

from sqlalchemy import inspect, null, select, text
from sqlalchemy.orm import selectinload

from katrain.web.core.models_db import TutorialBook, TutorialChapter, TutorialFigure, TutorialSection
from katrain.web.tutorials.catalog_sources import SOURCE_NAMESPACE, SourceBook, SourceOutcome, SourcePage
from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage

SOURCE_TABLES = (TutorialSourceBook.__table__, TutorialSourceFigure.__table__, TutorialSourcePage.__table__)


class CatalogImportError(RuntimeError):
    """A reportable, credential-free refusal to import or reuse an asset."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self):
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class AssetResult:
    key: str
    created: bool


class AssetStore(Protocol):
    def ensure_page(self, key: str, page: SourcePage, *, allow_create: bool = True) -> AssetResult:
        """Reuse checksum-identical bytes, or create without overwriting any object."""


@dataclass
class CatalogResult:
    catalog_id: str
    status: str
    mode: str = "dry_run"
    book_id: int | None = None
    proposed_new: bool = False
    source_book_id: int | None = None
    duplicate_of: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    matching_evidence: dict[str, Any] = field(default_factory=dict)
    figure_mappings: list[dict[str, Any]] = field(default_factory=list)
    commentary_aliases: list[dict[str, Any]] = field(default_factory=list)
    asset_keys: list[str] = field(default_factory=list)
    created_asset_keys: list[str] = field(default_factory=list)
    orphan_asset_keys: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None

    def as_dict(self):
        return asdict(self)


def _segment(value: str) -> str:
    encoded = quote(value, safe="-_")
    return encoded.replace(".", "%2E") if value in {".", ".."} else encoded


def page_asset_key(book: SourceBook, page: SourcePage) -> str:
    return f"tutorial_assets/catalog/{_segment(book.catalog_id)}/{page.image_sha256}/{page.path.name}"


def _source_bytes(page: SourcePage) -> bytes:
    data = page.path.read_bytes()
    if len(data) != page.size_bytes or hashlib.sha256(data).hexdigest() != page.image_sha256:
        raise CatalogImportError("source_asset_changed", "Source PNG changed after source validation")
    return data


class LocalPageAssets:
    """Filesystem implementation for isolated tests/tools; exclusive creation only."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def ensure_page(self, key, page, *, allow_create=True):
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root):
            raise CatalogImportError("invalid_asset_key", "Asset key leaves the local storage root")
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != page.image_sha256:
                raise CatalogImportError("asset_checksum_conflict", "Existing page object has different bytes")
            return AssetResult(key, False)
        if not allow_create:
            raise CatalogImportError("missing_registered_asset", "Registered source asset is missing")
        data = _source_bytes(page)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stream:
                stream.write(data)
        except FileExistsError:
            return self.ensure_page(key, page, allow_create=False)
        return AssetResult(key, True)


class S3PageAssets:
    """Conditional, immutable writes through the existing S3 backend client."""

    def __init__(self, backend=None, *, client=None, bucket=None):
        if backend is None and client is None:
            from katrain.web.core.storage.s3 import S3StorageBackend

            backend = S3StorageBackend()
        self.client = client if client is not None else backend._client
        self.bucket = bucket if bucket is not None else backend._bucket

    @staticmethod
    def _error_code(exc):
        return getattr(exc, "response", {}).get("Error", {}).get("Code", "")

    def _head(self, key):
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            if self._error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise CatalogImportError("asset_read_failed", "Cannot check existing page object") from exc

    def _verify(self, key, page, head):
        metadata = head.get("Metadata", {})
        etag = str(head.get("ETag", "")).strip('"')
        # Importer uploads are single-part and carry a server-checked ContentMD5.
        if (
            metadata.get("sha256") == page.image_sha256
            and etag == page.image_md5
            and head.get("ContentLength") == page.size_bytes
        ):
            return AssetResult(key, False)
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
            digest = hashlib.sha256()
            size = 0
            try:
                for chunk in iter(lambda: body.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
            finally:
                body.close()
        except Exception as exc:
            raise CatalogImportError("asset_read_failed", "Cannot verify existing page bytes") from exc
        if digest.hexdigest() != page.image_sha256 or size != page.size_bytes:
            raise CatalogImportError("asset_checksum_conflict", "Existing page object has different bytes")
        return AssetResult(key, False)

    def ensure_page(self, key, page, *, allow_create=True):
        head = self._head(key)
        if head is not None:
            return self._verify(key, page, head)
        if not allow_create:
            raise CatalogImportError("missing_registered_asset", "Registered source asset is missing")
        try:
            with page.path.open("rb") as stream:
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=stream,
                    ContentType="image/png",
                    ContentMD5=base64.b64encode(bytes.fromhex(page.image_md5)).decode("ascii"),
                    Metadata={"sha256": page.image_sha256, "md5": page.image_md5, "source-namespace": SOURCE_NAMESPACE},
                    CacheControl="public, max-age=31536000, immutable",
                    IfNoneMatch="*",
                )
        except Exception as exc:
            if self._error_code(exc) in {"412", "PreconditionFailed", "409", "ConditionalRequestConflict"}:
                head = self._head(key)
                if head is not None:
                    return self._verify(key, page, head)
            raise CatalogImportError("asset_upload_failed", "Conditional page upload failed") from exc
        return AssetResult(key, True)


_NUMERALS = {char: index for index, char in enumerate("零一二三四五六七八九")}
_NUMERALS.update({"〇": 0, "两": 2})
_NUMBER = r"[0-9零〇一二两三四五六七八九十百]+"


def _number(value: str) -> str:
    if value.isdigit():
        return str(int(value))
    total = current = 0
    for character in value:
        if character in {"十", "百"}:
            total += (current or 1) * {"十": 10, "百": 100}[character]
            current = 0
        else:
            current = _NUMERALS.get(character, 0)
    return str(total + current)


def normalize_identity(value: Any) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).lower().replace("曹熏铉", "曹薰铉")
    value = re.sub(rf"第?({_NUMBER})([卷册章节版])", lambda match: _number(match[1]) + match[2], value)
    return "".join(
        character
        for character in value
        if not character.isspace() and not unicodedata.category(character).startswith("P")
    )


def _volume(value: Any) -> str | None:
    if value is None or value == "":
        return None
    value = normalize_identity(value)
    value = re.sub(r"^[第卷册]+|[卷册]+$", "", value)
    if value in {"上", "中", "下"}:
        return value
    if re.fullmatch(_NUMBER, value):
        return _number(value)
    return value


def _title_identity(title: str, volume: Any = None) -> tuple[str, str | None]:
    title = unicodedata.normalize("NFKC", title or "")
    match = re.search(
        rf"(?:\(((?:上|中|下)[卷册]?|第?{_NUMBER}[卷册]?)\)|((?:上|中|下)[卷册]|第{_NUMBER}[卷册]))$", title
    )
    parsed = _volume(match[1] or match[2]) if match else None
    explicit = _volume(volume)
    if explicit is not None and parsed is not None and explicit != parsed:
        raise CatalogImportError("source_volume_conflict", "Actual JSON volume disagrees with its title")
    return normalize_identity(title[: match.start()] if match else title), explicit or parsed


def _source_identity(book):
    return _metadata_identity(book.source_metadata, book.title, book.author)


def _metadata_identity(metadata, fallback_title, fallback_author):
    actual = metadata.get("identity", {})
    title, volume = _title_identity(actual.get("title", fallback_title), actual.get("volume"))
    return title, normalize_identity(actual.get("author", fallback_author)), volume


def _book_identity(book):
    title, volume = _title_identity(book.title)
    return title, normalize_identity(book.author), volume


def _mapping(figure, figure_id, reason):
    return {
        "source_figure_id": figure.source_figure_id,
        "source_pointer": figure.pointer,
        "page": figure.page,
        "chapter_pointer": figure.chapter_pointer,
        "section_pointer": figure.section_pointer,
        "label": figure.label,
        "ordinal": figure.ordinal,
        "figure_id": figure_id,
        "reason": reason,
    }


def _hierarchy_mapping(source: SourceBook, existing: TutorialBook):
    """Match within chapters/sections; never use a global page/label or edited bbox."""
    chapter_targets = {}
    section_targets = {}
    problems = []
    evidence_count = 0
    for chapter in existing.chapters:
        candidates = [
            item
            for item in source.chapters
            if normalize_identity(item.number) == normalize_identity(chapter.chapter_number)
            and normalize_identity(item.title) == normalize_identity(chapter.title)
        ]
        if len(candidates) != 1:
            problems.append({"code": "chapter_identity_conflict", "chapter_id": chapter.id})
            continue
        source_chapter = candidates[0]
        if source_chapter.pointer in chapter_targets:
            problems.append({"code": "chapter_identity_ambiguous", "chapter_id": chapter.id})
            continue
        chapter_targets[source_chapter.pointer] = chapter
        evidence_count += 1
        for section in chapter.sections:
            candidates = [
                item
                for item in source_chapter.sections
                if normalize_identity(item.number) == normalize_identity(section.section_number)
                and normalize_identity(item.title) == normalize_identity(section.title)
            ]
            if len(candidates) != 1 or candidates[0].pointer in section_targets:
                problems.append({"code": "section_identity_conflict", "section_id": section.id})
                continue
            section_targets[candidates[0].pointer] = section
            evidence_count += 1
    mappings = []
    for chapter in source.chapters:
        for section in chapter.sections:
            target = section_targets.get(section.pointer)
            if target is None:
                reason = (
                    "legacy_intro_missing"
                    if section.synthetic and any(not item.synthetic for item in chapter.sections)
                    else (
                        "legacy_chapter_missing" if chapter.pointer not in chapter_targets else "legacy_section_missing"
                    )
                )
                mappings.extend(_mapping(figure, None, reason) for figure in section.figures)
                continue
            source_groups = defaultdict(list)
            target_groups = defaultdict(list)
            source_order = {figure.source_figure_id: order for order, figure in enumerate(section.figures, 1)}
            for figure in section.figures:
                source_groups[(figure.page, normalize_identity(figure.label))].append(figure)
            for figure in sorted(target.figures, key=lambda figure: figure.order):
                target_groups[(figure.page, normalize_identity(figure.figure_label))].append(figure)
            for figure in section.figures:
                key = (figure.page, normalize_identity(figure.label))
                candidates = target_groups[key]
                sources = source_groups[key]
                if not candidates:
                    mappings.append(_mapping(figure, None, "legacy_figure_missing"))
                elif len(candidates) != len(sources):
                    mappings.append(_mapping(figure, None, "ambiguous_figure_candidates"))
                else:
                    candidate = candidates[sources.index(figure)]
                    if len(sources) > 1 and candidate.order != source_order[figure.source_figure_id]:
                        mappings.append(_mapping(figure, None, "ambiguous_figure_order"))
                    else:
                        mappings.append(_mapping(figure, candidate.id, "matched_hierarchy_page_label_order"))
    ids = [item["figure_id"] for item in mappings if item["figure_id"] is not None]
    if len(set(ids)) != len(ids):
        problems.append({"code": "figure_target_reused"})
    return mappings, {"hierarchy_matches": evidence_count, "hierarchy_conflicts": problems}


def _registry(session, catalog_ids):
    present = [inspect(session.connection()).has_table(table.name) for table in SOURCE_TABLES]
    if not any(present):
        return {}, [], {}
    if not all(present):
        raise CatalogImportError(
            "incomplete_source_registry", "Provenance schema is incomplete; no import is permitted"
        )
    rows = session.scalars(select(TutorialSourceBook)).all()
    by_identity = {(row.source_namespace, row.catalog_id): row for row in rows}
    source_ids = [row.id for row in rows if row.source_namespace == SOURCE_NAMESPACE and row.catalog_id in catalog_ids]
    figures = defaultdict(list)
    pages = defaultdict(list)
    if source_ids:
        for row in session.scalars(
            select(TutorialSourceFigure).where(TutorialSourceFigure.source_book_id.in_(source_ids))
        ):
            figures[row.source_book_id].append(row)
        for row in session.scalars(select(TutorialSourcePage).where(TutorialSourcePage.source_book_id.in_(source_ids))):
            pages[row.source_book_id].append(row)
    return by_identity, rows, {"figures": figures, "pages": pages}


def _base_result(outcome, mode="dry_run"):
    result = CatalogResult(outcome.catalog_id, "failed", mode=mode, duplicate_of=outcome.duplicate_of)
    if outcome.book:
        book = outcome.book
        result.counts = {
            "chapters": len(book.chapters),
            "sections": sum(len(chapter.sections) for chapter in book.chapters),
            "figures": len(book.figures),
            "pages": len(book.pages),
        }
        result.warnings = copy.deepcopy(book.source_metadata.get("warnings", []))
        result.asset_keys = [page_asset_key(book, page) for page in book.pages]
    elif outcome.error:
        result.error = outcome.error.as_dict()
    return result


def _commentary_links(book, mappings):
    ids = {item["source_figure_id"]: item["figure_id"] for item in mappings}
    return [
        {
            "from_source_figure_id": figure.source_figure_id,
            "to_source_figure_id": ref["source_figure_id"],
            "figure_id": ids.get(ref["source_figure_id"]),
            "reference": copy.deepcopy(ref),
        }
        for figure in book.figures
        for ref in figure.commentary_refs
        if "source_figure_id" in ref
    ]


def _version_conflicts(source, registered):
    actual = source.source_metadata.get("identity", {})
    previous = registered.source_metadata.get("identity", {})
    return [
        name
        for name in ("publication_year", "publication_date", "edition", "isbn")
        if actual.get(name) is not None
        and previous.get(name) is not None
        and normalize_identity(actual[name]) != normalize_identity(previous[name])
    ]


def _plan_one(session, outcome, existing_books, registry, registered_rows, registry_content):
    result = _base_result(outcome)
    if not outcome.book:
        return result
    source = outcome.book
    registered = registry.get((SOURCE_NAMESPACE, source.catalog_id))
    if registered:
        result.book_id = registered.book_id
        result.source_book_id = registered.id
        result.matching_evidence = {"method": "source_registry", "source_book_id": registered.id}
        if (
            registered.source_json_sha256 != source.source_json_sha256
            or registered.assets_manifest_sha256 != source.assets_manifest_sha256
        ):
            result.status = "ambiguous"
            result.error = {
                "code": "source_reconciliation_required",
                "message": "Registered catalog source JSON or PNG manifest changed; manual reconciliation is required",
            }
            return result
        links = {row.source_figure_id: row for row in registry_content["figures"][registered.id]}
        pages = {row.page: row for row in registry_content["pages"][registered.id]}
        if (
            not any(book.id == registered.book_id for book in existing_books)
            or set(links) != {figure.source_figure_id for figure in source.figures}
            or set(pages) != {page.page for page in source.pages}
            or any(
                pages[page.page].image_sha256 != page.image_sha256
                or pages[page.page].page_image_path != page_asset_key(source, page)
                for page in source.pages
            )
        ):
            result.status = "ambiguous"
            result.error = {
                "code": "source_reconciliation_required",
                "message": "Registered provenance is incomplete or inconsistent",
            }
            return result
        result.status = "existing_skipped"
        result.figure_mappings = [
            _mapping(figure, links[figure.source_figure_id].figure_id, links[figure.source_figure_id].match_reason)
            for figure in source.figures
        ]
        result.commentary_aliases = _commentary_links(source, result.figure_mappings)
        return result
    identity = _source_identity(source)
    slugs = source.source_metadata.get("legacy_slug_candidates", [])
    registered_identity_ids = {
        book.id
        for book in existing_books
        for row in registered_rows
        if row.book_id == book.id
        and identity[1]
        and _metadata_identity(row.source_metadata, book.title, book.author) == identity
    }
    candidates = [
        book
        for book in existing_books
        if book.slug in slugs
        or (identity[1] and _book_identity(book) == identity)
        or book.id in registered_identity_ids
    ]
    if candidates:
        candidates = session.scalars(
            select(TutorialBook)
            .where(TutorialBook.id.in_([book.id for book in candidates]))
            .options(
                selectinload(TutorialBook.chapters)
                .selectinload(TutorialChapter.sections)
                .selectinload(TutorialSection.figures)
            )
            .execution_options(populate_existing=True)
        ).all()
    corroborated = []
    evidence = []
    for book in candidates:
        mappings, hierarchy = _hierarchy_mapping(source, book)
        versions = sorted(
            {name for row in registered_rows if row.book_id == book.id for name in _version_conflicts(source, row)}
        )
        details = {
            "book_id": book.id,
            "legacy_slug": book.slug,
            "slug_matches": book.slug in slugs,
            "title_author_volume_matches": bool(identity[1]) and _book_identity(book) == identity,
            "registered_actual_identity_matches": book.id in registered_identity_ids,
            "authoritative_version_conflicts": versions,
            **hierarchy,
        }
        evidence.append(details)
        if (
            details["slug_matches"]
            and details["title_author_volume_matches"]
            and not versions
            and hierarchy["hierarchy_matches"]
            and not any(problem["code"] == "figure_target_reused" for problem in hierarchy["hierarchy_conflicts"])
        ):
            corroborated.append((book, mappings))
    result.matching_evidence = {"method": "legacy_corroboration", "candidates": evidence}
    if len(candidates) == 1 and len(corroborated) == 1:
        book, result.figure_mappings = corroborated[0]
        result.book_id = book.id
        result.status = "existing_skipped"
        hierarchy_conflicts = evidence[0]["hierarchy_conflicts"]
        if hierarchy_conflicts:
            result.warnings.append(
                {
                    "code": "legacy_hierarchy_drift",
                    "message": "Existing hierarchy differs from the source; unresolved figure mappings remain NULL",
                    "conflicts": hierarchy_conflicts,
                }
            )
        if source.source_metadata.get("directory_year_hints") and source.source_metadata.get("identity", {}).get(
            "publication_year"
        ):
            result.warnings.append(
                {
                    "code": "legacy_year_is_hint",
                    "message": "Legacy slug year is not authoritative publication-version evidence",
                }
            )
    elif candidates:
        result.status = "ambiguous"
        result.error = {
            "code": "ambiguous_existing_book",
            "message": "Existing book identity lacks unique corroboration; import skipped",
        }
    else:
        result.status = "new"
        result.proposed_new = True
        result.figure_mappings = [_mapping(figure, None, "proposed_new") for figure in source.figures]
        result.matching_evidence = {"method": "new_catalog_identity"}
    result.commentary_aliases = _commentary_links(source, result.figure_mappings)
    return result


def _alias_result(outcome, previous, mode):
    result = _base_result(outcome, mode)
    original = previous.get(outcome.duplicate_of)
    if original and original.status in {"new", "existing_skipped"}:
        result.status = "existing_skipped"
        result.book_id = original.book_id
        result.source_book_id = original.source_book_id
        result.error = None
        result.matching_evidence = {"method": "catalog_alias", "duplicate_of": outcome.duplicate_of}
        result.counts = dict(original.counts)
        result.figure_mappings = copy.deepcopy(original.figure_mappings)
    else:
        result.error = {
            "code": "alias_target_unavailable",
            "message": "Duplicate source target did not import or plan successfully",
        }
    return result


def plan_catalog(session, outcomes: list[SourceOutcome]) -> list[CatalogResult]:
    """Read all outcomes against the actual existing tables; never DDL/upload."""
    with session.no_autoflush:
        registry, registered_rows, registry_content = _registry(session, {outcome.catalog_id for outcome in outcomes})
        existing_books = session.scalars(select(TutorialBook).execution_options(populate_existing=True)).all()
        results = []
        previous = {}
        for outcome in outcomes:
            try:
                result = (
                    _alias_result(outcome, previous, "dry_run")
                    if outcome.duplicate_of
                    else _plan_one(session, outcome, existing_books, registry, registered_rows, registry_content)
                )
            except CatalogImportError as exc:
                result = _base_result(outcome)
                result.error = exc.as_dict()
            _mapping_counts(result)
            results.append(result)
            previous[outcome.catalog_id] = result
    return results


def _mapping_counts(result):
    result.counts.update(
        mapped_figures=sum(mapping["figure_id"] is not None for mapping in result.figure_mappings),
        unmapped_figures=sum(
            mapping["figure_id"] is None and mapping["reason"] != "proposed_new" for mapping in result.figure_mappings
        ),
        proposed_figures=sum(mapping["reason"] == "proposed_new" for mapping in result.figure_mappings),
    )


def create_source_tables(bind):
    """Create only the three append-only provenance tables after target verification."""
    for table in SOURCE_TABLES:
        table.create(bind, checkfirst=True)


def verify_apply_target(
    session,
    settings,
    *,
    expected_db_system_id,
    expected_db_name,
    expected_s3_endpoint,
    expected_s3_bucket,
    expected_media_public_base,
):
    """Fail closed before any DDL, database mutation, or asset upload."""
    if os.getenv("KATRAIN_ADMIN_ENV") != "test":
        raise CatalogImportError("wrong_admin_environment", "Apply requires KATRAIN_ADMIN_ENV=test")
    expected = {
        "database system id": expected_db_system_id,
        "database name": expected_db_name,
        "S3 endpoint": expected_s3_endpoint,
        "S3 bucket": expected_s3_bucket,
        "media public base": expected_media_public_base,
    }
    if any(not str(value or "").strip() for value in expected.values()):
        raise CatalogImportError("missing_target_identity", "Apply requires all explicit expected target identities")
    if settings.STORAGE_BACKEND != "s3":
        raise CatalogImportError("wrong_storage_backend", "Apply requires the configured S3 storage backend")
    if (
        settings.S3_ENDPOINT_URL != expected_s3_endpoint
        or settings.S3_BUCKET != expected_s3_bucket
        or settings.S3_PUBLIC_BASE_URL != expected_media_public_base
    ):
        raise CatalogImportError(
            "storage_identity_mismatch", "Configured media storage does not match the explicit expected target"
        )
    if session.get_bind().dialect.name != "postgresql":
        raise CatalogImportError("wrong_database_backend", "Apply requires a live PostgreSQL TEST database")
    try:
        actual = str(session.execute(text("SELECT system_identifier::text FROM pg_control_system()")).scalar_one())
        actual_name = str(session.execute(text("SELECT current_database()")).scalar_one())
    except Exception as exc:
        raise CatalogImportError(
            "database_identity_unavailable", "Cannot verify the live PostgreSQL database identity"
        ) from exc
    if actual != str(expected_db_system_id):
        raise CatalogImportError(
            "database_identity_mismatch", "Live PostgreSQL system identifier does not match the expected TEST target"
        )
    if actual_name != expected_db_name:
        raise CatalogImportError(
            "database_name_mismatch", "Live PostgreSQL database name does not match the expected TEST target"
        )
    return {
        "database_system_id": actual,
        "database_name": actual_name,
        "storage_verified": True,
        "admin_environment": "test",
    }


def _advisory_key(value):
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big", signed=True)


def _lock_source(session, catalog_id):
    if session.get_bind().dialect.name == "postgresql":
        # Namespace lock also prevents simultaneous alternate IDs racing legacy matching.
        for identity in (SOURCE_NAMESPACE, f"{SOURCE_NAMESPACE}:{catalog_id}"):
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _advisory_key(identity)})


def _new_slug(catalog_id):
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", catalog_id):
        return catalog_id
    return "catalog-" + hashlib.sha256(catalog_id.encode("utf-8")).hexdigest()[:32]


def _insert_book(session, source, result):
    book = TutorialBook(
        category=source.category,
        subcategory="棋书",
        title=source.title,
        author=source.author,
        translator=source.translator,
        slug=_new_slug(source.catalog_id),
        asset_dir=f"tutorial_assets/catalog/{_segment(source.catalog_id)}",
    )
    source_to_figure = {}
    pages = {page.page: page for page in source.pages}
    for source_chapter in source.chapters:
        chapter = TutorialChapter(
            book=book, chapter_number=source_chapter.number, title=source_chapter.title, order=source_chapter.order
        )
        for source_section in source_chapter.sections:
            section = TutorialSection(
                chapter=chapter,
                section_number=source_section.number,
                title=source_section.title,
                order=source_section.order,
            )
            for order, source_figure in enumerate(source_section.figures, 1):
                figure = TutorialFigure(
                    section=section,
                    page=source_figure.page,
                    figure_label=source_figure.label,
                    book_text=source_figure.text,
                    page_context_text=source_figure.page_context_text,
                    bbox=copy.deepcopy(source_figure.bbox),
                    page_image_path=page_asset_key(source, pages[source_figure.page]),
                    board_payload=null(),
                    recognition_debug=null(),
                    order=order,
                )
                source_to_figure[source_figure.source_figure_id] = figure
    session.add(book)
    session.flush()  # One graph flush, never a round-trip per physical figure.
    result.book_id = book.id
    result.proposed_new = False
    result.figure_mappings = [
        _mapping(figure, source_to_figure[figure.source_figure_id].id, "new_created") for figure in source.figures
    ]


def _register_source(session, source, result):
    registered = TutorialSourceBook(
        source_namespace=SOURCE_NAMESPACE,
        catalog_id=source.catalog_id,
        book_id=result.book_id,
        source_json_sha256=source.source_json_sha256,
        assets_manifest_sha256=source.assets_manifest_sha256,
        source_metadata=copy.deepcopy(source.source_metadata),
        matching_evidence=copy.deepcopy(result.matching_evidence),
    )
    session.add(registered)
    session.flush()
    result.source_book_id = registered.id
    mapping = {item["source_figure_id"]: item for item in result.figure_mappings}
    chapters = {chapter.pointer: chapter for chapter in source.chapters}
    sections = {section.pointer: section for chapter in source.chapters for section in chapter.sections}
    for figure in source.figures:
        links = copy.deepcopy(figure.commentary_refs)
        for link in links:
            if "source_figure_id" in link:
                link["figure_id"] = mapping[link["source_figure_id"]]["figure_id"]
        metadata = {
            "raw_metadata": copy.deepcopy(figure.raw_metadata),
            "original_caption": {"label": figure.label, "title": figure.title, "text": figure.text},
            "bbox": copy.deepcopy(figure.bbox),
            "page_context_text": figure.page_context_text,
            "ordinal": figure.ordinal,
            "source_element_index": figure.source_element_index,
            "explicit_source_element_index": figure.explicit_source_element_index,
            "chapter": {
                "pointer": figure.chapter_pointer,
                "number": chapters[figure.chapter_pointer].number,
                "title": chapters[figure.chapter_pointer].title,
            },
            "section": {
                "pointer": figure.section_pointer,
                "number": sections[figure.section_pointer].number,
                "title": sections[figure.section_pointer].title,
                "synthetic": sections[figure.section_pointer].synthetic,
            },
            "commentary_refs": links,
        }
        session.add(
            TutorialSourceFigure(
                source_book_id=registered.id,
                source_figure_id=figure.source_figure_id,
                source_pointer=figure.pointer,
                page=figure.page,
                figure_id=mapping[figure.source_figure_id]["figure_id"],
                source_metadata=metadata,
                match_reason=mapping[figure.source_figure_id]["reason"],
            )
        )
    for page in source.pages:
        fragments = copy.deepcopy(page.text_fragments)
        for fragment in fragments:
            if fragment["kind"] == "figure_ref":
                fragment["figure_id"] = mapping[fragment["source_figure_id"]]["figure_id"]
                fragment["match_reason"] = mapping[fragment["source_figure_id"]]["reason"]
                fragment["original_caption"] = {name: fragment.get(name, "") for name in ("label", "title", "text")}
        session.add(
            TutorialSourcePage(
                source_book_id=registered.id,
                page=page.page,
                page_image_path=page_asset_key(source, page),
                image_sha256=page.image_sha256,
                text_fragments=fragments,
                page_context_text=page.page_context_text,
            )
        )
    result.commentary_aliases = _commentary_links(source, result.figure_mappings)


def import_catalog(session_factory, outcomes: list[SourceOutcome], asset_store: AssetStore) -> list[CatalogResult]:
    """Apply with fresh locked matching and a transaction for each book.

    The caller must have verified the target and created SOURCE_TABLES. Source
    validation failures/ambiguities do not write. Book transactions are isolated;
    arbitrary commit failures require read-only reconciliation before retrying.
    """
    results = []
    previous = {}
    for outcome in outcomes:
        if outcome.duplicate_of:
            result = _alias_result(outcome, previous, "apply")
        elif not outcome.book:
            result = _base_result(outcome, "apply")
        else:
            result = _base_result(outcome, "apply")
            created = []
            had_registry = False
            was_new = False
            try:
                with session_factory.begin() as session:
                    _lock_source(session, outcome.catalog_id)
                    result = plan_catalog(session, [outcome])[0]
                    result.mode = "apply"
                    had_registry = result.source_book_id is not None
                    was_new = result.status == "new"
                    if result.status in {"new", "existing_skipped"}:
                        registered = result.source_book_id is not None
                        for page in outcome.book.pages:
                            uploaded = asset_store.ensure_page(
                                page_asset_key(outcome.book, page), page, allow_create=not registered
                            )
                            if uploaded.created:
                                created.append(uploaded.key)
                        if not registered:
                            if result.status == "new":
                                _insert_book(session, outcome.book, result)
                            _register_source(session, outcome.book, result)
                    result.created_asset_keys = list(created)
            except Exception as exc:
                result.status = "failed"
                if was_new:
                    result.book_id = None
                if not had_registry:
                    result.source_book_id = None
                result.proposed_new = False
                result.created_asset_keys = list(created)
                result.orphan_asset_keys = list(created)
                if was_new or not result.figure_mappings:
                    result.figure_mappings = [
                        _mapping(figure, None, "book_transaction_failed") for figure in outcome.book.figures
                    ]
                result.commentary_aliases = _commentary_links(outcome.book, result.figure_mappings)
                result.error = (
                    exc.as_dict()
                    if isinstance(exc, CatalogImportError)
                    else {
                        "code": "book_transaction_failed",
                        "exception": type(exc).__name__,
                        "message": "Book transaction failed; reconcile database state with a read-only dry-run before retrying",
                    }
                )
        _mapping_counts(result)
        results.append(result)
        previous[outcome.catalog_id] = result
    return results


def write_catalog_reports(report_dir, results: list[CatalogResult], *, target=None):
    """Private JSON/CSV reports contain primitives and no connection credentials."""
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    report_dir.chmod(0o700)
    records = [result.as_dict() for result in results]
    report = {
        "report_version": 1,
        "mode": results[0].mode if results else "dry_run",
        "summary": dict(Counter(result.status for result in results)),
        "target": target,
        "outcomes": records,
    }
    json_reports = {
        "catalog-report.json": report,
        "null-figure-mappings.json": [
            {"catalog_id": result.catalog_id, **mapping}
            for result in results
            for mapping in result.figure_mappings
            if mapping["figure_id"] is None and mapping["reason"] != "proposed_new"
        ],
        "commentary-aliases.json": [
            {"catalog_id": result.catalog_id, **link} for result in results for link in result.commentary_aliases
        ],
    }
    for name, data in json_reports.items():
        path = report_dir / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        path.chmod(0o600)
    csv_reports = {
        "source-to-book.csv": (
            [
                "catalog_id",
                "status",
                "mode",
                "book_id",
                "source_book_id",
                "proposed_new",
                "duplicate_of",
                "figures",
                "pages",
                "error_code",
            ],
            [
                {
                    "catalog_id": r.catalog_id,
                    "status": r.status,
                    "mode": r.mode,
                    "book_id": r.book_id,
                    "source_book_id": r.source_book_id,
                    "proposed_new": r.proposed_new,
                    "duplicate_of": r.duplicate_of,
                    "figures": r.counts.get("figures", 0),
                    "pages": r.counts.get("pages", 0),
                    "error_code": (r.error or {}).get("code", ""),
                }
                for r in results
            ],
        ),
        "source-figure-map.csv": (
            [
                "catalog_id",
                "book_id",
                "source_figure_id",
                "source_pointer",
                "page",
                "chapter_pointer",
                "section_pointer",
                "label",
                "ordinal",
                "figure_id",
                "reason",
            ],
            [
                {"catalog_id": r.catalog_id, "book_id": r.book_id, **mapping}
                for r in results
                for mapping in r.figure_mappings
            ],
        ),
    }
    for name, (fields, rows) in csv_reports.items():
        path = report_dir / name
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        path.chmod(0o600)
    return report
