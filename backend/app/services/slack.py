"""Slack notifier — posts a formatted incident summary to a webhook URL.

Used by the webhook auto-ingest path. The full message is formatted as
Slack Block Kit so it renders as a proper incident card in the channel.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from app.core.config import Settings
from app.models import AnalyzeResponse, Severity

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    Severity.P1: ":rotating_light:",
    Severity.P2: ":warning:",
    Severity.P3: ":information_source:",
}

SEVERITY_COLOR = {
    Severity.P1: "#DC2626",
    Severity.P2: "#F59E0B",
    Severity.P3: "#10B981",
}


class SlackNotifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.slack_enabled

    async def post_incident(self, analysis: AnalyzeResponse) -> bool:
        """Send an incident card to the configured Slack webhook.

        Returns True on success, False otherwise. Never raises — Slack is
        best-effort and must not break the analysis flow.
        """
        if not self.enabled:
            return False

        try:
            payload = self._build_payload(analysis)
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(
                    self._settings.slack_webhook_url or "", json=payload
                )
                if response.status_code >= 400:
                    logger.warning(
                        "Slack webhook returned %s: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return False
                return True
        except Exception:  # noqa: BLE001
            logger.exception("Slack post failed")
            return False

    def _build_payload(self, analysis: AnalyzeResponse) -> Dict[str, Any]:
        emoji = SEVERITY_EMOJI.get(analysis.severity, ":bell:")
        color = SEVERITY_COLOR.get(analysis.severity, "#6366F1")

        blocks: List[Dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {analysis.severity.value} · {analysis.title[:140]}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Incident*\n`{analysis.incident_id}`"},
                    {"type": "mrkdwn", "text": f"*Source*\n{analysis.source.value}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence*\n{int(analysis.confidence * 100)}%",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Affected*\n{len(analysis.affected_services)} services",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root cause*\n{analysis.root_cause}",
                },
            },
        ]

        if analysis.forensic:
            forensic = analysis.forensic
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Patient zero* `{forensic.patient_zero.timestamp.strftime('%H:%M:%S')}`\n"
                            f"{forensic.patient_zero.detail}\n\n"
                            f"*Propagation*: {' → '.join(forensic.propagation_path[:6])}\n"
                            f"*Trigger* ({int(forensic.trigger_confidence * 100)}%): "
                            f"{forensic.trigger_hypothesis[:240]}"
                        ),
                    },
                }
            )

        if analysis.fixes:
            top_fix = sorted(analysis.fixes, key=lambda f: f.priority)[0]
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Top fix* — {top_fix.title}\n_{top_fix.action}_",
                    },
                }
            )

        return {
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks,
                }
            ]
        }
