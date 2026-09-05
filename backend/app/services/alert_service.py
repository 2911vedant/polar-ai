"""
POLAR-AI Alert Service
======================
Generates real-time navigation alerts based on changing conditions.
Alerts are stored in-memory and exposed via SSE (/api/alerts/stream)
and regular GET (/api/alerts).

Alert types:
  ICEBERG_PROXIMITY   — iceberg approaching route
  SEA_ICE_INCREASE    — SIC along route increased significantly
  WEATHER_DETERIORATION — wind speed exceeded threshold
  ROUTE_UNSAFE        — current route crosses high-risk zone
  ROUTE_REPLANNED     — automatic route recalculation triggered
  AIS_OFFLINE         — vessel tracking connection lost
  SOURCE_STALE        — data source became stale
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from enum import Enum
import uuid

from loguru import logger


class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    DANGER = "DANGER"
    CRITICAL = "CRITICAL"


class Alert:
    def __init__(self, alert_type: str, level: AlertLevel, title: str, message: str,
                 data: Optional[Dict] = None):
        self.id = str(uuid.uuid4())[:8]
        self.alert_type = alert_type
        self.level = level
        self.title = title
        self.message = message
        self.data = data or {}
        self.created_at = datetime.now(timezone.utc)
        self.acknowledged = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "age_seconds": round((datetime.now(timezone.utc) - self.created_at).total_seconds(), 1),
            "acknowledged": self.acknowledged,
        }


class AlertService:
    """In-memory alert store with SSE broadcast support."""
    _alerts: List[Alert] = []
    _max_alerts = 50
    _subscribers: List[asyncio.Queue] = []

    @classmethod
    def add_alert(cls, alert: Alert):
        """Add alert and broadcast to all SSE subscribers."""
        cls._alerts.insert(0, alert)
        if len(cls._alerts) > cls._max_alerts:
            cls._alerts = cls._alerts[:cls._max_alerts]
        logger.info(f"[alert] {alert.level.value}: {alert.title}")
        # Broadcast to SSE subscribers
        for q in cls._subscribers:
            try:
                q.put_nowait(alert.to_dict())
            except asyncio.QueueFull:
                pass

    @classmethod
    def subscribe(cls) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=20)
        cls._subscribers.append(q)
        return q

    @classmethod
    def unsubscribe(cls, q: asyncio.Queue):
        if q in cls._subscribers:
            cls._subscribers.remove(q)

    @classmethod
    def get_alerts(cls, limit: int = 20, unacknowledged_only: bool = False) -> List[Dict]:
        alerts = cls._alerts
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return [a.to_dict() for a in alerts[:limit]]

    @classmethod
    def acknowledge(cls, alert_id: str) -> bool:
        for alert in cls._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    @classmethod
    def get_unread_count(cls) -> int:
        return sum(1 for a in cls._alerts if not a.acknowledged)


async def check_route_safety():
    """
    Periodically called by scheduler to check if current route is safe.
    Generates alerts if conditions have changed significantly.
    """
    try:
        from app.services.risk_service import calculate_risk
        from app.schemas.routes import RiskCalculateRequest
        from app.sources.vessel_source import get_vessel_service

        vessel_svc = get_vessel_service()
        pos = vessel_svc.get_position()
        lat = pos["latitude"]
        lon = pos["longitude"]

        req = RiskCalculateRequest(latitude=lat, longitude=lon, radius_km=100.0)
        risk = calculate_risk(req)

        if risk["total_risk_score"] > 0.75:
            AlertService.add_alert(Alert(
                alert_type="HIGH_RISK",
                level=AlertLevel.DANGER,
                title="High Navigation Risk",
                message=(f"Navigation risk at vessel position is CRITICAL "
                         f"({risk['total_risk_score']*100:.0f}/100). "
                         f"Primary hazard: {risk['risk_factors'][0]['text'] if risk['risk_factors'] else 'multiple factors'}"),
                data={"risk_score": risk["total_risk_score"], "risk_category": risk["risk_category"],
                      "lat": lat, "lon": lon},
            ))
        elif risk["iceberg_risk"] > 0.6:
            AlertService.add_alert(Alert(
                alert_type="ICEBERG_PROXIMITY",
                level=AlertLevel.WARNING,
                title="Iceberg Proximity Alert",
                message=f"Elevated iceberg risk ({risk['iceberg_risk']*100:.0f}/100) near vessel position.",
                data={"iceberg_risk": risk["iceberg_risk"], "lat": lat, "lon": lon},
            ))
    except Exception as e:
        logger.debug(f"[alert] Route safety check failed: {e}")
