// Live analysis store. STUB — owner: Frontend A. See team/01_FRONTEND_A.md 3.4.
// TODO(Frontend A): npm i zustand and implement this state with applyEvent's merge rules.
import type { PipelineEvent, ReportAnalysis, StageName, StageStatus } from "@/lib/types";

export type AnalysisState = {
  analysis: Partial<ReportAnalysis>; // built up from events
  stages: Record<StageName, { status: StageStatus; startedAt?: number; ms?: number; lastData?: unknown }>;
  log: PipelineEvent[];
  selectedTechniqueId?: string;
  hoveredEvidence?: { start: number; end: number };
  applyEvent(e: PipelineEvent): void;
  setFinal(a: ReportAnalysis): void;
  select(techId?: string): void;
};
