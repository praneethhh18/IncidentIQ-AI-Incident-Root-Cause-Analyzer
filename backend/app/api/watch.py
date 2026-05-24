"""Watch mode endpoints.

POST /api/v1/watch/start   - begin polling Datadog for new incidents
POST /api/v1/watch/stop    - cancel the running poller
GET  /api/v1/watch/status  - 'watching for 12m, polled 8s ago, 2 auto-incidents'
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_analysis_store, get_analyzer
from app.core.config import get_settings
from app.services.analyzer import Analyzer
from app.services.store import AnalysisStore
from app.services.watch_mode import (
    DEFAULT_ERROR_THRESHOLD,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_WINDOW_MINUTES,
    WatchStatus,
    get_watch_service,
)

router = APIRouter()


class WatchStartRequest(BaseModel):
    service: Optional[str] = Field(
        default=None,
        description="Optional Datadog service name filter (e.g. 'fashion-aura-api').",
    )
    poll_interval_s: int = Field(default=DEFAULT_POLL_INTERVAL_S, ge=15, le=600)
    window_minutes: int = Field(default=DEFAULT_WINDOW_MINUTES, ge=1, le=60)
    error_threshold: int = Field(default=DEFAULT_ERROR_THRESHOLD, ge=1, le=100)


def _to_payload(status: WatchStatus) -> dict:
    return {
        "running": status.running,
        "started_at": status.started_at.isoformat() if status.started_at else None,
        "last_polled_at": status.last_polled_at.isoformat() if status.last_polled_at else None,
        "last_poll_log_lines": status.last_poll_log_lines,
        "last_poll_summary": status.last_poll_summary,
        "incidents_created": status.incidents_created,
        "last_incident_id": status.last_incident_id,
        "last_error": status.last_error,
        "poll_interval_s": status.poll_interval_s,
        "window_minutes": status.window_minutes,
        "error_threshold": status.error_threshold,
        "service_filter": status.service_filter,
    }


@router.post("/watch/start")
def watch_start(
    body: WatchStartRequest,
    analyzer: Analyzer = Depends(get_analyzer),
    store: AnalysisStore = Depends(get_analysis_store),
) -> dict:
    service = get_watch_service(get_settings(), analyzer, store)
    status = service.start(
        service_filter=body.service,
        poll_interval_s=body.poll_interval_s,
        window_minutes=body.window_minutes,
        error_threshold=body.error_threshold,
    )
    return _to_payload(status)


@router.post("/watch/stop")
def watch_stop(
    analyzer: Analyzer = Depends(get_analyzer),
    store: AnalysisStore = Depends(get_analysis_store),
) -> dict:
    service = get_watch_service(get_settings(), analyzer, store)
    return _to_payload(service.stop())


@router.get("/watch/status")
def watch_status(
    analyzer: Analyzer = Depends(get_analyzer),
    store: AnalysisStore = Depends(get_analysis_store),
) -> dict:
    service = get_watch_service(get_settings(), analyzer, store)
    return _to_payload(service.status)
