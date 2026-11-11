from __future__ import annotations

import uuid

from backend.app.api.exceptions import ConflictError, NotFoundError
from backend.app.database import get_db
from backend.app.schemas.pagination import PaginatedResponse
from backend.app.schemas.repository import RepositoryCreate, RepositoryRead, RepositoryUpdate
from backend.app.schemas.snapshot import SnapshotCreate, SnapshotRead
from backend.app.services.repository_service import RepositoryService
from backend.app.services.snapshot_service import DuplicateSnapshotError, SnapshotService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


@router.post("", response_model=RepositoryRead, status_code=status.HTTP_201_CREATED)
def create_repository(
    repo_in: RepositoryCreate,
    db: Session = Depends(get_db),
) -> RepositoryRead:
    """Register a new repository from a GitHub URL."""
    repo = RepositoryService.create_repository(db, repo_in, owner_id=None)
    return RepositoryRead.model_validate(repo)


@router.get("", response_model=PaginatedResponse[RepositoryRead])
def list_repositories(
    cursor: str | None = Query(default=None, description="Cursor for pagination"),
    limit: int = Query(default=50, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[RepositoryRead]:
    """List registered repositories with cursor-based pagination."""
    items, next_cursor = RepositoryService.list_repositories(db, cursor=cursor, limit=limit)
    return PaginatedResponse(
        items=[RepositoryRead.model_validate(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/{repository_id}", response_model=RepositoryRead)
def get_repository(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RepositoryRead:
    """Retrieve details for a single repository."""
    repo = RepositoryService.get_repository(db, repository_id)
    if not repo:
        raise NotFoundError("Repository", repository_id)
    return RepositoryRead.model_validate(repo)


@router.patch("/{repository_id}", response_model=RepositoryRead)
def update_repository(
    repository_id: uuid.UUID,
    update_in: RepositoryUpdate,
    db: Session = Depends(get_db),
) -> RepositoryRead:
    """Update repository settings: default branch and privacy flags."""
    repo = RepositoryService.get_repository(db, repository_id)
    if not repo:
        raise NotFoundError("Repository", repository_id)

    updated = RepositoryService.update_repository(db, repo, update_in)
    return RepositoryRead.model_validate(updated)


@router.post(
    "/{repository_id}/snapshots",
    response_model=SnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    repository_id: uuid.UUID,
    snapshot_in: SnapshotCreate,
    db: Session = Depends(get_db),
) -> SnapshotRead:
    """Create a new snapshot for a repository with status 'created'."""
    repo = RepositoryService.get_repository(db, repository_id)
    if not repo:
        raise NotFoundError("Repository", repository_id)

    try:
        snapshot = SnapshotService.create_snapshot(db, repository_id, snapshot_in)
        return SnapshotRead.model_validate(snapshot)
    except DuplicateSnapshotError as e:
        raise ConflictError(
            code="duplicate_snapshot",
            message=str(e),
            details={"repository_id": str(repository_id), "commit_sha": snapshot_in.commit_sha},
        ) from e


@router.get(
    "/{repository_id}/snapshots",
    response_model=list[SnapshotRead],
)
def list_snapshots(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[SnapshotRead]:
    """List all snapshots for a given repository."""
    repo = RepositoryService.get_repository(db, repository_id)
    if not repo:
        raise NotFoundError("Repository", repository_id)

    snapshots = SnapshotService.list_snapshots_for_repository(db, repository_id)
    return [SnapshotRead.model_validate(s) for s in snapshots]
