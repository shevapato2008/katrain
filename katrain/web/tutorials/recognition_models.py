"""Immutable recognition evidence. Importing models performs no DDL."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, event, func

from katrain.web.core.db import Base
from katrain.web.tutorials import source_models  # noqa: F401: register FK targets


class TutorialRecognitionCandidate(Base):
    __tablename__ = "tutorial_recognition_candidates"

    id = Column(Integer, primary_key=True)
    source_book_id = Column(Integer, ForeignKey("tutorial_source_books.id"), nullable=False, index=True)
    dataset = Column(String(128), nullable=False)
    recognition_id = Column(String(256), nullable=False)
    figure_id = Column(Integer, ForeignKey("tutorial_figures.id"), nullable=False, index=True)
    source_figure_id = Column(Integer, ForeignKey("tutorial_source_figures.id"), nullable=True, index=True)
    source_pointer = Column(Text, nullable=True)
    page = Column(Integer, nullable=False)
    source_content_sha256 = Column(String(64), nullable=False)
    raw_result = Column(JSON, nullable=False)
    board_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source_book_id", "dataset", "recognition_id", name="uq_tutorial_recognition_identity"),
    )


@event.listens_for(TutorialRecognitionCandidate, "before_update")
def _immutable_candidate(_mapper, _connection, _target):
    raise ValueError("Recognition candidates are immutable; create a new dataset identity")
