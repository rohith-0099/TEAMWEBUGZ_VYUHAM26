// Top navigation bar: search, health status, notifications, profile. Owner: Frontend A.
"use client";

import { Shield } from "lucide-react";
import { HealthDot } from "@/components/layout/HealthDot";
import { NotificationPanel } from "@/components/layout/NotificationPanel";
import { SearchCommandBar } from "@/components/layout/SearchCommandBar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function TopBar() {
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-background/90 px-4 backdrop-blur supports-backdrop-filter:bg-background/70 sm:px-6">
      <SearchCommandBar />

      <div className="ml-auto flex items-center gap-2">
        <span className="hidden items-center gap-1.5 rounded-full border border-border bg-surface px-2 py-1 text-xs text-muted-foreground sm:inline-flex">
          <Shield className="size-3 text-primary" aria-hidden="true" />
          <span className="font-mono">ATT&amp;CK v20</span>
        </span>
        <HealthDot />
        <NotificationPanel />
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <button
                type="button"
                className="flex size-8 items-center justify-center rounded-full border border-border bg-raised text-xs font-semibold text-foreground transition-colors hover:border-primary/40"
                aria-label="User profile"
              />
            }
          >
            AN
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>Analyst</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled>Team WeBugz · demo session</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
