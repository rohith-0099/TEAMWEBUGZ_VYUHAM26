// Plain-English briefing: the attack in order, then what to do now. Owner: Frontend A.
// Every step is backed by accepted techniques; "See proof" jumps to the quote in the report.
"use client";

import { ArrowRight, Download, ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { GlossaryHint } from "@/components/ui/glossary-hint";
import { useSources } from "@/lib/sources";
import { useAnalysisStore } from "@/lib/store";
import { useTactics } from "@/lib/tactics";
import type { BriefingAction, IOC } from "@/lib/types";

const PRIORITY_STYLE: Record<BriefingAction["priority"], string> = {
  urgent: "border-destructive/60 bg-destructive/15 text-destructive",
  high: "border-warning/60 bg-warning/15 text-warning",
  normal: "border-border bg-muted/30 text-muted-foreground",
};

const NETWORK_TYPES = new Set<IOC["type"]>(["ipv4", "ipv6", "domain", "url"]);

export function BriefingCard({ onSeeProof }: { onSeeProof: (start: number) => void }) {
  const briefing = useAnalysisStore((s) => s.analysis.briefing);
  const techniques = useAnalysisStore((s) => s.analysis.techniques);
  const iocs = useAnalysisStore((s) => s.analysis.iocs);
  const briefStage = useAnalysisStore((s) => s.stages.brief);
  const select = useAnalysisStore((s) => s.select);
  const { getColor, getName } = useTactics();
  const { source } = useSources();

  const firstEvidence = useMemo(() => {
    const map: Record<string, number> = {};
    for (const t of techniques ?? []) {
      if (t.status === "accepted" && t.evidence && !(t.technique_id in map)) map[t.technique_id] = t.evidence.start;
    }
    return map;
  }, [techniques]);

  // Kept (non-filtered) network indicators, refanged, one per line.
  const blockList = useMemo(
    () => (iocs ?? []).filter((i) => !i.filtered_reason && NETWORK_TYPES.has(i.type)).map((i) => i.value),
    [iocs],
  );

  const downloadBlockList = () => {
    const blob = new Blob([blockList.join("\n") + "\n"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trinetra-blocklist.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!briefing) {
    const running = briefStage?.status === "started";
    const failed = briefStage?.status === "error";
    return (
      <section className="rounded-[20px] border bg-card p-5 text-sm text-muted-foreground">
        <h2 className="console-title mb-2">Briefing</h2>
        {running
          ? "Writing the briefing from the verified findings…"
          : failed
            ? "The briefing couldn't be written this time (the AI service didn't respond). Everything below is still verified."
            : briefStage?.status === "skipped"
              ? "This analysis was made before briefings were added. Analyse the report again to get one."
            : briefStage?.status === "done"
              ? "No briefing: no technique was proven with a quote from this report."
              : "The briefing appears when the analysis finishes."}
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-5 rounded-[20px] border bg-card p-5">
      <div className="flex flex-col gap-1">
        <h2 className="console-title">Briefing</h2>
        <p className="text-xs text-muted-foreground">
          Written only from verified findings. Every step links to the sentence in the report that proves it.
        </p>
      </div>

      {briefing.steps.length > 0 && (
        <ol className="flex flex-col gap-3">
          {briefing.steps.map((step, i) => {
            const proof = step.technique_ids.find((t) => t in firstEvidence);
            return (
              <li key={i} className="flex gap-3">
                <span className="mt-0.5 font-mono text-xs text-muted-foreground">{i + 1}.</span>
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: getColor(step.tactic) }}
                          aria-hidden />
                    <span className="text-sm font-semibold">{step.title}</span>
                    <span className="text-[11px] text-muted-foreground">{getName(step.tactic)}</span>
                  </div>
                  <p className="text-sm text-foreground/90">{step.text}</p>
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="font-mono text-muted-foreground">{step.technique_ids.join(", ")}</span>
                    {proof && (
                      <button
                        type="button"
                        onClick={() => {
                          select(proof);
                          onSeeProof(firstEvidence[proof]);
                        }}
                        className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                      >
                        See proof <ArrowRight className="size-3" />
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {briefing.actions.length > 0 && (
        <div className="flex flex-col gap-3 border-t pt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">What to do now</h3>
            {blockList.length > 0 && (
              <button
                type="button"
                onClick={downloadBlockList}
                className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs hover:bg-muted/40"
              >
                <Download className="size-3.5" /> Download block list ({blockList.length})
              </button>
            )}
          </div>
          <ul className="flex flex-col gap-2">
            {briefing.actions.map((action, i) => {
              const s = source(action.source_key);
              return (
                <li key={i} className="flex flex-col gap-1 rounded-lg border p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${PRIORITY_STYLE[action.priority]}`}>
                      {action.priority}
                    </span>
                    <span className="text-[10px] uppercase text-muted-foreground">{action.kind}</span>
                  </div>
                  <p>{action.text}</p>
                  <span className="text-[11px] text-muted-foreground">
                    {s ? (
                      <a href={s.url} target="_blank" rel="noopener noreferrer"
                         className="inline-flex items-center gap-1 text-primary hover:underline">
                        Source: {s.title} <ExternalLink className="size-3" aria-hidden />
                      </a>
                    ) : (
                      "Based on the indicators in this report"
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
          {blockList.length > 0 && (
            <p className="text-[11px] text-muted-foreground">
              The block list holds the report&apos;s IPs, domains and URLs that passed every filter, refanged
              (<GlossaryHint term="defanged" />) so firewalls can read them. Review it before you load it.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
