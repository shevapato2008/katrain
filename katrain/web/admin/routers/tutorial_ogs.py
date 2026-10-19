"""Authenticated, read-only OGS tutorial views; never initialize missing tables."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.web.core.models_db import TutorialBook, TutorialChapter, TutorialFigure, TutorialSection
from katrain.web.tutorials.ogs_course import course_index, export_zip, step_output
from katrain.web.tutorials.ogs_models import TutorialOgsCourse, TutorialOgsStep

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _unavailable():
    return HTTPException(status_code=503, detail="OGS tutorial course is unavailable")


def _load(db, book_id):
    book = db.get(TutorialBook, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    course = db.scalar(select(TutorialOgsCourse).where(TutorialOgsCourse.book_id == book.id))
    if course is None:
        raise HTTPException(status_code=404, detail="OGS course not found")
    return book, course


@router.get("/books/{book_id}/ogs-course")
def get_ogs_course(book_id: int, db: Session = Depends(get_admin_db)):
    try:
        book, course = _load(db, book_id)
        return course_index(db, book, course)
    except (OperationalError, ProgrammingError, KeyError, TypeError, ValueError) as exc:
        raise _unavailable() from exc


@router.get("/books/{book_id}/ogs-steps/{page}")
def get_ogs_step(book_id: int, page: int, lang: str = "zh-cn", db: Session = Depends(get_admin_db)):
    try:
        book, course = _load(db, book_id)
        if lang not in course.catalog["languages"]:
            raise HTTPException(status_code=404, detail="OGS language not found")
        step = db.scalar(
            select(TutorialOgsStep)
            .join(TutorialFigure, TutorialOgsStep.figure_id == TutorialFigure.id)
            .join(TutorialSection, TutorialFigure.section_id == TutorialSection.id)
            .join(TutorialChapter, TutorialSection.chapter_id == TutorialChapter.id)
            .where(
                TutorialOgsStep.course_id == course.id, TutorialOgsStep.page == page, TutorialChapter.book_id == book.id
            )
        )
        if step is None:
            raise HTTPException(status_code=404, detail="OGS step not found")
        return step_output(book.id, step, lang)
    except (OperationalError, ProgrammingError, KeyError, TypeError, ValueError) as exc:
        raise _unavailable() from exc


@router.get("/books/{book_id}/ogs-export")
def get_ogs_export(book_id: int, db: Session = Depends(get_admin_db)):
    try:
        book, course = _load(db, book_id)
        return Response(
            export_zip(db, book, course),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="ogs-learn-to-play-go.zip"'},
        )
    except (OperationalError, ProgrammingError, KeyError, TypeError, ValueError) as exc:
        raise _unavailable() from exc
