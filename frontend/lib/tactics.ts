// Tactic helpers and color calculation. Owner: Frontend A. See team/01_FRONTEND_A.md §3.5.
"use client";

import { useEffect, useMemo, useState } from "react";
import { getTactics } from "@/lib/api";
import type { Tactic } from "@/lib/types";

// One neon colour per ATT&CK tactic, by matrix order. Names and order still come from the API.
export const TACTIC_COLORS = [
  "#FF3B5C", "#FF5F3B", "#FF8A1F", "#FFB81F", "#FFE14D",
  "#C6F135", "#5CF268", "#22E8A0", "#1FE0D0", "#22C8FF",
  "#3B8CFF", "#6B6BFF", "#9B5CFF", "#D14DFF", "#FF4DB8",
] as const;

export function tacticColor(ord: number): string {
  return TACTIC_COLORS[((ord % TACTIC_COLORS.length) + TACTIC_COLORS.length) % TACTIC_COLORS.length];
}

export function useTactics(): {
  tactics: Tactic[];
  byShortname: Record<string, Tactic>;
  getColor: (shortnameOrOrd: string | number) => string;
  getName: (shortname: string) => string;
} {
  const [tactics, setTactics] = useState<Tactic[]>([]);

  useEffect(() => {
    let active = true;
    getTactics()
      .then((data) => {
        if (active) setTactics(data);
      })
      .catch((err) => {
        console.warn("Failed to load tactics, using fallback:", err);
        if (active) setTactics([]);
      });
    return () => {
      active = false;
    };
  }, []);

  const byShortname = useMemo(() => {
    const map: Record<string, Tactic> = {};
    for (const t of tactics) {
      map[t.shortname] = t;
    }
    return map;
  }, [tactics]);

  const getColor = (shortnameOrOrd: string | number): string => {
    if (typeof shortnameOrOrd === "number") {
      return tacticColor(shortnameOrOrd);
    }
    const t = byShortname[shortnameOrOrd];
    return t ? tacticColor(t.ord) : "#5A5A63"; // neutral grey fallback
  };

  const getName = (shortname: string): string => {
    return byShortname[shortname]?.name ?? shortname;
  };

  return { tactics, byShortname, getColor, getName };
}
