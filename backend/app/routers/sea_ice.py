from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.services import sea_ice_service
from app.schemas.sea_ice import SeaIcePredictRequest

router = APIRouter()


@router.get("/current")
async def get_current_sea_ice(
    resolution: str = Query(default="low", enum=["low", "medium", "high"]),
    db: Session = Depends(get_db)
):
    """Get current Antarctic sea-ice concentration grid."""
    return sea_ice_service.get_current_sea_ice(resolution=resolution)


@router.get("/history")
async def get_sea_ice_history(
    days: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db)
):
    """Get historical sea-ice concentration time-series."""
    return sea_ice_service.get_history(days=days)


@router.get("/forecast")
async def get_sea_ice_forecast(
    horizon_hours: int = Query(default=72, ge=24, le=168),
    db: Session = Depends(get_db)
):
    """Get sea-ice concentration forecast for specified horizon."""
    return sea_ice_service.get_forecast(horizon_hours=horizon_hours)


@router.post("/predict")
async def predict_sea_ice(
    request: SeaIcePredictRequest,
    db: Session = Depends(get_db)
):
    """Run on-demand sea-ice concentration prediction."""
    return sea_ice_service.predict(request)
