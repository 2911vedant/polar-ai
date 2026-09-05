from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import weather_service

router = APIRouter()


@router.get("/current")
async def get_weather_current(db: Session = Depends(get_db)):
    """Get current Antarctic meteorological conditions."""
    return weather_service.get_current_weather()


@router.get("/forecast")
async def get_weather_forecast(
    horizon_hours: int = 72,
    db: Session = Depends(get_db)
):
    """Get weather forecast for specified horizon."""
    return weather_service.get_forecast(horizon_hours=horizon_hours)
