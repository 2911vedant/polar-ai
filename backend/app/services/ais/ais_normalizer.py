"""
AIS Normalizer — converts any provider format to a unified schema.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class NormalizedVessel:
    """Single, provider-agnostic vessel record."""
    mmsi: str
    imo: str = ""
    name: str = ""
    call_sign: str = ""
    ship_type: int = 0
    ship_type_name: str = ""
    flag: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: float = 0.0          # knots
    course: float = 0.0         # degrees 0-360
    heading: float = 0.0        # degrees 0-360
    navigation_status: str = "underway"
    destination: str = ""
    eta: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    is_real: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["age_seconds"] = round(
            (datetime.now(timezone.utc) - self.timestamp).total_seconds(), 1)
        d["data_mode"] = "live" if self.is_real else "demo"
        d["status_label"] = "LIVE" if self.is_real else "DEMO"
        return d

    def is_valid_position(self) -> bool:
        return (self.latitude is not None and self.longitude is not None
                and -90 <= self.latitude <= 90
                and -180 <= self.longitude <= 180
                and not (self.latitude == 0 and self.longitude == 0))


# IMO ship type mapping (simplified)
SHIP_TYPE_NAMES = {
    0: "Unknown", 20: "WIG", 30: "Fishing", 31: "Towing", 32: "Towing Large",
    33: "Dredging", 34: "Diving", 35: "Military", 36: "Sailing", 37: "Pleasure",
    40: "High-Speed", 50: "Pilot", 51: "SAR", 52: "Tug", 53: "Port Tender",
    54: "Anti-Pollution", 55: "Law Enforcement", 60: "Passenger",
    70: "Cargo", 71: "Cargo (Hazmat A)", 72: "Cargo (Hazmat B)",
    73: "Cargo (Hazmat C)", 74: "Cargo (Hazmat D)",
    80: "Tanker", 81: "Tanker (Hazmat A)", 82: "Tanker (Hazmat B)",
    83: "Tanker (Hazmat C)", 84: "Tanker (Hazmat D)",
    90: "Other",
}


def ship_type_name(code: int) -> str:
    # Round to nearest 10 for category lookup
    for k in [code, (code // 10) * 10]:
        if k in SHIP_TYPE_NAMES:
            return SHIP_TYPE_NAMES[k]
    return f"Type {code}"


def navigation_status_name(code: int) -> str:
    statuses = {
        0: "underway", 1: "at anchor", 2: "not under command",
        3: "restricted maneuverability", 4: "constrained by draught",
        5: "moored", 6: "aground", 7: "fishing", 8: "underway sailing",
        15: "not defined",
    }
    return statuses.get(code, f"status_{code}")


def from_aisstream(msg: dict) -> Optional[NormalizedVessel]:
    """Parse an AISStream.io message into NormalizedVessel."""
    try:
        meta = msg.get("MetaData", {})
        pos = msg.get("Message", {}).get("PositionReport", {})
        class_a = msg.get("Message", {}).get("StandardClassBPositionReport", pos)
        # Prefer ClassA PositionReport, fall back to ClassB
        pos = pos if pos else class_a

        mmsi = str(meta.get("MMSI", "")).strip()
        if not mmsi:
            return None

        lat = float(pos.get("Latitude", 0) or 0)
        lon = float(pos.get("Longitude", 0) or 0)

        vessel = NormalizedVessel(
            mmsi=mmsi,
            name=meta.get("ShipName", "").strip(),
            latitude=lat if lat != 0 else None,
            longitude=lon if lon != 0 else None,
            speed=float(pos.get("Sog", 0) or 0) / 10,
            course=float(pos.get("Cog", 0) or 0) / 10,
            heading=float(pos.get("TrueHeading", 0) or 0),
            navigation_status=navigation_status_name(
                int(pos.get("NavigationalStatus", 0) or 0)),
            timestamp=datetime.now(timezone.utc),
            source="AISStream.io",
            is_real=True,
        )

        # Ship static data if available
        static = msg.get("Message", {}).get("ShipStaticData", {})
        if static:
            vessel.imo = str(static.get("ImoNumber", "") or "")
            vessel.call_sign = str(static.get("CallSign", "") or "").strip()
            stype = int(static.get("Type", 0) or 0)
            vessel.ship_type = stype
            vessel.ship_type_name = ship_type_name(stype)
            vessel.destination = str(static.get("Destination", "") or "").strip()
            vessel.eta = str(static.get("Eta", "") or "")
            vessel.flag = str(static.get("Flag", "") or "")

        return vessel
    except Exception:
        return None
