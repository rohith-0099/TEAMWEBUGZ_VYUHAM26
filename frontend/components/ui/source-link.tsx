// "Source" link + one-line why for any reason that carries a source_key. Owner: Frontend A.
"use client";

import { ExternalLink } from "lucide-react";
import { useSources } from "@/lib/sources";
import { cn } from "@/lib/utils";

type Props = {
  /** The item's own source_key; falls back to the rule's single source. */
  sourceKey?: string | null;
  /** A filtered_reason / reject_reason, used for the plain-English label and fallback source. */
  reason?: string | null;
  showWhy?: boolean;
  className?: string;
};

export function SourceLink({ sourceKey, reason, showWhy = true, className }: Props) {
  const { source, rule } = useSources();
  const r = rule(reason);
  const key = sourceKey ?? (r?.source_keys.length === 1 ? r.source_keys[0] : null);
  const s = source(key);

  if (!s) {
    // No external standard behind it: say so instead of inventing one.
    return r && r.source_keys.length === 0 ? (
      <span className={cn("text-[10px] text-muted-foreground", className)} title={r.rule}>
        Project rule{showWhy ? ` · ${r.rule}` : ""}
      </span>
    ) : null;
  }

  return (
    <span className={cn("inline-flex flex-wrap items-baseline gap-x-1.5 text-[10px] text-muted-foreground", className)}>
      <a
        href={s.url}
        target="_blank"
        rel="noopener noreferrer"
        title={`${s.title} (${s.publisher})`}
        className="inline-flex items-center gap-0.5 font-medium text-primary underline-offset-2 hover:underline"
      >
        Source <ExternalLink className="size-2.5" aria-hidden />
      </a>
      {showWhy && <span>{s.why}</span>}
    </span>
  );
}
