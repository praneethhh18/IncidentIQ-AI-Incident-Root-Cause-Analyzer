"""Incident store backed by SQLite, scoped by user identity.

Every row carries a ``user_id`` (gh:/fb:/guest: prefixed). Reads filter
by user_id so two judges on different devices never see each other's
incidents. Webhook-ingested incidents land in the shared pool with
``user_id = NULL`` so external alerts (PagerDuty, Datadog monitors)
remain visible regardless of who's signed in.

Schema migration: an older deployment may have an ``incidents`` table
without ``user_id``. The migration adds the column non-destructively
(NULL default) so existing rows become "shared pool" without losing
history.

Default path: ``store_db_path`` from settings - production EC2 resolves
to ``/var/lib/incidentiq/store.db`` via systemd StateDirectory.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

from app.core.config import get_settings
from app.models import AnalyzeResponse, IncidentSummary

logger = logging.getLogger(__name__)


# Table + non-user-related indexes only - the user_id index has to wait
# until AFTER the ALTER TABLE migration runs, because on databases that
# pre-date the per-user work the column doesn't exist yet and
# `CREATE INDEX ... ON incidents(user_id, ...)` would crash with
# "no such column: user_id".
_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    payload     TEXT NOT NULL,
    user_id     TEXT
);
CREATE INDEX IF NOT EXISTS incidents_created_at_idx
    ON incidents(created_at DESC);
"""

# Index that requires user_id - created separately, after the ALTER
# migration guarantees the column exists.
_USER_INDEX = """
CREATE INDEX IF NOT EXISTS incidents_user_idx
    ON incidents(user_id, created_at DESC);
"""


# Sentinel for the shared / public bucket: webhook ingests, demo
# fallbacks, etc. Visible to every signed-in user *and* anonymous
# callers, so external alert sources don't have to know about identity.
SHARED_USER_ID: Optional[str] = None


class AnalysisStore:
    """SQLite-backed analysis store, with per-user scoping."""

    def __init__(self, db_path: Optional[str] = None, capacity: int = 2000) -> None:
        self._capacity = capacity
        self._lock = threading.Lock()
        self._db_path = db_path or get_settings().store_db_path

        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        # Non-destructive migration: pre-user_id databases need the
        # column added before the user_id index can be created. SQLite
        # raises 'duplicate column' if the column already exists, which
        # we swallow because that's the expected steady state.
        try:
            self._conn.execute("ALTER TABLE incidents ADD COLUMN user_id TEXT")
            logger.info("Migrated incidents table: added user_id column")
        except sqlite3.OperationalError:
            pass  # column already there
        # Index that depends on user_id - safe to create now that the
        # column is guaranteed to exist on both fresh DBs (added by
        # _SCHEMA's CREATE TABLE) and migrated DBs (added by the ALTER).
        self._conn.executescript(_USER_INDEX)

        logger.info("AnalysisStore using SQLite at %s", self._db_path)

    # ── Mutation ─────────────────────────────────────────────────────

    def save(
        self, analysis: AnalyzeResponse, *, user_id: Optional[str] = None,
    ) -> None:
        """Persist an analysis under the given user_id.

        ``user_id=None`` means the shared/public bucket - used by the
        webhook ingest path so PagerDuty/Datadog monitors don't need
        to know about IncidentIQ's identity scheme.
        """
        payload = analysis.model_dump_json()
        created_at_iso = analysis.created_at.isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO incidents "
                "(incident_id, created_at, payload, user_id) "
                "VALUES (?, ?, ?, ?)",
                (analysis.incident_id, created_at_iso, payload, user_id),
            )
            # LRU-style cap so the table doesn't grow unbounded over time.
            self._conn.execute(
                "DELETE FROM incidents WHERE incident_id IN ("
                "SELECT incident_id FROM incidents "
                "ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
                (self._capacity,),
            )

    def clear(self, *, user_id: Optional[str] = None) -> None:
        """Clear incidents. With user_id, scoped to that user; without,
        clears the entire store (admin use only - not exposed via API)."""
        with self._lock:
            if user_id is None:
                self._conn.execute("DELETE FROM incidents")
            else:
                self._conn.execute(
                    "DELETE FROM incidents WHERE user_id = ?", (user_id,),
                )

    # ── Reads ────────────────────────────────────────────────────────

    def get(
        self, incident_id: str, *, user_id: Optional[str] = None,
    ) -> Optional[AnalyzeResponse]:
        """Fetch a single incident.

        If ``user_id`` is supplied, only returns the row when it belongs
        to that user OR to the shared pool (user_id IS NULL). Without
        user_id, returns the row regardless of owner (used internally
        for cross-user operations like webhook follow-ups).
        """
        with self._lock:
            if user_id is not None:
                row = self._conn.execute(
                    "SELECT payload FROM incidents "
                    "WHERE incident_id = ? AND (user_id = ? OR user_id IS NULL)",
                    (incident_id, user_id),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT payload FROM incidents WHERE incident_id = ?",
                    (incident_id,),
                ).fetchone()
        if row is None:
            return None
        return AnalyzeResponse.model_validate_json(row[0])

    def list_recent(
        self,
        limit: int = 25,
        *,
        user_id: Optional[str] = None,
    ) -> List[IncidentSummary]:
        """Recent incidents visible to the given user.

        Always includes the shared/public bucket (user_id IS NULL).
        When ``user_id`` is None, returns only the shared pool - this
        is the safe default for unauthenticated requests so no signed-in
        user's private incidents leak.
        """
        capped_limit = max(1, min(limit, self._capacity))
        with self._lock:
            if user_id is None:
                rows = self._conn.execute(
                    "SELECT payload FROM incidents "
                    "WHERE user_id IS NULL "
                    "ORDER BY created_at DESC LIMIT ?",
                    (capped_limit,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT payload FROM incidents "
                    "WHERE user_id = ? OR user_id IS NULL "
                    "ORDER BY created_at DESC LIMIT ?",
                    (user_id, capped_limit),
                ).fetchall()

        summaries: List[IncidentSummary] = []
        for (payload_json,) in rows:
            try:
                analysis = AnalyzeResponse.model_validate_json(payload_json)
            except Exception:  # noqa: BLE001
                logger.exception("Skipping malformed incident row during list_recent")
                continue
            summaries.append(
                IncidentSummary(
                    incident_id=analysis.incident_id,
                    title=analysis.title,
                    created_at=analysis.created_at,
                    severity=analysis.severity,
                    root_cause=analysis.root_cause,
                    affected_service_count=len(analysis.affected_services),
                )
            )
        return summaries


_default_store: Optional[AnalysisStore] = None
_store_lock = threading.Lock()


def get_store() -> AnalysisStore:
    """Process-wide singleton store. First call creates + initialises it."""
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = AnalysisStore()
    return _default_store
