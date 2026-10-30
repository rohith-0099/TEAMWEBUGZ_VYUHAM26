"use client";

import dynamic from "next/dynamic";
import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Clock,
  Copy,
  ExternalLink,
  Repeat,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AttackFlowView } from "@/components/attack-flow";
import { AttackHeatmap } from "@/components/attack-heatmap";
import { DetectionPanel } from "@/components/detection-panel";
import { ExportDropdown } from "@/components/exports";
import { IocTable } from "@/components/ioc-table";
import { ContradictionCard } from "@/components/memory-graph/ContradictionCard";
import { PipelineCanvas } from "@/components/pipeline-canvas";
import { ReportViewer } from "@/components/report-viewer";
import { TechniqueCards } from "@/components/technique-card";
import { getAnalysis } from "@/lib/api";
import { useAnalysisStream } from "@/lib/sse";
import { useAnalysisStore } from "@/lib/store";
import type { MemoryAlert } from "@/lib/types";

// deck.gl and MapLibre touch WebGL as soon as they load, so they can only run in the browser.
const GlobeView = dynamic(() => import("@/components/globe").then((m) => m.GlobeView), { ssr: false });

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { finished } = useAnalysisStream(id);

  const analysis = useAnalysisStore((state) => state.analysis);
  const stages = useAnalysisStore((state) => state.stages);
  const setFinal = useAnalysisStore((state) => state.setFinal);

  const [activeTab, setActiveTab] = useState<string>("overview");
  const [selectedContradiction, setSelectedContradiction] = useState<MemoryAlert | null>(null);
  const [copiedRaw, setCopiedRaw] = useState(false);

  // If opening an existing report that is already done, load final state directly
  useEffect(() => {
    if (finished || !analysis.title) {
      getAnalysis(id)
        .then((data) => {
          setFinal(data);
        })
        .catch((err) => console.warn("Failed to fetch initial report analysis:", err));
    }
  }, [id, finished, setFinal, analysis.title]);

  const acceptedTechniques = useMemo(
    () => (analysis.techniques || []).filter((t) => t.status === "accepted"),
    [analysis.techniques]
  );

  const nonFilteredIocs = useMemo(
    () => (analysis.iocs || []).filter((i) => !i.filtered_reason),
    [analysis.iocs]
  );

  const hallucinationsBlocked = useMemo(
    () =>
      (analysis.techniques || []).filter(
        (t) =>
          t.status === "rejected" &&
          (t.reject_reason === "id_not_in_v20" ||
            t.reject_reason === "quote_not_in_source" ||
            t.reject_reason === "verifier_mismatch")
      ).length,
    [analysis.techniques]
  );

  const coveredTacticsCount = useMemo(() => {
    const tactics = new Set<string>();
    for (const t of acceptedTechniques) {
      for (const tac of t.tactics) tactics.add(tac);
    }
    return tactics.size;
  }, [acceptedTechniques]);

  const totalTimeMs = useMemo(() => {
    // Each stage's ms is time since the run started, so the largest is the total.
    return Object.values(stages).reduce((acc, s) => Math.max(acc, s.ms || 0), 0);
  }, [stages]);

  const copyRawJson = () => {
    const sanitized = JSON.stringify(
      analysis,
      (key, value) => (key === "value" ? undefined : value),
      2
    );
    navigator.clipboard.writeText(sanitized);
    setCopiedRaw(true);
    toast.success("Sanitized analysis JSON copied to clipboard");
    setTimeout(() => setCopiedRaw(false), 1500);
  };

  const injectionFlags = analysis.injection_flags || [];
  const memoryAlerts = analysis.memory_alerts || [];

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6">
      {/* Report Header */}
      <div className="flex flex-col gap-4 rounded-xl border bg-card/70 p-5 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
                <ShieldCheck className="size-3.5" />
                ATT&CK v20 Verified
              </span>
              <Badge
                variant="outline"
                className={
                  analysis.status === "done"
                    ? "border-emerald-500/60 bg-emerald-950/30 text-emerald-400 font-mono"
                    : analysis.status === "error"
                    ? "border-destructive/60 bg-destructive/10 text-destructive font-mono"
                    : "border-primary/60 bg-primary/10 text-primary font-mono animate-pulse"
                }
              >
                ● {analysis.status ?? "running"}
              </Badge>
              {analysis.source_url && (
                <a
                  href={analysis.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 font-mono text-xs text-muted-foreground hover:text-foreground"
                >
                  <span>{new URL(analysis.source_url).hostname}</span>
                  <ExternalLink className="size-3" />
                </a>
              )}
              {analysis.published_at && (
                <span className="font-mono text-xs text-muted-foreground">
                  Published: {new Date(analysis.published_at).toLocaleDateString()}
                </span>
              )}
            </div>

            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground sm:text-2xl">
              {analysis.title || "Processing Threat Report..."}
            </h1>
          </div>

          <ExportDropdown reportId={id} disabled={analysis.status !== "done"} />
        </div>

        {/* Prompt-Injection Firewall Alert Banner (S6) */}
        {injectionFlags.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/60 bg-destructive/10 p-3 text-xs text-destructive">
            <div className="flex items-center gap-2 font-medium">
              <ShieldAlert className="size-4 shrink-0" />
              <span>
                <strong>⚠ Prompt-injection attempt detected in this report</strong> (mapped to
                ATT&CK {injectionFlags[0]?.technique_id || "T1699"}). Untrusted content was treated
                strictly as data.
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setActiveTab("evidence")}
              className="h-7 border-destructive/40 bg-destructive/20 text-xs text-destructive hover:bg-destructive/30"
            >
              Show in Evidence
            </Button>
          </div>
        )}

        {/* Cross-Report Memory Alerts (S5) */}
        {memoryAlerts.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground">Memory:</span>
            {memoryAlerts.map((alert, idx) => {
              if (alert.type === "seen_before") {
                return (
                  <Link
                    key={idx}
                    href="/graph"
                    className="inline-flex items-center gap-1.5 rounded-full border border-teal-500/40 bg-teal-950/30 px-3 py-1 font-mono text-xs text-teal-300 hover:bg-teal-900/40"
                  >
                    <Repeat className="size-3" />
                    <span>{alert.message}</span>
                  </Link>
                );
              }
              return (
                <button
                  key={idx}
                  onClick={() => setSelectedContradiction(alert)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/50 bg-amber-950/30 px-3 py-1 font-mono text-xs text-amber-300 hover:bg-amber-900/40"
                >
                  <Zap className="size-3" />
                  <span>⚡ Contradiction: {alert.entity_display}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Stat Strip */}
        <div className="grid grid-cols-2 gap-3 border-t pt-4 sm:grid-cols-5">
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Indicators
            </span>
            <span className="font-heading text-xl font-bold text-foreground">
              {nonFilteredIocs.length}
            </span>
            <span className="text-[10px] text-muted-foreground">Cleaned &amp; Defanged</span>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Techniques
            </span>
            <span className="font-heading text-xl font-bold text-primary">
              {acceptedTechniques.length}
            </span>
            <span className="text-[10px] text-muted-foreground">ATT&amp;CK v20 Verified</span>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Tactics
            </span>
            <span className="font-heading text-xl font-bold text-foreground">
              {coveredTacticsCount}
              <span className="text-sm font-normal text-muted-foreground">/15</span>
            </span>
            <span className="text-[10px] text-muted-foreground">Matrix Coverage</span>
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
              <Shield className="size-3" /> Blocked 🛡️
            </span>
            <span className="font-heading text-xl font-bold text-emerald-400">
              {hallucinationsBlocked}
            </span>
            <span className="text-[10px] text-muted-foreground">Hallucinations Filtered</span>
          </div>

          <div className="flex flex-col gap-0.5 col-span-2 sm:col-span-1">
            <span className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              <Clock className="size-3" /> Latency
            </span>
            <span className="font-heading text-xl font-bold font-mono text-foreground">
              {totalTimeMs > 0 ? `${(totalTimeMs / 1000).toFixed(1)}s` : "streaming"}
            </span>
            <span className="text-[10px] text-muted-foreground">Parallel Stream</span>
          </div>
        </div>
      </div>

      {/* Pipeline Canvas (Full Width) */}
      <PipelineCanvas />

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col gap-4">
        <TabsList className="h-10 justify-start rounded-xl border bg-card/60 p-1">
          <TabsTrigger value="overview" className="text-xs font-semibold">
            Overview
          </TabsTrigger>
          <TabsTrigger value="evidence" className="text-xs font-semibold">
            Evidence Ground-Truth
          </TabsTrigger>
          <TabsTrigger value="flow" className="text-xs font-semibold">
            Attack Flow (S1/S2/S3)
          </TabsTrigger>
          <TabsTrigger value="detections" className="text-xs font-semibold">
            Detections &amp; Sigma (S4)
          </TabsTrigger>
          <TabsTrigger value="map" className="text-xs font-semibold">
            Infrastructure Map
          </TabsTrigger>
          <TabsTrigger value="raw" className="text-xs font-semibold">
            Raw JSON
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="flex flex-col gap-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <IocTable iocs={analysis.iocs} />
            <TechniqueCards
              techniques={analysis.techniques}
              onSelectTab={(tab) => setActiveTab(tab)}
            />
          </div>
          <AttackHeatmap />
        </TabsContent>

        {/* Evidence Tab */}
        <TabsContent value="evidence">
          <ReportViewer />
        </TabsContent>

        {/* Attack Flow Tab (Frontend B Slot) */}
        <TabsContent value="flow">
          <div className="rounded-xl border bg-card/60 p-4 shadow-sm backdrop-blur">
            <AttackFlowView analysis={analysis} />
          </div>
        </TabsContent>

        {/* Detections Tab (Frontend B Slot) */}
        <TabsContent value="detections">
          <div className="rounded-xl border bg-card/60 p-4 shadow-sm backdrop-blur">
            <DetectionPanel analysis={analysis} />
          </div>
        </TabsContent>

        {/* Map Tab (Frontend B Slot) */}
        <TabsContent value="map">
          <div className="rounded-xl border bg-card/60 p-4 shadow-sm backdrop-blur">
            <GlobeView analysisId={id} />
          </div>
        </TabsContent>

        {/* Raw Tab */}
        <TabsContent value="raw">
          <div className="flex flex-col gap-2 rounded-xl border bg-card/70 p-4 shadow-sm backdrop-blur">
            <div className="flex items-center justify-between border-b pb-2">
              <span className="font-heading text-xs font-semibold uppercase text-muted-foreground">
                Sanitized ReportAnalysis JSON (Value Field Omitted for Safety)
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={copyRawJson}
                className="h-7 gap-1 text-xs"
              >
                <Copy className="size-3" />
                <span>{copiedRaw ? "Copied" : "Copy JSON"}</span>
              </Button>
            </div>
            <pre className="max-h-[600px] overflow-auto rounded-lg bg-background/80 p-4 font-mono text-xs leading-relaxed text-foreground">
              {JSON.stringify(
                analysis,
                (key, value) => (key === "value" ? undefined : value),
                2
              )}
            </pre>
          </div>
        </TabsContent>
      </Tabs>

      {/* Contradiction Dialog */}
      <Dialog
        open={Boolean(selectedContradiction)}
        onOpenChange={(open) => !open && setSelectedContradiction(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading text-lg font-semibold text-amber-400">
              ⚡ Cross-Report Attribution Contradiction
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Identified by Temporal Memory Graph
            </DialogDescription>
          </DialogHeader>
          {selectedContradiction && <ContradictionCard alert={selectedContradiction} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
