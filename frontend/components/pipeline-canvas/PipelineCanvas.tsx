"use client";

import { useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ChevronDown, ChevronUp, Terminal, Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAnalysisStore } from "@/lib/store";
import type { StageName } from "@/lib/types";
import { NodeSheet } from "./NodeSheet";
import { PipelineNode } from "./PipelineNode";
import { PIPELINE_EDGES, STAGES_CONFIG } from "./stages";

const nodeTypes = {
  pipelineNode: PipelineNode,
};

export function PipelineCanvas() {
  const stages = useAnalysisStore((state) => state.stages);
  const log = useAnalysisStore((state) => state.log);
  const [collapsed, setCollapsed] = useState(false);
  const [selectedStage, setSelectedStage] = useState<StageName | null>(null);

  const nodes: Node[] = useMemo(() => {
    return Object.values(STAGES_CONFIG).map((meta) => {
      const stageState = stages[meta.id] || { status: "idle" };
      return {
        id: meta.id,
        type: "pipelineNode",
        position: { x: meta.x, y: meta.y },
        data: {
          meta,
          status: stageState.status,
          ms: stageState.ms,
          lastData: stageState.lastData,
          onSelectNode: (stageId: StageName) => setSelectedStage(stageId),
        },
      };
    });
  }, [stages]);

  const edges: Edge[] = useMemo(() => {
    return PIPELINE_EDGES.map((edgeDef) => {
      const targetState = stages[edgeDef.target as StageName] || { status: "idle" };
      const sourceState = stages[edgeDef.source as StageName] || { status: "idle" };

      const isRunning = targetState.status === "started" || targetState.status === "progress";
      const isDone = targetState.status === "done" && sourceState.status === "done";

      let stroke = "#334155"; // slate-700
      if (isRunning) stroke = "#22D3EE"; // cyan
      else if (isDone) stroke = "#10B981"; // emerald

      return {
        id: edgeDef.id,
        source: edgeDef.source,
        target: edgeDef.target,
        animated: isRunning,
        style: {
          stroke,
          strokeWidth: isRunning ? 2 : 1.5,
          opacity: isDone || isRunning ? 1 : 0.4,
        },
      };
    });
  }, [stages]);

  // Last 3 log events for the ticker
  const recentLogs = useMemo(() => log.slice(-3).reverse(), [log]);

  const activeCount = Object.values(stages).filter((s) => s.status === "started" || s.status === "progress").length;
  const doneCount = Object.values(stages).filter((s) => s.status === "done").length;

  return (
    <div className="flex flex-col rounded-xl border bg-card/60 shadow-sm backdrop-blur">
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Workflow className="size-4 text-primary" />
          <span className="font-heading text-sm font-semibold tracking-tight">
            Live Agent Pipeline Canvas
          </span>
          <Badge variant="outline" className="text-xs font-mono">
            {doneCount}/14 done {activeCount > 0 && `· ${activeCount} running`}
          </Badge>
        </div>

        <Button
          variant="ghost"
          size="sm"
          className="size-7 p-0 text-muted-foreground hover:text-foreground"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand canvas" : "Collapse canvas"}
        >
          {collapsed ? <ChevronDown className="size-4" /> : <ChevronUp className="size-4" />}
        </Button>
      </div>

      {!collapsed && (
        <>
          <div className="h-[210px] w-full overflow-hidden bg-background/50">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              zoomOnScroll={false}
              panOnScroll={false}
              panOnDrag={true}
              fitView
              fitViewOptions={{ padding: 0.15 }}
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#334155" />
            </ReactFlow>
          </div>

          <div className="flex items-center gap-2 border-t bg-muted/20 px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
            <Terminal className="size-3 text-primary shrink-0" />
            <div className="flex flex-1 items-center gap-4 truncate">
              {recentLogs.length > 0 ? (
                recentLogs.map((entry, idx) => (
                  <span key={idx} className="truncate">
                    <span className="text-primary font-semibold">[{entry.stage}]</span> {entry.status}{" "}
                    {entry.elapsed_ms !== undefined && `(${entry.elapsed_ms}ms)`}
                  </span>
                ))
              ) : (
                <span className="italic">Pipeline initialized. Awaiting events...</span>
              )}
            </div>
          </div>
        </>
      )}

      <NodeSheet
        stageId={selectedStage}
        status={selectedStage ? stages[selectedStage]?.status : undefined}
        ms={selectedStage ? stages[selectedStage]?.ms : undefined}
        lastData={selectedStage ? stages[selectedStage]?.lastData : undefined}
        open={Boolean(selectedStage)}
        onOpenChange={(open) => !open && setSelectedStage(null)}
      />
    </div>
  );
}
