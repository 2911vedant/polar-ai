"""
POLAR-AI v2 Application Configuration
Default: DATA_MODE=live (auto-detects real sources, shows OFFLINE if unavailable)
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str    = "POLAR-AI"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str     = "development"
    DEBUG: bool      = True
    SECRET_KEY: str  = "polar-ai-dev-secret-key"

    # Database
    DATABASE_URL: str = "postgresql://polarai:polarai_password@localhost:5432/polarai_db"

    # ── Data Mode ────────────────────────────────────────────────────────────
    # live  → use real data; show OFFLINE when unavailable (DEFAULT)
    # auto  → same as live
    # demo  → use deterministic seed=42 synthetic data (explicit testing only)
    DATA_MODE: str = "live"

    DEMO_RANDOM_SEED: int               = 42
    SIMULATION_SPEED_MULTIPLIER: float  = 1.0

    # ── Hourly update interval ────────────────────────────────────────────────
    UPDATE_INTERVAL_MINUTES: int = 60
    SCHEDULER_ENABLED: bool      = True

    # ── LLM (all optional) ───────────────────────────────────────────────────
    OPENAI_API_KEY: str  = ""
    GEMINI_API_KEY: str  = ""
    GROQ_API_KEY: str    = ""

    # ── Copernicus Data Space (Sentinel-1 SAR) ───────────────────────────────
    # Register free at https://dataspace.copernicus.eu/
    COPERNICUS_CLIENT_ID: str     = ""
    COPERNICUS_CLIENT_SECRET: str = ""
    COPERNICUS_TOKEN_URL: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
        "/protocol/openid-connect/token"
    )
    COPERNICUS_STAC_URL:  str = "https://catalogue.dataspace.copernicus.eu/stac"
    COPERNICUS_ODATA_URL: str = "https://catalogue.dataspace.copernicus.eu/odata/v1"

    # ── NASA Earthdata (NSIDC sea-ice CDR gridded) ───────────────────────────
    # Register free at https://urs.earthdata.nasa.gov/
    EARTHDATA_USERNAME: str = ""
    EARTHDATA_PASSWORD: str = ""

    # ── Copernicus CDS (ERA5 weather) ────────────────────────────────────────
    # Register free at https://cds.climate.copernicus.eu/
    CDS_API_KEY: str  = ""
    CDS_API_URL: str  = "https://cds.climate.copernicus.eu/api/v2"

    # ── Copernicus Marine (CMEMS ocean currents/SST) ─────────────────────────
    # Register free at https://marine.copernicus.eu/
    COPERNICUS_MARINE_USERNAME: str = ""
    COPERNICUS_MARINE_PASSWORD: str = ""
    # Legacy aliases
    CMEMS_USERNAME: str = ""
    CMEMS_PASSWORD: str = ""

    # ── AIS Vessel Tracking ──────────────────────────────────────────────────
    # Providers: aisstream | barentswatch | custom
    # AISStream free: https://aisstream.io/
    # BarentsWatch free: https://www.barentswatch.no/bwapi/
    AIS_PROVIDER:    str = ""
    AIS_API_KEY:     str = ""
    AIS_API_URL:     str = ""
    AIS_WS_URL:      str = ""
    AIS_VESSEL_MMSI: str = ""   # optional: filter to specific vessel

    # ── Weather fallback (if Open-Meteo is insufficient) ─────────────────────
    WEATHER_API_KEY: str = ""
    WEATHER_API_URL: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:5373"
    )

    # ── Server ───────────────────────────────────────────────────────────────
    BACKEND_PORT: int  = 8000
    BACKEND_HOST: str  = "0.0.0.0"

    # ── Cache directory ───────────────────────────────────────────────────────
    CACHE_DIR: str = ""

    # ── Freshness thresholds (seconds) ───────────────────────────────────────
    FRESHNESS_VESSEL_STALE_S:    int = 120      # 2 min
    FRESHNESS_OCEAN_STALE_S:     int = 3600     # 1 hr
    FRESHNESS_WEATHER_STALE_S:   int = 3600     # 1 hr
    FRESHNESS_SEA_ICE_STALE_S:   int = 172800   # 48 hr
    FRESHNESS_SATELLITE_STALE_S: int = 86400    # 24 hr
    FRESHNESS_ICEBERGS_STALE_S:  int = 604800   # 7 days

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def has_llm(self) -> bool:
        return bool(self.OPENAI_API_KEY or self.GEMINI_API_KEY or self.GROQ_API_KEY)

    @property
    def llm_provider(self) -> str:
        if self.OPENAI_API_KEY:  return "openai"
        if self.GEMINI_API_KEY:  return "gemini"
        if self.GROQ_API_KEY:    return "groq"
        return "none"

    @property
    def has_copernicus(self) -> bool:
        return bool(self.COPERNICUS_CLIENT_ID and self.COPERNICUS_CLIENT_SECRET)

    @property
    def has_earthdata(self) -> bool:
        return bool(self.EARTHDATA_USERNAME and self.EARTHDATA_PASSWORD)

    @property
    def has_cds(self) -> bool:
        return bool(self.CDS_API_KEY)

    @property
    def has_cmems(self) -> bool:
        u = self.COPERNICUS_MARINE_USERNAME or self.CMEMS_USERNAME
        p = self.COPERNICUS_MARINE_PASSWORD or self.CMEMS_PASSWORD
        return bool(u and p)

    @property
    def has_ais(self) -> bool:
        return bool(self.AIS_PROVIDER and self.AIS_API_KEY)

    @property
    def effective_data_mode(self) -> str:
        """
        Returns 'live' or 'demo'.
        'live' means: use real data, show OFFLINE when unavailable.
        'demo' means: use deterministic synthetic data (explicit).
        """
        if self.DATA_MODE.lower() == "demo":
            return "demo"
        # 'live' and 'auto' both resolve to live
        return "live"

    # Paths
    BASE_DIR: str  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str  = os.path.join(BASE_DIR, "data")
    MODELS_DIR: str = os.path.join(BASE_DIR, "models")
    DEMO_DATA_DIR: str = os.path.join(BASE_DIR, "data", "demo")

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
