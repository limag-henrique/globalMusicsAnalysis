"""Fixed annual top 80 from observed daily streams, before lyric eligibility gates."""

import polars as pl

ANNUAL_COHORT_SIZE = 80
ANNUAL_COHORT_VERSION = "annual-observed-streams-top80-v1"


def select_annual_top80(
    observations: pl.LazyFrame, *, candidate_limit: int = ANNUAL_COHORT_SIZE,
) -> pl.DataFrame:
    """Bound memory by processing one calendar year at a time."""
    if not 1 <= candidate_limit <= 200:
        raise ValueError("candidate_limit must be between 1 and 200")
    years = observations.select("year").unique().collect(engine="streaming")["year"].sort()
    if not len(years):
        raise ValueError("no historical daily stream observations")
    return pl.concat([
        _select_year(observations.filter(pl.col("year") == year), candidate_limit)
        for year in years
    ]).sort("market_code", "year", "annual_rank")


def _select_year(observations: pl.LazyFrame, candidate_limit: int) -> pl.DataFrame:
    """Use one provider per market/year; prefer most observed days, then depth.

    Never add mirrored providers' streams. Exact duplicate daily observations
    count once; contradictory values for the same recording/day fail closed.
    Missing lyric text never changes membership or advances the 81st song.
    """
    keys = ["provider", "market_code", "year"]
    daily = observations.select(
        *keys, "chart_track_id", "period_start", "metric_value", "track_title", "artist",
    ).unique()
    conflicts = daily.group_by(*keys, "chart_track_id", "period_start").agg(
        pl.col("metric_value").n_unique().alias("values"),
    ).filter(pl.col("values") != 1).limit(1).collect(engine="streaming")
    if conflicts.height:
        raise ValueError("conflicting daily stream observations")
    daily = daily.unique(subset=[*keys, "chart_track_id", "period_start"])
    coverage = daily.group_by(keys).agg(
        pl.col("period_start").n_unique().alias("observed_days"),
        pl.len().alias("observations"),
    ).collect(engine="streaming")
    providers = coverage.sort(
        ["market_code", "year", "observed_days", "observations", "provider"],
        descending=[False, False, True, True, False],
    ).unique(["market_code", "year"], keep="first", maintain_order=True)
    ranked = daily.join(providers.lazy(), on=keys).group_by(*keys, "chart_track_id").agg(
        pl.col("metric_value").sum().alias("annual_streams"),
        pl.col("track_title").sort().first(), pl.col("artist").sort().first(),
        pl.col("observed_days").first(),
    ).collect(engine="streaming").sort(
        ["market_code", "year", "annual_streams", "chart_track_id"],
        descending=[False, False, True, False],
    ).with_columns(
        pl.col("chart_track_id").cum_count().over("market_code", "year").alias("annual_rank"),
    )
    return ranked.filter(pl.col("annual_rank") <= candidate_limit)
