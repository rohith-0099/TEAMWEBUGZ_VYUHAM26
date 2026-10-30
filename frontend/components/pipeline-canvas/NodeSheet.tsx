"use client";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { StageName, StageStatus } from "@/lib/types";
import { STAGES_CONFIG } from "./stages";

interface NodeSheetProps {
  stageId: StageName | null;
  status?: StageStatus;
  ms?: number;
  lastData?: unknown;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function truncatePayload(data: unknown): unknown {
  if (Array.isArray(data)) {
    if (data.length > 20) {
      return [...data.slice(0, 20).map(truncatePayload), `... (${data.length - 20} more items)`];
    }
    return data.map(truncatePayload);
  }
  if (data !== null && typeof data === "object") {
    const copy: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
      copy[k] = truncatePayload(v);
    }
    return copy;
  }
  return data;
}

export function NodeSheet({ stageId, status, ms, lastData, open, onOpenChange }: NodeSheetProps) {
  if (!stageId) return null;
  const meta = STAGES_CONFIG[stageId];
  if (!meta) return null;

  const truncatedData = lastData ? truncatePayload(lastData) : null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col sm:max-w-md">
        <SheetHeader className="border-b pb-4">
          <div className="flex items-center justify-between gap-2">
            <SheetTitle className="font-heading text-lg font-semibold">{meta.name}</SheetTitle>
            <Badge variant="outline" className="font-mono text-xs">
              {meta.kind}
            </Badge>
          </div>
          <SheetDescription className="text-xs text-muted-foreground">
            {meta.description}
          </SheetDescription>
          <div className="mt-2 flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5 font-medium">
              Status:{" "}
              <span className={status === "done" ? "text-success" : status === "started" || status === "progress" ? "text-primary animate-pulse" : "text-muted-foreground"}>
                {status ?? "idle"}
              </span>
            </span>
            {ms !== undefined && (
              <span className="font-mono text-muted-foreground">
                Execution time: <strong className="text-foreground">{ms}ms</strong>
              </span>
            )}
          </div>
        </SheetHeader>

        <div className="flex flex-1 flex-col gap-2 overflow-hidden py-4">
          <span className="text-xs font-semibold text-muted-foreground">
            Last Streamed Payload
          </span>
          <ScrollArea className="flex-1 rounded-md border bg-muted/20 p-3 font-mono text-[11px]">
            {truncatedData ? (
              <pre className="text-xs leading-relaxed text-foreground/90 whitespace-pre-wrap">
                {JSON.stringify(truncatedData, null, 2)}
              </pre>
            ) : (
              <p className="italic text-muted-foreground">No output data recorded for this stage yet.</p>
            )}
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>
  );
}
