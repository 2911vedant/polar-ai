"""Data sources status — driven by the freshness registry."""
from datetime import datetime, timezone
from app.config import settings
from app.core.freshness import FreshnessRegistry, init_freshness_registry


def get_data_sources_status():
    now = datetime.now(timezone.utc)
    all_sources = FreshnessRegistry.get_all()

    # If registry is empty (e.g. test context), seed it
    if not all_sources:
        init_freshness_registry(settings)
        all_sources = FreshnessRegistry.get_all()

    # Build rich status per source
    sources = []
    for info in all_sources:
        d = info.to_dict()
        d["url"] = _source_urls.get(info.source_id, "")
        d["variables"] = _source_variables.get(info.source_id, [])
        d["resolution"] = _source_resolutions.get(info.source_id, "")
        d["format"] = _source_formats.get(info.source_id, "")
        d["credential_required"] = _source_creds.get(info.source_id, "")
        sources.append(d)

    connected = sum(1 for s in sources if s["status"] in ("LIVE", "NEAR_REAL_TIME", "LATEST_AVAILABLE"))
    demo = sum(1 for s in sources if s["status"] == "DEMO")
    offline = sum(1 for s in sources if s["status"] == "OFFLINE")

    return {
        "data_mode": settings.effective_data_mode,
        "sources": sources,
        "summary": {
            "total": len(sources),
            "connected": connected,
            "demo": demo,
            "offline": offline,
        },
        "credentials_configured": {
            "copernicus": settings.has_copernicus,
            "earthdata": settings.has_earthdata,
            "cds": settings.has_cds,
            "cmems": settings.has_cmems,
            "ais": settings.has_ais,
        },
        "disclaimer": (
            "Data marked DEMO is synthetically generated (seed=42). "
            "See DATA_SOURCES.md for credential setup to enable real data."
        ),
        "timestamp": now.isoformat(),
    }


_source_urls = {
    "ais": "https://aisstream.io/ (or configured provider)",
    "satellite": "https://dataspace.copernicus.eu/",
    "sea_ice": "https://noaadata.apps.nsidc.org/NOAA/G02135/",
    "icebergs": "https://usicecenter.gov/Products/AntarcIcebergs",
    "weather": "https://api.open-meteo.com/",
    "ocean": "https://marine-api.open-meteo.com/",
    "database": "local PostgreSQL + PostGIS",
}

_source_variables = {
    "ais": ["vessel position", "speed", "course", "heading", "MMSI"],
    "satellite": ["SAR backscatter", "footprint", "acquisition time", "polarization"],
    "sea_ice": ["sea ice extent km²", "sea ice area km²", "coverage %"],
    "icebergs": ["iceberg position", "dimensions", "tracking date"],
    "weather": ["wind speed", "wind direction", "temperature", "pressure", "precipitation"],
    "ocean": ["wave height", "wave period", "ocean current speed/direction"],
    "database": ["all stored observations"],
}

_source_resolutions = {
    "ais": "real-time (seconds)",
    "satellite": "product-level (~200km swath)",
    "sea_ice": "25 km, daily/monthly",
    "icebergs": "named icebergs, weekly",
    "weather": "~11 km, hourly NWP",
    "ocean": "wave model grid",
    "database": "varies",
}

_source_formats = {
    "ais": "WebSocket / REST JSON",
    "satellite": "GeoJSON (STAC metadata)",
    "sea_ice": "CSV",
    "icebergs": "CSV",
    "weather": "JSON (Open-Meteo)",
    "ocean": "JSON (Open-Meteo Marine)",
    "database": "PostgreSQL",
}

_source_creds = {
    "ais": "AIS_PROVIDER + AIS_API_KEY",
    "satellite": "COPERNICUS_CLIENT_ID + COPERNICUS_CLIENT_SECRET",
    "sea_ice": "None (free public)",
    "icebergs": "None (free public)",
    "weather": "None (free)",
    "ocean": "None (free)",
    "database": "DATABASE_URL",
}
