"""Platform-separated topic proportions and explicit missing-data scenarios."""

import polars as pl

from chart_observatory.lyrics.review_protocol import TOPICS

GROUP = ["country_code", "year", "platform", "window", "sample"]
BINDING = ["text_identity_id", "normalized_hash", "request_key"]


def build_rankings(memberships: pl.DataFrame, classifications: pl.DataFrame) -> pl.DataFrame:
    """Never replace absent text/scores with zero. Publication gates are separate."""
    required = {
        *GROUP,
        *BINDING,
        "candidate_id",
        "recording_id",
        "text_validated",
        "applicability",
        "coverage_status",
        "metric_value",
    }
    if not required <= set(memberships.columns):
        raise ValueError("selection is missing identity, coverage or sample fields")
    base = memberships.unique().with_columns([pl.col(k).cast(pl.String) for k in BINDING])
    if base.select(pl.struct(*GROUP, "candidate_id").n_unique()).item() != base.height:
        raise ValueError("duplicate or conflicting selection memberships")
    if base.filter(pl.col("text_validated") & pl.col("recording_id").is_null()).height:
        raise ValueError("validated text requires a recording identity")
    duplicates = base.filter(pl.col("text_validated")).group_by(*GROUP, "recording_id").len()
    if duplicates.filter(pl.col("len") > 1).height:
        raise ValueError("a recording occurs twice in the same selection")
    if base.filter(
        pl.col("metric_value").is_not_null()
        & ((pl.col("metric_value") < 0) | ~pl.col("metric_value").is_finite())
    ).height:
        raise ValueError("audience metrics must be nonnegative finite observations")
    if "metric_type" in base.columns:
        invalid = base.filter(
            ((pl.col("platform") == "SPOTIFY") & (pl.col("metric_type") != "STREAMS"))
            | ((pl.col("platform") == "YOUTUBE") & (pl.col("metric_type") != "VIEWS"))
        )
        if invalid.height:
            raise ValueError("incompatible audience metric for platform")
    labels = classifications.unique()
    expected = {*BINDING, "topic", "score", "classification_status"}
    if not expected <= set(labels.columns):
        raise ValueError("classifications require a complete text/signature binding")
    if labels.height and not labels.schema["score"].is_integer():
        raise ValueError("scores must be integers, never booleans or rounded floats")
    if labels.filter(pl.col("score").is_not_null() & ~pl.col("score").is_between(0, 3)).height:
        raise ValueError("intensity outside 0–3")
    if labels.select(pl.struct("request_key", "topic").n_unique()).item() != labels.height:
        raise ValueError("ambiguous classification for request/topic")
    if labels.filter(~pl.col("topic").is_in(list(TOPICS))).height:
        raise ValueError("unknown topic")
    labels = labels.with_columns([pl.col(k).cast(pl.String) for k in BINDING])
    output = []
    for topic in TOPICS:
        observed = base.join(
            labels.filter(pl.col("topic") == topic).select(
                *BINDING, "score", "classification_status"
            ),
            on=BINDING,
            how="left",
            validate="m:1",
        )
        applicable = pl.col("applicability") != "not_applicable"
        valid = (
            applicable
            & pl.col("text_validated")
            & (pl.col("classification_status") == "classified")
            & pl.col("score").is_not_null()
        )
        observed = observed.with_columns(valid.fill_null(False).alias("_valid"))
        grouped = (
            observed.group_by(GROUP)
            .agg(
                pl.len().alias("selection_n"),
                (pl.col("applicability") == "not_applicable").sum().alias("not_applicable_n"),
                (pl.col("text_validated") & applicable).sum().alias("text_eligible_n"),
                pl.col("_valid").sum().alias("scored_n"),
                (pl.col("_valid") & (pl.col("score") >= 2)).sum().alias("positive_n"),
                (pl.col("coverage_status") == "COMPLETE").all().alias("calendar_complete"),
                pl.col("metric_value").filter(pl.col("_valid")).sum().alias("scored_weight"),
                pl.col("metric_value")
                .filter(pl.col("_valid") & (pl.col("score") >= 2))
                .sum()
                .alias("positive_weight"),
                pl.col("metric_value").is_null().any().alias("weights_missing"),
            )
            .with_columns(
                (pl.col("selection_n") - pl.col("not_applicable_n")).alias("applicable_n"),
                pl.lit(topic).alias("topic"),
            )
            .with_columns(
                (pl.col("applicable_n") - pl.col("scored_n")).alias("unknown_n"),
                pl.when(pl.col("scored_n") > 0)
                .then(pl.col("positive_n") / pl.col("scored_n"))
                .otherwise(None)
                .alias("observed_proportion"),
                pl.when(pl.col("applicable_n") > 0)
                .then(pl.col("scored_n") / pl.col("applicable_n"))
                .otherwise(None)
                .alias("coverage"),
                pl.when((pl.col("scored_weight") > 0) & ~pl.col("weights_missing"))
                .then(pl.col("positive_weight") / pl.col("scored_weight"))
                .otherwise(None)
                .alias("audience_weighted_secondary"),
            )
            .with_columns(
                pl.when(pl.col("applicable_n") > 0)
                .then(pl.col("positive_n") / pl.col("applicable_n"))
                .otherwise(None)
                .alias("missing_all_absent"),
                pl.when(pl.col("applicable_n") > 0)
                .then((pl.col("positive_n") + pl.col("unknown_n")) / pl.col("applicable_n"))
                .otherwise(None)
                .alias("missing_all_present"),
                pl.when(
                    pl.col("calendar_complete")
                    & (pl.col("unknown_n") == 0)
                    & (pl.col("scored_n") > 0)
                    & ((pl.col("sample") != "eligible") | (pl.col("text_eligible_n") >= 80))
                )
                .then(pl.col("observed_proportion"))
                .otherwise(None)
                .alias("primary_proportion"),
                pl.max_horizontal(80 - pl.col("text_eligible_n").cast(pl.Int64), pl.lit(0)).alias(
                    "text_target_deficit"
                ),
            )
        )
        output.append(grouped)
    result = pl.concat(output)
    return result.with_columns(
        pl.col("primary_proportion")
        .rank("min", descending=True)
        .over("year", "platform", "window", "sample", "topic")
        .alias("country_rank")
    ).sort(*GROUP, "topic")


def compare_versions(before: pl.DataFrame, after: pl.DataFrame) -> pl.DataFrame:
    keys = [*GROUP, "topic"]
    columns = ["primary_proportion", "country_rank", "scored_n", "text_eligible_n"]
    return (
        before.select(*keys, *columns)
        .join(
            after.select(*keys, *columns),
            on=keys,
            how="full",
            coalesce=True,
            suffix="_corrected",
            validate="1:1",
        )
        .with_columns(
            (pl.col("primary_proportion_corrected") - pl.col("primary_proportion")).alias(
                "proportion_change"
            ),
            (
                pl.col("country_rank_corrected").cast(pl.Int64)
                - pl.col("country_rank").cast(pl.Int64)
            ).alias("rank_change"),
        )
    )
