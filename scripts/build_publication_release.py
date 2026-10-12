"""Consolidate the verified freeze into portable, explicitly allowlisted public releases."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import polars as pl
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.classification import LyricsClassification
from chart_observatory.lyrics.gemini_pipeline import _CLASSIFICATION_INSTRUCTIONS

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = ROOT / 'research/article'
DATA = ARTICLE / 'analysis-final'
MATERIALS = ROOT / 'research/publication_materials'
EXCLUDED = ['GLOBAL', 'HK', 'PR']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_stable(source, destination):
    before = digest(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if digest(source) != before or digest(destination) != before:
        raise RuntimeError('Source changed while copying: ' + str(source.relative_to(ROOT)))
    return before


def export(frame, directory, name, csv=False):
    directory.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(directory / (name + '.parquet'), compression='zstd')
    if csv:
        frame.write_csv(directory / (name + '.csv'))


def extract_codes(selected):
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={'connect_timeout': 5})
    mapping = {r['snapshot_id']: r['lyric_track_id'] for r in selected.select('snapshot_id', 'lyric_track_id').to_dicts()}
    records = []
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        ids = list(mapping)
        for start in range(0, len(ids), 20000):
            rows = connection.execute(text('SELECT id,result_json FROM lyric_classification_snapshots WHERE id=ANY(CAST(:ids AS uuid[]))'),
                                      {'ids': ids[start:start + 20000]}).mappings()
            for row in rows:
                obj = row['result_json']
                records.append(dict(research_recording_id=mapping[str(row['id'])], consent=obj['relationships']['consent'],
                    target_gender=obj['gender_representation']['target_gender'],
                    representation_roles=json.dumps(obj['gender_representation']['representation_roles']),
                    **{m + '_stance': obj['antisocial'][m]['stance'] for m in ['drugs_alcohol', 'crime', 'violence', 'weapons']}))
    engine.dispose()
    result = pl.DataFrame(records).sort('research_recording_id')
    assert result.height == selected.height and result['research_recording_id'].n_unique() == selected.height
    return result


def main(destination, refresh=False):
    if destination.exists() and not refresh:
        raise RuntimeError('Release directory already exists; choose a fresh --output directory')
    if refresh and not (destination / 'CONSOLIDATION_REPORT.json').is_file():
        raise RuntimeError('Refresh requires an existing release built by this command')
    destination.mkdir(parents=True, exist_ok=refresh)
    source_manifest = json.loads((DATA / 'manifest.json').read_text())
    selected = pl.read_parquet(DATA / 'selected-classifications.parquet').sort('append_order', descending=True).unique('lyric_track_id', keep='first')
    metrics = pl.read_csv(DATA / 'all-dimensions.csv')['metric'].to_list()
    full = selected.select(pl.col('lyric_track_id').alias('research_recording_id'), pl.col('lyrics_hash').alias('lyrics_sha256'), *metrics)
    native = pl.read_parquet(DATA / 'native-id-annotations.parquet').select(pl.col('chart_track_id').alias('recording_id'),
        pl.col('lyric_track_id').alias('research_recording_id'), pl.col('lyrics_hash').alias('lyrics_sha256'), *metrics)
    membership_source = ROOT / 'data/derived/research_quality/country-all-history-20261011-022524/unique-chart-track-market-year-source.parquet'
    membership = pl.read_parquet(membership_source).filter((pl.col('origin_platform') == 'SPOTIFY') & ~pl.col('market_code').is_in(EXCLUDED)).rename({'chart_track_id': 'recording_id'})
    codes = extract_codes(selected)
    external = pl.read_parquet(DATA / 'context/country-context-observations.parquet').drop('raw_path').with_columns(
        (pl.lit('source-sha256:') + pl.col('raw_sha256')).alias('source_artifact_ref'))
    search = pl.read_csv(ROOT / 'data/derived/country_context/trends-browser/trends-browser-observations.csv', infer_schema_length=10000)
    indicator_names = pl.read_parquet(DATA / 'context/coverage.parquet')['indicator_code'].unique().sort().to_list()
    dictionary = []
    provenance = external.select('source', 'indicator_code', 'unit', 'source_url', 'retrieved_at', 'raw_sha256', 'methodology_version').unique().sort('source', 'indicator_code')
    taxonomy = dict(version='lyrics-classification-v1', prompt_version='lyrics-classification-prompt-v2',
        model='gemini-3.8-flash', positive_threshold=2,
        dimensions={m: {'type': 'integer', 'minimum': 0, 'maximum': 3} for m in metrics},
        intensity_meanings={'0': 'absent', '1': 'incidental', '2': 'substantial', '3': 'central'},
        expert_verification='completed')
    manifests = []
    for platform in ['github', 'kaggle']:
        release = destination / platform
        release.mkdir(exist_ok=refresh)
        inputs, results = release / 'data/inputs', release / 'data/results'
        for file in MATERIALS.glob('*'):
            if file.suffix in {'.md', '.txt'}:
                copy_stable(file, release / file.name)
            elif file.suffix == '.py':
                copy_stable(file, release / 'code' / file.name)
        for name in ['article_context', 'historical_models', 'historical_panel']:
            source = (ROOT / 'src/chart_observatory/analysis' / (name + '.py')).read_text(encoding='utf-8')
            source = source.replace('from chart_observatory.analysis.article_context import EXCLUDED_MARKETS', 'from article_context import EXCLUDED_MARKETS')
            (release / 'code' / (name + '.py')).write_text(source, encoding='utf-8')
        (release / 'code/classification.py').write_text((ROOT / 'src/chart_observatory/lyrics/classification.py').read_text(encoding='utf-8'), encoding='utf-8')
        plotting = (ARTICLE / 'plot_global_patterns.py').read_text(encoding='utf-8')
        plotting = plotting.replace('HERE=Path(__file__).resolve().parent', 'HERE=Path(__file__).resolve().parents[1]')
        plotting = plotting.replace("DATA=HERE/'global-patterns'", "DATA=HERE/'data/results/global-patterns'")
        plotting = plotting.replace("FIGURES=HERE/'figures'", "FIGURES=HERE/'reproduced-figures'")
        plotting = plotting.replace("HERE/'analysis-final/annual-country-metrics.parquet'", "HERE/'data/results/annual-country-metrics.parquet'")
        plotting = plotting.replace("HERE/'analysis-final/", "HERE/'data/results/")
        plotting = plotting.replace("DATA/'figure-definitions.tex'", "FIGURES/'figure-definitions.tex'")
        plotting = plotting.replace("DATA/'figure-manifest.json'", "FIGURES/'figure-manifest.json'")
        (release / 'code/plot_global_patterns.py').write_text(plotting, encoding='utf-8')
        (release / 'classification-instructions.txt').write_text(_CLASSIFICATION_INSTRUCTIONS, encoding='utf-8')
        (release / 'taxonomy.json').write_text(json.dumps(taxonomy, indent=2), encoding='utf-8')
        (release / 'classification-schema.json').write_text(json.dumps(LyricsClassification.model_json_schema(), indent=2), encoding='utf-8')
        (release / 'context-indicators.json').write_text(json.dumps(indicator_names, indent=2), encoding='utf-8')
        gm = json.loads((ARTICLE / 'global-patterns/manifest.json').read_text())
        (release / 'global-panels.json').write_text(json.dumps({k: gm[k] for k in ['years', 'threshold', 'balanced_panel', 'weighting', 'spread', 'interpretation', 'panels']}, indent=2), encoding='utf-8')
        (release / 'selection-summary.json').write_text(json.dumps({k: source_manifest[k] for k in ['database_snapshot_utc', 'documents', 'status_counts', 'selected_documents', 'selected_unique_tracks', 'linked_native_ids', 'geographic_unique_tracks', 'markets', 'country_years', 'metric_threshold', 'confidence_filter', 'expert_verification']}, indent=2), encoding='utf-8')
        provenance.write_csv(release / 'source-attribution.csv')
        for name, frame in [('full-corpus-classifications', full), ('native-classifications', native), ('recording-categorical-codes', codes),
                            ('chart-membership', membership), ('external-context', external), ('search-observations', search)]:
            # The membership table is larger and has no copyrighted lyric/chart text.
            export(frame, inputs, name, csv=(platform == 'kaggle' and name != 'chart-membership'))
            for column, dtype in frame.schema.items():
                dictionary.append({'table': name, 'column': column, 'type': str(dtype), 'rows': frame.height})
        copy_stable(ROOT / 'data/derived/mgd_coverage.parquet', inputs / 'mgd-chart-coverage.parquet')
        for source in DATA.rglob('*.parquet'):
            if source.name in ['selected-classifications.parquet', 'native-id-annotations.parquet']:
                continue
            if 'context' in source.relative_to(DATA).parts:
                continue  # Consolidated long source table above; derived joins are reproducible.
            frame = pl.read_parquet(source)
            rel = source.relative_to(DATA)
            export(frame, results / rel.parent, source.stem, csv=True)
        for folder in ['social-context', 'global-patterns']:
            for source in (ARTICLE / folder).glob('*.parquet'):
                export(pl.read_parquet(source), results / folder, source.stem, csv=True)
            for source in (ARTICLE / folder).glob('*.csv'):
                if not source.with_suffix('.parquet').exists():
                    copy_stable(source, results / folder / source.name)
        # Native-period persistence and genre summaries are derivative results, not raw chart dumps.
        for name in ['persistence', 'market_anxiety', 'genre_variation', 'genre_distance']:
            source = ROOT / 'data/derived/article' / (name + '.parquet')
            copy_stable(source, results / 'chart-dynamics' / (name + '.parquet'))
        for name in ['article.tex', 'article.pdf', 'article.template.tex', 'international-atlas.csv', 'international-atlas.html']:
            copy_stable(ARTICLE / name, release / 'article' / name)
        for source in (ARTICLE / 'figures').glob('*'):
            if source.suffix.lower() in {'.png', '.pdf', '.svg'}:
                copy_stable(source, release / 'figures' / source.name)
        # Portable notebook: public file interface, no database or credential access.
        notebook = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
          'cells': [
            {'cell_type': 'markdown', 'metadata': {}, 'source': ['# External validation\n', 'Verify the frozen release, inspect Brazil and other markets, then reproduce all results offline.'], 'id': 'intro'},
            {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'id': 'load', 'source': [
              'from pathlib import Path\n', 'import sys, subprocess, json, hashlib, zipfile, shutil\n', 'import polars as pl\n',
              'root = Path.cwd()\n', 'if not (root / "RELEASE_MANIFEST.json").exists():\n',
              '    matches = list(Path("/kaggle/input").rglob("RELEASE_MANIFEST.json")) if Path("/kaggle/input").exists() else []\n',
              '    if matches: root = matches[0].parent\n', '    elif (root.parent / "RELEASE_MANIFEST.json").exists(): root = root.parent\n',
              '    else: raise FileNotFoundError("Select the extracted release root")\n',
              'manifest = json.loads((root / "RELEASE_MANIFEST.json").read_text())\n',
              'if any(not (root / row["path"]).is_file() for row in manifest["files"]):\n',
              '    expanded = Path("/kaggle/working/expanded-release") if Path("/kaggle/working").exists() else Path("expanded-release")\n',
              '    expanded.mkdir(exist_ok=False)\n',
              '    for row in manifest["files"]:\n',
              '        relative = Path(row["path"])\n',
              '        target = (expanded / relative).resolve()\n',
              '        if not target.is_relative_to(expanded.resolve()): raise ValueError("Invalid release path")\n',
              '        direct = root / relative\n',
              '        if direct.is_file(): content = direct.read_bytes()\n',
              '        else:\n',
              '            archive_path = root / (relative.parts[0] + ".zip")\n',
              '            with zipfile.ZipFile(archive_path) as archive:\n',
              '                candidates = [relative.as_posix(), Path(*relative.parts[1:]).as_posix()]\n',
              '                names = [name for name in candidates if name in archive.namelist()]\n',
              '                if len(names) != 1: raise ValueError("Missing or ambiguous archived member: " + str(relative))\n',
              '                content = archive.read(names[0])\n',
              '        if hashlib.sha256(content).hexdigest() != row["sha256"]: raise ValueError("Checksum mismatch")\n',
              '        target.parent.mkdir(parents=True, exist_ok=True)\n',
              '        target.write_bytes(content)\n',
              '    (expanded / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest))\n',
              '    if (root / "SHA256SUMS.txt").is_file(): shutil.copyfile(root / "SHA256SUMS.txt", expanded / "SHA256SUMS.txt")\n',
              '    root = expanded\n',
              'subprocess.run([sys.executable, str(root / "code/verify_release.py"), str(root)], check=True)\n']},
            {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'id': 'brazil', 'source': [
              'markets = pl.read_parquet(root / "data/results/country-metrics.parquet")\n',
              'markets.filter(pl.col("market_code").is_in(["BR", "US", "GB", "DE", "JP"]))\n']},
            {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'id': 'reproduce', 'source': [
              'output = Path("/kaggle/working/reproduced") if Path("/kaggle/working").exists() else Path("reproduced")\n',
              'subprocess.run([sys.executable, str(root / "code/reproduce.py"), "--release", str(root), "--output", str(output)], check=True)\n']}]}
        (release / 'notebooks').mkdir(exist_ok=refresh)
        (release / 'notebooks/external_validation.ipynb').write_text(json.dumps(notebook, indent=2), encoding='utf-8')
        pl.DataFrame(dictionary).unique().sort('table', 'column').write_csv(release / 'TABLE_SCHEMAS.csv')
        (release / 'DATA_DICTIONARY.md').write_text(dictionary_text(metrics), encoding='utf-8')
        (release / 'CITATION.cff').write_text('cff-version: 1.2.0\nmessage: "Please cite this research dataset and its release manifest."\ntitle: "PromiscuidadeMusical: Verified Lyrical Themes and Social Context"\nauthors:\n  - name: "PromiscuidadeMusical research project"\nversion: "1.0.0"\ndate-released: "2026-10-11"\nlicense: "CC-BY-4.0"\n', encoding='utf-8')
        (release / '.gitignore').write_text('__pycache__/\n.venv/\n.env\nreproduced/\nreproduced-figures/\n', encoding='utf-8')
        if platform == 'kaggle':
            metadata = {'title': 'PromiscuidadeMusical: Lyrics and Social Context',
              'id': 'YOUR_KAGGLE_USERNAME/promiscuidade-musical-verified-lyrics-atlas',
              'licenses': [{'name': 'CC-BY-4.0'}], 'subtitle': '26 lyrical dimensions, 68 markets, global trends and social context',
              'description': (release / 'README.md').read_text(encoding='utf-8')}
            assert 6 <= len(metadata['title']) <= 50 and 20 <= len(metadata['subtitle']) <= 80
            (release / 'dataset-metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        files = [{'path': p.relative_to(release).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(release.rglob('*'))
                 if p.is_file() and '__pycache__' not in p.parts and p.name not in ['RELEASE_MANIFEST.json', 'SHA256SUMS.txt'] and not (platform == 'kaggle' and p.name == 'dataset-metadata.json')]
        if platform == 'github' and any(f['bytes'] > 100 * 1024**2 for f in files):
            raise ValueError('GitHub ordinary-file size limit exceeded')
        manifest = {'version': '1.0.0', 'platform': platform, 'prepared_utc': datetime.now(UTC).isoformat(),
          'database_snapshot_utc': source_manifest['database_snapshot_utc'], 'expert_verification': 'completed',
          'licenses': {'original_data_documents': 'CC-BY-4.0', 'original_code': 'MIT', 'upstream': 'retained separately'},
          'counts': {'full_corpus_recordings': full.height, 'native_classification_ids': native.height, 'markets': 68, 'country_years': 386,
                     'membership_rows': membership.height, 'dimensions': len(metrics), 'search_observations': search.height},
          'withheld': ['raw copyrighted lyrics', 'bulk original chart provider dumps', 'credentials', 'database/runtime/backup clusters',
                       'cloud account and billing ledgers', 'dated operational diagnostics'],
          'files': files}
        (release / 'RELEASE_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        (release / 'SHA256SUMS.txt').write_text('\n'.join(f["sha256"] + '  ' + f['path'] for f in files) + '\n', encoding='utf-8')
        manifests.append(manifest)
    # ZIP archives contain only the curated release, never the workspace.
    packages = destination / 'packages'
    packages.mkdir(exist_ok=refresh)
    for platform in ['github', 'kaggle']:
        with zipfile.ZipFile(packages / (platform + '-research-release-v1.zip'), 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            release = destination / platform
            manifest = json.loads((release / 'RELEASE_MANIFEST.json').read_text())
            allowed = [f['path'] for f in manifest['files']] + ['RELEASE_MANIFEST.json', 'SHA256SUMS.txt']
            if platform == 'kaggle':
                allowed.append('dataset-metadata.json')
            for relative in sorted(allowed):
                archive.write(release / relative, relative)
    overview = {'version': '1.0.0', 'packages': [{'platform': m['platform'], 'files': len(m['files']),
                 'uncompressed_bytes': sum(f['bytes'] for f in m['files']),
                 'zip_bytes': (packages / (m['platform'] + '-research-release-v1.zip')).stat().st_size,
                 'sha256': digest(packages / (m['platform'] + '-research-release-v1.zip'))} for m in manifests]}
    (destination / 'CONSOLIDATION_REPORT.json').write_text(json.dumps(overview, indent=2), encoding='utf-8')
    print(json.dumps(overview, indent=2))


def dictionary_text(metrics):
    return '''# Data dictionary

`TABLE_SCHEMAS.csv` describes every input column's stored type and row count.

- **recording_id**: normalized native Spotify recording identifier; not a listener.
- **research_recording_id**: opaque canonical research identity in the full corpus.
- **lyrics_sha256**: hash of the frozen original lyric version, whose text is withheld.
- **chart-membership**: unique provider/platform/chart-family/market/year/recording
  presence. Contains no bulk raw ranks, streams, artist biography or lyric text.
- **market_code / year**: circulation market and chart observation year.
- **classified_tracks / chart_tracks / coverage**: distinct scored/observed recording
  counts and their ratio at that table's grain.
- **[dimension]_positive / [dimension]_pct**: count and percentage with intensity >=2;
  missing annotations never receive score zero.
- **external-context**: exact-reference-year numeric observations, units, attribution,
  retrieval dates and privately retained original source hashes. `source_artifact_ref`
  is a hash reference; it does not point to an included original provider file.
- **search-observations**: query-local samples; keep language, comparison_group,
  sampling periods, censoring status and original source hash.
- **global-patterns**: annual fixed-market means/medians/quartiles, paired changes,
  source sensitivity and fixed-sample social correlations. Quartiles are not CIs.
- **models**: all baseline, adjusted and 70%-coverage search models, samples and
  exclusions, with coefficients, clustered intervals and full-family BH q values.
- **categorical codes**: consent, target gender, representation roles, antisocial
  stances. Mention and endorsement remain separate.

## Intensity dimensions

''' + '\n'.join('- `' + m + '` (integer 0–3)' for m in metrics) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'publication')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    main(args.output, args.refresh)
