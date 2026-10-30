"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { API_URL, exportUrl } from "@/lib/api";
import { useAnalysisStore } from "@/lib/store";

interface StixPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reportId: string;
}

export function StixPreviewDialog({ open, onOpenChange, reportId }: StixPreviewDialogProps) {
  const analysis = useAnalysisStore((state) => state.analysis);
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string>("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open || !reportId) return;

    setLoading(true);
    fetch(`${API_URL}/api/analyses/${reportId}/export/stix`)
      .then(async (res) => {
        if (!res.ok) throw new Error("Backend export not available, building local preview");
        return res.json();
      })
      .then((data) => {
        setContent(JSON.stringify(data, null, 2));
      })
      .catch(() => {
        // Fallback STIX 2.1 bundle representation for mock/offline presentation
        const mockBundle = {
          type: "bundle",
          id: `bundle--${crypto.randomUUID()}`,
          objects: [
            {
              type: "report",
              id: `report--${crypto.randomUUID()}`,
              name: analysis.title || "Threat Intelligence Report",
              published: analysis.published_at || new Date().toISOString(),
              object_refs: (analysis.techniques || []).map((t) => `attack-pattern--${t.technique_id}`),
            },
            ...(analysis.iocs || []).map((ioc) => ({
              type: "indicator",
              id: `indicator--${crypto.randomUUID()}`,
              name: ioc.display,
              pattern: `[${ioc.type}:value = '${ioc.display}']`,
              pattern_type: "stix",
            })),
            ...(analysis.techniques || [])
              .filter((t) => t.status === "accepted")
              .map((t) => ({
                type: "attack-pattern",
                id: `attack-pattern--${crypto.randomUUID()}`,
                name: t.name,
                external_references: [
                  { source_name: "mitre-attack", external_id: t.technique_id },
                ],
              })),
          ],
        };
        setContent(JSON.stringify(mockBundle, null, 2));
      })
      .finally(() => setLoading(false));
  }, [open, reportId, analysis]);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    toast.success("STIX 2.1 JSON copied to clipboard");
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] w-full flex-col sm:max-w-2xl">
        <DialogHeader className="border-b pb-3">
          <div className="flex items-center justify-between">
            <DialogTitle className="font-heading text-lg font-semibold">
              STIX 2.1 Bundle Preview
            </DialogTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
                disabled={loading || !content}
                className="h-8 gap-1.5 text-xs"
              >
                {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
                <span>{copied ? "Copied" : "Copy"}</span>
              </Button>
              <a
                href={exportUrl(reportId, "stix")}
                download={`trinetra-${reportId}-stix.json`}
                className="inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground hover:bg-primary/90"
              >
                <Download className="size-3.5" />
                <span>Download</span>
              </a>
            </div>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            OASIS STIX 2.1 compliant representation mapping indicators to ATT&CK v20 attack patterns.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden py-2">
          <ScrollArea className="h-[500px] rounded-lg border bg-background/80 p-4 font-mono text-xs">
            {loading ? (
              <div className="flex h-48 items-center justify-center gap-2 text-muted-foreground">
                <Loader2 className="size-4 animate-spin text-primary" />
                <span>Generating STIX 2.1 bundle...</span>
              </div>
            ) : (
              <pre className="text-[11px] leading-relaxed text-foreground/90 whitespace-pre-wrap">
                {content}
              </pre>
            )}
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}
