"""Shared FastAPI dependencies — singleton services for request handlers."""

from __future__ import annotations

from threading import Lock

from typing import Optional

from fastapi import Header

from app.core.config import get_settings
from app.services.analyzer import Analyzer
from app.services.bedrock import BedrockClient
from app.services.github_auth import GitHubAuthService, get_github_auth_service
from app.services.identity import UserIdentity, parse_user_id
from app.services.integrations import IntegrationRegistry
from app.services.session_creds import (
    SessionCredentialStore,
    get_session_credential_store,
)
from app.services.store import AnalysisStore, get_store

_bedrock_singleton: BedrockClient | None = None
_registry_singleton: IntegrationRegistry | None = None
_lock = Lock()


def _ensure_singletons() -> tuple[BedrockClient, IntegrationRegistry]:
    global _bedrock_singleton, _registry_singleton
    if _bedrock_singleton is None or _registry_singleton is None:
        with _lock:
            if _bedrock_singleton is None:
                _bedrock_singleton = BedrockClient(get_settings())
            if _registry_singleton is None:
                _registry_singleton = IntegrationRegistry(get_settings())
    return _bedrock_singleton, _registry_singleton


def get_bedrock() -> BedrockClient:
    bedrock, _ = _ensure_singletons()
    return bedrock


def get_integrations() -> IntegrationRegistry:
    _, registry = _ensure_singletons()
    return registry


def get_analyzer() -> Analyzer:
    bedrock, registry = _ensure_singletons()
    return Analyzer(get_settings(), bedrock, registry)


def get_analysis_store() -> AnalysisStore:
    return get_store()


def get_github_auth() -> GitHubAuthService:
    return get_github_auth_service(get_settings())


def get_session_store() -> SessionCredentialStore:
    return get_session_credential_store()


def session_id_header(
    x_iiq_session: Optional[str] = Header(default=None, alias="X-IIQ-Session"),
    x_iiq_user: Optional[str] = Header(default=None, alias="X-IIQ-User"),
) -> Optional[str]:
    """Pulls the user / session identifier out of the incoming request.

    The new auth model uses ``X-IIQ-User`` (prefixed: gh:/fb:/guest:).
    For backwards compatibility with code paths that still send the
    older ``X-IIQ-Session`` header, we accept either. New code should
    depend on ``current_user`` instead and get a typed UserIdentity.
    """
    raw = x_iiq_user or x_iiq_session
    return (raw or "").strip() or None


def current_user(
    x_iiq_user: Optional[str] = Header(default=None, alias="X-IIQ-User"),
) -> Optional[UserIdentity]:
    """Resolve the request's user identity, or None for anonymous.

    Anonymous means no header at all - acceptable for server-to-server
    flows like the webhook ingest path, but the dashboard always
    attaches a header. Routes that require a real user should treat
    ``None`` as a 401.
    """
    return parse_user_id(x_iiq_user)
