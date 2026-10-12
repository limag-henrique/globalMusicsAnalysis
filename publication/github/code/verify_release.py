"""Verify the public release folder and its scientific table contracts, offline."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys

import polars as pl


def verify(root: Path) -> dict:
    manifest = json.loads((root / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    forbidden = {'original_lyrics', 'lyrics_text', 'raw_lyrics', 'access_token', 'refresh_token', 'private_key'}
    declared = {row['path'] for row in manifest['files']} | {'RELEASE_MANIFEST.json', 'SHA256SUMS.txt', 'dataset-metadata.json'}
    for candidate in root.rglob('*'):
        if candidate.is_file() and not {'__pycache__', 'reproduced-figures', 'reproduced'}.intersection(candidate.parts):
            relative = candidate.relative_to(root).as_posix()
            if relative not in declared:
                raise ValueError('Unlisted release file: ' + relative)
    for row in manifest['files']:
        p = (root / row['path']).resolve()
        if not p.is_relative_to(root.resolve()):
            raise ValueError('Manifest path escapes release')
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != row['sha256']:
            raise ValueError('Checksum mismatch: ' + row['path'])
        if p.suffix in {'.parquet', '.csv'}:
            frame = pl.read_parquet(p) if p.suffix == '.parquet' else pl.read_csv(p, infer_schema_length=10000)
            if forbidden.intersection(frame.columns):
                raise ValueError('Private text/credential column: ' + row['path'])
        elif p.suffix in {'.md', '.json', '.txt', '.py', '.html', '.tex'}:
            value = p.read_text(encoding='utf-8')
            patterns = [r'[A-Za-z]:[/\\]+Users[/\\]+[A-Za-z0-9]',
                        r'postgresql(?:\+psycopg)?://[^\s/]+:[^\s]+@',
                        r'ya29\.[A-Za-z0-9_-]{15,}']
            if any(re.search(pattern, value) for pattern in patterns):
                raise ValueError('Private workspace/credential material: ' + row['path'])
    schema = json.loads((root / 'taxonomy.json').read_text(encoding='utf-8'))
    metrics = list(schema['dimensions'])
    for name, key, expected in [('native-classifications', 'recording_id', 154942), ('full-corpus-classifications', 'research_recording_id', 154964)]:
        frame = pl.read_parquet(root / 'data/inputs' / (name + '.parquet'))
        if frame.height != expected or frame[key].n_unique() != expected:
            raise ValueError('Recording identity/count contract: ' + name)
        for m in metrics:
            if frame[m].null_count() or frame.filter(~pl.col(m).is_between(0, 3)).height:
                raise ValueError('Invalid intensity: ' + m)
    for name, keys, expected in [('country-metrics', ['market_code'], 68), ('annual-country-metrics', ['market_code', 'year'], 386)]:
        frame = pl.read_parquet(root / 'data/results' / (name + '.parquet'))
        if frame.height != expected or frame.select(pl.struct(keys).n_unique()).item() != expected:
            raise ValueError('Market/year uniqueness: ' + name)
        if frame.filter(pl.col('classified_tracks') > pl.col('chart_tracks')).height:
            raise ValueError('Classified denominator exceeds observed corpus')
        for m in metrics:
            errors = frame.filter((pl.col(m + '_pct') - 100 * pl.col(m + '_positive') / pl.col('classified_tracks')).abs() > 1e-8)
            if errors.height:
                raise ValueError('Numerator/denominator mismatch: ' + name + '/' + m)
    br = pl.read_parquet(root / 'data/results/country-metrics.parquet').filter(pl.col('market_code') == 'BR')
    if br['classified_tracks'].item() != 7186 or br['chart_tracks'].item() != 9619:
        raise ValueError('Brazil frozen corpus contract')
    return {'verified_files': len(manifest['files']), 'markets': 68, 'dimensions': len(metrics), 'status': 'passed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('release', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.release), indent=2))
    except (ValueError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
