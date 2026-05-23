"""POST /api/v1/webhook/{provider} — auto-ingest alerts from monitoring tools.

Accepts payloads from PagerDuty, Datadog, Opsgenie, or any generic JSON
shape with `title` + `message`/`logs`. Normalises the payload into a log
stream, runs the full agent analysis, persists the result, and (when
configured) posts a summary card back to Slack.

This is the "page fires → root cause in Slack before you open your
laptop" automation story.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from app.api.deps import get_analysis_store, get_analyzer
from app.core.config import get_settings
from app.models import AnalyzeRequest, SourceKind
from app.services.analyzer import Analyzer
from app.services.slack import SlackNotifier
from app.services.store import AnalysisStore
from app.services.webhook_ingest import normalize

logger = logging.getLogger(__name__)
router = APIRouter()

SUPPORTED_PROVIDERS = {"pagerduty", "datadog", "opsgenie", "generic"}


@router.post("/webhook/{provider}")
async def receive_webhook(
    provider: str = Path(..., description="pagerduty | datadog | opsgenie | generic"),
    payload: Dict[str, Any] = Body(...),
    analyzer: Analyzer = Depends(get_analyzer),
    store: AnalysisStore = Depends(get_analysis_store),
) -> Dict[str, Any]:
    provider = (provider or "generic").lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported provider '{provider}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            ),
        )

    title, logs = normalize(provider, payload)
    request = AnalyzeRequest(
        source=SourceKind.WEBHOOK,
        title=f"[{provider}] {title}",
        logs=logs,
    )

    try:
        analysis = await analyzer.analyze(request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Webhook analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    store.save(analysis)

    # Best-effort Slack post — never blocks success.
    slack = SlackNotifier(get_settings())
    slack_posted = False
    if slack.enabled:
        slack_posted = await slack.post_incident(analysis)

    return {
        "incident_id": analysis.incident_id,
        "severity": analysis.severity.value,
        "title": analysis.title,
        "root_cause": analysis.root_cause,
        "slack_posted": slack_posted,
        "dashboard_url": f"/incidents/{analysis.incident_id}",
    }
