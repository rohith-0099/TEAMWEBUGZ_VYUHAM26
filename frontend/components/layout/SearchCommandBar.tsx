// Global search over recent analyses. Owner: Frontend A.
"use client";

import { useQuery } from "@tanstack/react-query";
import { FileSearch, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { listAnalyses } from "@/lib/api";
import { cn } from "@/lib/utils";

export function SearchCommandBar() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  const { data: analyses } = useQuery({
    queryKey: ["analyses", "search"],
    queryFn: listAnalyses,
    enabled: open,
  });

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const results = (analyses ?? []).filter((a) =>
    a.title.toLowerCase().includes(query.toLowerCase()) ||
    (a.source_url ?? "").toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-8 w-full max-w-xs items-center gap-2 rounded-lg border border-border bg-surface px-2.5 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        aria-label="Search analyses"
      >
        <Search className="size-3.5 shrink-0" aria-hidden="true" />
        <span className="truncate">Search reports…</span>
        <kbd className="ml-auto rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
          ⌘K
        </kbd>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="top-[20%] max-w-lg translate-y-0 p-0 sm:max-w-lg">
          <DialogHeader className="border-b border-border p-3">
            <DialogTitle className="sr-only">Search analyses</DialogTitle>
            <Input
              autoFocus
              placeholder="Search by title or source…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search analyses"
            />
          </DialogHeader>
          <div className="max-h-80 overflow-y-auto p-2">
            {results.length === 0 && (
              <p className="px-2 py-6 text-center text-sm text-muted-foreground">No matching reports.</p>
            )}
            {results.map((a) => (
              <button
                key={a.report_id}
                type="button"
                onClick={() => {
                  setOpen(false);
                  router.push(`/report/${a.report_id}`);
                }}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                  "hover:bg-accent focus-visible:bg-accent focus-visible:outline-none",
                )}
              >
                <FileSearch className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-foreground">{a.title}</span>
                  <span className="block truncate font-mono text-xs text-muted-foreground">
                    {a.source_url ?? a.report_id}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
