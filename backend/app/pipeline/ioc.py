"""IOC engine. STUB — owner: Backend Core. See team/03_BACKEND_CORE.md Step 4."""
from app.mocks import sample_analysis
from app.models import IOC


def extract_iocs(text: str, publisher_domain: str | None = None) -> list[IOC]:
    """STUB — owner: Backend Core. See team/03_BACKEND_CORE.md."""
    return sample_analysis().iocs
