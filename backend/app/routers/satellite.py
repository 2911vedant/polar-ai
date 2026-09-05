"""Satellite product endpoints."""
from fastapi import APIRouter, HTTPException
from app.sources.satellite_source import get_satellite_source
from app.core.freshness import FreshnessRegistry
from datetime import datetime, timezone

router = APIRouter()


@router.get("/satellite/latest")
async def get_latest_satellite():
    """Return the most recently acquired Sentinel-1 product metadata."""
    source = get_satellite_source()
    product = source.get_latest_product()
    freshness = FreshnessRegistry.get("satellite")

    if not product:
        # No real product available — clearly state this
        return {
            "product": None,
            "status": "no_data",
            "message": (
                "No Sentinel-1 products in cache. "
                "Set COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET to enable satellite data."
                if not source.is_configured()
                else "No products found yet — search in progress."
            ),
            "freshness": freshness.to_dict() if freshness else None,
            "data_mode": "demo",
            "is_real": False,
        }

    return {
        "product": product,
        "freshness": freshness.to_dict() if freshness else None,
        "data_mode": "live",
        "is_real": True,
    }


@router.get("/satellite/products")
async def list_satellite_products():
    """Return all cached Sentinel-1 products."""
    source = get_satellite_source()
    products = source.get_all_products()
    freshness = FreshnessRegistry.get("satellite")

    return {
        "products": products,
        "count": len(products),
        "freshness": freshness.to_dict() if freshness else None,
        "data_mode": "live" if products and source.is_configured() else "demo",
        "is_real": source.is_configured(),
        "note": (
            None if source.is_configured()
            else "Satellite data requires COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET"
        ),
    }


@router.get("/satellite/{product_id}")
async def get_satellite_product(product_id: str):
    """Return metadata for a specific product by ID."""
    source = get_satellite_source()
    products = source.get_all_products()
    product = next((p for p in products if p.get("product_id") == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    return product


@router.post("/satellite/refresh")
async def refresh_satellite():
    """Trigger a new satellite product search (requires credentials)."""
    source = get_satellite_source()
    if not source.is_configured():
        return {
            "status": "skipped",
            "reason": "Copernicus credentials not configured",
            "required_env": ["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"],
        }
    try:
        products = await source.fetch()
        return {"status": "ok", "count": len(products) if products else 0}
    except Exception as e:
        return {"status": "error", "error": str(e)}
