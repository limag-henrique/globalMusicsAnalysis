from fastapi import APIRouter

from chart_observatory.api.dependencies import ApplicationDep

router = APIRouter()


@router.get("/rights")
def rights(service: ApplicationDep) -> dict[str, object]:
    return service.rights()
