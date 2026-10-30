"use client";

import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";

// A pipe that fades from the source tactic's colour into the target's.
export function TacticEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, data, markerEnd }: EdgeProps) {
  const [path] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  const { from, to } = (data ?? {}) as { from?: string; to?: string };
  const gradientId = `tactic-edge-${id.replace(/[^a-zA-Z0-9-]/g, "_")}`;
  return (
    <>
      <defs>
        <linearGradient id={gradientId} gradientUnits="userSpaceOnUse" x1={sourceX} y1={sourceY} x2={targetX} y2={targetY}>
          <stop offset="0%" stopColor={from ?? "#5A5A63"} />
          <stop offset="100%" stopColor={to ?? "#5A5A63"} />
        </linearGradient>
      </defs>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ ...style, stroke: style?.stroke ?? `url(#${gradientId})`, vectorEffect: "non-scaling-stroke" }} />
    </>
  );
}
