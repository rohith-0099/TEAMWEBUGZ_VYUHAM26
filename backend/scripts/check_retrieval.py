"""Evaluation script for candidate retrieval recall and MRR."""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models import Behaviour, Evidence
from app.pipeline.retrieve import retrieve_candidates

GOLD_SET = [
    (
        "The malware copies itself to the Startup folder and adds a value under HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.",
        ["T1547.001", "T1547"],
    ),
    (
        "The actors sent spearphishing emails with malicious Word attachments to employees.",
        ["T1566.001", "T1566"],
    ),
    (
        "The loader executes an encoded PowerShell command to download the next stage.",
        ["T1059.001", "T1105", "T1059"],
    ),
    (
        "They dumped credentials from LSASS memory using a renamed procdump binary.",
        ["T1003.001", "T1003"],
    ),
    (
        "The implant beacons to its C2 server over HTTPS every 60 seconds.",
        ["T1071.001", "T1071"],
    ),
    (
        "The threat actor moved laterally using RDP with stolen valid accounts.",
        ["T1021.001", "T1078", "T1021"],
    ),
    (
        "Files on network shares were encrypted and a ransom note was dropped.",
        ["T1486"],
    ),
    (
        "Data was compressed with 7-Zip and uploaded to a cloud storage account.",
        ["T1560.001", "T1567.002", "T1560", "T1567"],
    ),
    (
        "A scheduled task named 'UpdateCheck' runs the payload at every logon.",
        ["T1053.005", "T1053"],
    ),
    (
        "The attackers exploited a vulnerability in the public-facing VPN appliance for initial access.",
        ["T1190"],
    ),
    (
        "Adversaries injected shellcode into svchost.exe using process hollowing.",
        ["T1055.012", "T1055"],
    ),
    (
        "The backdoor captured user keystrokes using a custom keylogging hook.",
        ["T1056.001", "T1056"],
    ),
    (
        "The actor deployed vssadmin.exe delete shadows to inhibit system recovery.",
        ["T1490"],
    ),
    (
        "Threat actors queried the Active Directory using AdFind to discover domain accounts.",
        ["T1087.002", "T1087"],
    ),
    (
        "The malware abused Windows Command Shell cmd.exe to execute internal reconnaissance scripts.",
        ["T1059.003", "T1059"],
    ),
    (
        "The attackers staged stolen sensitive documents in a hidden folder inside C:\\ProgramData.",
        ["T1074.001", "T1074"],
    ),
    (
        "The malware decoded its secondary payload from a base64 encoded string.",
        ["T1140"],
    ),
    (
        "The attacker obtained valid credentials by harvesting password hashes from the SAM registry hive.",
        ["T1003.002", "T1003"],
    ),
    (
        "The adversary set up a proxy connection via SSH tunnels to bypass network egress filtering.",
        ["T1572", "T1090.001", "T1090"],
    ),
    (
        "The malware cleared Windows Event Logs to cover its tracks.",
        ["T1685.005", "T1685", "T1070.001", "T1070"],
    ),
    (
        "The actors established persistence by creating a malicious Windows Service.",
        ["T1543.003", "T1543"],
    ),
    (
        "The implant performed DNS tunneling queries to exfiltrate database records.",
        ["T1071.004", "T1048", "T1071"],
    ),
    (
        "The operators executed WMI queries via wmic.exe to identify installed antivirus software.",
        ["T1047", "T1518.001", "T1518"],
    ),
    (
        "Adversaries brute-forced remote SSH services using a precompiled dictionary list.",
        ["T1110.001", "T1110"],
    ),
    (
        "The malware masqueraded as legitimate Google Chrome update binary chrome_update.exe.",
        ["T1036.005", "T1036"],
    ),
    (
        "The threat actor leveraged PsExec for remote service execution across the domain.",
        ["T1569.002", "T1021.002", "T1569"],
    ),
    (
        "The attacker captured screenshots of the victim desktop at regular intervals.",
        ["T1113"],
    ),
    (
        "The adversary modified the local hosts file to redirect security updates to localhost.",
        ["T1565.001", "T1565"],
    ),
    (
        "The malware collected local network configuration details using ipconfig and arp.",
        ["T1016"],
    ),
    (
        "The threat group performed network share scanning using net view and nbtstat.",
        ["T1135"],
    ),
    (
        "The actors used spearphishing links directing targets to credential harvesting portals.",
        ["T1566.002", "T1566"],
    ),
    (
        "The attackers exfiltrated gigabytes of compressed archive data over an FTP connection.",
        ["T1048.003", "T1048"],
    ),
]


def evaluate() -> None:
    behaviours = [
        Behaviour(
            id=f"b-{i+1}",
            summary=sentence[:80],
            evidence=Evidence(quote=sentence, start=0, end=len(sentence)),
        )
        for i, (sentence, _) in enumerate(GOLD_SET)
    ]

    retrieved = retrieve_candidates(behaviours, k=12)

    hits_5 = 0
    hits_8 = 0
    hits_12 = 0
    reciprocal_ranks = []
    misses = []

    for b, (sentence, expected_ids) in zip(behaviours, GOLD_SET):
        cands = retrieved.get(b.id, [])
        cand_ids = [c.technique_id for c in cands]

        # Check hits
        hit_5 = any(tid in cand_ids[:5] for tid in expected_ids)
        hit_8 = any(tid in cand_ids[:8] for tid in expected_ids)
        hit_12 = any(tid in cand_ids[:12] for tid in expected_ids)

        if hit_5:
            hits_5 += 1
        if hit_8:
            hits_8 += 1
        if hit_12:
            hits_12 += 1
        else:
            misses.append((sentence, expected_ids, cand_ids[:8]))

        # Calculate reciprocal rank
        rank = None
        for r_idx, c_id in enumerate(cand_ids, start=1):
            if c_id in expected_ids:
                rank = r_idx
                break
        reciprocal_ranks.append(1.0 / rank if rank is not None else 0.0)

    n = len(GOLD_SET)
    r5 = hits_5 / n
    r8 = hits_8 / n
    r12 = hits_12 / n
    mrr = sum(reciprocal_ranks) / n

    print("=" * 60)
    print("ATT&CK CANDIDATE RETRIEVAL EVALUATION")
    print("=" * 60)
    print(f"Total gold samples: {n}")
    print(f"Recall@5:           {r5:.3f} ({hits_5}/{n})")
    print(f"Recall@8:           {r8:.3f} ({hits_8}/{n})")
    print(f"Recall@12:          {r12:.3f} ({hits_12}/{n})")
    print(f"MRR:                {mrr:.3f}")
    print("=" * 60)

    if misses:
        print("\nMissed Queries (not in top 12):")
        for sentence, exp, got in misses[:5]:
            print(f"  Sentence: {sentence}")
            print(f"  Expected: {exp}")
            print(f"  Got (top 8): {got}\n")
    else:
        print("\nZero misses! Perfect candidate recall.")


if __name__ == "__main__":
    evaluate()
