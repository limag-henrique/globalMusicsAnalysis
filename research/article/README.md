# Artigo e atlas internacional

Artigo em inglês, com foco no Brasil, sete páginas de texto e gráficos científicos
em duas colunas e uma página de atlas para todos os 68 mercados. Inclui oito
figuras vetoriais, cinco tabelas de resultados/métodos e a tabela internacional.

- `article.tex`: fonte LaTeX independente, com todos os dados gráficos incorporados.
- `article.pdf`: versão compilada e revisada visualmente, oito páginas A4.
- `international-atlas.html`: consulta interativa de países e posições em 26 dimensões.
- `international-atlas.csv`: valores, numeradores, denominadores e posições por dimensão.
- `analysis-final/`: resultados completos em CSV/Parquet, amostras dos modelos,
  exclusões, proveniência e hashes. Não contém o texto das letras.
- `social-context/`: matriz das 26 dimensões com 13 indicadores sociais e econômicos
  externos, por ano (1.690 células, 1.586 correlações descritivas disponíveis),
  perfil contextual do Brasil e coocorrência dos temas nas gravações.
- `global-patterns/`: tendências anuais em painéis de mercados fixos, variações
  das 26 dimensões, oito recortes de fonte/cobertura, união de gravações por ano
  e correlações sociais em amostras constantes.
- `chart-exposure/`: 17.268.835 entradas diárias deduplicadas do Top 200 MGD,
  medidas ponderadas por permanência e streams, perfis de gêneros brasileiros e
  cruzamentos sociais com três ponderações. Os originais permanecem preservados.
- `figures/`: cinco figuras adicionais em PDF, SVG e PNG, prontas para reutilização.
- `delivery-manifest.json`: hashes dos produtos e verificações de entrega.

O snapshot somente leitura do PostgreSQL é de 11/10/2026, 20:39:03 BRT. Foram
selecionadas 154.964 identidades de gravação no corpus geral e 153.501 IDs de
gravação no recorte geográfico. Classificação e ligação entre letras e gravações
foram verificadas por especialistas; a etapa é registrada como concluída,
conforme confirmação do responsável pelo projeto em 11/10/2026.

As posições são específicas de cada tema. A tabela impressa é ordenada pela
explicitude sexual; a consulta interativa permite qualquer dimensão. Intensidade
>=2 define presença substancial. Os resultados por mercado contam gravações
distintas, sem somar reaparições ou fontes sobrepostas. O Brasil está destacado.

## Reprodução

Para reproduzir tabelas, figuras, CSV e o fragmento interativo do snapshot salvo:

```powershell
.\.venv\Scripts\python.exe research\article\analyze_global_patterns.py
.\.venv\Scripts\python.exe research\article\plot_global_patterns.py
.\.venv\Scripts\python.exe research\article\analyze_chart_exposure.py
.\.venv\Scripts\python.exe research\article\plot_chart_exposure.py
.\.venv\Scripts\python.exe research\article\compose_article.py
tectonic -X compile research\article\article.tex --outdir research\article
```

`compose_article.py` usa `article.template.tex` e o diretório `analysis-final`.
A narrativa e as contagens do texto são referentes ao snapshot congelado. A
recomposição não consulta o banco nem chama APIs. O HTML completo foi produzido
com o renderizador da skill visualize a partir de
`international-atlas.fragment.html`; a biblioteca D3 é carregada de CDN.

Para recalcular a matriz social a partir do snapshot salvo:

```powershell
.\.venv\Scripts\python.exe research\article\extend_social_context.py
```

Os seis eixos sociais são intimidade/afetos, gênero/poder, status/desigualdade,
violência/segurança, ambiente digital e circulação cultural. O atlas inclui
valores de contexto de 2021 (Banco Mundial, UNDP e UNODC), identificados pelo
ano e separados das porcentagens musicais históricas. SIGI mantém a edição
de 2019 nos cruzamentos. Ausências externas permanecem nulas.

## Tendências internacionais

As trajetórias usam os mesmos 55 mercados nos cinco anos completos de 2017 a
2021. Cada mercado recebe peso igual; cada ID conta uma vez por mercado/ano.
Os intervalos gráficos são quartis dos mercados observados, não intervalos de
confiança. O limiar temático é intensidade >=2. O painel exige ao menos 300
gravações classificadas e 50% de cobertura de classificação em cada ano.

São fornecidos oito painéis: união principal (55), cobertura >=70% nos cinco
anos (8), Top 200 unido (52), MGD Top 200 (51), Viral 50 (55), Top 200 e Viral 50
nos mesmos 52 mercados, e elegibilidade de charts com início em 01/01/2017 (46).
O recorte com cobertura >=70% é uma sensibilidade pequena, explicitamente
identificada. Não é convertido em uma amostra internacional representativa.

Os achados se referem à composição do repertório: materialismo, crime, armas,
sofrimento amoroso e identidade territorial crescem em todos os recortes.
Romance cai no Top 200 e sobe no Viral 50 no mesmo conjunto de mercados. O
Brasil lidera a variação de sexo casual no painel principal e é segundo em
explicitude sexual. Rankings de mudanças não são rankings de níveis absolutos.

O pool anual deduplica também entre mercados e permite conferir que músicas
compartilhadas não foram somadas como gravações globais independentes. As seis
associações sociais longitudinais fixam o conjunto de países dentro de cada
par de variáveis e calculam Spearman por ano, sem juntar anos como eventos
independentes. Não se infere causalidade ou mudança de comportamento populacional.

## Repertório, permanência, streams e gêneros

A extensão usa somente MGD Top 200 e os mesmos 51 mercados durante 2017–2021.
São removidas 1.800 linhas exatamente repetidas de chart, sem alterar os arquivos
originais. Valores conflitantes para a mesma gravação/dia interrompem o cálculo.
Dias sem stream informado também exigem tratamento explícito antes de ponderar.

Todos os índices são calculados por gravações distintas, dias observados no chart
e soma dos streams elegíveis nos dias observados. Os denominadores de temas
contêm somente gravações classificadas. A cobertura de streams é registrada
separadamente: 69,4% no Brasil em 2021 e mediana de 73,1% nos 51 mercados naquele
ano. Os indicadores não representam pessoas nem streams fora dos charts.

Os oito maiores tags de gênero do Brasil são escolhidos pelo tamanho do repertório
observado antes de examinar os escores. Os tags derivam de artistas e se sobrepõem.
São exportadas todas as 26 dimensões por tag. As relações sociais usam sete
indicadores externos e três ponderações, com o mesmo conjunto de países dentro
de cada comparação em todos os cinco anos. A redação substitui as duas equações
exibidas por definições e interpretações em inglês simples.

Para uma nova extração, configurar um diretório de saída novo no
`build_analysis.py`. O comando recusa sobrescrever o snapshot existente e usa
uma transação PostgreSQL REPEATABLE READ READ ONLY. Atualizações do corpus
exigem também atualizar as contagens e a interpretação no texto do artigo.

Os dados históricos de contexto e buscas já coletados são reutilizados por
chaves exatas de mercado/ano. Os 30 modelos foram recalculados com os resultados
de classificação do snapshot atual; a correção BH inclui a família completa.
Os arquivos de avaliações históricas permanecem preservados e não substituem
a verificação por especialistas concluída posteriormente.

## Verificações

Compilação Tectonic, inspeção de todas as páginas por renderização Poppler,
revisão dos numeradores/denominadores e unicidade das junções. Consulta
interativa verificada em 1.000 e 360 pixels: seleção de país, mudança entre
dimensões, posição recalculada, tabela com 68 mercados e ausência de erros de
execução no navegador. Nenhum commit, troca de branch, chamada ao Gemini ou
alteração de dados no banco foi realizado na elaboração do artigo.
