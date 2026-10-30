import { cn } from "@/lib/utils";

export type Tile = { key: string; label: string; value: number; color: string };

// One tile per tactic. Empty tactics are hatched as well as dimmed, so colour isn't the only signal.
export function TileGrid({ tiles, ariaLabel }: { tiles: Tile[]; ariaLabel: string }) {
  return (
    <ul aria-label={ariaLabel} className="grid grid-cols-3 gap-2 sm:grid-cols-5">
      {tiles.map((tile) => {
        const active = tile.value > 0;
        return (
          <li
            key={tile.key}
            title={`${tile.label}: ${tile.value}`}
            className={cn("flex min-h-20 flex-col justify-between gap-1 rounded-xl border p-2", !active && "hatched")}
            style={active ? { borderColor: tile.color, backgroundColor: `${tile.color}1F` } : undefined}
          >
            <span className={cn("font-mono text-xl leading-none tabular", !active && "text-muted-foreground")} style={active ? { color: tile.color } : undefined}>
              {tile.value}
            </span>
            <span className={cn("text-[10px] leading-tight", active ? "text-foreground" : "text-muted-foreground")}>{tile.label}</span>
          </li>
        );
      })}
    </ul>
  );
}
