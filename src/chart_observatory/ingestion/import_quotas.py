"""Country/year quotas applied before lyrics acquisition, without replacements."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def apply_native_display_metadata(rows, resolutions):
    """Change display metadata only through an exact, hash-checked Spotify URI proof."""
    verified, documents = {}, {}
    for key, reference in resolutions.items():
        native = key.removeprefix("SPOTIFY:")
        if not key.startswith("SPOTIFY:"):
            raise ValueError("unsupported display metadata authority")
        document_key = reference["evidence_file"], reference["evidence_sha256"]
        if document_key not in documents:
            raw = Path(reference["evidence_file"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != reference["evidence_sha256"]:
                raise ValueError("native display metadata evidence hash mismatch")
            documents[document_key] = json.loads(raw)
        proof = documents[document_key]
        if reference.get("evidence_key"):
            proof = proof[reference["evidence_key"]]
        metadata = proof.get("metadata") or {}
        if (
            proof.get("status") != 200
            or proof.get("source_url") != f"https://open.spotify.com/embed/track/{native}"
            or metadata.get("uri") != f"spotify:track:{native}"
            or any(
                not isinstance(metadata.get(field), str) or not metadata[field].strip()
                for field in ("title", "artist")
            )
        ):
            raise ValueError("display metadata proof refers to another or unknown native track")
        verified[key] = metadata, reference
    for row in rows:
        if row["candidate_id"] not in verified:
            continue
        metadata, reference = verified[row["candidate_id"]]
        row.setdefault(
            "original_display_metadata", {field: row.get(field) for field in ("title", "artist")}
        )
        if row.get("metadata_resolution"):
            row["previous_metadata_resolution"] = row["metadata_resolution"]
        row.update(
            title=metadata["title"],
            artist=metadata["artist"],
            metadata_resolution=dict(
                basis="exact_native_uri_public_spotify_metadata",
                **reference,
                uri=metadata["uri"],
                recording_and_text_validation=False,
                **({"duration_ms": metadata["duration_ms"]}
                   if isinstance(metadata.get("duration_ms"), int)
                   and not isinstance(metadata["duration_ms"], bool)
                   and metadata["duration_ms"] > 0 else {}),
            ),
        )


def load_quotas(path: Path) -> dict[str, int]:
    quotas = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            country = row["country_code"]
            quota = int(row["quota_per_year_main"])
            if country in quotas or len(country) != 2 or not country.isupper():
                raise ValueError("duplicate or invalid quota country")
            if not 100 <= quota <= 500 or quota % 10:
                raise ValueError("quota must be a multiple of ten between 100 and 500")
            quotas[country] = quota
    if not quotas:
        raise ValueError("empty quota policy")
    return quotas


def select_quota_candidates(rankings, coverage, quotas, *, years=range(2018, 2027)):
    """Choose one complete platform per cell; Spotify wins a completeness tie.

    The caller supplies freshly aggregated ranks and audited calendar coverage.
    Calendar completeness alone does not certify chart depth or lyric identity.
    Incomplete cells remain empty, and missing lyrics never advance the boundary.
    """
    years = tuple(years)
    if any(type(year) is not int or not 2018 <= year <= 2026 for year in years):
        raise ValueError("new quota selections must stay within 2018–2026")
    sources, groups = {}, defaultdict(list)
    for row in coverage:
        key = row["country_code"], int(row["year"]), row["platform"]
        if key in sources:
            raise ValueError("multiple providers per cell: reconcile mirrored sources first")
        sources[key] = row
    for row in rankings:
        key = row["country_code"], int(row["year"]), row["platform"]
        if key[0] not in quotas or key[1] not in years:
            continue
        groups[key].append(row)
    selected, cells = [], []
    for country, quota in sorted(quotas.items()):
        for year in years:
            chosen = None
            for platform in ("SPOTIFY", "YOUTUBE"):
                key = country, year, platform
                source = sources.get(key, {})
                if (
                    source.get("coverage_status") == "COMPLETE"
                    and int(source.get("expected_periods", 0)) > 0
                    and int(source.get("collected_periods", 0)) == int(source["expected_periods"])
                ):
                    chosen = key
                    break
            rows = sorted(groups.get(chosen, []), key=lambda r: int(r["position"]))
            positions = [int(r["position"]) for r in rows]
            identities = [r["candidate_id"] for r in rows]
            if positions != list(range(1, len(rows) + 1)):
                raise ValueError("annual ranks must be unique and contiguous from one")
            if len(identities) != len(set(identities)):
                raise ValueError("duplicate candidate identity in annual ranking")
            if any(type(r["metric_value"]) is not int or r["metric_value"] < 0 for r in rows):
                raise ValueError("invalid annual metric")
            if any(
                a["metric_value"] < b["metric_value"] for a, b in zip(rows, rows[1:], strict=False)
            ):
                raise ValueError("annual ranking is not metric ordered")
            source = sources.get(chosen, {})
            if any(r.get("provider") != source.get("provider") for r in rows):
                raise ValueError("ranking and coverage providers differ")
            for row in rows[:quota]:
                selected.append({**row, "quota_main": quota, "not_for_paid_submission": True})
            cells.append(
                dict(
                    country_code=country,
                    year=year,
                    quota_main=quota,
                    platform=chosen[2] if chosen else None,
                    selected_items=min(len(rows), quota),
                    quota_shortfall=max(0, quota - len(rows)),
                    period_end=source.get("ranking_period_end"),
                    status=(
                        "NO_COMPLETE_CALENDAR"
                        if chosen is None
                        else "INSUFFICIENT_RANKING"
                        if len(rows) < quota
                        else "PARTIAL_YEAR"
                        if year == 2026
                        else "CALENDAR_ELIGIBLE"
                    ),
                )
            )
    return {"selections": selected, "coverage": cells}


def recovery_targets(selections):
    """Deduplicate platform candidates while retaining all territorial bindings.

    These are retrieval candidates, never confirmed recording/text identities.
    The existing recovery CLI accepts document_id, recording_id and chart_bindings.
    """
    tasks = {}
    for row in selections:
        key = row["candidate_id"]
        task = tasks.setdefault(
            key,
            dict(
                document_id=f"chart:{key}",
                recording_id=key,
                track_id=None,
                lyrics_hash="",
                title=row["title"],
                artist=row["artist"],
                cohort_version="country-year-quotas-20261030-v1",
                chart_bindings=[],
                identity_status="pending_recording_and_text_review",
                not_for_paid_submission=True,
            ),
        )
        if row.get("metadata_resolution"):
            task["metadata_resolution"] = row["metadata_resolution"]
        task["chart_bindings"].append(
            {k: row[k] for k in ("country_code", "year", "platform", "position", "quota_main")}
        )
        task["chart_bindings"][-1].update(
            ranking_metric_basis="sum_observed_chart_metrics",
            metric_type="STREAMS" if row["platform"] == "SPOTIFY" else "VIEWS",
        )
        if "metric_value" in row:
            task["chart_bindings"][-1]["metric_value"] = row["metric_value"]
        if row.get("original_display_metadata"):
            task["chart_bindings"][-1]["original_display_metadata"] = row[
                "original_display_metadata"
            ]
        for field in (
            "selection_status",
            "provider",
            "coverage_status",
            "collected_periods",
            "expected_periods",
        ):
            if field in row:
                task["chart_bindings"][-1][field] = row[field]
    return list(tasks.values())


def provisional_selection(rankings, coverage, quotas, definitive):
    """Observed Top N only where the definitive annual cell is absent.

    Conflicting/invalid sources are excluded even from provisional acquisition.
    No candidate below the quota replaces a song with missing lyrics.
    """
    finalized = {(r["country_code"], int(r["year"])) for r in definitive}
    groups = defaultdict(list)
    for row in rankings:
        groups[row["country_code"], int(row["year"]), row["platform"]].append(row)
    alternatives = defaultdict(list)
    for row in coverage:
        cell = row["country_code"], int(row["year"])
        key = (*cell, row["platform"])
        if (
            cell not in finalized
            and cell[0] in quotas
            and 2018 <= cell[1] <= 2026
            and row["coverage_status"] == "INCOMPLETE"
            and groups.get(key)
        ):
            alternatives[cell].append(row)
    selected = []
    for (country, year), sources in sorted(alternatives.items()):
        source = max(
            sources,
            key=lambda r: (
                int(r["collected_periods"]) / max(1, int(r["expected_periods"])),
                r["platform"] == "SPOTIFY",
                int(r.get("minimum_depth") or 0),
            ),
        )
        rows = sorted(groups[country, year, source["platform"]], key=lambda r: r["position"])
        if [r["position"] for r in rows] != list(range(1, len(rows) + 1)):
            raise ValueError("invalid provisional ranking")
        for row in rows[: quotas[country]]:
            selected.append(
                {
                    **row,
                    "quota_main": quotas[country],
                    "selection_status": "PROVISIONAL_OBSERVED_PERIODS",
                    "coverage_status": source["coverage_status"],
                    "collected_periods": int(source["collected_periods"]),
                    "expected_periods": int(source["expected_periods"]),
                    "not_for_paid_submission": True,
                }
            )
    return selected
