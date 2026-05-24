"""GET /api/v1/incidents — recent analysis history.
POST /api/v1/incidents/{id}/recheck — re-pull fresh telemetry, update status."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import (
    current_user,
    get_analysis_store,
    get_integrations,
)
from app.core.config import get_settings
from app.models import AnalyzeResponse, IncidentSummary
from app.services.email import EmailNotifier
from app.services.identity import UserIdentity
from app.services.integrations import IntegrationRegistry
from app.services.recheck import recheck_incident
from app.services.store import AnalysisStore

logger = logging.getLogger(__name__)
router = APIRouter()


class RecheckRequest(BaseModel):
    logs: Optional[str] = None
    dashboard_base_url: Optional[str] = None


class RecheckResponse(BaseModel):
    incident: AnalyzeResponse
    outcome_status: str
    outcome_summary: str
    matched_signals: List[str]
    email_sent: bool


@router.get("/incidents", response_model=List[IncidentSummary])
def list_incidents(
    limit: int = Query(default=25, ge=1, le=100),
    store: AnalysisStore = Depends(get_analysis_store),
    user: Optional[UserIdentity] = Depends(current_user),
) -> List[IncidentSummary]:
    return store.list_recent(limit=limit, user_id=user.id if user else None)


@router.get("/incidents/{incident_id}", response_model=AnalyzeResponse)
def get_incident(
    incident_id: str,
    store: AnalysisStore = Depends(get_analysis_store),
    user: Optional[UserIdentity] = Depends(current_user),
) -> AnalyzeResponse:
    analysis = store.get(incident_id, user_id=user.id if user else None)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return analysis


@router.post("/incidents/{incident_id}/recheck", response_model=RecheckResponse)
async def recheck(
    incident_id: str,
    body: RecheckRequest = Body(default_factory=RecheckRequest),
    store: AnalysisStore = Depends(get_analysis_store),
    integrations: IntegrationRegistry = Depends(get_integrations),
    user: Optional[UserIdentity] = Depends(current_user),
) -> RecheckResponse:
    """Re-evaluate an incident against fresh telemetry.

    Accepts either pasted fresh logs in the body, or pulls a fresh
    window from the same integration the original incident came from.
    Updates the incident's lifecycle status. Fires a resolution email
    when the incident transitions to resolved for the first time.
    """
    owner_id = user.id if user else None
    analysis = store.get(incident_id, user_id=owner_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    previous_status = analysis.status

    try:
        outcome = await recheck_incident(
            analysis=analysis,
            fresh_logs=body.logs,
            integrations=integrations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recheck failed")
        raise HTTPException(status_code=500, detail="Recheck failed") from exc

    store.save(analysis, user_id=owner_id)

    # Fire resolution email exactly once: only when this recheck flipped
    # the status into 'resolved'.
    email_sent = False
    if outcome.status == "resolved" and previous_status != "resolved":
        notifier = EmailNotifier(get_settings())
        if notifier.enabled:
            email_sent = await notifier.send_resolution(
                analysis=analysis,
                dashboard_base_url=body.dashboard_base_url or "",
            )

    return RecheckResponse(
        incident=analysis,
        outcome_status=outcome.status,
        outcome_summary=outcome.summary,
        matched_signals=outcome.matched_signals,
        email_sent=email_sent,
    )
