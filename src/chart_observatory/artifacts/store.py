import hashlib
import os
from pathlib import Path

from chart_observatory.artifacts.models import ArtifactContext, StoredArtifact
from chart_observatory.domain.enums import RightsOperation
from chart_observatory.rights.gate import RightsGate


class ArtifactStore:
    def __init__(self, root: Path, rights_gate: RightsGate) -> None:
        self.root = Path(root)
        self.rights_gate = rights_gate

    def put(self, content: bytes, context: ArtifactContext) -> StoredArtifact:
        self.rights_gate.require(context.source_id, RightsOperation.STORE_RAW, context.occurred_at)
        digest = hashlib.sha256(content).hexdigest()
        path = self.root / "sha256" / digest[:2] / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
        return StoredArtifact(digest, path, len(content), context)
