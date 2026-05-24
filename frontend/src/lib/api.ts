// Tiny typed wrapper around the IncidentIQ backend API.
//
// All calls go through `request`, which centralises base URL handling,
// JSON parsing, and error normalisation. Server actions, page components,
// and client components share the same surface.

import type {
  AgentStep,
  AnalyzeRequest,
  AnalyzeResponse,
  ChatMessage,
  GitHubRepo,
  GitHubStatus,
  IncidentSummary,
  IntegrationStatus,
  SampleIncident,
  WatchStatusPayload,
} from "./types";

export { API_BASE } from "./api-base";
import { API_BASE } from "./api-base";
import { getSessionId } from "./session";

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
  // Attach the per-browser session id so the backend can pick up the
  // user's pasted Datadog/Grafana/NR credentials. SSR fetches won't
  // have one (server has no localStorage); they fall back to .env on
  // the backend side, which is the expected behaviour.
  const sessionId = getSessionId();
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(sessionId ? { "X-IIQ-Session": sessionId } : {}),
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

  datadogServices: (windowMinutes = 60) =>
    request<{ connected: boolean; services: string[] }>(
      `/api/v1/integrations/datadog/services?window_minutes=${windowMinutes}`,
    ),

  watchStatus: () => request<WatchStatusPayload>("/api/v1/watch/status"),

  watchStart: (body: {
    service?: string;
    poll_interval_s?: number;
    window_minutes?: number;
    error_threshold?: number;
  }) =>
    request<WatchStatusPayload>("/api/v1/watch/start", {
      method: "POST",
      json: body,
    }),

  watchStop: () =>
    request<WatchStatusPayload>("/api/v1/watch/stop", { method: "POST" }),

  // ── Per-session credentials (Settings page) ──────────────────────
  sessionStatus: () =>
    request<{ session_id: string | null; status: { datadog: boolean; grafana: boolean; newrelic: boolean } }>(
      "/api/v1/session/status",
    ),

  setDatadogCreds: (body: { api_key: string; app_key: string; site: string }) =>
    request<{ session_id: string; status: { datadog: boolean; grafana: boolean; newrelic: boolean } }>(
      "/api/v1/integrations/datadog/credentials",
      { method: "POST", json: body },
    ),

  clearDatadogCreds: () =>
    request<{ session_id: string; status: { datadog: boolean; grafana: boolean; newrelic: boolean } }>(
      "/api/v1/integrations/datadog/credentials",
      { method: "DELETE" },
    ),

  setGrafanaCreds: (body: { url: string; api_key: string }) =>
    request<{ session_id: string; status: { datadog: boolean; grafana: boolean; newrelic: boolean } }>(
      "/api/v1/integrations/grafana/credentials",
      { method: "POST", json: body },
    ),

  clearGrafanaCreds: () =>
    request<{ session_id: string; status: { datadog: boolean; grafana: boolean; newrelic: boolean } }>(
      "/api/v1/integrations/grafana/credentials",
      { method: "DELETE" },
    ),

  setNewRelicCreds: (body: { user_key: string; account_id: string }) =>
    request<{ session_id: string; status: { datadog: boolean; grafana: boolean; newrelic: boolean } }>(
      "/api/v1/integrations/newrelic/credentials",
      { method: "POST", json: body },
    ),

  clearNewRelicCreds: () =>
    request<{ session_id: string; status: { datadog: boolean; grafana: boolean; newrelic: boolean } }>(
      "/api/v1/integrations/newrelic/credentials",
      { method: "DELETE" },
    ),

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

  deepTrace: (incidentId: string, logs?: string, reason?: string) =>
    request<AnalyzeResponse>(`/api/v1/incidents/${incidentId}/deep-trace`, {
      method: "POST",
      json: { logs, reason },
    }),

  codeFix: (incidentId: string, repoUrl: string) =>
    request<AnalyzeResponse>(`/api/v1/incidents/${incidentId}/code-fix`, {
      method: "POST",
      json: { repo_url: repoUrl },
    }),

  githubStatus: () => request<GitHubStatus>("/api/v1/auth/github/me"),

  githubRepos: () => request<GitHubRepo[]>("/api/v1/auth/github/repos"),

  githubLoginUrl: () => `${API_BASE}/api/v1/auth/github/login`,

  githubDisconnect: () =>
    request<{ status: string }>("/api/v1/auth/github/disconnect", {
      method: "POST",
    }),

  chat: (incidentId: string, message: string) =>
    request<{ reply: ChatMessage; history: ChatMessage[] }>(
      `/api/v1/incidents/${incidentId}/chat`,
      { method: "POST", json: { message } },
    ),

  recheck: (incidentId: string, logs?: string) =>
    request<{
      incident: AnalyzeResponse;
      outcome_status: "resolved" | "recovering" | "still_active" | string;
      outcome_summary: string;
      matched_signals: string[];
      email_sent: boolean;
    }>(`/api/v1/incidents/${incidentId}/recheck`, {
      method: "POST",
      json: {
        logs,
        dashboard_base_url:
          typeof window !== "undefined" ? window.location.origin : "",
      },
    }),

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

    // Find the next event boundary regardless of CRLF vs LF line endings.
    // sse-starlette emits "\r\n\r\n" on Windows; the SSE spec also allows "\n\n".
    const findBoundary = (str: string): { index: number; sep: number } | null => {
      const lf = str.indexOf("\n\n");
      const crlf = str.indexOf("\r\n\r\n");
      if (lf === -1 && crlf === -1) return null;
      if (lf === -1) return { index: crlf, sep: 4 };
      if (crlf === -1) return { index: lf, sep: 2 };
      return lf < crlf ? { index: lf, sep: 2 } : { index: crlf, sep: 4 };
    };

    const flushBuffer = function* (): Generator<StreamEvent> {
      let boundary = findBoundary(buffer);
      while (boundary !== null) {
        const raw = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary.sep);
        const parsed = parseSseChunk(raw);
        if (parsed) yield parsed;
        boundary = findBoundary(buffer);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        for (const event of flushBuffer()) yield event;
      }
      // Flush any trailing event left in the buffer once the stream closes.
      if (buffer.trim()) {
        const parsed = parseSseChunk(buffer);
        if (parsed) yield parsed;
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
  // Split on either CRLF or LF; trim each line of stray \r.
  const lines = raw.split(/\r?\n/);
  let dataPayload = "";
  for (const line of lines) {
    const clean = line.replace(/\r$/, "");
    if (clean.startsWith("data:")) {
      dataPayload += clean.slice(5).trim();
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
