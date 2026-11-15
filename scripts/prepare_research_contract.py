"""Create a private, draft-only 26-topic calibration bundle; no cloud clients."""

import argparse
import json
from pathlib import Path

from chart_observatory.lyrics.research_contract import write_contract_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = write_contract_bundle(args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), **manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
