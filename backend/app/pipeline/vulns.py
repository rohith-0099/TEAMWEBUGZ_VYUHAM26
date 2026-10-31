"""CVE enrichment from NVD (CVE API 2.0) and the CISA KEV catalog. Owner: Lead.

Facts only, never guessed: every field comes from the source's own record, keeps its
retrieval time, and a failed lookup is reported as unavailable with empty fields.
Results are cached in ext_cache so repeat analyses and offline demos don't refetch.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from psycopg.types.json import Jsonb

from app import db
from app.config import settings
from app.models import IOC, VulnInfo, VulnReference

log = logging.getLogger(__name__)

KEV_FEED_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
KEV_MAX_AGE = timedelta(days=1)
NVD_MAX_AGE = timedelta(days=1)
TIMEOUT_S = 20
# NVD allows fewer requests per 30 s without a key, so space them out.
NVD_GAP_S = 0.7 if settings.nvd_api_key else 6.5
MAX_DESCRIPTION_CHARS = 500
MAX_AFFECTED = 8
MAX_REFERENCES = 6
REFERENCE_TAGS = {"Patch", "Vendor Advisory"}
CVSS_KEYS = (("cvssMetricV31", "3.1"), ("cvssMetricV40", "4.0"), ("cvssMetricV30", "3.0"))


def _cache_get(key: str) -> tuple[dict, datetime] | None:
    with db.pool.connection() as conn:
        row = conn.execute("SELECT payload, fetched_at FROM ext_cache WHERE key=%s", (key,)).fetchone()
    return (row["payload"], row["fetched_at"]) if row else None


def _cache_put(key: str, payload: dict) -> datetime:
    with db.pool.connection() as conn:
        row = conn.execute(
            """INSERT INTO ext_cache (key, payload, fetched_at) VALUES (%s, %s, now())
               ON CONFLICT (key) DO UPDATE SET payload = EXCLUDED.payload, fetched_at = now()
               RETURNING fetched_at""",
            (key, Jsonb(payload)),
        ).fetchone()
    return row["fetched_at"]


async def _cached_fetch(key: str, max_age: timedelta, fetch) -> tuple[dict, datetime] | None:
    """Fresh cache, else fetch, else stale cache (its own date is shown), else None."""
    cached = await asyncio.to_thread(_cache_get, key)
    if cached and datetime.now(timezone.utc) - cached[1] < max_age:
        return cached
    try:
        payload = await fetch()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("lookup %s failed: %s", key, exc)
        return cached
    if payload is None:
        return None
    return payload, await asyncio.to_thread(_cache_put, key, payload)


async def _kev_catalog(client: httpx.AsyncClient) -> tuple[dict, datetime] | None:
    async def fetch():
        response = await client.get(KEV_FEED_URL)
        response.raise_for_status()
        feed = response.json()
        return {"catalogVersion": feed.get("catalogVersion"), "dateReleased": feed.get("dateReleased"),
                "entries": {v["cveID"]: v for v in feed.get("vulnerabilities", [])}}
    return await _cached_fetch("kev:feed", KEV_MAX_AGE, fetch)


async def _nvd_record(client: httpx.AsyncClient, cve_id: str) -> tuple[dict, datetime] | None:
    async def fetch():
        headers = {"apiKey": settings.nvd_api_key} if settings.nvd_api_key else {}
        response = await client.get(NVD_API_URL, params={"cveId": cve_id}, headers=headers)
        response.raise_for_status()
        found = response.json().get("vulnerabilities") or []
        return {"cve": found[0]["cve"]} if found else {"cve": None}
    return await _cached_fetch(f"nvd:{cve_id}", NVD_MAX_AGE, fetch)


def _cvss(metrics: dict) -> tuple[float | None, str | None, str | None, str | None]:
    for key, version in CVSS_KEYS:
        entries = metrics.get(key) or []
        if entries:
            best = next((e for e in entries if e.get("type") == "Primary"), entries[0])
            data = best.get("cvssData", {})
            return data.get("baseScore"), data.get("baseSeverity"), version, best.get("source")
    return None, None, None, None


def _affected(cve: dict) -> list[str]:
    ranges: list[str] = []
    for config in cve.get("configurations") or []:
        for node in config.get("nodes") or []:
            for match in node.get("cpeMatch") or []:
                if not match.get("vulnerable"):
                    continue
                parts = match.get("criteria", "").split(":")
                if len(parts) < 6:
                    continue
                vendor, name = parts[3].replace("_", " "), parts[4].replace("_", " ")
                product = name if vendor == name else f"{vendor} {name}"
                version = parts[5] if parts[5] not in ("*", "-") else ""
                low = match.get("versionStartIncluding") or match.get("versionStartExcluding")
                high = match.get("versionEndExcluding") or match.get("versionEndIncluding")
                if low or high:
                    text = f"{product} {low or 'any'} to {'before ' if match.get('versionEndExcluding') else ''}{high or 'latest'}"
                else:
                    text = f"{product} {version}".strip()
                if text not in ranges:
                    ranges.append(text)
    return ranges[:MAX_AFFECTED]


def _references(cve: dict) -> list[VulnReference]:
    refs: dict[str, VulnReference] = {}
    for ref in cve.get("references") or []:
        all_tags = set(ref.get("tags") or [])
        tags = [t for t in ref.get("tags") or [] if t in REFERENCE_TAGS]
        # NVD sometimes tags an exploit module as "Patch" too; never present an exploit as the fix.
        if tags and "Exploit" not in all_tags and ref.get("url") and ref["url"] not in refs:
            refs[ref["url"]] = VulnReference(url=ref["url"], tags=tags)
    return list(refs.values())[:MAX_REFERENCES]


def _english(cve: dict) -> str | None:
    text = next((d["value"] for d in cve.get("descriptions") or [] if d.get("lang") == "en"), None)
    if text and len(text) > MAX_DESCRIPTION_CHARS:
        text = text[:MAX_DESCRIPTION_CHARS].rsplit(" ", 1)[0] + "…"
    return text


async def enrich_cves(iocs: list[IOC]) -> list[VulnInfo]:
    """One VulnInfo per distinct CVE IOC, in report order."""
    cves = [i for i in iocs if i.type == "cve" and not i.filtered_reason]
    if not cves:
        return []
    results: list[VulnInfo] = []
    async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=True,
                                 headers={"User-Agent": "TRINETRA threat-report analyser"}) as client:
        kev = await _kev_catalog(client)
        for n, ioc in enumerate(cves):
            info = VulnInfo(cve_id=ioc.value, ioc_id=ioc.id)
            if kev:
                catalog, fetched = kev
                entry = catalog["entries"].get(ioc.value)
                info.kev_status, info.kev_retrieved_at = "ok", fetched
                info.kev_catalog_version = catalog.get("catalogVersion")
                info.in_kev = entry is not None
                if entry:
                    info.kev_name = entry.get("vulnerabilityName")
                    info.kev_date_added = entry.get("dateAdded")
                    info.kev_required_action = entry.get("requiredAction")
                    info.kev_due_date = entry.get("dueDate")
                    info.kev_ransomware_use = entry.get("knownRansomwareCampaignUse")

            if n:
                await asyncio.sleep(NVD_GAP_S)
            record = await _nvd_record(client, ioc.value)
            if record:
                payload, fetched = record
                info.nvd_retrieved_at = fetched
                cve = payload.get("cve")
                if cve is None:
                    info.nvd_status = "not_found"
                else:
                    info.nvd_status = "ok"
                    info.nvd_url = f"{NVD_API_URL}?cveId={ioc.value}"
                    metrics = cve.get("metrics") or {}
                    info.cvss_score, info.cvss_severity, info.cvss_version, info.cvss_source = _cvss(metrics)
                    info.description = _english(cve)
                    info.affected = _affected(cve)
                    info.references = _references(cve)
            results.append(info)
    return results
