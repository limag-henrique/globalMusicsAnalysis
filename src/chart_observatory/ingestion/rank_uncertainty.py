"""Conditional annual-rank bounds for censored daily Top-K observations."""

from bisect import bisect_left, bisect_right
from collections import defaultdict


def audit_rank_bounds(rows, *, expected_periods, depth, quota):
    """Never treat calendar completeness as proof of full annual popularity order.

    Bounds assume an unlisted track cannot exceed that day's last published
    stream count. They do not certify tracks excluded by provider eligibility rules.
    """
    periods = defaultdict(list)
    for row in rows:
        periods[row["period_end"]].append(row)
    if set(periods) != set(expected_periods):
        raise ValueError("rank bounds require the complete expected calendar")
    lower, present_floors = defaultdict(int), defaultdict(int)
    unseen_ceiling = 0
    for records in periods.values():
        records = sorted(records, key=lambda row: row["source_rank"])
        if [r["source_rank"] for r in records] != list(range(1, depth + 1)):
            raise ValueError("rank bounds require every published Top-K position")
        if len({r["native_id"] for r in records}) != depth:
            raise ValueError("duplicate native item in a published chart")
        values = [r["metric_value"] for r in records]
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in values):
            raise ValueError("invalid published stream count")
        if values != sorted(values, reverse=True):
            raise ValueError("published rank does not follow stream order")
        floor = values[-1]
        unseen_ceiling += floor
        for row in records:
            key = row["native_id"]
            lower[key] += row["metric_value"]
            present_floors[key] += floor
    upper = {key: value + unseen_ceiling - present_floors[key] for key, value in lower.items()}
    lowers, uppers = sorted(lower.values()), sorted(upper.values())
    ranked = sorted(lower, key=lambda key: (-lower[key], key))
    output = []
    for position, key in enumerate(ranked[:quota], 1):
        best = 1 + len(lowers) - bisect_right(lowers, upper[key])
        worst = (
            len(uppers) - bisect_left(uppers, lower[key]) if lower[key] > unseen_ceiling else None
        )
        output.append(
            dict(
                native_id=key,
                observed_rank=position,
                observed_streams=lower[key],
                annual_streams_lower=lower[key],
                annual_streams_upper=upper[key],
                best_possible_rank=best,
                worst_possible_rank=worst,
                exact_position_guaranteed=best == worst,
                top_quota_membership_guaranteed=worst is not None and worst <= quota,
            )
        )
    return dict(
        periods=len(periods),
        published_depth=depth,
        quota=quota,
        unseen_track_annual_ceiling=unseen_ceiling,
        assumption="unlisted eligible tracks never exceed the last published daily count",
        recording_and_lyrics_validated=False,
        rankings=output,
        exact_positions_guaranteed=sum(r["exact_position_guaranteed"] for r in output),
        memberships_guaranteed=sum(r["top_quota_membership_guaranteed"] for r in output),
    )
