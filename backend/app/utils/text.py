"""Text helpers. STUB — owner: Backend Core. See team/03_BACKEND_CORE.md Step 2."""


def normalize_text(raw: str) -> str:
    """STUB — owner: Backend Core. See team/03_BACKEND_CORE.md.

    One canonical text. ALL evidence offsets in the system point into this string.
    """
    return raw.strip()


def defang(value: str, ioc_type: str) -> str:
    """STUB — owner: Backend Core. See team/03_BACKEND_CORE.md.

    Safe display version. Never used for logic, only for UI/exports labels.
    """
    if ioc_type in ("ipv4", "domain", "url", "email"):
        return value.replace("http", "hxxp").replace(".", "[.]").replace("@", "[@]")
    return value
