"use client";

import { area, curveBasis } from "d3-shape";
import { scaleLinear } from "d3-scale";
import { useId } from "react";

export type RidgeRow = { key: string; label: string; color: string; samples: number[] };

const WIDTH = 720;
const ROW = 64;
const LEFT = 92;
const RIGHT = 16;
const BANDWIDTH = 0.09;
const GRID = 60;

function density(samples: number[], at: number): number {
  return samples.reduce((sum, s) => sum + Math.exp(-0.5 * ((at - s) / BANDWIDTH) ** 2), 0) / Math.max(samples.length, 1);
}

// Score distributions (0..1), one ridge per system, overlapping slightly like a mountain range.
export function Ridgeline({ rows, ariaLabel }: { rows: RidgeRow[]; ariaLabel: string }) {
  const id = useId().replace(/:/g, "");
  const height = ROW * rows.length + 46;
  const x = scaleLinear([0, 1], [LEFT, WIDTH - RIGHT]);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const grid = Array.from({ length: GRID + 1 }, (_, i) => i / GRID);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={ariaLabel} className="w-full">
      <defs>
        {rows.map((row) => (
          <linearGradient key={row.key} id={`${id}-${row.key}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={row.color} stopOpacity={0.75} />
            <stop offset="100%" stopColor={row.color} stopOpacity={0.05} />
          </linearGradient>
        ))}
      </defs>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={10} y2={height - 22} stroke="#1F1F1F" />
          <text x={x(t)} y={height - 6} textAnchor="middle" fontSize={11} fill="#8A8A93" fontFamily="var(--font-geist-mono)">
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      {rows.map((row, i) => {
        const base = ROW * (i + 1) + 14;
        const peak = Math.max(0.001, ...grid.map((g) => density(row.samples, g)));
        const shape = area<number>()
          .x((g) => x(g))
          .y0(base)
          .y1((g) => base - (density(row.samples, g) / peak) * (ROW + 10))
          .curve(curveBasis)(grid) ?? "";
        return (
          <g key={row.key}>
            <path d={shape} fill={`url(#${id}-${row.key})`} stroke={row.color} strokeWidth={1.5} />
            <line x1={LEFT} x2={WIDTH - RIGHT} y1={base} y2={base} stroke="#1F1F1F" />
            <text x={0} y={base - 4} fontSize={13} fill="#F5F5F7" fontFamily="var(--font-inter)">
              {row.label}
            </text>
            {row.samples.map((s, j) => (
              <line key={j} x1={x(s)} x2={x(s)} y1={base} y2={base + 5} stroke={row.color} />
            ))}
          </g>
        );
      })}
    </svg>
  );
}
