"use client";

import { useEffect } from "react";
import { safeDisplay } from "@/lib/defang";
import type { ReportAnalysis } from "@/lib/types";

interface PrintReportProps {
  analysis: ReportAnalysis;
  autoPrint?: boolean;
}

export function PrintReport({ analysis, autoPrint = false }: PrintReportProps) {
  useEffect(() => {
    if (autoPrint) {
      const timer = setTimeout(() => {
        window.print();
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [autoPrint]);

  const accepted = (analysis.techniques || []).filter((t) => t.status === "accepted");
  const nonFilteredIocs = (analysis.iocs || []).filter((i) => !i.filtered_reason);

  return (
    <div className="mx-auto max-w-4xl bg-white p-8 text-black print:p-0 print:text-black">
      {/* Print Controls (hidden on print) */}
      <div className="mb-6 flex items-center justify-between border-b pb-4 print:hidden">
        <div>
          <h1 className="text-xl font-bold">Executive Threat Intelligence Report</h1>
          <p className="text-xs text-gray-500">TRINETRA · Ground-Truth Verified</p>
        </div>
        <button
          onClick={() => window.print()}
          className="rounded bg-black px-4 py-1.5 text-xs font-semibold text-white hover:bg-gray-800"
        >
          Print / Save PDF
        </button>
      </div>

      {/* Header */}
      <header className="border-b-2 border-black pb-4">
        <div className="flex items-center justify-between">
          <div className="text-2xl font-extrabold tracking-tight">TRINETRA CTI</div>
          <div className="text-right text-xs text-gray-600 font-mono">
            MITRE ATT&CK® v20 Verified
          </div>
        </div>
        <h2 className="mt-3 text-2xl font-bold leading-tight">{analysis.title}</h2>
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-600">
          {analysis.source_url && (
            <span>
              <strong>Source:</strong> {analysis.source_url}
            </span>
          )}
          {analysis.published_at && (
            <span>
              <strong>Published:</strong> {new Date(analysis.published_at).toLocaleDateString()}
            </span>
          )}
          <span>
            <strong>Generated:</strong> {new Date().toLocaleDateString()}
          </span>
        </div>
      </header>

      {/* Summary Metrics */}
      <section className="my-6 grid grid-cols-4 gap-4 border border-gray-300 p-4 text-center">
        <div>
          <div className="text-2xl font-black">{nonFilteredIocs.length}</div>
          <div className="text-xs text-gray-600 uppercase font-mono">Verified IOCs</div>
        </div>
        <div>
          <div className="text-2xl font-black">{accepted.length}</div>
          <div className="text-xs text-gray-600 uppercase font-mono">ATT&CK Techniques</div>
        </div>
        <div>
          <div className="text-2xl font-black">{analysis.memory_alerts?.length || 0}</div>
          <div className="text-xs text-gray-600 uppercase font-mono">Memory Alerts</div>
        </div>
        <div>
          <div className="text-2xl font-black">
            {analysis.injection_flags?.length > 0 ? "Flagged (T1699)" : "Clean"}
          </div>
          <div className="text-xs text-gray-600 uppercase font-mono">Prompt Guard</div>
        </div>
      </section>

      {/* Verified Indicators Table */}
      <section className="my-6 break-after-auto">
        <h3 className="mb-2 border-b border-gray-300 pb-1 text-sm font-bold uppercase tracking-wider">
          Indicators of Compromise (Defanged)
        </h3>
        <table className="w-full text-left text-xs border border-gray-300">
          <thead className="bg-gray-100 font-mono">
            <tr>
              <th className="p-2 border">Type</th>
              <th className="p-2 border">Indicator</th>
              <th className="p-2 border">Role</th>
              <th className="p-2 border">Linked TTPs</th>
            </tr>
          </thead>
          <tbody>
            {nonFilteredIocs.map((ioc) => (
              <tr key={ioc.id} className="border-t">
                <td className="p-2 border font-mono">{ioc.type}</td>
                <td className="p-2 border font-mono font-semibold">{safeDisplay(ioc)}</td>
                <td className="p-2 border uppercase font-mono text-[10px]">{ioc.role}</td>
                <td className="p-2 border font-mono">{ioc.linked_techniques.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* ATT&CK v20 Mappings with Evidence Quotes */}
      <section className="my-6 break-before-auto">
        <h3 className="mb-2 border-b border-gray-300 pb-1 text-sm font-bold uppercase tracking-wider">
          Verified MITRE ATT&CK® v20 Techniques & Evidence
        </h3>
        <div className="space-y-4">
          {accepted.map((tech) => (
            <div key={tech.technique_id} className="border border-gray-300 p-3 rounded">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-mono font-bold text-sm">{tech.technique_id}</span>
                  <span className="ml-2 font-semibold text-sm">{tech.name}</span>
                </div>
                <span className="text-xs font-mono text-gray-600">
                  {tech.tactics.join(", ").toUpperCase()}
                </span>
              </div>

              {tech.evidence && (
                <div className="mt-2 border-l-2 border-gray-400 pl-2 text-xs italic bg-gray-50 p-1.5">
                  &ldquo;{tech.evidence.quote}&rdquo;
                </div>
              )}

              {tech.rationale && (
                <div className="mt-1.5 text-xs text-gray-700">
                  <strong>Rationale:</strong> {tech.rationale}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-12 border-t border-gray-300 pt-4 text-center text-xs text-gray-500 font-mono">
        Generated by TRINETRA CTI · Zero-Hallucination Framework · ATT&CK v20 Ground-Truth Verification
      </footer>
    </div>
  );
}
