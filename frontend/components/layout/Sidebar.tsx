// Collapsible left sidebar — nav reflects the actual routes in this app. Owner: Frontend A.
"use client";

import { Eye, Network, Trophy, PanelLeftClose, PanelLeftOpen, ShieldHalf } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/layout/Logo";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Analyze", icon: Eye, description: "Ingest a report and watch the pipeline run" },
  { href: "/graph", label: "Memory Graph", icon: Network, description: "Cross-report IOC & actor memory (Frontend B)" },
  { href: "/eval", label: "Scoreboard", icon: Trophy, description: "TRINETRA vs plain-LLM accuracy (Frontend B)" },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      data-collapsed={collapsed}
      className={cn(
        "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 md:flex",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
        <Logo className="size-6 shrink-0" />
        {!collapsed && (
          <span className="font-heading text-sm font-semibold tracking-[0.2em] text-sidebar-foreground">
            TRINETRA
          </span>
        )}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3" aria-label="Primary">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const link = (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground/70 transition-colors",
                "hover:bg-sidebar-accent hover:text-sidebar-foreground",
                active && "bg-sidebar-accent text-primary",
                collapsed && "justify-center px-0",
              )}
            >
              <item.icon
                className={cn(
                  "size-4 shrink-0",
                  active && "text-primary",
                )}
                aria-hidden="true"
              />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
          return collapsed ? (
            <Tooltip key={item.href}>
              <TooltipTrigger render={link} />
              <TooltipContent side="right">{item.label}</TooltipContent>
            </Tooltip>
          ) : (
            link
          );
        })}
      </nav>

      <div className="border-t border-sidebar-border p-2">
        <div
          className={cn(
            "mb-2 flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-sidebar-foreground/60",
            collapsed && "justify-center px-0",
          )}
        >
          <ShieldHalf className="size-3.5 shrink-0 text-observed" aria-hidden="true" />
          {!collapsed && <span className="font-mono">ATT&amp;CK v20</span>}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-center text-sidebar-foreground/60 hover:text-sidebar-foreground"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
        </Button>
      </div>
    </aside>
  );
}
