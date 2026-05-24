"""Grafana / Loki integration.

Uses the Loki query_range API (exposed by Grafana when Loki is added as a
data source). When credentials are absent, falls back to a seeded stream.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.core.config import Settings
from app.models import IntegrationStatus, SourceKind
from app.services.demo_data import DB_OUTAGE_LOGS
from app.services.integrations.base import MonitoringIntegration

logger = logging.getLogger(__name__)


class GrafanaIntegration(MonitoringIntegration):
    source = SourceKind.GRAFANA
    display_name = "Grafana / Loki"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return self._settings.grafana_enabled

    def _resolve(self, overrides: Optional["object"] = None) -> tuple[Optional[str], Optional[str]]:
        if overrides is not None:
            return (
                getattr(overrides, "url", None),
                getattr(overrides, "api_key", None),
            )
        return self._settings.grafana_url, self._settings.grafana_api_key

    def _headers_for(self, api_key: Optional[str]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key or ''}",
            "Accept": "application/json",
        }

    async def fetch_logs(
        self,
        *,
        query: Optional[str],
        window_minutes: int,
        overrides: Optional["object"] = None,
    ) -> str:
        url_cfg, api_key = self._resolve(overrides)
        if not (url_cfg and api_key):
            logger.info("Grafana not configured — returning seeded log stream")
            default_query = '{job=~".+"}'
            display_query = query or default_query
            return (
                f"# [demo] Grafana/Loki stream — query={display_query} "
                f"window={window_minutes}m\n{DB_OUTAGE_LOGS}"
            )

        base = url_cfg.rstrip("/")
        headers = self._headers_for(api_key)
        end_ns = int(time.time() * 1e9)
        start_ns = end_ns - int(window_minutes * 60 * 1e9)
        params = {
            "query": query or '{job=~".+"} |~ "(?i)(error|warn|fail|exception)"',
            "start": str(start_ns),
            "end": str(end_ns),
            "limit": "200",
            "direction": "BACKWARD",
        }
        url = f"{base}/loki/api/v1/query_range"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Grafana/Loki fetch failed, using seeded stream: %s", exc)
            return f"# [fallback] Grafana/Loki API error: {exc}\n{DB_OUTAGE_LOGS}"

        streams = payload.get("data", {}).get("result", [])
        if not streams:
            return "# No matching Loki log lines in the requested window."

        lines = []
        for stream in streams:
            labels = stream.get("stream", {})
            service = labels.get("service") or labels.get("app") or labels.get("job", "?")
            for ts, line in stream.get("values", []):
                lines.append(f"{ts} {service:<20} {line.strip()}")
        return "\n".join(lines)

    async def status(self) -> IntegrationStatus:
        if not self.is_configured():
            return IntegrationStatus(
                name=self.display_name,
                connected=False,
                enabled=False,
                detail="Add GRAFANA_URL and GRAFANA_API_KEY to enable.",
            )

        base = (self._settings.grafana_url or "").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    f"{base}/loki/api/v1/labels",
                    headers=self._headers_for(self._settings.grafana_api_key),
                )
                if response.status_code == 200:
                    return IntegrationStatus(
                        name=self.display_name,
                        connected=True,
                        enabled=True,
                        detail=f"Connected to {base}",
                    )
                return IntegrationStatus(
                    name=self.display_name,
                    connected=False,
                    enabled=True,
                    detail=f"Labels endpoint returned {response.status_code}",
                )
        except Exception as exc:  # noqa: BLE001
            return IntegrationStatus(
                name=self.display_name,
                connected=False,
                enabled=True,
                detail=f"Network error: {exc}",
            )
