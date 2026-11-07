"""Flag shared text across differing identities without deciding which is correct."""

from collections import defaultdict

from chart_observatory.lyrics.quota_acquisition import identity


def flag_shared_text_identities(records):
    groups = defaultdict(list)
    for record in records:
        if record.get("text_sha256"):
            groups[record["text_sha256"]].append(record)
    collisions = []
    for digest, members in sorted(groups.items()):
        flags = []
        for field, flag in (("title", "same_text_different_titles"),
                            ("artist", "same_text_different_performers")):
            if len({identity(row["payload"].get(field)) for row in members}) > 1:
                flags.append(flag)
        if not flags:
            continue
        for row in members:
            row["audit"]["text_quality_flags"] = sorted(
                set(row["audit"].get("text_quality_flags", [])) | set(flags)
            )
        collisions.append(dict(
            text_sha256=digest, flags=flags,
            candidates=[dict(candidate_id=row["candidate_id"],
                             title=row["payload"].get("title"),
                             artist=row["payload"].get("artist"),
                             selected_memberships=len(row["payload"].get("chart_bindings", [])))
                        for row in sorted(members, key=lambda item: item["candidate_id"])],
        ))
    return collisions
