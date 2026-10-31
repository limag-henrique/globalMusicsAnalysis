"""Audit observed calendars and rebuild annual ranks without mixing providers."""

from datetime import date, timedelta

import polars as pl


def integer_metric(column):
    """Parse integer-valued decimal CSV strings without floating-point rounding."""
    value = pl.col(column).str.strip_chars()
    return (
        pl.when(value.str.contains(r"^[+-]?\d+(?:\.0+)?$"))
        .then(value.str.replace(r"\.0+$", "").cast(pl.Int64, strict=False))
        .otherwise(None)
    )


def archive_overlap_agrees(primary, auxiliary):
    """Check an auxiliary archive without letting its omissions truncate primary days."""
    overlap = primary.keys() & auxiliary.keys()
    exact = [day for day in overlap if primary[day] == auxiliary[day] and auxiliary[day]]
    incompatible = [
        day
        for day in overlap
        if not auxiliary[day]
        or not auxiliary[day].keys() <= primary[day].keys()
        or any(primary[day][key] != value for key, value in auxiliary[day].items())
    ]
    return dict(
        compatible=bool(exact) and not incompatible,
        exact_overlap_days=len(exact),
        subset_overlap_days=len(overlap) - len(exact) - len(incompatible),
        incompatible_dates=sorted(map(str, incompatible)),
    )


def required_dates(year, cutoff, frequency):
    stop = min(date(year, 12, 31), cutoff)
    day, required = date(year, 1, 1), set()
    while day <= stop:
        if frequency == "DAILY" or day.weekday() == 3:
            required.add(day)
        day += timedelta(days=1)
    return required


def annual_ranks(frame, *, markets, year, cutoff, frequency, platform, provider):
    """Audit one year of normalized rows; identical repeated item/periods count once.

    Conflicting metrics or missing native IDs make the affected cell ineligible.
    Missing display metadata is tracked separately and never changes stream sums.
    Weekly boundary periods use their native end year; 2026 stays partial.
    """
    expected = required_dates(year, cutoff, frequency)
    frame = frame.filter(pl.col("period_end").is_in(sorted(expected)))
    rankings, coverage = [], []
    for (country,), records in frame.partition_by("country_code", as_dict=True).items():
        if country not in markets:
            continue
        invalid = records.filter(
            pl.col("metric_value").is_null()
            | (pl.col("metric_value") < 0)
            | pl.col("native_id").is_null()
            | (pl.col("native_id").str.len_chars() == 0)
            | (pl.col("native_id") == "T:")
        ).height
        metadata_missing = records.filter(
            pl.col("title").is_null()
            | (pl.col("title").str.strip_chars() == "")
            | pl.col("artist").is_null()
            | (pl.col("artist").str.strip_chars() == "")
        ).height

        def known(column):
            return (
                pl.col(column)
                .filter(pl.col(column).is_not_null() & (pl.col(column).str.strip_chars() != ""))
                .sort()
                .first()
            )

        daily = records.group_by("period_end", "native_id").agg(
            pl.col("metric_value").n_unique().alias("variants"),
            pl.col("metric_value").first(),
            known("title"),
            known("artist"),
        )
        conflicts = daily.filter(pl.col("variants") != 1).height
        dates = set(daily["period_end"].to_list())
        depth = daily.group_by("period_end").len()["len"].min()
        status = (
            "CONFLICT_OR_INVALID"
            if invalid or conflicts
            else "COMPLETE"
            if dates == expected
            else "INCOMPLETE"
        )
        coverage.append(
            dict(
                country_code=country,
                year=year,
                platform=platform,
                provider=provider,
                expected_periods=len(expected),
                collected_periods=len(dates),
                coverage_status=status,
                minimum_depth=depth,
                invalid_items=invalid,
                metadata_missing_observations=metadata_missing,
                conflicting_items=conflicts,
                duplicate_observations=records.height - daily.height,
                observed_start=str(min(dates)),
                observed_end=str(max(dates)),
                ranking_period_end=min(date(year, 12, 31), cutoff).isoformat(),
                frequency=frequency,
                metric_type="STREAMS" if platform == "SPOTIFY" else "VIEWS",
                identity_status="native_id_pending_recording_review",
            )
        )
        if invalid or conflicts:
            continue
        annual = (
            daily.group_by("native_id")
            .agg(
                pl.col("metric_value").sum(),
                known("title"),
                known("artist"),
            )
            .sort(["metric_value", "native_id"], descending=[True, False])
        )
        total, cumulative = annual["metric_value"].sum(), 0
        for position, row in enumerate(annual.head(500).to_dicts(), 1):
            cumulative += row["metric_value"]
            rankings.append(
                dict(
                    country_code=country,
                    year=year,
                    platform=platform,
                    provider=provider,
                    position=position,
                    candidate_id=f"{platform}:{row['native_id']}",
                    title=row["title"],
                    artist=row["artist"],
                    metric_value=row["metric_value"],
                    cumulative_observed_share=cumulative / total if total else 0.0,
                    identity_status=(
                        "native_id_pending_recording_review"
                        if row["title"] and row["artist"]
                        else "metadata_missing"
                    ),
                )
            )
    return rankings, coverage


def merge_sources(old_rankings, old_coverage, new_rankings, new_coverage):
    """Pick a whole source per platform/year: complete calendar, days, then depth.

    Keep the existing source on exact ties. No streams or overlapping frequencies
    from different providers are added together.
    """
    chosen = {}
    for origin, rows in (("old", old_coverage), ("new", new_coverage)):
        for row in rows:
            key = row["country_code"], int(row["year"]), row["platform"]
            quality = {"COMPLETE": 2, "INCOMPLETE": 1}.get(row["coverage_status"], 0)
            score = (
                quality,
                float(row["collected_periods"]) / max(1, int(row["expected_periods"])),
                int(row.get("minimum_depth") or 0),
                origin == "old",
            )
            if key not in chosen or score > chosen[key][0]:
                chosen[key] = score, origin, row
    coverage = [value[2] for _, value in sorted(chosen.items())]
    ranked = []
    for origin, rows in (("old", old_rankings), ("new", new_rankings)):
        for row in rows:
            key = row["country_code"], int(row["year"]), row["platform"]
            if (
                key in chosen
                and chosen[key][1] == origin
                and row["provider"] == chosen[key][2]["provider"]
            ):
                ranked.append(row)
    return ranked, coverage
