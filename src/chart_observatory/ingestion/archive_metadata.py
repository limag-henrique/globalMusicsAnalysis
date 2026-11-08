"""Exact-ID historical display metadata; never recording or lyrics adjudication."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


def kworb_display(html: str) -> dict[str, str]:
    page = BeautifulSoup(html, "html.parser")
    containers = [
        node
        for node in page.select("div.subcontainer")
        if node.find("span", class_="pagetitle", recursive=False)
    ]
    if len(containers) != 1:
        raise ValueError("ambiguous historical track page")
    container = containers[0]
    heading = container.find("span", class_="pagetitle", recursive=False)
    if heading is None or heading.get_text(" ", strip=True) != "Spotify Chart History":
        raise ValueError("not a Spotify track history")
    titles = []
    artists = []
    for child in container.children:
        if getattr(child, "name", None) == "div":
            break
        if not getattr(child, "name", None):
            titles.extend(re.findall(r"(?:^|\n)\s*Title:\s*([^\n]+)", str(child)))
        elif (
            isinstance(child, Tag)
            and child.name == "a"
            and re.fullmatch(r"\.\./artist/[A-Za-z0-9]{22}\.html", str(child.get("href", "")))
        ):
            artists.append(child.get_text(" ", strip=True))
    if len(titles) != 1 or not titles[0].strip() or not artists or not all(artists):
        raise ValueError("missing or ambiguous title/artist")
    title = titles[0].strip()
    if page.title is None or not page.title.get_text().endswith(
        f" - {title} - Spotify Chart History"
    ):
        raise ValueError("historical title representations disagree")
    return dict(title=title, artist=" | ".join(artists))


def archive_proof(candidate_id: str, reference: dict[str, Any]) -> dict[str, str]:
    native = candidate_id.removeprefix("SPOTIFY:")
    if not candidate_id.startswith("SPOTIFY:") or not re.fullmatch(r"[A-Za-z0-9]{22}", native):
        raise ValueError("invalid Spotify candidate")
    expected = f"https://kworb.net/spotify/track/{native}.html"
    if (
        reference.get("source_url") != expected
        or reference.get("response_url") != expected
        or reference.get("http_status") != 200
        or reference.get("native_id") != native
    ):
        raise ValueError("archive proof belongs to another native ID or source")
    raw = Path(reference["evidence_file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference["evidence_sha256"]:
        raise ValueError("archive evidence hash mismatch")
    return kworb_display(raw.decode("utf-8"))


def apply_archive_repairs(rows: list[dict[str, Any]], references: dict[str, Any]) -> int:
    """Fill missing display fields only; preserve existing complete names and ranks."""
    known = {key: archive_proof(key, proof) for key, proof in references.items()}
    planned = []

    def present(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    for row in rows:
        key = row["candidate_id"]
        if key not in known or (present(row.get("title")) and present(row.get("artist"))):
            continue
        metadata = known[key]
        for field in ("title", "artist"):
            if present(row.get(field)) and row[field] != metadata[field]:
                raise ValueError("archive conflicts with existing display metadata")
        planned.append((row, key, metadata))
    for row, key, metadata in planned:
        row.setdefault("original_display_metadata", {k: row.get(k) for k in ("title", "artist")})
        row.update(
            title=metadata["title"],
            artist=metadata["artist"],
            metadata_resolution=dict(
                basis="exact_native_id_historical_kworb_archive",
                **references[key],
                uri=f"spotify:track:{key.removeprefix('SPOTIFY:')}",
                display_metadata_complete=True,
                recording_and_text_validation=False,
            ),
        )
        if row.get("identity_status") == "metadata_missing":
            row["metadata_resolution"]["source_identity_status"] = "metadata_missing"
            row["identity_status"] = "native_id_pending_recording_review"
    return len(planned)
