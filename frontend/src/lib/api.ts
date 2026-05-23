// Tiny typed wrapper around the IncidentIQ backend API.
//
// All calls go through `request`, which centralises base URL handling,
// JSON parsing, and error normalisation. Server actions, page components,
// and client components share the same surface.

import type {
  AgentStep,
  AnalyzeRequest,
  AnalyzeResponse,
  IncidentSummary,
  IntegrationStatus,
  SampleIncident,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail ?? detail;
    } catch {
      // Ignore body-parse errors — fall back to status text.
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; bedrock_enabled: boolean; model: string }>("/health"),

  integrations: () => request<IntegrationStatus[]>("/api/v1/integrations"),

  samples: () => request<SampleIncident[]>("/api/v1/samples"),

  samplePayload: (id: string) =>
    request<{ title: string; logs: string; service_hint: string }>(
      `/api/v1/samples/${id}`,
    ),

  analyze: (body: AnalyzeRequest) =>
    request<AnalyzeResponse>("/api/v1/analyze", {
      method: "POST",
      json: body,
    }),

  recent: (limit = 25) =>
    request<IncidentSummary[]>(`/api/v1/incidents?limit=${limit}`),

  incident: (id: string) =>
    request<AnalyzeResponse>(`/api/v1/incidents/${id}`),

  exportPdfUrl: (id: string) =>
    `${API_BASE}/api/v1/incidents/${id}/export.pdf`,

  /**
   * Stream an analysis using SSE-over-fetch. Yields events as they arrive:
   *   { type: "phase", phase, message }
   *   { type: "agent_step", step }
   *   { type: "complete", analysis }
   *   { type: "error", message }
   *
   * Pass an AbortSignal to cancel mid-stream (e.g. when the user navigates away).
   */
  analyzeStream: async function* (
    body: AnalyzeRequest,
    signal?: AbortSignal,
  ): AsyncGenerator<StreamEvent> {
    const response = await fetch(`${API_BASE}/api/v1/analyze/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok || !response.body) {
      const detail = await response.text().catch(() => response.statusText);
      throw new ApiError(detail || "Stream failed", response.status);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const raw = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf("\n\n");
          const parsed = parseSseChunk(raw);
          if (parsed) yield parsed;
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
};

export type StreamEvent =
  | { type: "phase"; phase: string; message: string; log_lines?: number }
  | { type: "agent_step"; step: AgentStep }
  | { type: "complete"; analysis: AnalyzeResponse }
  | { type: "error"; message: string };

function parseSseChunk(raw: string): StreamEvent | null {
  const lines = raw.split("\n");
  let dataPayload = "";
  for (const line of lines) {
    if (line.startsWith("data:")) {
      dataPayload += line.slice(5).trim();
    }
  }
  if (!dataPayload) return null;
  try {
    const obj = JSON.parse(dataPayload);
    const eventName: string = obj.event ?? "phase";
    if (eventName === "agent_step") {
      return { type: "agent_step", step: obj.step as AgentStep };
    }
    if (eventName === "complete") {
      return { type: "complete", analysis: obj.analysis as AnalyzeResponse };
    }
    if (eventName === "error") {
      return { type: "error", message: obj.message ?? "Unknown error" };
    }
    return {
      type: "phase",
      phase: obj.phase ?? "unknown",
      message: obj.message ?? "",
      log_lines: obj.log_lines,
    };
  } catch {
    return null;
  }
}
