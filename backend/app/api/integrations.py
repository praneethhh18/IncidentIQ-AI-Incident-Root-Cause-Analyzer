"""GET /api/v1/integrations — connection status for monitoring tools."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_integrations
from app.models import IntegrationStatus, SourceKind
from app.services.integrations import IntegrationRegistry

router = APIRouter()


@router.get("/integrations", response_model=List[IntegrationStatus])
async def list_integrations(
    registry: IntegrationRegistry = Depends(get_integrations),
) -> List[IntegrationStatus]:
    return await registry.status_all()


@router.get("/integrations/datadog/services")
async def datadog_services(
    window_minutes: int = Query(60, ge=5, le=720),
    registry: IntegrationRegistry = Depends(get_integrations),
) -> dict:
    """Recent services that emitted error/warn logs - feeds the service dropdown."""
    integration = registry.get(SourceKind.DATADOG)
    if integration is None or not integration.is_configured():
        return {"connected": False, "services": []}
    services = await integration.list_recent_services(window_minutes=window_minutes)
    return {"connected": True, "services": services}
