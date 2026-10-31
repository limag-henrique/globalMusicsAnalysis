"""Hash-bound review gate for variable country quotas, preserving every ranked position."""

from collections import Counter, defaultdict

from chart_observatory.lyrics.annual_eligibility import _validate


def prepare_quota_review(
    candidates, validations, *, current_documents, blocked=(), expected_cells=()
):
    """Prepare evidence-bound candidates; never promote reserves or authorize paid calls."""
    evidence, groups = defaultdict(list), defaultdict(list)
    for entry in validations:
        evidence[entry["candidate_id"]].append(entry)
    for row in candidates:
        groups[row["country_code"], row["year"], row["platform"]].append(row)
    annotated, coverage = [], []
    blocked = set(blocked)
    for group, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda row: row["position"])
        quotas = {row["quota_main"] for row in rows}
        if len(quotas) != 1:
            raise ValueError("inconsistent country/year quota")
        quota = next(iter(quotas))
        if not isinstance(quota, int) or quota < 1:
            raise ValueError("invalid country/year quota")
        if [row["position"] for row in rows] != list(range(1, len(rows) + 1)) or len(rows) > quota:
            raise ValueError("ranking positions missing or outside country/year quota")
        if len({row["candidate_id"] for row in rows}) != len(rows):
            raise ValueError("duplicate native candidate within country/year ranking")
        for row in rows:
            entries = evidence[row["candidate_id"]]
            explicit_recording = entries[0].get("recording_id") if len(entries) == 1 else None
            checked = {**row, "recording_id": row.get("recording_id") or explicit_recording}
            if row.get("selection_status") == "PROVISIONAL_OBSERVED_PERIODS":
                binding, reason = None, "provisional_calendar"
            else:
                binding, reason = _validate(checked, entries, current_documents, blocked)
            annotated.append(
                {
                    **row,
                    "eligibility_reason": reason,
                    "validated_binding": binding,
                    "classification_ready": False,
                    "not_for_paid_submission": True,
                }
            )
        coverage.append(
            dict(
                country_code=group[0],
                year=group[1],
                platform=group[2],
                quota=quota,
                selected_positions=len(rows),
            )
        )
    hashes = defaultdict(set)
    for row in annotated:
        if binding := row["validated_binding"]:
            hashes[binding["recording_id"]].add(binding["lyrics_hash"])
    prepared = {}
    for row in annotated:
        binding = row["validated_binding"]
        if not binding:
            continue
        if len(hashes[binding["recording_id"]]) != 1:
            row["eligibility_reason"] = "recording_has_conflicting_validated_texts"
            continue
        signature = binding["recording_id"], binding["lyrics_hash"]
        task = prepared.setdefault(
            signature,
            dict(
                recording_id=signature[0],
                lyrics_hash=signature[1],
                document_id=binding["document_id"],
                memberships=[],
                status="reviewed_not_submitted",
                not_for_paid_submission=True,
            ),
        )
        task["memberships"].append(
            {
                key: row[key]
                for key in (
                    "candidate_id",
                    "country_code",
                    "year",
                    "platform",
                    "position",
                    "quota_main",
                )
            }
        )
    reviewed_cells = defaultdict(list)
    for row in annotated:
        reviewed_cells[row["country_code"], row["year"], row["platform"]].append(row)
    for cell in coverage:
        rows = reviewed_cells[cell["country_code"], cell["year"], cell["platform"]]
        eligible = sum(row["eligibility_reason"] == "eligible" for row in rows)
        cell.update(
            eligible_positions=eligible,
            deficit=cell["quota"] - eligible,
            reasons=dict(Counter(row["eligibility_reason"] for row in rows)),
        )
    represented = {(cell["country_code"], cell["year"]) for cell in coverage}
    for cell in expected_cells:
        if (cell["country_code"], cell["year"]) not in represented:
            quota = cell["quota_main"]
            coverage.append(
                dict(
                    country_code=cell["country_code"],
                    year=cell["year"],
                    platform=None,
                    quota=quota,
                    selected_positions=0,
                    eligible_positions=0,
                    deficit=quota,
                    reasons={"ranking_calendar_unavailable": quota},
                )
            )
    coverage.sort(key=lambda cell: (cell["country_code"], cell["year"]))
    return dict(
        ranked_positions=annotated,
        coverage=coverage,
        prepared_candidates=list(prepared.values()),
        classification_ready=False,
        paid_calls=0,
        remaining_gates=[
            "annual_ranking_basis_and_censoring",
            "protocol_signature",
            "budget_reconciliation",
            "pilot",
        ],
    )
