// Faint branching filaments behind the home page. Seeded so server and client render the same.
function rng(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
}

function filaments(): { d: string; soma: [number, number] }[] {
  const random = rng(20261030);
  const result: { d: string; soma: [number, number] }[] = [];
  for (let n = 0; n < 16; n++) {
    const sx = random() * 1600;
    const sy = random() * 1000;
    let d = "";
    for (let b = 0; b < 5; b++) {
      let x = sx;
      let y = sy;
      let angle = random() * Math.PI * 2;
      d += `M${x.toFixed(1)} ${y.toFixed(1)}`;
      for (let s = 0; s < 6; s++) {
        angle += (random() - 0.5) * 0.9;
        const length = 26 + random() * 46;
        const nx = x + Math.cos(angle) * length;
        const ny = y + Math.sin(angle) * length;
        d += `Q${(x + nx) / 2 + (random() - 0.5) * 20} ${(y + ny) / 2 + (random() - 0.5) * 20} ${nx.toFixed(1)} ${ny.toFixed(1)}`;
        x = nx;
        y = ny;
      }
    }
    result.push({ d, soma: [sx, sy] });
  }
  return result;
}

const FILAMENTS = filaments();

export function NeuronField() {
  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox="0 0 1600 1000"
      preserveAspectRatio="xMidYMid slice"
    >
      {FILAMENTS.map((f, i) => (
        <g key={i}>
          <path d={f.d} fill="none" stroke="#3B6BFF" strokeOpacity={0.13} strokeWidth={0.8} />
          <circle cx={f.soma[0]} cy={f.soma[1]} r={2.4} fill="#3B6BFF" fillOpacity={0.3} />
        </g>
      ))}
    </svg>
  );
}
