"""Audit revised manuscript against frozen counts and saved model samples."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
import numpy as np
import polars as pl
import statsmodels.api as sm

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    tex=(HERE/'article.tex').read_text(encoding='utf-8')
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.path.append(str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages'))
        from pypdf import PdfReader
    pdf=PdfReader(HERE/'article.pdf')
    text='\f'.join(page.extract_text() for page in pdf.pages)+'\f'
    text=unicodedata.normalize('NFKC',text).replace('\u2212','-').replace('-\n','')
    compact=re.sub(r'\s+',' ',text)
    assert '29.2%' not in compact and '29.2\\%' not in tex
    assert 'Streaming Longevity' not in text and 'East Asia' not in text
    assert '@@' not in tex and not re.search(r'\[\?\?\]',text)
    assert r'\usepackage{titlesec,indentfirst}' in tex and r'\titlespacing*' not in tex
    assert '100%ofthisintendedcorpus' in re.sub(r'\s+','',compact)
    assert 'source records' in compact and '154,964' in compact and '153,501' in compact
    assert 'before geographical restrictions' in compact
    assert len(re.findall(r'\\bibitem\{',tex))==14
    assert len(re.findall(r'\\label\{fig:',tex))==7
    assert len(re.findall(r'\\label\{tab:',tex))==6
    assert 'Overfull' not in (HERE/'article.log').read_text(encoding='utf-8')
    labels=pl.read_parquet(HERE/'analysis-final/native-id-annotations.parquet')
    catalog=pl.read_parquet(ROOT/'data/derived/research_quality/country-all-history-20261011-022524/unique-chart-track-market-year-source.parquet')
    pairs=catalog.filter((pl.col('origin_platform')=='SPOTIFY')&~pl.col('market_code').is_in(['GLOBAL','HK','PR'])).select('market_code','chart_track_id').unique()
    matched=pairs.join(labels,on='chart_track_id',validate='m:1')
    assert matched.height==461447 and matched['chart_track_id'].n_unique()==153501
    metrics=pl.read_csv(HERE/'analysis-final/all-dimensions.csv')['metric'].to_list()
    assert matched.select(metrics).null_count().row(0)==(0,)*26
    assert matched['market_code'].n_unique()==68
    assert pl.read_csv(HERE/'analysis-final/country-metrics.csv')['classified_tracks'].sum()==matched.height
    estimates=pl.read_csv(HERE/'social-revision/focused-models.csv')
    for theme in ['materialism','misogyny','violence']:
        frame=pl.read_csv(HERE/'social-revision'/f'{theme}-model-sample.csv').to_pandas()
        assert frame['market_code'].is_unique
        for spec in ['unadjusted','adjusted']:
            columns=['context_z']+(['log_income','internet_users','rap_share','untagged_share','shared_share'] if spec=='adjusted' else [])
            model=sm.OLS(frame[theme+'_pct'],sm.add_constant(frame[columns])).fit(cov_type='HC3',use_t=True)
            row=estimates.filter((pl.col('theme')==theme)&(pl.col('specification')==spec)).to_dicts()[0]
            assert len(frame)==row['n'] and np.isclose(model.params['context_z'],row['beta'],atol=1e-10)
            assert np.allclose(model.conf_int().loc['context_z'],[row['lower'],row['upper']],atol=1e-10)
    paired=pl.read_csv(HERE/'social-revision/paired-search-sample.csv')
    assert paired.height==232 and paired['market_code'].n_unique()==47
    assert paired.select('market_code','year').unique().height==paired.height
    assert paired.group_by('market_code').len()['len'].min()>=4
    standard=paired.group_by('market_code').agg(pl.col('english_z').std(),pl.col('local_z').std())
    assert np.allclose(standard['english_z'],1) and np.allclose(standard['local_z'],1)
    assert paired.select('english_z','local_z').null_count().row(0)==(0,0)
    search=pl.read_csv(HERE/'social-revision/paired-search-models.csv')
    assert search.height==4 and search['p_holm'].min()>.05
    assert '+0.024' in text and '-0.182' in text
    for item in json.loads((HERE/'social-revision/manifest.json').read_text())['inputs']:
        assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256']
    manifest=dict(revised_date_local='2026-10-12',generated_utc=datetime.now(timezone.utc).isoformat(),
        pages=text.count('\f'),markets=68,dimensions=26,references=14,figures=7,tables_excluding_atlas=6,
        database_snapshot_utc='2026-10-11 23:39:03.970865+00:00',
        checks=['Frozen classified geography independently joined: 153501 IDs / 461447 pairs / 68 markets / all 26 scores present',
        'All six focused coefficients and HC3 intervals independently refit from saved samples',
        'Four search models use identical 232 cells / 47 markets; both indices have unit SD per market',
        'Rendered PDF contains updated coefficients, corrected populations, intended-corpus wording and no forbidden exclusion percentage',
        'No unresolved placeholders, undefined references or layout overflows',
        'Final PDF pages rendered with Poppler and visually inspected',
        'No commit, branch switch, provider call or database modification'],
        independent_validation='Reviewer-level accuracy and actual lyric languages remain unavailable; explicitly disclosed',
        social_inference='Exploratory, post hoc; measured adjustment is incomplete and cannot identify causality',
        files=[])
    outputs=[HERE/'article.pdf',HERE/'article.tex',HERE/'article.template.tex',HERE/'compose_article.py',HERE/'plot_global_patterns.py',HERE/'plot_chart_exposure.py',HERE/'revision-methods.tex',HERE/'revision-results.template.tex',HERE/'social-revision.tex',HERE/'analyze_social_revision.py',Path(__file__),HERE/'README.md']
    outputs+=sorted((HERE/'social-revision').glob('*'))+sorted((HERE/'figures').glob('*'))
    manifest['files']=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in outputs if p.is_file()]
    (HERE/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'},indent=2))

if __name__=='__main__':main()
