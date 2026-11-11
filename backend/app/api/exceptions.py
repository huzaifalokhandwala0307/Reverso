from __future__ import annotations

from typing import Any


class APIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(APIError):
    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            code=f"{resource.lower()}_not_found",
            message=f"{resource} '{resource_id}' was not found.",
            status_code=404,
        )


class ConflictError(APIError):
    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(
            code=code,
            message=message,
            status_code=409,
            details=details,
        )


class BadRequestError(APIError):
    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(
            code=code,
            message=message,
            status_code=400,
            details=details,
        )
