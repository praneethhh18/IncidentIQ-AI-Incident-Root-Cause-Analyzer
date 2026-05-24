"""POST /api/v1/incidents/{id}/deep-trace — escalate an analysis.

The endpoint runs the Deep Trace pipeline against a previously-stored
analysis and attaches the result to it in the store. Returns the
updated analysis.

The body is optional; if absent we read the original logs from the
analysis's evidence. If logs aren't available, the request 400s.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import current_user, get_analysis_store, get_bedrock
from app.models import AnalyzeResponse
from app.services.bedrock import BedrockClient
from app.services.deep_trace import run_deep_trace, should_escalate
from app.services.identity import UserIdentity
from app.services.store import AnalysisStore

logger = logging.getLogger(__name__)
router = APIRouter()


class DeepTraceRequest(BaseModel):
    logs: Optional[str] = None  # If omitted we try to reconstruct from evidence
    reason: Optional[str] = None  # Override for the trigger reason


@router.post("/incidents/{incident_id}/deep-trace", response_model=AnalyzeResponse)
def deep_trace(
    incident_id: str,
    body: DeepTraceRequest = Body(default_factory=DeepTraceRequest),
    store: AnalysisStore = Depends(get_analysis_store),
    bedrock: BedrockClient = Depends(get_bedrock),
    user: Optional[UserIdentity] = Depends(current_user),
) -> AnalyzeResponse:
    owner_id = user.id if user else None
    analysis = store.get(incident_id, user_id=owner_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    logs = body.logs or "\n".join(analysis.evidence)
    if not logs.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "No logs available for deep trace. Supply them in the body as "
                "{'logs': '...'} or rerun analyze with logs preserved."
            ),
        )

    auto, auto_reason = should_escalate(analysis)
    triggered_reason = body.reason or (
        auto_reason
        if auto
        else "Manually invoked by the user to investigate deeper."
    )

    report = run_deep_trace(
        logs=logs,
        analysis=analysis,
        bedrock=bedrock,
        triggered_reason=triggered_reason,
        auto_triggered=auto,
    )

    # If the expert pass produced a revised root cause / confidence,
    # promote them onto the top-level analysis so the UI reflects the
    # corrected verdict.
    if report.revised_root_cause:
        analysis.root_cause = report.revised_root_cause
    if report.revised_confidence > 0:
        analysis.confidence = report.revised_confidence

    analysis.deep_trace = report
    store.save(analysis, user_id=owner_id)
    return analysis


@router.get("/incidents/{incident_id}/should-escalate")
def check_escalation(
    incident_id: str,
    store: AnalysisStore = Depends(get_analysis_store),
    user: Optional[UserIdentity] = Depends(current_user),
) -> dict:
    """UI helper — does this incident warrant a Deep Trace?"""
    analysis = store.get(incident_id, user_id=user.id if user else None)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    should, reason = should_escalate(analysis)
    return {"should_escalate": should, "reason": reason}
