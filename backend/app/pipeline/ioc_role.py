"""IOC role agent. Owner: RAG. See team/04_RAG_AI.md Step 7."""

import asyncio
import json
import logging
from typing import Literal
from pydantic import BaseModel

from app.llm import complete_json, RequestTooLarge, UNTRUSTED_RULE
from app.models import IOC, IOCRole
from app.utils.quotes import find_quote

logger = logging.getLogger(__name__)

ROLE_SYSTEM_PROMPT = f"""You are a cyber threat intelligence analyst determining the role of Indicators of Compromise (IOCs) from evidence snippets.
Roles:
- c2: command-and-control server, domain, IP or URL contacted by malware.
- payload: malicious file, hash, or download URL delivering malware.
- phishing: sender address, lure domain, or credential phishing URL.
- exfil: destination receiving stolen data or exfiltration endpoint.
- victim: targeted organization's internal asset, IP, domain, or mailbox.
- scanner: source of scanning, reconnaissance, or brute-force attempts.
- infrastructure: other attacker-controlled hosting, staging, or transit infrastructure.
- unknown: the text does not state the role.

Rules:
If the text does not state the role, answer unknown. Never guess from the indicator's appearance.
The quote MUST be a verbatim sentence fragment from the provided evidence justifying the role.
{UNTRUSTED_RULE}"""


class _R(BaseModel):
    id: str
    role: Literal["c2", "payload", "phishing", "exfil", "victim", "scanner", "infrastructure", "unknown"] = "unknown"
    confidence: float = 0.0  # 0..1
    quote: str = ""  # verbatim sentence fragment justifying the role


class _Out(BaseModel):
    roles: list[_R] = []


async def label_roles(text: str, iocs: list[IOC]) -> list[IOC]:
    """Label IOC roles using evidence snippets, batching up to 40 IOCs in parallel."""
    if not iocs:
        return []

    # Separate eligible and filtered IOCs
    eligible_iocs: list[IOC] = [ioc for ioc in iocs if ioc.filtered_reason is None]
    if not eligible_iocs:
        return iocs

    # Small batches: the request, including max_tokens, must fit the provider's per-minute token limit
    batch_size = 15
    batches = [eligible_iocs[i:i + batch_size] for i in range(0, len(eligible_iocs), batch_size)]

    async def _process_batch(batch: list[IOC]) -> list[_R]:
        items_payload = []
        for ioc in batch:
            ev_quotes = [ev.quote for ev in ioc.evidence if ev.quote]
            items_payload.append({
                "id": ioc.id,
                "type": ioc.type,
                "display": ioc.display,
                "evidence_snippets": ev_quotes,
            })

        user_prompt = (
            "Analyze the role of each IOC based strictly on its evidence snippets:\n"
            f"{json.dumps(items_payload, indent=2)}"
        )

        try:
            res: _Out = await complete_json(
                system=ROLE_SYSTEM_PROMPT,
                user=user_prompt,
                schema=_Out,
                model="verify",
                max_tokens=2000,
            )
            return res.roles
        except RequestTooLarge:
            if len(batch) == 1:
                logger.warning(f"IOC role request too large for {batch[0].id}")
                return []
            half = len(batch) // 2
            first, second = await asyncio.gather(_process_batch(batch[:half]), _process_batch(batch[half:]))
            return first + second
        except Exception as exc:
            logger.warning(f"IOC role labeling batch failed: {exc}")
            return []

    batch_results = await asyncio.gather(*[_process_batch(b) for b in batches])
    role_map: dict[str, _R] = {}
    for r_list in batch_results:
        for r in r_list:
            role_map[r.id] = r

    # Apply results to eligible IOCs
    for ioc in eligible_iocs:
        r = role_map.get(ioc.id)
        if not r or r.role == "unknown" or not r.quote:
            ioc.role = "unknown"
            ioc.confidence.role = None
            continue

        found = find_quote(text, r.quote)
        if found is not None:
            ev, _ = found
            ioc.role = r.role
            ioc.confidence.role = round(max(0.0, min(1.0, r.confidence)), 2)
            # Append evidence if not already present
            if not any(e.start == ev.start and e.end == ev.end for e in ioc.evidence):
                ioc.evidence.append(ev)
        else:
            ioc.role = "unknown"
            ioc.confidence.role = None

    return iocs
