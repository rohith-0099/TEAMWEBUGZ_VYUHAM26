// STUB — owner: Frontend B. See team/02_FRONTEND_B.md section 4.
import type { ReportAnalysis } from "@/lib/types";

export function DetectionPanel({ analysis }: { analysis: Partial<ReportAnalysis> }) {
  return <p className="text-muted-foreground">Coming soon: detections ({analysis.detections?.length ?? 0} techniques)</p>;
}
