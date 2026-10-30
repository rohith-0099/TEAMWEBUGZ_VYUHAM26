"use client";

import { arc } from "d3-shape";
import { useId } from "react";

const SIZE = 240;
const SEGMENTS = 40;

// Segmented half-dial. Lit segments glow; the number is what you actually read.
export function NeonGauge({ value, label, color = "#22F0FF" }: { value: number; label: string; color?: string }) {
  const id = useId().replace(/:/g, "");
  const clamped = Math.max(0, Math.min(100, value));
  const lit = Math.round((clamped / 100) * SEGMENTS);
  const shape = arc<number>()
    .innerRadius(84)
    .outerRadius(108)
    .startAngle((i) => -Math.PI / 2 + (i / SEGMENTS) * Math.PI + 0.012)
    .endAngle((i) => -Math.PI / 2 + ((i + 1) / SEGMENTS) * Math.PI - 0.012);
  const segments = Array.from({ length: SEGMENTS }, (_, i) => i);

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE / 2 + 28}`} role="img" aria-label={`${label}: ${Math.round(clamped)} percent`} className="w-full max-w-72">
      <defs>
        <filter id={`${id}-glow`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="5" />
        </filter>
      </defs>
      <g transform={`translate(${SIZE / 2},${SIZE / 2 + 8})`}>
        {segments.map((i) => (
          <path key={i} d={shape(i) ?? ""} fill="#1F1F1F" />
        ))}
        <g filter={`url(#${id}-glow)`} opacity={0.8}>
          {segments.slice(0, lit).map((i) => (
            <path key={i} d={shape(i) ?? ""} fill={color} />
          ))}
        </g>
        {segments.slice(0, lit).map((i) => (
          <path key={i} d={shape(i) ?? ""} fill={color} style={{ transition: "fill 300ms" }} />
        ))}
        <text textAnchor="middle" y={-8} fontSize={46} fill="#F5F5F7" fontFamily="var(--font-geist-mono)" style={{ fontVariantNumeric: "tabular-nums" }}>
          {Math.round(clamped)}
          <tspan fontSize={18} fill="#8A8A93">%</tspan>
        </text>
        <text textAnchor="middle" y={14} fontSize={12} fill="#8A8A93" fontFamily="var(--font-inter)">
          {label}
        </text>
      </g>
    </svg>
  );
}
