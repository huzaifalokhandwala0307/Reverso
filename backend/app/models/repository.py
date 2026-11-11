from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.app.database import Base
from sqlalchemy import BigInteger, Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.app.models.snapshot import Snapshot


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="github",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    installation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    default_branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="main",
    )
    allow_external_embeddings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    allow_external_llm: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    snapshots: Mapped[list[Snapshot]] = relationship(
        "Snapshot",
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="desc(Snapshot.created_at)",
    )
