"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { createAnalysis } from "@/lib/api";

// Placeholder home. Owner: Frontend A, see team/01_FRONTEND_A.md 4.2.
export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyze() {
    setBusy(true);
    setError(null);
    try {
      const { id } = await createAnalysis(url ? { url } : { text });
      router.push(`/report/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed to start");
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16">
      <h1 className="text-3xl font-semibold">Analyze a threat report</h1>
      <p className="text-muted-foreground">
        Paste a report URL or its text. Every technique is proven by a quote from the report.
      </p>
      <Input
        placeholder="https://..."
        aria-label="Report URL"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
      />
      <Textarea
        placeholder="Or paste the report text"
        aria-label="Report text"
        rows={8}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {error && <p className="text-destructive">{error}</p>}
      <Button className="self-start" disabled={busy || (!url && !text)} onClick={analyze}>
        {busy ? "Starting..." : "Analyze"}
      </Button>
    </main>
  );
}
