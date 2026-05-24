"""Root-cause analysis engine.

Coordinates Bedrock inference, integration data sources, and the demo
fallback so that callers always get a well-formed :class:`AnalyzeResponse`,
even when AWS or monitoring credentials are absent.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, Optional

from app.core.config import Settings
from app.models import AnalyzeRequest, AnalyzeResponse, SourceKind
from app.prompts.root_cause import SYSTEM_PROMPT, build_user_prompt
from app.services.agent import IncidentAgent
from app.services.bedrock import BedrockClient, BedrockUnavailable
from app.services.deep_trace import should_escalate as _should_escalate
from app.services.demo_data import fallback_analysis
from app.services.impact import build_five_whys
from app.services.integrations import IntegrationRegistry

logger = logging.getLogger(__name__)

MAX_LOG_CHARS = 80_000  # ~16k tokens — generous, still safely below model limits

# In live mode (Bedrock enabled) we refuse to "analyze" telemetry that has
# essentially no signal. Calling the LLM on a single sentinel comment line
# invites it to invent an incident from nothing, so we reject upstream
# instead. Thresholds are deliberately permissive - a handful of error
# lines is plenty for real analysis.
_MIN_SIGNAL_LINES = 3
_SIGNAL_LEVEL_TOKENS = ("error", "fatal", "warn", "warning", "exception", "panic")


class Analyzer:
    """High-level orchestration around Bedrock + integrations + fallbacks."""

    def __init__(
        self,
        settings: Settings,
        bedrock: BedrockClient,
        integrations: IntegrationRegistry,
        agent: IncidentAgent | None = None,
    ) -> None:
        self._settings = settings
        self._bedrock = bedrock
        self._integrations = integrations
        self._agent = agent or IncidentAgent()

    async def analyze_stream(
        self, request: AnalyzeRequest, step_delay: float = 0.18
    ) -> AsyncIterator[Dict[str, Any]]:
        """Same flow as ``analyze()``, but yields incremental events.

        Each event is a small JSON-serialisable dict that the SSE endpoint
        can emit straight to the client. The agent's reasoning trail
        streams step-by-step so judges (and humans) can watch the agent
        think in real time.
        """
        started = time.perf_counter()

        yield {"event": "phase", "phase": "perceive", "message": "Resolving telemetry source…"}

        try:
            logs = await self._resolve_logs(request)
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "message": f"Failed to resolve logs: {exc}"}
            return

        if not logs:
            yield {
                "event": "error",
                "message": "No logs provided. Paste/upload a payload or configure an integration.",
            }
            return

        if self._bedrock.enabled and not _has_enough_signal(logs):
            yield {
                "event": "error",
                "message": (
                    "Telemetry returned no error-level signal in this window. "
                    "Nothing to analyze - try widening the time window or "
                    "loosening the query."
                ),
            }
            return

        truncated = _truncate_logs(logs)
        yield {
            "event": "phase",
            "phase": "agent",
            "message": "Agent investigating…",
            "log_lines": logs.count("\n") + 1,
        }

        trail, agent_context = self._agent.plan_and_observe(truncated)

        # Stream each agent step with a small delay for visceral effect.
        for step in trail:
            yield {"event": "agent_step", "step": step.model_dump(mode="json")}
            if step_delay > 0:
                await asyncio.sleep(step_delay)

        yield {
            "event": "phase",
            "phase": "synthesize",
            "message": "Synthesising root cause with Bedrock Nova Pro…",
        }

        result = self._run_inference(
            logs=truncated,
            agent_context=agent_context,
            service_hint=request.service_hint,
            source=request.source,
            title=request.title,
        )

        yield {
            "event": "phase",
            "phase": "audit",
            "message": "Self-checking grounding…",
        }

        result = self._agent.audit_and_annotate(trail, agent_context, result)

        yield {
            "event": "phase",
            "phase": "five-whys",
            "message": "Generating 5 Whys postmortem…",
        }
        if result.five_whys is None:
            result.five_whys = build_five_whys(result, bedrock=self._bedrock)

        should_escalate_flag, escalate_reason = _should_escalate(result)
        result.should_escalate = should_escalate_flag
        result.escalation_reason = escalate_reason

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        result.duration_ms = elapsed_ms
        result.source = request.source
        if request.title:
            result.title = request.title

        yield {
            "event": "complete",
            "analysis": result.model_dump(mode="json"),
        }

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        started = time.perf_counter()

        logs = await self._resolve_logs(request)
        if not logs:
            raise ValueError(
                "No logs provided. Either paste/upload a log payload, or "
                "configure an integration and pass an integration_query."
            )

        if self._bedrock.enabled and not _has_enough_signal(logs):
            raise ValueError(
                "Telemetry returned no error-level signal in this window. "
                "Nothing to analyze - try widening the time window or "
                "loosening the query."
            )

        truncated = _truncate_logs(logs)

        # Phase 1 — agent runs its deterministic plan/observe loop and gathers
        # grounded context BEFORE the LLM ever sees the prompt. This is the
        # "agentic" part: the agent decides which tools to call based on what
        # it sees, and produces a visible reasoning trail.
        trail, agent_context = self._agent.plan_and_observe(truncated)

        # Phase 2 — synthesise the final structured analysis (LLM or fallback).
        result = self._run_inference(
            logs=truncated,
            agent_context=agent_context,
            service_hint=request.service_hint,
            source=request.source,
            title=request.title,
        )

        # Phase 3 — self-check and stitch the audit trail onto the response.
        result = self._agent.audit_and_annotate(trail, agent_context, result)

        # Phase 4 — derive the 5 Whys postmortem from the structured analysis.
        # Runs regardless of whether Bedrock supplied one, so the dashboard
        # always has the full picture.
        if result.five_whys is None:
            result.five_whys = build_five_whys(result, bedrock=self._bedrock)

        # Phase 5 — recommend Deep Trace if the regular pass looks shaky.
        should_escalate_flag, escalate_reason = _should_escalate(result)
        result.should_escalate = should_escalate_flag
        result.escalation_reason = escalate_reason

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        result.duration_ms = elapsed_ms
        result.source = request.source
        if request.title:
            result.title = request.title
        return result

    # ── Source resolution ──────────────────────────────────────────────

    async def _resolve_logs(self, request: AnalyzeRequest) -> Optional[str]:
        """Return the raw text to analyse, pulling from integrations as needed."""
        if request.logs:
            return request.logs

        if request.source in (SourceKind.PASTE, SourceKind.UPLOAD, SourceKind.DEMO):
            return None  # nothing to fall back to

        integration = self._integrations.get(request.source)
        if integration is None:
            logger.warning("No integration registered for source=%s", request.source)
            return None

        return await integration.fetch_logs(
            query=request.integration_query,
            window_minutes=request.time_window_minutes,
        )

    # ── Inference + fallback ───────────────────────────────────────────

    def _run_inference(
        self,
        *,
        logs: str,
        agent_context: dict,
        service_hint: str | None,
        source: SourceKind,
        title: str | None,
    ) -> AnalyzeResponse:
        # Demo mode is legitimate only when Bedrock isn't configured at all.
        # In live mode we never silently substitute the pre-canned demo
        # analysis - that would present fabricated data as a real result.
        if not self._bedrock.enabled:
            logger.info("Bedrock disabled - returning demo fallback analysis")
            return _stamp_fallback(fallback_analysis(logs), title)

        user_prompt = build_user_prompt(
            logs=logs,
            service_hint=service_hint,
            source_label=source.value,
            agent_context=agent_context,
        )

        try:
            payload = self._bedrock.converse_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=2048,
                temperature=0.2,
            )
        except BedrockUnavailable:
            # Surface honestly rather than masking with canned demo content.
            logger.exception("Bedrock call failed in live mode")
            raise

        try:
            return AnalyzeResponse(
                model=self._bedrock.model_id,
                **payload,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bedrock returned payload that failed schema validation")
            raise BedrockUnavailable(
                f"Model returned a response that didn't match the analysis schema: {exc}"
            ) from exc


def _stamp_fallback(response: AnalyzeResponse, title: str | None) -> AnalyzeResponse:
    if title:
        response.title = title
    return response


def _truncate_logs(logs: str) -> str:
    if len(logs) <= MAX_LOG_CHARS:
        return logs
    head = logs[: MAX_LOG_CHARS // 2]
    tail = logs[-MAX_LOG_CHARS // 2 :]
    return f"{head}\n\n… [truncated {len(logs) - MAX_LOG_CHARS} chars] …\n\n{tail}"


def _has_enough_signal(logs: str) -> bool:
    """True when the payload has enough error-level signal to analyze.

    A monitoring pull that returns zero error lines (or a single sentinel
    comment from the integration saying 'no events found') is not an
    incident - we refuse to fabricate one out of it.
    """
    real_lines = [
        line for line in logs.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(real_lines) < _MIN_SIGNAL_LINES:
        return False
    lowered = logs.lower()
    return any(tok in lowered for tok in _SIGNAL_LEVEL_TOKENS)
