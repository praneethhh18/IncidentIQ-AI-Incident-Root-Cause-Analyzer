"""Pydantic models for the analyze / incident lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class SourceKind(str, Enum):
    PASTE = "paste"
    UPLOAD = "upload"
    DATADOG = "datadog"
    GRAFANA = "grafana"
    NEWRELIC = "newrelic"
    DEMO = "demo"
    WEBHOOK = "webhook"


class TimelineEvent(BaseModel):
    timestamp: datetime
    label: str = Field(..., description="Short title of the event")
    detail: str = Field(..., description="One-sentence explanation")
    severity: Severity = Severity.P3


class AffectedService(BaseModel):
    name: str
    role: str = Field(..., description="e.g. 'database', 'gateway', 'worker'")
    impact: str = Field(..., description="One-line summary of the impact")
    health: str = Field("degraded", description="healthy | degraded | down")


class BlastRadiusEntity(BaseModel):
    """One thing the incident touched — service, user segment, region, dependency."""

    kind: str = Field(..., description="service | user_segment | region | dependency | data")
    name: str
    impact: str
    severity: Severity | None = Field(default=None)


class HiddenSignal(BaseModel):
    """A subtle pattern surfaced by Deep Trace that the regular pass missed.

    Examples: silent failures (200 OK followed by ERROR), regular-interval
    cron-like patterns, events arriving out of expected order, services
    that suddenly go silent mid-incident.
    """

    category: str = Field(..., description="silent_failure | timing_anomaly | order_anomaly | service_silence | hidden_dependency")
    title: str = Field(..., description="Short label for the signal")
    detail: str = Field(..., description="One-paragraph explanation of what was found")
    evidence: List[str] = Field(default_factory=list, description="Raw log lines supporting the signal")
    severity: "Severity" = Field(default=None)


class ServiceProbe(BaseModel):
    """Result of a focused investigation into a single affected service."""

    service: str
    role: str
    line_count: int = Field(..., description="Number of log lines mentioning this service")
    first_seen: str | None = None
    last_seen: str | None = None
    went_silent: bool = Field(False, description="True if service appeared early then stopped logging.")
    error_burst_rate: float = Field(0.0, description="ERROR/FATAL lines per minute for this service.")
    findings: List[str] = Field(default_factory=list, description="Plain-language observations.")
    suspected_role_in_cascade: str = Field(
        ..., description="primary | propagator | bystander | sink"
    )


class DeepTraceReport(BaseModel):
    """Output of Deep Trace mode — the emergency escalation.

    Surfaces what the surface-level analysis missed: hidden bugs,
    per-service deep probes, and (when Bedrock is live) an extended
    model pass focused on subtle defects.
    """

    triggered_reason: str = Field(..., description="Why Deep Trace was activated.")
    auto_triggered: bool = Field(..., description="True if the system escalated automatically.")
    extended_model_used: str = Field("", description="Model id used for the extended pass, or empty.")
    duration_ms: int = Field(0)
    hidden_signals: List[HiddenSignal] = Field(default_factory=list)
    service_probes: List[ServiceProbe] = Field(default_factory=list)
    expert_insights: List[str] = Field(
        default_factory=list,
        description="Subtle defects only an expert would catch — LLM expert pass output.",
    )
    revised_root_cause: str = Field(
        "",
        description="If the deep pass changed the root cause, this is the revised statement.",
    )
    revised_confidence: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Post-deep-trace confidence (often higher than the regular pass).",
    )


class ChatMessage(BaseModel):
    """A single turn in the follow-up chat attached to an analysis."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WhyStep(BaseModel):
    """One step in the 5 Whys postmortem ladder."""

    n: int = Field(..., ge=1, le=7, description="1-based depth in the why chain")
    question: str = Field(..., description="The 'why?' being asked at this depth.")
    answer: str = Field(..., description="The plain-language answer that produces the next why.")


class FiveWhys(BaseModel):
    """Classic SRE postmortem technique — recursive root-cause questioning."""

    steps: List[WhyStep] = Field(default_factory=list)
    final_root_cause: str = Field(
        ..., description="The deepest 'why' — the true systemic cause."
    )
    counter_factual: str = Field(
        default="",
        description="Optional: what would have prevented this incident entirely?",
    )


class ForensicReport(BaseModel):
    """Reverse-engineered view of the incident.

    Inspired by malware-forensic tools that trace an infection back to
    patient zero. We do the same for outages: find the first abnormal
    signal, reconstruct how it propagated, list every entity it touched,
    and hypothesize the trigger event that birthed it.
    """

    patient_zero: TimelineEvent = Field(
        ..., description="The first observable abnormal signal — origin of the cascade."
    )
    propagation_path: List[str] = Field(
        default_factory=list,
        description="Ordered service-to-service hops describing how the failure spread.",
    )
    blast_radius: List[BlastRadiusEntity] = Field(
        default_factory=list,
        description="Every entity the incident touched, classified by kind.",
    )
    trigger_hypothesis: str = Field(
        ..., description="Most-likely event that birthed patient zero (deploy / config change / traffic spike / dependency)."
    )
    trigger_confidence: float = Field(0.5, ge=0.0, le=1.0)
    minutes_to_detection: int | None = Field(
        default=None,
        description="Time between patient zero and the first user-visible symptom.",
    )


class FixRecommendation(BaseModel):
    title: str
    rationale: str
    action: str = Field(..., description="Concrete remediation step")
    snippet: Optional[str] = Field(
        default=None, description="Optional command, query, or code snippet"
    )
    priority: int = Field(1, ge=1, le=5, description="1 = highest priority")


class CodeFixSubStep(BaseModel):
    """One sub-agent in the code-fix pipeline."""

    name: str = Field(..., description="locate | diagnose | patch | verify")
    summary: str = Field(..., description="One-line description of what this sub-agent did")
    detail: str = Field(default="", description="Optional longer explanation or output")
    duration_ms: int = Field(default=0)


class CodeFix(BaseModel):
    """A code-aware fix proposal grounded in the user's actual repository.

    Generated by a small pipeline of sub-agents (locate, diagnose, patch,
    verify) that read the repo on disk, identify the buggy region, and
    produce a unified diff ready for ``git apply``.
    """

    repo_url: str = Field(..., description="The repo this fix was generated against")
    file_path: str = Field(..., description="Path relative to repo root of the buggy file")
    snippet: str = Field(
        ..., description="The current code in the buggy region (pre-patch)"
    )
    diff: str = Field(..., description="Unified diff that fixes the bug")
    rationale: str = Field(
        ..., description="Why this is the bug and how the patch fixes it"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="How confident the patch is correct"
    )
    verify_passed: bool = Field(
        default=False, description="True when post-patch lint / type-check was clean"
    )
    verify_output: str = Field(
        default="", description="Lint / type-check output (head of stderr if non-empty)"
    )
    candidate_files: List[str] = Field(
        default_factory=list,
        description="All files the locate sub-agent considered before settling on file_path",
    )
    sub_steps: List[CodeFixSubStep] = Field(
        default_factory=list,
        description="Trace of each sub-agent in the code-fix pipeline.",
    )
    duration_ms: int = Field(default=0, description="End-to-end pipeline duration")


class AgentStep(BaseModel):
    """One step in the agent's reasoning trail."""

    step: int = Field(..., description="1-based step index")
    kind: str = Field(..., description="'thought' | 'tool_call' | 'observation' | 'decision'")
    title: str = Field(..., description="Short label for the step")
    detail: str = Field(..., description="What the agent thought, did, or saw")
    tool: Optional[str] = Field(default=None, description="Tool name if kind=='tool_call'")
    output: Optional[Any] = Field(default=None, description="Tool output if kind=='observation'")


class AnalyzeRequest(BaseModel):
    """Input to the /analyze endpoint."""

    source: SourceKind = SourceKind.PASTE
    title: Optional[str] = Field(
        default=None, description="Optional human-friendly title for the incident"
    )
    logs: Optional[str] = Field(
        default=None,
        description="Raw log text (paste or upload). Required unless source is an integration.",
    )
    service_hint: Optional[str] = Field(
        default=None,
        description="Optional service name to focus the analysis (e.g. 'checkout-api')",
    )
    integration_query: Optional[str] = Field(
        default=None,
        description="Query string passed through to the chosen monitoring integration",
    )
    time_window_minutes: int = Field(
        default=30, ge=1, le=1440, description="Lookback window for integration pulls"
    )


class AnalyzeResponse(BaseModel):
    """Structured root-cause analysis returned to the client."""

    incident_id: str = Field(default_factory=lambda: f"INC-{uuid4().hex[:8].upper()}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    title: str
    summary: str = Field(..., description="One-paragraph executive summary")
    root_cause: str = Field(..., description="The most likely root cause, stated plainly")
    confidence: float = Field(..., ge=0.0, le=1.0, description="0-1 model confidence")
    severity: Severity
    severity_rationale: str
    affected_services: List[AffectedService] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    fixes: List[FixRecommendation] = Field(default_factory=list)
    evidence: List[str] = Field(
        default_factory=list,
        description="Quoted log lines or metric snippets supporting the analysis",
    )
    source: SourceKind = SourceKind.PASTE
    model: str = Field(..., description="Model id that generated the analysis, or 'demo'")
    duration_ms: int = Field(0, description="Server-side analysis time in milliseconds")
    agent_steps: List[AgentStep] = Field(
        default_factory=list,
        description="Trace of the agent's reasoning: thoughts, tool calls, observations, decision.",
    )
    forensic: ForensicReport | None = Field(
        default=None,
        description=(
            "Reverse-engineered view: patient zero, propagation path, blast radius, "
            "and trigger hypothesis. Populated when the agent could trace causality."
        ),
    )
    five_whys: FiveWhys | None = Field(
        default=None,
        description="Classic 5-Whys postmortem ladder with optional counter-factual.",
    )
    deep_trace: DeepTraceReport | None = Field(
        default=None,
        description=(
            "Deep Trace emergency-investigator output. Present only when the "
            "regular pass triggered escalation or the user manually invoked it."
        ),
    )
    should_escalate: bool = Field(
        default=False,
        description="True when the system recommends running Deep Trace on this analysis.",
    )
    escalation_reason: str = Field(
        default="",
        description="Human-readable explanation of why Deep Trace is recommended.",
    )
    # ── Lifecycle: status, rechecks, chat ──────────────────────────────
    status: str = Field(
        default="open",
        description="Lifecycle status: open | investigating | recovering | resolved",
    )
    resolved_at: datetime | None = Field(default=None)
    last_checked_at: datetime | None = Field(default=None)
    recheck_count: int = Field(default=0)
    resolution_summary: str = Field(
        default="",
        description="Short note explaining what changed when the incident was resolved.",
    )
    chat_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Follow-up Q&A between the user and the agent about this incident.",
    )
    code_fix: CodeFix | None = Field(
        default=None,
        description=(
            "Code-aware fix proposal: a unified diff against the user's repo "
            "produced by the locate/diagnose/patch/verify sub-agent pipeline. "
            "Populated only when the user opts in by supplying a repo URL."
        ),
    )


class IncidentSummary(BaseModel):
    """Compact record used for the dashboard history list."""

    incident_id: str
    title: str
    created_at: datetime
    severity: Severity
    root_cause: str
    affected_service_count: int


class IntegrationStatus(BaseModel):
    """Connection status for an external monitoring tool."""

    name: str
    connected: bool
    enabled: bool = Field(..., description="True when credentials are configured")
    detail: str = Field("", description="Human-readable status, error, or hint")
