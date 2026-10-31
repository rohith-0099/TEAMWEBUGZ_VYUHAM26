// "?" button that explains a term in one plain line, with its source. Text comes from GET /api/sources.
"use client";

import { ExternalLink, HelpCircle } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useSources } from "@/lib/sources";

export function GlossaryHint({ term }: { term: string }) {
  const { glossary, source } = useSources();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();
  const entry = glossary[term];
  const s = source(entry?.source_key);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  if (!entry) return null;

  return (
    <span ref={ref} className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={`What is ${entry.term}?`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="text-muted-foreground hover:text-foreground"
      >
        <HelpCircle className="size-3.5" />
      </button>
      {open && (
        <span
          id={id}
          role="dialog"
          className="absolute left-0 top-5 z-50 flex w-64 flex-col gap-1.5 rounded-lg border bg-popover p-3 text-left text-xs font-normal normal-case tracking-normal text-popover-foreground"
        >
          <span className="font-semibold">{entry.term}</span>
          <span className="text-muted-foreground">{entry.text}</span>
          {s && (
            <a href={s.url} target="_blank" rel="noopener noreferrer"
               className="inline-flex items-center gap-1 text-primary hover:underline">
              Source: {s.publisher} <ExternalLink className="size-3" aria-hidden />
            </a>
          )}
        </span>
      )}
    </span>
  );
}
