"""Focused adjusted associations and paired local-term search sensitivity.

Only frozen inputs. These are post hoc exploratory models, not causal tests.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import polars as pl
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
from analyze_revision import genre_group

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'social-revision'
OUT.mkdir(exist_ok=True)

def main():
    context = pl.read_csv(HERE/'social-context/market-context-2021.csv')
    exposure = pl.read_parquet(HERE/'chart-exposure/classified-track-market-year.parquet').filter(pl.col('year')==2021)
    tags = pl.read_parquet(ROOT/'data/derived/genre_claims.parquet').group_by('canonical_track_id').agg(pl.col('normalized_genre').unique())
    mapping = {r['canonical_track_id']: genre_group(r['normalized_genre']) for r in tags.to_dicts()}
    exposure = exposure.with_columns(pl.Series('genre_group',[mapping.get(x,'untagged') for x in exposure['chart_track_id']]))
    reach = exposure.group_by('chart_track_id').agg(pl.col('market_code').n_unique().alias('market_reach'))
    exposure = exposure.join(reach,on='chart_track_id',validate='m:1')
    repertoire = exposure.group_by('market_code').agg(
        (100*(pl.col('genre_group')=='rap hip hop').mean()).alias('rap_share'),
        (100*(pl.col('genre_group')=='untagged').mean()).alias('untagged_share'),
        (100*(pl.col('market_reach')>=5).mean()).alias('shared_share'),
        *[(100*(pl.col(m)>=2).mean()).alias(m+'_pct') for m in ['materialism','misogyny','violence']],
        pl.len().alias('classified_n'))
    frame = repertoire.join(context.select('market_code','gini','gender_inequality_index','homicide_unodc_total','gdp_pc_ppp_constant','internet_users'),on='market_code',validate='1:1').to_pandas()
    frame['log_income'] = np.log(frame['gdp_pc_ppp_constant'])
    frame['log_homicide'] = np.log1p(frame['homicide_unodc_total'])
    questions = [('materialism','gini'),('misogyny','gender_inequality_index'),('violence','log_homicide')]
    estimates = []
    for theme, predictor in questions:
        controls = ['log_income','internet_users','rap_share','untagged_share','shared_share']
        sample = frame.dropna(subset=[theme+'_pct',predictor,*controls]).copy()
        # Same sample and predictor SD in the unadjusted and adjusted contrast.
        sample['context_z'] = (sample[predictor]-sample[predictor].mean())/sample[predictor].std(ddof=1)
        sample.to_csv(OUT/(theme+'-model-sample.csv'),index=False)
        for kind, rhs in [('unadjusted','context_z'),('adjusted','context_z + '+' + '.join(controls))]:
            model = smf.ols(theme+'_pct ~ '+rhs,data=sample).fit(cov_type='HC3',use_t=True)
            if np.linalg.matrix_rank(model.model.exog) != model.model.exog.shape[1]:
                raise ValueError('Rank-deficient focused model')
            ci = model.conf_int().loc['context_z']
            estimates.append(dict(theme=theme,predictor=predictor,specification=kind,n=len(sample),
                beta=float(model.params['context_z']),lower=float(ci.iloc[0]),upper=float(ci.iloc[1]),
                p=float(model.pvalues['context_z']),r_squared=float(model.rsquared),
                condition_number=float(model.condition_number),predictor_sd=float(sample[predictor].std(ddof=1))))
    adjusted = [r for r in estimates if r['specification']=='adjusted']
    for r,q in zip(adjusted,multipletests([r['p'] for r in adjusted],method='holm')[1]):r['p_holm']=float(q)
    pl.DataFrame(estimates).write_csv(OUT/'focused-models.csv')
    # Every non-English term is tested separately on a matched English sample.
    trends = pl.read_parquet(ROOT/'data/derived/article-country-context/historical-trends-20261011/country-year-trends.parquet')
    music = pl.read_csv(HERE/'analysis-final/annual-country-metrics.csv')
    trends = trends.drop([c for c in trends.columns if c.endswith('_pct') or c.endswith('_positive') or c in ['classified_tracks','chart_tracks','coverage']]).join(
        music.select('market_code','year','classified_tracks','explicitness_pct','materialism_pct'),on=['market_code','year'],validate='m:1')
    trends = trends.filter(pl.col('year').is_between(2017,2021)&(pl.col('temporal_coverage')>=.8)&(pl.col('classified_tracks')>=300)&pl.col('mean_index').is_not_null())
    search_results=[]
    # English reference uses the original deterministic batch selection.
    english = trends.filter(pl.col('term')=='porn').sort('comparison_group').unique(['market_code','year'],keep='first',maintain_order=True)
    local = trends.filter(pl.col('language')!='en').sort(['market_code','term','language','comparison_group','year']).unique(['market_code','term','language','year'],keep='first',maintain_order=True)
    # Standardize each series before pooling; no comparison of raw search levels.
    local = local.with_columns(((pl.col('mean_index')-pl.col('mean_index').mean().over(['market_code','term','language']))/pl.col('mean_index').std().over(['market_code','term','language'])).alias('local_z'))
    # Equal mean of independently standardized available local terms per market-year.
    local = local.filter(pl.col('local_z').is_finite()).group_by('market_code','year').agg(pl.col('local_z').mean(),pl.col('term').sort().implode().alias('local_terms'))
    paired = english.join(local,on=['market_code','year'],validate='1:1').to_pandas()
    counts = paired.groupby('market_code')['year'].transform('count')
    paired = paired[counts>=4].copy()
    paired['english_z']=paired.groupby('market_code')['mean_index'].transform(lambda x:(x-x.mean())/x.std(ddof=1))
    paired['log_income']=np.log(paired['gdp_pc_ppp_constant'])
    paired=paired.dropna(subset=['english_z','local_z','log_income','internet_users'])
    counts=paired.groupby('market_code')['year'].transform('count')
    paired=paired[counts>=4].copy()
    for column in ['english_z','local_z']:
        paired[column]=paired.groupby('market_code')[column].transform(lambda x:(x-x.mean())/x.std(ddof=1))
    paired=paired.dropna(subset=['english_z','local_z'])
    paired.to_csv(OUT/'paired-search-sample.csv',index=False)
    for theme in ['explicitness','materialism']:
        for spec in ['english_z','local_z']:
            model=smf.ols(theme+'_pct ~ '+spec+' + log_income + internet_users + C(market_code) + C(year)',data=paired).fit(cov_type='cluster',cov_kwds={'groups':paired['market_code']},use_t=True)
            ci=model.conf_int().loc[spec]
            search_results.append(dict(theme=theme,specification=spec,n=len(paired),markets=paired['market_code'].nunique(),beta=float(model.params[spec]),lower=float(ci.iloc[0]),upper=float(ci.iloc[1]),p=float(model.pvalues[spec])))
    for r,q in zip(search_results,multipletests([r['p'] for r in search_results],method='holm')[1]):r['p_holm']=float(q)
    pl.DataFrame(search_results).write_csv(OUT/'paired-search-models.csv')
    local.select('market_code','year','local_terms').write_json(OUT/'local-search-terms.json')
    manifest=dict(status='post hoc exploratory; no causal identification',social_sample='2021 classified MGD Top 200 only; equal market weight',
        controls='log PPP income, internet access, rap/hip-hop share, untagged share, share charting in at least five observed panel markets',
        uncertainty='social HC3 t intervals, Holm across three adjusted tests; search market-cluster t intervals, Holm across four paired tests',
        limitations=['Actual lyric language unavailable; country language is not substituted','Shared-chart share measures circulation, not foreign artist origin','Rap share does not fully adjust all genre composition','Single platform held constant; no cross-platform generalization','Shared recordings create residual between-market dependence in social HC3 intervals','Post hoc hypotheses motivated after viewing original results; independent replication required'],
        search='equal mean of within-series standardized non-English terms; English and local models use identical complete market-years; at least four years per market')
    inputs=[Path(__file__),HERE/'social-context/market-context-2021.csv',HERE/'chart-exposure/classified-track-market-year.parquet',ROOT/'data/derived/genre_claims.parquet',ROOT/'data/derived/article-country-context/historical-trends-20261011/country-year-trends.parquet',HERE/'analysis-final/annual-country-metrics.csv']
    manifest['inputs']=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in inputs]
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(social=estimates,search=search_results),indent=2))

if __name__=='__main__':main()
