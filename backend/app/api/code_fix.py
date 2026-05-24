"""POST /api/v1/incidents/{id}/code-fix - generate a code-aware patch.

Runs the locate/diagnose/patch/verify sub-agent pipeline against the
user-supplied repo URL and attaches the result to the incident.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import (
    current_user,
    get_analysis_store,
    get_bedrock,
    get_github_auth,
)
from app.models import AnalyzeResponse
from app.services.bedrock import BedrockClient, BedrockUnavailable
from app.services.code_fix import CodeFixError, generate_code_fix
from app.services.github_auth import GitHubAuthService
from app.services.identity import UserIdentity
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
    github: GitHubAuthService = Depends(get_github_auth),
    user: Optional[UserIdentity] = Depends(current_user),
) -> AnalyzeResponse:
    owner_id = user.id if user else None
    analysis = store.get(incident_id, user_id=owner_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    raw_repo_url = body.repo_url.strip()
    if not raw_repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")

    # If we have an active GitHub OAuth session, transparently inject
    # the token into the clone URL so private repos work without the
    # user pasting a PAT. Public-repo URLs are returned unchanged.
    clone_url = github.authenticated_clone_url(raw_repo_url)

    try:
        fix = generate_code_fix(analysis, clone_url, bedrock)
    except CodeFixError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BedrockUnavailable as exc:
        raise HTTPException(status_code=502, detail=f"Model call failed: {exc}") from exc

    # Never store the token-bearing URL on the incident - keep the
    # human-readable form.
    fix.repo_url = raw_repo_url
    analysis.code_fix = fix
    store.save(analysis, user_id=owner_id)
    return analysis
