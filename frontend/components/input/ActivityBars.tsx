"use client";

import { useQuery } from "@tanstack/react-query";
import { StackedBars } from "@/components/charts";
import { listAnalyses } from "@/lib/api";

const SERIES = [
  { key: "iocs", label: "IOCs", color: "#3B6BFF" },
  { key: "techniques", label: "Techniques", color: "#22F0FF" },
  { key: "alerts", label: "Memory alerts", color: "#FFC53D" },
];
const MAX_REPORTS = 8;

export function ActivityBars() {
  const { data } = useQuery({ queryKey: ["analyses", "list"], queryFn: listAnalyses });
  const recent = (data ?? []).slice(0, MAX_REPORTS).reverse();

  if (recent.length === 0) {
    return <p className="rounded-[20px] border bg-card p-4 text-sm text-muted-foreground">Bars appear here after your first report.</p>;
  }
  return (
    <div className="rounded-[20px] border bg-card p-4">
      <StackedBars
        ariaLabel={`IOCs, techniques and memory alerts across the last ${recent.length} reports`}
        series={SERIES}
        bars={recent.map((a, i) => ({
          key: a.report_id,
          label: String(i + 1),
          values: { iocs: a.counts.iocs, techniques: a.counts.techniques, alerts: a.counts.alerts },
        }))}
      />
    </div>
  );
}
