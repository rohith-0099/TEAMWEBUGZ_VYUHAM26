"""STIX 2.1 export. STUB — owner: Backend Core. See team/03_BACKEND_CORE.md Step 6."""
from uuid import uuid4

from app.models import ReportAnalysis


def build_stix_bundle(analysis: ReportAnalysis) -> dict:
    """STUB — owner: Backend Core. See team/03_BACKEND_CORE.md.

    Bundle-shaped placeholder; use the stix2 library for the real one.
    """
    indicators = [{"type": "indicator", "id": f"indicator--{uuid4()}", "name": i.display}
                  for i in analysis.iocs if not i.filtered_reason]
    return {"type": "bundle", "id": f"bundle--{uuid4()}", "objects": indicators}
