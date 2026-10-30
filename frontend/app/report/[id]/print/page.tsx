"use client";

import { use, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PrintReport } from "@/components/print-report";
import { getAnalysis } from "@/lib/api";
import { useAnalysisStore } from "@/lib/store";
import type { ReportAnalysis } from "@/lib/types";

export default function PrintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const autoPrint = searchParams.get("auto") === "1";

  const storeAnalysis = useAnalysisStore((state) => state.analysis);
  const [analysis, setAnalysis] = useState<ReportAnalysis | null>(
    storeAnalysis.report_id === id ? (storeAnalysis as ReportAnalysis) : null
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysis) {
      getAnalysis(id)
        .then(setAnalysis)
        .catch((e: Error) => setError(e.message));
    }
  }, [id, analysis]);

  if (error) {
    return <div className="p-8 text-center text-red-600 font-mono">Error: {error}</div>;
  }

  if (!analysis) {
    return <div className="p-8 text-center text-gray-500 font-mono">Loading report for print...</div>;
  }

  return <PrintReport analysis={analysis} autoPrint={autoPrint} />;
}
