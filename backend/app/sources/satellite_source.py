"""
POLAR-AI Satellite Source — Copernicus Data Space Ecosystem
============================================================
Uses the Copernicus Data Space STAC API to search for and retrieve
Sentinel-1 SAR products over the Antarctic region.

Required credentials:
    COPERNICUS_CLIENT_ID
    COPERNICUS_CLIENT_SECRET
    (Register free at https://dataspace.copernicus.eu/)

Architecture:
    1. Authenticate → get OAuth2 bearer token
    2. Search STAC for latest Sentinel-1 products over Antarctica
    3. Return product metadata (footprint, acquisition time, assets)
    4. Cache products to avoid re-downloading
    5. Generate WMS/tile URL for map display
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import httpx
from loguru import logger

from app.core.base_source import BaseDataSource
from app.core.freshness import FreshnessRegistry, DataStatus
from app.config import settings


# Antarctic bounding box (WGS84): lon_min, lat_min, lon_max, lat_max
ANTARCTICA_BBOX = [-180, -90, 180, -50]


class CopernicusSatelliteSource(BaseDataSource):
    """
    Adapter for Copernicus Data Space Ecosystem (CDSE).
    Searches for Sentinel-1 SAR products over Antarctica.

    Credential check: COPERNICUS_CLIENT_ID + COPERNICUS_CLIENT_SECRET
    """
    source_id = "satellite"
    timeout_s = 45.0
    max_retries = 2

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._product_cache: List[Dict] = []
        self._cache_file = os.path.join(settings.DATA_DIR, "cache", "sentinel1_products.json")
        os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)

    def is_configured(self) -> bool:
        return settings.has_copernicus

    async def _get_token(self) -> Optional[str]:
        """Obtain OAuth2 token from Copernicus identity service."""
        now = datetime.now(timezone.utc)
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token

        try:
            resp = await self._post(
                settings.COPERNICUS_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.COPERNICUS_CLIENT_ID,
                    "client_secret": settings.COPERNICUS_CLIENT_SECRET,
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            token_data = resp.json()
            self._token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 600)
            self._token_expiry = now + timedelta(seconds=expires_in - 30)
            logger.info("[satellite] Copernicus token obtained successfully")
            return self._token
        except Exception as e:
            logger.error(f"[satellite] Token fetch failed: {e}")
            return None

    async def _fetch(self) -> Optional[List[Dict]]:
        """Search STAC for latest Sentinel-1 products over Antarctica."""
        token = await self._get_token()
        if not token:
            raise RuntimeError("Could not obtain Copernicus OAuth2 token")

        headers = {"Authorization": f"Bearer {token}"}

        # Build STAC search request
        # Antarctic coverage: last 7 days, Sentinel-1, GRD products
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)

        stac_search_url = f"{settings.COPERNICUS_STAC_URL}/search"
        payload = {
            "collections": ["SENTINEL-1"],
            "bbox": ANTARCTICA_BBOX,
            "datetime": f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "query": {
                "productType": {"eq": "GRD"},
            },
            "limit": 20,
            "sortby": [{"field": "datetime", "direction": "desc"}],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(stac_search_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            # Try OData fallback
            logger.warning(f"[satellite] STAC search failed ({e.response.status_code}), trying OData")
            return await self._fetch_odata(token)
        except Exception as e:
            raise RuntimeError(f"STAC search error: {e}")

        features = data.get("features", [])
        if not features:
            logger.warning("[satellite] No Sentinel-1 products found over Antarctica in last 7 days")
            return []

        products = [self._parse_stac_item(f) for f in features]
        products = [p for p in products if p is not None]

        # Cache to disk
        self._product_cache = products
        self._save_cache(products)

        FreshnessRegistry.update(
            self.source_id,
            record_count=len(products),
            status=DataStatus.LATEST_AVAILABLE,
        )
        logger.info(f"[satellite] Found {len(products)} Sentinel-1 products")
        return products

    async def _fetch_odata(self, token: str) -> List[Dict]:
        """OData fallback for product search."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)

        # OData filter for Sentinel-1 GRD over Antarctica
        odata_url = settings.COPERNICUS_ODATA_URL + "/Products"
        params = {
            "$filter": (
                f"Collection/Name eq 'SENTINEL-1' "
                f"and ContentDate/Start gt {start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')} "
                f"and ContentDate/Start lt {end_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')} "
                f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
                f"and att/OData.CSC.StringAttribute/Value eq 'GRD')"
            ),
            "$orderby": "ContentDate/Start desc",
            "$top": "10",
            "$expand": "Attributes",
        }

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.get(odata_url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("value", [])
        products = [self._parse_odata_item(item) for item in items]
        products = [p for p in products if p is not None]
        self._save_cache(products)
        return products

    def _parse_stac_item(self, item: Dict) -> Optional[Dict]:
        """Parse a STAC feature into a normalized product dict."""
        try:
            props = item.get("properties", {})
            geometry = item.get("geometry", {})
            assets = item.get("assets", {})

            product = {
                "product_id": item.get("id", ""),
                "collection": item.get("collection", "SENTINEL-1"),
                "acquisition_time": props.get("datetime", ""),
                "publication_time": props.get("created", ""),
                "platform": props.get("platform", "sentinel-1"),
                "instrument": props.get("instruments", ["SAR"])[0] if props.get("instruments") else "SAR",
                "product_type": props.get("productType", "GRD"),
                "polarization": props.get("polarisation", "VV VH"),
                "orbit_direction": props.get("orbitDirection", ""),
                "orbit_number": props.get("relativeOrbitNumber", None),
                "footprint": geometry,
                "thumbnail_url": assets.get("thumbnail", {}).get("href", ""),
                "download_url": assets.get("PRODUCT", {}).get("href", ""),
                "source": "Copernicus Data Space",
                "sensor": "Sentinel-1 SAR",
                "mode": "live",
            }

            # Compute approximate coverage area
            if geometry.get("type") == "Polygon":
                coords = geometry["coordinates"][0]
                lats = [c[1] for c in coords]
                lons = [c[0] for c in coords]
                product["bbox"] = [min(lons), min(lats), max(lons), max(lats)]
            else:
                product["bbox"] = ANTARCTICA_BBOX

            return product
        except Exception as e:
            logger.warning(f"[satellite] Could not parse STAC item: {e}")
            return None

    def _parse_odata_item(self, item: Dict) -> Optional[Dict]:
        """Parse OData product into normalized dict."""
        try:
            attrs = {a["Name"]: a.get("Value") for a in item.get("Attributes", [])}
            return {
                "product_id": item.get("Id", ""),
                "collection": "SENTINEL-1",
                "acquisition_time": item.get("ContentDate", {}).get("Start", ""),
                "publication_time": item.get("PublicationDate", ""),
                "platform": "sentinel-1",
                "instrument": "SAR",
                "product_type": attrs.get("productType", "GRD"),
                "polarization": attrs.get("polarisationChannels", "VV VH"),
                "orbit_direction": attrs.get("orbitDirection", ""),
                "orbit_number": attrs.get("relativeOrbitNumber", None),
                "footprint": None,
                "thumbnail_url": "",
                "download_url": f"{settings.COPERNICUS_ODATA_URL}/Products({item.get('Id', '')}/$value",
                "source": "Copernicus Data Space",
                "sensor": "Sentinel-1 SAR",
                "mode": "live",
                "bbox": ANTARCTICA_BBOX,
            }
        except Exception as e:
            logger.warning(f"[satellite] Could not parse OData item: {e}")
            return None

    def _save_cache(self, products: List[Dict]):
        try:
            with open(self._cache_file, "w") as f:
                json.dump({"cached_at": datetime.now(timezone.utc).isoformat(), "products": products}, f, indent=2)
        except Exception as e:
            logger.warning(f"[satellite] Cache save failed: {e}")

    def load_cache(self) -> Optional[List[Dict]]:
        """Load cached products if available and not too old."""
        try:
            if not os.path.exists(self._cache_file):
                return None
            with open(self._cache_file) as f:
                data = json.load(f)
            cached_at = datetime.fromisoformat(data["cached_at"])
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age < settings.FRESHNESS_SATELLITE_STALE_S:
                return data["products"]
        except Exception:
            pass
        return None

    def get_latest_product(self) -> Optional[Dict]:
        """Return the most recently acquired product from cache."""
        products = self._product_cache or self.load_cache() or []
        if not products:
            return None
        # Sort by acquisition time descending
        try:
            products.sort(key=lambda p: p.get("acquisition_time", ""), reverse=True)
            return products[0]
        except Exception:
            return products[0]

    def get_all_products(self) -> List[Dict]:
        return self._product_cache or self.load_cache() or []


# Singleton
_satellite_source: Optional[CopernicusSatelliteSource] = None


def get_satellite_source() -> CopernicusSatelliteSource:
    global _satellite_source
    if _satellite_source is None:
        _satellite_source = CopernicusSatelliteSource()
    return _satellite_source
