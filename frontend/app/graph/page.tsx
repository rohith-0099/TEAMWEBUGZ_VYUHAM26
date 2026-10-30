"use client";
// Owner: Frontend B — see team/02_FRONTEND_B.md §5
import dynamic from "next/dynamic";

const MemoryGraphPage = dynamic(
  () => import("@/components/memory-graph/MemoryGraphPage"),
  { ssr: false }
);

export default function GraphPage() {
  return <MemoryGraphPage />;
}
