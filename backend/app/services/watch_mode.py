"""Watch mode: auto-create incidents from live Datadog telemetry.

Background asyncio task that polls Datadog every N seconds. When the
window's error count crosses a threshold AND the cluster of error lines
hasn't already produced an incident in the recent past, the watcher
calls the same Analyzer that the dashboard uses, persists the result to
the store, and the dashboard picks it up on next refresh.

Scope kept small on purpose:

  - single-tenant, in-process state (one watcher per backend)
  - no celery / no redis - just an asyncio Task
  - dedup by hash of the first N error tokens, with a short cooldown
    window so flapping doesn't spam the dashboard
  - cancellable + restartable from the API

Production would replace the in-process loop with a real queue worker
and a more sophisticated detection algorithm, but the contract stays
the same.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from app.core.config import Settings
from app.models import AnalyzeRequest, AnalyzeResponse, SourceKind
from app.services.analyzer import Analyzer
from app.services.store import AnalysisStore

logger = logging.getLogger(__name__)


# Defaults are tuned for a hackathon demo cadence. Production would
# pull these from a config table per-tenant.
DEFAULT_POLL_INTERVAL_S = 60
DEFAULT_WINDOW_MINUTES = 5
DEFAULT_ERROR_THRESHOLD = 3
DEDUP_COOLDOWN_S = 600

# Pattern noise we strip out before fingerprinting so two semantically
# identical errors with different timestamps / request IDs still dedup.
NOISE_RE = re.compile(
    r"\b("
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"  # ISO timestamps
    r"|[0-9a-f]{8,}"                                                          # hex ids / uuids
    r"|\b\d+ms\b"                                                             # latency
    r"|user=u_\w+"                                                            # user ids
    r")\b",
    re.IGNORECASE,
)


@dataclass
class WatchStatus:
    """Snapshot the UI polls to show 'watching for N minutes, M incidents'."""

    running: bool = False
    started_at: Optional[datetime] = None
    last_polled_at: Optional[datetime] = None
    last_poll_log_lines: int = 0
    last_poll_summary: str = ""
    incidents_created: int = 0
    last_incident_id: Optional[str] = None
    last_error: Optional[str] = None
    poll_interval_s: int = DEFAULT_POLL_INTERVAL_S
    window_minutes: int = DEFAULT_WINDOW_MINUTES
    error_threshold: int = DEFAULT_ERROR_THRESHOLD
    service_filter: Optional[str] = None
    # Most recent fingerprints we've already created incidents for.
    recent_fingerprints: dict[str, float] = field(default_factory=dict)


class WatchService:
    """Holds the watcher state and the asyncio task that drives it."""

    def __init__(
        self,
        settings: Settings,
        analyzer: Analyzer,
        store: AnalysisStore,
    ) -> None:
        self._settings = settings
        self._analyzer = analyzer
        self._store = store
        self._task: Optional[asyncio.Task] = None
        self._status = WatchStatus()

    # ── Public surface ────────────────────────────────────────────────

    @property
    def status(self) -> WatchStatus:
        return self._status

    def start(
        self,
        *,
        service_filter: Optional[str] = None,
        poll_interval_s: int = DEFAULT_POLL_INTERVAL_S,
        window_minutes: int = DEFAULT_WINDOW_MINUTES,
        error_threshold: int = DEFAULT_ERROR_THRESHOLD,
    ) -> WatchStatus:
        if self._task is not None and not self._task.done():
            logger.info("Watch mode already running; returning current status")
            return self._status

        self._status = WatchStatus(
            running=True,
            started_at=datetime.now(timezone.utc),
            poll_interval_s=poll_interval_s,
            window_minutes=window_minutes,
            error_threshold=error_threshold,
            service_filter=service_filter,
        )
        self._task = asyncio.create_task(self._run_loop(), name="watch-mode-loop")
        return self._status

    def stop(self) -> WatchStatus:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._status.running = False
        return self._status

    # ── Loop body ─────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        s = self._status
        logger.info(
            "Watch mode started: interval=%ss window=%sm threshold=%s service=%s",
            s.poll_interval_s, s.window_minutes, s.error_threshold, s.service_filter,
        )
        try:
            while True:
                await self._poll_once()
                await asyncio.sleep(s.poll_interval_s)
        except asyncio.CancelledError:
            logger.info("Watch mode loop cancelled")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Watch mode loop crashed")
            s.running = False
            s.last_error = str(exc)

    async def _poll_once(self) -> None:
        s = self._status
        s.last_polled_at = datetime.now(timezone.utc)

        # Build the query based on the user's service filter (if any).
        # Severity range matches what the dashboard's Auto mode uses, so
        # an operator who flips Watch on sees the same line count they'd
        # see clicking Analyze manually.
        severity_filter = (
            "status:(emergency OR critical OR alert OR error OR warn OR warning)"
        )
        query_terms = [severity_filter]
        if s.service_filter:
            query_terms.insert(0, f"service:{s.service_filter}")
        query = " ".join(query_terms)

        # Reuse the analyzer's resolver so integration credentials and
        # demo-fallback behaviour stay consistent with the manual path.
        request = AnalyzeRequest(
            source=SourceKind.DATADOG,
            integration_query=query,
            time_window_minutes=s.window_minutes,
            title=None,
        )

        try:
            logs = await self._analyzer._resolve_logs(request)  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            logger.warning("Watch poll: log fetch failed: %s", exc)
            s.last_error = f"log fetch failed: {exc}"
            s.last_poll_summary = "fetch failed"
            return

        s.last_error = None
        if not logs:
            s.last_poll_log_lines = 0
            s.last_poll_summary = "no logs in window"
            return

        s.last_poll_log_lines = logs.count("\n") + 1

        # Count error-level lines. Below threshold = no new incident.
        error_count = sum(
            1 for line in logs.splitlines()
            if re.search(r"\b(ERROR|FATAL)\b", line, re.IGNORECASE)
        )
        if error_count < s.error_threshold:
            s.last_poll_summary = f"{error_count} error line(s); under threshold"
            return

        # Dedup: if a fingerprint we already saw is back inside the
        # cooldown window, skip.
        fingerprint = _fingerprint_logs(logs)
        now = time.time()
        self._prune_old_fingerprints(now)
        if fingerprint in s.recent_fingerprints:
            s.last_poll_summary = (
                f"{error_count} error line(s); deduped against recent incident"
            )
            return

        # Create the incident.
        logger.info("Watch mode auto-creating incident (fp=%s)", fingerprint[:8])
        try:
            result: AnalyzeResponse = await self._analyzer.analyze(request)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Watch poll: analyze failed")
            s.last_error = f"analyze failed: {exc}"
            s.last_poll_summary = "analyze failed"
            return

        if not result.title or result.title.strip() == "":
            result.title = "[watch] Auto-detected incident"
        else:
            result.title = f"[watch] {result.title}"
        self._store.save(result)
        s.recent_fingerprints[fingerprint] = now
        s.incidents_created += 1
        s.last_incident_id = result.incident_id
        s.last_poll_summary = (
            f"Created {result.incident_id} from {error_count} error line(s)"
        )

    def _prune_old_fingerprints(self, now: float) -> None:
        cutoff = now - DEDUP_COOLDOWN_S
        for fp in [k for k, ts in self._status.recent_fingerprints.items() if ts < cutoff]:
            self._status.recent_fingerprints.pop(fp, None)


def _fingerprint_logs(logs: str) -> str:
    """Build a stable hash of the dominant error signature in a log window.

    Strips timestamps, hex ids, latency, and user ids so two waves of the
    same outage produce the same fingerprint. Uses the first five
    error-level lines because they characterise the pattern, not the
    long tail of duplicates underneath.
    """
    error_lines = []
    for line in logs.splitlines():
        if re.search(r"\b(ERROR|FATAL)\b", line, re.IGNORECASE):
            cleaned = NOISE_RE.sub("", line).strip()
            error_lines.append(cleaned)
            if len(error_lines) >= 5:
                break
    if not error_lines:
        return "no-error-lines"
    blob = "\n".join(error_lines)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


_service_singleton: Optional[WatchService] = None


def get_watch_service(
    settings: Settings, analyzer: Analyzer, store: AnalysisStore,
) -> WatchService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = WatchService(settings, analyzer, store)
    return _service_singleton
