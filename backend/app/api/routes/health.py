from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AppError
from app.infrastructure.db.session import check_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    app: str
    env: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    from app.core.config import get_settings

    settings = get_settings()
    try:
        check_database()
        db_status = "ok"
    except SQLAlchemyError as exc:
        raise AppError(
            "database_error",
            "Database is unavailable",
            status_code=503,
            details={"reason": type(exc).__name__},
        ) from exc

    return HealthResponse(
        status="ok",
        database=db_status,
        app=settings.app_name,
        env=settings.app_env,
    )
