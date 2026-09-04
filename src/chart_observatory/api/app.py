from pathlib import Path

from fastapi import FastAPI

from chart_observatory.api.routes import charts, coverage, exports, rights, tracks
from chart_observatory.application import LocalResearchApplication


def create_app(application: LocalResearchApplication | None = None) -> FastAPI:
    app = FastAPI(title="Chart Observatory", version="0.1.0")
    app.state.application = application or LocalResearchApplication(Path("data/runtime"))
    for router in (charts.router, tracks.router, coverage.router, rights.router, exports.router):
        app.include_router(router)
    return app


app = create_app()
