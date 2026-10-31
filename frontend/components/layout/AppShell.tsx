// Professional application shell: sidebar + top bar + content workspace. Owner: Frontend A.
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { USE_MOCKS } from "@/lib/api";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        {USE_MOCKS && (
          <div role="status" className="sticky top-0 z-50 bg-amber-400 px-4 py-1.5 text-center text-sm font-bold tracking-wide text-black">
            MOCK DATA: nothing on this screen comes from a real analysis
          </div>
        )}
        <TopBar />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
