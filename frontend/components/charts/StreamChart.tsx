"use client";

import { area, curveMonotoneX } from "d3-shape";
import { scaleLinear, scalePoint } from "d3-scale";
import { useId, useMemo } from "react";
import { PillMarker } from "./PillMarker";

// One checkpoint in the filter. `removed` is how many leave the stream here.
export type StreamStage = { label: string; removed: number; color?: string };

const WIDTH = 960;
const HEIGHT = 220;
const PAD_X = 56;
const TOP = 34;
const BOTTOM = 34;

// Nested bands around a surviving core. Each rejection band runs from the left and pinches
// out at the checkpoint that removed it, so you can see where the hallucinations stopped.
export function StreamChart({
  survivors,
  stages,
  progress,
  ariaLabel,
}: {
  survivors: number;
  stages: StreamStage[];
  /** How many checkpoints have finished; the stream fills to there. Omit for all. */
  progress?: number;
  ariaLabel: string;
}) {
  const id = useId().replace(/:/g, "");
  const columns = useMemo(() => ["start", ...stages.map((_, i) => String(i))], [stages]);
  const x = useMemo(() => scalePoint(columns, [PAD_X, WIDTH - PAD_X]), [columns]);

  const totals = useMemo(() => {
    const removedAfter = (column: number) =>
      stages.slice(column).reduce((sum, s) => sum + s.removed, 0);
    return columns.map((_, column) => survivors + removedAfter(column));
  }, [columns, stages, survivors]);

  const max = Math.max(1, ...totals);
  const mid = (HEIGHT + TOP - BOTTOM) / 2;
  const half = (HEIGHT - TOP - BOTTOM) / 2;
  const y = scaleLinear([0, max], [0, half]);

  // Band edges at each column, stacked symmetrically outward from the core.
  const bands = useMemo(() => {
    const widthAt = (bandIndex: number, column: number) => {
      if (bandIndex === 0) return survivors;
      return column <= bandIndex - 1 ? stages[bandIndex - 1].removed : 0;
    };
    const layers = [{ color: "url(#core)", key: "core" }, ...stages.map((s, i) => ({ color: s.color ?? "#FF3B5C", key: String(i) }))];
    let inner = columns.map(() => 0);
    return layers.map((layer, bandIndex) => {
      const outer = inner.map((value, column) => value + widthAt(bandIndex, column));
      const lower = inner;
      const path = (sign: 1 | -1) =>
        area<number>()
          .x((_, i) => x(columns[i]) ?? 0)
          .y0((_, i) => mid + sign * y(lower[i]))
          .y1((_, i) => mid + sign * y(outer[i]))
          .curve(curveMonotoneX)(columns.map((_, i) => i)) ?? "";
      inner = outer;
      return { ...layer, top: path(-1), bottom: path(1), bandIndex };
    });
  }, [columns, stages, survivors, mid, x, y]);

  const reached = progress ?? stages.length;
  const clipWidth = reached >= stages.length ? WIDTH : (x(columns[Math.min(reached, stages.length)]) ?? PAD_X);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={ariaLabel} className="w-full">
      <defs>
        <linearGradient id="core" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#3B6BFF" />
          <stop offset="100%" stopColor="#22F0FF" />
        </linearGradient>
        <clipPath id={`${id}-clip`}>
          <rect x={0} y={0} height={HEIGHT} width={clipWidth} style={{ transition: "width 500ms ease-out" }} />
        </clipPath>
      </defs>

      <g clipPath={`url(#${id}-clip)`}>
        {bands.map((band) => (
          <g key={band.key} opacity={band.bandIndex === 0 ? 0.9 : 0.75 - band.bandIndex * 0.08}>
            <path d={band.top} fill={band.color} stroke="#000000" strokeWidth={1} />
            <path d={band.bottom} fill={band.color} stroke="#000000" strokeWidth={1} />
          </g>
        ))}
      </g>

      {columns.map((column, i) => {
        const cx = x(column) ?? 0;
        const stage = i === 0 ? null : stages[i - 1];
        return (
          <g key={column}>
            <line x1={cx} x2={cx} y1={TOP - 12} y2={HEIGHT - BOTTOM + 6} stroke="#000000" strokeWidth={3} />
            <line x1={cx} x2={cx} y1={TOP - 12} y2={HEIGHT - BOTTOM + 6} stroke="#FFFFFF" strokeOpacity={0.14} />
            <PillMarker x={cx} y={TOP - 12} label={String(totals[i])} />
            <text x={cx} y={HEIGHT - 8} textAnchor="middle" fontSize={11} fill="#8A8A93" fontFamily="var(--font-inter)">
              {stage ? stage.label : "Proposed"}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
