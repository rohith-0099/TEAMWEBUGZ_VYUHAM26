"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  Bug,
  FileText,
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
import { BracketChip } from "@/components/charts";
import { tacticColor } from "@/lib/tactics";
import { cn } from "@/lib/utils";
import type { StageName, StageStatus } from "@/lib/types";
import { STAGE_ORDER, type StageMeta } from "./stages";

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
  vulns: Bug,
  brief: FileText,
  export: Share2,
  pipeline: CheckCircle2,
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
  const stageColor = tacticColor(STAGE_ORDER.indexOf(meta.id));

  const isRunning = status === "started" || status === "progress";
  const isDone = status === "done";
  const isError = status === "error";

  return (
    <button
      type="button"
      onClick={() => onSelectNode(meta.id)}
      aria-label={`${meta.name}: ${status}`}
      style={{ "--stage-color": stageColor } as React.CSSProperties}
      className={cn(
        "group relative flex w-[152px] cursor-pointer flex-col gap-1.5 rounded-lg border border-dotted border-white/50 bg-black p-2 text-left text-xs transition-colors hover:border-white",
        status === "idle" && "border-white/25 text-muted-foreground",
        isRunning && "stage-running",
        isDone && "border-[var(--stage-color)]",
        isError && "border-solid border-danger text-danger",
      )}
    >
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-none !bg-muted-foreground/60" />

      <div className="flex items-center justify-between gap-1">
        <div className="flex items-center gap-1.5 truncate font-medium">
          <Icon className={cn("size-3.5 shrink-0", isRunning && "text-[var(--stage-color)]", isDone && "text-[var(--stage-color)]", isError && "text-destructive")} />
          <span className="truncate text-xs font-semibold">{meta.name}</span>
        </div>
        <div className="shrink-0">
          {isRunning && <Loader2 className="size-3 animate-spin text-[var(--stage-color)]" />}
          {isDone && <CheckCircle2 className="size-3 text-[var(--stage-color)]" />}
          {isError && <AlertTriangle className="size-3 text-destructive" />}
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px]">
        <BracketChip>{meta.kind}</BracketChip>
        <span className="font-mono text-muted-foreground">
          {ms !== undefined ? `${(ms / 1000).toFixed(1)}s` : isRunning ? "active" : "idle"}
        </span>
      </div>

      <Handle type="source" position={Position.Right} className="!size-1.5 !border-none !bg-muted-foreground/60" />
    </button>
  );
});
