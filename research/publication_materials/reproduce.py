"""Recalculate published results from public recording tables, offline."""
import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import spearmanr

from article_context import export_crossings
from historical_models import export_historical_models
from historical_panel import export_historical_panel
from verify_release import verify

FOCUS = ['explicitness', 'objectification', 'misogyny', 'materialism', 'infidelity',
         'casual_sex', 'transactional_sex', 'drugs_alcohol', 'violence', 'crime']
SOCIAL = ['gdp_pc_ppp_constant', 'gini', 'youth_unemployment', 'urban_population',
          'internet_users', 'fixed_broadband', 'gender_inequality_index', 'sigi_2019',
          'homicide_unodc_total', 'homicide_unodc_female', 'homicide_unodc_female_intimate_partner_family',
          'ooni_anomaly_pct_valid_tests', 'ooni_confirmed_pct_valid_tests']


def aggregate(pairs, groups, labels, metrics):
    totals = pairs.group_by(groups).agg(pl.len().alias('chart_tracks'))
    joined = pairs.join(labels, on='recording_id', how='inner', validate='m:1')
    expressions = [pl.len().alias('classified_tracks')]
    for metric in metrics:
        expressions += [(pl.col(metric) >= 2).sum().alias(metric + '_positive'),
                        (100 * (pl.col(metric) >= 2).mean()).alias(metric + '_pct')]
    return totals.join(joined.group_by(groups).agg(expressions), on=groups, how='left').with_columns(
        (pl.col('classified_tracks') / pl.col('chart_tracks')).alias('coverage')).sort(groups)


def compare(expected, actual, keys, columns, label, tolerance=1e-8):
    if expected.height != actual.height:
        raise ValueError('Row mismatch: ' + label)
    joined = expected.select(*keys, *columns).join(actual.select(*keys, *columns), on=keys, suffix='_new', validate='1:1')
    if joined.height != expected.height:
        raise ValueError('Key mismatch: ' + label)
    for column in columns:
        left, right = joined[column].to_numpy(), joined[column + '_new'].to_numpy()
        if not np.allclose(left, right, atol=tolerance, rtol=tolerance, equal_nan=True):
            raise ValueError('Published-value mismatch: ' + label + '/' + column)


def main(root, output):
    verify(root)
    if output.exists():
        raise ValueError('Output already exists; choose a new directory')
    output.mkdir(parents=True)
    inputs, published = root / 'data/inputs', root / 'data/results'
    metrics = list(json.loads((root / 'taxonomy.json').read_text())['dimensions'])
    labels = pl.read_parquet(inputs / 'native-classifications.parquet').select('recording_id', *metrics)
    membership = pl.read_parquet(inputs / 'chart-membership.parquet')
    pairs = membership.select('market_code', 'recording_id').unique()
    annual = aggregate(membership.select('market_code', 'year', 'recording_id').unique(), ['market_code', 'year'], labels, metrics)
    countries = aggregate(pairs, ['market_code'], labels, metrics)
    numeric = ['chart_tracks', 'classified_tracks', 'coverage'] + [m + s for m in metrics for s in ['_positive', '_pct']]
    compare(pl.read_parquet(published / 'country-metrics.parquet'), countries, ['market_code'], numeric, 'countries')
    compare(pl.read_parquet(published / 'annual-country-metrics.parquet'), annual, ['market_code', 'year'], numeric, 'annual')
    for name, frame in [('country-metrics', countries), ('annual-country-metrics', annual)]:
        frame.write_csv(output / (name + '.csv'))
    full = pl.read_parquet(inputs / 'full-corpus-classifications.parquet')
    global_stats = pl.DataFrame([{'metric': m, 'n': full.height, 'positive': (full[m] >= 2).sum(),
                                'pct': 100 * (full[m] >= 2).mean(), 'mean': full[m].mean()} for m in metrics])
    compare(pl.read_parquet(published / 'all-dimensions.parquet'), global_stats, ['metric'], ['n', 'positive', 'pct', 'mean'], 'full corpus')
    global_stats.write_csv(output / 'all-dimensions.csv')
    codes = pl.read_parquet(inputs / 'recording-categorical-codes.parquet')
    categories = []
    for variable in ['consent', 'target_gender', 'drugs_alcohol_stance', 'crime_stance', 'violence_stance', 'weapons_stance']:
        for row in codes.group_by(variable).len().to_dicts():
            categories.append(dict(variable=variable, category=row[variable], count=row['len'], n=codes.height, pct=100 * row['len'] / codes.height))
    category_stats = pl.DataFrame(categories)
    compare(pl.read_parquet(published / 'categorical-distributions.parquet'), category_stats,
            ['variable', 'category'], ['count', 'n', 'pct'], 'categorical coding')
    category_stats.write_csv(output / 'categorical-distributions.csv')
    observations = pl.read_parquet(inputs / 'external-context.parquet')
    indicators = json.loads((root / 'context-indicators.json').read_text())
    export_crossings(annual, observations, indicators, output / 'context')
    context = pl.read_parquet(output / 'context/country-year-crossings.parquet')
    records = []
    for year in range(2017, 2022):
        for m in metrics:
            for indicator in SOCIAL:
                sample = context.filter((pl.col('year') == year) & (pl.col('classified_tracks') >= 300)).select(
                    'market_code', 'coverage', m + '_pct', indicator).drop_nulls()
                valid = sample.height >= 10 and sample[indicator].n_unique() > 1 and sample[m + '_pct'].n_unique() > 1
                rho = float(spearmanr(sample[m + '_pct'], sample[indicator]).statistic) if valid else None
                records.append(dict(year=year, metric=m, context=indicator, n=sample.height, rho=rho))
    social = pl.DataFrame(records)
    compare(pl.read_parquet(published / 'social-context/all-theme-social-associations.parquet'), social,
            ['year', 'metric', 'context'], ['n', 'rho'], 'social matrix')
    social.write_csv(output / 'all-theme-social-associations.csv')
    observations = pl.read_parquet(inputs / 'search-observations.parquet')
    export_historical_panel(annual, observations, output / 'search')
    trajectories = pl.read_parquet(output / 'search/country-year-trends.parquet').join(
        context.select('market_code', 'year', 'internet_users', 'gdp_pc_ppp_constant'), on=['market_code', 'year'], validate='m:1')
    trajectories = trajectories.drop([m + '_pct' for m in metrics if m not in FOCUS])
    export_historical_models(trajectories, output / 'models')
    compare(pl.read_parquet(published / 'models/historical-associations.parquet'),
            pl.read_parquet(output / 'models/historical-associations.parquet'), ['model_id'],
            ['n_countries', 'n_country_years', 'coefficient', 'ci_lower', 'ci_upper', 'q_value_bh'], 'search models')
    balanced = annual.filter(pl.col('year').is_in(range(2017, 2022)) & (pl.col('classified_tracks') >= 300) & (pl.col('coverage') >= .5))
    markets = balanced.group_by('market_code').agg(pl.col('year').n_unique().alias('years')).filter(pl.col('years') == 5)['market_code']
    balanced = balanced.filter(pl.col('market_code').is_in(markets.implode()))
    trends = []
    for year in range(2017, 2022):
        f = balanced.filter(pl.col('year') == year)
        for m in metrics:
            v = f[m + '_pct']
            trends.append(dict(panel='combined55', year=year, metric=m, markets=f.height,
                               mean_pct=v.mean(), median_pct=v.median(), p25_pct=v.quantile(.25, interpolation='linear'),
                               p75_pct=v.quantile(.75, interpolation='linear')))
    trends = pl.DataFrame(trends)
    expected = pl.read_parquet(published / 'global-patterns/annual-global-trends.parquet').filter(pl.col('panel') == 'combined55')
    compare(expected, trends, ['panel', 'year', 'metric'], ['markets', 'mean_pct', 'median_pct', 'p25_pct', 'p75_pct'], 'global panel')
    trends.write_csv(output / 'annual-global-trends.csv')
    # Recalculate source/chart-family sensitivities and distinct-recording pooling.
    universe = sorted(markets.to_list())
    base = membership.filter(pl.col('market_code').is_in(universe) & pl.col('year').is_in(range(2017, 2022)))
    source_annual = {
        'top200_union': aggregate(base.filter(pl.col('chart_family') == 'TOP_200').select('market_code', 'year', 'recording_id').unique(), ['market_code', 'year'], labels, metrics),
        'mgd_top200': aggregate(base.filter((pl.col('provider') == 'MGD') & (pl.col('chart_family') == 'TOP_200')).select('market_code', 'year', 'recording_id').unique(), ['market_code', 'year'], labels, metrics),
        'kaggle_viral50': aggregate(base.filter(pl.col('chart_family') == 'VIRAL_50').select('market_code', 'year', 'recording_id').unique(), ['market_code', 'year'], labels, metrics)}
    declared_panels = json.loads((root / 'global-panels.json').read_text())['panels']
    all_trends = []
    for panel_name, panel_markets in declared_panels.items():
        if panel_name.startswith('top200_matched'):
            source = source_annual['top200_union']
        elif panel_name.startswith('viral50_matched'):
            source = source_annual['kaggle_viral50']
        elif panel_name in source_annual:
            source = source_annual[panel_name]
        else:
            source = annual
        frame = source.filter(pl.col('market_code').is_in(panel_markets) & pl.col('year').is_in(range(2017, 2022)))
        if frame.height != len(panel_markets) * 5:
            raise ValueError('Unbalanced global panel: ' + panel_name)
        for year in range(2017, 2022):
            f = frame.filter(pl.col('year') == year)
            for metric in metrics:
                v = f[metric + '_pct']
                all_trends.append(dict(panel=panel_name, year=year, metric=metric, markets=f.height,
                    mean_pct=v.mean(), median_pct=v.median(), p25_pct=v.quantile(.25, interpolation='linear'),
                    p75_pct=v.quantile(.75, interpolation='linear')))
    all_trends = pl.DataFrame(all_trends)
    compare(pl.read_parquet(published / 'global-patterns/annual-global-trends.parquet'), all_trends,
        ['panel', 'year', 'metric'], ['markets', 'mean_pct', 'median_pct', 'p25_pct', 'p75_pct'], 'all global source sensitivities')
    all_trends.write_csv(output / 'all-global-trends.csv')
    pool = aggregate(base.select('year', 'recording_id').unique(), ['year'], labels, metrics)
    compare(pl.read_parquet(published / 'global-patterns/distinct-recording-year-pool.parquet'), pool, ['year'], numeric, 'distinct-recording pool')
    pool.write_csv(output / 'distinct-recording-year-pool.csv')
    result = {'status': 'passed', 'markets': countries.height, 'country_years': annual.height,
              'global_panel_markets': len(markets), 'dimensions': len(metrics), 'social_cells': social.height,
              'global_sensitivity_panels': len(declared_panels), 'search_models': 30, 'provider_calls': 0, 'database_required': False}
    (output / 'REPRODUCTION_REPORT.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.release, args.output)
