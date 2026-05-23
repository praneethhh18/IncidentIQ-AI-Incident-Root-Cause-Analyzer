# IncidentIQ — Hackathon Submission

> Agentic AI Hackathon · Problem #3 — AI Incident Root Cause Analyzer for SRE Teams

This document maps the submission to the hackathon rules and explains
how IncidentIQ is built as a genuine **agentic** AI product rather than a
single-turn chat wrapper.

---

## TL;DR

- **Problem:** Engineers waste hours scrolling logs and dashboards during outages.
- **Solution:** An AI agent that ingests logs from Datadog / Grafana / New Relic / PagerDuty / Opsgenie webhooks (or pasted text), runs a multi-step think-act-observe loop with **eight tools**, performs **forensic reverse-engineering** (patient zero, blast radius, trigger hypothesis), and produces root cause + timeline + ranked fixes + PDF post-mortem in seconds.
- **Why agentic:** The agent calls deterministic tools (`extract_entities`, `correlate_timeline`, `search_logs`, `service_dependency_hints`, `query_similar_incidents`, `trace_origin`, `compute_blast_radius`, `infer_trigger`) **before** the LLM ever sees the prompt, then self-checks the LLM output against grounded observations. The reasoning trail **streams live via SSE** so judges watch the agent think.
- **Wow moment:** Forensic mode — inspired by malware-forensic tooling, it reverse-engineers the entire cascade back to patient zero and forward to every affected entity.

---

## Compliance with hackathon rules

### Core focus — "AI agents that can think, interact with tools, execute tasks independently"

| Requirement | How IncidentIQ satisfies it |
| --- | --- |
| **Think** | The agent maintains a visible chain of thoughts and decisions across 8+ reasoning steps per run (see `agent_steps[]` in any analysis). |
| **Interact with tools** | Five typed tools in [`backend/app/services/agent_tools.py`](backend/app/services/agent_tools.py): entity extraction, log search, timeline correlation, service-role inference, similar-incident lookup. The agent decides which tools to call based on what it observes. |
| **Execute tasks independently** | One HTTP call (`POST /api/v1/analyze`) triggers the full loop — no human-in-the-loop required between the tools. The agent independently chooses its hypothesis, validates it, and synthesises the final structured analysis. |

### Required deliverables

| Deliverable | Status |
| --- | --- |
| Complete agentic AI solution | ✅ Full-stack: FastAPI agent backend + Next.js 14 dashboard |
| Practical, real-world problem | ✅ SRE incident triage — every on-call engineer's pain |
| End-to-end product journey | ✅ Problem → architecture → integrations (Datadog/Grafana/New Relic + AWS Bedrock Nova Pro) → working product → PDF export |
| Functional prototype | ✅ Runs locally end-to-end, demo mode works with zero credentials |
| Demo video / live working product | ✅ Demo script in [README.md](README.md#demo-3-minute-walkthrough) |
| Codebase access | ✅ This repository |
| Brief explanation | ✅ [README.md](README.md) + [ARCHITECTURE.md](ARCHITECTURE.md) + this file |
| Process documentation | ✅ Problem → solution → architecture documented in [ARCHITECTURE.md](ARCHITECTURE.md) |

### Rules

| Rule | Status |
| --- | --- |
| Not a pre-built solution | ✅ Built from scratch during the hackathon window — see "Contribution breakdown" below |
| No plagiarism | ✅ All code original to this project; third-party libraries are standard open-source (FastAPI, Next.js, Tailwind, ReportLab, boto3) declared in `requirements.txt` / `package.json` |
| Contribution vs AI-generated output | ✅ Documented below |
| Fully working product | ✅ All 11 backend endpoints smoke-tested green; frontend builds clean with `next build`; demo mode requires no credentials |
| Submitted on time | ✅ Submitting before deadline |

---

## Agentic architecture (the part that matters)

IncidentIQ is structured as a four-phase agent rather than a single LLM call:

```
┌────────────────────────────────────────────────────────────────────┐
│ 1. PERCEIVE                                                        │
│    Resolve logs from the requested source (paste, upload, Datadog, │
│    Grafana, or New Relic — each with a graceful seeded fallback).  │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│ 2. PLAN & OBSERVE   (IncidentAgent.plan_and_observe)               │
│    Multi-step loop. The agent:                                     │
│      • Plans its investigation                                     │
│      • Calls extract_entities() to inventory services & signals    │
│      • Reflects on what it found                                   │
│      • Calls correlate_timeline() to order events chronologically  │
│      • Calls service_dependency_hints() to classify service roles  │
│      • Picks the strongest signal keyword as a hypothesis          │
│      • Calls search_logs() to test that hypothesis                 │
│      • Calls query_similar_incidents() for institutional memory    │
│      • Decides it has enough evidence to synthesise                │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│ 3. SYNTHESISE   (BedrockClient.converse_json)                      │
│    AWS Bedrock — Amazon Nova Pro — receives the grounded briefing  │
│    *plus* the raw telemetry, and returns a structured JSON         │
│    analysis (root cause / timeline / services / severity / fixes / │
│    evidence). Falls back to a hand-crafted analysis when Bedrock   │
│    is not configured.                                              │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│ 4. SELF-CHECK   (IncidentAgent.audit_and_annotate)                 │
│    The agent verifies that every service the LLM named was         │
│    actually observed in the logs. If not, confidence is reduced    │
│    by 15% and an audit step is appended to the trail.              │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    AnalyzeResponse (with agent_steps[])
```

The complete trail — every thought, tool call, observation, and decision —
is returned to the client and rendered in the UI under "Agent reasoning trail".

### Agent tools

| Tool | Purpose | File |
| --- | --- | --- |
| `extract_entities(logs)` | Inventory services, error levels, signal keywords, time bounds | `backend/app/services/agent_tools.py` |
| `correlate_timeline(logs)` | Order WARN/ERROR/FATAL events chronologically | same |
| `service_dependency_hints(services)` | Infer service roles (api/db/cache/worker/gateway) | same |
| `search_logs(logs, pattern)` | Regex grep against the log payload to test a hypothesis | same |
| `query_similar_incidents(signature)` | Look up past analyses with overlapping signatures | same |

---

## Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind | Modern, fast, deployable to Vercel in one command |
| Backend | FastAPI + Pydantic v2 (Python 3.11+) | Strict typed contracts make the agent loop safe |
| AI | AWS Bedrock — Amazon Nova Pro via Converse API | Enterprise-grade, swappable to any Bedrock model |
| Integrations | Datadog Logs Search v2, Grafana/Loki, New Relic NerdGraph/NRQL | Real APIs, each with a seeded fallback |
| PDF | ReportLab | Pure Python, no system deps — works on Vercel/Lambda |
| Store | In-memory (thread-safe, bounded) | Hackathon-friendly; swappable for SQLite/Postgres |

---

## Contribution breakdown — human vs AI

Per the hackathon rule: *"Teams must clearly specify their actual contribution vs AI-generated output."*

### Human contribution (the work I owned)

- **Problem selection and product framing.** Picked problem #3, defined the value prop ("what took 2 hours now takes 10 seconds"), and chose to position this as an SRE-grade tool with severity reasoning and PDF post-mortems rather than a generic log chat-bot.
- **Agent architecture.** Designed the four-phase agent loop (perceive → plan & observe → synthesise → self-check) and the five tools the agent has access to. This is the differentiator from a single-call LLM wrapper.
- **Demo strategy.** Decided the app must work end-to-end without any credentials so judges can try it instantly. This drove the "graceful fallback at every layer" pattern (`BedrockClient`, `MonitoringIntegration` fallbacks, `demo_data.fallback_analysis`).
- **Demo incident fixtures.** The three seeded incidents (cascading checkout failure, JVM memory leak, RDS failover) were hand-written to read like real production failure modes that an experienced SRE would recognise.
- **Prompt engineering.** The system prompt that frames the LLM as a "15-year senior SRE", the strict JSON output contract, and the agent briefing format.
- **Visual identity and UX.** Dark SRE-grade dashboard aesthetic, severity colour system, agent-trail visualisation pattern, copy-to-clipboard fix snippets.
- **Verification.** Smoke-testing all 11 endpoints and the full-stack build.

### AI assistance

- **Code generation.** AI tools were used to author the codebase under the architecture, prompts, and product decisions above. Every file was reviewed and verified to compile, build, and pass end-to-end smoke tests against the running stack.
- **Boilerplate scaffolding.** Tailwind config, FastAPI routing patterns, ReportLab styling — standard scaffolding accelerated by AI but reviewed for correctness.

### Pure third-party (open source)

- Libraries: FastAPI, Pydantic, Uvicorn, httpx, boto3, ReportLab, Next.js, React, Tailwind, lucide-react, clsx, tailwind-merge. All standard, all declared in `requirements.txt` / `package.json`.
- AWS Bedrock — Amazon Nova Pro is the model used for the final synthesis step.

---

## Demo script (3 minutes)

| Time | Beat |
| --- | --- |
| 0:00 | "It's 3am. Your app is down. 500 lines of logs. Your CEO is in the channel. This is IncidentIQ." |
| 0:20 | Open landing page → click **Try it now** |
| 0:35 | Show the dashboard — point out the three integrations (Datadog/Grafana/New Relic) and the **Try a sample incident** chips |
| 0:50 | Click **Cascading checkout failure** sample → click **Analyze incident** |
| 1:10 | Result loads: severity P1, root cause, confidence bar, summary |
| 1:25 | Scroll to **Affected services** — 5 services classified by role and health |
| 1:40 | **Incident timeline** — point out the chronological cascade |
| 1:55 | **Fix recommendations** — copy one of the SQL snippets to clipboard to show it's real |
| 2:10 | **Agent reasoning trail** — expand one tool call to show the JSON observation. This is where you sell the agentic nature. |
| 2:35 | Click **Export PDF** → open the post-mortem |
| 2:50 | Close: "What took 2 hours now takes 10 seconds. IncidentIQ." |

---

## How to run for the judges

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000

# Frontend (in another terminal)
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Open <http://localhost:3000>. **Works immediately — no API keys required.**

For live AWS Bedrock + monitoring integrations, drop keys into `backend/.env`:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` (with Bedrock model access for `amazon.nova-pro-v1:0`)
- Optional: `DATADOG_API_KEY` + `DATADOG_APP_KEY`, `GRAFANA_URL` + `GRAFANA_API_KEY`, `NEW_RELIC_USER_KEY` + `NEW_RELIC_ACCOUNT_ID`
