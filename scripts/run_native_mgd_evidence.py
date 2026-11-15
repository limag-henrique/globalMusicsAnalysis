"""Run bounded native MGD reconstruction; no network, database writes or approvals."""

import argparse
import json
from pathlib import Path

from chart_observatory.research_native_batch import run_campaign


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--reuse-root", action="append", type=Path, default=[])
    args = parser.parse_args()
    report = run_campaign(
        project=args.project,
        selection=args.selection,
        output=args.output,
        limit=args.limit,
        workers=args.workers,
        reuse_roots=args.reuse_root,
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "state": report["state"],
                "summary": report["summary"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
