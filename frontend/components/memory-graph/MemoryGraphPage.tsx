"use client";
// Owner: Frontend B — see team/02_FRONTEND_B.md §5
// Memory graph: sigma.js + graphology, ForceAtlas2, time slider, alert sidebar.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SigmaContainer, useLoadGraph, useRegisterEvents } from "@react-sigma/core";
import "@react-sigma/core/lib/style.css";
import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import FA2Layout from "graphology-layout-forceatlas2/worker";
import { motion, AnimatePresence } from "framer-motion";
import { getGraph } from "@/lib/api";
import type { GraphResponse } from "@/lib/types";
import { ContradictionCard } from "./ContradictionCard";

// ─── colours ──────────────────────────────────────────────────────────────────
const C = {
  bg: "#07090D",
  surface: "#0E1117",
  raised: "#151A22",
  border: "#232A35",
  text: "#E6EDF3",
  muted: "#8B95A5",
  observed: "#22D3EE",
  predicted: "#A78BFA",
  danger: "#F87171",
  warning: "#FBBF24",
  success: "#34D399",
};

const NODE_TYPE_COLOR: Record<string, string> = {
  report: "#E6EDF3",
  ioc: "#22D3EE",
  technique: "#A78BFA",
  actor: "#F87171",
  malware: "#FB923C",
  sector: "#60A5FA",
};

function nodeColor(type: string): string {
  return NODE_TYPE_COLOR[type] ?? C.muted;
}

interface LoaderProps {
  data: GraphResponse;
  filterTypes: Set<string>;
  minReports: number;
  atDate: string | null;
  onClickNode: (id: string) => void;
  onHoverNode: (id: string | null) => void;
}

function GraphLoader({ data, filterTypes, minReports, atDate, onClickNode, onHoverNode }: LoaderProps) {
  const loadGraph = useLoadGraph();
  const registerEvents = useRegisterEvents();
  const fa2Ref = useRef<FA2Layout | null>(null);

  const buildGraph = useCallback(() => {
    const g = new Graph({ multi: false });

    // filter nodes
    const visibleNodes = new Set<string>();
    for (const n of data.nodes) {
      if (!filterTypes.has(n.type)) continue;
      if (n.report_count < minReports) continue;
      // time filter
      if (atDate) {
        const d = new Date(atDate);
        if (n.first_seen && new Date(n.first_seen) > d) continue;
      }
      visibleNodes.add(n.id);
    }

    for (const n of data.nodes) {
      if (!visibleNodes.has(n.id)) continue;
      const size = 4 + Math.min(n.report_count * 3, 16);
      g.addNode(n.id, {
        label: n.label,
        size,
        color: nodeColor(n.type),
        x: Math.random() * 500,
        y: Math.random() * 500,
        _meta: n,
      });
    }

    for (const e of data.edges) {
      if (!visibleNodes.has(e.source) || !visibleNodes.has(e.target)) continue;
      if (g.hasEdge(e.source, e.target)) continue;
      g.addEdge(e.source, e.target, {
        label: e.relation,
        size: 1,
        color: `${C.border}`,
        _meta: e,
      });
    }

    loadGraph(g);

    // run ForceAtlas2
    if (fa2Ref.current) fa2Ref.current.stop();
    const fa2 = new FA2Layout(g, {
      settings: forceAtlas2.inferSettings(g),
    });
    fa2.start();
    fa2Ref.current = fa2;
    setTimeout(() => {
      if (fa2Ref.current) fa2Ref.current.stop();
    }, 2000);

    return () => {
      if (fa2Ref.current) fa2Ref.current.stop();
    };
  }, [data, filterTypes, minReports, atDate, loadGraph]);

  useEffect(() => {
    const cleanup = buildGraph();
    return cleanup;
  }, [buildGraph]);

  // events
  useEffect(() => {
    registerEvents({
      clickNode: ({ node }) => onClickNode(node),
      enterNode: ({ node }) => {
        onHoverNode(node);
      },
      leaveNode: () => {
        onHoverNode(null);
      },
    });
  }, [registerEvents, onClickNode, onHoverNode]);

  return null;
}

// ─── node detail drawer ────────────────────────────────────────────────────────
function NodeDrawer({
  nodeId,
  data,
  onClose,
}: {
  nodeId: string;
  data: GraphResponse;
  onClose: () => void;
}) {
  const node = data.nodes.find((n) => n.id === nodeId);
  if (!node) return null;

  const edges = data.edges.filter(
    (e) => e.source === nodeId || e.target === nodeId
  );
  const relatedReportIds = new Set(edges.map((e) => e.report_id).filter(Boolean) as string[]);
  const reports = data.nodes.filter((n) => n.type === "report" && relatedReportIds.has(n.id));

  return (
    <motion.div
      initial={{ x: 320, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 320, opacity: 0 }}
      transition={{ duration: 0.2 }}
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        width: 300,
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
        style={{
          float: "right",
          color: C.muted,
          background: "none",
          border: "none",
          cursor: "pointer",
          fontSize: 18,
        }}
      >
        ✕
      </button>
      <div
        style={{
          display: "inline-block",
          background: `${nodeColor(node.type)}22`,
          border: `1px solid ${nodeColor(node.type)}`,
          borderRadius: 4,
          padding: "2px 7px",
          fontSize: 10,
          color: nodeColor(node.type),
          marginBottom: 8,
          fontWeight: 600,
          textTransform: "uppercase",
        }}
      >
        {node.type}
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 13,
          color: C.text,
          fontWeight: 600,
          wordBreak: "break-all",
          marginBottom: 8,
        }}
      >
        {node.label}
      </div>
      {node.first_seen && (
        <div style={{ fontSize: 11, color: C.muted, marginBottom: 2 }}>
          First seen: {new Date(node.first_seen).toLocaleDateString()}
        </div>
      )}
      {node.last_seen && (
        <div style={{ fontSize: 11, color: C.muted, marginBottom: 8 }}>
          Last seen: {new Date(node.last_seen).toLocaleDateString()}
        </div>
      )}
      <div style={{ fontSize: 11, color: C.muted, marginBottom: 12 }}>
        Report count: {node.report_count}
      </div>

      {/* relationships */}
      {edges.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.text, marginBottom: 6 }}>
            Relationships
          </div>
          {edges.map((e) => {
            const other = e.source === nodeId ? e.target : e.source;
            const otherNode = data.nodes.find((n) => n.id === other);
            return (
              <div
                key={e.id}
                style={{
                  fontSize: 10,
                  color: C.muted,
                  borderLeft: `2px solid ${C.border}`,
                  paddingLeft: 6,
                  marginBottom: 4,
                }}
              >
                <span style={{ color: C.observed }}>{e.relation}</span>{" "}
                <span
                  style={{
                    fontFamily: "var(--font-mono, monospace)",
                    color: C.text,
                    fontSize: 10,
                  }}
                >
                  {otherNode?.label ?? other}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* reports */}
      {reports.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.text, marginBottom: 6 }}>
            Appears in reports
          </div>
          {reports.map((r) => (
            <a
              key={r.id}
              href={`/report/${r.id}`}
              style={{
                display: "block",
                fontSize: 11,
                color: C.observed,
                marginBottom: 4,
                textDecoration: "underline",
                wordBreak: "break-all",
              }}
            >
              {r.label}
            </a>
          ))}
        </div>
      )}
    </motion.div>
  );
}

// ─── main memory graph page ───────────────────────────────────────────────────
export default function MemoryGraphPage() {
  const [data, setData] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // filters
  const [filterTypes, setFilterTypes] = useState<Set<string>>(
    new Set(["report", "ioc", "technique", "actor", "malware", "sector"])
  );
  const [minReports, setMinReports] = useState(1);
  const [search, setSearch] = useState("");

  // selected node
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // time slider
  const [atDate, setAtDate] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const playRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // date range from data
  const dateRange = useMemo(() => {
    if (!data) return { min: "", max: "" };
    const dates = data.nodes
      .flatMap((n) => [n.first_seen, n.last_seen])
      .filter(Boolean)
      .map((d) => new Date(d!).getTime());
    if (dates.length === 0) return { min: "", max: "" };
    return {
      min: new Date(Math.min(...dates)).toISOString().slice(0, 10),
      max: new Date(Math.max(...dates)).toISOString().slice(0, 10),
    };
  }, [data]);

  useEffect(() => {
    getGraph()
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  // play animation
  useEffect(() => {
    if (!playing || !dateRange.min || !dateRange.max) return;
    const start = new Date(dateRange.min).getTime();
    const end = new Date(dateRange.max).getTime();
    const step = (end - start) / 30;
    let current = start;
    const tick = () => {
      current += step;
      if (current >= end) {
        setAtDate(new Date(end).toISOString().slice(0, 10));
        setPlaying(false);
        return;
      }
      setAtDate(new Date(current).toISOString().slice(0, 10));
      playRef.current = setTimeout(tick, 300);
    };
    playRef.current = setTimeout(tick, 300);
    return () => {
      if (playRef.current) clearTimeout(playRef.current);
    };
  }, [playing, dateRange]);

  const toggleType = (type: string) => {
    setFilterTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  if (loading) {
    return (
      <main
        style={{
          background: C.bg,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: C.muted,
          fontFamily: "var(--font-sans, Inter, sans-serif)",
        }}
      >
        Loading memory graph…
      </main>
    );
  }

  if (error || !data) {
    return (
      <main
        style={{
          background: C.bg,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: C.danger,
          fontFamily: "var(--font-sans, Inter, sans-serif)",
        }}
      >
        {error ?? "Failed to load graph"}
      </main>
    );
  }

  const allAlerts = data.alerts;

  return (
    <main
      style={{
        background: C.bg,
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        fontFamily: "var(--font-sans, Inter, sans-serif)",
        color: C.text,
      }}
    >
      {/* header */}
      <div
        style={{
          padding: "16px 24px",
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          gap: 12,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <div style={{ fontSize: 18, fontWeight: 700, color: C.text }}>
          🧠 Memory Graph
        </div>
        <div style={{ fontSize: 12, color: C.muted }}>
          {data.nodes.length} nodes · {data.edges.length} edges
        </div>
        {/* search */}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search nodes…"
          style={{
            background: C.raised,
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            color: C.text,
            padding: "4px 10px",
            fontSize: 12,
            outline: "none",
            width: 200,
          }}
        />
        {/* node type filters */}
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {Object.keys(NODE_TYPE_COLOR).map((type) => (
            <button
              key={type}
              onClick={() => toggleType(type)}
              style={{
                background: filterTypes.has(type) ? `${NODE_TYPE_COLOR[type]}22` : C.raised,
                border: `1px solid ${filterTypes.has(type) ? NODE_TYPE_COLOR[type] : C.border}`,
                borderRadius: 4,
                color: filterTypes.has(type) ? NODE_TYPE_COLOR[type] : C.muted,
                padding: "2px 8px",
                fontSize: 10,
                cursor: "pointer",
                textTransform: "capitalize",
              }}
            >
              {type}
            </button>
          ))}
        </div>
        {/* min reports filter */}
        <label style={{ fontSize: 11, color: C.muted, display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={minReports > 1}
            onChange={(e) => setMinReports(e.target.checked ? 2 : 1)}
            style={{ accentColor: C.observed }}
          />
          Only entities seen in ≥2 reports
        </label>
      </div>

      {/* main content */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* left sidebar: alerts */}
        <div
          style={{
            width: 300,
            borderRight: `1px solid ${C.border}`,
            padding: 12,
            overflowY: "auto",
            background: C.surface,
            flexShrink: 0,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>
            Alerts ({allAlerts.length})
          </div>
          {allAlerts.length === 0 ? (
            <div style={{ fontSize: 12, color: C.muted }}>No alerts across the stored reports.</div>
          ) : (
            allAlerts.map((alert, i) => (
              <ContradictionCard key={i} alert={alert} />
            ))
          )}
        </div>

        {/* graph canvas */}
        <div style={{ flex: 1, position: "relative", minHeight: 500 }}>
          <SigmaContainer
            style={{ width: "100%", height: "100%", background: C.bg }}
            options={{
              settings: {
                renderLabels: true,
                enableEdgeEvents: false,
              },
            }}
          >
            <GraphLoader
              data={data}
              filterTypes={filterTypes}
              minReports={minReports}
              atDate={atDate}
              onClickNode={(id) => setSelectedNode(selectedNode === id ? null : id)}
              onHoverNode={() => {}}
            />
          </SigmaContainer>

          {/* right node drawer */}
          <AnimatePresence>
            {selectedNode && (
              <NodeDrawer
                key={selectedNode}
                nodeId={selectedNode}
                data={data}
                onClose={() => setSelectedNode(null)}
              />
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* time slider */}
      {dateRange.min && dateRange.max && (
        <div
          style={{
            padding: "12px 24px",
            borderTop: `1px solid ${C.border}`,
            background: C.surface,
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <button
            onClick={() => {
              if (playing) {
                setPlaying(false);
                if (playRef.current) clearTimeout(playRef.current);
              } else {
                setAtDate(dateRange.min);
                setPlaying(true);
              }
            }}
            style={{
              background: playing ? `${C.danger}22` : C.raised,
              border: `1px solid ${playing ? C.danger : C.border}`,
              borderRadius: 6,
              color: playing ? C.danger : C.text,
              padding: "4px 12px",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            {playing ? "⏸ Pause" : "▶ Play"}
          </button>
          <span style={{ fontSize: 11, color: C.muted, minWidth: 70 }}>
            {dateRange.min}
          </span>
          <input
            type="range"
            min={new Date(dateRange.min).getTime()}
            max={new Date(dateRange.max).getTime()}
            value={atDate ? new Date(atDate).getTime() : new Date(dateRange.min).getTime()}
            onChange={(e) => {
              setPlaying(false);
              setAtDate(new Date(parseInt(e.target.value)).toISOString().slice(0, 10));
            }}
            style={{ flex: 1, accentColor: C.observed }}
          />
          <span style={{ fontSize: 11, color: C.muted, minWidth: 70 }}>
            {dateRange.max}
          </span>
          {atDate && (
            <span
              style={{
                fontSize: 12,
                fontFamily: "var(--font-mono, monospace)",
                color: C.observed,
                minWidth: 100,
              }}
            >
              {atDate}
            </span>
          )}
          {atDate && (
            <button
              onClick={() => setAtDate(null)}
              style={{
                background: "none",
                border: "none",
                color: C.muted,
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              ✕ Reset
            </button>
          )}
        </div>
      )}
    </main>
  );
}

