// Recent analyses list on the home page. Owner: Frontend A. See team/01_FRONTEND_A.md §4.2.
"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Fingerprint, Loader2, ShieldAlert, Swords } from "lucide-react";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { listAnalyses } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_STYLE = {
  done: { icon: CheckCircle2, className: "text-success", label: "done" },
  running: { icon: Loader2, className: "text-info animate-spin", label: "running" },
  error: { icon: AlertTriangle, className: "text-danger", label: "error" },
} as const;

function sourceDomain(url: string | null): string {
  if (!url) return "pasted text";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function RecentAnalyses() {
  const { data, isLoading } = useQuery({ queryKey: ["analyses", "list"], queryFn: listAnalyses });

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return <p className="text-sm text-muted-foreground">No analyses yet — paste a report above to begin.</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {data.map((a) => {
        const status = STATUS_STYLE[a.status];
        const StatusIcon = status.icon;
        return (
          <li key={a.report_id}>
            <Link
              href={`/report/${a.report_id}`}
              className="group flex items-center gap-4 rounded-xl border border-border bg-card px-4 py-3 transition-colors hover:border-primary/40 hover:bg-raised"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-foreground group-hover:text-primary">{a.title}</p>
                <p className="truncate font-mono text-xs text-muted-foreground">
                  {sourceDomain(a.source_url)} ·{" "}
                  {a.published_at ? new Date(a.published_at).toLocaleDateString() : "undated"}
                </p>
              </div>
              <div className="hidden shrink-0 items-center gap-3 text-xs text-muted-foreground sm:flex">
                <span className="flex items-center gap-1" title="Non-filtered IOCs">
                  <Fingerprint className="size-3.5" aria-hidden="true" /> {a.counts.iocs}
                </span>
                <span className="flex items-center gap-1" title="Accepted techniques">
                  <Swords className="size-3.5" aria-hidden="true" /> {a.counts.techniques}
                </span>
                <span className="flex items-center gap-1" title="Memory alerts">
                  <ShieldAlert className="size-3.5" aria-hidden="true" /> {a.counts.alerts}
                </span>
              </div>
              <span
                className={cn(
                  "flex shrink-0 items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide",
                  status.className,
                )}
              >
                <StatusIcon className="size-3" aria-hidden="true" /> {status.label}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
