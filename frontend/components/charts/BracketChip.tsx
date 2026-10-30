import { cn } from "@/lib/utils";

// A quiet mono tag: [ LLM ], [ T1059.001 ]. Brackets keep it readable without colour.
export function BracketChip({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap font-mono text-[10px] tabular text-muted-foreground", className)}>
      <span aria-hidden="true" className="opacity-50">[</span>
      {children}
      <span aria-hidden="true" className="opacity-50">]</span>
    </span>
  );
}
