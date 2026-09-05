"""
POLAR-AI Application Configuration
Loaded from environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "POLAR-AI"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "polar-ai-dev-secret-key"

    # Database
    DATABASE_URL: str = "postgresql://polarai:polarai_password@localhost:5432/polarai_db"

    # Data mode: auto | live | demo
    # auto  → use real data when credentials exist, else fallback to demo
    # live  → real data only, never silently fallback
    # demo  → deterministic seed=42 synthetic data
    DATA_MODE: str = "auto"
    DEMO_RANDOM_SEED: int = 42
    SIMULATION_SPEED_MULTIPLIER: float = 1.0

    # ── LLM API keys (all optional) ────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # ── Copernicus Data Space (Sentinel-1 satellite imagery) ───────────────────
    COPERNICUS_CLIENT_ID: str = ""
    COPERNICUS_CLIENT_SECRET: str = ""
    COPERNICUS_TOKEN_URL: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    COPERNICUS_STAC_URL: str = "https://catalogue.dataspace.copernicus.eu/stac"
    COPERNICUS_ODATA_URL: str = "https://catalogue.dataspace.copernicus.eu/odata/v1"

    # ── NASA Earthdata (NSIDC sea-ice CDR) ─────────────────────────────────────
    EARTHDATA_USERNAME: str = ""
    EARTHDATA_PASSWORD: str = ""

    # ── Copernicus CDS (ERA5 weather reanalysis) ───────────────────────────────
    CDS_API_KEY: str = ""
    CDS_API_URL: str = "https://cds.climate.copernicus.eu/api/v2"

    # ── Copernicus Marine Service (ocean currents/SST) ─────────────────────────
    CMEMS_USERNAME: str = ""
    CMEMS_PASSWORD: str = ""

    # ── AIS vessel tracking ────────────────────────────────────────────────────
    AIS_PROVIDER: str = ""          # e.g. "aisstream" | "marinetraffic" | "barentswatch"
    AIS_API_KEY: str = ""
    AIS_API_URL: str = ""
    AIS_WS_URL: str = ""            # WebSocket endpoint if provider supports it
    AIS_VESSEL_MMSI: str = ""       # MMSI of tracked research vessel (optional filter)

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:5373"

    # ── Server ─────────────────────────────────────────────────────────────────
    BACKEND_PORT: int = 8000
    BACKEND_HOST: str = "0.0.0.0"

    # ── Cache paths ────────────────────────────────────────────────────────────
    CACHE_DIR: str = ""             # if empty, uses BASE_DIR/cache

    # ── Scheduler ──────────────────────────────────────────────────────────────
    SCHEDULER_ENABLED: bool = True

    # ── Data freshness thresholds (seconds) ────────────────────────────────────
    FRESHNESS_VESSEL_STALE_S: int = 120       # vessel is stale after 2 min
    FRESHNESS_OCEAN_STALE_S: int = 3600       # ocean stale after 1 hour
    FRESHNESS_WEATHER_STALE_S: int = 3600     # weather stale after 1 hour
    FRESHNESS_SEA_ICE_STALE_S: int = 172800   # sea ice stale after 48 hours
    FRESHNESS_SATELLITE_STALE_S: int = 86400  # satellite stale after 24 hours
    FRESHNESS_ICEBERGS_STALE_S: int = 604800  # icebergs stale after 7 days

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def has_llm(self) -> bool:
        return bool(self.OPENAI_API_KEY or self.GEMINI_API_KEY or self.GROQ_API_KEY)

    @property
    def llm_provider(self) -> str:
        if self.OPENAI_API_KEY:
            return "openai"
        if self.GEMINI_API_KEY:
            return "gemini"
        if self.GROQ_API_KEY:
            return "groq"
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
        return bool(self.CMEMS_USERNAME and self.CMEMS_PASSWORD)

    @property
    def has_ais(self) -> bool:
        return bool(self.AIS_PROVIDER and self.AIS_API_KEY)

    @property
    def effective_data_mode(self) -> str:
        """Returns 'live', 'demo'. auto → picks based on available credentials."""
        if self.DATA_MODE == "demo":
            return "demo"
        if self.DATA_MODE == "live":
            return "live"
        # auto: use live if at least one real source configured
        if self.has_copernicus or self.has_earthdata or self.has_cmems or self.has_ais:
            return "live"
        return "demo"

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    MODELS_DIR: str = os.path.join(BASE_DIR, "models")
    DEMO_DATA_DIR: str = os.path.join(BASE_DIR, "data", "demo")

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
