// Typed client, one function per endpoint in contracts §8. Owner: Frontend A.
// Mock mode is the default; set NEXT_PUBLIC_USE_MOCKS=false to talk to the backend.
import analysisMock from "@/lib/mock/analysis.json";
import evalMock from "@/lib/mock/eval.json";
import geoMock from "@/lib/mock/geo.json";
import graphMock from "@/lib/mock/graph.json";
import readinessMock from "@/lib/mock/readiness.json";
import simulateMock from "@/lib/mock/simulate.json";
import tacticsMock from "@/lib/mock/tactics.json";
import type {
  AnalysisListItem, EvalResponse, GeoPoint, GraphResponse, ReadinessResponse, ReportAnalysis,
  SimulateResponse, Tactic, TechniqueDetail, Telemetry,
} from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }
  return response.json();
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function mock<T>(data: unknown): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, 300 + Math.random() * 500));
  return data as T;
}

const mockAnalysis = analysisMock as unknown as ReportAnalysis;

export async function createAnalysis(
  input: { url?: string; text?: string; title?: string } | File,
): Promise<{ id: string }> {
  if (USE_MOCKS) return mock({ id: mockAnalysis.report_id });
  if (input instanceof File) {
    const form = new FormData();
    form.append("file", input);
    return request("/analyses", { method: "POST", body: form });
  }
  return postJson("/analyses", input);
}

export async function listAnalyses(): Promise<AnalysisListItem[]> {
  if (USE_MOCKS) {
    const { report_id, title, source_url, published_at, created_at, status } = mockAnalysis;
    return mock([{
      report_id, title, source_url, published_at, created_at, status,
      counts: {
        iocs: mockAnalysis.iocs.filter((i) => !i.filtered_reason).length,
        techniques: mockAnalysis.techniques.filter((t) => t.status === "accepted").length,
        alerts: mockAnalysis.memory_alerts.length,
      },
    }]);
  }
  return request("/analyses");
}

export async function getAnalysis(id: string): Promise<ReportAnalysis> {
  if (USE_MOCKS) return mock(mockAnalysis);
  return request(`/analyses/${id}`);
}

export async function sendFeedback(
  id: string,
  body: { target_type: "technique" | "ioc"; target_id: string; verdict: "accept" | "reject"; note?: string },
): Promise<{ ok: boolean }> {
  if (USE_MOCKS) return mock({ ok: true });
  return postJson(`/analyses/${id}/feedback`, body);
}

export async function simulate(id: string, blockedNodeIds: string[]): Promise<SimulateResponse> {
  if (USE_MOCKS) return mock(simulateMock);
  return postJson(`/analyses/${id}/simulate`, { blocked_node_ids: blockedNodeIds });
}

export async function readiness(id: string, telemetry: Telemetry[]): Promise<ReadinessResponse> {
  if (USE_MOCKS) return mock(readinessMock);
  return postJson(`/analyses/${id}/readiness`, { telemetry });
}

export function exportUrl(id: string, fmt: "stix" | "navigator" | "sigma" | "flow"): string {
  return `${API_URL}/api/analyses/${id}/export/${fmt}`;
}

export async function getGraph(at?: string): Promise<GraphResponse> {
  if (USE_MOCKS) return mock(graphMock);
  return request(`/graph${at ? `?at=${encodeURIComponent(at)}` : ""}`);
}

export async function getTactics(): Promise<Tactic[]> {
  if (USE_MOCKS) return mock(tacticsMock);
  return request("/attack/tactics");
}

export async function getTechnique(id: string): Promise<TechniqueDetail> {
  if (USE_MOCKS) {
    const match = [...mockAnalysis.techniques, ...mockAnalysis.predictions].find(
      (t) => t.technique_id === id,
    );
    if (!match) throw new ApiError(404, `Technique ${id} not found`);
    return mock({
      technique_id: id, name: match.name, description: `Mock description of ${match.name}.`,
      tactics: match.tactics, is_subtechnique: id.includes("."),
      parent_id: id.includes(".") ? id.split(".")[0] : null, platforms: ["Windows"],
      url: match.url ?? "",
    });
  }
  return request(`/attack/techniques/${id}`);
}

export async function getEval(): Promise<EvalResponse> {
  if (USE_MOCKS) return mock(evalMock);
  return request("/eval");
}

export async function getGeo(id: string): Promise<GeoPoint[]> {
  if (USE_MOCKS) return mock(geoMock);
  return request(`/analyses/${id}/geo`);
}
