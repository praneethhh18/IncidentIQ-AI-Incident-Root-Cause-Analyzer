"""New Relic NRQL integration.

Uses the GraphQL NerdGraph API to run an NRQL query against the user's
account. Returns formatted log lines for the analyser. Falls back to a
seeded stream when credentials are absent or the call fails.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import Settings
from app.models import IntegrationStatus, SourceKind
from app.services.demo_data import MEMORY_LEAK_LOGS
from app.services.integrations.base import MonitoringIntegration

logger = logging.getLogger(__name__)

NERDGRAPH_URL = "https://api.newrelic.com/graphql"


class NewRelicIntegration(MonitoringIntegration):
    source = SourceKind.NEWRELIC
    display_name = "New Relic"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return self._settings.newrelic_enabled

    def _resolve(self, overrides: Optional["object"] = None) -> tuple[Optional[str], Optional[str]]:
        if overrides is not None:
            return (
                getattr(overrides, "user_key", None),
                getattr(overrides, "account_id", None),
            )
        return self._settings.new_relic_user_key, self._settings.new_relic_account_id

    async def fetch_logs(
        self,
        *,
        query: Optional[str],
        window_minutes: int,
        overrides: Optional["object"] = None,
    ) -> str:
        user_key, account_id = self._resolve(overrides)
        if not (user_key and account_id):
            logger.info("New Relic not configured — returning seeded log stream")
            return f"# [demo] New Relic NRQL stream — query={query or 'default'} window={window_minutes}m\n{MEMORY_LEAK_LOGS}"

        nrql = query or (
            "SELECT timestamp, level, service, message FROM Log "
            f"WHERE level IN ('error', 'warn', 'fatal') "
            f"SINCE {window_minutes} minutes ago LIMIT 200"
        )
        graphql = """
        query($accountId: Int!, $nrql: Nrql!) {
          actor {
            account(id: $accountId) {
              nrql(query: $nrql) {
                results
              }
            }
          }
        }
        """
        variables = {
            "accountId": int(account_id or 0),
            "nrql": nrql,
        }
        headers = {
            "API-Key": user_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    NERDGRAPH_URL,
                    json={"query": graphql, "variables": variables},
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("New Relic fetch failed, using seeded stream: %s", exc)
            return f"# [fallback] New Relic API error: {exc}\n{MEMORY_LEAK_LOGS}"

        try:
            rows = data["data"]["actor"]["account"]["nrql"]["results"] or []
        except (KeyError, TypeError):
            return "# New Relic returned no results."

        if not rows:
            return "# No matching New Relic log events in the requested window."

        lines = []
        for row in rows:
            ts = row.get("timestamp", "")
            level = (row.get("level") or "?").upper()
            service = row.get("service", "?")
            message = (row.get("message") or "").replace("\n", " ").strip()
            lines.append(f"{ts} {level:<5} {service:<20} {message}")
        return "\n".join(lines)

    async def status(self) -> IntegrationStatus:
        if not self.is_configured():
            return IntegrationStatus(
                name=self.display_name,
                connected=False,
                enabled=False,
                detail="Add NEW_RELIC_USER_KEY and NEW_RELIC_ACCOUNT_ID to enable.",
            )

        headers = {
            "API-Key": self._settings.new_relic_user_key or "",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(
                    NERDGRAPH_URL,
                    json={"query": "{ actor { user { email } } }"},
                    headers=headers,
                )
                if response.status_code == 200 and "errors" not in response.json():
                    return IntegrationStatus(
                        name=self.display_name,
                        connected=True,
                        enabled=True,
                        detail=f"Connected to account {self._settings.new_relic_account_id}",
                    )
                return IntegrationStatus(
                    name=self.display_name,
                    connected=False,
                    enabled=True,
                    detail=f"NerdGraph returned {response.status_code}",
                )
        except Exception as exc:  # noqa: BLE001
            return IntegrationStatus(
                name=self.display_name,
                connected=False,
                enabled=True,
                detail=f"Network error: {exc}",
            )
