import { ShieldCheck, Sparkles } from "lucide-react";
import { InputCard } from "@/components/input/InputCard";
import { RecentAnalyses } from "@/components/input/RecentAnalyses";

// Home: hero + input card + recent analyses. Owner: Frontend A, see team/01_FRONTEND_A.md §4.2.
export default function HomePage() {
  return (
    <div className="bg-grid-glow relative min-h-[calc(100dvh-3.5rem)]">
      <main className="relative mx-auto flex max-w-2xl flex-col gap-10 px-6 py-16 sm:py-24">
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
            <ShieldCheck className="size-3.5" aria-hidden="true" /> ATT&amp;CK v20 · evidence-grounded
          </span>
          <h1 className="text-balance font-heading text-4xl font-semibold tracking-tight sm:text-5xl">
            Threat reports in.{" "}
            <span className="text-primary drop-shadow-[0_0_18px_color-mix(in_oklch,var(--primary),transparent_40%)]">
              Verified intelligence
            </span>{" "}
            out.
          </h1>
          <p className="max-w-lg text-balance text-muted-foreground">
            Every technique is proven by the report&apos;s own words — no hallucinated IDs, no invented
            quotes. Paste a report and watch the pipeline work in real time.
          </p>
        </div>

        <InputCard />

        <section className="flex flex-col gap-3">
          <h2 className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
            <Sparkles className="size-3.5" aria-hidden="true" /> Recent analyses
          </h2>
          <RecentAnalyses />
        </section>
      </main>
    </div>
  );
}
