from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from chart_observatory.api.dependencies import ApplicationDep

router = APIRouter()


class PreviewRequest(BaseModel):
    path: str
    schema_version: str = "manual_generic_v1"


class ApplyRequest(BaseModel):
    token: str


@router.post("/imports/preview")
def preview(payload: PreviewRequest, service: ApplicationDep) -> dict[str, object]:
    return service.preview_import(Path(payload.path), payload.schema_version)


@router.post("/imports/apply")
def apply(payload: ApplyRequest, service: ApplicationDep) -> dict[str, object]:
    return service.apply_import(payload.token)


@router.get("/rankings")
def rankings(service: ApplicationDep, country: str | None = None) -> dict[str, object]:
    return service.rankings(country)
