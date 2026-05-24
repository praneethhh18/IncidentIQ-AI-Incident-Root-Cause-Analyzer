"""Unified identity endpoints.

POST /api/v1/auth/guest    - issue a guest user_id; client stores in localStorage
GET  /api/v1/auth/me       - return what the current X-IIQ-User header resolves to
POST /api/v1/auth/signout  - no server-side state to wipe (stateless tokens);
                              endpoint exists for symmetry + future bookkeeping

The GitHub OAuth callback (see api/github_auth.py) also issues a user_id
on success - the frontend stitches that into localStorage during the
post-callback bootstrap.

The Google/Firebase sign-in endpoint lives in api/firebase_auth.py and
gets registered once the user provides their Firebase project config.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import current_user
from app.services.identity import UserIdentity, new_guest_id

logger = logging.getLogger(__name__)
router = APIRouter()


class GuestResponse(BaseModel):
    user_id: str
    kind: str = "guest"


class MeResponse(BaseModel):
    authenticated: bool
    user_id: Optional[str] = None
    kind: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


@router.post("/auth/guest", response_model=GuestResponse)
def issue_guest() -> GuestResponse:
    """Mint a fresh anonymous identity for browsers that don't want to sign in.

    The returned user_id is the only place this guest lives - frontend
    stores it in localStorage and sends it back on every request via
    X-IIQ-User. Server keeps no registry; clearing localStorage = new
    guest, no carry-over. Their incidents and pasted credentials are
    visible to no one else.
    """
    user_id = new_guest_id()
    logger.info("Issued guest user_id=%s", user_id)
    return GuestResponse(user_id=user_id)


@router.get("/auth/me", response_model=MeResponse)
def whoami(
    user: Optional[UserIdentity] = Depends(current_user),
) -> MeResponse:
    """What does my X-IIQ-User header resolve to?"""
    if user is None:
        return MeResponse(authenticated=False)
    return MeResponse(
        authenticated=True,
        user_id=user.id,
        kind=user.kind,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )


@router.post("/auth/signout")
def signout() -> dict[str, str]:
    """Acknowledge the client-initiated sign-out.

    The actual sign-out is a client-side localStorage clear; the server
    holds no token state. This endpoint exists so the frontend can
    log a clean intent and so future hard-token revocation has a place
    to live.
    """
    return {"status": "ok"}
