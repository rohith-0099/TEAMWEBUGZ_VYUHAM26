"use client";

import { arc, curveCatmullRomClosed, lineRadial } from "d3-shape";
import { useId, useMemo } from "react";
import { tacticColor } from "@/lib/tactics";

export type RadarPoint = { shortname: string; name: string; ord: number; value: number };

const SIZE = 420;
const CENTER = SIZE / 2;
const OUTER = 150;
const FLOOR = 0.12; // keeps the shape closed and legible when a tactic has no techniques

// 15 tactic spokes. The outline takes each tactic's colour as it passes that spoke:
// a ring of colour wedges is masked by the spline, so the line itself is the spectrum.
export function NeonRadar({
  points,
  idle = false,
  caption,
}: {
  points: RadarPoint[];
  idle?: boolean;
  caption?: string;
}) {
  const id = useId().replace(/:/g, "");
  const count = points.length;
  const step = (2 * Math.PI) / Math.max(count, 1);
  const max = Math.max(1, ...points.map((p) => p.value));

  const shape = useMemo(() => {
    const radius = (p: RadarPoint, i: number) => {
      if (idle) return OUTER * (0.32 + 0.16 * Math.abs(Math.sin(i * 1.7)));
      return OUTER * Math.max(FLOOR, Math.sqrt(p.value / max));
    };
    return lineRadial<RadarPoint>()
      .angle((_, i) => i * step)
      .radius(radius)
      .curve(curveCatmullRomClosed.alpha(0.5))(points) ?? "";
  }, [points, idle, max, step]);

  const wedge = arc<number>()
    .innerRadius(0)
    .outerRadius(OUTER + 24)
    .startAngle((i) => (i - 0.5) * step)
    .endAngle((i) => (i + 0.5) * step);

  const covered = points.filter((p) => p.value > 0);
  const label =
    caption ??
    (idle
      ? "ATT&CK tactic radar, waiting for a report"
      : `ATT&CK tactic coverage: ${covered.length} of ${count} tactics. ${covered.map((p) => `${p.name} ${p.value}`).join(", ")}`);

  if (count === 0) return <div className="aspect-square w-full" aria-hidden="true" />;

  const wedges = points.map((p, i) => (
    <path key={p.shortname} d={wedge(i) ?? ""} fill={tacticColor(p.ord)} />
  ));

  return (
    <svg viewBox={`-90 0 ${SIZE + 180} ${SIZE}`} role="img" aria-label={label} className="h-full w-full">
      <defs>
        <mask id={`${id}-line`} maskUnits="userSpaceOnUse" x="0" y="0" width={SIZE} height={SIZE}>
          <path d={shape} transform={`translate(${CENTER},${CENTER})`} fill="none" stroke="#FFF" strokeWidth={2.5} />
        </mask>
        <mask id={`${id}-fill`} maskUnits="userSpaceOnUse" x="0" y="0" width={SIZE} height={SIZE}>
          <path d={shape} transform={`translate(${CENTER},${CENTER})`} fill="#FFF" />
        </mask>
        <filter id={`${id}-glow`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>

      {[0.25, 0.5, 0.75, 1].map((r) => (
        <circle key={r} cx={CENTER} cy={CENTER} r={OUTER * r} fill="none" stroke="#1F1F1F" />
      ))}
      {points.map((p, i) => {
        const angle = i * step - Math.PI / 2;
        const x = CENTER + Math.cos(angle) * OUTER;
        const y = CENTER + Math.sin(angle) * OUTER;
        const lx = CENTER + Math.cos(angle) * (OUTER + 10);
        const ly = CENTER + Math.sin(angle) * (OUTER + 10);
        const anchor = Math.abs(Math.cos(angle)) < 0.2 ? "middle" : Math.cos(angle) > 0 ? "start" : "end";
        const active = !idle && p.value > 0;
        return (
          <g key={p.shortname}>
            <line x1={CENTER} y1={CENTER} x2={x} y2={y} stroke="#1F1F1F" />
            <text
              x={lx}
              y={ly}
              dy="0.35em"
              textAnchor={anchor}
              fontSize={10}
              fontFamily="var(--font-inter)"
              fill={active ? tacticColor(p.ord) : "#5A5A63"}
            >
              {p.name}
              <title>{`${p.name}: ${p.value}`}</title>
            </text>
          </g>
        );
      })}

      <g className="reveal-grow">
        <g mask={`url(#${id}-fill)`} opacity={idle ? 0.06 : 0.14}>
          <g transform={`translate(${CENTER},${CENTER})`}>{wedges}</g>
        </g>
        <g filter={`url(#${id}-glow)`} opacity={idle ? 0.35 : 0.9}>
          <g mask={`url(#${id}-line)`}>
            <g transform={`translate(${CENTER},${CENTER})`}>{wedges}</g>
          </g>
        </g>
        <g mask={`url(#${id}-line)`} opacity={idle ? 0.55 : 1}>
          <g transform={`translate(${CENTER},${CENTER})`}>{wedges}</g>
        </g>
      </g>
    </svg>
  );
}
