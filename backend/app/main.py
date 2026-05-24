"""IncidentIQ FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import router as api_router
from app.api.deps import get_bedrock, get_integrations
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("incidentiq")

app = FastAPI(
    title="IncidentIQ",
    description=(
        "AI-driven incident root-cause analyzer for SRE teams. "
        "Connects to Datadog, Grafana, and New Relic; uses AWS Bedrock "
        "(Amazon Nova Pro) to produce root cause, timeline, affected "
        "services, severity, and prioritized fix recommendations."
    ),
    version=__version__,
)

# CORS whitelists:
#   - Exact origins (CORS_ORIGINS env): the production domains we own.
#   - Regex (CORS_ORIGIN_REGEX env): pattern for Vercel preview URLs
#     (incident-<hash>-<team>.vercel.app), which change per build and
#     can't be enumerated. Default lets *.vercel.app under the
#     praneethhh0218-7818s-projects team through; override per
#     environment via CORS_ORIGIN_REGEX in .env.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, object]:
    """Lightweight liveness probe with feature flags for the UI."""
    return {
        "status": "ok",
        "version": __version__,
        "bedrock_enabled": settings.bedrock_enabled,
        "model": settings.bedrock_model_id,
        "integrations": {
            "datadog": settings.datadog_enabled,
            "grafana": settings.grafana_enabled,
            "newrelic": settings.newrelic_enabled,
        },
    }


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "IncidentIQ",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }


@app.on_event("startup")
def _log_startup() -> None:
    bedrock = get_bedrock()
    registry = get_integrations()
    mode = "live" if bedrock.enabled else "demo"
    integration_names = [
        i.display_name for i in registry.all() if i.is_configured()
    ]
    logger.info(
        "IncidentIQ %s ready · mode=%s · integrations=%s",
        __version__,
        mode,
        integration_names or "none (demo fallbacks active)",
    )


# AWS Lambda adapter — opt-in, only used when deploying via Mangum.
try:
    from mangum import Mangum  # type: ignore

    handler = Mangum(app)
except Exception:  # pragma: no cover — Mangum is optional at runtime
    handler = None
