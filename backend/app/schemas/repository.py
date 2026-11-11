from __future__ import annotations

import re
import uuid
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


def parse_and_validate_github_url(raw_url: str) -> tuple[str, str, str]:
    """
    Validates that a URL is a valid GitHub repository URL.
    Returns (normalized_url, owner, repo).
    Raises ValueError on invalid host or format.
    """
    url = raw_url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in ("github.com", "www.github.com"):
        raise ValueError("Only github.com repository URLs are supported.")

    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) != 2:
        raise ValueError("GitHub URL must follow the format 'https://github.com/owner/repo'")

    owner, repo = parts[0], parts[1]
    # Basic identifier pattern validation for GitHub usernames and repo names
    if not re.match(r"^[A-Za-z0-9_.-]+$", owner) or not re.match(r"^[A-Za-z0-9_.-]+$", repo):
        raise ValueError("Invalid owner or repository name in GitHub URL.")

    normalized_url = f"https://github.com/{owner}/{repo}"
    return normalized_url, owner, repo


class RepositoryCreate(BaseModel):
    url: str = Field(..., description="GitHub repository URL")
    name: str | None = Field(
        default=None,
        description="Optional repository name. Defaults to owner/repo",
    )
    default_branch: str = Field(default="main", description="Default branch name")
    installation_id: int | None = Field(
        default=None,
        description="GitHub App installation ID if connected",
    )
    allow_external_embeddings: bool = Field(
        default=False,
        description="Whether external embedding providers (e.g. Voyage, OpenAI) are permitted",
    )
    allow_external_llm: bool = Field(
        default=False,
        description="Whether external LLM providers (e.g. OpenAI, Anthropic) are permitted",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        normalized_url, _, _ = parse_and_validate_github_url(v)
        return normalized_url


class RepositoryUpdate(BaseModel):
    default_branch: str | None = Field(default=None, description="Updated default branch name")
    allow_external_embeddings: bool | None = Field(
        default=None,
        description="Updated external embeddings privacy setting",
    )
    allow_external_llm: bool | None = Field(
        default=None,
        description="Updated external LLM privacy setting",
    )


class RepositoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID | None
    source: str
    name: str
    url: str
    installation_id: int | None
    default_branch: str
    allow_external_embeddings: bool
    allow_external_llm: bool
    created_at: datetime
