# Decisions

Every fix, the problem that caused it, and the public source that backs it. Sources are listed only
after the page was opened and the quoted text confirmed. The same references are served by
`GET /api/sources` (`backend/app/sources.py`) and shown in the app on the **How it works** page.

Sources that could not be opened are marked **UNVERIFIED** and are never shown in the UI.

---

## Phase 1: truth fixes

### D1. Map showed invented locations

- **Problem:** No GeoIP database is installed, so `geo.py` placed every IP it could not look up at
  latitude 37.7749, longitude -122.4194 (San Francisco) with country "US". On the CVE-2024-4577 PHP-CGI
  report, every point returned by `/geo` had those coordinates.
- **Fix:** With no database, `/geo` returns `{"available": false, "points": []}`. An IP the database
  cannot place gets no point. The frontend shows the **Map** tab only when `available` is true.
- **Files changed:** `backend/app/pipeline/geo.py`, `frontend/lib/api.ts`, `frontend/lib/types.ts`,
  `frontend/components/globe/GlobeView.tsx`, `frontend/app/report/[id]/page.tsx`,
  `team/00_SHARED_CONTRACTS.md` §8.
- **Source:** DB-IP, IP to City Lite, https://db-ip.com/db/download/ip-to-city-lite
- **Why it supports the fix:** The page describes the Lite database as having "reduced coverage and
  accuracy". Some IPs will not be found, so a missing result must stay missing, not be replaced with
  a default. (Licence on the same page: Creative Commons Attribution 4.0.)

### D2. "Hallucinations blocked" disagreed across the screen

- **Problem:** Three places showed three different numbers for the same thing. The stat card counted
  `id_not_in_v20` + `quote_not_in_source`. The filter chart's first checkpoint also included
  `deprecated`. The technique list's "Hallucinations Blocked" button counted every rejection,
  including normal verifier disagreements (23 on the PHP report).
- **Fix:** One helper, `frontend/lib/hallucinations.ts`, defines a hallucination as a rejection with
  reason `id_not_in_v20` or `quote_not_in_source`. All three places use it. The chart now shows
  `deprecated` as its own checkpoint, and the list button reads "rejected (N) · M hallucinations
  blocked" so both numbers are visible and neither is mislabelled.
- **Files changed:** `frontend/lib/hallucinations.ts` (new), `frontend/app/report/[id]/page.tsx`,
  `frontend/components/report-overview/FilterStream.tsx`,
  `frontend/components/technique-card/TechniqueCards.tsx`.
- **Source:** MITRE ATT&CK updates, https://attack.mitre.org/resources/updates/
- **Why it supports the fix:** It lists v20 (October 13, 2026) as the current version. An ID absent
  from that release does not exist, so proposing it is a fabrication. A quote absent from the report is
  the same kind of fabrication. Disagreeing about which real technique fits is not, so it is not counted.

### D3. "hello.world" reported as a domain

- **Problem:** The PHP report says "A second actor sent exploit requests to /hello.world". The
  extractor reported `hello.world` as a domain IOC, and the AI then labelled it a **victim**. `.world`
  is a real top-level domain, so a suffix check alone cannot catch this.
- **Fix:** A domain is filtered as `url_path_not_domain` when every occurrence comes directly after a
  single `/` (but not after `//`, which introduces a host).
- **Files changed:** `backend/app/pipeline/ioc.py`.
- **Source:** RFC 3986, URI Generic Syntax, https://www.rfc-editor.org/rfc/rfc3986
- **Why it supports the fix:** "A path consists of a sequence of path segments separated by a slash
  ("/") character." Text after a single slash is a path segment, not a host name.

### D4. Names without a real suffix accepted as domains

- **Problem:** The old check accepted any name whose last label was alphabetic.
- **Fix:** A domain must have a registrable public suffix, checked against the Public Suffix List
  snapshot bundled with `tldextract` (no network call). Otherwise it is filtered as `invalid_domain`.
- **Files changed:** `backend/app/pipeline/ioc.py`, `backend/requirements.txt` (adds `tldextract`).
- **Source:** Public Suffix List, https://publicsuffix.org/
- **Why it supports the fix:** "A 'public suffix' is one under which Internet users can (or
  historically could) directly register names." A name with no public suffix cannot be registered.

### D5. Private, reserved and documentation IPs

- **Problem:** The rule existed but had no visible justification, and it missed some special ranges.
- **Fix:** Any IP that is not globally reachable, or is multicast, is filtered as
  `private_or_reserved_ip`. The `source_key` names the most specific reference: RFC 1918 for private
  ranges, RFC 5737 for documentation ranges, the IANA registry for everything else (for example
  100.64.0.0/10).
- **Files changed:** `backend/app/pipeline/ioc.py`.
- **Sources:**
  - IANA IPv4 Special-Purpose Address Registry, https://www.iana.org/assignments/iana-ipv4-special-registry/
  - RFC 1918, https://www.rfc-editor.org/rfc/rfc1918
  - RFC 5737, https://www.rfc-editor.org/rfc/rfc5737
- **Why they support the fix:** The IANA registry lists each special block and whether it is globally
  reachable (for example "100.64.0.0/10 Shared Address Space"). RFC 1918 defines "10.0.0.0 -
  10.255.255.255 (10/8 prefix)" and the other private blocks. RFC 5737 says 192.0.2.0/24,
  198.51.100.0/24 and 203.0.113.0/24 "are provided for use in documentation".

### D6. Public DNS resolvers reported as attacker infrastructure

- **Problem:** On the PHP report, `114.114.114.114` was kept as an IOC and labelled
  **infrastructure**. Attackers set public resolvers in configs, but so does everyone else; the address
  says nothing about the attacker.
- **Fix:** 8.8.8.8, 8.8.4.4, 1.1.1.1, 1.0.0.1, 9.9.9.9, 208.67.222.222 and 114.114.114.114 are
  filtered as `public_dns` and stay visible under "Filtered out".
- **Files changed:** `backend/app/pipeline/ioc.py`.
- **Sources:**
  - Google Public DNS, https://developers.google.com/speed/public-dns: "8.8.8.8 and 8.8.4.4 as your DNS servers"
  - Cloudflare 1.1.1.1 IP addresses, https://developers.cloudflare.com/1.1.1.1/ip-addresses/: lists 1.1.1.1 and 1.0.0.1
  - Quad9, https://quad9.net/: lists 9.9.9.9
  - OpenDNS Setup Guide, https://www.opendns.com/setupguide/: "Our nameservers are always: 208.67.222.222 208.67.220.220"
  - **UNVERIFIED:** 114DNS, http://www.114dns.com/. The site's TLS certificate could not be
    verified, so the page could not be opened. 114.114.114.114 is still filtered, but its item shows
    no source link in the app.
- **Why they support the fix:** Each provider publishes these addresses as public resolvers anyone
  can use.

### D7. A harmless hash reported as a malware indicator

- **Problem:** The PHP report contains `e10adc3949ba59abbe56e057f20f883e`. It was kept as an md5 IOC.
  It is the MD5 of the text "123456", which the exploit makes the server print to prove the attack
  worked. It identifies no malware file.
- **Fix:** Hashes of empty input and of "123456" are filtered as `known_benign_hash`. The digests are
  computed in code (MD5, SHA-1, SHA-256, SHA-512), not typed in, so none can be mistyped.
- **Files changed:** `backend/app/pipeline/ioc.py`.
- **Sources:**
  - Cisco Talos, "Unmasking the new persistent attacks on Japan",
    https://blog.talosintelligence.com/new-persistent-attacks-japan/: "If the response contains the MD5
    hash "e10adc3949ba59abbe56e057f20f883e", it indicates a successful exploitation."
  - RFC 1321, The MD5 Message-Digest Algorithm, https://www.rfc-editor.org/rfc/rfc1321: its test suite
    gives `MD5 ("") = d41d8cd98f00b204e9800998ecf8427e`.
- **Why they support the fix:** Talos shows the PHP hash is the exploit's success check. RFC 1321
  shows the empty-input MD5 is the hash of nothing. The SHA variants of the same two inputs carry no
  external citation; their item shows "Project rule" in the app.

### D8. Re-analysing the same report flooded the header with alerts

- **Problem:** The PHP report was analysed twice. The second run produced 61 `seen_before` chips, one
  per IOC, all pointing at the earlier copy of the same document. That is not new intelligence.
- **Fix:** Before writing memory, the SHA-256 of the report's normalised text is compared with every
  finished analysis. On a match, the only alert is one `duplicate_report` notice, "This report was
  already analysed on <date>", with a link to the earlier analysis, and no memory edges are written.
  Otherwise the header shows at most 3 alert chips plus "+N more".
- **Files changed:** `backend/app/pipeline/memory.py`, `backend/app/models.py`,
  `frontend/lib/types.ts`, `frontend/app/report/[id]/page.tsx`, `team/00_SHARED_CONTRACTS.md` §6.
- **Source:** None. This is a display rule: one document should produce one notice.

### D9. Every rule carries its source

- **Problem:** Filter and rejection reasons appeared as raw codes such as `dropped: looks_like_filename`,
  with no explanation and nothing a judge could check.
- **Fix:** `backend/app/sources.py` holds `SOURCES` (confirmed references) and `RULES` (each reason,
  a plain-English rule, and its source keys). `IOC`, `TechniqueMatch` and `Migration` carry a
  `source_key`. `GET /api/sources` serves both tables; `frontend/lib/sources.ts` fetches them.
  Every filtered IOC, rejected technique and migration shows a **Source** link with a one-line why.
  Rules with no external standard (`benign_domain`, `looks_like_filename`, `reference_link`) say
  "Project rule". The new **How it works** page lists the pipeline, every rule, every source and the
  limitations.
- **Files changed:** `backend/app/sources.py` (new), `backend/app/models.py`,
  `backend/app/api/routes.py`, `backend/app/pipeline/ioc.py`, `backend/app/pipeline/verify.py`,
  `frontend/lib/sources.ts` (new), `frontend/components/ui/source-link.tsx` (new),
  `frontend/app/how-it-works/page.tsx` (new), `frontend/components/layout/Sidebar.tsx`,
  `frontend/components/ioc-table/IocTable.tsx`,
  `frontend/components/technique-card/TechniqueCards.tsx`, `team/00_SHARED_CONTRACTS.md` §6, §8.
- **Sources for technique rejections:** CISA, Best Practices for MITRE ATT&CK Mapping (PDF),
  https://www.cisa.gov/sites/default/files/2023-01/Best%20Practices%20for%20MITRE%20ATTCK%20Mapping.pdf
- **Why it supports the fix:** The guide tells analysts to work "until there are only clear, most
  likely matches or a lack of evidence to make any match", and warns that "a simple list of ATT&CK
  tactics or techniques—without associated technical context" is not enough to map. That is the basis
  for rejecting a mapping whose evidence does not fit (`verifier_mismatch`), is too indirect
  (`low_confidence`) or does not exist (`quote_not_in_source`).
- **Note on the reference list:** the CISA news page given in the brief
  (https://www.cisa.gov/news-events/news/best-practices-mitre-attckr-mapping) only announces the
  guide; the guidance itself is in the PDF above, so the app links the PDF. The InQuest iocextract
  URL redirects to https://github.com/pedramamini/iocextract, which is what the app links.

---

## Phase 2: evidence quality and speed

### D10. ATT&CK tables and appendices used as evidence

- **Problem:** On the CVE-2024-4577 PHP-CGI report, T1041 was proposed with the evidence
  "T1041 Exfiltration Over C2 Channel C vendor", a row of the report's Appendix A ATT&CK table. A
  table row names a technique; it says nothing about what the attacker did. Explicit IDs with no
  nearby behaviour were also verified "standalone" using their table row as the sentence.
- **Fix:**
  - `backend/app/utils/sections.py` (new) finds section headings and flags text that is mostly
    technique IDs and names (`is_listing`) or that sits under a heading containing "ATT&CK",
    "Appendix", "Techniques", "TTPs" or "References" (`in_reference_section`).
  - Behaviour agent: the prompt forbids table/appendix/list quotes, and code drops any behaviour whose
    quote is a listing or sits in such a section.
  - Verifier: the prompt says written technique IDs are hints only. Explicit IDs found in tables and
    appendices are no longer hints or standalone evidence. Any match whose evidence is a listing or in
    such a section is rejected as `verifier_mismatch`, with the reason shown in the app.
- **Files changed:** `backend/app/utils/sections.py` (new), `backend/app/pipeline/behaviours.py`,
  `backend/app/pipeline/verify.py`, `backend/app/attack/store.py` (`technique_names()`),
  `backend/app/sources.py` (rule text).
- **Source:** CISA, Best Practices for MITRE ATT&CK Mapping,
  https://www.cisa.gov/sites/default/files/2023-01/Best%20Practices%20for%20MITRE%20ATTCK%20Mapping.pdf
- **Why it supports the fix:** The guide's "To Map or Not to Map" section warns that "a simple list of
  ATT&CK tactics or techniques—without associated technical context that explains how the adversary
  executed the technique" is not enough to map.

### D11. Headings and summary phrases used as evidence

- **Problem:** In a run of the new code on the same report, T1068 was accepted with the evidence
  "privilege escalation", which is part of the heading "Discovery and privilege escalation.", and
  T1003 with "credential dumping", an item in the executive summary's list. Neither describes an
  action. The verifier prompt asked for the "shortest span that proves the match", which invited this.
- **Fix:** The prompt now asks for the sentence or clause that states the attacker's action, never a
  heading, summary item or bare technique name. Code rejects evidence of fewer than 4 words or lying
  inside a heading line as `verifier_mismatch`. Replaying that run's 10 accepted matches through the
  new checks rejects exactly these two and keeps the other 8.
- **Files changed:** `backend/app/pipeline/verify.py`.
- **Source:** the CISA guide above, same passage (technical context of how the adversary executed the
  technique is required).

### D12. LSASS and exfiltration recall

- **Problem:** The brief asked why T1003.001 (Mimikatz dumping LSASS) and T1041 (exfiltration over
  the C2 channel) were rejected on the PHP report. They were not rejected on their evidence. In run
  `6aa43e58dfe6`, the retriever ranked the right technique first for both sentences (T1003.001 at
  0.74 for "The actor ran Mimikatz to dump plaintext passwords and NTLM hashes from LSASS memory.",
  T1041 at 0.69 for "Collected data was sent out over the existing Cobalt Strike command-and-control
  channel."), but the verifier returned **no result** for either behaviour: their calls were lost to
  provider rate limits (see D13). The two T1041 rejections came from the appendix row and an IOC table
  line, both correctly not evidence.
- **Fix:** No threshold change. The fixes are in D13: calls are paced and no longer silently lost.
  The verifier prompt also now says that an action stated in the report's own words or tool names
  counts when the official description covers it.
- **Files changed:** `backend/app/pipeline/verify.py`, `backend/app/llm.py`.
- **Sources:**
  - ATT&CK T1003.001, https://attack.mitre.org/techniques/T1003/001/: "Adversaries may attempt to access
    credential material stored in the process memory of the Local Security Authority Subsystem Service
    (LSASS)." Its procedure examples include Mimikatz.
  - ATT&CK T1041, https://attack.mitre.org/techniques/T1041/: "Adversaries may steal data by exfiltrating
    it over an existing command and control channel."
- **Why they support the fix:** Both report sentences state exactly the action each official
  description defines, so the evidence was sufficient and the loss was operational, not a judgement.
- **Status:** not yet confirmed by a full run (D13).

### D13. Speed: the LLM key's limits, and calls being lost

- **Problem:** The key is Groq "on_demand". Its response headers state 8,000 tokens per minute and
  1,000 requests per day, and the errors state a daily limit of 200,000 tokens. Three bugs made this
  worse:
  1. A request larger than the per-minute limit returns "Request too large", which the code treated as
     a rate limit and retried 9 times (about 150 s) before failing. The IOC role stage took 156 s
     purely from this, and every IOC lost its role.
  2. Parallel calls all hit the limit together and gave up after their retries, so behaviours went
     unverified with only a log warning (D12).
  3. Batches of 4 behaviours per verifier call, tried as the brief asked, produced fewer and worse
     matches (10 accepted, including the two in D11 and ransomware encryption mapped to T1027.013) and
     two batches were too large to send.
- **Fix:**
  - "Request too large" fails at once (`RequestTooLarge`), and the verifier and IOC role agent split
    the batch in half and retry instead of losing it.
  - A client-side token bucket (`LLM_TOKENS_PER_MINUTE`, set to 8000 for this key) makes calls wait
    their turn instead of failing.
  - Verifier: 1 behaviour per call (measured above; batching saves only the repeated system prompt),
    candidate descriptions 300 characters, 1 procedure example of at most 200 characters, top 6
    candidates. Behaviours capped at 30. IOC role batches of 15. `LLM_CONCURRENCY` from env, cache kept,
    and `LLM_CACHE=false` added to measure real latency.
  - Each LLM call and each rate-limit wait is now logged with its time.
- **Files changed:** `backend/app/llm.py`, `backend/app/config.py`, `backend/app/pipeline/verify.py`,
  `backend/app/pipeline/ioc_role.py`, `backend/app/pipeline/behaviours.py`,
  `backend/app/pipeline/retrieve.py`, `.env.example`.
- **Source:** None external; the limits are from the provider's own response headers and error text.
- **Status:** the target of under a minute is **not reachable on this key**. Measuring the final code
  is blocked until the daily token quota frees up. The measured stage timings so far, none of them on
  the final code:

  | Stage | Before (`6aa43e58dfe6`, old code, same PDF analysed earlier, so partly cached) | Batch-4 run (`1b7dd2aab140`, uncached behaviours) |
  |---|---|---|
  | behaviours | 19.7 s | 109.3 s |
  | ioc_role | 13.7 s | 155.7 s (retry bug) |
  | verify | 160.9 s | 226.5 s (2 batches lost) |
  | detect | 28.0 s | 76.0 s |
  | memory | 6.4 s | 4.7 s |
  | everything else | 5.5 s | 4.2 s |

---

## Phase 3: plain-English briefing and CVE fix plan

### D14. CVE facts from NVD and CISA KEV, never guessed

- **Problem:** CVEs were shown as bare IDs. Evaluators asked how severe each one is, whether it is being
  exploited and how to fix it, and the app had no facts to answer with.
- **Fix:** New stage `vulns` (runs beside the AI stages, after IOC extraction). For each CVE in the
  report it reads:
  - the **NVD CVE API 2.0** record: CVSS score and severity (v3.1 first, then v4.0, v3.0; the
    "Primary" score when there are several), the English description, affected products and version
    ranges from the CPE configuration, and references tagged "Patch" or "Vendor Advisory";
  - the **CISA KEV JSON feed**: whether it is listed, date added, required action, due date and known
    ransomware use.

  Both are cached in Postgres (`ext_cache`, refreshed daily). If a lookup fails, the card says "lookup
  unavailable" and shows no values. Every field shows its source and retrieval date. `NVD_API_KEY`
  is optional; without it requests are spaced to respect NVD's lower limit.
- **Found while building it:** NVD tags the Metasploit pull request for CVE-2024-4577 as both "Patch"
  and "Exploit". Showing it as a patch link would send a reader to an exploit module, so references
  also tagged "Exploit" are excluded. For CVE-2024-4577 that leaves no patch link, and the card says
  "NVD lists no patch or vendor-advisory link for this CVE" rather than inventing one.
- **Files changed:** `backend/app/pipeline/vulns.py` (new), `backend/app/models.py` (`VulnInfo`),
  `backend/db/schema.sql` (`ext_cache`), `backend/app/config.py`, `backend/app/pipeline/graph.py`,
  `.env.example`, `frontend/components/report-overview/CveCards.tsx` (new), `frontend/lib/types.ts`,
  `frontend/lib/store.ts`, `frontend/components/pipeline-canvas/*`, `team/00_SHARED_CONTRACTS.md`.
- **Sources:**
  - CISA, Known Exploited Vulnerabilities Catalog, https://www.cisa.gov/known-exploited-vulnerabilities-catalog:
    "CISA maintains the authoritative source of vulnerabilities that have been exploited in the wild."
    Feed used: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
    (catalog version 2026.10.30 when tested; CVE-2024-4577 listed, added 2024-06-12, due 2024-07-03,
    known ransomware use "Known").
  - NVD CVE API 2.0, https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-4577: returned the
    record (status "Analyzed", CVSS 3.1 base 9.8 CRITICAL from nvd@nist.gov). Each CVE card links its
    own API record.
  - FIRST, CVSS v3.1 Specification, https://www.first.org/cvss/v3.1/specification-document: "Low 0.1 -
    3.9, Medium 4.0 - 6.9, High 7.0 - 8.9, Critical 9.0 - 10.0".
  - **UNVERIFIED:** NVD's documentation pages (https://nvd.nist.gov/developers/vulnerabilities and
    /developers/start-here) render with JavaScript only, so their text (rate limits, parameter
    descriptions) could not be read. Not shown in the app; the API record itself is linked instead.
- **Why they support the fix:** KEV is CISA's own authoritative list, so "actively exploited" is CISA's
  claim, not ours. NVD is the official record for scores and affected versions. The CVSS spec defines
  what "Critical" means.

### D15. The briefing is written from verified facts only

- **Problem:** The report view showed evidence and lists but never said in plain words what happened
  or what to do.
- **Fix:** New stage `brief`, after flow, detections, memory and CVE lookup. One call to the verify
  model at temperature 0. It receives only verified data: accepted techniques with their proof quotes
  in attack-flow order, kept IOCs with roles, the NVD/KEV facts, and techniques without detection
  guidance. It never sees the raw report. Code then:
  - drops any step that cites a technique this analysis did not accept, or names one in its text;
  - fixes a step's tactic to one of its techniques' tactics, and sorts steps in attack-flow order;
  - drops any action that names a CVE not in the report or a technique not accepted;
  - writes "Patch <CVE> — listed in CISA KEV" itself for every KEV-listed CVE. It is **urgent** and
    first when the CVE is in the report title or inside a quote that proves an accepted technique;
    otherwise **high**, with "Named in the report, but not part of the proven attack steps". On the PHP
    report, CVE-2024-4577 is urgent; Log4Shell (CVE-2021-44228) and CVE-2023-46604 are high, because the
    report mentions them only as the ransomware operators' past exploits ("a history of riding newly
    published, widely exploitable bugs such as Log4Shell…");
  - caps steps at 8 and actions at 6, and gives each action a source (CISA KEV or NVD for patches,
    ATT&CK for technique-based actions, "based on the indicators in this report" for blocking).
- **Frontend:** a Briefing card at the top of Overview with numbered steps, a tactic colour dot,
  "See proof" (jumps to the quote on the Evidence tab), a "What to do now" list with priority pills and
  source links, and "Download block list" (kept IPs, domains and URLs, refanged, one per line).
  Evidence highlights explain themselves on hover: "This sentence shows the attacker <action> (stage:
  <tactic>, code <ID>)", where <action> is the behaviour agent's summary of that same quote.
- **Files changed:** `backend/app/pipeline/brief.py` (new), `backend/app/models.py` (`Briefing`),
  `backend/app/pipeline/graph.py`, `frontend/components/report-overview/BriefingCard.tsx` (new),
  `frontend/components/report-viewer/ReportViewer.tsx`, `frontend/app/report/[id]/page.tsx`.
- **Source:** the CISA KEV catalog (above) for putting exploited CVEs first. The rest is a design rule:
  no step or action may reach the reader unless it rests on verified data.

### D16. Glossary for non-specialists

- **Problem:** Terms like IOC, C2 and T-code were used without explanation.
- **Fix:** A "?" next to IOC, CVE, C2, Technique, Tactic, Defanged, Hallucinations blocked, CVSS and
  CISA KEV opens one plain line and a source link. The text lives in `GLOSSARY` in
  `backend/app/sources.py` and is served with `/api/sources`.
- **Files changed:** `backend/app/sources.py`, `backend/app/api/routes.py`,
  `frontend/components/ui/glossary-hint.tsx` (new), `frontend/components/charts/StatCard.tsx`,
  `frontend/components/ioc-table/IocTable.tsx`, `frontend/app/report/[id]/page.tsx`.
- **Sources:**
  - NIST CSRC, Indicator of Compromise, https://csrc.nist.gov/glossary/term/indicator_of_compromise:
    "Technical artifacts or observables that suggest that an attack is imminent or is currently underway
    or that a compromise may have already occurred."
  - NIST CSRC, Common Vulnerabilities and Exposures, https://csrc.nist.gov/glossary/term/common_vulnerabilities_and_exposures:
    "A list of entries-each containing an identification number, a description, and at least one public
    reference-for publicly known CS vulnerabilities."
  - ATT&CK Command and Control (TA0011), https://attack.mitre.org/tactics/TA0011/: "The adversary is trying
    to communicate with compromised systems to control them."
  - ATT&CK tactics, https://attack.mitre.org/tactics/enterprise/: "Tactics represent the "why" of an ATT&CK
    technique or sub-technique."
  - ATT&CK techniques, https://attack.mitre.org/techniques/enterprise/: "Techniques represent 'how' an
    adversary achieves a tactical goal by performing an action." (The same page lists 227 techniques
    and 479 sub-techniques.)
  - iocextract (defanging), CVSS spec and CISA KEV as above; ATT&CK v20 updates for "Hallucinations
    blocked".
  - **UNVERIFIED:** CVE Program overview, https://www.cve.org/About/Overview (JavaScript only). The NIST
    definition is used instead.

---

## Phase 4: accuracy scoreboard

### D17. Ground truth from published ATT&CK tables

- **Problem:** `backend/app/eval/ground_truth/` held no answer keys, so `/api/eval` returned 404 and the
  scoreboard had nothing to show.
- **Fix:** Five answer keys. Four CISA joint advisories whose pages carry Enterprise ATT&CK technique
  tables: AA26-293A #StopRansomware: SafePay (23 techniques), AA26-281A PRC-linked actors (15),
  AA26-222A #StopRansomware: Gunra (36), AA26-204A Russian Zimbra phishing (36). Every table ID exists
  in v20; none dropped. The fifth is the CVE-2024-4577 test report, scored against its own Appendix A
  (35 techniques), with the appendix removed from the input. Its T1070.001 is revoked in v20 and was
  replaced by its successor T1685.005 "Clear Windows Event Logs" via the ATT&CK revocation data.
  Skipped: AA26-237A (a red-team exercise, not an intrusion) and AA26-194A (mostly hardening advice).
- **Files changed:** `backend/app/eval/ground_truth/*.json` (new), `.../README.md`,
  `backend/app/eval/samples/php_cgi_no_appendix.txt` (new).
- **Sources:** the advisories themselves:
  https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-293a,
  https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-281a,
  https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-222a,
  https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-204a
- **Why they support the fix:** CISA publishes these tables as its own mapping of each intrusion, so
  they are an answer key we did not write.

### D18. Leakage removal by section, plus two bugs found by the dry run

- **Problem:** The leakage rule only dropped short lines containing an ID. A new `--dry-run` mode
  (ingest and strip, no LLM) then exposed two real bugs:
  1. **URL ingestion crashed.** The Firecrawl SDK now returns a metadata object, and `ingest.py`
     called `.get()` on it. Every analysis started from a URL failed.
  2. **"https" counted as a reference heading.** The heading pattern matched "ttps" inside "https", so on
     AA26-204A two 13,000-character spans starting at a "Visit https://…" line were cut as reference
     sections. The same pattern drives the live behaviour filter (D10), so behaviours after such a line
     were being dropped.
- **Fix:** `strip_leakage` first cuts whole ATT&CK/appendix/reference sections, then drops ID lines and
  deletes remaining IDs; `run_eval.py` refuses to score if any ID survives. Firecrawl metadata is
  converted to a dict. The heading pattern matches whole words only. The run records the leakage rule,
  both methods and each answer key in the saved result, and `/eval` shows them with each source link
  and the run date.
- **Files changed:** `backend/app/eval/metrics.py`, `backend/scripts/run_eval.py`,
  `backend/app/pipeline/ingest.py`, `backend/app/utils/sections.py`,
  `frontend/components/eval/ScoreboardPage.tsx`, `frontend/lib/types.ts`.
- **Result of the dry run:** all five inputs ingested; characters before → after removal: PHP 14,791 →
  13,959; AA26-281A 136,971 → 133,084; AA26-204A 71,583 → 62,821; AA26-222A 50,662 → 40,303;
  AA26-293A 44,458 → 38,043. No technique or tactic ID left in any input.
- **Not run:** the scored run needs more LLM quota than the hackathon key allows (D13). The baseline's
  single call over AA26-281A (about 38,000 tokens) exceeds the key's 8,000 tokens-per-minute limit on
  its own, so it would be rejected however long we wait.
- **Source:** CISA ATT&CK mapping guide (D10), for why tables must not count as evidence.

---

## Phase 6: README truth pass

### D19. README claims checked against the code

- **Problems found:** the README claimed analysis "in under a minute" (runs on this key took minutes;
  D13), predictions from the "MITRE CTID Technique Inference Engine" (`tie.py` is a co-occurrence model
  and says so), D3FEND countermeasures (the simulator returns ATT&CK mitigations only), Sigma → KQL (only
  Splunk SPL conversion exists), a `pdf` export endpoint (the PDF is the browser print view), `npm test`
  (no such script), `docker compose up` starting the app (compose starts backend and database only), a
  hero GIF and LICENSE file that did not exist, and empty demo links.
- **Fix:** rewrote the README from verified behaviour; eval table says "not run" with the reason;
  added Limitations, Sources & methodology, correct setup, credits for ATT&CK, NVD, CISA KEV and DB-IP
  (optional); added the Apache-2.0 `LICENSE` (official text from https://www.apache.org/licenses/LICENSE-2.0.txt);
  added production-build screenshots in `docs/assets/`. `frontend/next.config.ts` accepts
  `NEXT_DIST_DIR` so a production build can run beside the dev server.
- **Also fixed while taking screenshots:** a finished analysis loaded from the database showed every
  stage as done, including stages added after it was made ("16/14 done"), and its briefing card claimed
  "no technique was proven". Stages without a recorded timing now show as skipped, the total comes from
  the stage list, and the card says the analysis predates briefings.

---

## Checklist pass

### D20. A final guard for the golden rule

- **Problem:** Checking every stored analysis against the acceptance rule "every accepted technique: ID
  exists in v20, `text[start:end] == evidence.quote`" found 16 failures, all in two smoke-test analyses
  from 30 Oct 13:44–13:47 (`848f99c4176c`, `5942ab4b26a6`). Their accepted techniques carry the bundled
  sample report's quotes and offsets, which are not in their text. The current verifier rechecks every
  quote, so this was older code, but the rule should not depend on any one stage being bug-free.
- **Fix:** `enforce_golden_rule()` re-checks every accepted technique and demotes failures to rejected
  (`id_not_in_v20` or `quote_not_in_source`). It runs at the end of every pipeline run and on every read
  of an analysis (which also covers exports), so old stored data is corrected on the way out. After the
  fix: 0 failing accepted techniques; the PHP analysis keeps all 20.
- **Files changed:** `backend/app/pipeline/verify.py`, `backend/app/pipeline/graph.py`,
  `backend/app/api/routes.py`.
- **Source:** ATT&CK v20 (attack_v20) and the CISA mapping guide, as for the verifier's own checks.

---

## Two LLM providers

### D21. Gemini for the extract slot, Groq for the verify slot

- **Problem:** With one Groq key on the on-demand tier, every LLM call in the pipeline shared one budget
  of 8,000 tokens per minute and 200,000 per day (D13). One analysis took many minutes, the daily quota
  ran out during testing, and the eval could not run: the baseline's single call over the longest
  advisory is bigger than the per-minute limit on its own (D18).
- **Fix:** Two providers at once, each with its own key and its own limits.
  - The **extract** slot (behaviour agent, Sigma behaviour rules, eval baseline) uses Gemini; the
    **verify** slot (verifier, IOC role agent, guard classifier, briefing) uses Groq. The models are set
    in `.env` (`LLM_EXTRACT_MODEL`, `LLM_VERIFY_MODEL`); the code reads the provider from the prefix.
  - The key is chosen by that prefix (`gemini/` → `GEMINI_API_KEY`, `groq/` → `GROQ_API_KEY`, anything
    else → `LLM_API_KEY`) and passed explicitly to LiteLLM. Keys are never logged; error text is
    trimmed and stripped of org IDs and anything key-like before it is logged or shown.
  - One token bucket **per provider** (`LLM_TPM_GEMINI`, `LLM_TPM_GROQ`; empty = no pacing), so a slow
    Groq budget never holds up Gemini calls and vice versa.
  - "Request too large" still fails at once so the caller can split the batch (D13). A **daily** quota
    error (Groq "TPD"/"RPD", Gemini "per day") now also fails at once instead of retrying for minutes,
    since waiting a minute cannot help. Per-minute 429s still back off, using the provider's own wait
    (Groq "try again in Ns", Gemini "retryDelay").
  - **No silent fallback.** A failed call names the provider, model and reason, and the stage event
    carries it (`llm_errors`), e.g. "gemini: daily quota exhausted for … this call failed and was not
    sent to another provider".
  - JSON mode is requested when LiteLLM reports `response_format` support for the model, as before, with
    the JSON-only instruction and robust parsing as the fallback. Temperature 0. The cache key already
    includes the model name, so answers from different models never mix.
  - Each call logs provider, model, slot, tokens in/out, latency and any rate-limit wait.
  - The eval run records both models and providers, and lists any report it had to skip (with the
    reason) instead of scoring it partially. `/eval` shows both.
- **Files changed:** `backend/app/config.py`, `backend/app/llm.py`, `backend/app/main.py` (app log
  output), `backend/app/pipeline/graph.py` (`llm_errors` in stage events), `backend/app/pipeline/sigma.py`,
  `backend/app/pipeline/verify.py`, `backend/scripts/run_eval.py`, `.env.example`,
  `frontend/components/eval/ScoreboardPage.tsx`, `frontend/lib/types.ts`.
- **Found while switching:** `gemini/gemini-2.5-flash` returned "This model models/gemini-2.5-flash is
  no longer available to new users", so the extract slot uses `gemini/gemini-3.1-flash-lite` (set in
  `.env`).
- **Sources:**
  - Groq, Rate Limits, https://console.groq.com/docs/rate-limits: lists `openai/gpt-oss-120b` and
    `openai/gpt-oss-20b` at "30 1K 8K 200K" (requests/minute, requests/day, tokens/minute, tokens/day) on
    this tier, and states "Rate limits apply at the organization level, not individual users."
  - Google, Gemini API rate limits, https://ai.google.dev/gemini-api/docs/rate-limits: "Rate limits are
    applied per project, not per API key", measured as requests per minute, input tokens per minute and
    requests per day, with active limits shown in AI Studio.
- **Why they support the fix:** Both providers limit per organisation or project, not per key, so a second
  key at the same provider would not have helped; a second provider has its own separate budget. Giving
  each provider its own bucket and key follows directly from that.

- **Measured on the switch (31 Oct):**
  - Tiny call per slot: extract `gemini/gemini-3.1-flash-lite` 8,666 ms; verify `groq/openai/gpt-oss-20b` 4,525 ms.
  - No-appendix PHP report, cache off (`74660bd1f828`): 793 s wall clock. Stages: verify 653.8 s,
    ioc_role 73.7 s, brief 34.8 s, vulns 13.1 s, guard 11.0 s, detect 10.8 s, behaviours 8.7 s (Gemini),
    memory 5.5 s, retrieve 3.2 s, everything else under 0.5 s. 29 behaviours; 14 accepted, 50 rejected
    (49 verifier_mismatch, 1 low_confidence); T1003.001 accepted with "The actor ran Mimikatz to dump
    plaintext passwords and NTLM hashes from LSASS memory."
- **Problems this run exposed, and fixes:**
  - Groq's server-side JSON mode rejected 10 of the verifier's answers (`json_validate_failed`), so 10
    behaviours went unverified. Now such a call is retried once on the same model without the provider's
    JSON mode; the prompt still asks for JSON only and the parser is tolerant.
  - A Gemini "503 Service Unavailable" failed at once; temporary outages now back off and retry on the
    same provider.
  - The first eval attempt exhausted Groq's daily quota (200,000 tokens/day) during the first report.
    The PHP report would have been scored with 5 failed verifier calls, so `run_eval.py` now skips any
    report whose pipeline logged a failed LLM call. Nothing was saved from that attempt.
  - The briefing wrote two indicators back in live form; code now rewrites every known indicator to its
    defanged form and drops any step or action naming an IP that isn't a kept indicator.
  - Added a per-provider requests-per-minute limiter (`LLM_RPM_GEMINI`, `LLM_RPM_GROQ`) next to the token
    bucket; Groq's page lists 30 requests/minute for these models.

---

## Reading text in report images

### D22. OCR of report images, with indicators from images flagged

- **Problem:** Threat reports often put indicators, commands and log excerpts in screenshots and
  figures, and some PDFs are scans with no text layer. Ingestion dropped every image, so that content
  never reached the pipeline.
- **Fix:** OCR with Tesseract (`pytesseract` + Pillow), no LLM, behind `OCR_ENABLED` (default true).
  - **URL reports:** image links in the scraped page (`![alt](src)` and `<img>`), resolved against the
    report URL. Only http(s) images on the report's own registrable domain or a subdomain of it (e.g. a
    static/CDN host of the same site); no SVGs, no icon/logo/badge file names, no bare-IP hosts, no inline
    images Firecrawl removed; at most 8, each at most 5 MB, `image/*` only, 10 s timeout, no redirects.
    **Never fetched:** any URL or host that the report itself lists as an indicator. Indicators are
    extracted from the page text first, so we never contact attacker infrastructure.
  - **PDF uploads:** embedded images (same limits, images under 200 px skipped) and any page with almost
    no text layer (under 50 characters) are rendered with pdfplumber and OCR'd.
  - Each image is converted to grayscale, upscaled ×2 when small, then read with
    `image_to_string(lang="eng", config="--psm 6")`. Images with fewer than 20 letters or digits are
    dropped; images under 200 px on a side are treated as icons.
  - Kept text is appended to the report **before normalisation** as
    `[Image N text (OCR) — source: <image URL or PDF page N>]`, so every evidence offset stays valid and
    quotes from images are visibly labelled. `ReportAnalysis.images` records index, source, characters,
    whether it was used, and the block's offsets; the ingest stage sends one progress event per image.
  - **Trust rules:** an indicator whose every evidence span lies inside an OCR block gets
    `from_ocr=true`, extraction confidence ×0.6, and the badge "From image (OCR) — verify". A hash that
    OCR split into pieces (hex groups that only join up to a hash length) is listed but dropped as
    `ocr_unreliable`, so the analyst sees it and checks the image rather than trusting or losing it.
    Evidence highlights inside OCR blocks say "Text read from image (OCR)".
  - If Tesseract is missing, OCR is off, or OCR fails, ingestion continues and the header says
    "Images not read (<reason>)". Otherwise it says "Read text from N images" with an expandable list of
    sources.
- **Tested (no LLM):** a scanned one-page PDF was OCR'd into a labelled block at offsets 0–225, and the
  IP read from it was flagged with extraction confidence 0.54. A hash OCR split as "9f86d08 1884c…" was
  listed as `ocr_unreliable`. With OCR turned off, or Tesseract missing, ingestion continued with the
  reason recorded. The image-URL filter kept only same-site and same-site-CDN images and skipped a logo,
  an SVG, an outside domain, an indicator host and a bare IP. A real CISA advisory had only icons and
  logos, so nothing was fetched; fetching and reading Tesseract's own sample image over the network
  worked.
- **Files changed:** `backend/app/pipeline/ocr.py` (new), `backend/app/pipeline/ingest.py`,
  `backend/app/pipeline/graph.py`, `backend/app/models.py` (`ImageInfo`, `IOC.from_ocr`,
  `ReportAnalysis.images`, `ocr_status`), `backend/app/config.py`, `backend/app/sources.py` (source +
  `ocr_unreliable` rule), `backend/requirements.txt`, `backend/Dockerfile` (`tesseract-ocr`),
  `frontend/app/report/[id]/page.tsx`, `frontend/components/ioc-table/IocTable.tsx`,
  `frontend/components/report-viewer/ReportViewer.tsx`, `frontend/app/how-it-works/page.tsx`,
  `frontend/lib/types.ts`, `frontend/lib/store.ts`.
- **Not done:** the brief named `deploy/hf-space/Dockerfile`, which does not exist in this repository.
- **Source:** Tesseract Open Source OCR Engine, https://github.com/tesseract-ocr/tesseract (page title
  "Tesseract Open Source OCR Engine (main repository)").
- **Why it supports the fix:** It is the engine we use. OCR output can misread characters (in our own
  test it split a 64-character hash into three pieces), which is why indicators read only from images
  are flagged and malformed hashes are dropped instead of being treated like text from the report.


### D21 update. Verify slot moved to Gemini

- **Problem:** With the verify slot on Groq's free on-demand tier (8,000 tokens per minute, 200,000 per
  day for `openai/gpt-oss-20b`), one uncached analysis of the 14,800-character test report took 793 s
  (about 13 minutes; the verifier alone 654 s, mostly waiting for Groq's per-minute budget), and the
  first eval attempt exhausted Groq's daily quota partway through its first report (D21).
- **Fix:** Both slots now use `gemini/gemini-3.1-flash-lite` (`.env.example`: `LLM_RPM_GEMINI=14`,
  `LLM_TPM_GEMINI=225000`). Groq support stays as optional configuration only: set a slot to a `groq/...`
  model and `GROQ_API_KEY` (and `LLM_RPM_GROQ=30`, `LLM_TPM_GROQ=8000`) to use it. There is still no
  automatic fallback between providers.
- **Sources:** as in D21 (Groq and Google rate-limit pages).

### D23. T1190 (initial access) was being mapped as T1210 (lateral movement)

- **Problem:** On the test report, the sentence about the exploit request to `php-cgi.exe` was accepted as
  T1210 Exploitation of Remote Services, and T1190 Exploit Public-Facing Application was not accepted
  at all. The briefing then described the break-in as "Lateral Movement".
- **Fix (threshold unchanged):**
  - Verifier prompt: "Exploiting a vulnerability in an internet-facing server or web application to gain
    initial access is T1190 (Exploit Public-Facing Application). T1210 (Exploitation of Remote Services)
    is exploiting a service on an internal system to move laterally after access."
  - Retriever: when a behaviour mentions exploiting a CVE or vulnerability, or an exploit request,
    against a web server, web application, php-cgi or a public-facing/internet-facing system, T1190 is
    added as a candidate hint. The verifier still decides. Checked: the hint fires on "A second actor sent
    exploit requests to /hello.world…" and "The attackers exploited the PHP-CGI flaw…", and not on
    "They exploited SMB on internal hosts to move laterally" or the LSASS sentence.
  - The retry after unparseable JSON now drops the provider's JSON mode for every provider (it was only
    triggered by Groq's own `json_validate_failed` error), so it also covers Gemini.
- **Files changed:** `backend/app/pipeline/verify.py`, `backend/app/pipeline/retrieve.py`, `backend/app/llm.py`.
- **Sources:**
  - ATT&CK T1190, https://attack.mitre.org/techniques/T1190/: "Adversaries may attempt to exploit a weakness
    in an Internet-facing host or system to initially access a network. The weakness in the system can be
    a software bug, a temporary glitch, or a misconfiguration. Exploited applications are often
    websites/web servers…"
  - ATT&CK T1210, https://attack.mitre.org/techniques/T1210/: "Adversaries may exploit remote services to
    gain unauthorized access to internal systems once inside of a network. … A common goal for
    post-compromise exploitation of remote services is for lateral movement…"
- **Why they support the fix:** MITRE's own definitions separate the two by where and when: an
  Internet-facing system for initial access (T1190) versus internal systems after access (T1210). The
  prompt line restates exactly that distinction.
