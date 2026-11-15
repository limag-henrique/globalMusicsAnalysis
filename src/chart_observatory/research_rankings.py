"""Independent reconstruction of annual sums of metrics observed inside charts.

This verifier does not infer a platform-wide annual ranking from a censored chart.
Weekly observations belong to the year of their period end, including a week
whose beginning falls in the previous calendar year.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

RECONSTRUCTION_VERSION = "chart-observed-annual-sum-v2"


def verify_published_annual(
    observations: Iterable[dict],
    *,
    country_code: str,
    year: int,
    platform: str,
    provider: str,
    quota: int,
    expected_depth: int,
    period_start: str,
    period_end: str,
    cutoff: str = "2026-10-15",
) -> dict:
    """Validate an exact published list, without inventing stream metrics.

    The caller binds the preserved publication and its documented period to
    these rows. A technical pass never authenticates a source or a reviewer.
    """
    if type(year) is not int or type(quota) is not int or quota < 1:
        raise ValueError("invalid published annual year/quota")
    if type(expected_depth) is not int or expected_depth < 1:
        raise ValueError("invalid published annual depth")
    start, end, limit = _day(period_start), _day(period_end), _day(cutoff)
    if start > end or end > limit or start.year != year or end.year != year:
        raise ValueError("published annual period outside declared year/cutoff")
    reasons, by_position, candidates = [], {}, set()
    duplicates = 0
    for raw in observations:
        if not isinstance(raw, Mapping):
            reasons.append("invalid_published_row")
            continue
        if any(
            raw.get(k) != v
            for k, v in {
                "country_code": country_code,
                "year": year,
                "platform": platform,
                "provider": provider,
                "period_start": period_start,
                "period_end": period_end,
            }.items()
        ):
            reasons.append("published_row_scope_mismatch")
            continue
        position = raw.get("position")
        if type(position) is not int or not 1 <= position <= expected_depth:
            reasons.append("invalid_published_position")
            continue
        if any(
            not isinstance(raw.get(k), str) or not raw[k].strip()
            for k in ("candidate_id", "title", "artist")
        ):
            reasons.append("published_identity_missing")
            continue
        record = dict(raw)
        record.setdefault("metric_value", None)
        record.update(
            tie_group=[], selected=position <= quota, position_semantics="native_published_rank"
        )
        if position in by_position:
            if by_position[position] == record:
                duplicates += 1
            else:
                reasons.append("published_position_conflict")
            continue
        if record["candidate_id"] in candidates:
            reasons.append("published_candidate_repeated")
        if raw.get("tie_group") or raw.get("position_semantics") == "shared_rank":
            reasons.append("published_tie_unresolved")
        candidates.add(record["candidate_id"])
        by_position[position] = record
    if set(by_position) != set(range(1, expected_depth + 1)):
        reasons.append("incomplete_published_depth")
    if expected_depth < quota:
        reasons.append("published_depth_below_quota")
    return {
        "version": "published-annual-verification-v1",
        "approved": not reasons,
        "scientific_approval": False,
        "reasons": list(dict.fromkeys(reasons)),
        "country_code": country_code,
        "year": year,
        "platform": platform,
        "provider": provider,
        "quota": quota,
        "expected_depth": expected_depth,
        "period_start": period_start,
        "ranking_period_end": period_end,
        "counts": {"published_rows": len(by_position), "exact_duplicates": duplicates},
        "source_semantics": {"native_published_annual_rank": True, "synthetic_metrics": False},
        "rows": [by_position[p] for p in sorted(by_position)],
    }


def _day(value):
    if not isinstance(value, str):
        raise ValueError("explicit ISO date required")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("canonical ISO YYYY-MM-DD date required")
    return parsed


def _metric(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("invalid chart metric")
    try:
        result = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("invalid chart metric") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("metric must be finite and nonnegative")
    return result


def _schedule(year, cutoff, frequency, expected_period_ends):
    start, end = date(year, 1, 1), min(date(year, 12, 31), cutoff)
    reasons = []
    if end < start:
        return set(), ["year_after_cutoff"]
    if frequency == "daily":
        expected = {start + timedelta(days=i) for i in range((end - start).days + 1)}
        if expected_period_ends is not None:
            declared = {_day(value) for value in expected_period_ends}
            if declared != expected:
                reasons.append("daily_schedule_does_not_match_calendar")
        return expected, reasons
    if expected_period_ends is None:
        return set(), ["weekly_expected_period_ends_required"]
    declared = [_day(value) for value in expected_period_ends]
    expected = set(declared)
    ordered = sorted(expected)
    if len(expected) != len(declared):
        reasons.append("duplicate_expected_period_end")
    if not ordered or any(value < start or value > end for value in ordered):
        reasons.append("weekly_schedule_outside_window_or_empty")
    elif (
        (ordered[0] - start).days > 6
        or (end - ordered[-1]).days > 6
        or any((b - a).days != 7 for a, b in zip(ordered, ordered[1:], strict=False))
    ):
        reasons.append("weekly_schedule_does_not_cover_window")
    return expected, reasons


def reconstruct_chart_sum(
    observations: Iterable[dict],
    *,
    country_code: str,
    year: int,
    platform: str,
    provider: str,
    quota: int,
    cutoff: str = "2026-10-15",
    frequency: str = "daily",
    expected_depth: int = 200,
    expected_period_ends: Iterable[str] | None = None,
) -> dict:
    """Rebuild a single country's annual chart-observed sums without mixing sources.

    Observation fields: country_code, platform, provider, period_start, period_end,
    candidate_id, position, metric_value, title, artist. Dates are ISO YYYY-MM-DD;
    daily windows have equal start/end and weekly windows span exactly seven days.
    Rows for other countries, platforms, providers or years are ignored, never
    merged. ``metric_value`` accepts numeric values or decimal strings. Returned
    totals are decimal strings so evidence round trips without float rounding.

    All rows are diagnostic when approved=False. Boundary-tied rows have no rank
    or selected flag: a deterministic candidate-ID order is never tie evidence.
    """
    if type(year) is not int or not 1 <= year <= 9999:
        raise ValueError("invalid year")
    if type(quota) is not int or quota < 1:
        raise ValueError("quota must be a positive integer")
    if type(expected_depth) is not int or expected_depth < 1:
        raise ValueError("expected_depth must be a positive integer")
    if frequency not in {"daily", "weekly"}:
        raise ValueError("frequency must be daily or weekly")
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (country_code, platform, provider)
    ):
        raise ValueError("country, platform and provider are required")
    cutoff_date = _day(cutoff)
    expected, reasons = _schedule(year, cutoff_date, frequency, expected_period_ends)
    by_period = defaultdict(dict)
    positions = defaultdict(dict)
    invalid = conflicts = duplicates = ignored = matched = metadata_missing = 0
    diagnostics = Counter()
    titles = defaultdict(Counter)
    artists = defaultdict(Counter)
    for raw in observations:
        if not isinstance(raw, Mapping):
            invalid += 1
            diagnostics["observation_not_mapping"] += 1
            continue
        if any(
            raw.get(key) != value
            for key, value in (
                ("country_code", country_code),
                ("platform", platform),
                ("provider", provider),
            )
        ):
            ignored += 1
            continue
        try:
            end = _day(raw.get("period_end"))
            if end.year != year or end > cutoff_date:
                ignored += 1
                continue
            start = _day(raw.get("period_start"))
            if (end - start).days != (0 if frequency == "daily" else 6):
                raise ValueError("period length mismatch")
            candidate = raw.get("candidate_id")
            title, artist = raw.get("title"), raw.get("artist")
            if not isinstance(candidate, str) or not candidate.strip():
                raise ValueError("candidate identity required")
            # A missing display name does not remove a real chart position or
            # its metric. Identity/display review remains separate from sums.
            title = title if isinstance(title, str) and title.strip() else None
            artist = artist if isinstance(artist, str) and artist.strip() else None
            position = raw.get("position")
            if type(position) is not int or not 1 <= position <= expected_depth:
                raise ValueError("invalid native position")
            metric = _metric(raw.get("metric_value"))
        except (TypeError, ValueError):
            invalid += 1
            diagnostics["invalid_observation"] += 1
            continue
        matched += 1
        metadata_missing += title is None or artist is None
        normalized = (start, end, candidate, position, metric, title, artist)
        prior = by_period[end].get(candidate)
        if prior is not None:
            if prior == normalized:
                duplicates += 1
            else:
                conflicts += 1
                diagnostics["candidate_conflict_within_period"] += 1
            continue
        if position in positions[end]:
            conflicts += 1
            diagnostics["position_conflict_within_period"] += 1
            continue
        by_period[end][candidate] = normalized
        positions[end][position] = candidate
        if title is not None:
            titles[candidate][title] += 1
        if artist is not None:
            artists[candidate][artist] += 1

    actual = set(by_period)
    missing, unexpected = sorted(expected - actual), sorted(actual - expected)
    shallow = sorted(
        end for end in actual if set(positions[end]) != set(range(1, expected_depth + 1))
    )
    if invalid:
        reasons.append("invalid_observations")
    if conflicts:
        reasons.append("conflicting_observations")
    if missing:
        reasons.append("missing_periods")
    if unexpected:
        reasons.append("unexpected_periods")
    if shallow:
        reasons.append("incomplete_chart_depth")
    totals = defaultdict(Decimal)
    appearances = Counter()
    for period in by_period.values():
        for _, _, candidate, _, metric, _, _ in period.values():
            totals[candidate] += metric
            appearances[candidate] += 1
    ordered = sorted(totals, key=lambda candidate: (-totals[candidate], candidate))
    if len(ordered) < quota:
        reasons.append("insufficient_annual_candidates_for_quota")
    boundary_tie = bool(
        len(ordered) > quota and totals[ordered[quota - 1]] == totals[ordered[quota]]
    )
    boundary_metric = totals[ordered[quota - 1]] if boundary_tie else None
    if boundary_tie:
        reasons.append("unresolved_quota_boundary_tie")
    groups = defaultdict(list)
    for candidate in ordered:
        groups[totals[candidate]].append(candidate)
    rank_start = {}
    for index, candidate in enumerate(ordered, 1):
        rank_start.setdefault(totals[candidate], index)
    ranked = []
    for candidate in ordered:
        total = totals[candidate]
        first = rank_start[total]
        last = first + len(groups[total]) - 1
        tie = len(groups[total]) > 1
        unresolved = total == boundary_metric
        ranked.append(
            {
                "country_code": country_code,
                "year": year,
                "platform": platform,
                "provider": provider,
                "candidate_id": candidate,
                "title": min(
                    titles[candidate],
                    key=lambda value: (-titles[candidate][value], value),
                    default=None,
                ),
                "artist": min(
                    artists[candidate],
                    key=lambda value: (-artists[candidate][value], value),
                    default=None,
                ),
                "position": None if unresolved else first,
                "position_range": [first, last],
                "metric_value": format(total, "f"),
                "observed_periods": appearances[candidate],
                "tie_group": groups[total] if tie else [],
                "selected": None if unresolved else last <= quota,
                "position_semantics": "shared_rank" if tie else "unique_rank",
            }
        )
    return {
        "version": RECONSTRUCTION_VERSION,
        "approved": not reasons,
        "metadata_complete": metadata_missing == 0,
        "scientific_approval": False,
        "reasons": list(dict.fromkeys(reasons)),
        "country_code": country_code,
        "year": year,
        "platform": platform,
        "provider": provider,
        "quota": quota,
        "cutoff": cutoff,
        "ranking_period_end": min(date(year, 12, 31), cutoff_date).isoformat(),
        "partial_year": year == cutoff_date.year and cutoff_date < date(year, 12, 31),
        "frequency": frequency,
        "expected_depth": expected_depth,
        "source_semantics": {
            "metric": "sum_of_metrics_observed_while_inside_published_chart",
            "year_assignment": "period_end_year",
            "platform_wide_consumption": False,
            "native_published_annual_rank": False,
            "cross_provider_or_platform_sum": False,
        },
        "counts": {
            "matched_observations": matched,
            "ignored_observations": ignored,
            "exact_duplicates": duplicates,
            "invalid_observations": invalid,
            "missing_display_metadata_observations": metadata_missing,
            "conflicts": conflicts,
            "expected_periods": len(expected),
            "observed_periods": len(actual),
            "annual_candidates": len(ordered),
        },
        "diagnostics": dict(diagnostics),
        "missing_period_ends": [value.isoformat() for value in missing],
        "unexpected_period_ends": [value.isoformat() for value in unexpected],
        "incomplete_depth_period_ends": [value.isoformat() for value in shallow],
        "rows": ranked,
    }
