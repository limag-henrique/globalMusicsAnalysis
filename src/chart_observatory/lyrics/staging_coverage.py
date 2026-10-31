"""Country/year position coverage without treating stored text as validated lyrics."""

from collections import defaultdict


def summarize_coverage(records, quotas, years=range(2018, 2027)):
    cells = {(country, year): defaultdict(list) for country in quotas for year in years}
    unique = {}
    for record in records:
        key = record["candidate_id"]
        state = unique.setdefault(key, dict(candidate_id=key, has_text=False,
                                            bindings=set(), min_position=None))
        state["has_text"] = state["has_text"] or bool(record.get("text_sha256"))
        for binding in record["payload"].get("chart_bindings", []):
            key = (binding["country_code"], int(binding["year"]))
            position = int(binding["position"])
            if key not in cells or not 1 <= position <= quotas[key[0]]:
                raise ValueError("binding outside the requested country/year quota")
            state["bindings"].add((key[0], key[1], position))
            state["min_position"] = min(position, state["min_position"] or position)
            cells[key][position].append(
                dict(
                    candidate_id=record["candidate_id"],
                    has_text=bool(record.get("text_sha256")),
                    provisional=binding.get("selection_status") == "PROVISIONAL_OBSERVED_PERIODS",
                    flagged=bool(record["audit"].get("text_quality_flags"))
                    or bool(record["audit"].get("source_quarantined")),
                )
            )
    rows = []
    for (country, year), positions in sorted(cells.items()):
        expected = set(range(1, quotas[country] + 1))
        conflicts = sorted(
            p for p, entries in positions.items() if len({e["candidate_id"] for e in entries}) != 1
        )
        texts = {p for p, entries in positions.items() if any(e["has_text"] for e in entries)}
        provisional = {
            p for p, entries in positions.items() if any(e["provisional"] for e in entries)
        }
        rows.append(
            dict(
                country_code=country,
                year=year,
                quota=quotas[country],
                selected_positions=len(positions),
                provisional_positions=len(provisional),
                positions_with_text=len(texts),
                positions_with_flagged_text=sum(
                    any(e["has_text"] and e["flagged"] for e in entries)
                    for entries in positions.values()
                ),
                missing_ranking_positions=sorted(expected - positions.keys()),
                missing_text_positions=sorted(positions.keys() - texts),
                conflicting_ranking_positions=conflicts,
                rank_selection_complete=set(positions) == expected and not conflicts,
                full_annual_rank_certified=False,
                lyrics_validated=False,
            )
        )
    missing_candidates = sorted(
        [dict(candidate_id=item["candidate_id"], selected_memberships=len(item["bindings"]),
              best_position=item["min_position"])
         for item in unique.values() if not item["has_text"] and item["bindings"]],
        key=lambda item: (-item["selected_memberships"], item["best_position"],
                          item["candidate_id"]),
    )
    return dict(
        missing_text_candidates=missing_candidates,
        cells=rows,
        summary=dict(
            unique_candidates=len(unique),
            unique_candidates_with_text=sum(item["has_text"] for item in unique.values()),
            unique_candidates_missing_text=len(missing_candidates),
            missing_candidate_order="most_selected_memberships_then_best_position",
            country_year_cells=len(rows),
            expected_positions=sum(r["quota"] for r in rows),
            selected_positions=sum(r["selected_positions"] for r in rows),
            provisional_positions=sum(r["provisional_positions"] for r in rows),
            positions_with_text=sum(r["positions_with_text"] for r in rows),
            missing_ranking_positions=sum(len(r["missing_ranking_positions"]) for r in rows),
            missing_text_positions=sum(len(r["missing_text_positions"]) for r in rows),
            conflicting_ranking_positions=sum(
                len(r["conflicting_ranking_positions"]) for r in rows
            ),
            empty_cells=sum(r["selected_positions"] == 0 for r in rows),
            full_annual_rank_certified=False,
            lyrics_validated=False,
            classification_ready=False,
        ),
    )
