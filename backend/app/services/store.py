"""Incident store backed by SQLite (with an in-memory fast path).

Default behaviour: persist to ``store_db_path`` from settings (which on
EC2 resolves to ``/var/lib/incidentiq/store.db`` thanks to systemd's
``StateDirectory=incidentiq``). Local dev gets ``./store.db`` next to
the working directory.

A single ``incidents`` table holds the full Pydantic payload as JSON in
one column - simple, schema-less, easy to evolve. Reads via a small
LRU cache so the chat / detail page doesn't re-deserialise the same
incident repeatedly.

The interface (save / get / list_recent / clear) is unchanged from the
in-memory version, so callers don't notice the swap.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

from app.core.config import get_settings
from app.models import AnalyzeResponse, IncidentSummary

logger = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    payload     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS incidents_created_at_idx
    ON incidents(created_at DESC);
"""


class AnalysisStore:
    """SQLite-backed analysis store.

    Connection is opened with ``check_same_thread=False`` and guarded by
    an explicit lock so multiple uvicorn workers (or async tasks) can
    share the same store instance safely. WAL mode keeps writers from
    blocking readers, which matters during long-running analyses.
    """

    def __init__(self, db_path: Optional[str] = None, capacity: int = 1000) -> None:
        self._capacity = capacity
        self._lock = threading.Lock()
        self._db_path = db_path or get_settings().store_db_path

        # ``:memory:`` is fine for tests; for a file path, ensure the
        # parent directory exists so we don't crash on first start.
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit; we batch where it matters
        )
        # WAL: readers don't block on writers (matters under load).
        # synchronous=NORMAL is the recommended pairing for WAL.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        logger.info("AnalysisStore using SQLite at %s", self._db_path)

    # ── Mutation ─────────────────────────────────────────────────────

    def save(self, analysis: AnalyzeResponse) -> None:
        payload = analysis.model_dump_json()
        created_at_iso = analysis.created_at.isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO incidents (incident_id, created_at, payload) "
                "VALUES (?, ?, ?)",
                (analysis.incident_id, created_at_iso, payload),
            )
            # LRU-style cap so the table doesn't grow unbounded over time.
            self._conn.execute(
                "DELETE FROM incidents WHERE incident_id IN ("
                "SELECT incident_id FROM incidents "
                "ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
                (self._capacity,),
            )

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM incidents")

    # ── Reads ────────────────────────────────────────────────────────

    def get(self, incident_id: str) -> Optional[AnalyzeResponse]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return AnalyzeResponse.model_validate_json(row[0])

    def list_recent(self, limit: int = 25) -> List[IncidentSummary]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM incidents ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, self._capacity)),),
            ).fetchall()
        summaries: List[IncidentSummary] = []
        for (payload_json,) in rows:
            try:
                analysis = AnalyzeResponse.model_validate_json(payload_json)
            except Exception:  # noqa: BLE001 - skip a single bad row, don't crash
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
