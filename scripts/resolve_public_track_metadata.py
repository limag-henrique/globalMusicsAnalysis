"""Resolve only exact Spotify IDs using public Spotify metadata or MusicBrainz URL links."""

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/audited-calendars-2018-2026-20261031"
CACHE = ROOT / "data/raw/metadata_resolution/20261031"


def kworb_metadata(html):
    page = BeautifulSoup(html, "html.parser")
    container = next(
        (
            node
            for node in page.select("div.subcontainer")
            if node.find("span", class_="pagetitle", recursive=False)
        ),
        None,
    )
    if not container:
        return None
    title = None
    for child in container.children:
        if getattr(child, "name", None) == "div":
            break
        if not getattr(child, "name", None):
            match = re.search(r"(?:^|\n)\s*Title:\s*([^\n]+)", str(child))
            if match:
                title = match[1].strip()
                break
    artists = [
        node.get_text(" ", strip=True)
        for node in container.find_all("a", recursive=False)
        if re.fullmatch(r"\.\./artist/[A-Za-z0-9]{22}\.html", str(node.get("href", "")))
    ]
    if not title or not artists or not all(artists):
        return None
    return dict(title=title, artist=" | ".join(artists))


def spotify_entity(html, native):
    script = BeautifulSoup(html, "html.parser").select_one("script#__NEXT_DATA__")
    if not script:
        return None
    data = json.loads(script.string or script.get_text())
    entity = (
        data.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("data", {})
        .get("entity", {})
    )
    if entity.get("uri") != f"spotify:track:{native}" or entity.get("type") != "track":
        return None
    title = entity.get("title") or entity.get("name")
    artists = [r.get("name") for r in entity.get("artists", []) if isinstance(r, dict)]
    if not isinstance(title, str) or not title.strip() or not artists or not all(artists):
        return None
    # Never persist the embed session/access token or other page settings.
    return dict(title=title, artist=" | ".join(artists), uri=entity["uri"])


def resolve(limit=None):
    path = BASE / "metadata-enrichment.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    CACHE.mkdir(parents=True, exist_ok=True)
    last_mb = 0.0
    completed = 0
    with httpx.Client(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "ChartObservatoryResearch/0.1 (music metadata study)"},
    ) as client:

        def mb_get(url, params):
            nonlocal last_mb
            time.sleep(max(0, 1.1 - (time.monotonic() - last_mb)))
            last_mb = time.monotonic()
            return client.get(url, params=params)

        for key in list(data.get("unresolved", [])):
            if limit is not None and completed >= limit:
                break
            native = key.removeprefix("SPOTIFY:")
            cached = CACHE / f"{native}.json"
            if cached.exists():
                record = json.loads(cached.read_text(encoding="utf-8"))
            else:
                record = dict(
                    native_id=native,
                    retrieved_at=datetime.now(UTC).isoformat(),
                    evidence=[],
                    status="unresolved",
                )
                embed = f"https://open.spotify.com/embed/track/{native}"
                try:
                    response = client.get(embed)
                    record["evidence"].append(
                        dict(
                            source="SPOTIFY_PUBLIC_EMBED",
                            url=embed,
                            http_status=response.status_code,
                            response_sha256=hashlib.sha256(response.content).hexdigest(),
                        )
                    )
                    entity = (
                        spotify_entity(response.text, native)
                        if response.status_code == 200
                        else None
                    )
                    if entity:
                        record.update(
                            status="resolved",
                            title=entity["title"],
                            artist=entity["artist"],
                            basis="exact_native_uri_public_spotify",
                        )
                except (httpx.HTTPError, ValueError, AttributeError) as exc:
                    record["evidence"].append(
                        dict(source="SPOTIFY_PUBLIC_EMBED", error=type(exc).__name__)
                    )
                if record["status"] != "resolved":
                    resource = f"https://open.spotify.com/track/{native}"
                    try:
                        response = mb_get(
                            "https://musicbrainz.org/ws/2/url/",
                            dict(resource=resource, inc="recording-rels", fmt="json"),
                        )
                        record["evidence"].append(
                            dict(
                                source="MUSICBRAINZ_URL",
                                url=str(response.url),
                                http_status=response.status_code,
                            )
                        )
                        payload = response.json() if response.status_code == 200 else {}
                        relations = (
                            payload.get("relations", [])
                            if payload.get("resource") == resource
                            else []
                        )
                        recordings = {
                            r["recording"]["id"]
                            for r in relations
                            if isinstance(r, dict)
                            and isinstance(r.get("recording"), dict)
                            and r["recording"].get("id")
                        }
                        if len(recordings) == 1:
                            mbid = next(iter(recordings))
                            response = mb_get(
                                f"https://musicbrainz.org/ws/2/recording/{mbid}",
                                dict(inc="artist-credits", fmt="json"),
                            )
                            payload = response.json() if response.status_code == 200 else {}
                            names = [
                                r.get("artist", {}).get("name")
                                for r in payload.get("artist-credit", [])
                                if isinstance(r, dict)
                            ]
                            if payload.get("title") and names and all(names):
                                record.update(
                                    status="resolved",
                                    title=payload["title"],
                                    artist=" | ".join(names),
                                    basis="exact_spotify_url_musicbrainz_recording",
                                    musicbrainz_recording_id=mbid,
                                )
                        elif len(recordings) > 1:
                            record["status"] = "ambiguous_recording_links"
                    except (httpx.HTTPError, ValueError, AttributeError) as exc:
                        record["evidence"].append(
                            dict(source="MUSICBRAINZ_URL", error=type(exc).__name__)
                        )
                cached.write_text(
                    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                time.sleep(0.6)
            if record["status"] != "resolved":
                kworb_cache = CACHE / f"{native}-kworb.json"
                if (
                    kworb_cache.exists()
                    and json.loads(kworb_cache.read_text(encoding="utf-8")).get("parser_version")
                    == 2
                ):
                    kworb_record = json.loads(kworb_cache.read_text(encoding="utf-8"))
                else:
                    url = f"https://kworb.net/spotify/track/{native}.html"
                    kworb_record = dict(status="unresolved", evidence=[], parser_version=2)
                    try:
                        response = client.get(url)
                        evidence = dict(
                            source="KWORB_ARCHIVE",
                            url=url,
                            retrieved_at=datetime.now(UTC).isoformat(),
                            http_status=response.status_code,
                            response_sha256=hashlib.sha256(response.content).hexdigest(),
                        )
                        kworb_record["evidence"].append(evidence)
                        if (
                            response.status_code == 200
                            and urlparse(str(response.url)).hostname == "kworb.net"
                            and urlparse(str(response.url)).path == f"/spotify/track/{native}.html"
                        ):
                            raw = CACHE / f"{native}-kworb.html"
                            raw.write_bytes(response.content)
                            evidence["raw_artifact"] = str(raw)
                            metadata = kworb_metadata(response.text)
                            if metadata:
                                kworb_record.update(
                                    metadata,
                                    status="resolved",
                                    basis="exact_spotify_id_kworb_archive",
                                )
                    except httpx.HTTPError as exc:
                        kworb_record["evidence"].append(
                            dict(source="KWORB_ARCHIVE", error=type(exc).__name__)
                        )
                    kworb_cache.write_text(
                        json.dumps(kworb_record, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    time.sleep(0.6)
                    if any(e.get("http_status") in (403, 429) for e in kworb_record["evidence"]):
                        print(
                            json.dumps(dict(status="provider_access_paused", source="KWORB")),
                            flush=True,
                        )
                        break
                if kworb_record["status"] == "resolved":
                    record = {
                        **kworb_record,
                        "evidence": record["evidence"] + kworb_record["evidence"],
                    }
            if record["status"] == "resolved":
                data["resolved"][key] = dict(
                    title=record["title"],
                    artist=record["artist"],
                    basis=record["basis"],
                    evidence=record["evidence"],
                    recording_and_text_validation=False,
                )
                data["unresolved"].remove(key)
            completed += 1
            temporary = path.with_suffix(".part")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
            print(
                json.dumps(
                    dict(identity=key, status=record["status"], unresolved=len(data["unresolved"]))
                ),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    resolve(args.limit)
