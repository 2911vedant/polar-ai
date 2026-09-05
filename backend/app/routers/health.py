from fastapi import APIRouter
from datetime import datetime, timezone
from app.config import settings
from app.database import check_db_connection, check_postgis
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check endpoint."""
    db_ok = check_db_connection()
    postgis_ok = check_postgis() if db_ok else False

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        database="connected" if db_ok else "disconnected",
        postgis=postgis_ok,
        data_mode=settings.DATA_MODE,
        llm_available=settings.has_llm,
        llm_provider=settings.llm_provider,
    )
