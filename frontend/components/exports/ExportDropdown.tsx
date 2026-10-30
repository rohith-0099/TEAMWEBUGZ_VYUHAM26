"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Code,
  Eye,
  FileCode,
  FileSpreadsheet,
  Network,
  Printer,
  Share2,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { TooltipProvider } from "@/components/ui/tooltip";
import { exportUrl } from "@/lib/api";
import { StixPreviewDialog } from "./StixPreviewDialog";

interface ExportDropdownProps {
  reportId: string;
  disabled?: boolean;
}

export function ExportDropdown({ reportId, disabled = false }: ExportDropdownProps) {
  const [showStixPreview, setShowStixPreview] = useState(false);

  return (
    <TooltipProvider delay={200}>
      <div className="flex items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <button
                type="button"
                disabled={disabled}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-xs font-semibold text-foreground transition-colors hover:bg-muted disabled:opacity-50"
              />
            }
          >
            <Share2 className="size-3.5" />
            <span>Export ▾</span>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" className="w-60 text-xs">
            <DropdownMenuLabel className="font-heading text-xs">Export Formats</DropdownMenuLabel>
            <DropdownMenuSeparator />

            <DropdownMenuItem
              render={
                <a
                  href={exportUrl(reportId, "stix")}
                  download={`trinetra-${reportId}-stix.json`}
                  className="flex cursor-pointer items-center gap-2"
                />
              }
            >
              <FileCode className="size-4 text-primary" />
              <div className="flex flex-col">
                <span className="font-medium">STIX 2.1 Bundle</span>
                <span className="text-[10px] text-muted-foreground">OASIS CTI JSON standard</span>
              </div>
            </DropdownMenuItem>

            <DropdownMenuItem
              render={
                <a
                  href={exportUrl(reportId, "navigator")}
                  download={`trinetra-${reportId}-navigator.json`}
                  className="flex cursor-pointer items-center gap-2"
                />
              }
            >
              <FileSpreadsheet className="size-4 text-emerald-400" />
              <div className="flex flex-col">
                <span className="font-medium">ATT&CK Navigator Layer</span>
                <span className="text-[10px] text-muted-foreground">v20 Matrix Layer JSON</span>
              </div>
            </DropdownMenuItem>

            <DropdownMenuItem
              render={
                <a
                  href={exportUrl(reportId, "sigma")}
                  download={`trinetra-${reportId}-sigma.yml`}
                  className="flex cursor-pointer items-center gap-2"
                />
              }
            >
              <Code className="size-4 text-amber-400" />
              <div className="flex flex-col">
                <span className="font-medium">Sigma Detection Rules</span>
                <span className="text-[10px] text-muted-foreground">Validated YAML archive</span>
              </div>
            </DropdownMenuItem>

            <DropdownMenuItem
              render={
                <a
                  href={exportUrl(reportId, "flow")}
                  download={`trinetra-${reportId}-flow.json`}
                  className="flex cursor-pointer items-center gap-2"
                />
              }
            >
              <Network className="size-4 text-teal-400" />
              <div className="flex flex-col">
                <span className="font-medium">Attack Flow Schema</span>
                <span className="text-[10px] text-muted-foreground">CTID Attack Flow 3 JSON</span>
              </div>
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            <DropdownMenuItem
              onClick={() => setShowStixPreview(true)}
              className="flex cursor-pointer items-center gap-2"
            >
              <Eye className="size-4 text-muted-foreground" />
              <span>Preview STIX 2.1 JSON</span>
            </DropdownMenuItem>

            <DropdownMenuItem
              render={
                <Link
                  href={`/report/${reportId}/print`}
                  className="flex cursor-pointer items-center gap-2"
                />
              }
            >
              <Printer className="size-4 text-muted-foreground" />
              <span>Print / Save as PDF</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Link
          href={`/report/${reportId}/print?auto=1`}
          target="_blank"
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-2.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Printable executive report"
        >
          <Printer className="size-3.5" />
          <span>Print</span>
        </Link>

        <StixPreviewDialog
          open={showStixPreview}
          onOpenChange={setShowStixPreview}
          reportId={reportId}
        />
      </div>
    </TooltipProvider>
  );
}
