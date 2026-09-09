from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from chart_observatory.adapters.files.manual import ImportMetadata
from chart_observatory.api.dependencies import ApplicationDep

router = APIRouter()


class PreviewRequest(BaseModel):
    path: str
    schema_version: str = "manual_generic_v2"
    provider: str | None = None
    origin_platform: str | None = None
    chart_family: str | None = None
    native_frequency: str | None = None
    metric_type: str | None = None


class ApplyRequest(BaseModel):
    token: str


@router.post("/imports/preview")
def preview(payload: PreviewRequest, service: ApplicationDep) -> dict[str, object]:
    metadata = None
    if all(
        value is not None
        for value in (
            payload.provider,
            payload.origin_platform,
            payload.chart_family,
            payload.native_frequency,
            payload.metric_type,
        )
    ):
        metadata = ImportMetadata(
            provider=payload.provider or "",
            origin_platform=payload.origin_platform or "",
            chart_family=payload.chart_family or "",
            native_frequency=payload.native_frequency or "",
            metric_type=payload.metric_type or "",
        )
    return service.preview_import(Path(payload.path), payload.schema_version, metadata)


@router.post("/imports/apply")
def apply(payload: ApplyRequest, service: ApplicationDep) -> dict[str, object]:
    return service.apply_import(payload.token)


@router.get("/rankings")
def rankings(
    service: ApplicationDep,
    country: str | None = None,
    limit: int = 200,
) -> dict[str, object]:
    return service.rankings(country, limit=max(1, min(limit, 5_000)))
