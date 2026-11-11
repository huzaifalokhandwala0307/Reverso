from __future__ import annotations

from pydantic import BaseModel, Field


class PaginatedResponse[T](BaseModel):
    items: list[T] = Field(default_factory=list, description="Page items")
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor token for retrieving the next page, or null if last page",
    )
