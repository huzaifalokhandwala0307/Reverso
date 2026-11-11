from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.app.database import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.repository import Repository


class SnapshotStatus(enum.StrEnum):
    CREATED = "created"
    CLONING = "cloning"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    GRAPH_BUILDING = "graph_building"
    INDEXED = "indexed"
    FAILED = "failed"


VALID_SNAPSHOT_STATUSES = tuple(status.value for status in SnapshotStatus)


class Snapshot(Base):
    __tablename__ = "snapshots"

    __table_args__ = (
        CheckConstraint(
            f"status IN {VALID_SNAPSHOT_STATUSES}",
            name="ck_snapshots_status",
        ),
        UniqueConstraint(
            "repository_id",
            "commit_sha",
            name="uq_snapshots_repository_commit",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ref: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="main",
    )
    commit_sha: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=SnapshotStatus.CREATED.value,
    )
    embed_model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    embed_dim: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    repository: Mapped[Repository] = relationship(
        "Repository",
        back_populates="snapshots",
    )
