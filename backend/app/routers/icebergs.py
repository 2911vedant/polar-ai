from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import iceberg_service
from app.schemas.icebergs import TrajectoryPredictRequest

router = APIRouter()


@router.get("")
async def list_icebergs(db: Session = Depends(get_db)):
    """List all active tracked icebergs."""
    return iceberg_service.list_icebergs()


@router.get("/{iceberg_name}")
async def get_iceberg(iceberg_name: str, db: Session = Depends(get_db)):
    """Get detailed information for a specific iceberg."""
    result = iceberg_service.get_iceberg_detail(iceberg_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Iceberg '{iceberg_name}' not found")
    return result


@router.get("/{iceberg_name}/trajectory")
async def get_iceberg_trajectory(
    iceberg_name: str,
    horizon_hours: int = 72,
    db: Session = Depends(get_db)
):
    """Get predicted trajectory for a specific iceberg."""
    result = iceberg_service.get_trajectory(iceberg_name, horizon_hours)
    if not result:
        raise HTTPException(status_code=404, detail=f"Iceberg '{iceberg_name}' not found")
    return result


@router.post("/detect")
async def detect_icebergs(db: Session = Depends(get_db)):
    """Run iceberg detection on latest satellite data."""
    return iceberg_service.detect_icebergs()


@router.post("/trajectory/predict")
async def predict_trajectory(
    request: TrajectoryPredictRequest,
    db: Session = Depends(get_db)
):
    """Predict trajectory for an arbitrary point (iceberg or custom location)."""
    return iceberg_service.predict_trajectory(request)
