"""Prepare hash-bound review cards from completed native evidence campaign cells."""

import argparse
import json
from pathlib import Path

from chart_observatory.research_native_review import build_queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_queue(args.campaign, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
