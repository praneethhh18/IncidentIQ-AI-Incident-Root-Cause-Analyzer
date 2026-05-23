# IncidentIQ — AI Incident Root Cause Analyzer

> **What took 2 hours now takes 10 seconds.**

Production-grade **agentic AI** for SRE teams. Connects to Datadog, Grafana, and New Relic, ingests logs in real-time, runs a multi-step think-act-observe loop with five tools, and uses AWS Bedrock (Amazon Nova Pro) to identify root causes, reconstruct incident timelines, map affected services, and recommend fixes — all in seconds.

> 🏆 **Hackathon submission?** See [HACKATHON.md](HACKATHON.md) for rules compliance, agentic architecture, and contribution breakdown.

![Hero](docs/hero.png)

---

## Why IncidentIQ

It's 3am. Pager goes off. Production is down.

You're staring at 500 lines of logs across three dashboards trying to figure out what broke and why. By the time you find the root cause, customers have already noticed.

IncidentIQ flips the script. Paste logs, connect a monitoring tool, or upload a file — within seconds you get:

- **Root cause** with confidence score and supporting evidence
- **Reconstructed timeline** showing the failure cascade
- **Affected services** mapped from the logs
- **Severity rating** (P1 / P2 / P3) with reasoning
- **Actionable fix recommendations** ranked by impact
- **One-click PDF report** for the post-mortem

---

## Demo (3-minute walkthrough)

| Time | What you see |
| --- | --- |
| 0:00 | "It's 3am. Your app is down. 500 lines of logs. This is IncidentIQ." |
| 0:30 | Dashboard tour, live Datadog connection |
| 1:00 | Trigger analysis on a real cascading-failure incident |
| 1:30 | Root cause, timeline, affected services revealed |
| 2:00 | Fix recommendations and severity reasoning |
| 2:30 | Export PDF post-mortem in one click |
| 2:50 | "What took 2 hours now takes 10 seconds." |

---

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│  Next.js 14 (App    │  HTTPS  │  FastAPI + Pydantic  │
│  Router) + Tailwind │ ──────▶ │  Python 3.11+        │
│  shadcn-style UI    │ ◀────── │  SSE streaming       │
└─────────────────────┘         └──────────┬───────────┘
                                           │
              ┌────────────────────────────┼──────────────────────────┐
              ▼                            ▼                          ▼
     ┌─────────────────┐         ┌────────────────┐         ┌──────────────────┐
     │  AWS Bedrock    │         │  Monitoring    │         │  PDF Reports     │
     │  (Nova Pro)     │         │  Integrations  │         │  (ReportLab)     │
     │  Root cause AI  │         │  Datadog,      │         │                  │
     │                 │         │  Grafana,      │         │                  │
     │                 │         │  New Relic     │         │                  │
     └─────────────────┘         └────────────────┘         └──────────────────┘
```

Full details in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Quick start

### Prerequisites
- Node.js 20+
- Python 3.11+
- (Optional) AWS account with Bedrock access for live AI
- (Optional) Datadog / Grafana / New Relic API keys for live integrations

> **Demo mode**: If no API keys are configured, IncidentIQ runs in **demo mode** with rich, realistic seeded data — perfect for a first run or a hackathon demo. You can still trigger every feature end-to-end.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS/Linux
pip install -r requirements.txt
copy .env.example .env              # Windows
# cp .env.example .env              # macOS/Linux
# (optionally) add your API keys to .env
uvicorn app.main:app --reload --port 8000
```

Backend is live at <http://localhost:8000>. Swagger docs at <http://localhost:8000/docs>.

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local        # Windows
# cp .env.example .env.local        # macOS/Linux
npm run dev
```

Frontend is live at <http://localhost:3000>.

---

## How the agent works

IncidentIQ is structured as a four-phase agent, not a single LLM call:

1. **Perceive** — pulls logs from the requested source (paste / upload / Datadog / Grafana / New Relic / webhook).
2. **Plan & observe** — the agent calls eight tools (`extract_entities`, `correlate_timeline`, `service_dependency_hints`, `search_logs`, `query_similar_incidents`, plus the forensic trio `trace_origin`, `compute_blast_radius`, `infer_trigger`).
3. **Synthesise** — feeds the grounded briefing + raw telemetry to Amazon Nova Pro for the final structured analysis (falls back to a hand-crafted analysis when Bedrock is offline).
4. **Self-check** — verifies that every service named in the analysis appears in the observed logs; lowers confidence if grounding is weak.

The full reasoning trail **streams live** via Server-Sent Events — judges watch the agent think step-by-step. See [ARCHITECTURE.md](ARCHITECTURE.md) and [HACKATHON.md](HACKATHON.md) for the deep dive.

## Forensic mode — the differentiator

Inspired by malware-forensic tools, IncidentIQ doesn't just diagnose — it **reverse engineers** the cascade:

- **Patient zero** — the first abnormal signal in the timeline (the origin)
- **Propagation path** — service-by-service hops showing how the failure spread
- **Blast radius** — every entity touched: services, dependencies, user segments, regions, data surfaces
- **Trigger hypothesis** — the most-likely precipitating event (deploy / config change / scaling / dependency failure) with confidence score
- **MTTD** — minutes from patient zero to first user-visible impact

## Webhook auto-ingest

Page fires → IncidentIQ analyzes → result posted to Slack. Supported providers:

- **PagerDuty**: `POST /api/v1/webhook/pagerduty`
- **Datadog**: `POST /api/v1/webhook/datadog`
- **Opsgenie**: `POST /api/v1/webhook/opsgenie`
- **Generic JSON**: `POST /api/v1/webhook/generic`

Set `SLACK_WEBHOOK_URL` in `backend/.env` to auto-post analysis cards to your channel.

## Core features

| Feature | Description |
| --- | --- |
| **🔬 Forensic mode** | Patient zero, propagation path, blast radius, trigger hypothesis — reverse-engineer the cascade |
| **⚡ Live streaming reasoning** | Watch the agent think live via SSE — every thought, tool call, and observation streams to the UI |
| **🪝 Webhook auto-ingest** | PagerDuty / Datadog / Opsgenie / generic alerts auto-analyzed; results posted to Slack |
| **Multi-step agent with tool use** | Real think → act → observe → decide loop with 8 tools |
| **Live monitoring integrations** | Connect Datadog, Grafana, New Relic; pull logs and metrics on demand |
| **Manual log paste / file upload** | Drop a log file, paste raw output — works even when integrations aren't configured |
| **AI root cause analysis** | AWS Bedrock (Nova Pro) with chain-of-thought reasoning, confidence score, supporting evidence |
| **Incident timeline reconstruction** | Auto-extracted chronological sequence of events from logs |
| **Affected services mapping** | Pulls service names from logs and maps their dependencies |
| **Severity scoring** | P1/P2/P3 with explainable reasoning |
| **Fix recommendations** | Ranked, actionable fixes with code/command snippets where applicable |
| **Incident history dashboard** | All past analyses persisted, searchable, re-openable |
| **PDF report export** | One-click post-mortem PDF, ready to share |
| **Demo mode** | Built-in realistic incidents (cascading failure, memory leak, DB outage) for instant trial |

---

## Environment variables

Required for **live mode** only — in demo mode, everything works without keys.

### Backend (`backend/.env`)

```bash
# AWS Bedrock (Amazon Nova Pro)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.nova-pro-v1:0

# Datadog
DATADOG_API_KEY=
DATADOG_APP_KEY=
DATADOG_SITE=datadoghq.com

# Grafana
GRAFANA_URL=
GRAFANA_API_KEY=

# New Relic
NEW_RELIC_USER_KEY=
NEW_RELIC_ACCOUNT_ID=

# Server
PORT=8000
CORS_ORIGINS=http://localhost:3000
```

### Frontend (`frontend/.env.local`)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Project structure

```
IncidentIQ/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── core/                # Config, logging, CORS
│   │   ├── api/                 # HTTP routes (analyze, integrations, export, incidents)
│   │   ├── models/              # Pydantic schemas
│   │   ├── services/            # Business logic
│   │   │   ├── bedrock.py       # AWS Bedrock client
│   │   │   ├── analyzer.py      # Root-cause analysis engine
│   │   │   ├── pdf_export.py    # PDF report generator
│   │   │   ├── store.py         # In-memory incident history
│   │   │   ├── demo_data.py     # Seeded demo incidents
│   │   │   └── integrations/    # Datadog / Grafana / New Relic clients
│   │   └── prompts/             # LLM prompt templates
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   ├── components/          # React components
│   │   └── lib/                 # API client, types, utilities
│   ├── package.json
│   └── .env.example
├── docs/
│   └── ARCHITECTURE.md
└── README.md
```

---

## Deployment

- **Frontend**: Vercel (recommended). `vercel deploy --prod` from `frontend/`.
- **Backend**: AWS Lambda via Mangum, or any container host (Fly.io, Render, Railway). Dockerfile included.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for step-by-step instructions.

---

## License

MIT. Built for the hackathon, ready for production.
