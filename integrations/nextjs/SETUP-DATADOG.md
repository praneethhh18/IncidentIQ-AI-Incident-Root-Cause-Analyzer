# End-to-end setup: FashionAura → Datadog → IncidentIQ

This walks you through the full PS-compliant architecture:

```
   FashionAura  ──ships logs──▶  Datadog  ──pulled by──▶  IncidentIQ
   (your app)                  (monitoring)              (root-cause AI)
```

Two key sets are involved — don't mix them up:

| Key | Where it lives | What it does |
| --- | --- | --- |
| **API key** (`DD-API-KEY`) | `.env.local` in FashionAura | Authorises log INGESTION (writes) |
| **Application key** + API key | `backend/.env` in IncidentIQ | Authorises log SEARCH (reads) |

Datadog requires both for the read path. The write path only needs the API key.

---

## 1. Sign up for Datadog (5 minutes, no credit card)

1. Go to <https://www.datadoghq.com/free-datadog-trial/>
2. Enter email → set password → choose region: **US1 (datadoghq.com)** (default)
3. Pick anything for the org name (e.g. "FashionAura demo")
4. Skip the "install agent" onboarding wizard — we use the HTTP intake instead. Click "Skip" or close any modal.

You're in.

## 2. Create the two keys

### a. API key (for writing logs from FashionAura)

1. Click your avatar / name (bottom-left) → **Organization Settings**
2. Left sidebar → **API Keys** → **+ New Key**
3. Name: `fashion-aura-ingest`
4. Copy the value (starts with letters/numbers, ~32 chars). **Keep this tab open or save the value somewhere.**

### b. Application key (for IncidentIQ to read logs back)

Same Organization Settings:

1. Left sidebar → **Application Keys** → **+ New Key**
2. Name: `incidentiq-search`
3. Copy that value too (longer string, ~40 chars).

## 3. Wire it into FashionAura (writes)

In `C:/Users/Praneeth p/FashionAura/.env.local`, append:

```
DATADOG_API_KEY=<the API key from step 2a>
DATADOG_SITE=us5.datadoghq.com    # change to match your region (datadoghq.com, us3.datadoghq.com, us5.datadoghq.com, datadoghq.eu, ap1.datadoghq.com)
```

Restart FashionAura's dev server (Ctrl+C, then `npm run dev` again).

## 4. Wire it into IncidentIQ (reads)

In `C:/Users/Praneeth p/OneDrive/Desktop/IncidentIQ/backend/.env`, fill in:

```
DATADOG_API_KEY=<same API key from step 2a>
DATADOG_APP_KEY=<the APP key from step 2b>
DATADOG_SITE=us5.datadoghq.com    # change to match your region (datadoghq.com, us3.datadoghq.com, us5.datadoghq.com, datadoghq.eu, ap1.datadoghq.com)
```

Restart the IncidentIQ backend (kill the process, run `python -m uvicorn app.main:app --port 8000` again).

## 5. Verify writes land in Datadog

```bash
curl "http://localhost:9002/api/demo/break?mode=db"
```

Wait ~30 seconds, then in Datadog:

1. Top nav → **Logs** → **Explorer**
2. In the search bar type: `service:fashion-aura-api`
3. You should see your error log lines

If you don't see anything after 60 seconds: check the FashionAura dev-server console — the reporter logs ship failures in dev mode. Most common issue: wrong DD region. If you picked EU during signup, use `DATADOG_SITE=datadoghq.eu` in both env files.

## 6. Verify IncidentIQ can read them

1. Open <http://localhost:3000/dashboard>
2. Look at the Integrations row — the **Datadog** card should now show `Connected · live` (green) instead of `demo fallback`
3. Click the **Datadog** tab on the analyze panel
4. Enter query: `service:fashion-aura-api status:error`
5. Click **Analyze incident**
6. IncidentIQ uses your search keys to pull the actual logs from Datadog and run them through the agent. You get a real root-cause analysis on the same logs that just landed in Datadog from FashionAura.

That's the complete PS-compliant loop.

## 7. (Optional, max impact) Add a Datadog monitor that webhooks IncidentIQ

The most production-shaped demo: Datadog itself triggers the analysis when it detects an error spike.

1. In Datadog: top nav → **Monitors** → **+ New Monitor** → **Logs**
2. Define query: `service:fashion-aura-api status:error`
3. Set "Alert threshold": above 5 in 5m (low threshold so it fires easily in demo)
4. Scroll down → **Notify your team**: in the message box type a message + add `@webhook-incidentiq`
5. **Configure webhook integration** (first time only):
   - Integrations → Webhooks → **+ New**
   - Name: `incidentiq`
   - URL: `https://your-incidentiq-deployed-url.com/api/v1/webhook/datadog` (use ngrok if testing locally)
   - Payload: leave default (Datadog ships the alert details)
   - Save
6. Test the monitor → alert fires → webhook hits IncidentIQ → auto-analysis lands in dashboard

This is the "PagerDuty-replacement" story. Datadog is the source of truth for alerts; IncidentIQ is what analyses them automatically.

---

# Same pattern for Grafana and New Relic

Once Datadog works, the others are 5-minute repeats of the same flow.

## Grafana Cloud + Loki

**FashionAura (writes):**
1. Sign up at <https://grafana.com/auth/sign-up/create-user>
2. After login, left sidebar → **Connections** → **Data sources** → click **grafanacloud-yourname-logs** entry → note the URL (e.g. `https://logs-prod-006.grafana.net`) and **User** field (e.g. `123456`)
3. **Security** → **Access Policies** → **+ Create access policy** → name `fashion-aura-write` → scope: **logs:write** → save → **Add token** → copy the token (starts with `glc_`)
4. In FashionAura `.env.local`:
   ```
   GRAFANA_LOKI_URL=https://logs-prod-006.grafana.net
   GRAFANA_LOKI_AUTH=<userId>:<glc_token>
   ```

**IncidentIQ (reads):**
- Same Access Policies page, create another with scope **logs:read**, copy token
- In `backend/.env`:
  ```
  GRAFANA_URL=https://logs-prod-006.grafana.net
  GRAFANA_API_KEY=<the read token>
  ```

Restart both. Trigger an error in FashionAura. Open IncidentIQ → Grafana tab → enter query `{service="fashion-aura-api"} |~ "(?i)(error|fail)"` → Analyze.

## New Relic

**FashionAura (writes):**
1. Sign up at <https://newrelic.com/signup>
2. After login, top-right → **API keys** → **+ Create a key** → key type **INGEST - LICENSE** → name `fashion-aura-ingest` → copy (starts with `NRII-`)
3. In FashionAura `.env.local`:
   ```
   NEW_RELIC_LICENSE_KEY=<NRII-key>
   NEW_RELIC_EU=1            # only if your account is EU
   ```

**IncidentIQ (reads):**
- Same API keys page, create another key, key type **USER** → name `incidentiq-search` → copy (starts with `NRAK-`)
- Account ID: look at the URL, it's the 7-digit number, or top-right user menu shows it
- In `backend/.env`:
  ```
  NEW_RELIC_USER_KEY=<NRAK-key>
  NEW_RELIC_ACCOUNT_ID=<7-digit account id>
  ```

Restart both. Trigger an error in FashionAura. Open IncidentIQ → New Relic tab → enter NRQL: `SELECT * FROM Log WHERE service='fashion-aura-api' SINCE 30 minutes ago` → Analyze.

---

# The architecture you can defend to judges

After all three are wired:

- **FashionAura** ships every error to **all three** monitoring tools in parallel (Datadog + Grafana + New Relic) plus directly to **IncidentIQ's webhook**.
- **IncidentIQ** has read credentials for all three and can pull from any of them on demand.
- **Same logs visible in 4 places.** Engineers can verify in their existing tools (Datadog dashboard, Grafana Explore, New Relic Logs). IncidentIQ adds the AI analysis layer on top.
- **No agents installed.** Pure HTTP intake APIs — works on Vercel, Lambda, Edge, anywhere fetch is available.

This is the exact shape of every real-world SRE platform. You're not faking the integration story; you're building the same wiring real SRE teams build between their app, their monitoring stack, and their alerting platform.
