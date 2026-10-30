"""Single local entry point for the annual revision preparation and readiness gates."""

from chart_observatory.revision_workflow import main

if __name__ == "__main__":
    raise SystemExit(main())
