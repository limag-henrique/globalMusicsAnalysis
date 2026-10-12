"""Compare repertoire, persistence and classified chart-stream weights."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import polars as pl

HERE=Path(__file__).resolve().parent
DATA=HERE/'chart-exposure'
METRICS=['romantic_affection','heartbreak','explicitness','casual_sex','misogyny','materialism','crime','weapons']
LABELS=['Romance','Heartbreak','Explicitness','Casual sex','Misogyny','Materialism','Crime','Weapons']
WEIGHTS=[('recording','blue','*',.18,'Recording IDs'),('chart_day','orange','square*',0,'Chart days'),('stream','teal','triangle*',-.18,'Chart streams')]

def latex_exposure():
    country=pl.read_csv(DATA/'weighted-country-year.csv')
    global_data=pl.read_csv(DATA/'global-weighted-trends.csv')
    groups=[]
    for place in ['Brazil','51-market mean']:
        groups.append(r'\nextgroupplot[title={'+place+r'},yticklabels={'+(','.join(LABELS) if place=='Brazil' else '')+'}]')
        for weight,color,mark,shift,label in WEIGHTS:
            values=[]
            for i,m in enumerate(METRICS):
                if place=='Brazil':value=country.filter((pl.col('market_code')=='BR')&(pl.col('year')==2021))[m+'_'+weight+'_pct'].item()
                else:value=global_data.filter((pl.col('year')==2021)&(pl.col('metric')==m)&(pl.col('weight')==weight))['mean_pct'].item()
                values.append(f'({value:.6f},{8-i+shift:.2f})')
            groups.append(r'\addplot[only marks,'+color+',mark='+mark+r',mark size=2pt] coordinates {'+' '.join(values)+'};')
    fig=r'''\begin{figure*}[t]
\centering\begin{tikzpicture}
\begin{groupplot}[group style={group size=2 by 1,horizontal sep=14mm},width=.37\textwidth,height=57mm,scale only axis=true,
 xmin=0,xmax=55,ymin=.4,ymax=8.6,xtick={0,10,20,30,40,50},ytick={8,7,6,5,4,3,2,1},
 tick label style={font=\scriptsize},title style={font=\small},xlabel={Theme share (\%)},xlabel style={font=\scriptsize},
 xmajorgrids=true,grid style={gray!18},axis line style={gray}]
'''+ '\n'.join(groups)+r'''
\end{groupplot}\end{tikzpicture}
\caption{Three views of the same classified Top-200 repertoire in 2021. Blue circles count recording IDs equally; orange squares weight their observed chart days; teal triangles weight observed chart streams. The right panel averages the same 51 markets equally. Every denominator contains classified records only. Brazil has 1,035 classified IDs out of 1,382 charted IDs, covering 71.9\% of chart days and 69.4\% of chart streams. Median stream coverage across the 51 markets is 73.1\% (range 45.5--80.9\%). Streams are chart-eligible plays during chart appearances, not people or all Spotify plays.}
\label{fig:chart-exposure}
\end{figure*}'''
    genres=pl.read_csv(DATA/'brazil-genre-thematic-profiles.csv')
    names={'POP':'Pop','AGRONEJO':'Agronejo','ARROCHA':'Arrocha','RAP_HIPHOP':'Rap / hip-hop','FUNK_BR':'Brazilian funk','SERTANEJO_BR':'Sertanejo','ROCK':'Rock','K_POP':'K-pop'}
    rows=[]
    for r in genres.to_dicts():
        rows.append(f"{names[r['normalized_genre']]} & {r['classified_tracks']} & {100*r['classification_coverage']:.1f} & "+
            ' & '.join(f"{r[m+'_pct']:.1f}" for m in ['romantic_affection','explicitness','casual_sex','misogyny','materialism'])+r' \\')
    table=r'''\begin{table}[t]
\caption{Brazilian genre-tag profiles, MGD Top 200, 2017--2021. The eight largest artist-derived tags are selected by charted recording count. $n$: classified IDs; Cov.: classification coverage; R: romance; E: explicitness; C: casual sex; M: misogyny; Mat.: materialism. Theme values are percentages of classified IDs, not genre-wide population estimates. Tags overlap.}
\label{tab:genre-profiles}
\centering\scriptsize\setlength{\tabcolsep}{2.8pt}
\begin{tabular}{@{}lrrrrrrr@{}}\toprule Tag & $n$ & Cov. & R & E & C & M & Mat.\\\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule\end{tabular}
\end{table}'''
    return {'CHART_EXPOSURE_FIGURE':fig,'GENRE_PROFILE_TABLE':table}

def main():
    plt.rcParams.update({'font.size':8,'axes.titlesize':10,'xtick.labelsize':8,'ytick.labelsize':8,'pdf.fonttype':42})
    country=pl.read_csv(DATA/'weighted-country-year.csv');global_data=pl.read_csv(DATA/'global-weighted-trends.csv')
    fig,axes=plt.subplots(1,2,figsize=(7.15,3.1),layout='constrained',sharex=True,sharey=True)
    for ax,place in zip(axes,['Brazil','51-market mean'],strict=True):
        for weight,color,mark,shift,label in WEIGHTS:
            vals=[]
            for m in METRICS:
                value=country.filter((pl.col('market_code')=='BR')&(pl.col('year')==2021))[m+'_'+weight+'_pct'].item() if place=='Brazil' else global_data.filter((pl.col('year')==2021)&(pl.col('metric')==m)&(pl.col('weight')==weight))['mean_pct'].item()
                vals.append(value)
            palette={'blue':'#245581','orange':'#BD5B21','teal':'#187E78'}
            ax.scatter(vals,[8-i+shift for i in range(8)],s=22,color=palette[color],marker={'*':'o','square*':'s','triangle*':'^'}[mark],label=label)
        ax.set_title(place);ax.set_yticks(range(8,0,-1),LABELS);ax.set_xlim(0,55);ax.set_xlabel('Share among classified chart records (%)')
        ax.grid(axis='x',color='#E1E5E9',linewidth=.5);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
    fig.legend(*axes[0].get_legend_handles_labels(),loc='outside upper center',ncol=3,frameon=False)
    paths=[]
    for suffix in ['pdf','svg','png']:
        file=HERE/'figures'/('chart-exposure-weights.'+suffix);fig.savefig(file,bbox_inches='tight',dpi=220);paths.append(file)
    plt.close(fig)
    (DATA/'figure-definitions.tex').write_text('\n\n'.join(latex_exposure().values()),encoding='utf-8')
    inputs=[DATA/'weighted-country-year.csv',DATA/'global-weighted-trends.csv',DATA/'brazil-genre-thematic-profiles.csv',Path(__file__)]
    manifest={'inputs':[dict(path=str(p.relative_to(HERE)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in inputs],
        'outputs':[dict(path=str(p.relative_to(HERE)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]}
    (DATA/'figure-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Created chart-exposure figure and genre-profile table.')

if __name__=='__main__':main()
