from fastapi import APIRouter

from chart_observatory.api.dependencies import ApplicationDep

router = APIRouter()


@router.get("/coverage")
def coverage(service: ApplicationDep, country: str | None = None) -> dict[str, object]:
    return service.coverage(country)
