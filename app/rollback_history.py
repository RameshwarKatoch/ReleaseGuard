from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime, timezone

from app.models import Base


class RollbackHistory(Base):
    __tablename__ = "rollback_history"

    id = Column(Integer, primary_key=True, index=True)

    release_id = Column(
        Integer,
        ForeignKey("releases.id"),
        nullable=False
    )

    target_release_id = Column(
        Integer,
        ForeignKey("releases.id"),
        nullable=False
    )

    target_commit_sha = Column(
        String,
        nullable=False
    )

    status = Column(
        String,
        nullable=False
    )

    started_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    completed_at = Column(
        DateTime,
        nullable=True
    )