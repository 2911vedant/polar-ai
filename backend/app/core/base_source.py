"""
POLAR-AI Base Data Source
=========================
Abstract base class every real-data adapter inherits from.
Handles retries, timeouts, error logging, and freshness updates.
"""
from __future__ import annotations
import asyncio
import httpx
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
from loguru import logger

from app.core.freshness import FreshnessRegistry, DataStatus


class BaseDataSource(ABC):
    """
    Abstract base for all POLAR-AI external data adapters.

    Subclasses must implement:
      - source_id: str (class attribute)
      - is_configured() -> bool
      - _fetch() -> Any
    """
    source_id: str = "unknown"
    max_retries: int = 3
    timeout_s: float = 30.0
    backoff_base: float = 2.0

    def is_configured(self) -> bool:
        """Return True if all required credentials/config are present."""
        return False

    async def fetch(self) -> Optional[Any]:
        """
        Public fetch method with retry + freshness tracking.
        Returns data on success, None on failure.
        """
        FreshnessRegistry.update(self.source_id, last_attempted=datetime.now(timezone.utc))

        if not self.is_configured():
            logger.debug(f"[{self.source_id}] Not configured — skipping fetch")
            FreshnessRegistry.update(self.source_id, status=DataStatus.DEMO)
            return None

        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"[{self.source_id}] Fetching (attempt {attempt}/{self.max_retries})")
                result = await self._fetch()
                FreshnessRegistry.update(
                    self.source_id,
                    last_updated=datetime.now(timezone.utc),
                    status=DataStatus.NEAR_REAL_TIME,
                )
                logger.info(f"[{self.source_id}] Fetch succeeded")
                return result
            except Exception as exc:
                last_exc = exc
                logger.warning(f"[{self.source_id}] Attempt {attempt} failed: {exc}")
                if attempt < self.max_retries:
                    wait = self.backoff_base ** attempt
                    await asyncio.sleep(wait)

        FreshnessRegistry.update(
            self.source_id,
            last_error=str(last_exc),
            status=DataStatus.OFFLINE,
        )
        logger.error(f"[{self.source_id}] All {self.max_retries} attempts failed: {last_exc}")
        return None

    @abstractmethod
    async def _fetch(self) -> Any:
        """Override to implement the actual data fetch."""
        ...

    @staticmethod
    async def _get(url: str, headers: dict = None, params: dict = None,
                   timeout: float = 30.0) -> httpx.Response:
        """Convenience async HTTP GET."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, headers=headers or {}, params=params or {})

    @staticmethod
    async def _post(url: str, data: dict = None, json: dict = None,
                    headers: dict = None, timeout: float = 30.0) -> httpx.Response:
        """Convenience async HTTP POST."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, data=data, json=json, headers=headers or {})
