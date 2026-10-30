"use client";

import { TileGrid } from "@/components/charts";
import { useTacticCounts } from "./TacticRadarCard";

export function TacticTiles() {
  const points = useTacticCounts();
  const covered = points.filter((p) => p.value > 0).length;
  return (
    <section className="flex min-w-0 flex-col gap-3 rounded-[20px] border bg-card p-4">
      <h2 className="console-title">Tactics</h2>
      <TileGrid
        ariaLabel={`Techniques per tactic. ${covered} of ${points.length} tactics seen.`}
        tiles={points.map((p) => ({ key: p.shortname, label: p.name, value: p.value, color: p.color }))}
      />
    </section>
  );
}
