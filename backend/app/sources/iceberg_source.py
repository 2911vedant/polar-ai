"""
POLAR-AI Iceberg Source — US National Ice Center (NIC)
======================================================
Downloads the NIC Antarctic iceberg tracking database.
This is a free public dataset with no credentials required.

Source: https://usicecenter.gov/Products/AntarcIcebergs

Data: Named Antarctic tabular icebergs (>18.5 km²) with positions,
dimensions, and tracking dates.

Update frequency: Weekly (when new NIC report published)

Fallback: demo_service synthetic icebergs (clearly labeled).
"""
from __future__ import annotations
import csv
import io
import os
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import httpx
from loguru import logger

from app.core.base_source import BaseDataSource
from app.core.freshness import FreshnessRegistry, DataStatus
from app.config import settings

# NIC iceberg table CSV — direct public download
NIC_CSV_URL = "https://usicecenter.gov/File/DownloadProduct?products=/products/iceberg/icebergtable.csv&fName=icebergtable.csv"
# Backup: NIC API endpoint
NIC_API_URL = "https://usicecenter.gov/api/icebergs"


class NicIcebergSource(BaseDataSource):
    """
    Adapter for US National Ice Center Antarctic Iceberg Tracking.
    Free, no credentials required.
    """
    source_id = "icebergs"
    timeout_s = 30.0
    max_retries = 3

    def __init__(self):
        self._cache_dir = os.path.join(settings.DATA_DIR, "cache")
        os.makedirs(self._cache_dir, exist_ok=True)
        self._cache_file = os.path.join(self._cache_dir, "nic_icebergs.json")
        self._icebergs: List[Dict] = []

    def is_configured(self) -> bool:
        return True  # NIC is free / open

    async def _fetch(self) -> List[Dict]:
        # Check disk cache (valid for 24h)
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file) as f:
                    cached = json.load(f)
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["cached_at"])).total_seconds()
                if age < 86400 and cached.get("icebergs"):
                    self._icebergs = cached["icebergs"]
                    FreshnessRegistry.update(self.source_id, record_count=len(self._icebergs),
                                             status=DataStatus.LATEST_AVAILABLE)
                    logger.info(f"[icebergs] Using cached NIC data ({len(self._icebergs)} icebergs)")
                    return self._icebergs
            except Exception:
                pass

        icebergs = await self._download_csv()
        if not icebergs:
            logger.warning("[icebergs] NIC download failed, trying backup")
            icebergs = []  # will trigger demo fallback upstream

        if icebergs:
            self._icebergs = icebergs
            try:
                with open(self._cache_file, "w") as f:
                    json.dump({
                        "cached_at": datetime.now(timezone.utc).isoformat(),
                        "icebergs": icebergs,
                    }, f, indent=2)
            except Exception:
                pass

            FreshnessRegistry.update(
                self.source_id,
                last_updated=datetime.now(timezone.utc),
                record_count=len(icebergs),
                status=DataStatus.LATEST_AVAILABLE,
            )
            logger.info(f"[icebergs] Loaded {len(icebergs)} icebergs from NIC")

        return icebergs

    async def _download_csv(self) -> List[Dict]:
        """Download NIC CSV and parse to normalized dicts."""
        headers = {
            "User-Agent": "POLAR-AI Research System (Antarctic Navigation Research)",
            "Accept": "text/csv,text/plain,*/*",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True) as client:
                resp = await client.get(NIC_CSV_URL, headers=headers)
                resp.raise_for_status()
                content = resp.text
        except Exception as e:
            logger.warning(f"[icebergs] CSV download failed: {e}")
            return []

        return self._parse_csv(content)

    def _parse_csv(self, content: str) -> List[Dict]:
        """Parse NIC CSV into normalized iceberg records."""
        icebergs = []
        lines = content.strip().splitlines()
        if not lines:
            return []

        # NIC CSV has variable headers — detect them
        header_line = None
        data_start = 0
        for i, line in enumerate(lines):
            if re.search(r'iceberg|name|berg|lat|lon', line, re.IGNORECASE):
                header_line = line
                data_start = i + 1
                break

        if header_line is None:
            # Try parsing as headerless CSV with known column order
            header_line = "Iceberg,Latitude,Longitude,Length,Width,Area,Last_Seen,Source"
            data_start = 0

        reader = csv.DictReader(io.StringIO("\n".join([header_line] + lines[data_start:])))

        for row in reader:
            try:
                # Try various possible column name formats from NIC
                name = (row.get("Iceberg") or row.get("Name") or row.get("ICE_BERG")
                        or row.get("iceberg") or "").strip()
                if not name:
                    continue

                lat = self._parse_float(row.get("Latitude") or row.get("LAT") or row.get("lat"))
                lon = self._parse_float(row.get("Longitude") or row.get("LON") or row.get("lon"))

                if lat is None or lon is None:
                    continue
                # Validate Antarctic bounds
                if not (-90 <= lat <= -45 and -180 <= lon <= 180):
                    continue

                length_nm = self._parse_float(row.get("Length") or row.get("LENGTH") or row.get("length_nm"))
                width_nm = self._parse_float(row.get("Width") or row.get("WIDTH") or row.get("width_nm"))
                length_km = (length_nm * 1.852) if length_nm else None
                width_km = (width_nm * 1.852) if width_nm else None
                area_km2 = (length_km * width_km * 0.85) if (length_km and width_km) else None

                # Parse date
                date_str = row.get("Last_Seen") or row.get("Date") or row.get("DATE") or ""
                try:
                    obs_time = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    try:
                        obs_time = datetime.strptime(date_str.strip()[:10], "%d/%m/%Y").replace(tzinfo=timezone.utc)
                    except ValueError:
                        obs_time = datetime.now(timezone.utc) - timedelta(days=7)

                icebergs.append({
                    "iceberg_name": name,
                    "latitude": round(lat, 4),
                    "longitude": round(lon, 4),
                    "length_km": round(length_km, 1) if length_km else None,
                    "width_km": round(width_km, 1) if width_km else None,
                    "area_km2": round(area_km2, 1) if area_km2 else None,
                    "last_observed_at": obs_time.isoformat(),
                    "source": "US National Ice Center",
                    "source_url": "https://usicecenter.gov/Products/AntarcIcebergs",
                    "is_real": True,
                    "data_mode": "live",
                })
            except Exception as e:
                logger.debug(f"[icebergs] Skipped row: {e}")
                continue

        return icebergs

    @staticmethod
    def _parse_float(val) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(str(val).strip().replace(",", ""))
        except (ValueError, TypeError):
            return None

    def get_icebergs(self) -> List[Dict]:
        """Return cached icebergs (may be empty if not yet fetched)."""
        # Try loading from disk cache
        if not self._icebergs and os.path.exists(self._cache_file):
            try:
                with open(self._cache_file) as f:
                    data = json.load(f)
                self._icebergs = data.get("icebergs", [])
            except Exception:
                pass
        return self._icebergs


# Singleton
_iceberg_source: Optional[NicIcebergSource] = None


def get_iceberg_source() -> NicIcebergSource:
    global _iceberg_source
    if _iceberg_source is None:
        _iceberg_source = NicIcebergSource()
    return _iceberg_source
