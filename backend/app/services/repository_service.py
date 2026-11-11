from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

from backend.app.models.repository import Repository
from backend.app.schemas.repository import (
    RepositoryCreate,
    RepositoryUpdate,
    parse_and_validate_github_url,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


class RepositoryService:
    @staticmethod
    def encode_cursor(repo_id: uuid.UUID) -> str:
        return base64.urlsafe_b64encode(str(repo_id).encode("utf-8")).decode("utf-8")

    @staticmethod
    def decode_cursor(cursor_str: str) -> uuid.UUID | None:
        try:
            raw = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
            return uuid.UUID(raw)
        except Exception:
            return None

    @classmethod
    def create_repository(
        cls,
        db: Session,
        repo_in: RepositoryCreate,
        owner_id: uuid.UUID | None = None,
    ) -> Repository:
        normalized_url, owner, repo = parse_and_validate_github_url(repo_in.url)
        name = repo_in.name if repo_in.name else f"{owner}/{repo}"

        repository = Repository(
            id=uuid.uuid4(),
            owner_id=owner_id,
            source="github",
            name=name,
            url=normalized_url,
            installation_id=repo_in.installation_id,
            default_branch=repo_in.default_branch,
            allow_external_embeddings=repo_in.allow_external_embeddings,
            allow_external_llm=repo_in.allow_external_llm,
            created_at=datetime.now(UTC),
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)
        return repository

    @classmethod
    def get_repository(cls, db: Session, repository_id: uuid.UUID) -> Repository | None:
        return db.get(Repository, repository_id)

    @classmethod
    def list_repositories(
        cls,
        db: Session,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Repository], str | None]:
        safe_limit = max(1, min(limit, 200))
        query = select(Repository).order_by(Repository.created_at.desc(), Repository.id.desc())

        if cursor:
            cursor_id = cls.decode_cursor(cursor)
            if cursor_id:
                cursor_repo = db.get(Repository, cursor_id)
                if cursor_repo:
                    query = query.where(
                        (Repository.created_at < cursor_repo.created_at)
                        | (
                            (Repository.created_at == cursor_repo.created_at)
                            & (Repository.id < cursor_repo.id)
                        )
                    )

        # Fetch one extra to determine next_cursor
        results = db.scalars(query.limit(safe_limit + 1)).all()
        items = list(results)

        next_cursor = None
        if len(items) > safe_limit:
            items = items[:safe_limit]
            last_item = items[-1]
            next_cursor = cls.encode_cursor(last_item.id)

        return items, next_cursor

    @classmethod
    def update_repository(
        cls,
        db: Session,
        repository: Repository,
        update_in: RepositoryUpdate,
    ) -> Repository:
        if update_in.default_branch is not None:
            repository.default_branch = update_in.default_branch
        if update_in.allow_external_embeddings is not None:
            repository.allow_external_embeddings = update_in.allow_external_embeddings
        if update_in.allow_external_llm is not None:
            repository.allow_external_llm = update_in.allow_external_llm

        db.add(repository)
        db.commit()
        db.refresh(repository)
        return repository
