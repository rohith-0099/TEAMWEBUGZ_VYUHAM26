"""Offline IP geolocation (NICE). STUB — owner: Backend Core. See team/03_BACKEND_CORE.md Step 8."""
from app.models import ReportAnalysis


def geo_points(analysis: ReportAnalysis) -> list[dict]:
    """STUB — owner: Backend Core. See team/03_BACKEND_CORE.md.

    GeoPoint[]: mock coordinates for every non-filtered IPv4 IOC.
    """
    return [{"ioc_id": i.id, "display": i.display, "lat": 52.37, "lon": 4.89,
             "country": "NL", "city": "Amsterdam", "role": i.role}
            for i in analysis.iocs if i.type == "ipv4" and not i.filtered_reason]
