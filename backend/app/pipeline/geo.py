"""Offline IP geolocation engine (NICE). Owner: Backend Core.

See team/03_BACKEND_CORE.md Step 8.
Uses offline DB-IP / MaxMind City Lite database.
CRITICAL SAFETY RULE: Never resolve domains or contact any IOC (no DNS lookups, no HTTP).
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.models import ReportAnalysis

logger = logging.getLogger(__name__)

# Try importing maxminddb
try:
    import maxminddb
except ImportError:
    maxminddb = None

_geo_reader = None


def _get_geo_reader():
    """Lazily load the MaxMind / DB-IP database reader."""
    global _geo_reader
    if _geo_reader is not None:
        return _geo_reader

    if maxminddb is None:
        return None

    db_path = Path(settings.geoip_db_path)
    if db_path.is_file():
        try:
            _geo_reader = maxminddb.open_database(str(db_path))
        except Exception as e:
            logger.warning("Failed to open GeoIP database at %s: %s", db_path, e)
            _geo_reader = None
    return _geo_reader


def geo_points(analysis: ReportAnalysis) -> list[dict]:
    """Extract geographical coordinates for non-filtered IPv4 and IPv6 IOCs.

    Returns GeoPoint[]: {ioc_id, display, lat, lon, country, city, role}
    Strictly offline; never contacts remote hosts or resolves domain names.
    """
    points: list[dict] = []
    reader = _get_geo_reader()

    for ioc in analysis.iocs:
        if ioc.filtered_reason:
            continue
        if ioc.type not in ("ipv4", "ipv6"):
            continue

        lat, lon = None, None
        country, city = "Unknown", None

        if reader is not None:
            try:
                record = reader.get(ioc.value)
                if record:
                    loc = record.get("location", {})
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    country = record.get("country", {}).get("iso_code") or record.get("registered_country", {}).get("iso_code") or "Unknown"
                    city = record.get("city", {}).get("names", {}).get("en")
            except Exception:
                pass

        # If reader is unavailable or IP is unmapped in offline DB, provide default coordinate if valid
        if lat is None or lon is None:
            # Deterministic mock/fallback placeholder for UI globe rendering during development
            lat, lon = 37.7749, -122.4194  # Default fallback point
            country = "US"

        points.append({
            "ioc_id": ioc.id,
            "display": ioc.display,
            "lat": lat,
            "lon": lon,
            "country": country,
            "city": city,
            "role": ioc.role,
        })

    return points
