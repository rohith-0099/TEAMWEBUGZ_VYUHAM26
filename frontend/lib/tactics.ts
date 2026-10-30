// Tactic helpers. STUB — owner: Frontend A. See team/01_FRONTEND_A.md 3.5.
// TODO(Frontend A): move useTactics onto react-query. Never hard-code tactic names.
"use client";

import { useEffect, useState } from "react";
import { getTactics } from "@/lib/api";
import type { Tactic } from "@/lib/types";

export function tacticColor(ord: number): string {
  return `hsl(${ord * 24}, 70%, 60%)`;
}

export function useTactics(): Tactic[] {
  const [tactics, setTactics] = useState<Tactic[]>([]);
  useEffect(() => {
    getTactics().then(setTactics).catch(() => setTactics([]));
  }, []);
  return tactics;
}
