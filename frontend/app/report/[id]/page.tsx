"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AttackFlowView } from "@/components/attack-flow";
import { DetectionPanel } from "@/components/detection-panel";
import { GlobeView } from "@/components/globe";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getAnalysis } from "@/lib/api";
import { useAnalysisStream } from "@/lib/sse";
import type { ReportAnalysis } from "@/lib/types";

// Placeholder tabs shell. Owner: Frontend A, see team/01_FRONTEND_A.md 4.3.
export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const { last, finished } = useAnalysisStream(id);
  const [analysis, setAnalysis] = useState<ReportAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!finished) return;
    getAnalysis(id)
      .then(setAnalysis)
      .catch((e: Error) => setError(e.message));
  }, [id, finished]);

  if (error) return <main className="p-6 text-destructive">{error}</main>;
  if (!analysis) {
    return (
      <main className="p-6 text-muted-foreground">
        Running pipeline{last ? `: ${last.stage} ${last.status}` : "..."}
      </main>
    );
  }

  const accepted = analysis.techniques.filter((t) => t.status === "accepted").length;
  const iocs = analysis.iocs.filter((i) => !i.filtered_reason).length;

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-4 px-6 py-8">
      <h1 className="text-2xl font-semibold">{analysis.title}</h1>
      {analysis.status === "error" && <p className="text-destructive">{analysis.error}</p>}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="flow">Attack Flow</TabsTrigger>
          <TabsTrigger value="detections">Detections</TabsTrigger>
          <TabsTrigger value="map">Map</TabsTrigger>
          <TabsTrigger value="raw">Raw</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="py-4">
          <p>
            {iocs} IOCs, {accepted} accepted techniques, {analysis.memory_alerts.length} memory alerts
          </p>
        </TabsContent>
        <TabsContent value="evidence" className="py-4">
          <p className="text-muted-foreground">Coming soon: evidence viewer</p>
        </TabsContent>
        <TabsContent value="flow" className="py-4">
          <AttackFlowView analysis={analysis} />
        </TabsContent>
        <TabsContent value="detections" className="py-4">
          <DetectionPanel analysis={analysis} />
        </TabsContent>
        <TabsContent value="map" className="py-4">
          <GlobeView analysisId={analysis.report_id} />
        </TabsContent>
        <TabsContent value="raw" className="py-4">
          <pre className="overflow-x-auto rounded-lg bg-card p-4 font-mono text-xs">
            {/* IOC `value` is the live indicator, so the UI never prints it */}
            {JSON.stringify(analysis, (key, value) => (key === "value" ? undefined : value), 2)}
          </pre>
        </TabsContent>
      </Tabs>
    </main>
  );
}
