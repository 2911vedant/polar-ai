from fastapi import APIRouter
from app.services import data_sources_service

router = APIRouter()


@router.get("/data-sources")
async def get_data_sources():
    """Get status of all data sources (real vs demo, last updated, etc.)."""
    return data_sources_service.get_data_sources_status()
