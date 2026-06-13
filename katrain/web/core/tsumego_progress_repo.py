"""Local repository + shared merge logic for tsumego progress (board offline mode).

Mirrors the style of ``core/user_game_repo.py``. The merge rules here are the
single source of truth — both this local repo and the server-mode direct-DB
path in ``api/v1/endpoints/tsumego.py`` call ``merge_tsumego_progress`` so the
field semantics never drift.

Field merge invariants (design.md Section 4.12.2):
  - attempts:           max(existing, incoming)
  - completed:          existing OR incoming   (monotonic — never regresses)
  - last_duration:      incoming if not None else existing
  - first_completed_at: earliest non-null (set to now when completing for the
                        first time and not previously set)
  - last_attempt_at:    now
"""

from datetime import datetime
from typing import Dict, Optional

from katrain.web.core import models_db


def merge_tsumego_progress(existing: Optional[dict], incoming: dict, now: Optional[datetime] = None) -> dict:
    """Merge an incoming progress update onto an existing record.

    Args:
        existing: Current persisted fields (or None for a brand-new record).
                  Recognized keys: completed, attempts, last_duration,
                  first_completed_at, last_attempt_at.
        incoming: Update from the client. Recognized keys: completed, attempts,
                  lastDuration (camelCase, matching ``ProgressUpdate``).
        now: Timestamp to stamp last_attempt_at / first_completed_at. Defaults
             to ``datetime.utcnow()``; passed in for deterministic tests.

    Returns:
        A dict of merged fields keyed by DB column name:
        {completed, attempts, last_duration, first_completed_at, last_attempt_at}.
    """
    now = now or datetime.utcnow()
    existing = existing or {}

    existing_attempts = existing.get("attempts") or 0
    incoming_attempts = incoming.get("attempts") or 0

    existing_completed = bool(existing.get("completed"))
    incoming_completed = bool(incoming.get("completed"))
    completed = existing_completed or incoming_completed

    # last_duration: incoming if provided, else keep existing
    incoming_duration = incoming.get("lastDuration")
    last_duration = incoming_duration if incoming_duration is not None else existing.get("last_duration")

    # first_completed_at: earliest non-null; set to now when completing for the
    # first time and there is no prior completion timestamp.
    first_completed_at = existing.get("first_completed_at")
    if completed and not first_completed_at:
        first_completed_at = now

    return {
        "completed": completed,
        "attempts": max(existing_attempts, incoming_attempts),
        "last_duration": last_duration,
        "first_completed_at": first_completed_at,
        "last_attempt_at": now,
    }


class LocalTsumegoProgressRepository:
    """Local SQLite store for per-user tsumego progress (board offline mode)."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def upsert(self, user_id: int, problem_id: str, data: dict) -> dict:
        """Insert or merge a progress row keyed by (user_id, problem_id).

        ``data`` uses the client/``ProgressUpdate`` camelCase shape
        ({completed, attempts, lastDuration}). Returns the merged row as a
        plain dict in the same camelCase shape that GET /progress returns.
        """
        session = self.session_factory()
        try:
            row = (
                session.query(models_db.UserTsumegoProgress)
                .filter(
                    models_db.UserTsumegoProgress.user_id == user_id,
                    models_db.UserTsumegoProgress.problem_id == problem_id,
                )
                .first()
            )

            existing = None
            if row is not None:
                existing = {
                    "completed": row.completed,
                    "attempts": row.attempts,
                    "last_duration": row.last_duration,
                    "first_completed_at": row.first_completed_at,
                    "last_attempt_at": row.last_attempt_at,
                }

            merged = merge_tsumego_progress(existing, data)

            if row is None:
                row = models_db.UserTsumegoProgress(
                    user_id=user_id,
                    problem_id=problem_id,
                    completed=merged["completed"],
                    attempts=merged["attempts"],
                    last_duration=merged["last_duration"],
                    first_completed_at=merged["first_completed_at"],
                    last_attempt_at=merged["last_attempt_at"],
                )
                session.add(row)
            else:
                row.completed = merged["completed"]
                row.attempts = merged["attempts"]
                row.last_duration = merged["last_duration"]
                row.first_completed_at = merged["first_completed_at"]
                row.last_attempt_at = merged["last_attempt_at"]

            session.commit()
            session.refresh(row)
            return self._to_dict(row)
        finally:
            session.close()

    def list(self, user_id: int) -> Dict[str, dict]:
        """Return {problem_id: {completed, attempts, firstCompletedAt, ...}}.

        Shape mirrors GET /progress (camelCase) so online vs offline reads are
        interchangeable for the frontend.
        """
        session = self.session_factory()
        try:
            rows = (
                session.query(models_db.UserTsumegoProgress)
                .filter(models_db.UserTsumegoProgress.user_id == user_id)
                .all()
            )
            return {row.problem_id: self._to_dict(row) for row in rows}
        finally:
            session.close()

    @staticmethod
    def _to_dict(row: "models_db.UserTsumegoProgress") -> dict:
        return {
            "problemId": row.problem_id,
            "completed": bool(row.completed),
            "attempts": row.attempts or 0,
            "firstCompletedAt": row.first_completed_at.isoformat() if row.first_completed_at else None,
            "lastAttemptAt": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
            "lastDuration": row.last_duration,
        }
