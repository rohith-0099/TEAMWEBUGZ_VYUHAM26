"use client";
// Methodology & sources. Every rule and reference comes from GET /api/sources.

import { ExternalLink } from "lucide-react";
import { useSources } from "@/lib/sources";
import type { SourceRule } from "@/lib/types";

const STEPS = [
  ["Read the report", "Text is taken from the URL, PDF or pasted text and cleaned up. Text inside the report's own images (and scanned PDF pages) is read with Tesseract OCR and added in clearly labelled blocks. Nothing else is added."],
  ["Check for prompt injection", "Rules and one AI check look for text that tries to give orders to an AI (ATT&CK T1698 / T1699)."],
  ["Extract indicators", "IPs, domains, URLs, hashes and CVEs are found by fixed rules, including defanged ones like evil[.]com. Noise is filtered by the rules below and kept visible."],
  ["Find attacker behaviours", "An AI lists each attacker action together with the exact sentence that describes it."],
  ["Map to ATT&CK v20", "Each behaviour is compared with official ATT&CK v20 technique descriptions. A verifier keeps only matches the sentence really supports."],
  ["Hard checks", "Code rejects any technique ID that is not in ATT&CK v20 and any quote that is not in the report. These rejections are counted as hallucinations blocked."],
  ["Connect and remember", "Indicators are linked to the techniques they take part in, and compared with earlier reports."],
];

const LIMITATIONS = [
  "AI steps can miss behaviours that are described only vaguely. Missing techniques are possible; made-up IDs and quotes are not.",
  "Indicator roles (C2, payload…) are AI judgements backed by a quote, not lookups in threat feeds.",
  "OCR can misread characters, so indicators found only in image text are marked \"From image (OCR) — verify\", and hashes from images that aren't a clean hex string of the right length are dropped.",
  "Some filters are our own rules with no external standard. They are labelled \"Project rule\" and the filtered items stay visible.",
  "The map appears only when an offline GeoIP database is installed; IPs it cannot place are not shown.",
];

function RuleTable({ title, rules }: { title: string; rules: [string, SourceRule][] }) {
  const { source } = useSources();
  return (
    <section className="flex flex-col gap-3 rounded-[20px] border bg-card p-5">
      <h2 className="console-title">{title}</h2>
      <ul className="flex flex-col divide-y divide-border">
        {rules.map(([reason, r]) => (
          <li key={reason} className="flex flex-col gap-1 py-3 text-sm">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-semibold">{r.label}</span>
              <code className="font-mono text-[11px] text-muted-foreground">{reason}</code>
            </div>
            <p className="text-muted-foreground">{r.rule}</p>
            <div className="flex flex-wrap gap-3 text-xs">
              {r.source_keys.length === 0 && <span className="text-muted-foreground">Project rule (no external standard)</span>}
              {r.source_keys.map((k) => {
                const s = source(k);
                return s ? (
                  <a key={k} href={s.url} target="_blank" rel="noopener noreferrer"
                     className="inline-flex items-center gap-1 text-primary hover:underline">
                    {s.publisher}: {s.title} <ExternalLink className="size-3" aria-hidden />
                  </a>
                ) : null;
              })}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function HowItWorksPage() {
  const { sources, rules, isLoading, isError } = useSources();
  const entries = Object.entries(rules);

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-8 sm:px-6">
      <header className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl font-semibold">How it works</h1>
        <p className="text-sm text-muted-foreground">
          What TRINETRA does with a report, every rule it applies, and the public source behind each rule.
        </p>
      </header>

      <section className="flex flex-col gap-3 rounded-[20px] border bg-card p-5">
        <h2 className="console-title">Pipeline</h2>
        <ol className="flex flex-col gap-3 text-sm">
          {STEPS.map(([name, text], i) => (
            <li key={name} className="flex gap-3">
              <span className="font-mono text-muted-foreground">{i + 1}.</span>
              <span><span className="font-semibold">{name}.</span> <span className="text-muted-foreground">{text}</span></span>
            </li>
          ))}
        </ol>
      </section>

      {isLoading && <p className="text-sm text-muted-foreground">Loading rules and sources…</p>}
      {isError && (
        <p className="text-sm text-destructive">
          Couldn&apos;t load the rules from the backend. Check that the API is running, then reload this page.
        </p>
      )}

      {entries.length > 0 && (
        <>
          <RuleTable title="Indicator filters" rules={entries.filter(([, r]) => r.kind === "ioc_filter")} />
          <RuleTable title="Why a technique is rejected" rules={entries.filter(([, r]) => r.kind === "technique_reject")} />
          <section className="flex flex-col gap-3 rounded-[20px] border bg-card p-5">
            <h2 className="console-title">Data sources and references</h2>
            <ul className="flex flex-col gap-2 text-sm">
              {Object.entries(sources).map(([k, s]) => (
                <li key={k}>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary hover:underline">
                    {s.title}
                  </a>{" "}
                  <span className="text-muted-foreground">({s.publisher}). {s.why}</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

      <section className="flex flex-col gap-3 rounded-[20px] border bg-card p-5">
        <h2 className="console-title">Limitations</h2>
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
          {LIMITATIONS.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </section>
    </div>
  );
}
