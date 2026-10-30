// Tactic helpers and color calculation. Owner: Frontend A. See team/01_FRONTEND_A.md §3.5.
"use client";

import { useEffect, useMemo, useState } from "react";
import { getTactics } from "@/lib/api";
import type { Tactic } from "@/lib/types";

export function tacticColor(ord: number): string {
  return `hsl(${ord * 24}, 70%, 60%)`;
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
    return t ? tacticColor(t.ord) : "hsl(215, 15%, 50%)"; // neutral grey fallback
  };

  const getName = (shortname: string): string => {
    return byShortname[shortname]?.name ?? shortname;
  };

  return { tactics, byShortname, getColor, getName };
}
