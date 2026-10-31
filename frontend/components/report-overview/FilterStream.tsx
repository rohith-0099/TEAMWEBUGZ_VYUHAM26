"use client";

import { useMemo } from "react";
import { StreamChart } from "@/components/charts";
import { countHallucinations } from "@/lib/hallucinations";
import { useAnalysisStore } from "@/lib/store";

const CHECKPOINTS = [
  { label: "ID exists in v20", reasons: ["id_not_in_v20"], color: "#FF3B5C" },
  { label: "Quote is in the report", reasons: ["quote_not_in_source"], color: "#C92A48" },
  { label: "Not deprecated", reasons: ["deprecated"], color: "#A3243F" },
  { label: "Verifier agrees", reasons: ["verifier_mismatch"], color: "#8F1F35" },
  { label: "Confident enough", reasons: ["low_confidence"], color: "#5F1524" },
];

// Every proposed technique enters on the left. Red bands are what the verifier stopped, and where.
export function FilterStream() {
  const techniques = useAnalysisStore((state) => state.analysis.techniques);
  const stages = useAnalysisStore((state) => state.stages);

  const { streamStages, survivors, hallucinations } = useMemo(() => {
    const all = techniques ?? [];
    return {
      hallucinations: countHallucinations(all),
      survivors: all.filter((t) => t.status === "accepted").length,
      streamStages: CHECKPOINTS.map((c) => ({
        label: c.label,
        color: c.color,
        removed: all.filter((t) => t.status === "rejected" && t.reject_reason && c.reasons.includes(t.reject_reason)).length,
      })),
    };
  }, [techniques]);

  const running = stages.verify?.status === "started" || stages.verify?.status === "progress";
  const verified = stages.verify?.status === "done";
  const progress = verified ? (stages.link?.status === "done" ? 4 : 3) : running ? 1 : 0;
  const finished = stages.pipeline?.status === "done" || (!running && !stages.verify?.status) || stages.verify?.status === "idle";
  const total = survivors + streamStages.reduce((sum, s) => sum + s.removed, 0);

  return (
    <section className="flex min-w-0 flex-col gap-2 rounded-[20px] border bg-card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="console-title">Hallucination filter</h2>
        <p className="text-xs text-muted-foreground">
          {total === 0
            ? "Waiting for the verifier"
            : `${survivors} of ${total} proposed techniques passed every check · ${hallucinations} hallucinations blocked`}
        </p>
      </div>
      <StreamChart
        survivors={survivors}
        stages={streamStages}
        progress={finished ? undefined : progress}
        ariaLabel={`${total} techniques proposed. ${streamStages.map((s) => `${s.label}: ${s.removed} removed`).join(". ")}. ${survivors} accepted.`}
      />
    </section>
  );
}
