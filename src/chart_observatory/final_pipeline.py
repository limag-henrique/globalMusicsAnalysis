"""Three resumable operations over one catalog; never performs paid inference.

Historical selections and acquisition stores are read-only inputs. Texts remain
at their original content-addressed paths, avoiding another full corpus copy.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

import httpx
import pycountry
from bs4 import BeautifulSoup

VERSION = "final-pipeline-v1"
MAX_SONGS = 150_000


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(encode(value), encoding="utf-8")
    temporary.replace(path)


@contextmanager
def catalog(root):
    root.mkdir(parents=True, exist_ok=True)
    # OS lock is released even when a worker crashes; no stale lockfile repair.
    import msvcrt

    with (root / "owner.lock").open("a+b") as lock:
        lock.seek(0)
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("another final pipeline operation owns this catalog") from exc
        try:
            with closing(sqlite3.connect(root / "catalog.sqlite")) as db, db:
                db.row_factory = sqlite3.Row
                db.executescript("""
                    PRAGMA journal_mode=WAL;
                    CREATE TABLE IF NOT EXISTS songs(
                        id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                        result TEXT, attempts INTEGER NOT NULL DEFAULT 0);
                    CREATE TABLE IF NOT EXISTS memberships(
                        scope TEXT, country TEXT, period TEXT, platform TEXT,
                        rank INTEGER, song_id TEXT, payload TEXT,
                        PRIMARY KEY(scope,country,period,platform,rank));
                    CREATE TABLE IF NOT EXISTS selections(
                        path TEXT PRIMARY KEY, sha256 TEXT, summary TEXT);
                    CREATE TABLE IF NOT EXISTS charts(
                        country TEXT, platform TEXT, report TEXT,
                        PRIMARY KEY(country,platform));
                    CREATE TABLE IF NOT EXISTS prepared(
                        edition_id TEXT PRIMARY KEY, request_id TEXT, payload_sha256 TEXT);
                    CREATE TABLE IF NOT EXISTS replacement_ledger(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        song_id TEXT NOT NULL,
                        replaced_at TEXT NOT NULL,
                        old_text_sha256 TEXT,
                        new_text_sha256 TEXT,
                        old_result TEXT,
                        new_result TEXT,
                        reason TEXT NOT NULL,
                        old_score TEXT,
                        new_score TEXT);
                """)
                yield db
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def add_song(db, key, payload):
    db.execute("INSERT OR IGNORE INTO songs(id,payload) VALUES (?,?)", (key, encode(payload)))


def import_selection(db, selection):
    from chart_observatory.research_flow import load_selection

    manifest, _, members, hashes = load_selection(selection)
    scope = str(selection.resolve())
    manifest_hash = hashes[str(selection.resolve() / "manifest.json")]
    previous = db.execute("SELECT sha256 FROM selections WHERE path=?", (scope,)).fetchone()
    if previous and previous[0] != manifest_hash:
        raise ValueError("selection changed in place; use a new immutable selection directory")
    with db:
        for row in members:
            key = row["candidate_id"]
            add_song(db, key, row)
            db.execute(
                "INSERT OR IGNORE INTO memberships VALUES (?,?,?,?,?,?,?)",
                (
                    scope,
                    row["country_code"],
                    str(row["year"]),
                    row["platform"],
                    row["position"],
                    key,
                    digest(encode(row).encode()),
                ),
            )
        summary = dict(
            memberships=len(members),
            expected_positions=manifest["requested_positions"],
            missing_positions=manifest["requested_positions"] - len(members),
            cutoff=manifest["cutoff"],
            current_chart=False,
        )
        db.execute(
            "INSERT OR IGNORE INTO selections VALUES (?,?,?)",
            (scope, manifest_hash, encode(summary)),
        )
    return summary


def chart_links(html, platform):
    pattern = (
        r"https://kworb.net/spotify/country/([a-z]{2})_daily.html"
        if platform == "SPOTIFY"
        else r"https://kworb.net/youtube/insights/([a-z]{2}).html"
    )
    base = (
        "https://kworb.net/spotify/"
        if platform == "SPOTIFY"
        else "https://kworb.net/youtube/insights/"
    )
    result = {}
    for anchor in BeautifulSoup(html, "html.parser").select("a[href]"):
        url = urljoin(base, anchor["href"])
        match = re.fullmatch(pattern, url)
        if match and pycountry.countries.get(alpha_2=match[1].upper()):
            result[match[1].upper()] = url
    return result


def parse_chart(html, platform, *, today, top_n, max_age):
    page = BeautifulSoup(html, "html.parser")
    text = page.get_text(" ", strip=True)
    pattern = (
        r"Spotify Daily Chart.*? - (20\d{2}/\d{2}/\d{2})"
        if platform == "SPOTIFY"
        else r"Week ending (20\d{2}/\d{2}/\d{2})"
    )
    match = re.search(pattern, text)
    if not match:
        raise ValueError("chart has no explicit source date")
    period = date.fromisoformat(match[1].replace("/", "-"))
    if not 0 <= (today - period).days <= max_age:
        raise ValueError(f"stale or future chart: {period}")
    rows = []
    for tr in page.select("table tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 7:
            continue
        rank = int(cells[0].get_text(strip=True))
        if rank > top_n:
            continue
        native = None
        if platform == "SPOTIFY":
            title = cells[2].select_one('a[href*="/track/"]')
            artists = cells[2].select('a[href*="/artist/"]')
            if title is None or not artists:
                raise ValueError("missing Spotify native identity")
            native = title["href"].rsplit("/", 1)[-1].removesuffix(".html")
            title = title.get_text(" ", strip=True)
            artist = " | ".join(a.get_text(" ", strip=True) for a in artists)
        else:
            entry = cells[2].get_text(" ", strip=True)
            artist, separator, title = entry.partition(" - ")
            if not separator:
                raise ValueError("ambiguous YouTube title/artist boundary")
        if not title or not artist:
            raise ValueError("empty chart identity")
        rows.append(
            dict(
                position=rank,
                title=title,
                artist=artist,
                native_id=native,
                streams=int(cells[6].get_text(strip=True).replace(",", "")),
            )
        )
    if not rows or [r["position"] for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("missing or duplicate native ranking positions")
    return period.isoformat(), rows


def collect_rankings(db, root, config, *, countries=None, today=None):
    today = today or datetime.now(UTC).date()
    reports = []
    with httpx.Client(
        timeout=30, follow_redirects=True, headers={"User-Agent": "ChartObservatory/1.0 research"}
    ) as client:
        for platform in config["platforms"]:
            index_url = (
                "https://kworb.net/spotify/"
                if platform == "SPOTIFY"
                else "https://kworb.net/youtube/insights/"
            )
            try:
                index = client.get(index_url)
                index.raise_for_status()
                links = chart_links(index.text, platform)
            except (httpx.HTTPError, ValueError):
                links = {}
            requested = sorted(countries or {country.alpha_2 for country in pycountry.countries})
            for country in requested:
                n = config.get("country_top_n", {}).get(country, config["top_n"])
                report = dict(
                    country=country,
                    platform=platform,
                    requested_positions=n,
                    observed_positions=0,
                    status="source_unavailable",
                )
                if country in links:
                    try:
                        response = client.get(links[country])
                        response.raise_for_status()
                        period, rows = parse_chart(
                            response.text,
                            platform,
                            today=today,
                            top_n=n,
                            max_age=config["max_age_days"][platform],
                        )
                        raw_hash = digest(response.content)
                        raw = root / "chart-evidence" / f"{raw_hash}.html.gz"
                        raw.parent.mkdir(exist_ok=True)
                        if not raw.exists():
                            raw.write_bytes(gzip.compress(response.content, mtime=0))
                        report.update(
                            period=period,
                            source_url=str(response.url),
                            evidence=str(raw),
                            raw_sha256=raw_hash,
                            retrieved_at=datetime.now(UTC).isoformat(),
                            observed_positions=len(rows),
                            status="complete" if len(rows) == n else "partial",
                            kind="daily" if platform == "SPOTIFY" else "weekly",
                            provider="KWORB",
                            annual_ranking=False,
                        )
                        with db:
                            for row in rows:
                                # YouTube mirror lacks recording IDs. Keep this explicit;
                                # never merge with another platform by title/artist alone.
                                native = row["native_id"]
                                key = (
                                    f"SPOTIFY:{native}"
                                    if native
                                    else "YOUTUBE_UNRESOLVED:"
                                    + digest(encode([row["title"], row["artist"]]).encode())
                                )
                                payload = dict(
                                    row,
                                    platform=platform,
                                    provider="KWORB",
                                    country_code=country,
                                    native_id_available=bool(native),
                                )
                                add_song(db, key, payload)
                                db.execute(
                                    "INSERT OR REPLACE INTO memberships VALUES (?,?,?,?,?,?,?)",
                                    (
                                        "current",
                                        country,
                                        period,
                                        platform,
                                        row["position"],
                                        key,
                                        digest(encode(payload).encode()),
                                    ),
                                )
                    except (httpx.HTTPError, ValueError) as exc:
                        report.update(status="failed", error=str(exc))
                with db:
                    db.execute(
                        "INSERT OR REPLACE INTO charts VALUES (?,?,?)",
                        (country, platform, encode(report)),
                    )
                reports.append(report)
                if country in links:
                    print(encode(report), flush=True)
    return reports


def _native_ids_compatible(old, new):
    """Ensure two payloads do not refer to distinct native recording IDs."""
    for field in ("spotify_track_id", "recording_id"):
        a, b = old.get(field), new.get(field)
        if a and b and a != b:
            return False
    old_res = old.get("metadata_resolution") or {}
    new_res = new.get("metadata_resolution") or {}
    for field in ("spotify_track_id", "recording_id", "isrc"):
        a, b = old_res.get(field), new_res.get(field)
        if a and b and a != b:
            return False
    return True


def _merge_native_metadata(old, new):
    """Preserve existing native identity while filling missing metadata fields."""
    merged = dict(old)
    changed = False
    for key in ("duration_ms", "language_code"):
        if not merged.get(key) and new.get(key):
            merged[key] = new[key]
            changed = True
    if new.get("metadata_resolution"):
        old_res = dict(merged.get("metadata_resolution") or {})
        for k, v in new["metadata_resolution"].items():
            if not old_res.get(k) and v:
                old_res[k] = v
                changed = True
        if old_res:
            merged["metadata_resolution"] = old_res
    if new.get("chart_bindings") and not merged.get("chart_bindings"):
        merged["chart_bindings"] = new["chart_bindings"]
        changed = True
    return merged, changed


def _native_duration_match(native_ms, provider_seconds, native_identity_compatible):
    """Use duration only when both sides provide valid data for the verified native identity."""
    import math

    from chart_observatory.lyrics.text_quality import recording_duration_mismatch

    if not native_identity_compatible:
        return 0
    if (
        not isinstance(native_ms, int)
        or isinstance(native_ms, bool)
        or native_ms <= 0
        or not isinstance(provider_seconds, (int, float))
        or isinstance(provider_seconds, bool)
    ):
        return 0
    try:
        valid_provider_duration = math.isfinite(float(provider_seconds)) and provider_seconds > 0
    except (OverflowError, TypeError, ValueError):
        return 0
    return int(
        valid_provider_duration
        and not recording_duration_mismatch(native_ms, provider_seconds)
    )


def _score_result(
    payload, result, project, *, preloaded=None, native_identity_compatible=False
):
    """Score a result's evidence quality; higher tuple means strictly stronger proof."""
    try:
        check = validate_text(payload, result, project, preloaded=preloaded)
    except ValueError:
        return (0, 0, 0, 0, -999)
    ident_ok = check.get("identity", {}).get("status") == "passed"
    comp_ok = check.get("completeness", {}).get("status") == "passed"
    integ_ok = check.get("source_text_integrity", {}).get("status") == "passed"
    blockers = len(check.get("identity", {}).get("blocking_quality_flags") or []) + len(
        check.get("completeness", {}).get("blocking_quality_flags") or []
    )
    source_result = preloaded[0] if preloaded is not None else read_result(result, project)[0]
    native_duration = (payload.get("metadata_resolution") or {}).get("duration_ms")
    provider_duration = (source_result.get("source_metadata") or {}).get("duration_seconds")
    duration_match = _native_duration_match(
        native_duration, provider_duration, native_identity_compatible
    )
    return (
        int(ident_ok and comp_ok),
        int(ident_ok) + int(comp_ok),
        int(integ_ok),
        -blockers,
        duration_match,
    )


def _record_replacement(db, key, old_result, new_result, reason, old_score, new_score):
    db.execute(
        "INSERT INTO replacement_ledger("
        "song_id,replaced_at,old_text_sha256,new_text_sha256,"
        "old_result,new_result,reason,old_score,new_score) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            key,
            datetime.now(UTC).isoformat(),
            old_result.get("text_sha256"),
            new_result.get("text_sha256"),
            encode(old_result),
            encode(new_result),
            reason,
            encode(list(old_score)),
            encode(list(new_score)),
        ),
    )


def import_store(db, store, project):
    """Read a transactionally consistent live store; only reference verified bodies."""
    from chart_observatory.lyrics.quota_acquisition import identity
    from chart_observatory.lyrics.recovery_pipeline import (
        apply_native_proof_to_record,
        load_native_spotify_proofs,
    )

    imported = 0
    native_proofs = load_native_spotify_proofs(project)
    # Recording IDs must agree. No title/artist-only adoption from v1.
    with sqlite3.connect(
        (store / "acquisition.sqlite").resolve().as_uri() + "?mode=ro", uri=True
    ) as source:
        source.execute("BEGIN")
        for key, payload, raw in source.execute("SELECT identity,payload,result FROM tasks"):
            if not raw:
                continue
            target = db.execute("SELECT payload,result FROM songs WHERE id=?", (key,)).fetchone()
            if target is None:
                continue
            old, new, result = json.loads(target[0]), json.loads(payload), json.loads(raw)
            if any(identity(old.get(k)) != identity(new.get(k)) for k in ("title", "artist")):
                continue
            if not _native_ids_compatible(old, new):
                continue
            path = Path(result.get("text_path") or "__missing__").resolve()
            if not path.is_relative_to(project) or not path.is_file():
                continue
            if digest(path.read_bytes()) != result.get("text_sha256"):
                continue
            merged_payload, payload_changed = _merge_native_metadata(old, new)
            proof_payload = json.loads(encode(merged_payload))
            _native_ok, native_flags, native_ev = apply_native_proof_to_record(
                key, proof_payload, result, native_proofs
            )
            native_identity_compatible = bool(
                native_ev.get("native_proof_present")
                and not {
                    "native_title_disagreement",
                    "native_artist_disagreement",
                }.intersection(native_flags)
            )
            if native_identity_compatible:
                merged_payload = proof_payload
            if target[1]:
                old_result = json.loads(target[1])
                old_score = _score_result(
                    merged_payload,
                    old_result,
                    project,
                    native_identity_compatible=native_identity_compatible,
                )
                new_score = _score_result(
                    merged_payload,
                    result,
                    project,
                    native_identity_compatible=native_identity_compatible,
                )
                if new_score <= old_score:
                    if payload_changed:
                        with db:
                            db.execute(
                                "UPDATE songs SET payload=? WHERE id=?",
                                (encode(merged_payload), key),
                            )
                    continue
                reason = (
                    "same_text_store_evidence_enriched"
                    if old_result.get("text_sha256") == result.get("text_sha256")
                    else "store_evidence_improved"
                )
                with db:
                    _record_replacement(
                        db,
                        key,
                        old_result,
                        result,
                        reason,
                        old_score,
                        new_score,
                    )
                    db.execute(
                        "UPDATE songs SET payload=?, result=? WHERE id=?",
                        (encode(merged_payload), encode(result), key),
                    )
            else:
                with db:
                    db.execute(
                        "UPDATE songs SET payload=?, result=? WHERE id=?",
                        (encode(merged_payload), encode(result), key),
                    )
            imported += 1
    return imported


def import_staging(db, path, run_id, project):
    """Index an immutable staging run without copying its text or source results."""
    from chart_observatory.lyrics.quota_acquisition import identity
    from chart_observatory.lyrics.recovery_pipeline import (
        apply_native_proof_to_record,
        load_native_spotify_proofs,
    )

    path = path.resolve()
    if not path.is_relative_to(project):
        raise ValueError("staging input outside project")
    imported = 0
    native_proofs = load_native_spotify_proofs(project)
    ref_conns: dict[str, sqlite3.Connection] = {}
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
            source.execute("BEGIN")
            if not source.execute(
                "SELECT 1 FROM quota_lyric_staging_runs WHERE id=?", (run_id,)
            ).fetchone():
                raise ValueError("declared immutable staging run not found")
            with db:
                for key, payload, sha, body, sr_json, audit_json in source.execute(
                    "SELECT c.candidate_id,c.payload,c.text_sha256,b.body,c.source_result,c.audit "
                    "FROM quota_lyric_staging_candidates c JOIN quota_lyric_staging_blobs b "
                    "ON b.sha256=c.text_sha256 WHERE c.run_id=?",
                    (run_id,),
                ):
                    target = db.execute(
                        "SELECT payload,result FROM songs WHERE id=?", (key,)
                    ).fetchone()
                    if target is None:
                        continue
                    old, new = json.loads(target[0]), json.loads(payload)
                    if any(
                        identity(old.get(k)) != identity(new.get(k)) for k in ("title", "artist")
                    ):
                        continue
                    if not _native_ids_compatible(old, new):
                        continue
                    if digest(body.encode()) != sha:
                        raise ValueError("staging text hash mismatch")
                    merged_payload, payload_changed = _merge_native_metadata(old, new)
                    source_result = json.loads(sr_json)
                    proof_payload = json.loads(encode(merged_payload))
                    _native_ok, native_flags, native_ev = apply_native_proof_to_record(
                        key, proof_payload, source_result, native_proofs
                    )
                    native_identity_compatible = bool(
                        native_ev.get("native_proof_present")
                        and not {
                            "native_title_disagreement",
                            "native_artist_disagreement",
                        }.intersection(native_flags)
                    )
                    if native_identity_compatible:
                        merged_payload = proof_payload
                    result = dict(
                        text_sha256=sha,
                        staging_reference=dict(
                            database=str(path),
                            run_id=run_id,
                            candidate_id=key,
                        ),
                    )
                    if target[1]:
                        old_result = json.loads(target[1])
                        old_ref = old_result.get("staging_reference") or {}
                        if old_ref.get("run_id") == run_id and old_result.get("text_sha256") == sha:
                            if payload_changed:
                                db.execute(
                                    "UPDATE songs SET payload=? WHERE id=?",
                                    (encode(merged_payload), key),
                                )
                            continue
                        new_audit = json.loads(audit_json)
                        preloaded = (
                            dict(source_result, text_sha256=sha),
                            body,
                            new_audit,
                        )
                        old_score = _score_result(
                            merged_payload,
                            old_result,
                            project,
                            native_identity_compatible=native_identity_compatible,
                        )
                        new_score = _score_result(
                            merged_payload,
                            result,
                            project,
                            preloaded=preloaded,
                            native_identity_compatible=native_identity_compatible,
                        )
                        if new_score <= old_score:
                            if payload_changed:
                                db.execute(
                                    "UPDATE songs SET payload=? WHERE id=?",
                                    (encode(merged_payload), key),
                                )
                            continue
                        _record_replacement(
                            db,
                            key,
                            old_result,
                            result,
                            "staging_evidence_improved",
                            old_score,
                            new_score,
                        )
                    db.execute(
                        "UPDATE songs SET payload=?, result=? WHERE id=?",
                        (encode(merged_payload), encode(result), key),
                    )
                    imported += 1
    finally:
        for conn in ref_conns.values():
            conn.close()
    return imported


def read_result(result, project):
    """Resolve content-addressed file or exact immutable staging tuple, read only."""
    ref = result.get("staging_reference")
    if ref:
        path = Path(ref["database"]).resolve()
        if not path.is_relative_to(project):
            raise ValueError("staging reference outside project")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
            row = source.execute(
                "SELECT c.source_result,c.audit,c.text_sha256,b.body "
                "FROM quota_lyric_staging_candidates c JOIN quota_lyric_staging_blobs b "
                "ON b.sha256=c.text_sha256 WHERE c.run_id=? AND c.candidate_id=?",
                (ref["run_id"], ref["candidate_id"]),
            ).fetchone()
        if row is None or row[2] != result["text_sha256"] or digest(row[3].encode()) != row[2]:
            raise ValueError("immutable staging reference missing or changed")
        return dict(json.loads(row[0]), text_sha256=row[2]), row[3], json.loads(row[1])
    path = Path(result.get("text_path") or "__missing__").resolve()
    if not path.is_relative_to(project) or not path.is_file():
        return result, None, {}
    return result, path.read_text(encoding="utf-8"), {}


def validate_text(payload, result, project, *, preloaded=None):
    from chart_observatory.lyrics.automated_validation import assess_lyric_identity_completeness
    from chart_observatory.lyrics.language_identification import identify_language
    from chart_observatory.lyrics.quota_discovery import audit_saved_result
    from chart_observatory.lyrics.source_chain import verify_source_chain

    if preloaded is not None:
        result, text, saved_audit = preloaded
    else:
        result, text, saved_audit = read_result(result, project)
    if text is None:
        return dict(overall_status="pending_review", reason="no_local_text")
    chain = verify_source_chain(payload, result, text, result.get("text_sha256"), project)
    audit = audit_saved_result(payload, result)
    audit["text_quality_flags"] = sorted(
        set(audit.get("text_quality_flags") or [])
        | set(saved_audit.get("text_quality_flags") or [])
    )
    audit["source_quarantined"] = bool(
        audit.get("source_quarantined") or saved_audit.get("source_quarantined")
    )
    record = dict(
        payload=payload,
        source_result=result,
        text_sha256=result.get("text_sha256"),
        audit=audit,
    )
    assessment = assess_lyric_identity_completeness(record, text, chain)
    assessment["language_identification"] = identify_language(
        text, source_metadata=result.get("source_metadata")
    )
    return assessment


def population_order(selection):
    from chart_observatory.research_flow import load_selection

    selection = Path(selection).resolve()
    manifest, _, members, _ = load_selection(selection)
    allocation = json.loads((selection / "allocation-summary.json").read_text(encoding="utf-8"))
    country_order = {
        country: index for index, country in enumerate(allocation["priority_countries"])
    }
    priorities = {}
    for row in members:
        cid = row["candidate_id"]
        key = (country_order[row["country_code"]], row["position"], row["year"], cid)
        priorities[cid] = min(key, priorities.get(cid, key))
    return manifest, members, priorities


def acquire_lyrics(db, root, project, *, limit, retry=False, selection=None):
    from chart_observatory.lyrics.quota_acquisition import PacedHTTP
    from chart_observatory.lyrics.quota_discovery import recover_with_fallback

    if not 0 <= limit <= MAX_SONGS:
        raise ValueError(f"limit must be between 0 and {MAX_SONGS}")
    completed = 0
    if selection:
        _, _, priorities = population_order(selection)
        available = {
            row["id"]: row
            for row in db.execute("SELECT id,payload,result,attempts FROM songs")
            if row["id"] in priorities
        }
        rows = [available[cid] for cid in sorted(available, key=priorities.get)]
    else:
        rows = db.execute(
            "SELECT id,payload,result,attempts FROM songs WHERE attempts=0 OR ? ORDER BY id",
            (retry,),
        ).fetchall()
    with httpx.Client(timeout=25, follow_redirects=True) as client:
        http = PacedHTTP(root / "http-cache", client)
        for row in rows:
            if completed >= limit:
                break
            if row["attempts"] and not retry:
                continue
            payload = json.loads(row["payload"])
            old = json.loads(row["result"]) if row["result"] else {}
            validation = validate_text(payload, old, project)
            if (
                validation.get("identity", {}).get("status") == "passed"
                and validation.get("completeness", {}).get("status") == "passed"
            ):
                continue
            result = recover_with_fallback(
                payload["title"],
                payload["artist"],
                http,
                metadata_resolution=payload.get("metadata_resolution"),
            )
            text = result.pop("text", None)
            if text:
                sha = digest(text.encode())
                path = root / "texts" / f"{sha}.txt"
                path.parent.mkdir(exist_ok=True)
                if not path.exists():
                    path.write_bytes(text.encode())
                result.update(text_path=str(path.resolve()), text_sha256=sha)
            assessment = validate_text(payload, result, project)
            result["final_validation"] = assessment
            # A failed retry never displaces an existing transcription.
            if old:
                history = root / "attempts"
                history.mkdir(exist_ok=True)
                save(history / f"{uuid4()}.json", dict(song_id=row["id"], result=result))
            if not old or (
                assessment.get("identity", {}).get("status") == "passed"
                and assessment.get("completeness", {}).get("status") == "passed"
            ):
                with db:
                    db.execute("UPDATE songs SET result=? WHERE id=?", (encode(result), row["id"]))
            with db:
                db.execute("UPDATE songs SET attempts=attempts+1 WHERE id=?", (row["id"],))
            completed += 1
            print(
                encode(dict(song_id=row["id"], completed=completed, validation=assessment)),
                flush=True,
            )
    return completed


def prepare_vertex(db, root, project, *, audit=None, prepared=None):
    """Recheck existing scientific gates and stream at most 150k distinct editions.

    Existing prepared research requests carry the approved rubric and immutable
    model profile. The draft contract never becomes an executable request.
    """
    from chart_observatory import research_flow as flow
    from chart_observatory.lyrics.research_contract import write_contract_bundle
    from chart_observatory.lyrics.research_vertex_payload import vertex_payload

    output = root / "vertex" / uuid4().hex
    output.mkdir(parents=True)
    write_contract_bundle(output / "contract")
    report = dict(
        version=VERSION,
        max_songs=MAX_SONGS,
        monetary_budget_separate=True,
        currency_estimate=None,
        prepared_songs=0,
        reserved_total=int(db.execute("SELECT count(*) FROM prepared").fetchone()[0]),
        paid_calls=0,
        uploads=0,
        ready=False,
        output=str(output),
        reason="approved research audit and prepared requests required",
    )
    if audit is not None and prepared is not None:
        from uuid import UUID

        from chart_observatory.lyrics.classification_gate import ClassificationGate

        current = flow.require_research_stage(audit, "G3", project=project)
        allowed = set(current["canonical_state"])
        gate = ClassificationGate.load()
        # Stream into a temporary file; publish only after every row is checked.
        target = output / "requests.jsonl.tmp"
        with (audit / "preparatory-table.csv").open(encoding="utf-8-sig", newline="") as handle:
            allowed_requests = {
                (row["request_id"], row["document_id"])
                for row in csv.DictReader(handle)
                if row.get("prepared") == "True"
            }
        seen, staged = {}, []
        reserved = db.execute("SELECT count(*) FROM prepared").fetchone()[0]
        new_count = 0
        with prepared.open(encoding="utf-8") as source, target.open("x", encoding="utf-8") as dest:
            for line in source:
                request = json.loads(line)
                edition = request["edition_id"]
                if edition in seen:
                    if seen[edition] != request["request_id"]:
                        raise ValueError("conflicting requests for the same edition")
                    continue
                if edition not in allowed:
                    raise ValueError("prepared edition is outside approved canonical state")
                if (request["request_id"], edition) not in allowed_requests:
                    raise ValueError("request profile is outside approved audit")
                previous = db.execute(
                    "SELECT request_id FROM prepared WHERE edition_id=?", (edition,)
                ).fetchone()
                if previous and previous[0] != request["request_id"]:
                    raise ValueError("edition already frozen with a different request")
                if reserved + new_count >= MAX_SONGS and not previous:
                    break
                document = flow.read_canonical_documents(project, [UUID(edition)]).get(edition)
                if (
                    document is None
                    or not gate.assess(document).eligible
                    or flow.canonical_fingerprint(document) != current["canonical_state"][edition]
                    or digest((document.text or "").encode()) != request["text_sha256"]
                ):
                    raise ValueError("canonical text or eligibility changed")
                payload = vertex_payload(request)
                flow.require_vertex_rights(current, request, payload["dispatch_target"])
                # Official batch JSONL envelope; mapping stays in a separate file.
                dest.write(encode({"request": payload["request"]}) + "\n")
                staged.append(
                    (
                        edition,
                        request["request_id"],
                        digest(encode(payload).encode()),
                        bool(previous),
                    )
                )
                seen[edition] = request["request_id"]
                new_count += not previous
        with db:
            db.executemany(
                "INSERT OR IGNORE INTO prepared VALUES (?,?,?)", [entry[:3] for entry in staged]
            )
        target.replace(output / "requests.jsonl")
        save(
            output / "mapping.json",
            [dict(edition_id=e, request_id=r, payload_sha256=h) for e, r, h, _ in staged],
        )
        report.update(
            prepared_songs=len(staged),
            ready=bool(staged),
            reason="prepared locally; dispatch must recheck gates and campaign budget",
        )
    save(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["rankings", "lyrics", "vertex"])
    parser.add_argument("--root", type=Path, default=Path("data/runtime/final-pipeline"))
    parser.add_argument("--config", type=Path, default=Path("config/final_pipeline.json"))
    parser.add_argument("--selection", action="append", type=Path, default=[])
    parser.add_argument("--store", action="append", type=Path, default=[])
    parser.add_argument("--audit-limit", type=int, default=MAX_SONGS)
    parser.add_argument("--countries", help="Comma-separated ISO alpha-2 codes")
    parser.add_argument("--limit", type=int, default=MAX_SONGS)
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--materialize", action="store_true")
    args = parser.parse_args(argv)
    project = Path.cwd().resolve()
    root = args.root.resolve()
    if not root.is_relative_to(project / "data/runtime"):
        parser.error("root must remain inside project data/runtime")
    if not 0 <= args.limit <= MAX_SONGS:
        parser.error("limit must be between 0 and 150000")
    if not 0 <= args.audit_limit <= MAX_SONGS:
        parser.error("audit-limit must be between 0 and 150000")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if set(config["platforms"]) - {"SPOTIFY", "YOUTUBE"}:
        parser.error("unsupported current chart platform")
    for n in [config["top_n"], *config.get("country_top_n", {}).values()]:
        if type(n) is not int or not 1 <= n <= 500:
            parser.error("country ranking depth must be between 1 and 500")
    countries = set(args.countries.upper().split(",")) if args.countries else None
    if countries and any(pycountry.countries.get(alpha_2=c) is None for c in countries):
        parser.error("countries must be ISO alpha-2 codes")
    if (
        args.stage == "vertex"
        and config.get("automatic_preparation_authorized") is True
        and args.audit is None
        and args.prepared is None
    ):
        import sys

        sys.path.insert(0, str(project / "scripts"))
        from prepare_automatically_verified_vertex import main as automatic_vertex_main

        output = project / "data/runtime" / f"automatic-vertex-population-150k-{uuid4().hex}"
        forwarded = [
            "--verification",
            str(project / config["automatic_verification"]),
            "--selection",
            str(project / config["population_selection"]),
            "--output",
            str(output),
        ]
        if args.materialize:
            forwarded.append("--materialize")
        return automatic_vertex_main(forwarded)
    with catalog(root) as db:
        if args.stage == "rankings":
            selections = args.selection or [Path(p) for p in config.get("selections", [])]
            historical = {str(p): import_selection(db, p) for p in selections}
            reports = collect_rankings(db, root, config, countries=countries)
            result = dict(
                historical=historical,
                charts=reports,
                ready=bool(reports) and all(r["status"] == "complete" for r in reports),
            )
        elif args.stage == "lyrics":
            selection_path = project / config["population_selection"]
            population_manifest, _, population_priorities = population_order(selection_path)
            population_import = import_selection(db, selection_path)
            staging_reused = 0
            for staging in config.get("staging", []):
                staging_reused += import_staging(
                    db, Path(staging["database"]), staging["run_id"], project
                )
                print(encode(dict(staging=staging["run_id"], indexed=staging_reused)), flush=True)
            stores = args.store or [Path(p) for p in config.get("stores", [])]
            missing_stores = [str(p) for p in stores if not (p / "acquisition.sqlite").is_file()]
            reused = sum(
                import_store(db, p.resolve(), project)
                for p in stores
                if (p / "acquisition.sqlite").is_file()
            )
            count = acquire_lyrics(
                db,
                root,
                project,
                limit=args.limit,
                retry=args.retry,
                selection=selection_path,
            )
            counts = {
                "total": 0,
                "with_text": 0,
                "provider_integrity_passed": 0,
                "audited_texts": 0,
                "unaudited_texts": 0,
            }
            by_language = {}
            queue = root / "lyric-review-queue.jsonl.tmp"
            selected_ids = set(population_priorities)
            audit_rows = [
                row
                for row in db.execute("SELECT id,payload,result FROM songs")
                if row["id"] in selected_ids
            ]
            audit_rows.sort(key=lambda row: population_priorities[row["id"]])
            with queue.open("w", encoding="utf-8") as handle:
                for row in audit_rows:
                    result = json.loads(row["result"]) if row["result"] else {}
                    has_text = bool(result.get("text_sha256"))
                    if has_text and counts["audited_texts"] >= args.audit_limit:
                        counts["unaudited_texts"] += 1
                        assessment = dict(reason="not_audited_in_this_execution")
                    else:
                        assessment = validate_text(json.loads(row["payload"]), result, project)
                        counts["audited_texts"] += has_text
                        lang_info = assessment.get("language_identification")
                        if lang_info:
                            lang = lang_info.get("language_code", "und")
                            by_language[lang] = by_language.get(lang, 0) + 1
                    counts["total"] += 1
                    counts["with_text"] += bool(result.get("text_sha256"))
                    passed = (
                        assessment.get("identity", {}).get("status") == "passed"
                        and assessment.get("completeness", {}).get("status") == "passed"
                    )
                    counts["provider_integrity_passed"] += passed
                    if not passed:
                        handle.write(encode(dict(song_id=row["id"], assessment=assessment)) + "\n")
                    if counts["total"] % 1000 == 0:
                        print(encode(dict(progress=counts)), flush=True)
            queue.replace(root / "lyric-review-queue.jsonl")
            replacements_total = int(
                db.execute("SELECT count(*) FROM replacement_ledger").fetchone()[0]
            )
            result = dict(
                population_selection=config["population_selection"],
                total_position_budget=population_manifest["requested_positions"],
                selected_unique_songs=len(population_priorities),
                population_import=population_import,
                reused=reused,
                staging_reused=staging_reused,
                replacements_total=replacements_total,
                missing_stores=missing_stores,
                attempted=count,
                counts=counts,
                by_language=by_language,
                ready=counts["total"] > 0
                and counts["provider_integrity_passed"] == counts["total"],
                scientific_approval=False,
            )
        else:
            result = prepare_vertex(db, root, project, audit=args.audit, prepared=args.prepared)
        result.update(
            version=VERSION,
            stage=args.stage,
            config=config,
            implementation_sha256=digest(Path(__file__).read_bytes()),
            completed_at=datetime.now(UTC).isoformat(),
        )
        save(root / f"{args.stage}-report.json", result)
        print(encode(result), flush=True)
        return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
