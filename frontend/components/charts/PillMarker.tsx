// A small count pill for use inside SVG charts, sitting on a black vertical line.
export function PillMarker({ x, y, label }: { x: number; y: number; label: string }) {
  const width = Math.max(26, label.length * 7.2 + 14);
  return (
    <g transform={`translate(${x},${y})`}>
      <rect x={-width / 2} y={-10} width={width} height={20} rx={10} fill="#000000" stroke="#FFFFFF" strokeOpacity={0.85} />
      <text textAnchor="middle" dy="0.35em" fill="#FFFFFF" fontSize={11} fontFamily="var(--font-geist-mono)" style={{ fontVariantNumeric: "tabular-nums" }}>
        {label}
      </text>
    </g>
  );
}
