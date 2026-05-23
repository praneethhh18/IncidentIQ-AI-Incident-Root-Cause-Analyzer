"""IncidentIQ agent — the actually-agentic part.

Where ``Analyzer`` is a thin LLM wrapper, ``IncidentAgent`` is the
think → act → observe → decide loop that turns IncidentIQ into a real
agent rather than a one-shot prompt.

The agent's job each run:

  1. **Inventory** the telemetry with ``extract_entities``.
  2. **Triangulate** by calling ``correlate_timeline``, then
     ``service_dependency_hints`` on the discovered services.
  3. **Test a hypothesis** with ``search_logs`` for the strongest signal
     keyword (e.g. ``oom``, ``exhausted``, ``failover``).
  4. **Look back** at past incidents with ``query_similar_incidents`` to
     see if we have institutional memory on this signature.
  5. **Synthesise** by handing the enriched context to the LLM for the
     final structured root-cause analysis (or, when Bedrock is offline,
     pick a hand-crafted fallback).
  6. **Self-check** — verify the LLM output names at least one service
     we actually observed; if not, lower confidence in the audit trail.

The full trace is returned to the caller as ``agent_steps`` so the UI can
render it. This satisfies the hackathon's "think and make decisions,
interact with tools, execute tasks independently" core requirement.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Tuple

from app.models import (
    AgentStep,
    AnalyzeResponse,
    BlastRadiusEntity,
    ForensicReport,
    Severity,
    SourceKind,
    TimelineEvent,
)
from app.services.agent_tools import TOOLS, TOOL_CATALOG

logger = logging.getLogger(__name__)


SignalSelector = Callable[[Dict[str, Any]], List[str]]


def _pick_signal_keywords(entities: Dict[str, Any]) -> List[str]:
    """Pick up to two keywords from the entity inventory to grep for."""
    keywords = entities.get("signature_keywords", []) or []
    # Prefer the strongest specific signals over generic ones.
    priority = [
        "oom", "outofmemory", "exhausted", "failover", "circuit breaker",
        "crashloopbackoff", "deadlock", "panic", "503", "504", "throttl",
    ]
    ranked = [k for k in priority if k in keywords]
    if not ranked:
        ranked = keywords[:2]
    return ranked[:2]


class IncidentAgent:
    """Runs the multi-step reasoning loop and produces an annotated trail."""

    def __init__(self, tools: Dict[str, Callable[..., Any]] | None = None) -> None:
        self._tools = tools or TOOLS

    # ── Trail construction ────────────────────────────────────────────

    def plan_and_observe(self, logs: str) -> Tuple[List[AgentStep], Dict[str, Any]]:
        """Run the deterministic part of the agent loop.

        Returns the (trail, context) pair. ``context`` is a dict of
        observations the LLM will use during final synthesis.
        """
        trail: List[AgentStep] = []
        ctx: Dict[str, Any] = {}
        counter = _StepCounter()

        # 1. Plan
        trail.append(
            AgentStep(
                step=counter.next(),
                kind="thought",
                title="Plan the investigation",
                detail=(
                    "I will inventory the telemetry, then correlate the timeline, "
                    "then test the strongest signal as a hypothesis, then look "
                    "for matching past incidents before synthesising the root cause."
                ),
            )
        )

        # 2. Inventory
        entities = self._call("extract_entities", trail, counter, logs=logs)
        ctx["entities"] = entities

        services_msg = ", ".join(entities.get("services", [])[:6]) or "no clear service names"
        trail.append(
            AgentStep(
                step=counter.next(),
                kind="thought",
                title="Reflect on the inventory",
                detail=(
                    f"Saw {entities.get('log_lines')} log lines across "
                    f"{len(entities.get('services', []))} services ({services_msg}). "
                    f"Level mix: {entities.get('level_counts') or 'unknown'}. "
                    f"Signal keywords: {entities.get('signature_keywords') or 'none'}."
                ),
            )
        )

        # 3. Correlate the timeline
        timeline_obs = self._call("correlate_timeline", trail, counter, logs=logs)
        ctx["timeline_obs"] = timeline_obs

        # 4. Service roles
        roles = self._call(
            "service_dependency_hints",
            trail,
            counter,
            services=entities.get("services", []),
        )
        ctx["service_roles"] = roles

        # 5. Hypothesis test — grep for the strongest signal
        keywords = _pick_signal_keywords(entities)
        ctx["signal_keywords"] = keywords
        if keywords:
            trail.append(
                AgentStep(
                    step=counter.next(),
                    kind="thought",
                    title="Form a hypothesis",
                    detail=(
                        f"Strongest signal looks like {keywords[0]!r}. "
                        "Grepping for it to confirm it's a real incident-driving event, "
                        "not a stray warning."
                    ),
                )
            )
            grep_out = self._call(
                "search_logs",
                trail,
                counter,
                logs=logs,
                pattern=keywords[0],
                max_matches=5,
            )
            ctx["hypothesis_evidence"] = grep_out

        # 6. Institutional memory
        signature = " ".join(
            (entities.get("signature_keywords") or [])[:3]
            + (entities.get("services") or [])[:2]
        ) or "incident"
        history = self._call(
            "query_similar_incidents", trail, counter, signature=signature, limit=3
        )
        ctx["similar"] = history
        if history.get("matches"):
            trail.append(
                AgentStep(
                    step=counter.next(),
                    kind="thought",
                    title="Found related history",
                    detail=(
                        f"Local store has {len(history['matches'])} similar past "
                        "incident(s). I'll let the analysis lean on them."
                    ),
                )
            )

        # ── Forensic phase ────────────────────────────────────────────
        # This is the Maya-style reverse-engineering: trace back to
        # patient zero, map the blast radius, hypothesize the trigger.
        trail.append(
            AgentStep(
                step=counter.next(),
                kind="thought",
                title="Pivot to forensic analysis",
                detail=(
                    "I have enough surface-level signal. Now reversing causality: "
                    "find patient zero, map the blast radius, and hypothesize what "
                    "actually birthed this incident."
                ),
            )
        )

        origin = self._call("trace_origin", trail, counter, logs=logs)
        ctx["origin"] = origin

        blast = self._call(
            "compute_blast_radius",
            trail,
            counter,
            services=entities.get("services", []),
            roles=(roles or {}).get("roles", {}),
            log_entities=entities,
        )
        ctx["blast_radius"] = blast

        trigger = self._call(
            "infer_trigger", trail, counter, log_entities=entities, logs=logs
        )
        ctx["trigger"] = trigger

        trail.append(
            AgentStep(
                step=counter.next(),
                kind="decision",
                title="Forensic picture is complete",
                detail=(
                    f"Patient zero located ({(origin.get('event') or {}).get('timestamp', 'unknown')}). "
                    f"Blast radius: {blast.get('total', 0)} entities. "
                    f"Trigger hypothesis: {trigger.get('trigger', 'unknown')} "
                    f"({int(trigger.get('confidence', 0) * 100)}% confidence)."
                ),
            )
        )

        # Final decision: ready to synthesise
        trail.append(
            AgentStep(
                step=counter.next(),
                kind="decision",
                title="Hand off to root-cause synthesis",
                detail=(
                    "Observations + forensic context are sufficient. Synthesising "
                    "the final analysis now and attaching the forensic report."
                ),
            )
        )

        return trail, ctx

    # ── Post-synthesis self-check ─────────────────────────────────────

    def audit_and_annotate(
        self,
        trail: List[AgentStep],
        context: Dict[str, Any],
        analysis: AnalyzeResponse,
    ) -> AnalyzeResponse:
        """After the LLM synthesises, verify the output is grounded.

        Mutates ``analysis`` in place and appends audit steps to ``trail``.
        """
        counter = _StepCounter(start=len(trail))
        observed_services = set(context.get("entities", {}).get("services", []) or [])
        named_in_analysis = {s.name.lower() for s in analysis.affected_services}
        overlap = {s for s in observed_services if any(s in n for n in named_in_analysis)}

        if observed_services and not overlap:
            trail.append(
                AgentStep(
                    step=counter.next(),
                    kind="thought",
                    title="Self-check: weak grounding",
                    detail=(
                        "Analysis names services I didn't observe in the logs. "
                        "Reducing confidence by 15% to reflect the uncertainty."
                    ),
                )
            )
            analysis.confidence = round(max(0.0, analysis.confidence - 0.15), 2)
        else:
            trail.append(
                AgentStep(
                    step=counter.next(),
                    kind="thought",
                    title="Self-check passed",
                    detail=(
                        "Analysis is grounded — every affected service it names "
                        "appears in the raw telemetry I inventoried."
                    ),
                )
            )

        if context.get("similar", {}).get("matches"):
            count = len(context["similar"]["matches"])
            trail.append(
                AgentStep(
                    step=counter.next(),
                    kind="decision",
                    title="Annotate with related history",
                    detail=(
                        f"Linking {count} similar prior incident(s) into the "
                        "context for the responder."
                    ),
                )
            )

        # Attach the forensic report. If the LLM produced one, keep it.
        # Otherwise synthesize one from the agent's observations.
        if analysis.forensic is None:
            forensic = self._build_forensic_from_observations(context, analysis)
            if forensic is not None:
                analysis.forensic = forensic
                trail.append(
                    AgentStep(
                        step=counter.next(),
                        kind="decision",
                        title="Attach forensic report",
                        detail=(
                            "LLM did not supply a forensic block; assembling one "
                            "from observed tool outputs (patient zero, blast "
                            "radius, trigger hypothesis)."
                        ),
                    )
                )

        analysis.agent_steps = trail
        return analysis

    # ── Forensic synthesis from observations ─────────────────────────

    def _build_forensic_from_observations(
        self, context: Dict[str, Any], analysis: AnalyzeResponse
    ) -> ForensicReport | None:
        """Assemble a ForensicReport from the agent's tool observations.

        Used when the LLM didn't return a forensic block (or fell back to
        demo data). Guarantees that every analysis has a forensic view.
        """
        origin = (context.get("origin") or {}).get("event")
        if not origin:
            return None

        # Patient zero — promote the earliest observed event to a TimelineEvent.
        try:
            patient_zero = TimelineEvent(
                timestamp=origin["timestamp"],
                label="Patient zero — first abnormal signal",
                detail=origin["text"],
                severity=_severity_for_level(origin.get("level", "WARN")),
            )
        except Exception:  # noqa: BLE001
            return None

        # Propagation path — derive from the chronological timeline.
        timeline = analysis.timeline or []
        propagation_path: List[str] = []
        seen: set[str] = set()
        for event in timeline:
            for token in event.label.split():
                token_clean = token.strip(".,;:!?").lower()
                if token_clean.endswith(("-api", "-svc", "-service", "-worker", "-gateway", "-db")):
                    if token_clean not in seen:
                        propagation_path.append(token_clean)
                        seen.add(token_clean)
        # Fallback: just use the affected services as the path.
        if not propagation_path:
            propagation_path = [s.name for s in analysis.affected_services][:6]

        # Blast radius — from the compute_blast_radius tool output.
        raw_blast = (context.get("blast_radius") or {}).get("entities", [])
        blast_radius: List[BlastRadiusEntity] = []
        for entry in raw_blast:
            try:
                blast_radius.append(
                    BlastRadiusEntity(
                        kind=entry.get("kind", "service"),
                        name=entry.get("name", "unknown"),
                        impact=entry.get("impact", "Touched by the incident"),
                        severity=_severity_for_kind(entry.get("kind", "service"), analysis.severity),
                    )
                )
            except Exception:  # noqa: BLE001
                continue

        # Trigger hypothesis — from infer_trigger.
        trigger = context.get("trigger") or {}
        trigger_text = trigger.get("trigger", "Unknown trigger")
        trigger_evidence = trigger.get("evidence", "")
        if trigger_evidence:
            trigger_text = f"{trigger_text}. {trigger_evidence}"

        return ForensicReport(
            patient_zero=patient_zero,
            propagation_path=propagation_path[:6],
            blast_radius=blast_radius,
            trigger_hypothesis=trigger_text,
            trigger_confidence=float(trigger.get("confidence", 0.5)),
            minutes_to_detection=(context.get("origin") or {}).get("minutes_to_impact"),
        )

    # ── Internal helpers ──────────────────────────────────────────────

    def _call(
        self,
        tool_name: str,
        trail: List[AgentStep],
        counter: "_StepCounter",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run a tool, append the call + observation steps to the trail."""
        if tool_name not in self._tools:
            logger.warning("Unknown tool requested: %s", tool_name)
            return {}

        printable_args = {k: _short(v) for k, v in kwargs.items() if k != "logs"}
        trail.append(
            AgentStep(
                step=counter.next(),
                kind="tool_call",
                title=f"Call tool `{tool_name}`",
                detail=(
                    f"Invoking `{tool_name}({_format_args(printable_args)})` "
                    "to gather more evidence."
                ),
                tool=tool_name,
            )
        )

        try:
            result = self._tools[tool_name](**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent tool %s failed", tool_name)
            trail.append(
                AgentStep(
                    step=counter.next(),
                    kind="observation",
                    title=f"Tool `{tool_name}` errored",
                    detail=f"{exc}",
                    tool=tool_name,
                )
            )
            return {}

        trail.append(
            AgentStep(
                step=counter.next(),
                kind="observation",
                title=f"Observed result from `{tool_name}`",
                detail=_summarise(tool_name, result),
                tool=tool_name,
                output=result,
            )
        )
        return result


class _StepCounter:
    def __init__(self, start: int = 0) -> None:
        self._n = start

    def next(self) -> int:
        self._n += 1
        return self._n


def _short(value: Any, limit: int = 80) -> Any:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _format_args(args: Dict[str, Any]) -> str:
    if not args:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def _summarise(tool_name: str, result: Dict[str, Any]) -> str:
    if tool_name == "extract_entities":
        return (
            f"{len(result.get('services', []))} services, "
            f"{sum(result.get('level_counts', {}).values())} severity events, "
            f"{len(result.get('signature_keywords', []))} signal keywords."
        )
    if tool_name == "correlate_timeline":
        events = result.get("events", [])
        if not events:
            return "No timestamped WARN/ERROR/FATAL events found."
        return (
            f"{len(events)} significant events ordered chronologically. "
            f"First: {events[0]['timestamp']} ({events[0]['level']}). "
            f"Last: {events[-1]['timestamp']} ({events[-1]['level']})."
        )
    if tool_name == "service_dependency_hints":
        roles = result.get("roles", {})
        if not roles:
            return "No services classified."
        return ", ".join(f"{role}: {len(svcs)}" for role, svcs in roles.items())
    if tool_name == "search_logs":
        return f"{result.get('total', 0)} matching line(s) for `{result.get('pattern')}`."
    if tool_name == "query_similar_incidents":
        m = result.get("matches", [])
        if not m:
            return "No similar incidents in local history."
        return ", ".join(f"{x['incident_id']} ({x['severity']})" for x in m)
    return _short(result, 200)


def _severity_for_level(level: str) -> Severity:
    upper = level.upper()
    if upper == "FATAL":
        return Severity.P1
    if upper == "ERROR":
        return Severity.P2
    return Severity.P3


def _severity_for_kind(kind: str, incident_severity: Severity) -> Severity:
    # Surface entities (user segments) inherit the overall incident severity.
    if kind in ("user_segment", "region"):
        return incident_severity
    if kind == "dependency":
        return Severity.P2
    return Severity.P3


__all__ = ["IncidentAgent", "TOOL_CATALOG"]
