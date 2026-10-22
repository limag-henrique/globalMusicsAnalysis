"""Cheap HTML-only supplement for article markets without YouTube charts.

This collects the explicitly dated current daily chart, not an annual ranking.
"""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, SoupStrainer
from scrape_youtube_chart_titles import OUTPUT, save_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", default="AD,BG,GR,LT,LV,MA,SK")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    wanted = set(args.countries.split(","))
    args.output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        trust_env=False, timeout=20, follow_redirects=True, limits=httpx.Limits(max_connections=2)
    ) as client:
        index = client.get("https://kworb.net/spotify/")
        index.raise_for_status()
        links = BeautifulSoup(index.text, "html.parser", parse_only=SoupStrainer("a"))
        urls = {}
        for a in links.select("a[href]"):
            url = urljoin(str(index.url), a["href"])
            match = re.fullmatch(r"https://kworb.net/spotify/country/([a-z]{2})_daily.html", url)
            if match and match[1].upper() in wanted:
                urls[match[1].upper()] = url

        def collect(pair):
            country, url = pair
            response = client.get(url)
            if response.status_code == 404:
                return {"country": country, "status": "NO_CURRENT_CHART", "url": url}
            response.raise_for_status()
            period = re.search(r"Spotify Daily Chart[^\n]*?(\d{4}/\d{2}/\d{2})", response.text)
            if not period:
                raise ValueError(f"missing source date for {country}")
            day = datetime.strptime(period[1], "%Y/%m/%d").date().isoformat()
            table = BeautifulSoup(
                response.text, "html.parser", parse_only=SoupStrainer("table", id="spotifydaily")
            )
            rows = []
            for tr in table.select("tr"):
                title = tr.select_one('a[href*="/track/"]')
                cells = tr.find_all("td", recursive=False)
                if title is None or not cells:
                    continue
                artists = [a.get_text(" ", strip=True) for a in tr.select('a[href*="/artist/"]')]
                native = str(title.get("href")).rsplit("/", 1)[-1].removesuffix(".html")
                rows.append(
                    {
                        "rank": int(cells[0].get_text(strip=True)),
                        "title": title.get_text(" ", strip=True),
                        "artist": ", ".join(artists),
                        "native_id": native,
                    }
                )
            _, count = save_capture(
                {
                    "provider": "KWORB_SPOTIFY_WEB",
                    "country_code": country,
                    "source_url": url,
                    "period_start": day,
                    "period_end": day,
                    "rows": rows,
                },
                args.output,
            )
            return {"country": country, "date": day, "titles": count}

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(collect, sorted(urls.items())))
    print(
        json.dumps(
            {
                "snapshots": results,
                "unavailable": sorted(wanted - urls.keys()),
                "coverage_type": "DATED_CURRENT_SNAPSHOT_NOT_ANNUAL",
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
