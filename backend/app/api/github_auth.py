"""GitHub OAuth + repo listing endpoints.

Click "Connect GitHub" in the dashboard ->
  GET  /api/v1/auth/github/login    -> 302 to github.com/login/oauth/authorize
  GET  /api/v1/auth/github/callback -> exchanges code, redirects to dashboard
  GET  /api/v1/auth/github/me       -> { enabled, connected, login, avatar_url }
  GET  /api/v1/auth/github/repos    -> the user's accessible repos
  POST /api/v1/auth/github/disconnect

Single-user, in-memory token store: the active session belongs to
whoever finished the OAuth dance most recently. Production would key
this by an IncidentIQ user id and persist somewhere encrypted.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.api.deps import get_github_auth
from app.core.config import get_settings
from app.services.github_auth import GitHubAuthService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/auth/github/login")
def github_login(
    auth: GitHubAuthService = Depends(get_github_auth),
) -> RedirectResponse:
    """Kick off the OAuth dance - redirect to GitHub."""
    if not auth.enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "GitHub OAuth not configured. Add GITHUB_OAUTH_CLIENT_ID and "
                "GITHUB_OAUTH_CLIENT_SECRET to the backend .env."
            ),
        )
    return RedirectResponse(url=auth.build_authorize_url(), status_code=302)


@router.get("/auth/github/callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    auth: GitHubAuthService = Depends(get_github_auth),
) -> RedirectResponse:
    """Handle the GitHub redirect, exchange code for token, bounce back."""
    if not auth.enabled:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")

    if not auth.consume_state(state):
        raise HTTPException(
            status_code=400,
            detail="OAuth state did not match. Start the login flow again.",
        )

    try:
        session = await auth.exchange_code(code)
    except Exception as exc:  # noqa: BLE001
        logger.exception("GitHub code exchange failed")
        raise HTTPException(
            status_code=502, detail=f"GitHub code exchange failed: {exc}"
        ) from exc

    # Promote the GitHub login into a sign-in event. The redirect fragment
    # tells the frontend bootstrap to (a) flip from guest -> gh:<login>
    # if the user was browsing as a guest, and (b) refresh the user chip
    # in the header. Frontend reads gh_login from the fragment instead
    # of round-tripping through another /auth/me call.
    target = get_settings().github_oauth_post_login_redirect
    return RedirectResponse(
        url=f"{target}#github=connected&login={session.login}",
        status_code=302,
    )


@router.get("/auth/github/me")
def github_me(
    auth: GitHubAuthService = Depends(get_github_auth),
) -> Dict[str, Any]:
    """Current connection status for the UI status pill."""
    return auth.public_status()


@router.get("/auth/github/repos")
async def github_repos(
    auth: GitHubAuthService = Depends(get_github_auth),
) -> List[Dict[str, Any]]:
    """List repos the connected GitHub user can read."""
    if not auth.is_connected:
        raise HTTPException(
            status_code=401,
            detail="Not connected to GitHub. Click 'Connect GitHub' first.",
        )
    try:
        return await auth.list_repos()
    except Exception as exc:  # noqa: BLE001
        logger.exception("GitHub /user/repos failed")
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}") from exc


@router.post("/auth/github/disconnect")
def github_disconnect(
    auth: GitHubAuthService = Depends(get_github_auth),
) -> Dict[str, str]:
    auth.disconnect()
    return {"status": "disconnected"}
