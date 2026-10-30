"use client";
// Owner: Frontend B — see team/02_FRONTEND_B.md §5.3
// ContradictionCard: exported for Frontend A import.

import { motion } from "framer-motion";
import type { MemoryAlert } from "@/lib/types";

const C = {
  surface: "#0A0A0A",
  raised: "#141414",
  border: "#1F1F1F",
  text: "#F5F5F7",
  muted: "#8A8A93",
  warning: "#FFC53D",
  danger: "#FF3B5C",
  success: "#39FF88",
};

export function ContradictionCard({ alert }: { alert: MemoryAlert }) {
  const isContradiction = alert.type === "contradiction";

  if (!isContradiction) {
    // seen_before
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          background: C.raised,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: 12,
          marginBottom: 8,
          fontFamily: "var(--font-sans, Inter, sans-serif)",
        }}
      >
        <div style={{ fontSize: 12, color: C.text, fontWeight: 600, marginBottom: 6 }}>
          
          <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#22F0FF" }}>
            {alert.entity_display}
          </span>{" "}
          appeared in {alert.reports.length} report{alert.reports.length !== 1 ? "s" : ""}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {alert.reports.map((r) => (
            <div key={r.report_id} style={{ fontSize: 11, color: C.muted }}>
              <span style={{ color: C.text }}>{r.title}</span>
              {r.published_at && (
                <span style={{ marginLeft: 6, fontSize: 10 }}>
                  ({new Date(r.published_at).toLocaleDateString()})
                </span>
              )}
              {r.quote && (
                <div
                  style={{
                    fontStyle: "italic",
                    color: C.muted,
                    fontSize: 10,
                    marginTop: 2,
                    borderLeft: `2px solid ${C.border}`,
                    paddingLeft: 6,
                  }}
                >
                  &ldquo;{r.quote}&rdquo;
                </div>
              )}
            </div>
          ))}
        </div>
      </motion.div>
    );
  }

  // contradiction
  const footnoteColor = alert.explained_by_time ? C.warning : C.danger;
  const footnoteMsg = alert.explained_by_time
    ? "Likely explained by time (infrastructure reused/reassigned)"
    : "Genuine conflict — verify before acting";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: C.raised,
        border: `1px solid ${footnoteColor}`,
        borderRadius: 8,
        padding: 12,
        marginBottom: 8,
        fontFamily: "var(--font-sans, Inter, sans-serif)",
        boxShadow: `0 0 8px ${footnoteColor}30`,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 8 }}>
        Conflicting claims about{" "}
        <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#22F0FF" }}>
          {alert.entity_display}
        </span>
      </div>

      {/* two-column report comparison */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {alert.reports.map((r) => (
          <div
            key={r.report_id}
            style={{
              flex: 1,
              minWidth: 160,
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 6,
              padding: 8,
            }}
          >
            <div style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>{r.title}</div>
            {r.published_at && (
              <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
                {new Date(r.published_at).toLocaleDateString()}
              </div>
            )}
            {r.quote && (
              <div
                style={{
                  fontStyle: "italic",
                  color: C.muted,
                  fontSize: 11,
                  marginTop: 6,
                  borderLeft: `2px solid ${C.border}`,
                  paddingLeft: 6,
                  lineHeight: 1.4,
                }}
              >
                &ldquo;{r.quote}&rdquo;
              </div>
            )}
          </div>
        ))}
      </div>

      {/* footer */}
      <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: 11, color: footnoteColor, fontWeight: 600 }}>
          {footnoteMsg}
        </div>
        <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
          Shared infrastructure is not proof of the same operator.
        </div>
      </div>
    </motion.div>
  );
}
