"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ChevronDown, ChevronUp, Maximize2, Minimize2, Terminal, Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BracketChip } from "@/components/charts";
import { useAnalysisStore } from "@/lib/store";
import { tacticColor } from "@/lib/tactics";
import { cn } from "@/lib/utils";
import type { StageName } from "@/lib/types";
import { NodeSheet } from "./NodeSheet";
import { PipelineNode } from "./PipelineNode";
import { PIPELINE_EDGES, STAGES_CONFIG, STAGE_ORDER } from "./stages";

// Below this the labels stop being readable, so narrow screens pan instead of shrinking further.
const MIN_ZOOM = 0.55;

const nodeTypes = {
  pipelineNode: PipelineNode,
};

export function PipelineCanvas() {
  const stages = useAnalysisStore((state) => state.stages);
  const log = useAnalysisStore((state) => state.log);
  const [collapsed, setCollapsed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [selectedStage, setSelectedStage] = useState<StageName | null>(null);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

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

      // Rainbow pipes: each pipe takes the colour of the stage it feeds.
      const pipeColor = tacticColor(STAGE_ORDER.indexOf(edgeDef.target as StageName));
      const stroke = isRunning || isDone ? pipeColor : "#2A2A2A";

      return {
        id: edgeDef.id,
        source: edgeDef.source,
        target: edgeDef.target,
        animated: isRunning,
        style: {
          stroke,
          strokeWidth: isRunning || isDone ? 2.5 : 1.5,
          opacity: 1,
        },
      };
    });
  }, [stages]);

  // Last 3 log events for the ticker
  const recentLogs = useMemo(() => log.slice(-3).reverse(), [log]);

  const activeCount = Object.values(stages).filter((s) => s.status === "started" || s.status === "progress").length;
  const doneCount = Object.entries(stages).filter(
    ([name, s]) => name !== "pipeline" && s.status === "done",
  ).length;

  return (
    <section
      className={cn(
        "flex min-w-0 flex-col overflow-hidden rounded-[20px] border bg-card",
        expanded && "fixed inset-4 z-50 shadow-2xl",
      )}
    >
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Workflow className="size-4 text-muted-foreground" aria-hidden="true" />
          <h2 className="console-title">Pipeline</h2>
          <BracketChip>
            {doneCount}/{STAGE_ORDER.length - 1} done{activeCount > 0 && `, ${activeCount} running`}
          </BracketChip>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="size-7 p-0 text-muted-foreground hover:text-foreground"
            onClick={() => {
              setCollapsed(false);
              setExpanded(!expanded);
            }}
            aria-label={expanded ? "Exit full screen" : "View full screen"}
          >
            {expanded ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
          </Button>
          {!expanded && (
            <Button
              variant="ghost"
              size="sm"
              className="size-7 p-0 text-muted-foreground hover:text-foreground"
              onClick={() => setCollapsed(!collapsed)}
              aria-label={collapsed ? "Expand canvas" : "Collapse canvas"}
            >
              {collapsed ? <ChevronDown className="size-4" /> : <ChevronUp className="size-4" />}
            </Button>
          )}
        </div>
      </div>

      {!collapsed && (
        <>
          <div
            className={cn(
              "w-full overflow-hidden bg-black",
              expanded ? "min-h-0 flex-1" : "aspect-[7/2] min-h-[340px]",
            )}
          >
            {/* key remounts on resize so fitView runs again */}
            <ReactFlow
              key={expanded ? "expanded" : "inline"}
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              zoomOnScroll={false}
              panOnScroll={false}
              panOnDrag={true}
              minZoom={MIN_ZOOM}
              fitView
              fitViewOptions={{ padding: 0.04, minZoom: MIN_ZOOM, maxZoom: 1.2 }}
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#1F1F1F" />
            </ReactFlow>
          </div>

          <div className="flex items-center gap-2 border-t bg-muted/20 px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
            <Terminal className="size-3 shrink-0" aria-hidden="true" />
            <div className="flex flex-1 items-center gap-4 truncate">
              {recentLogs.length > 0 ? (
                recentLogs.map((entry, idx) => (
                  <span key={idx} className="truncate">
                    <span className="text-foreground">[{entry.stage}]</span> {entry.status}{" "}
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
    </section>
  );
}
