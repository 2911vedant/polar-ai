"""
POLAR-AI v2 FastAPI Application
Antarctic Ice Intelligence & Navigation Decision Support
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger
import time

from app.config import settings
from app.database import check_db_connection, check_postgis
from app.core.freshness import init_freshness_registry, FreshnessRegistry, DataStatus

# ── Routers ────────────────────────────────────────────────────────────────────
from app.routers import (
    health, dashboard, sea_ice, icebergs,
    weather, ocean, routes, analytics,
    data_sources, agent, simulation,
    system, satellite, vessel, alerts,
)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info(f"POLAR-AI v{settings.APP_VERSION} Starting Up")
    logger.info(f"Data Mode: {settings.DATA_MODE}  (effective: {settings.effective_data_mode})")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Copernicus: {'✓' if settings.has_copernicus else '✗'}")
    logger.info(f"NSIDC/Earthdata: {'✓' if settings.has_earthdata else '✗'}")
    logger.info(f"CMEMS Ocean: {'✓' if settings.has_cmems else '✗'}")
    logger.info(f"AIS Provider: {settings.AIS_PROVIDER or '✗ (demo mode)'}")
    logger.info("=" * 60)

    # 1. Init freshness registry
    init_freshness_registry(settings)

    # 2. Database check
    db_ok = check_db_connection()
    if db_ok:
        logger.info("✓ Database connected")
        FreshnessRegistry.update("database", status=DataStatus.NEAR_REAL_TIME)
        if check_postgis():
            logger.info("✓ PostGIS available")
    else:
        logger.warning("✗ Database not connected — running in limited mode")
        FreshnessRegistry.update("database", status=DataStatus.OFFLINE)

    # 3. Ensure cache/data dirs exist
    import os
    os.makedirs(os.path.join(settings.DATA_DIR, "cache"), exist_ok=True)
    os.makedirs(settings.DEMO_DATA_DIR, exist_ok=True)
    os.makedirs(settings.MODELS_DIR, exist_ok=True)

    # 4. Bootstrap free real sources (no credentials needed)
    # Weather and Ocean use Open-Meteo — free, always attempt
    # Icebergs use NIC — free public CSV
    import asyncio
    async def _bootstrap():
        try:
            from app.sources.weather_source import get_weather_source
            await get_weather_source().fetch()
        except Exception as e:
            logger.warning(f"Weather bootstrap failed: {e}")
        try:
            from app.sources.ocean_source import get_ocean_source
            await get_ocean_source().fetch()
        except Exception as e:
            logger.warning(f"Ocean bootstrap failed: {e}")
        try:
            from app.sources.iceberg_source import get_iceberg_source
            await get_iceberg_source().fetch()
        except Exception as e:
            logger.warning(f"Iceberg bootstrap failed: {e}")
        try:
            from app.sources.sea_ice_source import get_sea_ice_source
            await get_sea_ice_source().fetch()
        except Exception as e:
            logger.warning(f"Sea ice bootstrap failed: {e}")

    asyncio.create_task(_bootstrap())

    # 5. Start background scheduler
    try:
        from app.ingestion.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler start failed: {e}")

    yield

    # Shutdown
    try:
        from app.ingestion.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
    logger.info("POLAR-AI shutting down")


app = FastAPI(
    title="POLAR-AI v2",
    description="""
## Antarctic Ice Intelligence & Navigation Decision Support System

**SIH26059** — AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory & Navigation Decision Support

### Data Sources
- 🛰️ Sentinel-1 SAR (Copernicus Data Space — requires credentials)
- 🧊 NSIDC Sea Ice Index (free, always available)
- 🏔️ US National Ice Center Icebergs (free, always available)
- 🌬️ Open-Meteo NWP Weather (free, always available)
- 🌊 Open-Meteo Marine Ocean (free, always available)
- 🚢 AIS Vessel Tracking (configurable provider)

### Data Modes
- **LIVE** — real data from external sources
- **NEAR_REAL_TIME** — recent external data within expected update cycle
- **LATEST_AVAILABLE** — external data, possibly delayed
- **DEMO** — synthetic deterministic data (seed=42)

> Research prototype. Not certified for autonomous navigation.
    """,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.time() - start:.3f}s"
    response.headers["X-POLAR-AI-Version"] = settings.APP_VERSION
    response.headers["X-Data-Mode"] = settings.effective_data_mode
    return response


# ── Register all routers ───────────────────────────────────────────────────────
app.include_router(health.router,       prefix="/api",            tags=["Health"])
app.include_router(system.router,       prefix="/api",            tags=["System"])
app.include_router(dashboard.router,    prefix="/api",            tags=["Dashboard"])
app.include_router(sea_ice.router,      prefix="/api/sea-ice",    tags=["Sea Ice"])
app.include_router(icebergs.router,     prefix="/api/icebergs",   tags=["Icebergs"])
app.include_router(weather.router,      prefix="/api/weather",    tags=["Weather"])
app.include_router(ocean.router,        prefix="/api/ocean",      tags=["Ocean"])
app.include_router(routes.router,       prefix="/api",            tags=["Routes"])
app.include_router(analytics.router,    prefix="/api",            tags=["Analytics"])
app.include_router(data_sources.router, prefix="/api",            tags=["Data Sources"])
app.include_router(agent.router,        prefix="/api/agent",      tags=["AI Agent"])
app.include_router(simulation.router,   prefix="/api/simulation", tags=["Simulation"])
app.include_router(satellite.router,    prefix="/api",            tags=["Satellite"])
app.include_router(vessel.router,       prefix="/api",            tags=["Vessel"])
app.include_router(alerts.router,       prefix="/api",            tags=["Alerts"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "POLAR-AI",
        "version": settings.APP_VERSION,
        "sih_problem": "SIH26059",
        "subtitle": "Antarctic Ice Intelligence & Navigation Decision Support",
        "data_mode": settings.effective_data_mode,
        "docs": "/api/docs",
        "system_status": "/api/system/status",
        "disclaimer": "Research prototype. Not for real navigation.",
    }
