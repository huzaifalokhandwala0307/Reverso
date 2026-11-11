from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.app.models.snapshot import Snapshot, SnapshotStatus
from backend.app.schemas.snapshot import SnapshotCreate
from sqlalchemy import select
from sqlalchemy.orm import Session


class DuplicateSnapshotError(Exception):
    def __init__(self, repository_id: uuid.UUID, commit_sha: str):
        self.repository_id = repository_id
        self.commit_sha = commit_sha
        msg = (
            f"A snapshot with commit SHA '{commit_sha}' already exists "
            f"for repository {repository_id}."
        )
        super().__init__(msg)


class SnapshotService:
    @classmethod
    def create_snapshot(
        cls,
        db: Session,
        repository_id: uuid.UUID,
        snapshot_in: SnapshotCreate,
    ) -> Snapshot:
        # Check duplicate commit_sha if commit_sha is provided
        if snapshot_in.commit_sha:
            existing = db.scalar(
                select(Snapshot).where(
                    Snapshot.repository_id == repository_id,
                    Snapshot.commit_sha == snapshot_in.commit_sha,
                )
            )
            if existing:
                raise DuplicateSnapshotError(repository_id, snapshot_in.commit_sha)

        snapshot = Snapshot(
            id=uuid.uuid4(),
            repository_id=repository_id,
            ref=snapshot_in.ref,
            commit_sha=snapshot_in.commit_sha,
            status=SnapshotStatus.CREATED.value,
            created_at=datetime.now(UTC),
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @classmethod
    def get_snapshot(cls, db: Session, snapshot_id: uuid.UUID) -> Snapshot | None:
        return db.get(Snapshot, snapshot_id)

    @classmethod
    def list_snapshots_for_repository(
        cls,
        db: Session,
        repository_id: uuid.UUID,
    ) -> list[Snapshot]:
        stmt = (
            select(Snapshot)
            .where(Snapshot.repository_id == repository_id)
            .order_by(Snapshot.created_at.desc())
        )
        return list(db.scalars(stmt).all())
