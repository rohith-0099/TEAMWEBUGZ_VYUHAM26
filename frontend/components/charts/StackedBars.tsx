"use client";

import { scaleBand, scaleLinear } from "d3-scale";
import { stack } from "d3-shape";

export type StackedSeries = { key: string; label: string; color: string };
export type StackedBar = { key: string; label: string; values: Record<string, number> };

const WIDTH = 480;
const HEIGHT = 170;
const BOTTOM = 26;

export function StackedBars({ bars, series, ariaLabel }: { bars: StackedBar[]; series: StackedSeries[]; ariaLabel: string }) {
  const rows = bars.map((b) => ({ key: b.key, ...b.values }));
  const stacked = stack<Record<string, number | string>>().keys(series.map((s) => s.key)).value((d, k) => Number(d[k] ?? 0))(rows);
  const max = Math.max(1, ...stacked.flatMap((layer) => layer.map((point) => point[1])));
  const x = scaleBand(bars.map((b) => b.key), [0, WIDTH]).padding(0.28);
  const y = scaleLinear([0, max], [HEIGHT - BOTTOM, 6]);

  return (
    <div className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={ariaLabel} className="w-full">
        <line x1={0} x2={WIDTH} y1={HEIGHT - BOTTOM} y2={HEIGHT - BOTTOM} stroke="#1F1F1F" />
        {stacked.map((layer, layerIndex) =>
          layer.map((point, i) => (
            <rect
              key={`${layer.key}-${bars[i].key}`}
              x={x(bars[i].key)}
              y={y(point[1])}
              width={x.bandwidth()}
              height={Math.max(0, y(point[0]) - y(point[1]) - 1)}
              rx={2}
              fill={series[layerIndex].color}
            >
              <title>{`${bars[i].label}: ${series[layerIndex].label} ${point[1] - point[0]}`}</title>
            </rect>
          )),
        )}
        {bars.map((b) => (
          <text key={b.key} x={(x(b.key) ?? 0) + x.bandwidth() / 2} y={HEIGHT - 8} textAnchor="middle" fontSize={11} fill="#8A8A93" fontFamily="var(--font-geist-mono)">
            {b.label}
          </text>
        ))}
      </svg>
      <ul className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="size-2 rounded-sm" style={{ background: s.color }} aria-hidden="true" />
            {s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
