"""Integrate an explicitly provisional native annual supplement in a new snapshot."""

import argparse
import json
from pathlib import Path

from chart_observatory.ingestion.published_annual_overlay import build_published_overlay

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("parent", "supplement", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = build_published_overlay(
        args.parent, args.supplement, args.output, project=Path(__file__).resolve().parents[1]
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "memberships",
                    "published_annual_provisional_added_positions",
                    "missing_positions",
                    "source_coverage_rows",
                    "raw_membership_coverage_pct",
                    "g1_approved",
                )
            }
        )
    )
