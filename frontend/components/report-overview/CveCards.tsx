// One card per CVE named in the report: NVD and CISA KEV facts, each with its source and date.
"use client";

import { ExternalLink, ShieldAlert } from "lucide-react";
import { GlossaryHint } from "@/components/ui/glossary-hint";
import { useSources } from "@/lib/sources";
import { useAnalysisStore } from "@/lib/store";
import type { VulnInfo } from "@/lib/types";

const SEVERITY_STYLE: Record<string, string> = {
  CRITICAL: "border-destructive/60 bg-destructive/15 text-destructive",
  HIGH: "border-warning/60 bg-warning/15 text-warning",
  MEDIUM: "border-border bg-muted/40 text-foreground",
  LOW: "border-border bg-muted/20 text-muted-foreground",
};

function day(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
}

function CveCard({ v }: { v: VulnInfo }) {
  const { source } = useSources();
  const kev = source("cisa_kev");
  const cvss = source("cvss31");

  return (
    <article className="flex flex-col gap-3 rounded-[20px] border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold">{v.cve_id}</span>
        {v.cvss_score !== null && (
          <span className={`rounded-full border px-2 py-0.5 font-mono text-[11px] font-semibold ${SEVERITY_STYLE[v.cvss_severity ?? ""] ?? SEVERITY_STYLE.LOW}`}>
            CVSS {v.cvss_version} {v.cvss_score.toFixed(1)} · {v.cvss_severity}
          </span>
        )}
        {v.in_kev && (
          <span className="inline-flex items-center gap-1 rounded-full border border-destructive/60 bg-destructive/15 px-2 py-0.5 text-[11px] font-semibold text-destructive">
            <ShieldAlert className="size-3" /> Actively exploited (CISA KEV)
          </span>
        )}
      </div>

      {/* NVD */}
      {v.nvd_status === "ok" ? (
        <div className="flex flex-col gap-2 text-sm">
          {v.description && <p className="text-foreground/90">{v.description}</p>}
          {v.affected.length > 0 && (
            <div className="text-xs">
              <span className="font-semibold">Affected: </span>
              <span className="text-muted-foreground">{v.affected.join("; ")}</span>
            </div>
          )}
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {v.references.length > 0 ? (
              v.references.map((r) => (
                <a key={r.url} href={r.url} target="_blank" rel="noopener noreferrer"
                   className="inline-flex items-center gap-1 text-primary hover:underline">
                  {r.tags.join(" / ")}: {new URL(r.url).hostname} <ExternalLink className="size-3" aria-hidden />
                </a>
              ))
            ) : (
              <span className="text-muted-foreground">NVD lists no patch or vendor-advisory link for this CVE.</span>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground">
            Source:{" "}
            {v.nvd_url && (
              <a href={v.nvd_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                NVD record
              </a>
            )}
            {v.cvss_source && <> · scored by {v.cvss_source}</>} · retrieved {day(v.nvd_retrieved_at)}
            {cvss && (
              <>
                {" · "}
                <a href={cvss.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  CVSS severity bands
                </a>
              </>
            )}
          </p>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          {v.nvd_status === "not_found"
            ? "NVD has no record for this ID."
            : "NVD lookup unavailable right now. Nothing is shown rather than a guess."}
        </p>
      )}

      {/* CISA KEV */}
      {v.kev_status === "ok" ? (
        v.in_kev ? (
          <div className="flex flex-col gap-1 border-t pt-3 text-xs">
            <p><span className="font-semibold">Added to KEV:</span> {v.kev_date_added}</p>
            {v.kev_due_date && <p><span className="font-semibold">CISA due date:</span> {v.kev_due_date}</p>}
            {v.kev_required_action && <p><span className="font-semibold">Required action:</span> {v.kev_required_action}</p>}
            {v.kev_ransomware_use && <p><span className="font-semibold">Known ransomware use:</span> {v.kev_ransomware_use}</p>}
            <p className="text-[11px] text-muted-foreground">
              Source:{" "}
              {kev && <a href={kev.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">CISA KEV</a>}
              {" "}catalog {v.kev_catalog_version} · retrieved {day(v.kev_retrieved_at)}
            </p>
          </div>
        ) : (
          <p className="border-t pt-3 text-[11px] text-muted-foreground">
            Not in the CISA KEV catalog (version {v.kev_catalog_version}, retrieved {day(v.kev_retrieved_at)}).
          </p>
        )
      ) : (
        <p className="border-t pt-3 text-[11px] text-muted-foreground">CISA KEV lookup unavailable right now.</p>
      )}
    </article>
  );
}

export function CveCards() {
  const vulns = useAnalysisStore((s) => s.analysis.vulnerabilities);
  if (!vulns || vulns.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <h2 className="console-title flex items-center gap-2">
        Vulnerabilities <GlossaryHint term="cve" /> <GlossaryHint term="kev" />
      </h2>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {vulns.map((v) => <CveCard key={v.cve_id} v={v} />)}
      </div>
    </section>
  );
}
