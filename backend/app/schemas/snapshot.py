from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SnapshotCreate(BaseModel):
    ref: str = Field(default="main", description="Git branch, tag or reference")
    commit_sha: str | None = Field(default=None, description="40-character hex commit SHA if known")

    @field_validator("commit_sha")
    @classmethod
    def validate_commit_sha(cls, v: str | None) -> str | None:
        if v is not None:
            clean = v.strip().lower()
            if not re.match(r"^[0-9a-f]{7,40}$", clean):
                raise ValueError("commit_sha must be a valid 7 to 40 character hexadecimal string.")
            return clean
        return None


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    ref: str
    commit_sha: str | None
    status: str
    embed_model: str | None
    embed_dim: int | None
    indexed_at: datetime | None
    error: str | None
    created_at: datetime
