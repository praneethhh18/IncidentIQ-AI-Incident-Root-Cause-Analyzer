/**
 * Per-browser session id management.
 *
 * On first page load we ask the backend for a session id and stash it
 * in localStorage. Every subsequent API request (in api.ts) sends it
 * back as ``X-IIQ-Session: <uuid>``. The backend looks the id up in an
 * in-memory dict to find any monitoring credentials the user pasted
 * via the Settings page.
 *
 * This is intentionally NOT auth: it's a lightweight per-browser
 * credential bucket that lets the public IncidentIQ deployment serve
 * multiple visitors without any of them touching the server's .env.
 * Sessions TTL out after 24h server-side.
 */

import { API_BASE } from "./api-base";

const STORAGE_KEY = "iiq.session_id";

let cachedSessionId: string | null = null;

export function getSessionId(): string | null {
  if (typeof window === "undefined") return null;
  if (cachedSessionId) return cachedSessionId;
  cachedSessionId = window.localStorage.getItem(STORAGE_KEY);
  return cachedSessionId;
}

export function setSessionId(id: string): void {
  if (typeof window === "undefined") return;
  cachedSessionId = id;
  window.localStorage.setItem(STORAGE_KEY, id);
}

export function clearSessionId(): void {
  if (typeof window === "undefined") return;
  cachedSessionId = null;
  window.localStorage.removeItem(STORAGE_KEY);
}

/**
 * Idempotent: ensures we have a session id. Either returns the cached
 * one (touching its server-side last_seen) or asks the backend for a
 * fresh one. Safe to call from a useEffect; safe to call repeatedly.
 */
export async function ensureSessionId(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const existing = getSessionId();
  const headers: Record<string, string> = {};
  if (existing) headers["X-IIQ-Session"] = existing;
  try {
    const res = await fetch(`${API_BASE}/api/v1/session/new`, {
      method: "POST",
      headers,
    });
    if (!res.ok) return existing;
    const body = (await res.json()) as { session_id?: string };
    if (body.session_id) {
      setSessionId(body.session_id);
      return body.session_id;
    }
  } catch {
    /* offline / CORS / blocked — fall through to whatever we had */
  }
  return existing;
}
