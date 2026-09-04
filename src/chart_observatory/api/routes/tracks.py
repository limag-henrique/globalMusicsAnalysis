from fastapi import APIRouter

from chart_observatory.api.dependencies import ApplicationDep

router = APIRouter()


@router.get("/resolution")
def resolution(service: ApplicationDep) -> dict[str, object]:
    return service.resolution()


@router.get("/provenance")
def provenance(service: ApplicationDep) -> dict[str, object]:
    return service.provenance()
