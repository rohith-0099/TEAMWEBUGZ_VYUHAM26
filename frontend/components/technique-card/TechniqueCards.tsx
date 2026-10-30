"use client";

import { useMemo, useState } from "react";
import {
  AlertOctagon,
  ArrowRight,
  ExternalLink,
  Layers,
  Shield,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { sendFeedback } from "@/lib/api";
import { useAnalysisStore } from "@/lib/store";
import { useTactics } from "@/lib/tactics";
import type { RejectReason, TechniqueMatch } from "@/lib/types";

const REJECT_REASONS: Record<RejectReason, string> = {
  id_not_in_v20: "Hallucinated ID — not in ATT&CK v20",
  quote_not_in_source: "Quote not found in report",
  verifier_mismatch: "Evidence doesn't match technique definition",
  low_confidence: "Below confidence threshold",
  deprecated: "Deprecated in v20 — see migration",
};

interface TechniqueCardsProps {
  techniques?: TechniqueMatch[];
  onSelectTab?: (tab: string) => void;
}

export function TechniqueCards({ techniques: propTechniques, onSelectTab }: TechniqueCardsProps) {
  const storeTechniques = useAnalysisStore((state) => state.analysis.techniques);
  const predictions = useAnalysisStore((state) => state.analysis.predictions) || [];
  const migrations = useAnalysisStore((state) => state.analysis.migrations) || [];
  const selectedTechniqueId = useAnalysisStore((state) => state.selectedTechniqueId);
  const selectTechnique = useAnalysisStore((state) => state.select);
  const analysisId = useAnalysisStore((state) => state.analysis.report_id);

  const { tactics, byShortname, getColor, getName } = useTactics();

  const techniques = propTechniques || storeTechniques || [];

  const [expandedQuotes, setExpandedQuotes] = useState<Record<string, boolean>>({});
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, "accept" | "reject">>({});
  const [showRejected, setShowRejected] = useState(false);

  const accepted = useMemo(() => techniques.filter((t) => t.status === "accepted"), [techniques]);
  const rejected = useMemo(() => techniques.filter((t) => t.status === "rejected"), [techniques]);

  // Group accepted techniques by tactic in matrix order (ord)
  const groupedByTactic = useMemo(() => {
    const map = new Map<string, TechniqueMatch[]>();

    // Initialise ordered groups from tactics list
    for (const tac of tactics) {
      map.set(tac.shortname, []);
    }

    for (const tech of accepted) {
      const primaryTactic = tech.tactics[0] || "other";
      if (!map.has(primaryTactic)) {
        map.set(primaryTactic, []);
      }
      map.get(primaryTactic)!.push(tech);
    }

    return Array.from(map.entries()).filter(([, list]) => list.length > 0);
  }, [accepted, tactics]);

  const handleFeedback = async (techId: string, verdict: "accept" | "reject") => {
    setFeedbackGiven((prev) => ({ ...prev, [techId]: verdict }));
    toast.success(`Feedback recorded: ${verdict === "accept" ? "Accepted technique" : "Rejected candidate"}`);
    if (analysisId) {
      try {
        await sendFeedback(analysisId, {
          target_type: "technique",
          target_id: techId,
          verdict,
        });
      } catch (err) {
        console.warn("Feedback save failed:", err);
      }
    }
  };

  const toggleQuote = (id: string) => {
    setExpandedQuotes((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Migrations Banner */}
      {migrations.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-lg border border-primary/40 bg-primary/10 p-3 text-xs">
          <div className="flex items-center gap-2 font-semibold text-primary">
            <Shield className="size-4" />
            <span>ATT&CK v20 Taxonomy Migrations ({migrations.length})</span>
          </div>
          <div className="space-y-1 text-muted-foreground">
            {migrations.map((m, i) => (
              <p key={i}>
                <span className="font-mono line-through text-destructive">{m.old_id}</span>
                {" → "}
                <span className="font-mono font-semibold text-foreground">{m.new_ids.join(", ")}</span>:{" "}
                {m.reason}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Header and Filter summary */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="size-4 text-primary" />
          <h2 className="font-heading text-sm font-semibold tracking-tight">
            Verified ATT&CK v20 Techniques
          </h2>
          <Badge variant="outline" className="font-mono text-xs">
            {accepted.length} accepted
          </Badge>
        </div>

        {rejected.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowRejected(!showRejected)}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            <AlertOctagon className="mr-1.5 size-3.5 text-destructive" />
            {showRejected ? "Hide" : "Show"} Hallucinations Blocked ({rejected.length})
          </Button>
        )}
      </div>

      {/* Tactic-Grouped Accepted Cards */}
      <div className="flex flex-col gap-4">
        {groupedByTactic.map(([shortname, techs]) => {
          const tacticName = getName(shortname);
          const color = getColor(shortname);

          return (
            <div key={shortname} className="flex flex-col gap-2">
              <div className="flex items-center gap-2 border-b border-border/60 pb-1.5">
                <span
                  className="size-2.5 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <h3 className="font-heading text-xs font-semibold tracking-wide uppercase text-foreground">
                  {tacticName}
                </h3>
                <span className="font-mono text-[11px] text-muted-foreground">
                  ({techs.length})
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2.5">
                {techs.map((tech) => {
                  const isSelected = selectedTechniqueId === tech.technique_id;
                  const mappingConf = tech.confidence.mapping
                    ? Math.round(tech.confidence.mapping * 100)
                    : Math.round(tech.confidence.extraction * 100);
                  const quote = tech.evidence?.quote || "";
                  const isQuoteLong = quote.length > 180;
                  const isExpanded = expandedQuotes[tech.technique_id];
                  const displayQuote = isQuoteLong && !isExpanded ? `${quote.slice(0, 180)}...` : quote;

                  return (
                    <div
                      key={tech.technique_id}
                      onClick={() => selectTechnique(tech.technique_id)}
                      className={`flex flex-col gap-2 rounded-lg border bg-card/70 p-3.5 shadow-sm transition-all hover:border-primary/60 hover:shadow-md ${
                        isSelected
                          ? "border-primary ring-1 ring-primary/50 shadow-[0_0_15px_rgba(34,211,238,0.2)]"
                          : "border-border/60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-primary">
                              {tech.technique_id}
                            </span>
                            <h4 className="font-heading text-xs font-semibold text-foreground">
                              {tech.name}
                            </h4>
                          </div>

                          <div className="flex flex-wrap gap-1 mt-1">
                            {tech.tactics.map((tShort) => (
                              <span
                                key={tShort}
                                className="rounded px-1.5 py-0.5 text-[9px] font-mono uppercase text-muted-foreground bg-muted/30"
                              >
                                {byShortname[tShort]?.name || tShort}
                              </span>
                            ))}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <div
                            className="flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold"
                            style={{ borderColor: color, color }}
                          >
                            <span>{mappingConf}%</span>
                          </div>

                          {tech.url && (
                            <a
                              href={tech.url}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-muted-foreground hover:text-foreground"
                              title="View technique on MITRE ATT&CK"
                            >
                              <ExternalLink className="size-3.5" />
                            </a>
                          )}
                        </div>
                      </div>

                      {/* Verbatim Evidence Quote */}
                      {quote && (
                        <blockquote className="border-l-2 border-primary/50 bg-muted/20 pl-2.5 py-1 text-xs italic text-foreground/90">
                          &ldquo;{displayQuote}&rdquo;
                          {isQuoteLong && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleQuote(tech.technique_id);
                              }}
                              className="ml-1.5 text-primary text-[10px] font-mono not-italic underline"
                            >
                              {isExpanded ? "show less" : "show more"}
                            </button>
                          )}
                        </blockquote>
                      )}

                      {/* Rationale */}
                      {tech.rationale && (
                        <p className="text-[11px] text-muted-foreground">
                          <strong className="text-foreground/80 font-medium">Verifier rationale: </strong>
                          {tech.rationale}
                        </p>
                      )}

                      {/* Footer: Linked IOCs and feedback buttons */}
                      <div className="flex items-center justify-between border-t border-border/40 pt-2 text-xs">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[10px] text-muted-foreground">Linked:</span>
                          {tech.linked_iocs.length > 0 ? (
                            tech.linked_iocs.map((iocId) => (
                              <span
                                key={iocId}
                                className="rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px]"
                              >
                                {iocId}
                              </span>
                            ))
                          ) : (
                            <span className="text-muted-foreground text-[10px]">None directly</span>
                          )}
                        </div>

                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className={`size-6 p-0 ${feedbackGiven[tech.technique_id] === "accept" ? "text-emerald-400 bg-emerald-950/40" : "text-muted-foreground"}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleFeedback(tech.technique_id, "accept");
                            }}
                            title="Accept match (ground truth)"
                          >
                            <ThumbsUp className="size-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className={`size-6 p-0 ${feedbackGiven[tech.technique_id] === "reject" ? "text-destructive bg-destructive/10" : "text-muted-foreground"}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleFeedback(tech.technique_id, "reject");
                            }}
                            title="Reject match (false positive)"
                          >
                            <ThumbsDown className="size-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Rejected / Hallucinations Blocked Section */}
      {showRejected && rejected.length > 0 && (
        <div className="flex flex-col gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertOctagon className="size-4 text-destructive" />
              <h3 className="font-heading text-xs font-semibold uppercase text-destructive">
                Hallucinated / Rejected Candidates Filtered ({rejected.length})
              </h3>
            </div>
            <span className="font-mono text-[10px] text-muted-foreground">
              Guaranteed by Verifier
            </span>
          </div>

          <div className="grid grid-cols-1 gap-2 pt-1">
            {rejected.map((tech) => {
              const reasonText =
                (tech.reject_reason && REJECT_REASONS[tech.reject_reason]) ||
                tech.reject_reason ||
                "Verifier mismatch";

              return (
                <div
                  key={tech.technique_id}
                  className="flex flex-col gap-1 rounded-lg border border-destructive/20 bg-background/50 p-2.5 opacity-80"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold line-through text-destructive">
                        {tech.technique_id}
                      </span>
                      <span className="text-xs text-muted-foreground">{tech.name}</span>
                    </div>
                    <Badge variant="outline" className="border-destructive/60 bg-destructive/10 text-[10px] text-destructive">
                      {reasonText}
                    </Badge>
                  </div>
                  {tech.rationale && (
                    <p className="text-[11px] italic text-muted-foreground">{tech.rationale}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Prediction indicator link */}
      {predictions.length > 0 && onSelectTab && (
        <div className="rounded-lg border border-purple-900/40 bg-purple-950/20 p-3">
          <button
            onClick={() => onSelectTab("flow")}
            className="flex w-full items-center justify-between text-xs text-purple-300 hover:text-purple-200"
          >
            <span className="font-medium">
              ⚡ {predictions.length} Predicted ghost techniques to hunt for
            </span>
            <span className="flex items-center gap-1 font-mono text-[11px]">
              Explore in Attack Flow <ArrowRight className="size-3" />
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
