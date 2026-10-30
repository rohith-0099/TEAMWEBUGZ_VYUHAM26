// Live pipeline events subscriber & mock replayer. Owner: Frontend A. See team/01_FRONTEND_A.md §3.3.
"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL, USE_MOCKS, getAnalysis } from "@/lib/api";
import eventsMock from "@/lib/mock/events.json";
import { useAnalysisStore } from "@/lib/store";
import type { PipelineEvent } from "@/lib/types";

function isTerminal(event: PipelineEvent): boolean {
  return event.stage === "pipeline" && (event.status === "done" || event.status === "error");
}

function dedupeKey(e: PipelineEvent): string {
  const dataLen = e.data ? JSON.stringify(e.data).length : 0;
  return `${e.stage}:${e.status}:${e.ts}:${dataLen}`;
}

export function useAnalysisStream(id: string) {
  const applyEvent = useAnalysisStore((state) => state.applyEvent);
  const setFinal = useAnalysisStore((state) => state.setFinal);
  const reset = useAnalysisStore((state) => state.reset);

  const [finished, setFinished] = useState(false);
  const [last, setLast] = useState<PipelineEvent | null>(null);
  const seenEventsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!id) return;

    reset();
    seenEventsRef.current.clear();
    setFinished(false);
    setLast(null);

    let isCancelled = false;

    if (USE_MOCKS) {
      const mockEvents = eventsMock as unknown as PipelineEvent[];
      let index = 0;
      let timer: NodeJS.Timeout | null = null;

      const scheduleNext = () => {
        if (isCancelled || index >= mockEvents.length) return;
        const event = mockEvents[index++];
        if (!event) return;

        applyEvent(event);
        setLast(event);

        if (isTerminal(event)) {
          setFinished(true);
          getAnalysis(id).then((finalAnalysis) => {
            if (!isCancelled) setFinal(finalAnalysis);
          }).catch(console.error);
          return;
        }

        // Realistic delays between stages for smooth UI animation
        let delay = 120;
        if (event.status === "started") delay = 80;
        else if (event.stage === "ingest") delay = 350;
        else if (event.stage === "ioc" || event.stage === "ioc_role") delay = 250;
        else if (event.stage === "behaviours" || event.stage === "verify") delay = 200;
        else if (event.stage === "flow" || event.stage === "detect" || event.stage === "memory") delay = 300;

        timer = setTimeout(scheduleNext, delay);
      };

      timer = setTimeout(scheduleNext, 100);

      return () => {
        isCancelled = true;
        if (timer) clearTimeout(timer);
      };
    }

    // Live backend connection via EventSource
    const eventSource = new EventSource(`${API_URL}/api/analyses/${id}/events`);

    eventSource.onmessage = (message) => {
      if (isCancelled) return;
      try {
        const event: PipelineEvent = JSON.parse(message.data);
        const key = dedupeKey(event);

        if (seenEventsRef.current.has(key)) return;
        seenEventsRef.current.add(key);

        applyEvent(event);
        setLast(event);

        if (isTerminal(event)) {
          setFinished(true);
          eventSource.close();
          getAnalysis(id).then((finalAnalysis) => {
            if (!isCancelled) setFinal(finalAnalysis);
          }).catch(console.error);
        }
      } catch (err) {
        console.error("Failed to parse SSE event:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn("SSE connection error or reconnecting:", err);
    };

    return () => {
      isCancelled = true;
      eventSource.close();
    };
  }, [id, applyEvent, setFinal, reset]);

  return { finished, last };
}
