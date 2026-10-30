"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Brain,
  CheckCircle2,
  Code2,
  Cpu,
  Database,
  FileSearch,
  Filter,
  GitBranch,
  Layers,
  Link as LinkIcon,
  Loader2,
  Network,
  Share2,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { StageName, StageStatus } from "@/lib/types";
import type { StageKind, StageMeta } from "./stages";

const STAGE_ICONS: Record<StageName, React.ElementType> = {
  ingest: FileSearch,
  guard: ShieldAlert,
  ioc: Filter,
  ioc_role: Bot,
  behaviours: Brain,
  retrieve: Database,
  verify: Layers,
  link: LinkIcon,
  migrate: GitBranch,
  tie: Sparkles,
  flow: Network,
  detect: Cpu,
  memory: Activity,
  export: Share2,
  pipeline: CheckCircle2,
};

const KIND_BADGES: Record<StageKind, { label: string; className: string }> = {
  deterministic: { label: "deterministic", className: "bg-slate-800/80 text-slate-300 border-slate-700" },
  LLM: { label: "LLM", className: "bg-purple-950/70 text-purple-300 border-purple-800" },
  vector: { label: "vector", className: "bg-cyan-950/70 text-cyan-300 border-cyan-800" },
  hybrid: { label: "hybrid", className: "bg-amber-950/70 text-amber-300 border-amber-800" },
  graph: { label: "graph", className: "bg-teal-950/70 text-teal-300 border-teal-800" },
  "ML model": { label: "ML model", className: "bg-pink-950/70 text-pink-300 border-pink-800" },
  "LLM + rules": { label: "LLM + rules", className: "bg-indigo-950/70 text-indigo-300 border-indigo-800" },
};

export type PipelineNodeData = {
  meta: StageMeta;
  status: StageStatus;
  ms?: number;
  lastData?: unknown;
  onSelectNode: (stageId: StageName) => void;
};

export const PipelineNode = memo(function PipelineNode({ data }: NodeProps) {
  const nodeData = data as unknown as PipelineNodeData;
  const { meta, status, ms, onSelectNode } = nodeData;
  const Icon = STAGE_ICONS[meta.id] || Code2;
  const kindBadge = KIND_BADGES[meta.kind];

  const isRunning = status === "started" || status === "progress";
  const isDone = status === "done";
  const isError = status === "error";

  return (
    <div
      onClick={() => onSelectNode(meta.id)}
      className={cn(
        "group relative flex w-[155px] cursor-pointer flex-col gap-1.5 rounded-lg border bg-card/90 p-2 text-xs shadow-sm backdrop-blur transition-all hover:border-primary/60 hover:shadow-md",
        status === "idle" && "border-border/60 opacity-60 hover:opacity-100",
        isRunning && "border-primary bg-primary/10 shadow-[0_0_15px_rgba(34,211,238,0.35)] ring-1 ring-primary/50 animate-pulse",
        isDone && "border-emerald-600/70 bg-emerald-950/20 text-foreground",
        isError && "border-destructive/80 bg-destructive/10 text-destructive",
      )}
    >
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-none !bg-muted-foreground/60" />

      <div className="flex items-center justify-between gap-1">
        <div className="flex items-center gap-1.5 truncate font-medium">
          <Icon className={cn("size-3.5 shrink-0", isRunning && "text-primary animate-spin", isDone && "text-emerald-400", isError && "text-destructive")} />
          <span className="truncate text-[11px] font-semibold">{meta.name}</span>
        </div>
        <div className="shrink-0">
          {isRunning && <Loader2 className="size-3 animate-spin text-primary" />}
          {isDone && <CheckCircle2 className="size-3 text-emerald-400" />}
          {isError && <AlertTriangle className="size-3 text-destructive" />}
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px]">
        <span className={cn("rounded border px-1 py-0.2 text-[9px] font-mono uppercase tracking-wider", kindBadge.className)}>
          {kindBadge.label}
        </span>
        <span className="font-mono text-muted-foreground">
          {ms !== undefined ? `${ms}ms` : isRunning ? "active" : "idle"}
        </span>
      </div>

      <Handle type="source" position={Position.Right} className="!size-1.5 !border-none !bg-muted-foreground/60" />
    </div>
  );
});
