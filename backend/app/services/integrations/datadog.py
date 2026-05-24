"""Datadog Logs integration.

Uses the public Logs Search API (v2) for on-demand pulls. When credentials
are absent or the API is unreachable, the integration falls back to a
seeded log stream so the analyser can still run end-to-end.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import Settings
from app.models import IntegrationStatus, SourceKind
from app.services.demo_data import CASCADING_FAILURE_LOGS
from app.services.integrations.base import MonitoringIntegration

logger = logging.getLogger(__name__)


class DatadogIntegration(MonitoringIntegration):
    source = SourceKind.DATADOG
    display_name = "Datadog"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        site = settings.datadog_site or "datadoghq.com"
        self._base_url = f"https://api.{site}"

    def is_configured(self) -> bool:
        return self._settings.datadog_enabled

    def _resolve_credentials(
        self,
        overrides: Optional["object"] = None,
    ) -> tuple[Optional[str], Optional[str], str, str]:
        """Pick credentials for this call.

        Overrides come from the per-session credential store (the user
        pasted their own keys in the Settings page). When no overrides
        are supplied we fall back to .env values from settings. Returns
        ``(api_key, app_key, site, base_url)``.
        """
        if overrides is not None:
            api_key = getattr(overrides, "api_key", None)
            app_key = getattr(overrides, "app_key", None)
            site = getattr(overrides, "site", None) or "datadoghq.com"
            base_url = f"https://api.{site}"
            return api_key, app_key, site, base_url
        return (
            self._settings.datadog_api_key,
            self._settings.datadog_app_key,
            self._settings.datadog_site or "datadoghq.com",
            self._base_url,
        )

    def is_configured_for(self, overrides: Optional["object"] = None) -> bool:
        """True if EITHER the per-session overrides or .env have valid creds."""
        if overrides is not None:
            return bool(
                getattr(overrides, "api_key", None)
                and getattr(overrides, "app_key", None)
            )
        return self._settings.datadog_enabled

    async def fetch_logs(
        self,
        *,
        query: Optional[str],
        window_minutes: int,
        overrides: Optional["object"] = None,
    ) -> str:
        api_key, app_key, site, base_url = self._resolve_credentials(overrides)
        if not (api_key and app_key):
            logger.info("Datadog not configured — returning seeded log stream")
            return f"# [demo] Datadog stream — query={query or '*'} window={window_minutes}m\n{CASCADING_FAILURE_LOGS}"

        url = f"{base_url}/api/v2/logs/events/search"
        now = datetime.now(timezone.utc)
        body = {
            "filter": {
                "query": query or "status:error OR status:warn",
                "from": (now - timedelta(minutes=window_minutes)).isoformat(),
                "to": now.isoformat(),
            },
            "page": {"limit": 200},
            "sort": "-timestamp",
        }
        headers = {
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Datadog fetch failed, using seeded stream: %s", exc)
            return f"# [fallback] Datadog API error: {exc}\n{CASCADING_FAILURE_LOGS}"

        events = payload.get("data", [])
        if not events:
            return "# No matching Datadog log events in the requested window."

        lines = []
        for event in events:
            attrs = event.get("attributes", {})
            ts = attrs.get("timestamp", "")
            service = attrs.get("service", "?")
            status = attrs.get("status", "?")
            message = (attrs.get("message") or "").replace("\n", " ").strip()
            lines.append(f"{ts} {status.upper():<5} {service:<20} {message}")
        return "\n".join(lines)

    async def list_recent_services(
        self,
        window_minutes: int = 60,
        overrides: Optional["object"] = None,
    ) -> list[str]:
        """Return distinct service names that emitted error/warn logs recently.

        Tries the Logs Analytics Aggregate endpoint first (gives us
        deduped service names quickly). If that 400s for any reason -
        Datadog is picky about timestamps and tenant variants - we fall
        back to a small Search API call and bucket services client-side.
        Returns an empty list only when both fail or no creds.
        """
        api_key, app_key, site, base_url = self._resolve_credentials(overrides)
        if not (api_key and app_key):
            return []

        services = await self._list_services_via_aggregate(
            window_minutes, api_key, app_key, base_url,
        )
        if services:
            return services
        return await self._list_services_via_search(
            window_minutes, api_key, app_key, base_url,
        )

    async def _list_services_via_aggregate(
        self,
        window_minutes: int,
        api_key: str,
        app_key: str,
        base_url: str,
    ) -> list[str]:
        url = f"{base_url}/api/v2/logs/analytics/aggregate"
        # Use Datadog's relative-time strings instead of ISO timestamps.
        # The aggregate endpoint is fussy about timezone formatting and
        # 'now-Xm' is the form their docs and console use.
        body = {
            "compute": [{"aggregation": "count", "type": "total"}],
            "filter": {
                "from": f"now-{int(window_minutes)}m",
                "to": "now",
                "query": "status:error OR status:warn",
            },
            "group_by": [
                {
                    "facet": "service",
                    "limit": 25,
                    "sort": {"aggregation": "count", "order": "desc"},
                }
            ],
        }
        headers = {
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code >= 400:
                    logger.warning(
                        "Datadog aggregate %s: %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    return []
                payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Datadog aggregate call failed: %s", exc)
            return []

        buckets = (payload.get("data") or {}).get("buckets") or []
        names: list[str] = []
        for bucket in buckets:
            svc = (bucket.get("by") or {}).get("service")
            if svc and svc not in names:
                names.append(svc)
        return names

    async def _list_services_via_search(
        self,
        window_minutes: int,
        api_key: str,
        app_key: str,
        base_url: str,
    ) -> list[str]:
        """Fallback: pull recent events and bucket by `service` ourselves."""
        url = f"{base_url}/api/v2/logs/events/search"
        now = datetime.now(timezone.utc)
        body = {
            "filter": {
                "query": "status:error OR status:warn",
                "from": (now - timedelta(minutes=window_minutes)).isoformat(),
                "to": now.isoformat(),
            },
            "page": {"limit": 200},
            "sort": "-timestamp",
        }
        headers = {
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code >= 400:
                    logger.warning(
                        "Datadog search %s: %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    return []
                payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Datadog search fallback failed: %s", exc)
            return []

        seen: list[str] = []
        for event in payload.get("data", []):
            svc = (event.get("attributes") or {}).get("service")
            if svc and svc not in seen:
                seen.append(svc)
                if len(seen) >= 25:
                    break
        return seen

    async def status(self) -> IntegrationStatus:
        if not self.is_configured():
            return IntegrationStatus(
                name=self.display_name,
                connected=False,
                enabled=False,
                detail="Add DATADOG_API_KEY and DATADOG_APP_KEY to enable.",
            )

        url = f"{self._base_url}/api/v1/validate"
        headers = {
            "DD-API-KEY": self._settings.datadog_api_key or "",
            "DD-APPLICATION-KEY": self._settings.datadog_app_key or "",
        }
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return IntegrationStatus(
                        name=self.display_name,
                        connected=True,
                        enabled=True,
                        detail=f"Connected to {self._settings.datadog_site}",
                    )
                return IntegrationStatus(
                    name=self.display_name,
                    connected=False,
                    enabled=True,
                    detail=f"Validation failed ({response.status_code})",
                )
        except Exception as exc:  # noqa: BLE001
            return IntegrationStatus(
                name=self.display_name,
                connected=False,
                enabled=True,
                detail=f"Network error: {exc}",
            )
