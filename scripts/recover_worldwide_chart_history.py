"""Resume source-aware worldwide chart discovery; never rewrites frozen selections."""

import argparse
import asyncio
import json
from pathlib import Path

from chart_observatory.research_chart_recovery import collect_campaign, initialize_campaign

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=12)
    parser.add_argument("--hours", type=float, default=2)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--retry-unresolved", action="store_true")
    args = parser.parse_args()
    if args.plan_only:
        report = initialize_campaign(project=ROOT, selection=args.selection, state=args.state)
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "catalog_observed_markets",
                        "catalog_capacity_percent",
                        "youtube_documented_markets",
                    )
                },
                ensure_ascii=False,
            )
        )
    else:
        result = asyncio.run(
            collect_campaign(
                project=ROOT,
                selection=args.selection,
                state=args.state,
                max_requests=args.max_requests,
                hours=args.hours,
                retry_unresolved=args.retry_unresolved,
            )
        )
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
