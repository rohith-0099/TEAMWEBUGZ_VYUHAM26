"use client";
// Owner: Frontend B — see team/02_FRONTEND_B.md §4
// Detection panel: telemetry checklist → readiness gauge → technique table → Sigma viewer.

import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import SyntaxHighlighter from "react-syntax-highlighter";
import { atomOneDark } from "react-syntax-highlighter/dist/esm/styles/hljs";
import { NeonGauge } from "@/components/charts";
import type { Detection, ReportAnalysis, SigmaRule, Telemetry } from "@/lib/types";
import { readiness, exportUrl } from "@/lib/api";
import type { ReadinessResponse } from "@/lib/types";

// ─── colours (§11) ───────────────────────────────────────────────────────────
const C = {
  bg: "#000000",
  surface: "#0A0A0A",
  raised: "#141414",
  border: "#1F1F1F",
  text: "#F5F5F7",
  muted: "#8A8A93",
  observed: "#22F0FF",
  predicted: "#A78BFA",
  success: "#39FF88",
  warning: "#FFC53D",
  danger: "#FF3B5C",
};

// ─── telemetry display config ─────────────────────────────────────────────────
const TELEMETRY_INFO: Record<Telemetry, { label: string; icon: string }> = {
  sysmon: { label: "Sysmon", icon: "" },
  windows_security: { label: "Windows Security Log", icon: "" },
  powershell_scriptblock: { label: "PowerShell Script Block Logging", icon: "" },
  edr: { label: "EDR", icon: "" },
  dns: { label: "DNS logs", icon: "" },
  proxy: { label: "Web proxy logs", icon: "" },
  firewall: { label: "Firewall logs", icon: "" },
  netflow: { label: "NetFlow", icon: "" },
  cloud_audit: { label: "Cloud audit logs", icon: "" },
  email_gateway: { label: "Email gateway", icon: "" },
  linux_auditd: { label: "Linux auditd", icon: "" },
};

const ALL_TELEMETRY = Object.keys(TELEMETRY_INFO) as Telemetry[];

const PRESETS: Record<string, Telemetry[]> = {
  "Typical SME": ["windows_security", "firewall", "email_gateway"],
  "Mature SOC": ALL_TELEMETRY,
  Nothing: [],
};

const LS_KEY = "trinetra_telemetry_selection";

function loadTelemetry(): Telemetry[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw) as Telemetry[];
  } catch {}
  return PRESETS["Typical SME"];
}

function saveTelemetry(sel: Telemetry[]) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(sel));
  } catch {}
}

// ─── Radial readiness gauge ────────────────────────────────────────────────────
function ReadinessGauge({ pct }: { pct: number }) {
  const color = pct >= 70 ? C.success : pct >= 40 ? C.warning : C.danger;
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: 16 }}>
      <NeonGauge value={pct} label="Detection readiness" color={color} />
    </div>
  );
}

// ─── Sigma rule viewer ────────────────────────────────────────────────────────
function SigmaRuleViewer({ rules, analysisId }: { rules: SigmaRule[]; analysisId: string }) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [activeConv, setActiveConv] = useState<string | null>(null);
  if (rules.length === 0) return null;
  const rule = rules[activeIdx];
  const convKeys = Object.keys(rule.conversions);

  const downloadYml = () => {
    const blob = new Blob([rule.yaml], { type: "application/x-yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${rule.title.replace(/\s+/g, "_")}.yml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ marginTop: 12 }}>
      {/* rule tabs */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 8 }}>
        {rules.map((r, i) => (
          <button
            key={i}
            onClick={() => {
              setActiveIdx(i);
              setActiveConv(null);
            }}
            style={{
              background: i === activeIdx ? C.observed + "22" : C.raised,
              border: `1px solid ${i === activeIdx ? C.observed : C.border}`,
              borderRadius: 4,
              color: i === activeIdx ? C.observed : C.muted,
              padding: "3px 8px",
              fontSize: 11,
              cursor: "pointer",
            }}
          >
            {r.title}
          </button>
        ))}
      </div>

      {/* validity badge + kind */}
      <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
        <span
          style={{
            fontSize: 10,
            padding: "2px 7px",
            borderRadius: 4,
            background: rule.valid ? `${C.success}22` : `${C.danger}22`,
            color: rule.valid ? C.success : C.danger,
            border: `1px solid ${rule.valid ? C.success : C.danger}`,
            fontWeight: 700,
          }}
        >
          {rule.valid ? "✓ Valid (pySigma)" : "✗ Invalid"}
        </span>
        <span
          style={{
            fontSize: 10,
            padding: "2px 7px",
            borderRadius: 4,
            background: `${C.predicted}22`,
            color: C.predicted,
            border: `1px solid ${C.predicted}`,
          }}
        >
          {rule.kind === "ioc" ? "IOC rule" : "Behaviour rule"}
        </span>
        {rule.errors.length > 0 && (
          <span style={{ fontSize: 10, color: C.danger }}>
            {rule.errors.join("; ")}
          </span>
        )}
      </div>

      {/* YAML viewer */}
      <div style={{ borderRadius: 6, overflow: "hidden", border: `1px solid ${C.border}` }}>
        {activeConv === null ? (
          <SyntaxHighlighter
            language="yaml"
            style={atomOneDark}
            customStyle={{ margin: 0, fontSize: 11, maxHeight: 260, overflowY: "auto", background: "#000000" }}
          >
            {rule.yaml}
          </SyntaxHighlighter>
        ) : (
          <SyntaxHighlighter
            language="sql"
            style={atomOneDark}
            customStyle={{ margin: 0, fontSize: 11, maxHeight: 260, overflowY: "auto", background: "#000000" }}
          >
            {rule.conversions[activeConv] ?? ""}
          </SyntaxHighlighter>
        )}
      </div>

      {/* conversion sub-tabs + download */}
      <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap", alignItems: "center" }}>
        <button
          onClick={() => setActiveConv(null)}
          style={{
            background: activeConv === null ? `${C.observed}22` : C.raised,
            border: `1px solid ${activeConv === null ? C.observed : C.border}`,
            borderRadius: 4,
            color: activeConv === null ? C.observed : C.muted,
            padding: "2px 7px",
            fontSize: 10,
            cursor: "pointer",
          }}
        >
          YAML
        </button>
        {convKeys.map((k) => (
          <button
            key={k}
            onClick={() => setActiveConv(k)}
            style={{
              background: activeConv === k ? `${C.observed}22` : C.raised,
              border: `1px solid ${activeConv === k ? C.observed : C.border}`,
              borderRadius: 4,
              color: activeConv === k ? C.observed : C.muted,
              padding: "2px 7px",
              fontSize: 10,
              cursor: "pointer",
            }}
          >
            {k}
          </button>
        ))}
        {activeConv !== null && (
          <button
            onClick={() => {
              navigator.clipboard.writeText(rule.conversions[activeConv!] ?? "").catch(() => {});
            }}
            style={{
              background: C.raised,
              border: `1px solid ${C.border}`,
              borderRadius: 4,
              color: C.muted,
              padding: "2px 7px",
              fontSize: 10,
              cursor: "pointer",
            }}
          >
            Copy
          </button>
        )}
        <button
          onClick={downloadYml}
          style={{
            marginLeft: "auto",
            background: C.raised,
            border: `1px solid ${C.border}`,
            borderRadius: 4,
            color: C.muted,
            padding: "2px 7px",
            fontSize: 10,
            cursor: "pointer",
          }}
        >
          Download .yml
        </button>
        <a
          href={exportUrl(analysisId, "sigma")}
          style={{
            background: C.raised,
            border: `1px solid ${C.border}`,
            borderRadius: 4,
            color: C.muted,
            padding: "2px 7px",
            fontSize: 10,
            textDecoration: "none",
          }}
        >
          Download all Sigma
        </a>
      </div>
    </div>
  );
}

// ─── technique row ────────────────────────────────────────────────────────────
function StatusChip({ status }: { status: "covered" | "partial" | "gap" }) {
  const cfg = {
    covered: { bg: `${C.success}22`, color: C.success, label: "Covered" },
    partial: { bg: `${C.warning}22`, color: C.warning, label: "Partial" },
    gap: { bg: `${C.danger}22`, color: C.danger, label: "Gap" },
  }[status];
  return (
    <span
      style={{
        background: cfg.bg,
        color: cfg.color,
        border: `1px solid ${cfg.color}`,
        borderRadius: 4,
        fontSize: 10,
        padding: "2px 7px",
        fontWeight: 700,
      }}
    >
      {cfg.label}
    </span>
  );
}

function TechniqueRow({
  item,
  detection,
  analysisId,
}: {
  item: ReadinessResponse["per_technique"][number];
  detection?: Detection;
  analysisId: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 10px",
          cursor: "pointer",
          borderBottom: `1px solid ${C.border}`,
          background: open ? C.raised : "transparent",
          transition: "background 0.15s",
        }}
      >
        <StatusChip status={item.status} />
        <span
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 11,
            color: C.observed,
            minWidth: 80,
          }}
        >
          {item.technique_id}
        </span>
        <span style={{ flex: 1, fontSize: 12, color: C.text }}>
          {item.technique_name}
        </span>
        {/* have chips */}
        <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
          {item.have.map((t) => (
            <span
              key={t}
              title={TELEMETRY_INFO[t as Telemetry]?.label ?? t}
              style={{
                background: `${C.success}22`,
                border: `1px solid ${C.success}`,
                borderRadius: 3,
                fontSize: 9,
                color: C.success,
                padding: "1px 4px",
              }}
            >
              {TELEMETRY_INFO[t as Telemetry]?.icon ?? t}
            </span>
          ))}
          {item.missing.map((t) => (
            <span
              key={t}
              title={TELEMETRY_INFO[t as Telemetry]?.label ?? t}
              style={{
                background: `${C.danger}22`,
                border: `1px solid ${C.danger}`,
                borderRadius: 3,
                fontSize: 9,
                color: C.danger,
                padding: "1px 4px",
              }}
            >
              {TELEMETRY_INFO[t as Telemetry]?.icon ?? t}
            </span>
          ))}
        </div>
        <span style={{ color: C.muted, fontSize: 12 }}>{open ? "▲" : "▼"}</span>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: "hidden" }}
          >
            <div style={{ padding: "10px 14px 14px", background: `${C.raised}80` }}>
              {/* detection strategies */}
              {detection?.strategies.map((strat) => (
                <div key={strat.id} style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 12, color: C.text, fontWeight: 600, marginBottom: 4 }}>
                    {strat.name}
                    <span
                      style={{
                        marginLeft: 6,
                        fontFamily: "var(--font-mono, monospace)",
                        fontSize: 10,
                        color: C.muted,
                      }}
                    >
                      {strat.id}
                    </span>
                  </div>
                  {strat.analytics.map((an) => (
                    <div
                      key={an.id}
                      style={{
                        background: C.surface,
                        border: `1px solid ${C.border}`,
                        borderRadius: 6,
                        padding: 8,
                        marginBottom: 6,
                      }}
                    >
                      <div style={{ fontSize: 11, color: C.text, marginBottom: 4 }}>
                        {an.name}
                        {an.platforms.length > 0 && (
                          <span style={{ fontSize: 9, color: C.muted, marginLeft: 6 }}>
                            [{an.platforms.join(", ")}]
                          </span>
                        )}
                      </div>
                      {an.log_sources.map((ls, i) => (
                        <div
                          key={i}
                          style={{
                            display: "flex",
                            gap: 6,
                            alignItems: "center",
                            fontSize: 10,
                            color: C.muted,
                            marginTop: 2,
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "var(--font-mono, monospace)",
                              color: C.muted,
                              fontSize: 9,
                            }}
                          >
                            {ls.name}
                          </span>
                          {ls.data_component && (
                            <span style={{ color: C.border }}>→</span>
                          )}
                          {ls.data_component && (
                            <span style={{ color: C.muted, fontSize: 9 }}>{ls.data_component}</span>
                          )}
                          {ls.telemetry && (
                            <span
                              style={{
                                background: `${C.observed}22`,
                                color: C.observed,
                                border: `1px solid ${C.observed}`,
                                borderRadius: 3,
                                padding: "1px 4px",
                                fontSize: 9,
                              }}
                            >
                              {TELEMETRY_INFO[ls.telemetry]?.icon}{" "}
                              {TELEMETRY_INFO[ls.telemetry]?.label ?? ls.telemetry}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              ))}
              {/* Sigma rules */}
              {detection && detection.sigma.length > 0 && (
                <SigmaRuleViewer rules={detection.sigma} analysisId={analysisId} />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────
export function DetectionPanel({ analysis }: { analysis: Partial<ReportAnalysis> }) {
  const detections = analysis.detections ?? [];
  const analysisId = analysis.report_id ?? "mock-report";

  const [selected, setSelected] = useState<Telemetry[]>(loadTelemetry);
  const [readinessData, setReadinessData] = useState<ReadinessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const detMap = new Map(detections.map((d) => [d.technique_id, d]));

  const toggle = (t: Telemetry) => {
    setSelected((prev) => {
      const next = prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t];
      saveTelemetry(next);
      return next;
    });
  };

  const applyPreset = (name: string) => {
    const sel = PRESETS[name];
    setSelected(sel);
    saveTelemetry(sel);
  };

  // debounced API call
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await readiness(analysisId, selected);
        setReadinessData(res);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [selected, analysisId]);

  // sort: gaps first
  const sorted = readinessData
    ? [...readinessData.per_technique].sort((a, b) => {
        const ord = { gap: 0, partial: 1, covered: 2 };
        return ord[a.status] - ord[b.status];
      })
    : [];

  return (
    <div
      style={{
        fontFamily: "var(--font-sans, Inter, sans-serif)",
        color: C.text,
        minHeight: 400,
      }}
    >
      {/* telemetry checklist */}
      <div
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
            Your telemetry
          </div>
          <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
            {Object.keys(PRESETS).map((name) => (
              <button
                key={name}
                onClick={() => applyPreset(name)}
                style={{
                  background: C.raised,
                  border: `1px solid ${C.border}`,
                  borderRadius: 4,
                  color: C.muted,
                  padding: "2px 8px",
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {ALL_TELEMETRY.map((t) => {
            const active = selected.includes(t);
            const info = TELEMETRY_INFO[t];
            return (
              <button
                key={t}
                onClick={() => toggle(t)}
                style={{
                  background: active ? `${C.observed}22` : C.raised,
                  border: `1px solid ${active ? C.observed : C.border}`,
                  borderRadius: 6,
                  color: active ? C.observed : C.muted,
                  padding: "4px 10px",
                  fontSize: 11,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  transition: "background 0.15s, border-color 0.15s, color 0.15s",
                }}
              >
                <span>{info.icon}</span>
                <span>{info.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* readiness gauge + matrix */}
      {readinessData && (
        <div
          style={{
            display: "flex",
            gap: 16,
            alignItems: "flex-start",
            flexWrap: "wrap",
          }}
        >
          <ReadinessGauge pct={readinessData.readiness_pct} />

          <div style={{ flex: 1, minWidth: 300 }}>
            {loading && (
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 8 }}>Recalculating…</div>
            )}
            <div
              style={{
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                overflow: "hidden",
              }}
            >
              {/* table header */}
              <div
                style={{
                  display: "flex",
                  padding: "6px 10px",
                  borderBottom: `1px solid ${C.border}`,
                  background: C.raised,
                  fontSize: 10,
                  color: C.muted,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  gap: 8,
                }}
              >
                <span style={{ minWidth: 70 }}>Status</span>
                <span style={{ minWidth: 80 }}>ID</span>
                <span style={{ flex: 1 }}>Technique</span>
                <span>Coverage</span>
                <span />
              </div>
              <AnimatePresence initial={false}>
                {sorted.map((item) => (
                  <motion.div
                    key={item.technique_id}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <TechniqueRow
                      item={item}
                      detection={detMap.get(item.technique_id)}
                      analysisId={analysisId}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>
      )}

      {/* loading skeleton */}
      {!readinessData && loading && (
        <div style={{ color: C.muted, fontSize: 13 }}>Loading detection readiness…</div>
      )}

      {/* empty state */}
      {!readinessData && !loading && detections.length === 0 && (
        <div style={{ color: C.muted, fontSize: 13 }}>
          No detections available yet. The analysis pipeline will populate this when the detect stage completes.
        </div>
      )}
    </div>
  );
}
