"""Select recent native metadata proofs without changing study membership."""

import hashlib
import json
from datetime import datetime
from pathlib import Path


def recent_native_targets(selected_ids, resolutions, since):
    if since.tzinfo is None:
        raise ValueError("metadata cutoff must include a timezone")
    documents, targets = {}, []
    for key, ref in sorted(resolutions.items()):
        if key not in selected_ids or not key.startswith("SPOTIFY:"):
            continue
        signature = ref["evidence_file"], ref["evidence_sha256"]
        if signature not in documents:
            raw = Path(signature[0]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != signature[1]:
                raise ValueError("native metadata evidence hash mismatch")
            documents[signature] = json.loads(raw)
        proof = documents[signature]
        if ref.get("evidence_key"):
            proof = proof[ref["evidence_key"]]
        native = key.removeprefix("SPOTIFY:")
        metadata = proof.get("metadata") or {}
        if (
            proof.get("status") != 200
            or proof.get("source_url") != f"https://open.spotify.com/embed/track/{native}"
            or metadata.get("uri") != f"spotify:track:{native}"
            or any(
                not isinstance(metadata.get(field), str) or not metadata[field].strip()
                for field in ("title", "artist")
            )
        ):
            raise ValueError("native metadata proof belongs to another or unknown track")
        if not proof.get("retrieved_at"):
            continue
        retrieved = datetime.fromisoformat(proof["retrieved_at"])
        if retrieved.tzinfo is None:
            raise ValueError("metadata observation must include a timezone")
        if retrieved >= since:
            targets.append(
                dict(
                    candidate_id=key,
                    retrieved_at=retrieved.isoformat(),
                    evidence_sha256=signature[1],
                )
            )
    return targets
