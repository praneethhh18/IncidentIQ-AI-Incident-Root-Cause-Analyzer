# IncidentIQ + Next.js integration

Drop these two files into a Next.js app (App Router or Pages Router) to:

1. Capture unhandled errors and ship them to IncidentIQ automatically.
2. Expose a `/api/demo/break?mode=...` endpoint you can hit to trigger a controlled, production-shaped failure that IncidentIQ analyses end-to-end.

Tested with Next.js 13 / 14 / 15. Works on Vercel out of the box.

---

## Files

| File | Where it goes | Purpose |
| --- | --- | --- |
| [`incidentiq-reporter.ts`](./incidentiq-reporter.ts) | `src/lib/incidentiq-reporter.ts` | Ring buffer + `reportIncident()` + `withIncidentReporting()` wrapper |
| [`demo-break.route.ts`](./demo-break.route.ts) | `src/app/api/demo/break/route.ts` (App Router) or `src/pages/api/demo/break.ts` (Pages Router) | A `/api/demo/break?mode=db\|oom\|upstream\|cascade` endpoint that triggers a realistic failure |

## Install

### 1. Copy the two files

```bash
mkdir -p src/lib
cp /path/to/IncidentIQ/integrations/nextjs/incidentiq-reporter.ts src/lib/

# For App Router:
mkdir -p src/app/api/demo/break
cp /path/to/IncidentIQ/integrations/nextjs/demo-break.route.ts src/app/api/demo/break/route.ts

# For Pages Router:
mkdir -p src/pages/api/demo
cp /path/to/IncidentIQ/integrations/nextjs/demo-break.route.ts src/pages/api/demo/break.ts
# Then follow the comment at the bottom of demo-break.route.ts to switch to the default handler export.
```

### 2. Set the IncidentIQ webhook URL

Add to your `.env.local` (and to your Vercel env vars):

```bash
# For local dev pointing at a local IncidentIQ:
INCIDENTIQ_WEBHOOK_URL=http://localhost:8000/api/v1/webhook/generic

# For production (once IncidentIQ is deployed):
INCIDENTIQ_WEBHOOK_URL=https://your-incidentiq.com/api/v1/webhook/generic
```

That single env var is the only configuration the reporter needs.

### 3. Verify

Restart your dev server, then hit the demo endpoint:

```bash
curl https://your-app.vercel.app/api/demo/break?mode=db
```

You should see:
- HTTP 500 with a JSON body explaining the simulated failure
- An incident appearing in IncidentIQ's history within a second or two
- The agent analysing the logs and posting the root cause

---

## Optional: report your real errors automatically

If you want any unhandled error in your real route handlers to ship to IncidentIQ, wrap them:

### App Router example

```ts
// src/app/api/checkout/route.ts
import { withIncidentReporting } from "@/lib/incidentiq-reporter";

async function GET(req: Request) {
  // your real code, may throw
  const order = await placeOrder(req);
  return Response.json(order);
}

export const GET = withIncidentReporting(GET, { service: "checkout-api" });
```

### Server actions example

```ts
"use server";
import { withIncidentReporting } from "@/lib/incidentiq-reporter";

export const placeOrderAction = withIncidentReporting(
  async (formData: FormData) => {
    // your real code, may throw
  },
  { service: "fashion-aura-actions" },
);
```

### Anywhere else

```ts
import { reportIncident } from "@/lib/incidentiq-reporter";

try {
  await thingThatMayFail();
} catch (err) {
  reportIncident({
    title: "User signup failed",
    logs: `${err}\n${(err as Error).stack ?? ""}`,
    service: "auth",
  });
  throw err;
}
```

### Capture console.error globally

If you want every `console.error` your app makes to also contribute context to incident reports, call this once in your root layout:

```ts
// src/app/layout.tsx (or anywhere that runs once at startup)
import { installConsolePatch } from "@/lib/incidentiq-reporter";

if (typeof process !== "undefined") {
  installConsolePatch("fashion-aura");
}
```

---

## How it behaves

**Best-effort.** If IncidentIQ is unreachable, the reporter never throws. Your user-facing requests keep flowing normally; only the incident report is dropped.

**Non-blocking.** `reportIncident()` returns a Promise but the typical pattern is `void reportIncident(...)` so it doesn't suspend the caller. With `keepalive: true` on the fetch, Vercel serverless functions don't keep their lambda warm waiting for it.

**Tiny payload.** Each incident ships ~30 lines of recent log context plus the specific error. Stays well under any reasonable HTTP request limit.

**No external SDKs.** Just `fetch`. Works in Node runtime and Edge runtime alike.

---

## Demo flow for the video

Once installed and deployed (or running locally):

1. Open your app's normal pages so the audience sees a working product.
2. Open `https://your-app.vercel.app/api/demo/break?mode=cascade` in a new tab. It returns HTTP 500 with a simulated cascading failure.
3. Switch to IncidentIQ's dashboard. The new incident is already there, fully analysed.
4. Walk through the analysis: root cause, forensic, fix recommendations.
5. (Optional) Ask a follow-up in the chat panel.
6. Back to your app. The endpoint still 500s. You "apply the fix" (e.g. add the missing fix mentioned by IncidentIQ).
7. Run IncidentIQ's recheck against the now-healthy app. Status flips to resolved.
8. If SendGrid is configured, an email lands confirming resolution.

That's the complete production loop on real infrastructure.

---

## Modes available on `/api/demo/break`

| `?mode=` | Simulates | Shape |
| --- | --- | --- |
| `db` (default) | Postgres connection pool exhaustion | Pool waits → exhausted → 503s → SLO burn |
| `oom` | Node process out of memory | Heap growth → Full GC → V8 OOM → function terminated |
| `upstream` | Upstream payment provider (Stripe) 504s | Slow API → 504 → circuit breaker open |
| `cascade` | Full multi-service cascade | DB pool → Redis CLUSTERDOWN → breaker → worker OOM |

Each mode produces ~5-7 realistic log lines in known production formats that the agent is tuned to analyse cleanly.
