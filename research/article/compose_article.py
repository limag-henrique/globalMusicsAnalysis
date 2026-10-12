"""Render a standalone LaTeX manuscript from the frozen article analysis."""
from pathlib import Path
import json
import polars as pl
import pycountry

HERE = Path(__file__).resolve().parent
DATA = HERE / 'analysis-final'
LABELS = {
 'explicitness':'Sexual explicitness','sexual_desire':'Sexual desire','sexual_innuendo':'Sexual innuendo',
 'explicit_sexual_act':'Explicit sexual acts','explicit_sexual_anatomy':'Sexual anatomy',
 'romantic_affection':'Romantic affection','heartbreak':'Heartbreak','infidelity':'Infidelity',
 'transactional_sex':'Transactional sex','casual_sex':'Casual sex','jealousy_possession':'Jealousy / possession',
 'reciprocity':'Reciprocity','objectification':'Objectification','misogyny':'Misogyny',
 'sexual_agency':'Sexual agency','status_symbolization':'Status symbolization','commodification':'Commodification',
 'money_reference':'Money references','materialism':'Materialism','conspicuous_consumption':'Conspicuous consumption',
 'wealth_as_status':'Wealth as status','drugs_alcohol':'Drugs / alcohol','crime':'Crime','violence':'Violence',
 'weapons':'Weapons','territorial_identity':'Territorial identity'}

def main():
    global_stats=pl.read_csv(DATA/'all-dimensions.csv').to_dicts()
    countries=pl.read_csv(DATA/'country-metrics.csv')
    br=countries.filter(pl.col('market_code')=='BR').to_dicts()[0]
    models=pl.read_csv(DATA/'models/historical-associations.csv')
    associations=pl.read_csv(HERE/'social-context/all-theme-social-associations.csv')
    manifest=json.loads((DATA/'manifest.json').read_text())
    rows=[]
    for code in ['BR','US','GB','DE','FR','ES','PT','JP']:
        r=countries.filter(pl.col('market_code')==code).to_dicts()[0]
        rows.append(f"{code} & {r['classified_tracks']:,} & " +
            ' & '.join(f"{r[m+'_pct']:.1f}" for m in ['explicitness','casual_sex','misogyny','materialism'])+r' \\')
    coords_all=' '.join(f"({r['pct']:.5f},{26-i})" for i,r in enumerate(global_stats))
    coords_br=' '.join(f"({br[r['metric']+'_pct']:.5f},{26-i})" for i,r in enumerate(global_stats))
    ticks=','.join(str(26-i) for i in range(26))
    ticklabels=','.join('{'+LABELS[r['metric']]+'}' for r in global_stats)
    annual=pl.read_csv(DATA/'annual-country-metrics.csv').filter(pl.col('market_code')=='BR').sort('year')
    annual_plots=[]
    for metric,color,mark in [('romantic_affection','blue','*'),('casual_sex','orange','square*'),('explicitness','teal','triangle*'),('materialism','gray','diamond*')]:
        coords=' '.join(f"({r['year']},{r[metric+'_pct']:.5f})" for r in annual.to_dicts())
        annual_plots.append(r'\addplot[color='+color+',mark='+mark+r',thick] coordinates {'+coords+r'};\addlegendentry{'+LABELS[metric]+'}')
    context_rows=[]
    items=[('objectification','gender_inequality_index','Objectification / GII',2021),
       ('misogyny','gender_inequality_index','Misogyny / GII',2021),('objectification','sigi_2019','Objectification / SIGI',2019),
       ('misogyny','sigi_2019','Misogyny / SIGI',2019),('materialism','gini','Materialism / Gini',2021),
       ('materialism','gdp_pc_ppp_constant','Materialism / income (PPP)',2021),
       ('materialism','youth_unemployment','Materialism / youth unemployment',2021),
       ('violence','homicide_unodc_total','Violence / total homicide',2021),('crime','homicide_unodc_total','Crime / total homicide',2021),
       ('violence','homicide_unodc_female','Violence / female homicide',2021),
       ('violence','homicide_unodc_female_intimate_partner_family','Violence / partner-family deaths',2021),
       ('romantic_affection','youth_unemployment','Romance / youth unemployment',2021),
       ('heartbreak','youth_unemployment','Heartbreak / youth unemployment',2021),
       ('reciprocity','gender_inequality_index','Reciprocity / GII',2021),
       ('sexual_agency','gender_inequality_index','Sexual agency / GII',2021),
       ('wealth_as_status','gdp_pc_ppp_constant','Wealth as status / income',2021),
       ('territorial_identity','urban_population','Territorial identity / urbanization',2021),
       ('explicitness','internet_users','Explicitness / internet access',2021),
       ('explicitness','ooni_anomaly_pct_valid_tests','Explicitness / OONI anomalies',2021)]
    for metric,context,label,year in items:
        r=associations.filter((pl.col('metric')==metric)&(pl.col('context')==context)&(pl.col('year')==year)).to_dicts()[0]
        context_rows.append(f"{label} & {year} & {r['n']} & {r['rho']:+.3f}"+r' \\')
    model_rows=[]
    focus=['explicitness','objectification','misogyny','materialism','infidelity','casual_sex','transactional_sex','drugs_alcohol','violence','crime']
    for metric in focus:
        r=models.filter((pl.col('outcome')==metric+'_pct')&(pl.col('specification')=='adjusted')).to_dicts()[0]
        model_rows.append(f"{LABELS[metric]} & {r['coefficient']:+.3f} & [{r['ci_lower']:+.3f}, {r['ci_upper']:+.3f}] & {r['q_value_bh']:.3f}"+r' \\')
    template=(HERE/'article.template.tex').read_text(encoding='utf-8')
    replacements={'COUNTRY_ROWS':'\n'.join(rows),'ALL_COORDS':coords_all,'BR_COORDS':coords_br,
        'DIM_TICKS':ticks,'DIM_LABELS':ticklabels,'ANNUAL_PLOTS':'\n'.join(annual_plots),
        'CONTEXT_ROWS':'\n'.join(context_rows),'MODEL_ROWS':'\n'.join(model_rows)}
    social=pl.read_csv(HERE/'social-revision/focused-models.csv')
    focused=[]
    for theme,label in [('materialism','Materialism / Gini'),('misogyny','Misogyny / GII'),('violence','Violence / log homicide')]:
        cells=[]
        for specification in ['unadjusted','adjusted']:
            r=social.filter((pl.col('theme')==theme)&(pl.col('specification')==specification)).to_dicts()[0]
            cells.append(f"{r['beta']:+.2f} [{r['lower']:+.2f}, {r['upper']:+.2f}]")
        focused.append(f"{label} & {r['n']} & "+' & '.join(cells)+f" & {r['p_holm']:.3f}"+r' \\')
    replacements['SOCIAL_REVISION']=(HERE/'social-revision.tex').read_text(encoding='utf-8').replace('@@FOCUSED_SOCIAL_ROWS@@','\n'.join(focused))
    regional=pl.read_csv(HERE/'revision-analysis/regional-trends.csv')
    regional_rows=[]
    for region in ['Latin America','Nordic countries','East Asia','Southeast Asia','Anglophone markets','Other panel markets']:
        cells=[]
        for metric in ['wealth_as_status','weapons','romantic_affection']:
            r=regional.filter((pl.col('region')==region)&(pl.col('metric')==metric)).to_dicts()[0]
            cells.append(f"{r['change_pp']:+.2f} [{r['ci_lower']:+.2f}, {r['ci_upper']:+.2f}]")
        regional_rows.append(('Japan and Taiwan' if region=='East Asia' else region)+' & '+' & '.join(cells)+r' \\')
    revision_results=(HERE/'revision-results.template.tex').read_text(encoding='utf-8').replace('@@REGIONAL_ROWS@@','\n'.join(regional_rows))
    replacements.update({'LITERATURE_REVIEW':(HERE/'literature-review.tex').read_text(encoding='utf-8'),
        'REVISION_METHODS':(HERE/'revision-methods.tex').read_text(encoding='utf-8'),
        'REVISION_RESULTS':revision_results})
    from plot_global_patterns import latex_figures
    replacements.update(latex_figures())
    from plot_chart_exposure import latex_exposure
    replacements.update(latex_exposure())
    atlas=countries.sort('explicitness_pct',descending=True).with_row_index('explicitness_rank',offset=1)
    atlas_rows=[]
    names={'BO':'Bolivia','TW':'Taiwan','KR':'South Korea','RU':'Russia','VN':'Vietnam','GB':'United Kingdom'}
    for r in atlas.to_dicts():
        country=pycountry.countries.get(alpha_2=r['market_code'])
        name=names.get(r['market_code'],country.name)
        row=f"{r['explicitness_rank']} & {name} ({r['market_code']}) & {r['classified_tracks']:,} & "+' & '.join(f"{r[m+'_pct']:.1f}" for m in ['romantic_affection','explicitness','casual_sex','objectification','misogyny','materialism','violence','crime'])
        if r['market_code']=='BR':row=' & '.join(r'\textbf{'+cell.strip()+'}' for cell in row.split('&'))
        atlas_rows.append(row+r' \\')
    replacements['ATLAS_ROWS']='\n'.join(atlas_rows)
    atlas=atlas.with_columns(pl.Series('market_name',[names.get(c,pycountry.countries.get(alpha_2=c).name) for c in atlas['market_code']]))
    context2021=pl.read_csv(HERE/'social-context/market-context-2021.csv').select('market_code',
        *[pl.col(c).alias('context_2021_'+c) for c in ['gdp_pc_ppp_constant','gini','youth_unemployment','gender_inequality_index','homicide_unodc_total','internet_users','urban_population']])
    atlas=atlas.join(context2021,on='market_code',how='left',validate='1:1')
    for metric in LABELS:
        ranks=atlas.select('market_code',pl.col(metric+'_pct').rank(method='min',descending=True).alias(metric+'_rank'))
        atlas=atlas.join(ranks,on='market_code',validate='1:1')
    atlas.write_csv(HERE/'international-atlas.csv')
    visual_data={'records':atlas.to_dicts(),'labels':LABELS,'snapshot':manifest['database_snapshot_utc']}
    fragment=(HERE/'international-atlas.template.html').read_text(encoding='utf-8').replace('@@DATA@@',json.dumps(visual_data,ensure_ascii=False))
    visual_path=Path('C:/Users/Henrique Lima/.codex/visualizations/2026/10/11/01a12d4e-89a1-75c3-a70e-814dcc61ac52/international-music-atlas.html')
    # The current task only writes artifacts inside this workspace.
    (HERE/'international-atlas.fragment.html').write_text(fragment,encoding='utf-8')
    for key,value in replacements.items():template=template.replace('@@'+key+'@@',value)
    assert '@@' not in template
    (HERE/'article.tex').write_text(template,encoding='utf-8',newline='\n')
    print('Written',HERE/'article.tex','using snapshot',manifest['database_snapshot_utc'])

if __name__=='__main__':main()
