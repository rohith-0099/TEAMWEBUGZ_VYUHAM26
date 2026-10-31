// The source registry, fetched from GET /api/sources (backend/app/sources.py). Never copied by hand.
"use client";

import { useQuery } from "@tanstack/react-query";
import { getSources } from "@/lib/api";
import type { Source, SourceRule } from "@/lib/types";

export function useSources() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["sources"],
    queryFn: getSources,
    staleTime: Infinity,
  });
  const sources = data?.sources ?? {};
  const rules = data?.rules ?? {};
  const glossary = data?.glossary ?? {};
  return {
    sources,
    rules,
    glossary,
    isLoading,
    isError,
    source: (key?: string | null): Source | undefined => (key ? sources[key] : undefined),
    rule: (reason?: string | null): SourceRule | undefined => (reason ? rules[reason] : undefined),
  };
}
