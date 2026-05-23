"""HTTP API routes for IncidentIQ."""

from fastapi import APIRouter

from app.api import analyze, export, incidents, integrations, samples, webhooks

router = APIRouter()
router.include_router(analyze.router, prefix="/api/v1", tags=["analyze"])
router.include_router(export.router, prefix="/api/v1", tags=["export"])
router.include_router(incidents.router, prefix="/api/v1", tags=["incidents"])
router.include_router(integrations.router, prefix="/api/v1", tags=["integrations"])
router.include_router(samples.router, prefix="/api/v1", tags=["samples"])
router.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
