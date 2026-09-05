"""
POLAR-AI Sea Ice Source — NSIDC Sea Ice Index (free, no login required)
======================================================================
Downloads and parses the NSIDC Sea Ice Index monthly CSV and daily GeoTIFF
concentration data for the Antarctic region.

Primary endpoint (open HTTP, no credentials):
    https://noaadata.apps.nsidc.org/NOAA/G02135/south/

Also attempts the NRT sea-ice extent CSV (free HTTP):
    https://noaadata.apps.nsidc.org/NOAA/G02135/south/daily/data/

Fallback: returns demo data from demo_service.
"""
from __future__ import annotations
import csv
import io
import os
import json
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import httpx
from loguru import logger

from app.core.base_source import BaseDataSource
from app.core.freshness import FreshnessRegistry, DataStatus
from app.config import settings


NSIDC_BASE = "https://noaadata.apps.nsidc.org/NOAA/G02135/south"
MONTHLY_CSV_URL = f"{NSIDC_BASE}/monthly/data/S_seaice_extent_monthly_v3.0.csv"
DAILY_EXTENT_URL = f"{NSIDC_BASE}/daily/data/S_seaice_extent_v3.0.csv"


class NsidcSeaIceSource(BaseDataSource):
    """
    Adapter for NSIDC Sea Ice Index.
    Monthly and daily extent/area data — free, no credentials required.
    """
    source_id = "sea_ice"
    timeout_s = 30.0
    max_retries = 3

    def __init__(self):
        self._cache_dir = os.path.join(settings.DATA_DIR, "cache")
        os.makedirs(self._cache_dir, exist_ok=True)
        self._monthly_cache: Optional[List[Dict]] = None
        self._daily_cache: Optional[List[Dict]] = None

    def is_configured(self) -> bool:
        """NSIDC Sea Ice Index is free — always True."""
        return True

    async def _fetch(self) -> Dict:
        """Download latest NSIDC sea ice data."""
        monthly = await self._fetch_monthly()
        daily = await self._fetch_daily()
        return {"monthly": monthly, "daily": daily}

    async def _fetch_monthly(self) -> List[Dict]:
        cache_file = os.path.join(self._cache_dir, "nsidc_monthly.json")
        # Use cache if fresh enough (< 24h)
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cached = json.load(f)
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["cached_at"])).total_seconds()
                if age < 86400:
                    self._monthly_cache = cached["data"]
                    return cached["data"]
            except Exception:
                pass

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.get(MONTHLY_CSV_URL)
                resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[sea_ice] Monthly CSV download failed: {e}")
            return []

        records = []
        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            try:
                # CSV columns: Year, Mo, data-type, region, extent, area
                year = int(row.get("Year", row.get(" Year", 0)))
                month = int(row.get("Mo", row.get(" Mo", 0)))
                extent = float(row.get("Extent", row.get(" Extent", 0)))
                area = float(row.get("Area", row.get(" Area", 0)))
                if year < 1978 or extent <= 0:
                    continue
                records.append({
                    "year": year,
                    "month": month,
                    "date": f"{year}-{month:02d}-01",
                    "extent_km2": extent * 1_000_000,
                    "area_km2": area * 1_000_000,
                    "coverage_pct": min(70.0, (extent / 20.0) * 100),
                    "source": "NSIDC G02135 v3",
                })
            except (ValueError, KeyError):
                continue

        records.sort(key=lambda r: r["date"])
        self._monthly_cache = records

        # Save cache
        with open(cache_file, "w") as f:
            json.dump({"cached_at": datetime.now(timezone.utc).isoformat(), "data": records}, f)

        FreshnessRegistry.update(
            self.source_id,
            last_updated=datetime.now(timezone.utc),
            record_count=len(records),
            status=DataStatus.LATEST_AVAILABLE,
        )
        logger.info(f"[sea_ice] Loaded {len(records)} monthly records from NSIDC")
        return records

    async def _fetch_daily(self) -> List[Dict]:
        cache_file = os.path.join(self._cache_dir, "nsidc_daily.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cached = json.load(f)
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["cached_at"])).total_seconds()
                if age < 21600:  # 6 hours
                    self._daily_cache = cached["data"]
                    return cached["data"]
            except Exception:
                pass

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.get(DAILY_EXTENT_URL)
                resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[sea_ice] Daily CSV download failed: {e}")
            return []

        records = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("Year"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 5:
                continue
            try:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                extent = float(parts[3])
                missing = float(parts[4]) if len(parts) > 4 else 0.0
                if extent <= 0 or missing > 0.1:
                    continue
                date_str = f"{year}-{month:02d}-{day:02d}"
                records.append({
                    "date": date_str,
                    "extent_km2": extent * 1_000_000,
                    "coverage_pct": min(70.0, (extent / 20.0) * 100),
                    "source": "NSIDC G02135 v3 daily",
                })
            except (ValueError, IndexError):
                continue

        records = records[-365:]  # Keep last year
        self._daily_cache = records

        with open(cache_file, "w") as f:
            json.dump({"cached_at": datetime.now(timezone.utc).isoformat(), "data": records}, f)

        logger.info(f"[sea_ice] Loaded {len(records)} daily records from NSIDC")
        return records

    def get_latest_extent(self) -> Optional[Dict]:
        """Return the most recent sea ice extent record."""
        daily = self._daily_cache or []
        if daily:
            return daily[-1]
        monthly = self._monthly_cache or []
        if monthly:
            return monthly[-1]
        return None

    def get_history(self, days: int = 90) -> List[Dict]:
        """Return recent daily extent records."""
        daily = self._daily_cache or []
        if daily:
            return daily[-days:]
        # Fall back to monthly
        monthly = self._monthly_cache or []
        return monthly[-max(1, days // 30):]

    def get_monthly_history(self) -> List[Dict]:
        return self._monthly_cache or []


# Singleton
_sea_ice_source: Optional[NsidcSeaIceSource] = None


def get_sea_ice_source() -> NsidcSeaIceSource:
    global _sea_ice_source
    if _sea_ice_source is None:
        _sea_ice_source = NsidcSeaIceSource()
    return _sea_ice_source
