from __future__ import annotations

from backend.app.database import get_db
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health_liveness() -> dict[str, str]:
    """Liveness probe: verifies the application process is running."""
    return {"status": "ok"}


@router.get("/health/ready")
def health_readiness(db: Session = Depends(get_db)):
    """Readiness probe: verifies the database connection is operational."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "Database readiness probe failed.",
                    "details": str(e),
                }
            },
        )
