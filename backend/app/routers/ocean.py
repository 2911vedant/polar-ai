from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import ocean_service

router = APIRouter()


@router.get("/current")
async def get_ocean_current(db: Session = Depends(get_db)):
    """Get current Antarctic ocean conditions (currents, SST)."""
    return ocean_service.get_current_ocean()
