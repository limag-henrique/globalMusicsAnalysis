from pathlib import Path

from fastapi import FastAPI

from chart_observatory.api.routes import charts, coverage, exports, rights, tracks
from chart_observatory.application import ResearchApplication
from chart_observatory.config import Settings


def create_app(
    application: ResearchApplication | None = None,
    *,
    database_url: str | None = None,
    root: Path = Path("data/runtime"),
) -> FastAPI:
    app = FastAPI(title="Chart Observatory", version="0.1.0")
    if application is None:
        settings = Settings.load(Path.cwd())
        application = ResearchApplication(
            root,
            database_url=database_url or settings.database_url,
        )
    app.state.application = application
    for router in (charts.router, tracks.router, coverage.router, rights.router, exports.router):
        app.include_router(router)
    return app


app = create_app()
