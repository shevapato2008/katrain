"""Repository for live comment database operations."""

from typing import Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_

from katrain.web.core.models_db import LiveCommentDB, User

logger = logging.getLogger("katrain_web")


class LiveCommentRepo:
    """Repository for managing live match comments in the database."""

    def __init__(self, db: Session):
        self.db = db

    def get_comments(
        self,
        match_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> list[LiveCommentDB]:
        """Get comments for a match, ordered by creation time (newest last).

        Args:
            match_id: The match ID
            limit: Maximum number of comments to return
            offset: Number of comments to skip

        Returns:
            List of comment records
        """
        return self.db.query(LiveCommentDB).filter(
            and_(
                LiveCommentDB.match_id == match_id,
                LiveCommentDB.is_deleted == False
            )
        ).order_by(
            LiveCommentDB.created_at.asc()
        ).offset(offset).limit(limit).all()

    def get_comment_count(self, match_id: str) -> int:
        """Get total number of non-deleted comments for a match."""
        return self.db.query(LiveCommentDB).filter(
            and_(
                LiveCommentDB.match_id == match_id,
                LiveCommentDB.is_deleted == False
            )
        ).count()

    def create_comment(
        self,
        match_id: str,
        user_id: int,
        content: str
    ) -> LiveCommentDB:
        """Create a new comment.

        Args:
            match_id: The match ID
            user_id: The user ID
            content: Comment text

        Returns:
            Created comment record
        """
        comment = LiveCommentDB(
            match_id=match_id,
            user_id=user_id,
            content=content,
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        logger.info(f"Created comment {comment.id} on match {match_id} by user {user_id}")
        return comment

    def delete_comment(
        self,
        comment_id: int,
        user_id: int
    ) -> bool:
        """Soft delete a comment (only by the owner).

        Args:
            comment_id: The comment ID
            user_id: The requesting user's ID

        Returns:
            True if deleted, False if not found or not authorized
        """
        comment = self.db.query(LiveCommentDB).filter(
            LiveCommentDB.id == comment_id
        ).first()

        if not comment:
            logger.warning(f"Comment {comment_id} not found for deletion")
            return False

        if comment.user_id != user_id:
            logger.warning(f"User {user_id} not authorized to delete comment {comment_id}")
            return False

        comment.is_deleted = True
        self.db.commit()
        logger.info(f"Deleted comment {comment_id}")
        return True

    def get_comment_by_id(self, comment_id: int) -> Optional[LiveCommentDB]:
        """Get a comment by ID."""
        return self.db.query(LiveCommentDB).filter(
            LiveCommentDB.id == comment_id
        ).first()

    def get_recent_comments(
        self,
        match_id: str,
        since_id: int = 0,
        limit: int = 20
    ) -> list[LiveCommentDB]:
        """Get comments newer than a given ID (for polling).

        Args:
            match_id: The match ID
            since_id: Only return comments with ID greater than this
            limit: Maximum number of comments to return

        Returns:
            List of new comment records
        """
        return self.db.query(LiveCommentDB).filter(
            and_(
                LiveCommentDB.match_id == match_id,
                LiveCommentDB.id > since_id,
                LiveCommentDB.is_deleted == False
            )
        ).order_by(
            LiveCommentDB.created_at.asc()
        ).limit(limit).all()
