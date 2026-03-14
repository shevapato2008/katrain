from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from katrain.web.core.models_db import UserTutorialProgress


def get_user_progress(db: Session, user_id: int) -> List[Dict]:
    rows = db.query(UserTutorialProgress).filter_by(user_id=user_id).all()
    return [
        {
            "example_id": r.example_id,
            "topic_id": r.topic_id,
            "last_step_id": r.last_step_id,
            "completed": r.completed,
            "last_played_at": r.last_played_at.isoformat() if r.last_played_at else None,
        }
        for r in rows
    ]


def upsert_progress(
    db: Session,
    user_id: int,
    example_id: str,
    topic_id: str,
    last_step_id: str,
    completed: bool,
) -> Dict:
    row = db.query(UserTutorialProgress).filter_by(
        user_id=user_id, example_id=example_id
    ).first()
    if row is None:
        row = UserTutorialProgress(
            user_id=user_id,
            example_id=example_id,
            topic_id=topic_id,
        )
        db.add(row)
    row.last_step_id = last_step_id
    row.completed = completed
    # Explicit Python-side timestamp; DB onupdate=func.now() is a fallback for
    # direct SQL updates that bypass SQLAlchemy.
    row.last_played_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return {
        "example_id": row.example_id,
        "topic_id": row.topic_id,
        "last_step_id": row.last_step_id,
        "completed": row.completed,
        "last_played_at": row.last_played_at.isoformat() if row.last_played_at else None,
    }
