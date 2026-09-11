"""
POLAR-AI v2 — Live Data Engine
================================
Starts with DATA_MODE=live by default.
Free sources (weather, ocean, icebergs, sea ice) connect on startup.
Credentialed sources (satellite, AIS) connect when credentials are present.
All sources update every UPDATE_INTERVAL_MINUTES (default 60).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger
import time
import asyncio

from app.config import settings
from app.database import check_db_connection, check_postgis
from app.core.freshness import init_freshness_registry, FreshnessRegistry, DataStatus

# ── Routers ────────────────────────────────────────────────────────────────────
from app.routers import (
    health, dashboard, sea_ice, icebergs,
    weather, ocean, routes, analytics,
    data_sources, agent, simulation,
    system, satellite, vessel, alerts, live,
)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info(f"POLAR-AI v{settings.APP_VERSION} — LIVE DATA ENGINE")
    logger.info(f"Data Mode: {settings.DATA_MODE}  (effective: {settings.effective_data_mode})")
    logger.info(f"Update interval: every {settings.UPDATE_INTERVAL_MINUTES} minutes")
    logger.info(f"LLM: {settings.llm_provider}")
    logger.info("-" * 60)
    logger.info(f"  Sentinel-1 SAR:  {'✓ configured' if settings.has_copernicus else '✗ not configured (need COPERNICUS_CLIENT_ID/SECRET)'}")
    logger.info(f"  NSIDC Sea Ice:   ✓ free / no credentials")
    logger.info(f"  NIC Icebergs:    ✓ free / no credentials")
    logger.info(f"  Open-Meteo Wx:   ✓ free / no credentials")
    logger.info(f"  Open-Meteo Ocean:✓ free / no credentials")
    logger.info(f"  AIS Vessel:      {'✓ ' + settings.AIS_PROVIDER if settings.has_ais else '✗ not configured (need AIS_PROVIDER + AIS_API_KEY)'}")
    logger.info("=" * 60)

    # 1. Init freshness registry with correct real/demo classification
    init_freshness_registry(settings)

    # 2. Database
    db_ok = check_db_connection()
    if db_ok:
        logger.info("✓ Database connected")
        FreshnessRegistry.update("database", status=DataStatus.NEAR_REAL_TIME)
        if check_postgis():
            logger.info("✓ PostGIS available")
    else:
        logger.warning("✗ Database unavailable — some features limited")
        FreshnessRegistry.update("database", status=DataStatus.OFFLINE)

    # 3. Ensure directories exist
    import os
    for d in [settings.DATA_DIR, settings.DEMO_DATA_DIR, settings.MODELS_DIR,
              os.path.join(settings.DATA_DIR, "cache")]:
        os.makedirs(d, exist_ok=True)

    # 4. Wire WebSocket broadcast into hourly update service
    from app.routers.live import manager as live_manager
    from app.services.hourly_update_service import set_broadcast_fn
    set_broadcast_fn(live_manager.broadcast)

    # 5. Start AISStream WebSocket immediately if configured
    if settings.has_ais and settings.AIS_PROVIDER.lower() == "aisstream":
        async def _start_aisstream():
            await asyncio.sleep(3)
            from app.sources.vessel_source import get_vessel_service
            from app.services.hourly_update_service import _ensure_aisstream_running
            _ensure_aisstream_running(get_vessel_service())
            logger.info("✓ AISStream WebSocket listener started")
        asyncio.create_task(_start_aisstream())

    # 6. Run initial data synchronization immediately at startup
    async def _initial_sync():
        await asyncio.sleep(2)  # give the server 2s to fully start
        logger.info("[startup] Running initial data synchronization...")
        try:
            from app.services.hourly_update_service import run_hourly_update
            await run_hourly_update(triggered_by="startup")
        except Exception as e:
            logger.error(f"[startup] Initial sync failed: {e}")

    asyncio.create_task(_initial_sync())

    # 6. Start APScheduler for recurring updates
    try:
        from app.ingestion.scheduler import start_scheduler
        start_scheduler()
        logger.info(f"✓ Scheduler started — updates every {settings.UPDATE_INTERVAL_MINUTES} min")
    except Exception as e:
        logger.warning(f"Scheduler start failed: {e}")

    logger.info("✓ POLAR-AI ready — http://localhost:8000/api/docs")

    yield

    # Shutdown
    try:
        from app.ingestion.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
    logger.info("POLAR-AI shutting down")


app = FastAPI(
    title="POLAR-AI",
    description="""
## Antarctic Ice Intelligence & Navigation Decision Support

**SIH26059** | Live data from NSIDC, NIC, Open-Meteo, Copernicus, AIS

### Data Modes
- **LIVE** (default) — real data; OFFLINE when source unavailable
- **DEMO** — explicit synthetic mode for testing (DATA_MODE=demo)

> Research prototype. Not for real vessel navigation.
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


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(health.router,       prefix="/api",            tags=["Health"])
app.include_router(live.router,         prefix="/api",            tags=["Live Data Engine"])
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
        "data_mode": settings.effective_data_mode,
        "update_interval_minutes": settings.UPDATE_INTERVAL_MINUTES,
        "docs": "/api/docs",
        "live_status": "/api/live/status",
        "ws_live": "/ws/live",
        "disclaimer": "Research prototype. Not for real navigation.",
    }
