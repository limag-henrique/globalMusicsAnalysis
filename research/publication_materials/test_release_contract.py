"""External file-contract checks: tampering and forbidden text must be rejected."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('verify_release', HERE / 'verify_release.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublicReleaseContract(unittest.TestCase):
    def test_tampered_release_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file = root / 'data.csv'
            file.write_text('value\n1\n', encoding='utf-8')
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            (root / 'RELEASE_MANIFEST.json').write_text(json.dumps({'files': [{'path': 'data.csv', 'sha256': digest}]}))
            file.write_text('value\n2\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                module.verify(root)

    def test_private_lyric_column_is_rejected_even_with_valid_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file = root / 'data.csv'
            file.write_text('original_lyrics\nsynthetic-test-marker\n', encoding='utf-8')
            (root / 'RELEASE_MANIFEST.json').write_text(json.dumps({'files': [{'path': 'data.csv', 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}]}))
            with self.assertRaisesRegex(ValueError, 'Private text/credential column'):
                module.verify(root)

    def test_manifest_cannot_escape_release_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'RELEASE_MANIFEST.json').write_text(json.dumps({'files': [{'path': '../outside.csv', 'sha256': ''}]}))
            with self.assertRaisesRegex(ValueError, 'escapes release'):
                module.verify(root)


if __name__ == '__main__':
    unittest.main()
