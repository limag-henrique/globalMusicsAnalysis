from fastapi import APIRouter
from pydantic import BaseModel

from chart_observatory.api.dependencies import ApplicationDep

router = APIRouter()


class ExportRequest(BaseModel):
    dataset_name: str
    format: str


@router.post("/exports")
def create_export(payload: ExportRequest, service: ApplicationDep) -> dict[str, object]:
    return service.export(payload.dataset_name, payload.format)
