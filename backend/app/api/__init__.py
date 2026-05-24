"""HTTP API routes for IncidentIQ."""

from fastapi import APIRouter

from app.api import (
    analyze,
    auth,
    chat,
    code_fix,
    deep_trace,
    export,
    firebase_auth,
    github_auth,
    incidents,
    integrations,
    samples,
    watch,
    webhooks,
)

router = APIRouter()
router.include_router(analyze.router, prefix="/api/v1", tags=["analyze"])
router.include_router(auth.router, prefix="/api/v1", tags=["auth"])
router.include_router(chat.router, prefix="/api/v1", tags=["chat"])
router.include_router(code_fix.router, prefix="/api/v1", tags=["code-fix"])
router.include_router(deep_trace.router, prefix="/api/v1", tags=["deep-trace"])
router.include_router(export.router, prefix="/api/v1", tags=["export"])
router.include_router(firebase_auth.router, prefix="/api/v1", tags=["firebase-auth"])
router.include_router(github_auth.router, prefix="/api/v1", tags=["github-auth"])
router.include_router(incidents.router, prefix="/api/v1", tags=["incidents"])
router.include_router(integrations.router, prefix="/api/v1", tags=["integrations"])
router.include_router(samples.router, prefix="/api/v1", tags=["samples"])
router.include_router(watch.router, prefix="/api/v1", tags=["watch"])
router.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
