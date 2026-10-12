"""Publication figures and equivalent inline PGFPlots from frozen global trends.

Shared position scales follow Cleveland & McGill's quantitative encoding principle;
facets avoid comparing trends on hidden axes (Few). Color is paired with markers.
"""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

HERE=Path(__file__).resolve().parent
DATA=HERE/'global-patterns'
FIGURES=HERE/'figures'
BLUE='#245581';ORANGE='#BD5B21';GRAY='#AAB3BD'
FOCUS=['romantic_affection','explicitness','materialism','crime','weapons','heartbreak']
LABELS={
 'explicitness':'Sexual explicitness','sexual_desire':'Sexual desire','sexual_innuendo':'Sexual innuendo',
 'explicit_sexual_act':'Explicit sexual acts','explicit_sexual_anatomy':'Sexual anatomy',
 'romantic_affection':'Romantic affection','heartbreak':'Heartbreak','infidelity':'Infidelity',
 'transactional_sex':'Transactional sex','casual_sex':'Casual sex','jealousy_possession':'Jealousy / possession',
 'reciprocity':'Reciprocity','objectification':'Objectification','misogyny':'Misogyny',
 'sexual_agency':'Sexual agency','status_symbolization':'Status symbolization','commodification':'Commodification',
 'money_reference':'Money references','materialism':'Materialism','conspicuous_consumption':'Conspicuous consumption',
 'wealth_as_status':'Wealth as status','drugs_alcohol':'Drugs / alcohol','crime':'Crime','violence':'Violence',
 'weapons':'Weapons','territorial_identity':'Territorial identity'}
PAIR_TITLES={
 ('romantic_affection','youth_unemployment'):'Romance / youth unemployment',
 ('materialism','gdp_pc_ppp_constant'):'Materialism / PPP income',
 ('materialism','gini'):'Materialism / Gini',
 ('misogyny','gender_inequality_index'):'Misogyny / GII',
 ('violence','homicide_unodc_total'):'Violence / homicide',
 ('territorial_identity','urban_population'):'Territorial identity / urbanization'}

def coords(frame,x,y):
    return ' '.join(f"({r[x]:.6f},{r[y]:.6f})" for r in frame.to_dicts())

def save(fig,name):
    FIGURES.mkdir(exist_ok=True)
    for suffix in ['pdf','svg','png']:
        path=FIGURES/(name+'.'+suffix)
        fig.savefig(path,bbox_inches='tight',dpi=220)
        if suffix=='svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    plt.close(fig)

def style(ax):
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='y',color='#E1E5E9',linewidth=.45)
    ax.set_axisbelow(True)

def latex_figures():
    trends=pl.read_csv(DATA/'annual-global-trends.csv').filter(pl.col('panel')=='combined55')
    annual=pl.read_parquet(HERE/'analysis-final/annual-country-metrics.parquet').filter((pl.col('market_code')=='BR')&(pl.col('year')<=2021)).sort('year')
    summary=pl.read_csv(DATA/'change-summary.csv')
    grid=[]
    for i,m in enumerate(FOCUS):
        s=trends.filter(pl.col('metric')==m).sort('year')
        grid.append(r'\nextgroupplot[title={'+LABELS[m]+r'},ylabel={'+(r'Recordings (\%)' if i%3==0 else '')+r'}]')
        grid += [r'\addplot[name path=lower'+str(i)+r',draw=none] coordinates {'+coords(s,'year','p25_pct')+'};',
            r'\addplot[name path=upper'+str(i)+r',draw=none] coordinates {'+coords(s,'year','p75_pct')+'};',
            r'\addplot[blue!13,draw=none] fill between[of=lower'+str(i)+' and upper'+str(i)+'];',
            r'\addplot[blue,thick,mark=*,mark size=1.3pt] coordinates {'+coords(s,'year','mean_pct')+'};',
            r'\addplot[orange,thick,dashed,mark=square*,mark size=1.3pt] coordinates {'+coords(annual,'year',m+'_pct')+'};']
    time=r'''\begin{figure*}[t]
\centering\begin{tikzpicture}
\begin{groupplot}[group style={group size=3 by 2,horizontal sep=9mm,vertical sep=9mm},
 width=.27\textwidth,height=39mm,scale only axis=true,
 xmin=2016.8,xmax=2021.2,ymin=0,ymax=50,xtick={2017,2019,2021},xticklabels={17,19,21},ytick={0,20,40},
 tick label style={font=\scriptsize},title style={font=\small},ylabel style={font=\scriptsize},
 axis line style={gray},ymajorgrids=true,grid style={gray!18}]
'''+ '\n'.join(grid)+r'''
\end{groupplot}\end{tikzpicture}
\caption{International trajectories, 2017--2021. Blue circles: equal-market means for the same 55 markets in all five years; orange dashed squares: Brazil. Bands are the middle 50\% of market values, not confidence intervals. Each theme uses the same 0--50\% axis; substantial presence means intensity $\geq2$. Markets have at least 300 classified recordings and 50\% classification coverage in every year. The changing annual repertoires, not changes within a song, are measured.}
\label{fig:global-time}
\end{figure*}'''
    s=summary.filter(pl.col('panel')=='combined55').sort('mean_change_pp',descending=True)
    ticks=','.join(str(26-i) for i in range(26))
    labels=','.join('{'+LABELS[r['metric']]+'}' for r in s.to_dicts())
    marks=[]
    for i,r in enumerate(s.to_dicts()):
        y=26-i
        marks.append(f"\\draw[gray!65,thick] (axis cs:{r['p25_change_pp']:.6f},{y})--(axis cs:{r['p75_change_pp']:.6f},{y});")
        marks.append(f"\\node[font=\\scriptsize,anchor=east] at (axis cs:11.5,{y}) {{{r['markets_increasing']}/55}};")
    points=' '.join(f"({r['mean_change_pp']:.6f},{26-i})" for i,r in enumerate(s.to_dicts()))
    shift=r'''\begin{figure}[t]
\centering\begin{tikzpicture}
\begin{axis}[width=\dimexpr\columnwidth-24mm\relax,height=104mm,scale only axis=false,
 xmin=-4,xmax=12,ymin=.2,ymax=27.6,xtick={-4,0,4,8},ytick={'''+ticks+r'''},yticklabels={'''+labels+r'''},
 xlabel={Change in share, 2017--2021 (pp)},xlabel style={font=\scriptsize},tick label style={font=\scriptsize},
 xmajorgrids=true,grid style={gray!18},axis line style={gray}]
\draw[gray,dashed] (axis cs:0,.3)--(axis cs:0,26.6);
'''+ '\n'.join(marks)+r'''
\addplot[only marks,blue,mark=*,mark size=1.7pt] coordinates {'''+points+r'''};
\node[font=\scriptsize,anchor=east] at (axis cs:11.5,27.2) {Rising};
\end{axis}\end{tikzpicture}
\caption{Changes in all 26 dimensions in the fixed 55-market panel. Blue points: mean paired market change; gray segments: interquartile range of market changes. Right-hand counts show markets with a positive change. ``pp'' means percentage points. These spreads describe observed markets, not sampling confidence.}
\label{fig:global-changes}
\end{figure}'''
    # Two aligned panels give every dimension room at the article's full width.
    panels=[]
    for part in range(2):
        rows=s.to_dicts()[part*13:(part+1)*13]
        ticks=','.join(str(13-i) for i in range(13))
        labels=','.join('{'+LABELS[r['metric']]+'}' for r in rows)
        panels.append(r'\nextgroupplot[ytick={'+ticks+r'},yticklabels={'+labels+r'},title={'+('Larger mean increases' if part==0 else 'Smaller increases and decreases')+r'}]')
        panels.append(r'\draw[gray,dashed] (axis cs:0,.4)--(axis cs:0,13.6);')
        for i,r in enumerate(rows):
            y=13-i
            panels.append(f"\\draw[gray!65,thick] (axis cs:{r['p25_change_pp']:.6f},{y})--(axis cs:{r['p75_change_pp']:.6f},{y});")
            panels.append(f"\\node[font=\\scriptsize,anchor=east] at (axis cs:7.8,{y}) {{{r['markets_increasing']}/55}};")
        panels.append(r'\addplot[only marks,blue,mark=*,mark size=2pt] coordinates {'+' '.join(f"({r['mean_change_pp']:.6f},{13-i})" for i,r in enumerate(rows))+'};')
    shift=r'''\begin{figure*}[t]
\centering\begin{tikzpicture}
\begin{groupplot}[group style={group size=2 by 1,horizontal sep=44mm},
width=48mm,height=86mm,scale only axis=true,xmin=-4,xmax=8,ymin=.4,ymax=13.6,
xtick={-4,-2,0,2,4,6},xlabel={Change in share (percentage points)},
xlabel style={font=\scriptsize},tick label style={font=\scriptsize},title style={font=\small},
xmajorgrids=true,grid style={gray!18},axis line style={gray}]
'''+ '\n'.join(panels)+r'''
\end{groupplot}\end{tikzpicture}
\caption{Which themes increased, and how widely? All 26 dimensions are ordered by mean change from 2017 to 2021 and split across two panels with the same scale. A blue point to the right of zero indicates an increase in the average market share. Gray bars show the middle half of market changes, not confidence intervals. Counts at the right show how many of the same 55 markets increased. Materialism, crime and weapons rose in most markets, whereas a positive mean for sexual desire masks a less widespread change.}
\label{fig:global-changes}
\end{figure*}'''
    family=['romantic_affection','heartbreak','explicitness','misogyny','materialism','crime','weapons','territorial_identity']
    family_points=[]
    for panel,color,mark,offset in [('top200_matched52','blue','*',.13),('viral50_matched52','orange','triangle*',-.13)]:
        points=[]
        for i,m in enumerate(family):
            v=summary.filter((pl.col('panel')==panel)&(pl.col('metric')==m))['mean_change_pp'].item()
            points.append(f'({v:.6f},{8-i+offset:.3f})')
        family_points.append(r'\addplot[only marks,'+color+',mark='+mark+r',mark size=2pt] coordinates {'+' '.join(points)+'};')
    family_tex=r'''\begin{figure}[t]
\centering\begin{tikzpicture}
\begin{axis}[width=\dimexpr\columnwidth-16mm\relax,height=66mm,
 xmin=-4,xmax=5,ymin=.4,ymax=8.6,xtick={-4,-2,0,2,4},ytick={8,7,6,5,4,3,2,1},
 yticklabels={Romance,Heartbreak,Explicitness,Misogyny,Materialism,Crime,Weapons,Territorial identity},
 xlabel={2017--2021 change (pp)},xlabel style={font=\scriptsize},tick label style={font=\scriptsize},
 xmajorgrids=true,grid style={gray!18},axis line style={gray}]
\draw[gray,dashed] (axis cs:0,.5)--(axis cs:0,8.5);
'''+ '\n'.join(family_points)+r'''
\end{axis}\end{tikzpicture}
\caption{Chart-family contrast in the same 52 markets. Blue circles: Top 200 (source union, IDs deduplicated); orange triangles: Viral 50. Each panel has at least 300 classified IDs and 50\% classification coverage in every full year. The romance trend changes direction across chart families; growth of status and conflict themes persists.}
\label{fig:family-trends}
\end{figure}'''
    social=pl.read_csv(DATA/'fixed-sample-social-correlations.csv')
    panels=[]
    for i,((lyric,external),title) in enumerate(PAIR_TITLES.items()):
        rows=social.filter((pl.col('metric')==lyric)&(pl.col('context')==external)).sort('year')
        title=title+r' ($n='+str(rows['markets'][0])+r'$)'
        panels.append(r'\nextgroupplot[title={'+title+r'},ylabel={'+('$\rho$' if i%3==0 else '')+r'}]')
        panels.append(r'\draw[gray,dashed] (axis cs:2016.8,0)--(axis cs:2021.2,0);')
        panels.append(r'\addplot[teal,thick,mark=diamond*,mark size=1.5pt] coordinates {'+coords(rows,'year','rho')+'};')
    social_tex=r'''\begin{figure*}[t]
\centering\begin{tikzpicture}
\begin{groupplot}[group style={group size=3 by 2,horizontal sep=9mm,vertical sep=9mm},
 width=.265\textwidth,height=31mm,scale only axis=true,
 xmin=2016.8,xmax=2021.2,ymin=-.75,ymax=.75,xtick={2017,2019,2021},xticklabels={17,19,21},ytick={-.5,0,.5},
 tick label style={font=\scriptsize},title style={font=\scriptsize},ylabel style={font=\scriptsize},
 axis line style={gray},ymajorgrids=true,grid style={gray!18}]
'''+ '\n'.join(panels)+r'''
\end{groupplot}\end{tikzpicture}
\caption{Persistence of social associations, using a fixed market sample within each pair in every year. Points are separate-year Spearman correlations; $n$ counts markets, not people. World Bank data supply income, Gini, youth unemployment and urbanization; UNDP supplies GII; UNODC supplies homicide. No interpolation or pooled-year correlation is used. Stable directions describe aggregate associations and do not establish causes.}
\label{fig:social-time}
\end{figure*}'''
    return {'GLOBAL_TIME_FIGURE':time,'GLOBAL_CHANGE_FIGURE':shift,'FAMILY_TREND_FIGURE':family_tex,'SOCIAL_TIME_FIGURE':social_tex}

def main():
    plt.rcParams.update({'font.size':8,'axes.labelsize':8,'axes.titlesize':9,'xtick.labelsize':7,'ytick.labelsize':7,
        'pdf.fonttype':42,'ps.fonttype':42,'figure.dpi':150})
    trends=pl.read_csv(DATA/'annual-global-trends.csv').filter(pl.col('panel')=='combined55')
    annual=pl.read_csv(HERE/'analysis-final/annual-country-metrics.csv').filter((pl.col('market_code')=='BR')&(pl.col('year')<=2021)).sort('year')
    fig,axes=plt.subplots(2,3,figsize=(7.15,3.8),layout='constrained',sharex=True,sharey=True)
    for ax,m in zip(axes.flat,FOCUS,strict=True):
        rows=trends.filter(pl.col('metric')==m).sort('year')
        ax.fill_between(rows['year'].to_numpy(),rows['p25_pct'].to_numpy(),rows['p75_pct'].to_numpy(),color=BLUE,alpha=.13,label='Market IQR')
        ax.plot(rows['year'],rows['mean_pct'],'o-',color=BLUE,markersize=3,label='55-market mean')
        ax.plot(annual['year'],annual[m+'_pct'],'s--',color=ORANGE,markersize=3,label='Brazil')
        ax.set_title(LABELS[m]);ax.set_ylim(0,50);ax.set_xticks([2017,2019,2021]);style(ax)
    for ax in axes[:,0]:ax.set_ylabel('Classified recordings (%)')
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='outside upper center',ncol=3,frameon=False)
    save(fig,'global-trajectories')
    s=pl.read_csv(DATA/'change-summary.csv').filter(pl.col('panel')=='combined55').sort('mean_change_pp',descending=True)
    fig,axes=plt.subplots(1,2,figsize=(10,5),layout='constrained',sharex=True)
    for part,ax in enumerate(axes):
        rows=s.to_dicts()[part*13:(part+1)*13]
        for i,r in enumerate(rows):
            ax.plot([r['p25_change_pp'],r['p75_change_pp']],[i,i],color=GRAY,linewidth=2)
            ax.scatter(r['mean_change_pp'],i,color=BLUE,s=24)
            ax.text(7.8,i,f"{r['markets_increasing']}/55",ha='right',va='center',fontsize=8)
        ax.set_yticks(range(13),[LABELS[r['metric']] for r in rows]);ax.invert_yaxis()
        ax.set_xlim(-4,8);ax.set_xticks([-4,-2,0,2,4,6]);ax.axvline(0,color=GRAY,linestyle='--',linewidth=.6)
        ax.set_xlabel('Change in share (percentage points)')
        ax.set_title('Larger mean increases' if part==0 else 'Smaller increases and decreases')
        ax.grid(axis='x',color='#E1E5E9',linewidth=.45);ax.spines[['top','right']].set_visible(False)
    save(fig,'global-dimension-changes')
    summary=pl.read_csv(DATA/'change-summary.csv');family=['romantic_affection','heartbreak','explicitness','misogyny','materialism','crime','weapons','territorial_identity']
    fig,ax=plt.subplots(figsize=(4.2,2.7),layout='constrained')
    y=np.arange(len(family))
    for panel,color,marker,offset,label in [('top200_matched52',BLUE,'o',.12,'Top 200'),('viral50_matched52',ORANGE,'^',-.12,'Viral 50')]:
        values=[summary.filter((pl.col('panel')==panel)&(pl.col('metric')==m))['mean_change_pp'].item() for m in family]
        ax.scatter(values,y+offset,color=color,marker=marker,s=24,label=label)
    ax.set_yticks(y,[LABELS[m] for m in family]);ax.invert_yaxis();ax.set_xlim(-4,5);ax.axvline(0,color=GRAY,linestyle='--',linewidth=.6)
    ax.set_xlabel('2017–2021 mean change (percentage points)');ax.set_title('Same 52 markets · chart-family contrast')
    ax.grid(axis='x',color='#E1E5E9',linewidth=.45);ax.spines[['top','right']].set_visible(False)
    fig.legend(*ax.get_legend_handles_labels(),loc='outside upper center',ncol=2,frameon=False)
    save(fig,'chart-family-contrast')
    social=pl.read_csv(DATA/'fixed-sample-social-correlations.csv')
    fig,axes=plt.subplots(2,3,figsize=(7.15,3.2),layout='constrained',sharex=True,sharey=True)
    for ax,((lyric,external),title) in zip(axes.flat,PAIR_TITLES.items(),strict=True):
        rows=social.filter((pl.col('metric')==lyric)&(pl.col('context')==external)).sort('year')
        ax.plot(rows['year'],rows['rho'],'D-',color='#187E78',markersize=3);ax.axhline(0,color=GRAY,linewidth=.6,linestyle='--')
        ax.set_title(title+'\n'+str(rows['markets'][0])+' fixed markets',fontsize=8);ax.set_ylim(-.75,.75);ax.set_xticks([2017,2019,2021]);style(ax)
    for ax in axes[:,0]:ax.set_ylabel('Spearman correlation')
    save(fig,'social-association-trajectories')
    (DATA/'figure-definitions.tex').write_text('\n\n'.join(latex_figures().values()),encoding='utf-8',newline='\n')
    manifest={'inputs':[{'path':str(p.relative_to(HERE)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in
        [DATA/'annual-global-trends.csv',DATA/'change-summary.csv',DATA/'fixed-sample-social-correlations.csv',HERE/'analysis-final/annual-country-metrics.parquet',Path(__file__)]],
        'outputs':[{'path':str(p.relative_to(HERE)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(FIGURES.glob('*'))
            if p.is_file() and p.stem in ['global-trajectories','global-dimension-changes','chart-family-contrast','social-association-trajectories']],
        'inline_definitions_sha256':hashlib.sha256((DATA/'figure-definitions.tex').read_bytes()).hexdigest()}
    (DATA/'figure-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Created four publication figures in PDF, SVG and PNG; inline LaTeX uses the same frozen tables.')

if __name__=='__main__':main()
