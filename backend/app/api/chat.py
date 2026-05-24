"""Chat follow-up endpoints for incidents."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from typing import Optional

from app.api.deps import current_user, get_analysis_store, get_bedrock
from app.models import ChatMessage
from app.services.bedrock import BedrockClient
from app.services.chat import run_chat_turn
from app.services.identity import UserIdentity
from app.services.store import AnalysisStore

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: ChatMessage
    history: List[ChatMessage]


@router.post("/incidents/{incident_id}/chat", response_model=ChatResponse)
def chat(
    incident_id: str,
    body: ChatRequest = Body(...),
    store: AnalysisStore = Depends(get_analysis_store),
    bedrock: BedrockClient = Depends(get_bedrock),
    user: Optional[UserIdentity] = Depends(current_user),
) -> ChatResponse:
    owner_id = user.id if user else None
    analysis = store.get(incident_id, user_id=owner_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        reply = run_chat_turn(
            analysis=analysis,
            user_message=body.message,
            bedrock=bedrock,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat turn failed")
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc

    store.save(analysis, user_id=owner_id)
    return ChatResponse(reply=reply, history=analysis.chat_history)


@router.get("/incidents/{incident_id}/chat", response_model=List[ChatMessage])
def get_chat_history(
    incident_id: str,
    store: AnalysisStore = Depends(get_analysis_store),
    user: Optional[UserIdentity] = Depends(current_user),
) -> List[ChatMessage]:
    analysis = store.get(incident_id, user_id=user.id if user else None)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return analysis.chat_history
