"""Reproduce manuscript extensions from frozen data, without provider or DB calls.

Recording-cluster Poisson bootstrap preserves all appearances of a shared song.
Language is deliberately unresolved: national language is not lyric language.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import polars as pl
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.spatial.distance import pdist, squareform
import statsmodels.formula.api as smf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'revision-analysis'
SEED = 20261012
REGIONS = {
    'Latin America': 'AR BO BR CL CO CR DO EC GT HN MX PA PE PY SV UY'.split(),
    'Nordic countries': 'DK FI IS NO SE'.split(),
    'East Asia': 'JP TW'.split(),
    'Southeast Asia': 'ID MY PH SG TH'.split(),
    'Anglophone markets': 'AU CA GB IE NZ US'.split(),
}
FOCUS = ['wealth_as_status', 'weapons', 'romantic_affection', 'materialism', 'crime']

def write(frame, name):
    frame.write_csv(OUT / (name + '.csv'))
    frame.write_parquet(OUT / (name + '.parquet'))

def genre_group(tags):
    # One exclusive broad group, with explicit priority; tags are artist-derived.
    text = ' '.join(tags).lower()
    for group, words in [
        ('rap hip hop', ['hip_hop', 'rap', 'trap', 'drill']),
        ('latin urban funk', ['reggaeton', 'funk', 'dembow']),
        ('country sertanejo', ['country', 'sertanejo', 'agronejo']),
        ('rock metal', ['rock', 'metal', 'punk']),
        ('dance electronic', ['dance', 'edm', 'house', 'electro', 'techno']),
        ('soul rnb', ['r&b', 'rnb', 'soul']),
        ('pop', ['pop']),
    ]:
        if any(word in text for word in words):
            return group
    return 'other tagged' if tags else 'untagged'

def main():
    OUT.mkdir(exist_ok=True)
    metrics = pl.read_csv(HERE / 'analysis-final/all-dimensions.csv')['metric'].to_list()
    labels = pl.read_parquet(HERE / 'analysis-final/native-id-annotations.parquet')
    assert labels['chart_track_id'].n_unique() == labels.height
    old = ROOT / 'data/derived/research_quality/country-all-history-20261011-022524'
    catalog = pl.read_parquet(old / 'unique-chart-track-market-year-source.parquet')
    panel = json.loads((HERE / 'global-patterns/manifest.json').read_text())['panels']['combined55']
    pairs = catalog.filter((pl.col('origin_platform') == 'SPOTIFY') &
        pl.col('market_code').is_in(panel) & pl.col('year').is_in([2017, 2021]))
    pairs = pairs.select('market_code', 'year', 'chart_track_id').unique().join(labels, on='chart_track_id', validate='m:1')
    genres = pl.read_parquet(ROOT / 'data/derived/genre_claims.parquet').group_by('canonical_track_id').agg(pl.col('normalized_genre').unique())
    genre_map = {r['canonical_track_id']: genre_group(r['normalized_genre']) for r in genres.to_dicts()}
    release = pl.read_csv(ROOT / 'mgd/songs/spotify_hit_songs_dataset_complete.csv', separator='\t', infer_schema_length=10000)
    release = release.select(pl.col('song_id').alias('chart_track_id'), pl.col('release_date').str.slice(0, 4).cast(pl.Int32, strict=False).alias('release_year')).unique('chart_track_id')
    first = catalog.filter(pl.col('origin_platform') == 'SPOTIFY').group_by('chart_track_id').agg(pl.col('year').min().alias('first_chart_year'))
    release = release.join(first,on='chart_track_id',how='left',validate='1:1').with_columns(
        pl.when(pl.col('release_year')<=pl.col('first_chart_year')).then(pl.col('release_year')).otherwise(None).alias('release_year')).drop('first_chart_year')
    pairs = pairs.join(release, on='chart_track_id', how='left', validate='m:1').with_columns(
        pl.Series('genre_group', [genre_map.get(x, 'untagged') for x in pairs['chart_track_id']]))
    pairs = pairs.with_columns(pl.when(pl.col('release_year').is_null()).then(pl.lit('unknown'))
        .when(pl.col('release_year') <= 2016).then(pl.lit('through 2016'))
        .when(pl.col('release_year') <= 2018).then(pl.lit('2017 to 2018'))
        .when(pl.col('release_year') <= 2020).then(pl.lit('2019 to 2020'))
        .otherwise(pl.lit('2021 onward')).alias('release_cohort'))
    # Fixed recording labels: decomposition concerns circulating repertoire.
    ids = sorted(pairs['chart_track_id'].unique().to_list())
    idmap = {x: i for i, x in enumerate(ids)}
    ii = np.array([idmap[x] for x in pairs['chart_track_id']])
    markets = sorted(panel)
    mm = np.array([markets.index(x) for x in pairs['market_code']])
    yy = np.array([0 if x == 2017 else 1 for x in pairs['year']])
    cell = mm * 2 + yy
    outcomes = np.column_stack([(pairs[x].to_numpy() >= 2).astype(float) for x in FOCUS])
    rng = np.random.default_rng(SEED)
    boots = []
    for b in range(401):
        weights = np.ones(len(ids)) if b == 0 else rng.poisson(1, len(ids))
        rowweights = weights[ii]
        den = np.bincount(cell, weights=rowweights, minlength=len(markets)*2)
        values = np.column_stack([100*np.bincount(cell, weights=rowweights*outcomes[:,j], minlength=len(markets)*2)/den for j in range(len(FOCUS))])
        boots.append(values.reshape(len(markets), 2, len(FOCUS)))
    boots = np.array(boots)
    regional = []
    regions = {**REGIONS, 'Other panel markets': [m for m in markets if m not in sum(REGIONS.values(), [])]}
    for name, members in regions.items():
        pos = [markets.index(m) for m in members]
        vals = boots[:,pos].mean(axis=1)
        for j, metric in enumerate(FOCUS):
            changes = vals[1:,1,j] - vals[1:,0,j]
            regional.append(dict(region=name, markets=len(pos), members=' '.join(members), metric=metric,
                pct_2017=vals[0,0,j], pct_2021=vals[0,1,j], change_pp=vals[0,1,j]-vals[0,0,j],
                ci_lower=np.quantile(changes,.025), ci_upper=np.quantile(changes,.975)))
    write(pl.DataFrame(regional), 'regional-trends')
    # Symmetric exact decomposition: delta = within groups + group composition.
    decompositions = []
    group_details = []
    for dimension in ['genre_group', 'release_cohort']:
        groups = sorted(pairs[dimension].unique().to_list())
        gg = np.array([groups.index(x) for x in pairs[dimension]])
        gc = (mm*2+yy)*len(groups)+gg
        estimates = []
        rng = np.random.default_rng(SEED+1)
        for b in range(401):
            w = np.ones(len(ids)) if b == 0 else rng.poisson(1,len(ids))
            rw = w[ii]
            counts = np.bincount(gc,weights=rw,minlength=len(markets)*2*len(groups)).reshape(len(markets),2,len(groups))
            shares = counts/counts.sum(axis=2,keepdims=True)
            result=[]
            for j in range(len(FOCUS)):
                num = np.bincount(gc,weights=rw*outcomes[:,j],minlength=counts.size).reshape(counts.shape)
                rates=np.divide(100*num,counts,out=np.zeros_like(counts),where=counts>0)
                # If a group is observed in only one year, carry its rate over:
                # all its contribution is then composition, not an invented trend.
                for year in [0,1]:
                    rates[:,year,:]=np.where(counts[:,year,:]>0,rates[:,year,:],rates[:,1-year,:])
                within=((shares[:,0]+shares[:,1])/2*(rates[:,1]-rates[:,0])).sum(axis=1).mean()
                composition=((rates[:,0]+rates[:,1])/2*(shares[:,1]-shares[:,0])).sum(axis=1).mean()
                if b==0:
                    for g,group in enumerate(groups):
                        group_details.append(dict(grouping=dimension,group=group,metric=FOCUS[j],
                            mean_share_2017=shares[:,0,g].mean(),mean_share_2021=shares[:,1,g].mean(),
                            within_pp=(((shares[:,0,g]+shares[:,1,g])/2)*(rates[:,1,g]-rates[:,0,g])).mean(),
                            composition_pp=(((rates[:,0,g]+rates[:,1,g])/2)*(shares[:,1,g]-shares[:,0,g])).mean()))
                result.append([within,composition])
            estimates.append(result)
        estimates=np.array(estimates)
        for j,metric in enumerate(FOCUS):
            total=estimates[0,j].sum()
            assert abs(total-(boots[0,:,1,j]-boots[0,:,0,j]).mean())<1e-8
            decompositions.append(dict(grouping=dimension,metric=metric,total_pp=total,
                within_pp=estimates[0,j,0],within_lower=np.quantile(estimates[1:,j,0],.025),within_upper=np.quantile(estimates[1:,j,0],.975),
                composition_pp=estimates[0,j,1],composition_lower=np.quantile(estimates[1:,j,1],.025),composition_upper=np.quantile(estimates[1:,j,1],.975)))
    write(pl.DataFrame(decompositions),'composition-decomposition')
    write(pl.DataFrame(group_details),'decomposition-group-details')
    # Theme clustering uses all 68 selected repertoires, all 26 dimensions.
    countries=pl.read_parquet(HERE/'analysis-final/country-metrics.parquet').sort('market_code')
    x=countries.select([m+'_pct' for m in metrics]).to_numpy()
    z=(x-x.mean(axis=0))/x.std(axis=0)
    tree=linkage(z,method='ward'); distances=squareform(pdist(z))
    quality=[]
    for k in range(2,9):
        c=cut_tree(tree,n_clusters=k).ravel()
        silhouette=[]
        for i in range(len(c)):
            own=(c==c[i]);own[i]=False
            if own.sum()==0: silhouette.append(0.);continue
            a=distances[i,own].mean()
            b=min(distances[i,c==other].mean() for other in set(c) if other!=c[i])
            silhouette.append((b-a)/max(a,b))
        quality.append(dict(k=k,silhouette=float(np.mean(silhouette))))
    best=max(quality,key=lambda r:r['silhouette'])
    c=cut_tree(tree,n_clusters=best['k']).ravel()+1
    write(countries.select('market_code').with_columns(pl.Series('cluster',c)),'theme-clusters')
    write(pl.DataFrame(quality),'cluster-quality')
    # Window-limited observed days, counted over years, not calendar span.
    exposure=pl.read_parquet(HERE/'chart-exposure/classified-track-market-year.parquet')
    longevity=exposure.group_by('market_code','chart_track_id').agg(pl.col('chart_days').sum(),pl.col('year').min().alias('first_observed_year'),*[pl.col(m).first() for m in metrics])
    longevity=longevity.join(release,on='chart_track_id',how='left',validate='m:1').with_columns(
        pl.Series('genre_group',[genre_map.get(x,'untagged') for x in longevity['chart_track_id']]))
    longevity=longevity.with_columns(pl.when(pl.col('release_year').is_null()).then(pl.lit('unknown')).when(pl.col('release_year')<=2016).then(pl.lit('through 2016')).otherwise(pl.col('release_year').cast(pl.String)).alias('release_cohort'))
    summaries=[]
    for metric in ['romantic_affection','explicitness','conspicuous_consumption']:
        for positive in [False,True]:
            sample=longevity.filter((pl.col(metric)>=2)==positive)
            summaries.append(dict(metric=metric,substantial=positive,recording_market_pairs=sample.height,
                median_days=sample['chart_days'].median(),p25_days=sample['chart_days'].quantile(.25),p75_days=sample['chart_days'].quantile(.75)))
    write(pl.DataFrame(summaries),'longevity-descriptive')
    frame=longevity.to_pandas()
    for m in ['romantic_affection','explicitness','conspicuous_consumption']:frame[m+'_high']=(frame[m]>=2).astype(int)
    model=smf.ols('np.log1p(chart_days) ~ romantic_affection_high + explicitness_high + conspicuous_consumption_high + C(market_code) + C(first_observed_year) + C(genre_group) + C(release_cohort)',data=frame).fit(cov_type='cluster',cov_kwds={'groups':frame['chart_track_id']})
    ci=model.conf_int()
    write(pl.DataFrame([dict(metric=m,coefficient=model.params[m+'_high'],ci_lower=ci.loc[m+'_high',0],ci_upper=ci.loc[m+'_high',1],n=len(frame),unique_recordings=frame['chart_track_id'].nunique()) for m in ['romantic_affection','explicitness','conspicuous_consumption']]),'longevity-adjusted')
    contrasts=[]
    for other in ['explicitness','conspicuous_consumption']:
        test=model.t_test('romantic_affection_high - '+other+'_high = 0')
        interval=test.conf_int()[0]
        contrasts.append(dict(contrast='romantic_affection minus '+other,coefficient=float(np.asarray(test.effect).item()),ci_lower=float(interval[0]),ci_upper=float(interval[1])))
    write(pl.DataFrame(contrasts),'longevity-contrasts')
    # Provisional independent audit draw: one representative market per recording.
    excluded=set(pl.read_csv(ROOT/'data/derived/research_quality/classification-review-20261010-143717/review-sheet.csv')['document_id'])
    audit_pairs=catalog.filter((pl.col('origin_platform')=='SPOTIFY') & ~pl.col('market_code').is_in(['GLOBAL','HK','PR'])).select('chart_track_id','market_code').unique().join(labels,on='chart_track_id',validate='m:1')
    audit_pairs=audit_pairs.with_columns(pl.Series('genre_group',[genre_map.get(x,'untagged') for x in audit_pairs['chart_track_id']]))
    candidates=audit_pairs.filter(~pl.col('document_id').is_in(excluded)).select('chart_track_id','document_id','lyrics_hash','market_code','genre_group',*metrics).unique(['chart_track_id','market_code'])
    def h(key):return hashlib.sha256((str(SEED)+key).encode()).hexdigest()
    candidates=candidates.with_columns(pl.Series('draw_key',[h(r['chart_track_id']+r['market_code']) for r in candidates.to_dicts()])).sort('draw_key').unique('chart_track_id',keep='first',maintain_order=True)
    candidates=candidates.with_columns(pl.max_horizontal([pl.col(m) for m in metrics]).alias('intensity_stratum'),pl.lit('unresolved').alias('language_stratum'))
    # Equal capped allocation by joint stratum; retain inclusion weights.
    strata=candidates.partition_by(['market_code','genre_group','intensity_stratum'],maintain_order=True)
    selected=[]
    for s in strata:
        n=min(2,s.height)
        selected.append(s.head(n).with_columns(pl.lit(s.height).alias('stratum_population'),pl.lit(n).alias('stratum_draw'),pl.lit(n/s.height).alias('inclusion_probability')))
    audit=pl.concat(selected).sort('draw_key')
    write(audit,'audit-key-private')
    blank=audit.select('chart_track_id','document_id','lyrics_hash','market_code','genre_group','language_stratum').with_columns(pl.lit('').alias('confirmed_language'),pl.lit('').alias('identity_verdict'),pl.lit('').alias('notes'),*[pl.lit('').alias(m) for m in metrics])
    for reviewer in [1,2]:blank.write_csv(OUT/f'human-reviewer-{reviewer}-blind.csv')
    info=dict(seed=SEED,bootstrap_replicates=400,bootstrap_unit='recording ID shared across all market/year appearances',
        analytical_corpus='153501 classified recording IDs; 461447 recording-market pairs; exclusions remain in selection flow',
        regions=regions,clustering=best,genre_priority='rap hip hop; latin urban funk; country sertanejo; rock metal; dance electronic; soul rnb; pop; other tagged; untagged',
        genre_tagged_endpoint_pairs=pairs.filter(pl.col('genre_group')!='untagged').height,endpoint_pairs=pairs.height,
        release_known_endpoint_pairs=pairs.filter(pl.col('release_year').is_not_null()).height,
        validation=dict(status='pending human annotation and language metadata; provisional draw only',sample_size=audit.height,human_reviews_completed=0,prior_review_documents_excluded=len(excluded),
            sampling='one hashed representative market per recording; two records per market x exclusive genre x maximum ordinal intensity cell, capped by cell size; no human result available',language_stratification='not possible yet; all unresolved; revise draw after independently confirming languages'),
        limits=['CIs condition on frozen classifications and observed markets, not human coding accuracy or national population sampling','Genre and release decompositions are separate, non-additive, metadata-dependent descriptions','Clusters are exploratory, k chosen by silhouette; no stability validation','Longevity is observed 2017-2021 chart days, not uncensored lifetime or a causal effect'])
    info['inputs']=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [Path(__file__),HERE/'analysis-final/native-id-annotations.parquet',old/'unique-chart-track-market-year-source.parquet',ROOT/'data/derived/genre_claims.parquet',ROOT/'mgd/songs/spotify_hit_songs_dataset_complete.csv',HERE/'chart-exposure/classified-track-market-year.parquet']]
    (OUT/'manifest.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info,indent=2))

if __name__=='__main__':main()
