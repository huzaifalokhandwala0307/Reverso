from __future__ import annotations

import logging

from backend.app.api.exceptions import APIError
from backend.app.api.health import router as health_router
from backend.app.api.repositories import router as repositories_router
from backend.app.api.snapshots import router as snapshots_router
from backend.app.config import settings
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("blackboxrag")

app = FastAPI(
    title=settings.APP_NAME,
    description="BlackBoxRAG Repository Intelligence API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Include routers
app.include_router(health_router)
app.include_router(repositories_router)
app.include_router(snapshots_router)


# ─────────────────────────────────────────────────────────────────────────────
# Standard Error Envelope Exception Handlers
# ─────────────────────────────────────────────────────────────────────────────


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    # Format a human-readable summary
    first_error = errors[0] if errors else {}
    msg = first_error.get("msg", "Validation error")
    loc = " -> ".join(str(loc_item) for loc_item in first_error.get("loc", []))
    summary_message = f"{loc}: {msg}" if loc else msg

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": {
                "code": "validation_error",
                "message": summary_message,
                "details": jsonable_encoder(errors),
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "not_found" if exc.status_code == 404 else "http_error"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "details": None,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected server error occurred.",
                "details": str(exc) if settings.DEBUG else None,
            }
        },
    )
