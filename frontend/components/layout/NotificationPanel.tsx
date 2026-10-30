// Notification center — surfaces real analysis status changes, no fabricated alerts. Owner: Frontend A.
"use client";

import { useQuery } from "@tanstack/react-query";
import { Bell, CheckCircle2, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { listAnalyses } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_ICON = { done: CheckCircle2, running: Loader2, error: XCircle } as const;
const STATUS_COLOR = { done: "text-success", running: "text-info animate-spin", error: "text-danger" } as const;

export function NotificationPanel() {
  const { data: analyses } = useQuery({
    queryKey: ["analyses", "notifications"],
    queryFn: listAnalyses,
    refetchInterval: 15_000,
  });

  const items = (analyses ?? []).slice(0, 6);
  const activeCount = items.filter((a) => a.status === "running").length;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            className="relative flex size-8 items-center justify-center rounded-lg border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-accent hover:text-foreground"
            aria-label="Notifications"
          />
        }
      >
        <Bell className="size-4" aria-hidden="true" />
        {activeCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex size-3.5 items-center justify-center rounded-full bg-primary text-[9px] font-semibold text-primary-foreground">
            {activeCount}
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Recent analyses</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {items.length === 0 && (
          <p className="px-2 py-4 text-center text-sm text-muted-foreground">No analyses yet.</p>
        )}
        {items.map((a) => {
          const Icon = STATUS_ICON[a.status];
          return (
            <DropdownMenuItem key={a.report_id} render={<Link href={`/report/${a.report_id}`} />}>
              <Icon className={cn("size-3.5 shrink-0", STATUS_COLOR[a.status])} aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">{a.title || a.report_id}</span>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
