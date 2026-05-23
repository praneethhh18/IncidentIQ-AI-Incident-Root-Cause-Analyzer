"""Normalise inbound alert webhooks into log payloads the analyzer can ingest.

Each supported provider has its own quirky JSON shape. We extract the
fields that look log-like (title, message, custom_details, log_url) and
flatten them into a synthetic log payload. The downstream analyzer then
treats it like any other paste.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Tuple


def normalize(provider: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    """Return (incident_title, synthetic_log_payload) for the given provider."""
    provider = (provider or "generic").lower()
    if provider == "pagerduty":
        return _pagerduty(payload)
    if provider == "datadog":
        return _datadog_alert(payload)
    if provider == "opsgenie":
        return _opsgenie(payload)
    return _generic(payload)


def _pagerduty(payload: Dict[str, Any]) -> Tuple[str, str]:
    event = payload.get("event") or payload
    incident = event.get("data", event)

    title = incident.get("title") or incident.get("description") or "PagerDuty incident"
    summary = incident.get("summary") or incident.get("description") or ""
    service = (incident.get("service") or {}).get("summary", "")
    severity = (incident.get("priority") or {}).get("summary", incident.get("urgency", ""))
    custom_details = incident.get("custom_details") or {}

    lines = [
        f"# Source: PagerDuty incident {incident.get('id', '')}",
        f"# Title: {title}",
        f"# Service: {service}",
        f"# Severity: {severity}",
        f"# Summary: {summary}",
    ]
    for key, value in custom_details.items():
        lines.append(f"{_iso_now()} ALERT {service or '?'} {key}={_short(value)}")

    if not custom_details:
        lines.append(f"{_iso_now()} ALERT {service or '?'} {summary}")

    return title, "\n".join(lines)


def _datadog_alert(payload: Dict[str, Any]) -> Tuple[str, str]:
    title = payload.get("title") or payload.get("alert_title") or "Datadog alert"
    message = payload.get("text") or payload.get("body") or payload.get("message") or ""
    aggregation_key = payload.get("aggregation_key", "")
    alert_type = payload.get("alert_type") or payload.get("event_type", "alert")
    tags = payload.get("tags") or []

    lines = [
        f"# Source: Datadog {alert_type} {aggregation_key}",
        f"# Title: {title}",
        f"# Tags: {', '.join(tags) if isinstance(tags, list) else tags}",
    ]
    # Datadog message bodies often contain multi-line markdown — preserve them.
    for line in str(message).splitlines():
        if line.strip():
            lines.append(f"{_iso_now()} ALERT datadog {line.strip()}")

    return title, "\n".join(lines)


def _opsgenie(payload: Dict[str, Any]) -> Tuple[str, str]:
    alert = payload.get("alert") or payload
    title = alert.get("message") or alert.get("alias") or "Opsgenie alert"
    description = alert.get("description") or ""
    priority = alert.get("priority", "")
    tags = alert.get("tags", [])

    lines = [
        f"# Source: Opsgenie alert {alert.get('alertId', '')}",
        f"# Title: {title}",
        f"# Priority: {priority}",
        f"# Tags: {', '.join(tags) if isinstance(tags, list) else tags}",
        f"{_iso_now()} ALERT opsgenie {description}",
    ]
    return title, "\n".join(lines)


def _generic(payload: Dict[str, Any]) -> Tuple[str, str]:
    """Fallback: accept any shape with a `title` and `logs` or `message`."""
    title = (
        payload.get("title")
        or payload.get("summary")
        or payload.get("name")
        or "External alert"
    )
    # Prefer pre-formatted logs when supplied.
    if isinstance(payload.get("logs"), str) and payload["logs"].strip():
        return title, payload["logs"]
    message = (
        payload.get("message")
        or payload.get("description")
        or payload.get("body")
        or ""
    )
    return title, f"# Source: generic webhook\n# Title: {title}\n{_iso_now()} ALERT external {message}"


def _short(value: Any, limit: int = 200) -> str:
    text = str(value).replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
