"""Extract preserved Official Charts annual pages into noncanonical evidence."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from chart_observatory.research_rankings import verify_published_annual


def extract(content, year):
    soup = BeautifulSoup(content, "html.parser")
    heading = soup.find("h1")
    if not heading or "End of Year Singles Chart" not in heading.get_text():
        raise ValueError("not an annual singles publication")
    if str(year) not in heading.get_text():
        raise ValueError("publication year differs")
    rows = []
    for item in soup.select(".chart-item-content"):
        title = item.select_one("a.chart-name")
        artist = item.select_one("a.chart-artist")
        position = item.select_one(".position")
        if not title or not artist or not position:
            raise ValueError("incomplete chart entry")
        spans = title.find_all("span", recursive=False)
        text = [s.get_text(" ", strip=True) for s in spans if not s.get("class")]
        if len(text) != 1:
            raise ValueError("ambiguous title markup")
        rows.append(
            dict(
                country_code="GB",
                year=year,
                platform="NATIONAL",
                provider="OFFICIAL_CHARTS",
                period_start=f"{year}-01-01",
                period_end=f"{year}-12-31",
                position=int(re.sub(r"\D", "", position.get_text())),
                candidate_id="OFFICIAL_CHARTS:" + title["href"],
                title=text[0],
                artist=artist.get_text(" ", strip=True),
                metric_value=None,
                identity_status="chart_entry_pending_recording_review",
            )
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--quota", type=int, required=True)
    args = parser.parse_args()
    content = args.html.read_bytes()
    rows = extract(content, args.year)
    result = verify_published_annual(
        rows,
        country_code="GB",
        year=args.year,
        platform="NATIONAL",
        provider="OFFICIAL_CHARTS",
        quota=args.quota,
        expected_depth=100,
        period_start=f"{args.year}-01-01",
        period_end=f"{args.year}-12-31",
    )
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "observations.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf8"
    )
    (args.output / "verification.json").write_text(
        json.dumps(
            {
                **result,
                "source_sha256": hashlib.sha256(content).hexdigest(),
                "source_path": str(args.html),
                "scientific_approval": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    print(
        json.dumps(
            {
                "rows": len(rows),
                "quota": args.quota,
                "approved": result["approved"],
                "reasons": result["reasons"],
                "scientific_approval": False,
            }
        )
    )


if __name__ == "__main__":
    main()
