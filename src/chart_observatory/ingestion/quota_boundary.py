"""Fail closed at the annual analysis boundary; reference chart rows are never memberships."""

from collections import defaultdict


def validate_quota_memberships(rows, quotas):
    positions, identities = defaultdict(set), defaultdict(set)
    for row in rows:
        country, year = row["country_code"], row["year"]
        position = row["position"]
        if country not in quotas or type(year) is not int or not 2018 <= year <= 2026:
            raise ValueError("membership outside approved country/year scope")
        quota = quotas[country]
        if type(position) is not int or not 1 <= position <= quota:
            raise ValueError("annual position exceeds approved country quota")
        if row.get("quota_main", quota) != quota:
            raise ValueError("membership quota differs from approved country table")
        key = country, year
        if position in positions[key] or row["candidate_id"] in identities[key]:
            raise ValueError("duplicate annual position or candidate")
        if row.get("selection_status") == "DISCOVERY_QUARANTINE":
            raise ValueError("weekly reference observations cannot enter annual analysis")
        positions[key].add(position)
        identities[key].add(row["candidate_id"])
    return [
        dict(country_code=c, year=y, quota=quotas[c], selected_positions=len(p), excess_positions=0)
        for (c, y), p in sorted(positions.items())
    ]


def validate_ranking_positions(selections, rankings):
    """Require the exact frozen source candidate at the exact market/year/platform/rank."""
    lookup = {}
    for row in rankings:
        key = tuple(row[k] for k in ("country_code", "year", "platform", "position"))
        previous = lookup.setdefault(key, row["candidate_id"])
        if previous != row["candidate_id"]:
            raise ValueError("conflicting source identities at a ranking position")
    for row in selections:
        key = tuple(row[k] for k in ("country_code", "year", "platform", "position"))
        if lookup.get(key) != row["candidate_id"]:
            raise ValueError("selected song differs from the frozen country/year/rank")
