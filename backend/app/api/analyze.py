"""POST /api/v1/analyze — run a root-cause analysis."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sse_starlette.sse import EventSourceResponse
from typing import Optional

from app.api.deps import get_analyzer, get_analysis_store
from app.models import AnalyzeRequest, AnalyzeResponse, SourceKind
from app.services.analyzer import Analyzer
from app.services.store import AnalysisStore

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    analyzer: Analyzer = Depends(get_analyzer),
    store: AnalysisStore = Depends(get_analysis_store),
) -> AnalyzeResponse:
    """Run a root-cause analysis on the supplied logs or integration query."""
    try:
        result = await analyzer.analyze(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Analyzer failed")
        raise HTTPException(status_code=500, detail="Internal analyzer error") from exc

    store.save(result)
    return result


@router.post("/analyze/stream")
async def analyze_stream(
    request: AnalyzeRequest,
    analyzer: Analyzer = Depends(get_analyzer),
    store: AnalysisStore = Depends(get_analysis_store),
) -> EventSourceResponse:
    """SSE variant of ``/analyze`` that streams the agent's reasoning live.

    The client opens an EventSource on this endpoint and receives a
    sequence of small JSON payloads:

    * ``phase``      — pipeline phase changed (perceive / agent / synthesize / audit)
    * ``agent_step`` — one entry in the agent's reasoning trail
    * ``complete``   — final ``AnalyzeResponse`` payload
    * ``error``      — fatal stream error
    """

    async def event_publisher():
        final_payload = None
        try:
            async for event in analyzer.analyze_stream(request):
                if event["event"] == "complete":
                    final_payload = event["analysis"]
                yield {
                    "event": event["event"],
                    "data": json.dumps(event, default=str),
                }
        except Exception as exc:  # noqa: BLE001
            logger.exception("Stream analyzer failed")
            yield {
                "event": "error",
                "data": json.dumps({"event": "error", "message": str(exc)}),
            }
            return

        # Persist outside the stream so the history endpoint sees it.
        if final_payload is not None:
            try:
                store.save(AnalyzeResponse.model_validate(final_payload))
            except Exception:  # noqa: BLE001
                logger.exception("Failed to persist streamed analysis")

    return EventSourceResponse(event_publisher())


@router.post("/analyze/upload", response_model=AnalyzeResponse)
async def analyze_upload(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    service_hint: Optional[str] = Form(default=None),
    analyzer: Analyzer = Depends(get_analyzer),
    store: AnalysisStore = Depends(get_analysis_store),
) -> AnalyzeResponse:
    """Run analysis on the contents of an uploaded log file."""
    raw = await file.read()
    try:
        logs = raw.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Cannot decode file: {exc}") from exc

    request = AnalyzeRequest(
        source=SourceKind.UPLOAD,
        title=title or file.filename,
        service_hint=service_hint,
        logs=logs,
    )
    result = await analyzer.analyze(request)
    store.save(result)
    return result
