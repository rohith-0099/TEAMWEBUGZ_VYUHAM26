"use client";

import { useMemo } from "react";
import { NeonRadar } from "@/components/charts";
import { useAnalysisStore } from "@/lib/store";
import { useTactics } from "@/lib/tactics";

export function useTacticCounts() {
  const techniques = useAnalysisStore((state) => state.analysis.techniques);
  const { tactics, getColor } = useTactics();
  return useMemo(() => {
    const counts: Record<string, Set<string>> = {};
    for (const t of techniques ?? []) {
      if (t.status !== "accepted") continue;
      for (const tactic of t.tactics) (counts[tactic] ??= new Set()).add(t.technique_id);
    }
    return tactics.map((t) => ({
      shortname: t.shortname,
      name: t.name,
      ord: t.ord,
      value: counts[t.shortname]?.size ?? 0,
      color: getColor(t.ord),
    }));
    // getColor only depends on the tactic list
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [techniques, tactics]);
}

export function TacticRadarCard() {
  const points = useTacticCounts();
  const empty = points.every((p) => p.value === 0);
  return (
    <section className="flex min-w-0 flex-col rounded-[20px] border bg-card p-4">
      <h2 className="console-title">Tactic coverage</h2>
      <div className="my-auto aspect-[60/42] w-full">
        {/* key restarts the grow-in once, when the first technique lands */}
        <NeonRadar key={empty ? "idle" : "live"} points={points} idle={empty} />
      </div>
    </section>
  );
}
