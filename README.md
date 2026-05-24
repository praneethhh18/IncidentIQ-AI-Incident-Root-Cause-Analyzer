# IncidentIQ

AI-powered root-cause analysis for production incidents. Connects to your monitoring stack (Datadog, Grafana, New Relic), reads error logs in real time, and uses an agentic AWS Bedrock pipeline to produce a structured root-cause analysis, propose code-level fixes against your GitHub repo, and auto-detect new incidents while you're not watching.

Live demo: **https://incidentiq.nexusagent.in**

## What it actually does

- **Pulls real production logs** via the Datadog (or Grafana / New Relic) API. No mock data on live mode — only what the monitoring stack actually has.
- **Runs a multi-tool agent** (`extract_entities`, `correlate_timeline`, `service_dependency_hints`, `search_logs`, `query_similar_incidents`, `trace_origin`, `compute_blast_radius`, `infer_trigger`) and streams the reasoning trail live via SSE.
- **Synthesises a structured analysis** with AWS Bedrock (Amazon Nova Pro): root cause, confidence, severity rationale, affected services, evidence, forensic report with patient-zero and blast radius.
- **Generates a 5 Whys postmortem** with the deepest layers written by the LLM grounded in the incident — not severity-keyed templates.
- **Escalates to Deep Trace** automatically on low confidence or P1 with no matching history: four hidden-signal scanners + per-service probe + extended LLM pass for subtle defects.
- **Produces a real code-fix diff** against your GitHub repo. Five sub-agents: clone → locate → diagnose → patch → verify. Output is a unified diff that applies cleanly with `git apply`, with a cosmetic-diff guard so we never claim a fix that's only whitespace.
- **Watch Mode** background poller auto-creates incidents when Datadog sees a fresh error cluster.
- **Lifecycle**: open → investigating → recovering → resolved, with paste-fresh-logs recheck.
- **Follow-up chat** with three-tier remediation answers (immediate mitigation → stabilise + verify → root-cause fix).
- **PDF export** of the full report.

## Architecture

```
Next.js 14 (Vercel)  ──HTTPS──▶  FastAPI + Pydantic v2 (AWS EC2)  ─┬─▶  AWS Bedrock (Nova Pro)
                                                                   ├─▶  Datadog / Grafana / New Relic
                                                                   ├─▶  GitHub OAuth + repo clone
                                                                   └─▶  SQLite store (StateDirectory)
```

Production split: frontend on Vercel with custom domain, backend on AWS EC2 t3.small behind nginx + Let's Encrypt SSL, SQLite persistence via systemd `StateDirectory`. CI/CD via GitHub Actions on push to `main`.

## Quick start (local dev)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                          # Windows
# source .venv/bin/activate                     # macOS / Linux
pip install -r requirements.txt
cp .env.example .env                            # fill in AWS + Datadog + GitHub OAuth keys
uvicorn app.main:app --reload --port 8000
```

Health: <http://localhost:8000/health>. Swagger: <http://localhost:8000/docs>.

### Frontend

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open <http://localhost:3000>.

### Required environment variables (live mode)

Without these, the corresponding feature degrades gracefully. With them, everything is real.

| Key | Purpose |
|---|---|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | Bedrock inference |
| `DATADOG_API_KEY` / `DATADOG_APP_KEY` / `DATADOG_SITE` | Live log search |
| `GITHUB_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_SECRET` | "Connect GitHub" for code-fix |
| `GRAFANA_URL` / `GRAFANA_API_KEY` | Optional |
| `NEW_RELIC_USER_KEY` / `NEW_RELIC_ACCOUNT_ID` | Optional |

## Production deployment

The repo includes a complete EC2 + nginx + systemd + Let's Encrypt setup that deploys via GitHub Actions on every push to `main`.

See [deploy/README.md](deploy/README.md) for the operator runbook (one-time bootstrap, secrets, SSL provisioning, subsequent deploys, rollback).

## Project layout

```
backend/         FastAPI app: agents, integrations, Bedrock client, SQLite store
frontend/        Next.js 14 App Router + Tailwind
deploy/          bootstrap.sh, nginx + systemd configs, .env template
.github/         CI/CD workflow (push to main -> SSH deploy + health check)
```

## License

MIT.
