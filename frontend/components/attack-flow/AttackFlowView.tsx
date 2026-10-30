"use client";
// Owner: Frontend B — see team/02_FRONTEND_B.md §3
// Attack Flow graph: observed / predicted / unknown nodes, dagre LR layout,
// swimlane bands, node-by-node build animation, embedded simulator.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type ReactFlowInstance,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import { AnimatePresence, motion } from "framer-motion";
import type { FlowNode as FlowNodeData, IOC, ReportAnalysis, TechniqueMatch } from "@/lib/types";
import { simulate } from "@/lib/api";
import { useTactics } from "@/lib/tactics";
import { TacticEdge } from "./TacticEdge";

// ─── colours (§11) ───────────────────────────────────────────────────────────
const C = {
  observed: "#22F0FF",
  predicted: "#A78BFA",
  unknown: "#8A8A93",
  danger: "#FF3B5C",
  warning: "#FFC53D",
  success: "#39FF88",
  bg: "#000000",
  surface: "#0A0A0A",
  raised: "#141414",
  border: "#1F1F1F",
  text: "#F5F5F7",
  muted: "#8A8A93",
};

const IOC_ROLE_COLOR: Record<string, string> = {
  c2: "#FF3B5C",
  payload: "#FF8A1F",
  phishing: "#FFC53D",
  exfil: "#D14DFF",
  victim: "#3B6BFF",
  scanner: "#8A8A93",
  infrastructure: "#22E8A0",
  unknown: "#5A5A63",
};

// ─── node dimensions ─────────────────────────────────────────────────────────
const NODE_W = 220;
const NODE_H = 90;

// ─── dagre layout ────────────────────────────────────────────────────────────
const EDGE_TYPES = { tactic: TacticEdge };
const MAX_ROW_COLUMNS = 8;
const ROW_GAP = 90;
const FIT_VIEW = { padding: 0.15, maxZoom: 1 };

function applyDagre(nodes: Node[], edges: Edge[]) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", ranksep: 80, nodesep: 40 });
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  const placed = nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } };
  });

  // A kill chain runs to 14+ stages; on one line that's unreadable, so it wraps onto a second row.
  const columns = [...new Set(placed.map((n) => n.position.x))].sort((a, b) => a - b);
  if (columns.length <= MAX_ROW_COLUMNS) return placed;
  const perRow = Math.ceil(columns.length / 2);
  const bottom = Math.max(...placed.map((n) => n.position.y)) - Math.min(...placed.map((n) => n.position.y));
  const rowOffset = bottom + NODE_H + ROW_GAP;
  return placed.map((n) => {
    const column = columns.indexOf(n.position.x);
    if (column < perRow) return n;
    return { ...n, position: { x: columns[column - perRow], y: n.position.y + rowOffset } };
  });
}

// React Flow can't draw an edge without a handle at each end.
function FlowPorts() {
  const hidden = { opacity: 0, width: 1, height: 1, minWidth: 0, minHeight: 0, border: "none" };
  return (
    <>
      <Handle type="target" position={Position.Left} isConnectable={false} style={hidden} />
      <Handle type="source" position={Position.Right} isConnectable={false} style={hidden} />
    </>
  );
}

// ─── custom node components ───────────────────────────────────────────────────
type NodeExtraData = {
  flowNode: FlowNodeData;
  technique?: TechniqueMatch;
  iocs: IOC[];
  blocked: boolean;
  affected: boolean;
  simMode: boolean;
  onBlock?: (id: string) => void;
  onOpenDetail?: (t: TechniqueMatch) => void;
};

function ObservedNode({ data }: { data: NodeExtraData }) {
  const { flowNode, technique, iocs, blocked, affected, simMode, onBlock, onOpenDetail } = data;
  const conf = technique?.confidence?.mapping;
  const linkedIocs = iocs.slice(0, 3);
  const extra = iocs.length - 3;

  return (
    <div
      className="relative select-none cursor-pointer"
      style={{
        width: NODE_W,
        minHeight: NODE_H,
        background: C.raised,
        border: `2px solid ${blocked ? C.danger : C.observed}`,
        borderRadius: 8,
        opacity: affected ? 0.25 : 1,
        transition: "opacity 0.3s, border-color 0.2s",
        boxShadow: blocked ? `0 0 12px ${C.danger}80` : `0 0 8px ${C.observed}40`,
        fontFamily: "var(--font-sans, Inter, sans-serif)",
      }}
      onClick={() => {
        if (simMode && onBlock) onBlock(flowNode.id);
        else if (technique && onOpenDetail) onOpenDetail(technique);
      }}
    >
      <FlowPorts />
      {/* tactic colour strip */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: 4,
          background: C.observed,
          borderRadius: "6px 0 0 6px",
        }}
      />
      <div style={{ padding: "8px 10px 8px 14px" }}>
        <div
          style={{
            fontFamily: "var(--font-mono, JetBrains Mono, monospace)",
            fontSize: 10,
            color: C.observed,
            letterSpacing: "0.05em",
          }}
        >
          {flowNode.technique_id ?? ""}
        </div>
        <div style={{ fontSize: 12, fontWeight: 600, color: C.text, marginTop: 2, lineHeight: 1.3 }}>
          {flowNode.label.replace(/^T[\d.]+\s*/, "")}
        </div>
        {/* IOC chips */}
        {linkedIocs.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 4 }}>
            {linkedIocs.map((ioc) => (
              <span
                key={ioc.id}
                title={ioc.display}
                style={{
                  background: `${IOC_ROLE_COLOR[ioc.role] ?? IOC_ROLE_COLOR.unknown}22`,
                  border: `1px solid ${IOC_ROLE_COLOR[ioc.role] ?? IOC_ROLE_COLOR.unknown}`,
                  borderRadius: 4,
                  fontSize: 9,
                  color: IOC_ROLE_COLOR[ioc.role] ?? IOC_ROLE_COLOR.unknown,
                  padding: "1px 4px",
                  maxWidth: 80,
                  overflow: "hidden",
                  whiteSpace: "nowrap",
                  textOverflow: "ellipsis",
                  fontFamily: "var(--font-mono, monospace)",
                }}
              >
                {ioc.display}
              </span>
            ))}
            {extra > 0 && (
              <span style={{ fontSize: 9, color: C.muted }}>+{extra}</span>
            )}
          </div>
        )}
        {/* confidence dot */}
        {conf != null && (
          <div
            title={`Mapping confidence: ${(conf * 100).toFixed(0)}%`}
            style={{
              position: "absolute",
              top: 8,
              right: 8,
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: conf >= 0.85 ? C.success : conf >= 0.6 ? C.warning : C.danger,
            }}
          />
        )}
        {/* blocked overlay */}
        {blocked && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "#FF3B5C30",
              borderRadius: 6,
              fontSize: 22,
              pointerEvents: "none",
            }}
          >
            ✕
          </div>
        )}
        {affected && !blocked && (
          <div
            title="Cut off — no paths reach this node"
            style={{
              position: "absolute",
              top: 4,
              right: 4,
              background: C.muted,
              color: C.bg,
              borderRadius: 3,
              fontSize: 8,
              padding: "1px 3px",
              fontWeight: 700,
            }}
          >
            CUT OFF
          </div>
        )}
      </div>
    </div>
  );
}

function PredictedNode({ data }: { data: NodeExtraData }) {
  const { flowNode, technique } = data;
  const score = technique?.prediction_score;
  return (
    <div
      style={{
        width: NODE_W,
        minHeight: NODE_H,
        background: `${C.raised}BB`,
        border: `2px dashed ${C.predicted}`,
        borderRadius: 8,
        opacity: 0.8,
        fontFamily: "var(--font-sans, Inter, sans-serif)",
        position: "relative",
        padding: "8px 10px 8px 14px",
      }}
      title="Not in the report. Commonly seen with the observed techniques — check your logs."
    >
      <FlowPorts />
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: 4,
          background: `${C.predicted}80`,
          borderRadius: "6px 0 0 6px",
        }}
      />
      <div style={{ fontSize: 9, color: C.predicted, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Hunt for:
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 10,
          color: C.predicted,
        }}
      >
        {flowNode.technique_id ?? ""}
      </div>
      <div style={{ fontSize: 11, fontWeight: 600, color: `${C.text}CC`, marginTop: 2, lineHeight: 1.3 }}>
        {flowNode.label.replace(/^T[\d.]+\s*/, "")}
      </div>
      {score != null && (
        <div style={{ marginTop: 4 }}>
          <div style={{ fontSize: 9, color: C.muted }}>Score: {(score * 100).toFixed(0)}%</div>
          <div
            style={{
              height: 3,
              background: C.border,
              borderRadius: 2,
              marginTop: 2,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${score * 100}%`,
                background: C.predicted,
                borderRadius: 2,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function UnknownNode({ data }: { data: NodeExtraData }) {
  const { flowNode } = data;
  return (
    <div
      style={{
        width: NODE_W,
        minHeight: NODE_H,
        background:
          "repeating-linear-gradient(45deg, #141414, #141414 6px, #1F1F1F 6px, #1F1F1F 12px)",
        border: `2px solid ${C.border}`,
        borderRadius: 8,
        opacity: 0.75,
        fontFamily: "var(--font-sans, Inter, sans-serif)",
        position: "relative",
        padding: "8px 10px 8px 14px",
      }}
      title="Gap in the intelligence — not an observation."
    >
      <FlowPorts />
      <div style={{ fontSize: 9, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Gap — not observed
      </div>
      <div style={{ fontSize: 11, color: C.muted, marginTop: 4, lineHeight: 1.4 }}>
        {flowNode.label}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = {
  observed: ObservedNode as never,
  predicted: PredictedNode as never,
  unknown: UnknownNode as never,
};

// ─── detail side panel ────────────────────────────────────────────────────────
function TechniqueDetailPanel({
  technique,
  onClose,
}: {
  technique: TechniqueMatch;
  onClose: () => void;
}) {
  return (
    <motion.div
      initial={{ x: 40, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 40, opacity: 0 }}
      transition={{ duration: 0.2 }}
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        width: 320,
        height: "100%",
        background: C.surface,
        borderLeft: `1px solid ${C.border}`,
        zIndex: 20,
        overflowY: "auto",
        padding: 16,
        fontFamily: "var(--font-sans, Inter, sans-serif)",
      }}
    >
      <button
        onClick={onClose}
        style={{ float: "right", color: C.muted, background: "none", border: "none", cursor: "pointer", fontSize: 18 }}
      >
        ✕
      </button>
      <div style={{ fontFamily: "var(--font-mono, monospace)", color: C.observed, fontSize: 12 }}>
        {technique.technique_id}
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginTop: 4 }}>
        {technique.name}
      </div>
      <div style={{ fontSize: 11, color: C.muted, marginTop: 4 }}>
        Tactics: {technique.tactics.join(", ")}
      </div>
      {technique.evidence && (
        <div
          style={{
            marginTop: 12,
            background: C.raised,
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            padding: 10,
            fontSize: 12,
            color: C.text,
            fontStyle: "italic",
            lineHeight: 1.5,
          }}
        >
          &ldquo;{technique.evidence.quote}&rdquo;
        </div>
      )}
      {technique.rationale && (
        <div style={{ marginTop: 10, fontSize: 12, color: C.muted, lineHeight: 1.5 }}>
          {technique.rationale}
        </div>
      )}
      {technique.url && (
        <div style={{ marginTop: 10 }}>
          <span style={{ fontSize: 11, color: C.muted }}>ATT&CK: </span>
          <span
            style={{
              fontFamily: "var(--font-mono, monospace)",
              fontSize: 11,
              color: C.observed,
              wordBreak: "break-all",
            }}
          >
            {technique.url}
          </span>
        </div>
      )}
    </motion.div>
  );
}

// ─── simulator result panel ───────────────────────────────────────────────────
import type { SimulateResponse } from "@/lib/types";

function SimResultPanel({
  result,
  onClose,
}: {
  result: SimulateResponse;
  onClose: () => void;
}) {
  const pct = result.broken_pct;
  const color = pct >= 70 ? C.success : pct >= 30 ? C.warning : C.danger;

  return (
    <motion.div
      initial={{ x: 40, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 40, opacity: 0 }}
      transition={{ duration: 0.2 }}
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        width: 320,
        height: "100%",
        background: C.surface,
        borderLeft: `1px solid ${C.border}`,
        zIndex: 20,
        overflowY: "auto",
        padding: 16,
        fontFamily: "var(--font-sans, Inter, sans-serif)",
      }}
    >
      <button
        onClick={onClose}
        style={{ float: "right", color: C.muted, background: "none", border: "none", cursor: "pointer", fontSize: 18 }}
      >
        ✕
      </button>
      <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 12 }}>
        Simulation result
      </div>
      {/* big % */}
      <motion.div
        key={pct}
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        style={{
          fontSize: 48,
          fontWeight: 800,
          color,
          textAlign: "center",
          marginBottom: 4,
          textShadow: `0 0 20px ${color}80`,
        }}
      >
        {pct.toFixed(0)}%
      </motion.div>
      <div style={{ textAlign: "center", color: C.muted, fontSize: 12, marginBottom: 16 }}>
        of attack paths disrupted
        <br />
        <span style={{ fontFamily: "var(--font-mono, monospace)", color: C.text }}>
          {result.broken_paths} / {result.total_paths}
        </span>{" "}
        paths
      </div>

      {/* surviving paths */}
      {result.surviving_paths.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: C.warning, fontWeight: 600, marginBottom: 4 }}>
            Surviving paths ({result.surviving_paths.length})
          </div>
          {result.surviving_paths.slice(0, 3).map((p, i) => (
            <div
              key={i}
              style={{
                fontSize: 10,
                color: C.muted,
                fontFamily: "var(--font-mono, monospace)",
                background: C.raised,
                borderRadius: 4,
                padding: "3px 6px",
                marginBottom: 3,
                wordBreak: "break-all",
              }}
            >
              {p.join(" → ")}
            </div>
          ))}
        </div>
      )}

      {/* countermeasures */}
      {result.countermeasures.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: C.success, fontWeight: 600, marginBottom: 6 }}>
            Countermeasures
          </div>
          {result.countermeasures.map((cm) => (
            <div
              key={cm.id}
              style={{
                background: C.raised,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                padding: "6px 8px",
                marginBottom: 6,
              }}
            >
              <div style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>{cm.name}</div>
              <div style={{ display: "flex", gap: 4, marginTop: 3, flexWrap: "wrap" }}>
                <span
                  style={{
                    fontSize: 9,
                    padding: "1px 5px",
                    borderRadius: 3,
                    background:
                      cm.source === "d3fend" ? "#22F0FF22" : "#A78BFA22",
                    color: cm.source === "d3fend" ? C.observed : C.predicted,
                    border: `1px solid ${cm.source === "d3fend" ? C.observed : C.predicted}`,
                    fontWeight: 600,
                  }}
                >
                  {cm.source === "d3fend" ? "D3FEND" : "ATT&CK Mitigation"}
                </span>
                {cm.derived && (
                  <span
                    style={{
                      fontSize: 9,
                      padding: "1px 5px",
                      borderRadius: 3,
                      background: "#FFC53D22",
                      color: C.warning,
                      border: `1px solid ${C.warning}`,
                    }}
                  >
                    derived
                  </span>
                )}
                <span
                  style={{
                    fontFamily: "var(--font-mono, monospace)",
                    fontSize: 9,
                    color: C.muted,
                  }}
                >
                  {cm.id}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {result.note && (
        <div style={{ fontSize: 10, color: C.muted, fontStyle: "italic" }}>{result.note}</div>
      )}
    </motion.div>
  );
}

// ─── predictions table (below canvas) ────────────────────────────────────────
function PredictionsTable({ predictions }: { predictions: TechniqueMatch[] }) {
  if (predictions.length === 0) return null;
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: 16,
        marginTop: 16,
        fontFamily: "var(--font-sans, Inter, sans-serif)",
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>
        Hunt for these{" "}
        <span style={{ fontSize: 11, color: C.muted, fontWeight: 400 }}>
          — Predicted, not observed
        </span>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${C.border}` }}>
            {["Technique", "Name", "Tactic", "Score", "Why?"].map((h) => (
              <th
                key={h}
                style={{ textAlign: "left", fontSize: 10, color: C.muted, padding: "4px 8px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {predictions.map((p) => (
            <tr key={p.technique_id} style={{ borderBottom: `1px solid ${C.border}20` }}>
              <td style={{ padding: "6px 8px", fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: C.predicted }}>
                {p.technique_id}
              </td>
              <td style={{ padding: "6px 8px", fontSize: 12, color: C.text }}>
                {p.name}
              </td>
              <td style={{ padding: "6px 8px", fontSize: 11, color: C.muted }}>
                {p.tactics[0] ?? "—"}
              </td>
              <td style={{ padding: "6px 8px", minWidth: 80 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ flex: 1, height: 4, background: C.border, borderRadius: 2, overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${(p.prediction_score ?? 0) * 100}%`,
                        background: C.predicted,
                        borderRadius: 2,
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 10, color: C.predicted, minWidth: 28 }}>
                    {((p.prediction_score ?? 0) * 100).toFixed(0)}%
                  </span>
                </div>
              </td>
              <td style={{ padding: "6px 8px" }}>
                <span
                  title={p.rationale}
                  style={{
                    fontSize: 10,
                    color: C.muted,
                    cursor: "help",
                    borderBottom: `1px dashed ${C.muted}`,
                  }}
                >
                  Why?
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── public export ────────────────────────────────────────────────────────────
// ─── main inner component (needs ReactFlowProvider wrapper) ──────────────────
function FlowInner({ analysis }: { analysis: Partial<ReportAnalysis> }) {
  const flow = analysis.flow ?? { nodes: [], edges: [] };

  // Build technique lookup
  const techMap = useMemo(() => {
    const techniques = analysis.techniques ?? [];
    const predictions = analysis.predictions ?? [];
    const m = new Map<string, TechniqueMatch>();
    [...techniques, ...predictions].forEach((t) => m.set(t.technique_id, t));
    return m;
  }, [analysis.techniques, analysis.predictions]);

  // IOC lookup by id
  const iocMap = useMemo(() => {
    const iocs = analysis.iocs ?? [];
    const m = new Map<string, IOC>();
    iocs.forEach((i) => m.set(i.id, i));
    return m;
  }, [analysis.iocs]);

  // ── simulation state ──────────────────────────────────────────────────────
  const [simMode, setSimMode] = useState(false);
  const [blocked, setBlocked] = useState<Set<string>>(new Set());
  const [simResult, setSimResult] = useState<SimulateResponse | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const simDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── detail panel ──────────────────────────────────────────────────────────
  const [detailTech, setDetailTech] = useState<TechniqueMatch | null>(null);

  // ── build animation ────────────────────────────────────────────────────────
  const [visibleCount, setVisibleCount] = useState(0);
  const [animating, setAnimating] = useState(false);
  const prefersReducedMotion = useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  // sort nodes by order for animation
  const sortedFlowNodes = useMemo(
    () => [...flow.nodes].sort((a, b) => a.order - b.order),
    [flow.nodes]
  );

  const runAnimation = useCallback(() => {
    if (prefersReducedMotion || sortedFlowNodes.length === 0) {
      setVisibleCount(sortedFlowNodes.length);
      return;
    }
    setVisibleCount(0);
    setAnimating(true);
    let i = 0;
    const step = () => {
      i++;
      setVisibleCount(i);
      if (i < sortedFlowNodes.length) {
        setTimeout(step, 150);
      } else {
        setAnimating(false);
      }
    };
    setTimeout(step, 150);
  }, [prefersReducedMotion, sortedFlowNodes.length]);

  useEffect(() => {
    runAnimation();
  }, [runAnimation]);

  // visible node ids in animation order
  const visibleIds = useMemo(
    () => new Set(sortedFlowNodes.slice(0, visibleCount).map((n) => n.id)),
    [sortedFlowNodes, visibleCount]
  );

  // ── RF nodes ──────────────────────────────────────────────────────────────
  const buildRfNodes = useCallback(
    (affectedIds: Set<string>): Node[] => {
      return flow.nodes
        .filter((fn) => visibleIds.has(fn.id))
        .map((fn) => {
          const technique = fn.technique_id ? techMap.get(fn.technique_id) : undefined;
          const linkedIocs = (technique?.linked_iocs ?? [])
            .map((id) => iocMap.get(id))
            .filter(Boolean) as IOC[];
          return {
            id: fn.id,
            type: fn.kind,
            position: { x: 0, y: 0 },
            data: {
              flowNode: fn,
              technique,
              iocs: linkedIocs,
              blocked: blocked.has(fn.id),
              affected: affectedIds.has(fn.id),
              simMode,
              onBlock: (id: string) => {
                setBlocked((prev) => {
                  const next = new Set(prev);
                  if (next.has(id)) next.delete(id);
                  else next.add(id);
                  return next;
                });
              },
              onOpenDetail: (t: TechniqueMatch) => {
                if (!simMode) setDetailTech(t);
              },
            } satisfies NodeExtraData,
          };
        });
    },
    [flow.nodes, visibleIds, techMap, iocMap, blocked, simMode]
  );

  const affectedSet = useMemo(
    () => new Set(simResult?.affected_node_ids ?? []),
    [simResult]
  );

  const rawNodes = useMemo(() => buildRfNodes(affectedSet), [buildRfNodes, affectedSet]);

  const { tactics, getColor } = useTactics();
  const flowInstance = useRef<ReactFlowInstance | null>(null);

  const rfEdges: Edge[] = useMemo(() => {
    const tacticOf = (id: string) => flow.nodes.find((n) => n.id === id)?.tactic ?? "";
    return flow.edges
      .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
      .map((e) => {
        const isPredictedTarget = flow.nodes.find((n) => n.id === e.target)?.kind === "predicted";
        const isInfra = e.relation === "uses_infrastructure";
        const isSurviving =
          simResult?.surviving_paths?.some(
            (path) => path.includes(e.source) && path.includes(e.target)
          ) ?? false;

        return {
          id: `${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          type: "tactic",
          animated: isSurviving,
          data: { from: getColor(tacticOf(e.source)), to: getColor(tacticOf(e.target)) },
          style: {
            strokeDasharray: isPredictedTarget || isInfra ? "6 3" : undefined,
            // Otherwise TacticEdge paints a gradient between the two tactics.
            stroke: isSurviving ? C.warning : isPredictedTarget ? C.predicted : undefined,
            strokeWidth: e.relation === "enables" ? 3 : 2,
            opacity: affectedSet.has(e.target) ? 0.3 : 1,
          },
        };
      });
    // getColor changes only when the tactic list loads
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow.edges, flow.nodes, visibleIds, simResult, affectedSet, tactics]);

  // The flow builds node by node, so keep the whole graph framed as it grows.
  useEffect(() => {
    const frame = requestAnimationFrame(() => flowInstance.current?.fitView({ ...FIT_VIEW, duration: 250 }));
    return () => cancelAnimationFrame(frame);
  }, [visibleIds.size]);

  // dagre layout
  const layoutNodes = useMemo(() => applyDagre(rawNodes, rfEdges), [rawNodes, rfEdges]);

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState(layoutNodes);
  const [rfEdgesState, setRfEdges, onEdgesChange] = useEdgesState(rfEdges);

  useEffect(() => {
    setRfNodes(layoutNodes);
  }, [layoutNodes, setRfNodes]);

  useEffect(() => {
    setRfEdges(rfEdges);
  }, [rfEdges, setRfEdges]);

  const onConnect = useCallback(
    (c: Connection) => setRfEdges((eds) => addEdge(c, eds)),
    [setRfEdges]
  );

  // swimlane bands (computed after layout)

  // ── simulate API call ──────────────────────────────────────────────────────
  const analysisId = analysis.report_id ?? "mock-report";

  useEffect(() => {
    if (!simMode) {
      setSimResult(null);
      return;
    }
    if (simDebounceRef.current) clearTimeout(simDebounceRef.current);
    simDebounceRef.current = setTimeout(async () => {
      setSimLoading(true);
      try {
        const res = await simulate(analysisId, Array.from(blocked));
        setSimResult(res);
      } catch {
        // ignore
      } finally {
        setSimLoading(false);
      }
    }, 250);
    return () => {
      if (simDebounceRef.current) clearTimeout(simDebounceRef.current);
    };
  }, [simMode, blocked, analysisId]);

  // ── best single block ──────────────────────────────────────────────────────
  const [bestBlock, setBestBlock] = useState<{ id: string; label: string; pct: number } | null>(
    null
  );
  const [bestLoading, setBestLoading] = useState(false);
  const bestCacheRef = useRef<Map<string, number>>(new Map());

  const runBestBlock = useCallback(async () => {
    setBestLoading(true);
    const observedNodes = flow.nodes
      .filter((n) => n.kind === "observed")
      .slice(0, 15);
    const cache = bestCacheRef.current;
    let best = { id: "", label: "", pct: -1 };
    for (const fn of observedNodes) {
      if (!cache.has(fn.id)) {
        try {
          const r = await simulate(analysisId, [fn.id]);
          cache.set(fn.id, r.broken_pct);
        } catch {
          cache.set(fn.id, 0);
        }
      }
      const pct = cache.get(fn.id) ?? 0;
      if (pct > best.pct) best = { id: fn.id, label: fn.label, pct };
    }
    setBestBlock(best.pct >= 0 ? best : null);
    setBestLoading(false);
  }, [flow.nodes, analysisId]);

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ position: "relative", width: "100%", height: 620, fontFamily: "var(--font-sans, Inter, sans-serif)" }}>
      {/* toolbar */}
      <div
        style={{
          position: "absolute",
          top: 10,
          left: 10,
          zIndex: 10,
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        {/* legend */}
        <div
          style={{
            background: `${C.surface}EE`,
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            padding: "6px 10px",
            display: "flex",
            gap: 12,
            fontSize: 11,
            color: C.text,
            alignItems: "center",
          }}
        >
          <span style={{ color: C.observed }}>● Observed</span>
          <span style={{ color: C.predicted, fontStyle: "italic" }}>◌ Predicted</span>
          <span style={{ color: C.muted }}>▨ Unknown gap</span>
        </div>
      </div>

      {/* top-right controls */}
      <div
        style={{
          position: "absolute",
          top: 10,
          right: simMode || detailTech ? 330 : 10,
          zIndex: 10,
          display: "flex",
          gap: 8,
          transition: "right 0.2s",
        }}
      >
        <button
          onClick={runAnimation}
          disabled={animating}
          style={{
            background: C.raised,
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            color: C.text,
            padding: "5px 12px",
            fontSize: 12,
            cursor: animating ? "not-allowed" : "pointer",
            opacity: animating ? 0.5 : 1,
          }}
        >
          ▶ Replay
        </button>
        <button
          onClick={() => {
            setSimMode((v) => !v);
            if (simMode) {
              setBlocked(new Set());
              setSimResult(null);
              setBestBlock(null);
            }
            setDetailTech(null);
          }}
          style={{
            background: simMode ? `${C.danger}22` : C.raised,
            border: `1px solid ${simMode ? C.danger : C.border}`,
            borderRadius: 6,
            color: simMode ? C.danger : C.text,
            padding: "5px 12px",
            fontSize: 12,
            cursor: "pointer",
            fontWeight: simMode ? 700 : 400,
          }}
        >
          {simMode ? "Exit simulation" : "Simulate defence"}
        </button>
        {simMode && (
          <button
            onClick={runBestBlock}
            disabled={bestLoading}
            style={{
              background: C.raised,
              border: `1px solid ${C.border}`,
              borderRadius: 6,
              color: C.text,
              padding: "5px 12px",
              fontSize: 12,
              cursor: bestLoading ? "wait" : "pointer",
              opacity: bestLoading ? 0.6 : 1,
            }}
          >
            {bestLoading ? "Calculating…" : "Best single block"}
          </button>
        )}
        {simLoading && (
          <span style={{ color: C.muted, fontSize: 11, alignSelf: "center" }}>simulating…</span>
        )}
      </div>

      {/* best block callout */}
      {bestBlock && (
        <div
          style={{
            position: "absolute",
            bottom: 10,
            left: 10,
            zIndex: 10,
            background: C.raised,
            border: `1px solid ${C.success}`,
            borderRadius: 6,
            padding: "8px 12px",
            color: C.success,
            fontSize: 12,
            maxWidth: 340,
          }}
        >
          Best single block:{" "}
          <span style={{ fontFamily: "var(--font-mono, monospace)", fontWeight: 700 }}>
            {bestBlock.label}
          </span>{" "}
          breaks {bestBlock.pct.toFixed(0)}% of paths
        </div>
      )}

      {/* React Flow canvas */}
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdgesState}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={EDGE_TYPES}
        fitView
        fitViewOptions={FIT_VIEW}
        minZoom={0.2}
        onInit={(instance) => {
          flowInstance.current = instance;
        }}
        colorMode="dark"
        proOptions={{ hideAttribution: true }}
        style={{ background: C.bg, "--xy-background-color": C.bg } as React.CSSProperties}
        defaultEdgeOptions={{ animated: false }}
      >
        <Background color={C.border} gap={24} bgColor={C.bg} />
        <Controls />
        <MiniMap
          bgColor="#0A0A0A"
          maskColor="#000000B3"
          nodeColor={(n) => (n.type === "predicted" ? C.predicted : n.type === "unknown" ? C.unknown : C.observed)}
          style={{ border: `1px solid ${C.border}` }}
        />
      </ReactFlow>

      {/* detail / sim panels */}
      <AnimatePresence>
        {detailTech && !simMode && (
          <TechniqueDetailPanel
            key="detail"
            technique={detailTech}
            onClose={() => setDetailTech(null)}
          />
        )}
        {simMode && simResult && (
          <SimResultPanel key="sim" result={simResult} onClose={() => setSimResult(null)} />
        )}
      </AnimatePresence>

      {/* sim mode overlay hint */}
      {simMode && !simResult && (
        <div
          style={{
            position: "absolute",
            bottom: 10,
            right: 10,
            background: `${C.raised}EE`,
            border: `1px solid ${C.danger}`,
            borderRadius: 6,
            padding: "6px 12px",
            fontSize: 11,
            color: C.danger,
            zIndex: 10,
          }}
        >
          Click observed nodes to block them
        </div>
      )}
    </div>
  );
}

export function AttackFlowView({ analysis }: { analysis: Partial<ReportAnalysis> }) {
  return (
    <div>
      <ReactFlowProvider>
        <FlowInner analysis={analysis} />
      </ReactFlowProvider>
      <PredictionsTable predictions={analysis.predictions ?? []} />
    </div>
  );
}
