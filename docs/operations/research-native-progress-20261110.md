# Andamento e reconstrução nativa — 10/11/2026

Nova conferência às 19:45 BRT. O PostgreSQL configurado permanece indisponível
na consulta somente de leitura; nenhum coletor histórico pesquisado está ativo.
Os percentuais abaixo referem-se aos arquivos locais vinculados à seleção,
não a um estado atual certificado do banco.

| Indicador | Numerador / denominador | Percentual |
| --- | --- | ---: |
| Posições observadas | 92.000 / 277.650 posições previstas | 33,14% |
| Células país/ano com músicas | 622 / 2.250 | 27,64% |
| Células com cota preenchida e calendário anual completo | 531 / 2.250 | 23,60% |
| Letras disponíveis entre candidatos já selecionados | 27.606 / 30.927 | 89,26% |
| Portões científicos aprovados | 0 / 5 | 0% |

Não calcular média entre esses indicadores. G2/G3/G5 ainda não têm denominador
elegível e seu percentual é indefinido. O fluxo final aprovado permanece em 0%.
Isso não afirma que todos os dados estão errados; indica ausência das evidências
e homologações exigidas pelo protocolo. O snapshot de letras tem cerca de 47h.

## Implementação adicionada

- `research progress`: exporta progresso por unidade, origem, timestamp, hash,
  estado dos portões e alertas de snapshot antigo/auditoria desatualizada.
- `research project-mgd`: lê o TSV nativo, preserva posição original, inteiro de
  streams, ID, linha e arquivo; confere seu hash no inventário MGD; reconstrói o
  ano e compara com todas as posições da célula congelada.
- Reconstrutor v2: ausência de título/artista passa a ser contada separadamente.
  Uma linha com ID, posição e métrica válidos não desaparece do calendário por
  estar sem nome. O nome desconhecido permanece desconhecido; não é completado
  por inferência. A conferência nominal de cada posição e a aprovação científica
  continuam obrigatórias.
- A definição de fonte exige URL HTTPS e timestamp válido com timezone;
  templates com campos vazios não podem ser usados como aprovação.

## Execução real sobre os arquivos originais

Não houve rede, alteração do banco, adjudicação automática ou inferência Vertex.
Foram projetadas 511.600 observações nativas em sete células operacionais:

| Célula | Posições selecionadas | Posição + métrica coincidentes | Nomes exatamente iguais | Reconstrução estrutural |
| --- | ---: | ---: | ---: | --- |
| BR/2018 | 230 | 230 | 124 | Passou; 10 observações sem nomes |
| BR/2019 | 230 | 230 | 112 | Passou |
| BR/2020 | 230 | 230 | 111 | Passou; 42 observações sem nomes |
| BR/2021 | 230 | 230 | 110 | Retida por seis versões de metadados no mesmo período |
| PT/2018 | 120 | 120 | 52 | Passou |
| PT/2019 | 120 | 120 | 57 | Passou |
| PT/2020 | 120 | 120 | 59 | Passou; quatro observações sem nomes |

As 1.280 posições e métricas coincidiram: 100% desse piloto diagnóstico,
equivalentes a 1,39% das posições observadas ou 0,46% das previstas. Seis das
sete células passaram na reconstrução estrutural. Nenhuma recebeu adjudicação
científica, portanto esses resultados não aumentam o numerador de G1.

Diferença literal de nomes não significa necessariamente música incorreta.
Foram encontrados separadores diferentes de artistas, créditos expandidos e
alterações de título/versão. Preservar as duas versões para revisão. Em BR/2021,
o arquivo repete 01/09: 194 observações são duplicatas exatas e seis têm nomes
diferentes, embora posições e métricas sejam iguais. A divergência não foi
escondida por deduplicação arbitrária.

Resultados: `data/runtime/research-flow-20261110/native-reconstruction-v2/`.
Cada célula tem observações, comparação JSONL/CSV, reconstrução, template de
definição de fonte e manifesto com hashes de dados e código. Templates mantêm
aprovações falsas e campos de revisão pendentes.

## Reproduzir e consultar

```powershell
.venv/Scripts/chart-observatory.exe research project-mgd --selection data/derived/annual_revision/global-2018-2026-20261108 --raw-source mgd/charts/regional/spotify_charts_regional_br.csv --output data/runtime/research-flow-20261110/nova-reconstrucao-BR-2019 --country BR --year 2019
.venv/Scripts/chart-observatory.exe research progress --audit data/runtime/research-flow-20261110/audit-0004 --staging-status data/runtime/global-lyrics-20261108/final-staging/status.json --output data/runtime/research-flow-20261110/novo-progresso
```

A auditoria `audit-0004` preserva a seleção e os bloqueios. O progresso exportado
está em `progress-0001`. Saídas novas não sobrescrevem versões anteriores.
O próximo trabalho de dados continua sendo recuperar fontes das células
ausentes e resolver a identidade/metadados com evidência, antes da aprovação
de G1 e da passagem para a validação de letras.
