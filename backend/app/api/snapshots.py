from __future__ import annotations

import uuid

from backend.app.api.exceptions import NotFoundError
from backend.app.database import get_db
from backend.app.schemas.snapshot import SnapshotRead
from backend.app.services.snapshot_service import SnapshotService
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/snapshots", tags=["Snapshots"])


@router.get("/{snapshot_id}", response_model=SnapshotRead)
def get_snapshot(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SnapshotRead:
    """Retrieve details for a single snapshot."""
    snapshot = SnapshotService.get_snapshot(db, snapshot_id)
    if not snapshot:
        raise NotFoundError("Snapshot", snapshot_id)
    return SnapshotRead.model_validate(snapshot)
