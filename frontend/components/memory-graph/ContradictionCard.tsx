// STUB — owner: Frontend B. See team/02_FRONTEND_B.md section 5.
import type { MemoryAlert } from "@/lib/types";

export function ContradictionCard({ alert }: { alert: MemoryAlert }) {
  return <p className="text-muted-foreground">Coming soon: {alert.message}</p>;
}
