from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import analytics_service

router = APIRouter()


@router.get("/analytics")
async def get_analytics(
    days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db)
):
    """Get analytics data: trends, distributions, model performance."""
    return analytics_service.get_analytics(days=days)
