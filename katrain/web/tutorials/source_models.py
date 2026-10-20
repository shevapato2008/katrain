"""Catalog provenance tables; importing this module never creates or changes tables."""

from sqlalchemy import Column, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

from katrain.web.core.db import Base

# Register the existing FK targets in the shared metadata without modifying legacy models.
from katrain.web.core.models_db import TutorialBook, TutorialFigure  # noqa: F401


class TutorialSourceBook(Base):
    __tablename__ = "tutorial_source_books"

    id = Column(Integer, primary_key=True)
    source_namespace = Column(String(64), nullable=False)
    catalog_id = Column(String(128), nullable=False)
    book_id = Column(Integer, ForeignKey("tutorial_books.id"), nullable=False, index=True)
    source_json_sha256 = Column(String(64), nullable=False)
    assets_manifest_sha256 = Column(String(64), nullable=False)
    source_metadata = Column(JSON, nullable=False)
    matching_evidence = Column(JSON, nullable=False)

    __table_args__ = (UniqueConstraint("source_namespace", "catalog_id", name="uq_tutorial_source_book_identity"),)


class TutorialSourceFigure(Base):
    __tablename__ = "tutorial_source_figures"

    id = Column(Integer, primary_key=True)
    source_book_id = Column(Integer, ForeignKey("tutorial_source_books.id"), nullable=False, index=True)
    source_figure_id = Column(String(256), nullable=False)
    source_pointer = Column(Text, nullable=False)
    page = Column(Integer, nullable=False)
    figure_id = Column(Integer, ForeignKey("tutorial_figures.id"), nullable=True, index=True)
    source_metadata = Column(JSON, nullable=False)
    match_reason = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_book_id", "source_figure_id", name="uq_tutorial_source_figure_identity"),
        UniqueConstraint("source_book_id", "figure_id", name="uq_tutorial_source_figure_target"),
    )


class TutorialSourcePage(Base):
    __tablename__ = "tutorial_source_pages"

    id = Column(Integer, primary_key=True)
    source_book_id = Column(Integer, ForeignKey("tutorial_source_books.id"), nullable=False, index=True)
    page = Column(Integer, nullable=False)
    page_image_path = Column(String(512), nullable=False)
    image_sha256 = Column(String(64), nullable=False)
    text_fragments = Column(JSON, nullable=False)
    page_context_text = Column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("source_book_id", "page", name="uq_tutorial_source_page_identity"),)
