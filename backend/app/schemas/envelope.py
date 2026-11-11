from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")
    details: Any = Field(default=None, description="Optional diagnostic details")


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
