"use client";

import { useMemo, useState } from "react";
import { LayoutGrid, Sparkles } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAnalysisStore } from "@/lib/store";
import { useTactics } from "@/lib/tactics";
import type { TechniqueMatch } from "@/lib/types";

interface AttackHeatmapProps {
  compact?: boolean;
}

export function AttackHeatmap({ compact = false }: AttackHeatmapProps) {
  const { tactics, getColor } = useTactics();
  const techniques = useAnalysisStore((state) => state.analysis.techniques) || [];
  const predictions = useAnalysisStore((state) => state.analysis.predictions) || [];
  const selectedTechniqueId = useAnalysisStore((state) => state.selectedTechniqueId);
  const selectTechnique = useAnalysisStore((state) => state.select);

  const [showPredicted, setShowPredicted] = useState(false);

  const accepted = useMemo(
    () => techniques.filter((t) => t.status === "accepted"),
    [techniques]
  );

  // Group by tactic shortname
  const matrix = useMemo(() => {
    const map: Record<string, { observed: TechniqueMatch[]; predicted: TechniqueMatch[] }> = {};
    for (const t of tactics) {
      map[t.shortname] = { observed: [], predicted: [] };
    }

    for (const tech of accepted) {
      for (const tac of tech.tactics) {
        if (map[tac]) {
          map[tac].observed.push(tech);
        }
      }
    }

    if (showPredicted) {
      for (const pred of predictions) {
        for (const tac of pred.tactics) {
          if (map[tac]) {
            map[tac].predicted.push(pred);
          }
        }
      }
    }

    return map;
  }, [tactics, accepted, predictions, showPredicted]);

  return (
    <TooltipProvider delay={150}>
      <div className={`flex flex-col gap-3 rounded-xl border bg-card/60 shadow-sm backdrop-blur ${compact ? "p-3" : "p-4"}`}>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2.5">
          <div className="flex items-center gap-2">
            <LayoutGrid className="size-4 text-primary" />
            <h3 className="font-heading text-sm font-semibold tracking-tight">
              ATT&CK v20 Enterprise Heatmap
            </h3>
            <span className="font-mono text-xs text-muted-foreground">
              (15 Tactics)
            </span>
          </div>

          {predictions.length > 0 && (
            <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground hover:text-foreground">
              <input
                type="checkbox"
                checked={showPredicted}
                onChange={(e) => setShowPredicted(e.target.checked)}
                className="size-3.5 rounded border-border text-primary focus:ring-primary"
              />
              <span className="flex items-center gap-1 font-mono text-[11px]">
                <Sparkles className="size-3 text-purple-400" />
                Show Predicted Ghost Techniques ({predictions.length})
              </span>
            </label>
          )}
        </div>

        {/* 15 Tactic Matrix Grid */}
        <div className="overflow-x-auto pb-2">
          <div className="grid min-w-[900px] grid-cols-15 gap-1 text-center">
            {tactics.map((tactic) => {
              const columnData = matrix[tactic.shortname] || { observed: [], predicted: [] };
              const count = columnData.observed.length + (showPredicted ? columnData.predicted.length : 0);
              const headerColor = getColor(tactic.ord);

              return (
                <div key={tactic.shortname} className="flex flex-col gap-1">
                  {/* Column Header */}
                  <div
                    className="flex flex-col items-center justify-center rounded border p-1 text-[10px]"
                    style={{
                      borderColor: `${headerColor}40`,
                      backgroundColor: `${headerColor}10`,
                    }}
                  >
                    <span
                      className="truncate font-heading font-semibold text-[10px] w-full"
                      title={tactic.name}
                    >
                      {tactic.name}
                    </span>
                    <span className="font-mono text-[9px] text-muted-foreground">
                      {count}
                    </span>
                  </div>

                  {/* Technique Cells */}
                  <div className="flex flex-col gap-1 min-h-[70px]">
                    {count === 0 ? (
                      <div className="flex h-14 items-center justify-center rounded border border-dashed border-border/40 text-muted-foreground/40 font-mono text-xs">
                        —
                      </div>
                    ) : (
                      <>
                        {columnData.observed.map((tech) => {
                          const isSelected = selectedTechniqueId === tech.technique_id;
                          const conf = tech.confidence.mapping ?? tech.confidence.extraction ?? 0.8;
                          const alpha = Math.max(0.35, Math.min(0.95, conf));

                          return (
                            <Tooltip key={tech.technique_id}>
                              <TooltipTrigger
                                render={
                                  <button
                                    type="button"
                                    onClick={() => selectTechnique(tech.technique_id)}
                                    className={`rounded border p-1 font-mono text-[9px] font-semibold transition-all hover:scale-105 ${
                                      isSelected
                                        ? "ring-2 ring-primary border-primary shadow-sm"
                                        : "border-border/60"
                                    }`}
                                    style={{
                                      backgroundColor: `color-mix(in oklch, var(--primary) ${Math.round(
                                        alpha * 100
                                      )}%, transparent)`,
                                      color: alpha > 0.6 ? "#080A0A" : "#E6EDF3",
                                    }}
                                  />
                                }
                              >
                                {tech.technique_id}
                              </TooltipTrigger>
                              <TooltipContent side="top" className="max-w-xs text-xs">
                                <p className="font-bold font-mono text-primary">
                                  {tech.technique_id}: {tech.name}
                                </p>
                                <p className="text-[11px] text-muted-foreground font-mono">
                                  Confidence: {Math.round(conf * 100)}%
                                </p>
                                {tech.evidence?.quote && (
                                  <p className="mt-1 italic text-[11px] border-l-2 border-primary/50 pl-1.5">
                                    &ldquo;{tech.evidence.quote.slice(0, 100)}...&rdquo;
                                  </p>
                                )}
                              </TooltipContent>
                            </Tooltip>
                          );
                        })}

                        {columnData.predicted.map((tech) => (
                          <Tooltip key={`pred-${tech.technique_id}`}>
                            <TooltipTrigger
                              render={
                                <div
                                  className="rounded border border-dashed border-purple-500/70 bg-purple-950/40 p-1 font-mono text-[9px] font-medium text-purple-300 opacity-80"
                                />
                              }
                            >
                              {tech.technique_id}
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-xs text-xs">
                              <p className="font-bold font-mono text-purple-400">
                                [PREDICTED] {tech.technique_id}: {tech.name}
                              </p>
                              <p className="text-[11px] text-muted-foreground">
                                Predicted by TIE (hunt for this precursor/follow-on)
                              </p>
                            </TooltipContent>
                          </Tooltip>
                        ))}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
