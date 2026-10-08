"""Evidence gates for scientific use, independent of successful AI execution."""

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from chart_observatory.lyrics.classification import LyricsClassification
from chart_observatory.lyrics.identity_quarantine import EXCLUDED_DECISIONS, IdentityQuarantineEntry
from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS


@dataclass(frozen=True)
class ScientificEligibility:
    primary_eligible: bool
    exploratory_eligible: bool
    reasons: tuple[str, ...]


def assess_classification(
    document: Any,
    snapshot: Any,
    *,
    entries: tuple[IdentityQuarantineEntry, ...],
    suspended_sources: frozenset[str],
) -> ScientificEligibility:
    """Require a current, hash-bound identity review for the primary sample.

    This gate does not establish a link to a chart observation or validate
    human agreement with AI scores; callers must establish those separately.
    """
    reasons: list[str] = []
    if document.canonical_track_id != snapshot.canonical_track_id:
        reasons.append("track_mismatch")
    if document.content_sha256 != snapshot.lyrics_hash:
        reasons.append("hash_mismatch")
    if document.rights_status not in AUTHORIZED_RIGHTS:
        reasons.append("rights_unauthorized")
    if document.source.upper() in suspended_sources:
        reasons.append("source_suspended")
    if snapshot.classification_status != "classified":
        reasons.append("not_classified")
    else:
        try:
            result = LyricsClassification.model_validate(snapshot.result_json)
            if result.classification_status != snapshot.classification_status:
                reasons.append("result_status_mismatch")
        except ValidationError:
            reasons.append("invalid_result")
    review = next((entry for entry in entries if entry.lyric_document_id == document.id), None)
    if review is not None:
        if (
            review.canonical_track_id != document.canonical_track_id
            or review.lyrics_hash != document.content_sha256
            or review.source.upper() != document.source.upper()
        ):
            reasons.append("review_binding_mismatch")
        if review.decision in EXCLUDED_DECISIONS:
            reasons.append("identity_excluded")
    exploratory = not reasons
    if review is None or review.decision != "confirmed_match":
        reasons.append("identity_unverified")
    return ScientificEligibility(not reasons, exploratory, tuple(reasons))
