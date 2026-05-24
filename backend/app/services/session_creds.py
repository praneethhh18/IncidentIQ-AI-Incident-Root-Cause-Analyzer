"""Per-session credential store for the monitoring connectors.

Lets visitors at the public IncidentIQ deployment paste their *own*
Datadog / Grafana / New Relic credentials in-app, without us having to
touch the server-side ``.env``. Each browser keeps its own session UUID
in localStorage and sends it back as ``X-IIQ-Session: <uuid>``; the
backend looks the UUID up in this in-memory dict and uses whatever
credentials are stashed there to talk to that user's monitoring stack.

Falls back to ``.env`` credentials when:
  - the request has no session header (e.g. server-to-server, webhooks)
  - the session has no overrides for that specific provider

Storage is in-process and TTL'd (sessions expire after 24h without
activity). Production multi-tenancy would replace this with an
encrypted database table keyed by user id - the interface stays the
same so callers won't notice.

We deliberately never echo stored credentials back to the client - the
``status`` endpoint returns booleans only ("datadog: configured: true")
so a stolen session id can't be exchanged for plaintext keys.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# Sessions get pruned after this long without a read/write.
SESSION_TTL_SECONDS = 24 * 60 * 60

# How often we sweep expired sessions (lazy: triggered on writes).
SWEEP_INTERVAL_SECONDS = 600


@dataclass
class DatadogCreds:
    api_key: str
    app_key: str
    site: str = "datadoghq.com"


@dataclass
class GrafanaCreds:
    url: str
    api_key: str


@dataclass
class NewRelicCreds:
    user_key: str
    account_id: str


@dataclass
class SessionEntry:
    """All credentials a single browser session has stored."""

    datadog: Optional[DatadogCreds] = None
    grafana: Optional[GrafanaCreds] = None
    newrelic: Optional[NewRelicCreds] = None
    last_seen: float = field(default_factory=time.time)


class SessionCredentialStore:
    """Process-wide, lock-guarded store of per-session credentials."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionEntry] = {}
        self._lock = threading.Lock()
        self._last_sweep_at: float = 0.0

    # ── Session lifecycle ────────────────────────────────────────────

    def issue_session_id(self) -> str:
        """Generate a fresh session id and reserve a slot for it."""
        session_id = secrets.token_urlsafe(24)
        with self._lock:
            self._sessions[session_id] = SessionEntry()
            self._maybe_sweep_locked()
        return session_id

    def get_or_create(self, session_id: Optional[str]) -> str:
        """Return the supplied session id (touching its last_seen) or issue a new one."""
        if session_id:
            with self._lock:
                entry = self._sessions.get(session_id)
                if entry is not None:
                    entry.last_seen = time.time()
                    return session_id
        # Either no id was provided or it's no longer in our store.
        return self.issue_session_id()

    # ── Provider-specific accessors ──────────────────────────────────

    def get_datadog(self, session_id: Optional[str]) -> Optional[DatadogCreds]:
        return self._get_entry(session_id).datadog if session_id else None

    def get_grafana(self, session_id: Optional[str]) -> Optional[GrafanaCreds]:
        return self._get_entry(session_id).grafana if session_id else None

    def get_newrelic(self, session_id: Optional[str]) -> Optional[NewRelicCreds]:
        return self._get_entry(session_id).newrelic if session_id else None

    def set_datadog(self, session_id: str, creds: DatadogCreds) -> None:
        self._update(session_id, lambda e: setattr(e, "datadog", creds))

    def set_grafana(self, session_id: str, creds: GrafanaCreds) -> None:
        self._update(session_id, lambda e: setattr(e, "grafana", creds))

    def set_newrelic(self, session_id: str, creds: NewRelicCreds) -> None:
        self._update(session_id, lambda e: setattr(e, "newrelic", creds))

    def clear_datadog(self, session_id: str) -> None:
        self._update(session_id, lambda e: setattr(e, "datadog", None))

    def clear_grafana(self, session_id: str) -> None:
        self._update(session_id, lambda e: setattr(e, "grafana", None))

    def clear_newrelic(self, session_id: str) -> None:
        self._update(session_id, lambda e: setattr(e, "newrelic", None))

    def public_status(self, session_id: Optional[str]) -> Dict[str, bool]:
        """Booleans only - never echoes the actual keys back to the client."""
        entry = self._get_entry(session_id)
        return {
            "datadog": entry.datadog is not None,
            "grafana": entry.grafana is not None,
            "newrelic": entry.newrelic is not None,
        }

    # ── Internals ────────────────────────────────────────────────────

    def _get_entry(self, session_id: Optional[str]) -> SessionEntry:
        if not session_id:
            return SessionEntry()
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                return SessionEntry()
            entry.last_seen = time.time()
            return entry

    def _update(self, session_id: str, mutator) -> None:
        with self._lock:
            entry = self._sessions.setdefault(session_id, SessionEntry())
            mutator(entry)
            entry.last_seen = time.time()
            self._maybe_sweep_locked()

    def _maybe_sweep_locked(self) -> None:
        """Drop entries idle for > SESSION_TTL_SECONDS. Called under lock."""
        now = time.time()
        if now - self._last_sweep_at < SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep_at = now
        cutoff = now - SESSION_TTL_SECONDS
        expired = [sid for sid, e in self._sessions.items() if e.last_seen < cutoff]
        for sid in expired:
            self._sessions.pop(sid, None)
        if expired:
            logger.info("Pruned %d expired session(s)", len(expired))


_default_store: Optional[SessionCredentialStore] = None
_store_lock = threading.Lock()


def get_session_credential_store() -> SessionCredentialStore:
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = SessionCredentialStore()
    return _default_store
