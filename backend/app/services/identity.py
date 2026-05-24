"""Unified user identity.

Three identity sources land in a single ``user_id`` string namespace so
the rest of the app can scope data without caring how the user signed in:

  gh:<github_login>     — signed in via the existing GitHub OAuth flow
  fb:<firebase_uid>     — signed in via Firebase (Google)
  guest:<random_uuid>   — clicked "Continue as guest", per-browser only

Every API request must carry the user id in a single place: the
``X-IIQ-User`` request header. Frontend stores it in localStorage and
attaches it to every fetch (same pattern as the old X-IIQ-Session, just
promoted to identity instead of bucket-of-credentials).

Backend dependencies read the header, normalise to a UserIdentity dataclass,
and pass it everywhere a "who is asking?" question matters: which
incidents to list, which Datadog keys to use, whose Watch Mode to start.

Guest ids are issued by POST /api/v1/auth/guest — random, opaque, never
recyclable. There's no server-side guest registry beyond what shows up
in the per-user credential store; clearing localStorage = new guest.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Literal, Optional

logger = logging.getLogger(__name__)


UserKind = Literal["github", "firebase", "guest"]


@dataclass(frozen=True)
class UserIdentity:
    """The result of resolving an ``X-IIQ-User`` header.

    ``id`` is always prefixed (``gh:foo`` / ``fb:abc`` / ``guest:xyz``).
    ``kind`` is the trailing literal so handler code can branch on it
    without re-parsing the prefix.
    """

    id: str
    kind: UserKind
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    @property
    def is_anonymous_guest(self) -> bool:
        return self.kind == "guest"


def new_guest_id() -> str:
    """Issue a fresh ``guest:<token>`` id. Opaque + unguessable + unique."""
    return f"guest:{secrets.token_urlsafe(24)}"


def github_user_id(login: str) -> str:
    """Build the canonical user id for a GitHub login."""
    return f"gh:{login}"


def firebase_user_id(uid: str) -> str:
    """Build the canonical user id for a Firebase uid."""
    return f"fb:{uid}"


def parse_user_id(raw: Optional[str]) -> Optional[UserIdentity]:
    """Parse a raw header value into UserIdentity, or None if missing/malformed.

    We do NOT validate the suffix here - the header is the user's
    self-declared identity, and the security model assumes a stolen
    token is bounded by what's in that user's own slot (their pasted
    keys, their incident history). For real auth, a JWT signed by the
    backend would gate this. For hackathon scope, opaque guest tokens +
    OAuth-validated GitHub logins are enough.
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    if raw.startswith("gh:"):
        login = raw[3:].strip()
        if not login:
            return None
        return UserIdentity(id=raw, kind="github", display_name=login)
    if raw.startswith("fb:"):
        uid = raw[3:].strip()
        if not uid:
            return None
        return UserIdentity(id=raw, kind="firebase")
    if raw.startswith("guest:"):
        token = raw[6:].strip()
        if not token or len(token) < 8:
            return None
        return UserIdentity(id=raw, kind="guest")
    return None
