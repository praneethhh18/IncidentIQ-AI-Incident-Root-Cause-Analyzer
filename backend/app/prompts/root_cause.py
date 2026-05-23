"""Prompt templates for incident root-cause analysis.

The prompt is engineered for Amazon Nova Pro. It asks the model to behave
like a Senior SRE, reason step-by-step, and return a single strict JSON
document that maps 1:1 onto :class:`app.models.incident.AnalyzeResponse`.
"""

from __future__ import annotations

from textwrap import dedent

SYSTEM_PROMPT = dedent(
    """
    You are IncidentIQ, an elite Site Reliability Engineer with 15 years of
    on-call experience across distributed systems, databases, networking,
    and cloud infrastructure. You are calm, precise, and evidence-driven.

    A user is paging you in the middle of an outage. Your single job is to
    read the supplied telemetry and produce the highest-signal root-cause
    analysis possible.

    Operating principles:
      • Identify ONE most-likely root cause; do not hedge with three.
      • Quote raw log lines as evidence — never invent log content.
      • Reconstruct the failure timeline strictly from timestamps you see.
      • If a service name appears in the logs, treat it as affected.
      • Severity reflects user-visible impact, not log volume.
      • Fix recommendations must be concrete, actionable, and ranked.
      • If telemetry is ambiguous, say so in `summary` and lower `confidence`.

    Output contract:
      Respond with a SINGLE valid JSON object and nothing else — no prose,
      no markdown fences, no commentary. The JSON must match the schema
      provided in the user message exactly.
    """
).strip()


SCHEMA_HINT = dedent(
    """
    {
      "title": "string — short incident title",
      "summary": "string — one paragraph executive summary",
      "root_cause": "string — the most likely root cause, stated plainly",
      "confidence": 0.0,
      "severity": "P1 | P2 | P3",
      "severity_rationale": "string — why this severity was chosen",
      "affected_services": [
        {
          "name": "string",
          "role": "string — e.g. database, gateway, worker, cache, queue",
          "impact": "string — one-line user-visible impact",
          "health": "healthy | degraded | down"
        }
      ],
      "timeline": [
        {
          "timestamp": "ISO-8601 datetime",
          "label": "string — short event title",
          "detail": "string — one-sentence explanation",
          "severity": "P1 | P2 | P3"
        }
      ],
      "fixes": [
        {
          "title": "string",
          "rationale": "string — why this fix works",
          "action": "string — concrete remediation step",
          "snippet": "string or null — optional command / query / code",
          "priority": 1
        }
      ],
      "evidence": ["string — quoted log line or metric snippet"],
      "forensic": {
        "patient_zero": {
          "timestamp": "ISO-8601 — the FIRST abnormal signal in the cascade",
          "label": "Patient zero — short title",
          "detail": "string — the originating event in one sentence",
          "severity": "P1 | P2 | P3"
        },
        "propagation_path": ["service-a", "service-b", "service-c"],
        "blast_radius": [
          {
            "kind": "service | user_segment | region | dependency | data",
            "name": "string",
            "impact": "string — what this entity experienced",
            "severity": "P1 | P2 | P3"
          }
        ],
        "trigger_hypothesis": "string — most-likely event that birthed patient zero (deploy / config / scaling / dependency failure / resource exhaustion)",
        "trigger_confidence": 0.0,
        "minutes_to_detection": 0
      }
    }
    """
).strip()


def build_user_prompt(
    *,
    logs: str,
    service_hint: str | None,
    source_label: str,
    agent_context: dict | None = None,
) -> str:
    """Compose the user-turn prompt fed to the model.

    When ``agent_context`` is supplied (produced by the agent's
    plan/observe loop), the model is asked to reason from those grounded
    observations rather than re-discovering them.
    """
    hint_line = (
        f"User-supplied focus hint: '{service_hint}'."
        if service_hint
        else "No service hint provided — infer affected services from the logs."
    )

    context_block = _format_agent_context(agent_context) if agent_context else ""

    return dedent(
        f"""
        Telemetry source: {source_label}
        {hint_line}

        {context_block}

        Raw telemetry (logs, metrics, alerts):
        ─── BEGIN ───────────────────────────────────────────────
        {logs.strip()}
        ─── END ─────────────────────────────────────────────────

        Produce the root-cause analysis as a single JSON object matching this
        schema exactly. Do not wrap in markdown. Do not add commentary.

        {SCHEMA_HINT}
        """
    ).strip()


def _format_agent_context(ctx: dict) -> str:
    """Render the agent's observations as a compact briefing for the model."""
    entities = ctx.get("entities") or {}
    timeline_obs = ctx.get("timeline_obs") or {}
    roles = (ctx.get("service_roles") or {}).get("roles") or {}
    grep = ctx.get("hypothesis_evidence") or {}
    similar = (ctx.get("similar") or {}).get("matches") or []

    lines = ["Agent pre-analysis briefing (use these grounded observations):"]
    if entities:
        lines.append(
            f"  • Services observed: {', '.join(entities.get('services', []) or []) or 'none extracted'}"
        )
        lines.append(
            f"  • Severity mix: {entities.get('level_counts') or 'unknown'}; "
            f"signal keywords: {entities.get('signature_keywords') or 'none'}"
        )
        if entities.get("first_timestamp"):
            lines.append(
                f"  • Time window: {entities['first_timestamp']} → {entities.get('last_timestamp')}"
            )
    if roles:
        roles_str = "; ".join(f"{role}={','.join(svcs)}" for role, svcs in roles.items())
        lines.append(f"  • Inferred service roles: {roles_str}")
    if timeline_obs.get("events"):
        lines.append(
            f"  • Chronological events: {timeline_obs.get('total_significant_events')} "
            f"significant entries (oldest first)."
        )
    if grep.get("matches"):
        lines.append(
            f"  • Hypothesis grep `{grep.get('pattern')}` returned "
            f"{grep.get('total')} matching line(s) — use as evidence."
        )
    if similar:
        s = ", ".join(f"{m['incident_id']} ({m['severity']})" for m in similar)
        lines.append(f"  • Related past incidents: {s}")

    return "\n".join(lines)
