"""POST /api/v1/incidents/{id}/code-fix - generate a code-aware patch.

Runs the locate/diagnose/patch/verify sub-agent pipeline against the
user-supplied repo URL and attaches the result to the incident.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_analysis_store, get_bedrock
from app.models import AnalyzeResponse
from app.services.bedrock import BedrockClient, BedrockUnavailable
from app.services.code_fix import CodeFixError, generate_code_fix
from app.services.store import AnalysisStore

logger = logging.getLogger(__name__)
router = APIRouter()


class CodeFixRequest(BaseModel):
    repo_url: str = Field(
        ...,
        description="HTTPS git URL of the repo to patch (public or PAT-embedded).",
    )


@router.post("/incidents/{incident_id}/code-fix", response_model=AnalyzeResponse)
def code_fix(
    incident_id: str,
    body: CodeFixRequest,
    store: AnalysisStore = Depends(get_analysis_store),
    bedrock: BedrockClient = Depends(get_bedrock),
) -> AnalyzeResponse:
    analysis = store.get(incident_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    if not body.repo_url.strip():
        raise HTTPException(status_code=400, detail="repo_url is required")

    try:
        fix = generate_code_fix(analysis, body.repo_url.strip(), bedrock)
    except CodeFixError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BedrockUnavailable as exc:
        raise HTTPException(status_code=502, detail=f"Model call failed: {exc}") from exc

    analysis.code_fix = fix
    store.save(analysis)
    return analysis
