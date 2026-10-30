"use client";
// Owner: Frontend B — see team/02_FRONTEND_B.md §6
// Scoreboard/eval page: proof of accuracy vs baseline.

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Ridgeline } from "@/components/charts";
import { getEval } from "@/lib/api";
import type { EvalResponse } from "@/lib/types";

// ─── colours ──────────────────────────────────────────────────────────────────
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

// ─── animated bar ─────────────────────────────────────────────────────────────
function MetricBar({
  value,
  color,
  label,
}: {
  value: number;
  color: string;
  label: string;
}) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 11, color: C.muted }}>{label}</span>
        <span style={{ fontSize: 12, color, fontWeight: 700 }}>
          {(value * 100).toFixed(1)}%
        </span>
      </div>
      <div
        style={{ height: 6, background: C.border, borderRadius: 3, overflow: "hidden" }}
      >
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value * 100}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          style={{ height: "100%", background: color, borderRadius: 3 }}
        />
      </div>
    </div>
  );
}

function reportF1({ tp, fp, fn }: { tp: string[]; fp: string[]; fn: string[] }): number {
  const denominator = 2 * tp.length + fp.length + fn.length;
  return denominator ? (2 * tp.length) / denominator : 0;
}

// ─── system card ──────────────────────────────────────────────────────────────
function SystemCard({
  system,
  otherF1,
}: {
  system: EvalResponse["systems"][number];
  otherF1: number;
}) {
  const isTrinetra = system.system === "trinetra";
  const diff = isTrinetra ? system.f1 - otherF1 : otherF1 - system.f1;
  const color = isTrinetra ? C.observed : C.muted;

  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${isTrinetra ? C.observed : C.border}`,
        borderRadius: 20,
        padding: 20,
        flex: 1,
        minWidth: 240,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: isTrinetra ? C.observed : C.text }}>
            {isTrinetra ? "TRINETRA" : "Plain LLM"}
          </div>
          <div style={{ fontFamily: "var(--font-geist-mono)", fontSize: 64, lineHeight: 1.1, color, fontVariantNumeric: "tabular-nums" }}>
            {system.f1.toFixed(2)}
          </div>
          <div style={{ fontSize: 12, color: C.muted }}>F1 score</div>
        </div>
        {diff !== 0 && (
          <div
            style={{
              marginLeft: "auto",
              fontSize: 13,
              fontWeight: 700,
              color: diff > 0 ? C.success : C.danger,
              background: diff > 0 ? `${C.success}22` : `${C.danger}22`,
              border: `1px solid ${diff > 0 ? C.success : C.danger}`,
              borderRadius: 6,
              padding: "3px 8px",
            }}
          >
            {diff > 0 ? "+" : ""}{(diff * 100).toFixed(1)} F1
          </div>
        )}
      </div>
      <MetricBar value={system.precision} color={color} label="Precision" />
      <MetricBar value={system.recall} color={color} label="Recall" />
            <MetricBar value={system.parent_f1} color={`${color}BB`} label="Parent-level F1" />
      <div style={{ marginTop: 10, fontSize: 11, color: C.muted }}>
        Avg latency:{" "}
        <span style={{ color: C.text, fontFamily: "var(--font-mono, monospace)" }}>
          {system.avg_latency_ms.toLocaleString()} ms
        </span>
      </div>
    </div>
  );
}

// ─── per-report row ───────────────────────────────────────────────────────────
function ReportRow({ report }: { report: EvalResponse["per_report"][number] }) {
  const [open, setOpen] = useState(false);

  const tpB = report.baseline.tp.length;
  const fpB = report.baseline.fp.length;
  const fnB = report.baseline.fn.length;
  const tpT = report.trinetra.tp.length;
  const fpT = report.trinetra.fp.length;
  const fnT = report.trinetra.fn.length;

  return (
    <div style={{ borderBottom: `1px solid ${C.border}` }}>
      <div
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          padding: "10px 12px",
          cursor: "pointer",
          background: open ? C.raised : "transparent",
          transition: "background 0.15s",
        }}
      >
        <a
          href={report.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          style={{ fontSize: 12, color: C.observed, flex: 1, wordBreak: "break-all" }}
        >
          {report.title}
        </a>
        {/* baseline */}
        <div style={{ display: "flex", gap: 4, minWidth: 100 }}>
          <Chip label={`TP:${tpB}`} color={C.success} />
          <Chip label={`FP:${fpB}`} color={C.danger} />
          <Chip label={`FN:${fnB}`} color={C.muted} />
        </div>
        {/* trinetra */}
        <div style={{ display: "flex", gap: 4, minWidth: 100 }}>
          <Chip label={`TP:${tpT}`} color={C.success} />
          <Chip label={`FP:${fpT}`} color={C.danger} />
          <Chip label={`FN:${fnT}`} color={C.muted} />
        </div>
        <span style={{ color: C.muted, fontSize: 12 }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={{ padding: "8px 20px 14px", display: "flex", gap: 20, flexWrap: "wrap" }}>
          <TechniqueChips label="Baseline" counts={report.baseline} />
          <TechniqueChips label="TRINETRA" counts={report.trinetra} />
        </div>
      )}
    </div>
  );
}

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        fontSize: 9,
        fontFamily: "var(--font-mono, monospace)",
        background: `${color}22`,
        border: `1px solid ${color}`,
        color,
        borderRadius: 4,
        padding: "1px 5px",
        fontWeight: 700,
      }}
    >
      {label}
    </span>
  );
}

function TechniqueChips({
  label,
  counts,
}: {
  label: string;
  counts: { tp: string[]; fp: string[]; fn: string[] };
}) {
  return (
    <div style={{ flex: 1, minWidth: 200 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: C.text, marginBottom: 6 }}>
        {label}
      </div>
      {counts.tp.length > 0 && (
        <div style={{ marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: C.success, fontWeight: 600 }}>TP (correct): </span>
          <span style={{ display: "inline-flex", gap: 3, flexWrap: "wrap" }}>
            {counts.tp.map((id) => (
              <span
                key={id}
                style={{
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 9,
                  background: `${C.success}22`,
                  border: `1px solid ${C.success}`,
                  color: C.success,
                  borderRadius: 3,
                  padding: "1px 4px",
                }}
              >
                {id}
              </span>
            ))}
          </span>
        </div>
      )}
      {counts.fp.length > 0 && (
        <div style={{ marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: C.danger, fontWeight: 600 }}>
            FP (hallucinated/wrong):{" "}
          </span>
          <span style={{ display: "inline-flex", gap: 3, flexWrap: "wrap" }}>
            {counts.fp.map((id) => (
              <span
                key={id}
                style={{
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 9,
                  background: `${C.danger}22`,
                  border: `1px solid ${C.danger}`,
                  color: C.danger,
                  borderRadius: 3,
                  padding: "1px 4px",
                  textDecoration: "line-through",
                }}
              >
                {id}
              </span>
            ))}
          </span>
        </div>
      )}
      {counts.fn.length > 0 && (
        <div>
          <span style={{ fontSize: 9, color: C.muted, fontWeight: 600 }}>FN (missed): </span>
          <span style={{ display: "inline-flex", gap: 3, flexWrap: "wrap" }}>
            {counts.fn.map((id) => (
              <span
                key={id}
                style={{
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 9,
                  background: `${C.muted}22`,
                  border: `1px solid ${C.muted}`,
                  color: C.muted,
                  borderRadius: 3,
                  padding: "1px 4px",
                }}
              >
                {id}
              </span>
            ))}
          </span>
        </div>
      )}
    </div>
  );
}

// ─── main scoreboard component ────────────────────────────────────────────────
export function ScoreboardPage() {
  const [evalData, setEvalData] = useState<EvalResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    getEval()
      .then((d) => {
        setEvalData(d);
        // detect mock flag
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setIsMock(!!(d as any)._mock);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

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
        Loading scoreboard…
      </main>
    );
  }

  if (error || !evalData) {
    return (
      <main
        style={{
          background: C.bg,
          minHeight: "100vh",
          padding: 24,
          fontFamily: "var(--font-sans, Inter, sans-serif)",
          color: C.text,
        }}
      >
        <h1 className="console-title">Scoreboard</h1>
        No evaluation has been run yet.
        {!evalData && (
          <div style={{ color: C.muted, fontSize: 12, marginTop: 8 }}>
            Run{" "}
            <code
              style={{
                fontFamily: "var(--font-mono, monospace)",
                background: C.raised,
                padding: "2px 6px",
                borderRadius: 4,
              }}
            >
              python scripts/run_eval.py
            </code>{" "}
            to generate results.
          </div>
        )}
      </main>
    );
  }

  const baseline = evalData.systems.find((s) => s.system === "baseline");
  const trinetra = evalData.systems.find((s) => s.system === "trinetra");

  return (
    <main
      style={{
        background: C.bg,
        minHeight: "100vh",
        fontFamily: "var(--font-sans, Inter, sans-serif)",
        color: C.text,
        padding: "24px",
        maxWidth: 1100,
        margin: "0 auto",
      }}
    >
      {/* MOCK ribbon */}
      {isMock && (
        <div
          style={{
            background: `${C.warning}22`,
            border: `1px solid ${C.warning}`,
            borderRadius: 6,
            padding: "8px 16px",
            fontSize: 12,
            color: C.warning,
            fontWeight: 700,
            marginBottom: 16,
            textAlign: "center",
          }}
        >
          Mock data. These numbers are for development only. Run the real eval before the demo.
        </div>
      )}

      {/* hero */}
      <div style={{ textAlign: "center", marginBottom: 32 }}>
        <div
          style={{
            fontSize: 32,
            fontWeight: 800,
            color: C.text,
            marginBottom: 6,
          }}
        >
          Measured, not claimed.
        </div>
        <div style={{ fontSize: 14, color: C.muted }}>
          {evalData.reports} report{evalData.reports !== 1 ? "s" : ""} evaluated,{" "}
          <span style={{ fontFamily: "var(--font-mono, monospace)", color: C.muted }}>
            {new Date(evalData.ran_at).toLocaleString()}
          </span>
        </div>
      </div>

      {/* system cards */}
      <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
        {evalData.systems.map((sys) => (
          <SystemCard
            key={sys.system}
            system={sys}
            otherF1={
              sys.system === "trinetra"
                ? baseline?.f1 ?? 0
                : trinetra?.f1 ?? 0
            }
          />
        ))}
      </div>

      {/* explanation strip */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginBottom: 24,
          flexWrap: "wrap",
        }}
      >
        {[
          { label: "Ground truth = ATT&CK tables published in CISA advisories" },
          { label: "Precision = how many claimed techniques were right" },
          { label: "Recall = how many real techniques we found" },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              flex: 1,
              minWidth: 200,
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              padding: "12px 16px",
              display: "flex",
              gap: 10,
              alignItems: "flex-start",
            }}
          >
            <span style={{ fontSize: 12, color: C.muted, lineHeight: 1.4 }}>{item.label}</span>
          </div>
        ))}
      </div>

      {/* score distribution */}
      <section className="mb-6 flex flex-col gap-3 rounded-[20px] border bg-card p-4">
        <h2 className="console-title">F1 across reports</h2>
        <Ridgeline
          ariaLabel="Distribution of per-report F1 scores for the plain LLM and for TRINETRA"
          rows={[
            { key: "baseline", label: "Plain LLM", color: "#8A8A93", samples: evalData.per_report.map((r) => reportF1(r.baseline)) },
            { key: "trinetra", label: "TRINETRA", color: "#22F0FF", samples: evalData.per_report.map((r) => reportF1(r.trinetra)) },
          ]}
        />
      </section>

      {/* per-report table */}
      <div
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 12,
            padding: "8px 12px",
            borderBottom: `1px solid ${C.border}`,
            background: C.raised,
            fontSize: 10,
            color: C.muted,
            fontWeight: 600,
          }}
        >
          <span style={{ flex: 1 }}>Report</span>
          <span style={{ minWidth: 100 }}>Baseline</span>
          <span style={{ minWidth: 100 }}>TRINETRA</span>
          <span style={{ width: 20 }} />
        </div>
        {evalData.per_report.map((r) => (
          <ReportRow key={r.report_id} report={r} />
        ))}
      </div>
    </main>
  );
}

