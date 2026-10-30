// Live pipeline events. STUB — owner: Frontend A. See team/01_FRONTEND_A.md 3.3.
// TODO(Frontend A): push events into the Zustand store and dedupe on reconnect.
"use client";

import { useEffect, useState } from "react";
import { API_URL, USE_MOCKS } from "@/lib/api";
import eventsMock from "@/lib/mock/events.json";
import type { PipelineEvent } from "@/lib/types";

const MOCK_EVENT_DELAY_MS = 60;

function isTerminal(event: PipelineEvent): boolean {
  return event.stage === "pipeline" && (event.status === "done" || event.status === "error");
}

export function useAnalysisStream(id: string) {
  const [events, setEvents] = useState<PipelineEvent[]>([]);

  useEffect(() => {
    setEvents([]);
    if (USE_MOCKS) {
      const mockEvents = eventsMock as unknown as PipelineEvent[];
      let index = 0;
      const timer = setInterval(() => {
        const event = mockEvents[index++];
        if (event) setEvents((current) => [...current, event]);
        else clearInterval(timer);
      }, MOCK_EVENT_DELAY_MS);
      return () => clearInterval(timer);
    }

    const source = new EventSource(`${API_URL}/api/analyses/${id}/events`);
    source.onmessage = (message) => {
      const event: PipelineEvent = JSON.parse(message.data);
      setEvents((current) => [...current, event]);
      if (isTerminal(event)) source.close(); // otherwise EventSource reconnects forever
    };
    return () => source.close();
  }, [id]);

  const last = events.at(-1);
  return { events, last, finished: last !== undefined && isTerminal(last) };
}
