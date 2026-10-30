import { NeuronField } from "@/components/charts";
import { ActivityBars } from "@/components/input/ActivityBars";
import { IdleRadar } from "@/components/input/IdleRadar";
import { InputCard } from "@/components/input/InputCard";
import { RecentAnalyses } from "@/components/input/RecentAnalyses";

// Home: input + idle radar, then recent reports + activity. Owner: Frontend A, see team/01_FRONTEND_A.md §4.2.
export default function HomePage() {
  return (
    <div className="relative min-h-[calc(100dvh-3.5rem)] overflow-hidden">
      <NeuronField />
      <main className="relative mx-auto flex max-w-6xl flex-col gap-10 px-4 py-10 sm:px-6 lg:py-14">
        <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
          <div className="flex min-w-0 flex-col gap-6">
            <div className="flex flex-col gap-3">
              <h1 className="text-4xl font-semibold tracking-tight xl:text-5xl">
                Threat reports in.
                <br />
                Verified intelligence out.
              </h1>
              <p className="max-w-xl text-balance text-muted-foreground">
                Every technique is proven by the report&apos;s own words. No invented IDs, no invented quotes.
              </p>
            </div>
            <InputCard />
          </div>
          <div className="mx-auto w-full max-w-md lg:max-w-none">
            <IdleRadar />
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <section className="flex min-w-0 flex-col gap-3">
            <h2 className="console-title">Recent reports</h2>
            <RecentAnalyses />
          </section>
          <section className="flex min-w-0 flex-col gap-3">
            <h2 className="console-title">Activity</h2>
            <ActivityBars />
          </section>
        </div>
      </main>
    </div>
  );
}
