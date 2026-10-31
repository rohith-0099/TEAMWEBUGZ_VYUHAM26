"""Public references behind every rule. Served by GET /api/sources; the UI never duplicates this.

Only pages that were opened and confirmed belong in SOURCES. A link that could not be confirmed
goes in UNVERIFIED: it is recorded in docs/DECISIONS.md and never sent to the UI.
A rule with no external standard has source_keys=[] and is shown as a project rule.
"""

SOURCES: dict[str, dict[str, str]] = {
    "attack_v20": {
        "title": "MITRE ATT&CK updates (v20, released October 13, 2026)",
        "url": "https://attack.mitre.org/resources/updates/",
        "publisher": "MITRE",
        "why": "The official list of ATT&CK versions. v20 is the version every technique ID is checked against.",
    },
    "attack_t1698": {
        "title": "Indirect Prompt Injection, Technique T1698",
        "url": "https://attack.mitre.org/techniques/T1698/",
        "publisher": "MITRE",
        "why": "Defines prompts embedded in content that an LLM is expected to process.",
    },
    "attack_t1699": {
        "title": "Direct Prompt Injection, Technique T1699",
        "url": "https://attack.mitre.org/techniques/T1699/",
        "publisher": "MITRE",
        "why": "Defines prompts entered directly into an LLM's user interface.",
    },
    "attack_t1003_001": {
        "title": "OS Credential Dumping: LSASS Memory, Technique T1003.001",
        "url": "https://attack.mitre.org/techniques/T1003/001/",
        "publisher": "MITRE",
        "why": "Defines accessing credential material stored in LSASS process memory.",
    },
    "attack_t1041": {
        "title": "Exfiltration Over C2 Channel, Technique T1041",
        "url": "https://attack.mitre.org/techniques/T1041/",
        "publisher": "MITRE",
        "why": "Defines stealing data by exfiltrating it over an existing command and control channel.",
    },
    "tesseract": {
        "title": "Tesseract Open Source OCR Engine",
        "url": "https://github.com/tesseract-ocr/tesseract",
        "publisher": "Tesseract OCR project",
        "why": "The OCR engine that reads text in report images. OCR can misread characters, so indicators "
               "found only in image text are flagged for verification.",
    },
    "cisa_attack_mapping": {
        "title": "Best Practices for MITRE ATT&CK Mapping",
        "url": "https://www.cisa.gov/sites/default/files/2023-01/Best%20Practices%20for%20MITRE%20ATTCK%20Mapping.pdf",
        "publisher": "CISA",
        "why": "Tells analysts to iterate until there are only clear matches or a lack of evidence to make any match.",
    },
    "iana_ipv4_special": {
        "title": "IANA IPv4 Special-Purpose Address Registry",
        "url": "https://www.iana.org/assignments/iana-ipv4-special-registry/",
        "publisher": "IANA",
        "why": "Lists the address blocks reserved for special use, and which are not globally reachable.",
    },
    "rfc1918": {
        "title": "RFC 1918: Address Allocation for Private Internets",
        "url": "https://www.rfc-editor.org/rfc/rfc1918",
        "publisher": "IETF",
        "why": "Defines 10/8, 172.16/12 and 192.168/16 as private address space.",
    },
    "rfc5737": {
        "title": "RFC 5737: IPv4 Address Blocks Reserved for Documentation",
        "url": "https://www.rfc-editor.org/rfc/rfc5737",
        "publisher": "IETF",
        "why": "Reserves TEST-NET-1, -2 and -3 for documentation, so they never identify real hosts.",
    },
    "rfc791": {
        "title": "RFC 791: Internet Protocol",
        "url": "https://www.rfc-editor.org/rfc/rfc791",
        "publisher": "IETF",
        "why": "IPv4 addresses are four octets, so a dotted number with a part above 255 cannot be one.",
    },
    "rfc3986": {
        "title": "RFC 3986: Uniform Resource Identifier (URI): Generic Syntax",
        "url": "https://www.rfc-editor.org/rfc/rfc3986",
        "publisher": "IETF",
        "why": "A path is a sequence of segments separated by a slash, so text after a single slash is a path, not a host.",
    },
    "rfc1321": {
        "title": "RFC 1321: The MD5 Message-Digest Algorithm",
        "url": "https://www.rfc-editor.org/rfc/rfc1321",
        "publisher": "IETF",
        "why": 'Its test suite gives d41d8cd98f00b204e9800998ecf8427e as MD5(""), the hash of nothing.',
    },
    "public_suffix_list": {
        "title": "Public Suffix List",
        "url": "https://publicsuffix.org/",
        "publisher": "Public Suffix List project",
        "why": "Lists the suffixes under which names can be registered. A name without one is not a real domain.",
    },
    "google_public_dns": {
        "title": "Google Public DNS",
        "url": "https://developers.google.com/speed/public-dns",
        "publisher": "Google",
        "why": "Publishes 8.8.8.8 and 8.8.4.4 as public DNS servers.",
    },
    "cloudflare_dns": {
        "title": "Cloudflare 1.1.1.1 IP addresses",
        "url": "https://developers.cloudflare.com/1.1.1.1/ip-addresses/",
        "publisher": "Cloudflare",
        "why": "Publishes 1.1.1.1 and 1.0.0.1 as public DNS resolvers.",
    },
    "quad9": {
        "title": "Quad9",
        "url": "https://quad9.net/",
        "publisher": "Quad9",
        "why": "Publishes 9.9.9.9 as a public DNS resolver.",
    },
    "opendns": {
        "title": "OpenDNS Setup Guide",
        "url": "https://www.opendns.com/setupguide/",
        "publisher": "OpenDNS (Cisco)",
        "why": "Publishes 208.67.222.222 as an OpenDNS nameserver.",
    },
    "talos_php_exploit": {
        "title": "Unmasking the new persistent attacks on Japan",
        "url": "https://blog.talosintelligence.com/new-persistent-attacks-japan/",
        "publisher": "Cisco Talos",
        "why": "Shows e10adc3949ba59abbe56e057f20f883e is what the exploit script checks for to confirm success, not malware.",
    },
    "iocextract": {
        "title": "iocextract: Defanged Indicator of Compromise (IOC) Extractor",
        "url": "https://github.com/pedramamini/iocextract",
        "publisher": "InQuest project",
        "why": "Documents the defanging conventions indicators use in threat reports.",
    },
    "dbip_city_lite": {
        "title": "DB-IP IP to City Lite",
        "url": "https://db-ip.com/db/download/ip-to-city-lite",
        "publisher": "DB-IP",
        "why": "Free offline IP-to-location database, licensed CC BY 4.0, with reduced coverage and accuracy.",
    },
    "nvd_api": {
        "title": "NVD CVE API 2.0",
        "url": "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1",
        "publisher": "NIST National Vulnerability Database",
        "why": "The official CVE records: CVSS scores, descriptions, affected versions and tagged references.",
    },
    "cisa_kev": {
        "title": "CISA Known Exploited Vulnerabilities Catalog",
        "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "publisher": "CISA",
        "why": "CISA's authoritative list of vulnerabilities exploited in the wild, with required actions and due dates.",
    },
    "cvss31": {
        "title": "CVSS v3.1 Specification Document",
        "url": "https://www.first.org/cvss/v3.1/specification-document",
        "publisher": "FIRST",
        "why": "Defines the severity bands: Low 0.1-3.9, Medium 4.0-6.9, High 7.0-8.9, Critical 9.0-10.0.",
    },
    "nist_cve": {
        "title": "Common Vulnerabilities and Exposures (CVE), NIST CSRC glossary",
        "url": "https://csrc.nist.gov/glossary/term/common_vulnerabilities_and_exposures",
        "publisher": "NIST",
        "why": "Defines CVE as a list of publicly known vulnerabilities, each with an ID, description and reference.",
    },
    "nist_ioc": {
        "title": "Indicator of Compromise, NIST CSRC glossary",
        "url": "https://csrc.nist.gov/glossary/term/indicator_of_compromise",
        "publisher": "NIST",
        "why": "Defines indicators of compromise as technical artifacts that suggest an attack or compromise.",
    },
    "attack_tactics": {
        "title": "ATT&CK Enterprise tactics",
        "url": "https://attack.mitre.org/tactics/enterprise/",
        "publisher": "MITRE",
        "why": "Tactics are the \"why\": the adversary's goal for an action.",
    },
    "attack_techniques": {
        "title": "ATT&CK Enterprise techniques",
        "url": "https://attack.mitre.org/techniques/enterprise/",
        "publisher": "MITRE",
        "why": "Techniques are the \"how\": the action an adversary performs to reach a goal.",
    },
    "attack_ta0011": {
        "title": "Command and Control, Tactic TA0011",
        "url": "https://attack.mitre.org/tactics/TA0011/",
        "publisher": "MITRE",
        "why": "Defines command and control as the adversary communicating with compromised systems to control them.",
    },
}

UNVERIFIED: dict[str, dict[str, str]] = {
    "dns114": {
        "title": "114DNS",
        "url": "http://www.114dns.com/",
        "publisher": "114DNS",
        "why": "The site's TLS certificate could not be verified, so the page could not be opened.",
    },
    "nvd_docs": {
        "title": "NVD Vulnerability APIs documentation",
        "url": "https://nvd.nist.gov/developers/vulnerabilities",
        "publisher": "NIST",
        "why": "The page renders with JavaScript only, so its text could not be read. The API itself was confirmed.",
    },
    "cve_org": {
        "title": "CVE Program overview",
        "url": "https://www.cve.org/About/Overview",
        "publisher": "CVE Program",
        "why": "The page renders with JavaScript only, so its text could not be read.",
    },
}

# One plain line per term for the "?" popovers in the app.
GLOSSARY: dict[str, dict[str, str]] = {
    "ioc": {"term": "IOC (indicator of compromise)",
            "text": "A technical clue, such as an IP address, domain or file hash, that suggests an attack happened.",
            "source_key": "nist_ioc"},
    "cve": {"term": "CVE",
            "text": "A public ID for one known software vulnerability, such as CVE-2024-4577.",
            "source_key": "nist_cve"},
    "c2": {"term": "C2 (command and control)",
           "text": "A server the attacker uses to send orders to, and receive data from, infected machines.",
           "source_key": "attack_ta0011"},
    "technique": {"term": "Technique (T-code)",
                  "text": "How an attacker does something, such as dumping passwords. T1003.001 is its ATT&CK code.",
                  "source_key": "attack_techniques"},
    "tactic": {"term": "Tactic",
               "text": "Why the attacker does it: the goal of a step, such as gaining access or stealing credentials.",
               "source_key": "attack_tactics"},
    "defanged": {"term": "Defanged",
                 "text": "Written so it can't be clicked by accident, e.g. evil[.]com instead of evil.com.",
                 "source_key": "iocextract"},
    "hallucinations": {"term": "Hallucinations blocked",
                       "text": "AI answers we threw away because the technique ID doesn't exist in ATT&CK v20 "
                               "or the quoted proof isn't in the report.",
                       "source_key": "attack_v20"},
    "cvss": {"term": "CVSS score",
             "text": "A 0 to 10 severity score for a vulnerability. 9.0 and above is Critical.",
             "source_key": "cvss31"},
    "kev": {"term": "CISA KEV",
            "text": "CISA's list of vulnerabilities that attackers are known to be exploiting right now.",
            "source_key": "cisa_kev"},
}

# reason -> what the rule does and what backs it. Shown on the "How it works" page.
RULES: dict[str, dict] = {
    # IOC filters
    "private_or_reserved_ip": {
        "kind": "ioc_filter", "label": "Private or reserved IP",
        "rule": "Addresses that are not globally reachable cannot identify attacker infrastructure.",
        "source_keys": ["iana_ipv4_special", "rfc1918", "rfc5737"],
    },
    "public_dns": {
        "kind": "ioc_filter", "label": "Public DNS resolver",
        "rule": "Well-known public resolvers are used by everyone, so they do not point to an attacker.",
        "source_keys": ["google_public_dns", "cloudflare_dns", "quad9", "opendns"],
    },
    "version_number": {
        "kind": "ioc_filter", "label": "Version number",
        "rule": "A dotted number with a part above 255 is not an IP. Numbers right after a word like "
                "\"version\" or \"build\" are also treated as versions (project rule).",
        "source_keys": ["rfc791"],
    },
    "invalid_domain": {
        "kind": "ioc_filter", "label": "Not a real domain",
        "rule": "A domain must end in a registrable public suffix.",
        "source_keys": ["public_suffix_list"],
    },
    "url_path_not_domain": {
        "kind": "ioc_filter", "label": "URL path, not a domain",
        "rule": "Text directly after a single slash is part of a path, such as /hello.world.",
        "source_keys": ["rfc3986"],
    },
    "known_benign_hash": {
        "kind": "ioc_filter", "label": "Known harmless hash",
        "rule": "Hashes of empty input or of the text \"123456\" identify no malware.",
        "source_keys": ["talos_php_exploit", "rfc1321"],
    },
    "benign_domain": {
        "kind": "ioc_filter", "label": "Common legitimate domain",
        "rule": "Our own allowlist of widely used services. Filtered items stay visible for review.",
        "source_keys": [],
    },
    "looks_like_filename": {
        "kind": "ioc_filter", "label": "File name",
        "rule": "Names ending in a file extension, or also seen as a file in a path. Some extensions "
                "are real suffixes, such as .sh and .zip, so this is our own judgement.",
        "source_keys": [],
    },
    "reference_link": {
        "kind": "ioc_filter", "label": "Reference link",
        "rule": "Links to reference sites such as ATT&CK and NVD are citations, not indicators.",
        "source_keys": [],
    },
    "ocr_unreliable": {
        "kind": "ioc_filter", "label": "Unreliable OCR hash",
        "rule": "A hash read only from an image must be a clean hex string of the exact length. OCR can "
                "misread characters, so anything else is dropped; other indicators from images are kept but "
                "marked \"From image (OCR) - verify\".",
        "source_keys": ["tesseract"],
    },
    # technique rejections
    "id_not_in_v20": {
        "kind": "technique_reject", "label": "ID not in ATT&CK v20",
        "rule": "The ID does not exist in the official ATT&CK v20 data, so it was made up.",
        "source_keys": ["attack_v20"],
    },
    "deprecated": {
        "kind": "technique_reject", "label": "Deprecated technique",
        "rule": "The ID is revoked or deprecated in ATT&CK v20.",
        "source_keys": ["attack_v20"],
    },
    "quote_not_in_source": {
        "kind": "technique_reject", "label": "Quote not in the report",
        "rule": "The quoted evidence does not appear in the report, so nothing supports the mapping.",
        "source_keys": ["cisa_attack_mapping"],
    },
    "verifier_mismatch": {
        "kind": "technique_reject", "label": "Evidence does not fit",
        "rule": "The verifier compared the evidence with the official description and found no match, "
                "or the evidence only names the technique (an ATT&CK table, appendix or list) instead of "
                "describing what the attacker did.",
        "source_keys": ["cisa_attack_mapping"],
    },
    "low_confidence": {
        "kind": "technique_reject", "label": "Not enough evidence",
        "rule": "The evidence is too indirect to meet the confidence threshold.",
        "source_keys": ["cisa_attack_mapping"],
    },
}


def source_key_for(reason: str | None) -> str | None:
    """The reference for a reason, when that reason has exactly one."""
    keys = RULES.get(reason or "", {}).get("source_keys", [])
    return keys[0] if len(keys) == 1 else None
