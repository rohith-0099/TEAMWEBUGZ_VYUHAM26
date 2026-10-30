"use client";

import { NeonRadar } from "@/components/charts";
import { useTactics } from "@/lib/tactics";

export function IdleRadar() {
  const { tactics } = useTactics();
  return (
    <div className="aspect-[60/42] w-full">
      <NeonRadar idle points={tactics.map((t) => ({ shortname: t.shortname, name: t.name, ord: t.ord, value: 0 }))} />
    </div>
  );
}
