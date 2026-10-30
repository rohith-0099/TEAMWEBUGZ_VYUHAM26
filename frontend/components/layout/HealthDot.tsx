// Backend health indicator — green when /api/health.ok. Owner: Frontend A.
"use client";

import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

export function HealthDot() {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  const ok = !isError && data?.ok;

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2 py-1 text-xs text-muted-foreground"
      title={ok ? "Backend healthy" : "Backend unreachable"}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          ok ? "bg-success glow-primary" : "bg-danger glow-danger",
        )}
        aria-hidden="true"
      />
      <span className="font-mono">{ok ? "online" : "offline"}</span>
    </span>
  );
}
