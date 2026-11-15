"""Extract the preserved Pro-Musica 2018 Top200 table as review evidence."""

import argparse
import hashlib
import json
from pathlib import Path

import pdfplumber

from chart_observatory.research_rankings import verify_published_annual


def extract(path):
    def clean(value):
        return " ".join(value.split())

    records = []
    with pdfplumber.open(path) as pdf:
        for page_number in range(8, 16):
            page = pdf.pages[page_number - 1]
            footers = [w["top"] for w in page.extract_words() if w["text"].startswith("Fonte:")]
            if len(footers) != 1:
                raise ValueError(f"source footer missing/ambiguous on page {page_number}")
            page = page.crop((0, 0, page.width, footers[0] - 1))
            tables = page.extract_tables()
            if len(tables) != 1 or tables[0][0] != ["", "Faixa", "Artista", "Gravadora"]:
                raise ValueError(f"unexpected table/header on page {page_number}")
            for position, title, artist, label in tables[0][1:]:
                records.append(
                    dict(
                        country_code="BR",
                        year=2018,
                        platform="MULTIPLATFORM",
                        provider="PRO_MUSICA_BMAT",
                        period_start="2018-01-01",
                        period_end="2018-12-31",
                        position=int(position),
                        candidate_id=f"PRO_MUSICA:2018:{int(position)}",
                        title=clean(title),
                        artist=clean(artist),
                        label=clean(label),
                        source_page=page_number,
                        metric_value=None,
                        identity_status="local_chart_entry_pending_recording_review",
                    )
                )
    if [r["position"] for r in records] != list(range(1, 201)):
        raise ValueError("table does not contain positions 1-200 exactly")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = extract(args.pdf)
    result = verify_published_annual(
        records,
        country_code="BR",
        year=2018,
        platform="MULTIPLATFORM",
        provider="PRO_MUSICA_BMAT",
        quota=230,
        expected_depth=200,
        period_start="2018-01-01",
        period_end="2018-12-31",
    )
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "observations.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf8"
    )
    (args.output / "verification.json").write_text(
        json.dumps(
            {
                **result,
                "source_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
                "period_definition_review_pending": True,
                "recording_review_pending": True,
                "source_path": str(args.pdf),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    print(
        json.dumps(
            {
                "rows": len(records),
                "approved": result["approved"],
                "reasons": result["reasons"],
                "scientific_approval": False,
            }
        )
    )


if __name__ == "__main__":
    main()
