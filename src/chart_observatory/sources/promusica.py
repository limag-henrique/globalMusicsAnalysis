from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from chart_observatory.sources.models import SourceObservation

DOMAIN = "pro-musicabr.org.br"
_KEYWORDS = re.compile(r"chart|streaming|top|ranking|m[eê]s|ano|pdf|xls|csv", re.I)


@dataclass(frozen=True)
class ProMusicaInventoryItem:
    url: str
    title: str
    publication_date: date | None
    detected_period: str | None
    format: str
    chart_type: str | None
    downloadable: bool
    parsed: bool = False
    checksum: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ProMusicaDateReview:
    status: str
    start_date: date
    end_date: date
    reason: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


class ProMusicaHtmlParser:
    def parse(
        self,
        raw_html: str,
        *,
        period: date,
        chart_type: str = "TOP_50_STREAMING",
        source_document: str = "",
    ) -> tuple[SourceObservation, ...]:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", raw_html, flags=re.I | re.S)
        observations: list[SourceObservation] = []
        for row_number, row_html in enumerate(rows, start=1):
            cells = [
                html.unescape(re.sub(r"<[^>]+>", "", value)).strip()
                for value in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.I | re.S)
            ]
            if len(cells) < 3:
                continue
            try:
                rank = int(re.sub(r"\D", "", cells[0]))
            except ValueError:
                continue
            artist = cells[2]
            track = cells[1]
            if not track:
                parts = [part.strip() for part in artist.splitlines() if part.strip()]
                artist = parts[0] if parts else ""
                track = parts[-1] if len(parts) > 1 else ""
            observations.append(
                SourceObservation(
                    provider="PRO_MUSICA_BRASIL",
                    origin_platform="MULTI_PLATFORM_AGGREGATE",
                    country_code="BR",
                    chart_name=chart_type,
                    period_start=period,
                    period_end=period,
                    rank=rank,
                    track_title=track,
                    artist=artist,
                    metric_type=None,
                    source_artifact=source_document,
                    source_row_number=row_number,
                    raw_fields={"cells": cells},
                )
            )
        return tuple(observations)


def period_from_html(raw_html: str, fallback: date) -> date:
    """Read the chart's displayed Portuguese month/year, retaining a safe fallback."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
    months = {
        "janeiro": 1,
        "fevereiro": 2,
        "março": 3,
        "marco": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }
    match = re.search(
        r"(" + "|".join(months) + r")\s+(?:de\s+)?(20\d{2})", text, flags=re.IGNORECASE
    )
    if not match:
        return fallback
    return date(int(match.group(2)), months[match.group(1).casefold()], 1)


class ProMusicaCsvParser:
    def parse(
        self, raw: bytes, *, period: date, source_document: str = ""
    ) -> tuple[SourceObservation, ...]:
        rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        result = []
        for number, row in enumerate(rows, start=2):
            rank = int(row.get("rank", row.get("Rank", "0")))
            result.append(
                SourceObservation(
                    provider="PRO_MUSICA_BRASIL",
                    origin_platform="MULTI_PLATFORM_AGGREGATE",
                    country_code="BR",
                    chart_name="TOP_50_STREAMING",
                    period_start=period,
                    period_end=period,
                    rank=rank,
                    track_title=row.get("track", row.get("Track", "")),
                    artist=row.get("artist", row.get("Artist", "")),
                    source_artifact=source_document,
                    source_row_number=number,
                    raw_fields=dict(row),
                )
            )
        return tuple(result)


class ProMusicaPdfParser:
    def parse(self, _raw: bytes, **_: object) -> tuple[SourceObservation, ...]:
        raise RuntimeError("PDF parser requires a text layer or an explicitly added PDF dependency")


class ProMusicaExcelParser:
    def parse(self, _raw: bytes, **_: object) -> tuple[SourceObservation, ...]:
        raise RuntimeError("Excel parser requires an explicitly configured spreadsheet dependency")


class ProMusicaBrasilSource:
    provider = "PRO_MUSICA_BRASIL"
    origin_platform = "MULTI_PLATFORM_AGGREGATE"

    def __init__(self, base_url: str = "https://pro-musicabr.org.br/") -> None:
        self.base_url = base_url

    @staticmethod
    def review_period(start_date: date, end_date: date) -> ProMusicaDateReview:
        if start_date > end_date:
            return ProMusicaDateReview(
                "CONFIGURATION_REQUIRES_REVIEW",
                start_date,
                end_date,
                "The configured start date is later than the configured end date; "
                "no silent correction was applied.",
            )
        return ProMusicaDateReview("VALID", start_date, end_date, "")

    def inventory_from_html(self, raw_html: str) -> tuple[ProMusicaInventoryItem, ...]:
        parser = _LinkParser()
        parser.feed(raw_html)
        items: list[ProMusicaInventoryItem] = []
        seen: set[str] = set()
        for href, title in parser.links:
            url = urljoin(self.base_url, href)
            parsed = urlparse(url)
            if parsed.netloc.casefold().removeprefix("www.") != DOMAIN:
                continue
            if url in seen or not _KEYWORDS.search(f"{url} {title}"):
                continue
            seen.add(url)
            extension = Path(parsed.path).suffix.casefold().removeprefix(".")
            file_format = extension.upper() if extension else "HTML"
            chart_type = (
                "TOP_50_STREAMING"
                if re.search(r"top.?50|streaming", f"{url} {title}", re.I)
                else None
            )
            items.append(
                ProMusicaInventoryItem(
                    url=url,
                    title=title or url,
                    publication_date=None,
                    detected_period=_detect_period(f"{url} {title}"),
                    format=file_format,
                    chart_type=chart_type,
                    downloadable=extension in {"pdf", "xls", "xlsx", "csv"},
                )
            )
        return tuple(items)

    def write_inventory(self, items: tuple[ProMusicaInventoryItem, ...], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "url",
            "title",
            "publication_date",
            "detected_period",
            "format",
            "chart_type",
            "downloadable",
            "parsed",
            "checksum",
            "notes",
        ]
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for item in items:
                writer.writerow({field: getattr(item, field) for field in fields})
        return output_path

    def store_artifact(
        self, raw: bytes, url: str, output_root: Path, retrieved_at: datetime
    ) -> Path:
        digest = hashlib.sha256(raw).hexdigest()
        parsed = urlparse(url)
        if parsed.netloc.casefold().removeprefix("www.") != DOMAIN:
            raise ValueError("Pro-Música artifact must come from the official domain")
        filename = Path(parsed.path).name or "index.html"
        destination = output_root / str(retrieved_at.year) / f"{retrieved_at.month:02d}" / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            destination = destination.with_name(
                f"{destination.stem}-{digest[:12]}{destination.suffix}"
            )
        if not destination.exists():
            destination.write_bytes(raw)
        metadata = destination.with_suffix(destination.suffix + ".json")
        metadata.write_text(
            json.dumps(
                {
                    "url": url,
                    "retrieved_at": retrieved_at.isoformat(),
                    "sha256": digest,
                    "byte_size": len(raw),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return destination


def _detect_period(value: str) -> str | None:
    match = re.search(r"(20\d{2})[-_/](0?[1-9]|1[0-2])", value)
    return f"{match.group(1)}-{int(match.group(2)):02d}" if match else None
