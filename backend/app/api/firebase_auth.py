"""Firebase ID-token verification endpoint.

The frontend Firebase Web SDK signs the user in with Google, gets back
a short-lived ID token, and POSTs it here. We verify it with the
Firebase Admin SDK (which checks the JWT signature against Google's
public certs and ensures the token was minted for our project) and
return a canonical user_id of ``fb:<uid>`` plus profile bits.

Disabled silently when the three FIREBASE_* settings aren't set -
exposes a 503 so the frontend can surface "configure Firebase" without
the route 404ing.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.identity import firebase_user_id

logger = logging.getLogger(__name__)
router = APIRouter()

_initialized = False


def _ensure_firebase_admin() -> None:
    """Lazy-init the Firebase Admin SDK on first verify call.

    Done lazily so that importing this module doesn't blow up when the
    env vars are missing (e.g. local dev without Firebase configured).
    """
    global _initialized
    if _initialized:
        return

    settings = get_settings()
    if not settings.firebase_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "Firebase sign-in not configured on this server. "
                "Set FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, "
                "FIREBASE_PRIVATE_KEY in the backend .env."
            ),
        )

    import firebase_admin  # noqa: WPS433 — deferred to avoid cold import
    from firebase_admin import credentials

    # Env-stored private keys keep their literal "\n" escapes so the
    # value fits on one line. Unescape before handing to the SDK or
    # cryptography rejects the PEM.
    private_key = (settings.firebase_private_key or "").replace("\\n", "\n")

    cred = credentials.Certificate(
        {
            "type": "service_account",
            "project_id": settings.firebase_project_id,
            "client_email": settings.firebase_client_email,
            "private_key": private_key,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )
    # Tolerate double-init across uvicorn reloads.
    if not firebase_admin._apps:  # pragma: no cover — runtime guard
        firebase_admin.initialize_app(cred)
    _initialized = True


class FirebaseExchangeRequest(BaseModel):
    id_token: str


class FirebaseExchangeResponse(BaseModel):
    user_id: str
    kind: str = "firebase"
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None


@router.post("/auth/firebase", response_model=FirebaseExchangeResponse)
def exchange_firebase_token(
    payload: FirebaseExchangeRequest,
) -> FirebaseExchangeResponse:
    """Verify a Firebase ID token and return our canonical identity.

    The token is minted by the Firebase Web SDK after a successful
    Google sign-in popup. Verification is delegated to firebase_admin -
    it checks JWT signature, expiry, audience (= our project_id), and
    issuer. Any failure raises 401; we deliberately do not echo the
    underlying error message because it can leak project ids.
    """
    _ensure_firebase_admin()

    # Import lazily so module import succeeds without firebase_admin
    # installed at all (e.g. CI without the dep).
    from firebase_admin import auth as fb_auth  # noqa: WPS433

    try:
        decoded = fb_auth.verify_id_token(payload.id_token)
    except Exception as exc:  # noqa: BLE001 — surface as 401 either way
        logger.warning("Firebase verify failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid Firebase ID token")

    uid = decoded.get("uid") or decoded.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Firebase token missing uid")

    display_name = decoded.get("name") or decoded.get("email") or "Google user"
    avatar_url = decoded.get("picture")
    email = decoded.get("email")

    user_id = firebase_user_id(uid)
    logger.info("Firebase sign-in resolved user_id=%s", user_id)

    return FirebaseExchangeResponse(
        user_id=user_id,
        display_name=display_name,
        avatar_url=avatar_url,
        email=email,
    )
