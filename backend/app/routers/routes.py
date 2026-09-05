from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.routes import (
    RouteGenerateRequest, RouteCompareRequest, RouteCompareResponse,
    RiskCalculateRequest, RiskCalculateResponse
)
from app.services import route_service, risk_service

router = APIRouter()


@router.post("/risk/calculate", response_model=RiskCalculateResponse)
async def calculate_risk(
    request: RiskCalculateRequest,
    db: Session = Depends(get_db)
):
    """Calculate navigation risk for a geographic location."""
    return risk_service.calculate_risk(request)


@router.post("/routes/generate")
async def generate_routes(
    request: RouteGenerateRequest,
    db: Session = Depends(get_db)
):
    """Generate navigation route(s) using A* algorithm."""
    return route_service.generate_routes(request)


@router.post("/routes/compare", response_model=RouteCompareResponse)
async def compare_routes(
    request: RouteCompareRequest,
    db: Session = Depends(get_db)
):
    """Generate and compare all route types (shortest, safest, fuel-efficient, balanced)."""
    return route_service.compare_routes(request)


@router.get("/routes/{route_id}")
async def get_route(route_id: str, db: Session = Depends(get_db)):
    """Get details of a previously generated route."""
    result = route_service.get_route_by_id(route_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Route '{route_id}' not found")
    return result
