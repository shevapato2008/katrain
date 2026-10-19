"""OGS provenance only; importing models never initializes database tables."""

from sqlalchemy import Column, ForeignKey, Integer, JSON, String, UniqueConstraint

from katrain.web.core.db import Base
from katrain.web.core.models_db import TutorialBook, TutorialFigure  # noqa: F401


class TutorialOgsCourse(Base):
    __tablename__ = "tutorial_ogs_courses"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("tutorial_books.id"), nullable=False, unique=True)
    source_commit = Column(String(40), nullable=False)
    locale_version = Column(String(64), nullable=False)
    content_sha256 = Column(String(64), nullable=False)
    catalog = Column(JSON, nullable=False)


class TutorialOgsStep(Base):
    __tablename__ = "tutorial_ogs_steps"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("tutorial_ogs_courses.id"), nullable=False, index=True)
    source_id = Column(String(256), nullable=False)
    page = Column(Integer, nullable=False)
    figure_id = Column(Integer, ForeignKey("tutorial_figures.id"), nullable=False, unique=True)
    content_sha256 = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    screenshot = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("course_id", "source_id", name="uq_ogs_step_source"),
        UniqueConstraint("course_id", "page", name="uq_ogs_step_page"),
    )
