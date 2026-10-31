// Live analysis store. Owner: Frontend A. See team/01_FRONTEND_A.md §3.4.
import { create } from "zustand";
import type {
  Behaviour,
  Detection,
  IOC,
  PipelineEvent,
  ReportAnalysis,
  StageName,
  StageStatus,
  TechniqueMatch,
} from "@/lib/types";

export const INITIAL_STAGES: Record<
  StageName,
  { status: StageStatus; startedAt?: number; ms?: number; lastData?: unknown }
> = {
  ingest: { status: "idle" },
  guard: { status: "idle" },
  ioc: { status: "idle" },
  ioc_role: { status: "idle" },
  behaviours: { status: "idle" },
  retrieve: { status: "idle" },
  verify: { status: "idle" },
  link: { status: "idle" },
  migrate: { status: "idle" },
  tie: { status: "idle" },
  flow: { status: "idle" },
  detect: { status: "idle" },
  memory: { status: "idle" },
  vulns: { status: "idle" },
  brief: { status: "idle" },
  export: { status: "idle" },
  pipeline: { status: "idle" },
};

export type AnalysisState = {
  analysis: Partial<ReportAnalysis>;
  stages: Record<
    StageName,
    { status: StageStatus; startedAt?: number; ms?: number; lastData?: unknown }
  >;
  log: PipelineEvent[];
  selectedTechniqueId?: string;
  hoveredEvidence?: { start: number; end: number };

  applyEvent: (event: PipelineEvent) => void;
  setFinal: (analysis: ReportAnalysis) => void;
  select: (techId?: string) => void;
  hover: (evidence?: { start: number; end: number }) => void;
  reset: () => void;
};

export const useAnalysisStore = create<AnalysisState>((set) => ({
  analysis: {
    iocs: [],
    behaviours: [],
    techniques: [],
    predictions: [],
    injection_flags: [],
    detections: [],
    memory_alerts: [],
    migrations: [],
    timings_ms: {},
  },
  stages: { ...INITIAL_STAGES },
  log: [],
  selectedTechniqueId: undefined,
  hoveredEvidence: undefined,

  select: (techId) => set({ selectedTechniqueId: techId }),
  hover: (evidence) => set({ hoveredEvidence: evidence }),

  reset: () =>
    set({
      analysis: {
        iocs: [],
        behaviours: [],
        techniques: [],
        predictions: [],
        injection_flags: [],
        detections: [],
        memory_alerts: [],
        migrations: [],
        timings_ms: {},
      },
      stages: { ...INITIAL_STAGES },
      log: [],
      selectedTechniqueId: undefined,
      hoveredEvidence: undefined,
    }),

  setFinal: (finalAnalysis) =>
    set((state) => ({
      analysis: finalAnalysis,
      stages: Object.keys(state.stages).reduce((acc, stageKey) => {
        const key = stageKey as StageName;
        // Only stages that really ran have a timing; anything else (e.g. a stage added after this
        // analysis was made) is shown as skipped, never as done.
        const ran = key === "pipeline" || key in (finalAnalysis.timings_ms ?? {}) || state.stages[key].status === "done";
        acc[key] = {
          ...state.stages[key],
          status: state.stages[key].status === "error" ? "error" : ran ? "done" : "skipped",
        };
        return acc;
      }, {} as Record<StageName, { status: StageStatus; startedAt?: number; ms?: number; lastData?: unknown }>),
    })),

  applyEvent: (event) =>
    set((state) => {
      const nextLog = [...state.log, event];
      const prevStage = state.stages[event.stage] || { status: "idle" };

      const nextStage = {
        ...prevStage,
        status: event.status,
        startedAt: event.status === "started" ? Date.now() : prevStage.startedAt,
        ms:
          event.elapsed_ms ??
          (event.status === "done" && prevStage.startedAt
            ? Date.now() - prevStage.startedAt
            : prevStage.ms),
        lastData: event.data,
      };

      const nextStages = {
        ...state.stages,
        [event.stage]: nextStage,
      };

      const nextAnalysis: Partial<ReportAnalysis> = { ...state.analysis };

      // Merge data payloads per contracts §9
      if (event.data) {
        switch (event.stage) {
          case "ingest":
            if (event.status === "done") {
              if (event.data.title) nextAnalysis.title = event.data.title;
              if (event.data.source_url) nextAnalysis.source_url = event.data.source_url;
              if (event.data.published_at) nextAnalysis.published_at = event.data.published_at;
              if (event.data.text) nextAnalysis.text = event.data.text;
              if (Array.isArray(event.data.images)) nextAnalysis.images = event.data.images;
              if (event.data.ocr_status !== undefined) nextAnalysis.ocr_status = event.data.ocr_status;
            } else if (event.status === "progress" && event.data.image) {
              const current = nextAnalysis.images || [];
              if (!current.some((i) => i.index === event.data.image.index)) {
                nextAnalysis.images = [...current, event.data.image];
              }
            }
            break;

          case "guard":
            if (event.status === "done" && Array.isArray(event.data.flags)) {
              nextAnalysis.injection_flags = event.data.flags;
            }
            break;

          case "ioc":
          case "ioc_role":
            if (event.status === "done" && Array.isArray(event.data.iocs)) {
              nextAnalysis.iocs = event.data.iocs as IOC[];
            }
            break;

          case "behaviours":
            if (event.status === "progress" && event.data.behaviour) {
              const b = event.data.behaviour as Behaviour;
              const current = nextAnalysis.behaviours || [];
              if (!current.some((x) => x.id === b.id)) {
                nextAnalysis.behaviours = [...current, b];
              }
            }
            break;

          case "verify":
            if (event.status === "progress" && event.data.technique) {
              const tech = event.data.technique as TechniqueMatch;
              const current = nextAnalysis.techniques || [];
              const idx = current.findIndex(
                (t) =>
                  t.technique_id === tech.technique_id &&
                  (t.behaviour_id === tech.behaviour_id || (!t.behaviour_id && !tech.behaviour_id)),
              );
              if (idx >= 0) {
                const updated = [...current];
                updated[idx] = tech;
                nextAnalysis.techniques = updated;
              } else {
                nextAnalysis.techniques = [...current, tech];
              }
            }
            break;

          case "link":
            if (event.status === "done") {
              if (Array.isArray(event.data.techniques)) {
                nextAnalysis.techniques = event.data.techniques as TechniqueMatch[];
              }
              if (Array.isArray(event.data.iocs)) {
                nextAnalysis.iocs = event.data.iocs as IOC[];
              }
            }
            break;

          case "migrate":
            if (event.status === "done" && Array.isArray(event.data.migrations)) {
              nextAnalysis.migrations = event.data.migrations;
            }
            break;

          case "tie":
            if (event.status === "done" && Array.isArray(event.data.predictions)) {
              nextAnalysis.predictions = event.data.predictions;
            }
            break;

          case "flow":
            if (event.status === "done" && event.data.flow) {
              nextAnalysis.flow = event.data.flow;
            }
            break;

          case "detect":
            if (event.status === "progress" && event.data.detection) {
              const det = event.data.detection as Detection;
              const current = nextAnalysis.detections || [];
              if (!current.some((d) => d.technique_id === det.technique_id)) {
                nextAnalysis.detections = [...current, det];
              }
            } else if (event.status === "done" && Array.isArray(event.data.detections)) {
              nextAnalysis.detections = event.data.detections;
            }
            break;

          case "memory":
            if (event.status === "done" && Array.isArray(event.data.alerts)) {
              nextAnalysis.memory_alerts = event.data.alerts;
            }
            break;

          case "vulns":
            if (event.status === "done" && Array.isArray(event.data.vulnerabilities)) {
              nextAnalysis.vulnerabilities = event.data.vulnerabilities;
            }
            break;

          case "brief":
            if (event.status === "done") {
              nextAnalysis.briefing = event.data.briefing ?? null;
            }
            break;

          case "pipeline":
            if (event.status === "done") {
              nextAnalysis.status = "done";
            } else if (event.status === "error") {
              nextAnalysis.status = "error";
              nextAnalysis.error = event.data.message || "Pipeline error";
            }
            break;
        }
      }

      return {
        stages: nextStages,
        log: nextLog,
        analysis: nextAnalysis,
      };
    }),
}));
