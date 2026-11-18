"""Import verified supplemental provider series into a lineage-preserving catalog."""

import argparse
import json
from pathlib import Path

from chart_observatory.supplemental_series import import_verified_provider_series


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("data/derived/annual_revision/provider_series"),
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/derived/annual_revision/provider_series/supplemental-catalog.sqlite"),
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("data/derived/annual_revision/provider_series/supplemental-denominators.json"),
    )
    parser.add_argument("--packets", nargs="*", default=None)
    args = parser.parse_args(argv)
    summary = import_verified_provider_series(
        args.base_dir,
        args.db_path,
        packet_names=args.packets,
    )
    args.report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
