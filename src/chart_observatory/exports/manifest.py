import hashlib

from chart_observatory.artifacts.manifest import deterministic_manifest
from chart_observatory.exports.models import ExportManifest


def manifest_bytes(manifest: ExportManifest) -> bytes:
    return deterministic_manifest(manifest)


def manifest_sha256(manifest: ExportManifest) -> str:
    return hashlib.sha256(manifest_bytes(manifest)).hexdigest()
