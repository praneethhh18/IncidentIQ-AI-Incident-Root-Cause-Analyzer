/**
 * IncidentIQ reporter for Next.js (App Router or Pages Router).
 *
 * Drop this file into your Next.js project at:
 *   src/lib/incidentiq-reporter.ts
 *
 * Then either:
 *   - Wrap your error-prone server actions / route handlers with
 *     `withIncidentReporting(handler)`
 *   - Or call `reportIncident({ title, logs })` directly when you
 *     catch an error you want analysed.
 *
 * Configuration: set INCIDENTIQ_WEBHOOK_URL in your environment, e.g.
 *   INCIDENTIQ_WEBHOOK_URL=https://incidentiq.your-domain.com/api/v1/webhook/generic
 *
 * For local dev pointing at a local IncidentIQ:
 *   INCIDENTIQ_WEBHOOK_URL=http://localhost:8000/api/v1/webhook/generic
 *
 * The reporter is best-effort: it never throws, never blocks your app's
 * response. If IncidentIQ is unreachable the error stays logged but
 * your user-facing flow continues as before.
 */

interface ReportArgs {
  /** Short human title shown in IncidentIQ's incident list. */
  title: string;
  /** Free-form log payload (one or more lines). */
  logs: string;
  /** Optional service hint to focus the agent. */
  service?: string;
}

// In-process ring buffer so a single error can ship the surrounding
// context, not just the error line itself.
const RECENT_LOGS: string[] = [];
const RECENT_LIMIT = 80;

function pushLog(line: string): void {
  RECENT_LOGS.push(line);
  if (RECENT_LOGS.length > RECENT_LIMIT) {
    RECENT_LOGS.splice(0, RECENT_LOGS.length - RECENT_LIMIT);
  }
}

function fmtLine(level: "INFO" | "WARN" | "ERROR" | "FATAL", service: string, message: string): string {
  const ts = new Date().toISOString();
  return `${ts} ${level.padEnd(5)} ${service.padEnd(20)} ${message}`;
}

/** Hook console.error into the ring buffer so casual `console.error` calls
 *  contribute to incident context automatically. Call once at app startup. */
let consolePatched = false;
export function installConsolePatch(service = "next-app"): void {
  if (consolePatched) return;
  consolePatched = true;

  const origError = console.error.bind(console);
  console.error = (...args: unknown[]) => {
    const message = args
      .map((a) => (a instanceof Error ? `${a.message}\n${a.stack ?? ""}` : String(a)))
      .join(" ");
    pushLog(fmtLine("ERROR", service, message));
    origError(...args);
  };

  const origWarn = console.warn.bind(console);
  console.warn = (...args: unknown[]) => {
    const message = args
      .map((a) => (a instanceof Error ? `${a.message}\n${a.stack ?? ""}` : String(a)))
      .join(" ");
    pushLog(fmtLine("WARN", service, message));
    origWarn(...args);
  };

  const origLog = console.log.bind(console);
  console.log = (...args: unknown[]) => {
    const message = args.map((a) => String(a)).join(" ");
    pushLog(fmtLine("INFO", service, message));
    origLog(...args);
  };
}

/** Returns the current ring-buffer of log lines (newest last). */
export function recentLogs(): string[] {
  return [...RECENT_LOGS];
}

/** Force-add a structured log line (useful for manual instrumentation). */
export function note(
  level: "INFO" | "WARN" | "ERROR" | "FATAL",
  service: string,
  message: string,
): void {
  pushLog(fmtLine(level, service, message));
}

/**
 * Ship an incident report to IncidentIQ. Best-effort and non-blocking:
 * any failure to reach IncidentIQ is swallowed (and logged to console).
 *
 * The function returns a Promise but you generally don't need to await it.
 */
export async function reportIncident(args: ReportArgs): Promise<void> {
  const url =
    process.env.INCIDENTIQ_WEBHOOK_URL ||
    process.env.NEXT_PUBLIC_INCIDENTIQ_WEBHOOK_URL ||
    "";
  if (!url) {
    // Not configured. Don't spam; just log once at startup if missing.
    return;
  }

  // Prepend the manual logs onto the ring-buffer tail so the report has
  // both the explicit error context and any recent surrounding logs.
  const ring = recentLogs().slice(-30);
  const payload = {
    title: args.title.slice(0, 240),
    logs: `${ring.join("\n")}\n${args.logs}`.trim(),
    ...(args.service ? { service_hint: args.service } : {}),
  };

  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      // Vercel functions: don't hold up the response on this call.
      keepalive: true,
    });
  } catch (err) {
    // Silent. We never want this to break the user's request.
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.error("[incidentiq] reporter failed:", err);
    }
  }
}

/**
 * Wrap a Next.js route handler or server action so any thrown error is
 * automatically reported to IncidentIQ before being re-thrown.
 *
 * Usage (App Router):
 *
 *   import { withIncidentReporting } from "@/lib/incidentiq-reporter";
 *
 *   async function GET(req: Request) {
 *     // your code, may throw
 *   }
 *   export const GET = withIncidentReporting(GET, { service: "fashion-aura-api" });
 */
export function withIncidentReporting<TArgs extends unknown[], TReturn>(
  handler: (...args: TArgs) => Promise<TReturn>,
  options: { service?: string; titlePrefix?: string } = {},
): (...args: TArgs) => Promise<TReturn> {
  const service = options.service ?? "next-app";
  const titlePrefix = options.titlePrefix ?? "Unhandled error";

  return async (...args: TArgs) => {
    try {
      return await handler(...args);
    } catch (error) {
      const e = error instanceof Error ? error : new Error(String(error));
      note("ERROR", service, `${e.name}: ${e.message}`);
      if (e.stack) note("ERROR", service, e.stack.split("\n").slice(0, 6).join("\n"));

      // Fire-and-forget. We use a void here so this doesn't suspend
      // the caller's error path.
      void reportIncident({
        title: `${titlePrefix} - ${e.message.slice(0, 120)}`,
        logs: `${e.name}: ${e.message}\n${e.stack ?? ""}`,
        service,
      });

      throw error;
    }
  };
}
