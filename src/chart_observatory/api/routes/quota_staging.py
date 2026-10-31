from fastapi import APIRouter, HTTPException, Query

from chart_observatory.api.dependencies import ApplicationDep
from chart_observatory.lyrics.staging_review import browse_pending, list_snapshots, pending_detail

router = APIRouter(prefix="/quota-staging", tags=["Pending quota imports"])


@router.get("/snapshots")
def snapshots(service: ApplicationDep, limit: int = Query(20, ge=1, le=100)):
    return {"snapshots": list_snapshots(service.engine, limit), "classification_ready": False}


@router.get("/candidates")
def pending_candidates(
    service: ApplicationDep,
    run_id: str | None = Query(None, pattern=r"^[0-9a-f]{64}$"),
    country: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    year: int | None = Query(None, ge=2018, le=2026),
    has_text: bool | None = None,
    query: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return browse_pending(
        service.engine,
        run_id=run_id,
        country=country,
        year=year,
        has_text=has_text,
        query=query,
        limit=limit,
        offset=offset,
    )


@router.get("/candidates/{candidate_id}")
def candidate_detail(
    candidate_id: str,
    service: ApplicationDep,
    run_id: str | None = Query(None, pattern=r"^[0-9a-f]{64}$"),
):
    try:
        result = pending_detail(service.engine, candidate_id, run_id=run_id)
    except ValueError:
        raise HTTPException(409, "Stored text failed its integrity check") from None
    if result is None:
        raise HTTPException(404, "Candidate not found in this snapshot")
    return result
