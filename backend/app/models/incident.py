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
