// STUB — owner: Frontend B. See team/02_FRONTEND_B.md section 3.
import type { ReportAnalysis } from "@/lib/types";

export function AttackFlowView({ analysis }: { analysis: Partial<ReportAnalysis> }) {
  return <p className="text-muted-foreground">Coming soon: attack flow ({analysis.flow?.nodes.length ?? 0} nodes)</p>;
}
