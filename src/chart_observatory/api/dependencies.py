from typing import Annotated, cast

from fastapi import Depends, Request

from chart_observatory.application import LocalResearchApplication


def application(request: Request) -> LocalResearchApplication:
    return cast(LocalResearchApplication, request.app.state.application)


ApplicationDep = Annotated[LocalResearchApplication, Depends(application)]
