"use client";

import { useMemo, useRef } from "react";
import {
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  Eye,
  FileText,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAnalysisStore } from "@/lib/store";
import { useTactics } from "@/lib/tactics";
import type { TechniqueMatch } from "@/lib/types";

interface SpanMeta {
  technique?: TechniqueMatch;
  isIoc?: boolean;
  iocRole?: string;
  isInjection?: boolean;
}

interface Segment {
  start: number;
  end: number;
  text: string;
  meta: SpanMeta;
}

export function ReportViewer() {
  const analysis = useAnalysisStore((state) => state.analysis);
  const selectedTechniqueId = useAnalysisStore((state) => state.selectedTechniqueId);
  const selectTechnique = useAnalysisStore((state) => state.select);

  const { getColor, getName } = useTactics();
  const textRef = useRef<HTMLDivElement>(null);

  const reportText = analysis.text || "";
  const techniques = analysis.techniques || [];
  const iocs = analysis.iocs || [];
  const injectionFlags = analysis.injection_flags || [];
  const behaviourSummary = useMemo(() => {
    const map: Record<string, string> = {};
    for (const b of analysis.behaviours || []) map[b.id] = b.summary;
    return map;
  }, [analysis.behaviours]);

  // "This sentence shows the attacker <action> (stage: <tactic>, code <id>)". The action is the
  // behaviour agent's summary of this very quote; the technique name is the fallback.
  const ocrSpans = useMemo(
    () => (analysis.images || []).filter((i) => i.used && i.start !== null && i.end !== null) as
      { start: number; end: number }[],
    [analysis.images],
  );
  const fromImage = (start: number) => ocrSpans.some((s) => start >= s.start && start < s.end);

  const explain = (t: TechniqueMatch): string => {
    const summary = (t.behaviour_id && behaviourSummary[t.behaviour_id]) || "";
    const action = summary
      ? summary.charAt(0).toLowerCase() + summary.slice(1).replace(/\.$/, "")
      : `used ${t.name}`;
    return `This sentence shows the attacker ${action.replace(/^the attacker /i, "")} ` +
      `(stage: ${getName(t.tactics[0] ?? "")}, code ${t.technique_id})`;
  };

  const selectedTechnique = useMemo(() => {
    return techniques.find((t) => t.technique_id === selectedTechniqueId) || techniques[0];
  }, [techniques, selectedTechniqueId]);

  // Compute segmented text with overlapping boundaries
  const segments: Segment[] = useMemo(() => {
    if (!reportText) return [];

    const boundaries = new Set<number>([0, reportText.length]);

    for (const tech of techniques) {
      if (tech.status === "accepted" && tech.evidence) {
        if (tech.evidence.start >= 0 && tech.evidence.end <= reportText.length) {
          boundaries.add(tech.evidence.start);
          boundaries.add(tech.evidence.end);
        }
      }
    }

    for (const ioc of iocs) {
      for (const ev of ioc.evidence) {
        if (ev.start >= 0 && ev.end <= reportText.length) {
          boundaries.add(ev.start);
          boundaries.add(ev.end);
        }
      }
    }

    for (const inj of injectionFlags) {
      if (inj.evidence && inj.evidence.start >= 0 && inj.evidence.end <= reportText.length) {
        boundaries.add(inj.evidence.start);
        boundaries.add(inj.evidence.end);
      }
    }

    const sorted = Array.from(boundaries).sort((a, b) => a - b);
    const result: Segment[] = [];

    for (let i = 0; i < sorted.length - 1; i++) {
      const start = sorted[i];
      const end = sorted[i + 1];
      if (start >= end) continue;

      const subText = reportText.slice(start, end);
      const meta: SpanMeta = {};

      // Match accepted techniques
      for (const tech of techniques) {
        if (tech.status === "accepted" && tech.evidence) {
          if (start >= tech.evidence.start && end <= tech.evidence.end) {
            meta.technique = tech;
            break;
          }
        }
      }

      // Match IOCs
      for (const ioc of iocs) {
        for (const ev of ioc.evidence) {
          if (start >= ev.start && end <= ev.end) {
            meta.isIoc = true;
            meta.iocRole = ioc.role;
            break;
          }
        }
        if (meta.isIoc) break;
      }

      // Match Injections
      for (const inj of injectionFlags) {
        if (inj.evidence && start >= inj.evidence.start && end <= inj.evidence.end) {
          meta.isInjection = true;
          break;
        }
      }

      result.push({ start, end, text: subText, meta });
    }

    return result;
  }, [reportText, techniques, iocs, injectionFlags]);

  const jumpToSpan = (start: number) => {
    const el = document.getElementById(`span-${start}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring-2", "ring-primary", "scale-105");
      setTimeout(() => {
        el.classList.remove("ring-2", "ring-primary", "scale-105");
      }, 1500);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-10">
      {/* 60% Left: Highlighted Ground-Truth Document */}
      <div className="flex flex-col gap-3 lg:col-span-6">
        <div className="flex items-center justify-between border-b pb-2">
          <div className="flex items-center gap-2">
            <FileText className="size-4 text-primary" />
            <h3 className="font-heading text-sm font-semibold tracking-tight">
              Report Ground-Truth Evidence
            </h3>
            <span className="font-mono text-xs text-muted-foreground">
              ({reportText.length} characters)
            </span>
          </div>

          <div className="flex items-center gap-3 text-[11px] font-mono text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-primary" /> Technique
            </span>
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full border border-dashed border-observed/40" /> IOC
            </span>
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-destructive" /> Injected
            </span>
          </div>
        </div>

        <div
          ref={textRef}
          className="rounded-[20px] border bg-card p-5 font-mono text-xs leading-relaxed text-foreground/90 whitespace-pre-wrap selection:bg-primary/30"
        >
          {segments.map((seg, idx) => {
            const isTech = Boolean(seg.meta.technique);
            const isSelected = seg.meta.technique?.technique_id === selectedTechniqueId;
            const tacticColor = isTech ? getColor(seg.meta.technique!.tactics[0] || 0) : undefined;

            return (
              <span
                key={idx}
                id={`span-${seg.start}`}
                onClick={() => {
                  if (seg.meta.technique) {
                    selectTechnique(seg.meta.technique.technique_id);
                  }
                }}
                className={`transition-all duration-200 ${
                  isTech
                    ? "cursor-pointer rounded px-0.5 py-0.2 font-medium hover:brightness-125"
                    : ""
                } ${
                  isSelected
                    ? "ring-1 ring-primary brightness-110"
                    : ""
                } ${
                  seg.meta.isIoc
                    ? "border-b border-dotted border-observed/40 text-observed"
                    : ""
                } ${
                  seg.meta.isInjection
                    ? "border-b-2 border-wavy border-destructive text-destructive"
                    : ""
                }`}
                style={
                  isTech
                    ? {
                        backgroundColor: `${tacticColor}25`,
                        borderBottom: `2px solid ${tacticColor}`,
                      }
                    : undefined
                }
                title={
                  seg.meta.technique
                    ? (fromImage(seg.start) ? "Text read from image (OCR). " : "") + explain(seg.meta.technique)
                    : seg.meta.isIoc
                    ? (fromImage(seg.start) ? "Text read from image (OCR). " : "") + `Indicator in role: ${seg.meta.iocRole}`
                    : seg.meta.isInjection
                    ? "Adversarial prompt-injection string"
                    : undefined
                }
              >
                {seg.meta.isInjection && (
                  <AlertTriangle className="mr-0.5 inline-block size-3 text-destructive" />
                )}
                {seg.text}
              </span>
            );
          })}
        </div>
      </div>

      {/* 40% Right: Selected Technique & Evidence Inspector */}
      <div className="flex flex-col gap-3 lg:col-span-4">
        <div className="flex items-center justify-between border-b pb-2">
          <div className="flex items-center gap-2">
            <Eye className="size-4 text-primary" />
            <h3 className="font-heading text-sm font-semibold tracking-tight">
              Evidence Inspector
            </h3>
          </div>
          <Badge variant="outline" className="font-mono text-xs">
            {techniques.filter((t) => t.status === "accepted").length} verified
          </Badge>
        </div>

        {selectedTechnique ? (
          <div className="sticky top-20 flex flex-col gap-4 rounded-[20px] border bg-card p-4">
            <div className="flex items-start justify-between gap-2 border-b pb-3">
              <div className="flex flex-col gap-1">
                <span className="font-mono text-sm font-bold text-primary">
                  {selectedTechnique.technique_id}
                </span>
                <h4 className="font-heading text-sm font-semibold text-foreground">
                  {selectedTechnique.name}
                </h4>
                <div className="flex flex-wrap gap-1 mt-1">
                  {selectedTechnique.tactics.map((t) => (
                    <Badge key={t} variant="secondary" className="font-mono text-[9px]">
                      {getName(t)}
                    </Badge>
                  ))}
                </div>
              </div>

              {selectedTechnique.url && (
                <a
                  href={selectedTechnique.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md border p-1 text-muted-foreground hover:text-foreground"
                  title="MITRE ATT&CK reference"
                >
                  <ExternalLink className="size-3.5" />
                </a>
              )}
            </div>

            {/* Evidence Quote with Jump Button */}
            {selectedTechnique.evidence && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-semibold text-muted-foreground">
                  Verbatim Source Evidence
                </span>
                <blockquote className="rounded-md border-l-2 border-primary bg-muted/20 p-3 font-mono text-xs italic text-foreground">
                  &ldquo;{selectedTechnique.evidence.quote}&rdquo;
                </blockquote>

                <div className="flex items-center justify-between text-[11px] text-muted-foreground font-mono">
                  <span>
                    Offsets: {selectedTechnique.evidence.start} → {selectedTechnique.evidence.end}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1 text-[11px]"
                    onClick={() => jumpToSpan(selectedTechnique.evidence!.start)}
                  >
                    <span>Jump to Span</span>
                    <ArrowRight className="size-3" />
                  </Button>
                </div>
              </div>
            )}

            {/* Verifier Rationale */}
            {selectedTechnique.rationale && (
              <div className="flex flex-col gap-1.5 border-t pt-3">
                <span className="text-xs font-semibold text-muted-foreground">
                  Verifier Rationale
                </span>
                <p className="text-xs leading-relaxed text-foreground/90">
                  {selectedTechnique.rationale}
                </p>
              </div>
            )}

            {/* Linked Indicators */}
            {selectedTechnique.linked_iocs.length > 0 && (
              <div className="flex flex-col gap-1.5 border-t pt-3">
                <span className="text-xs font-semibold text-muted-foreground">
                  Associated Indicators
                </span>
                <div className="flex flex-wrap gap-1">
                  {selectedTechnique.linked_iocs.map((iocId) => (
                    <Badge key={iocId} variant="outline" className="font-mono text-xs">
                      {iocId}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex h-48 items-center justify-center rounded-[20px] border border-dashed text-xs text-muted-foreground">
            Click any highlighted text to inspect evidence.
          </div>
        )}
      </div>
    </div>
  );
}
