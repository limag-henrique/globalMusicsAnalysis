# Incorporação mundial por país e ano — 08/11/2026

A incorporação operacional foi implementada e aplicada ao PostgreSQL para todas
as 250 entradas geográficas e todos os anos de 2018–2026: 2.250 células. **O
preenchimento integral das cotas ainda não foi alcançado.** Uma célula cadastrada
não equivale a um ranking disponível. Não foram criadas músicas ou posições para
preencher lacunas.

As 242 cotas com população documentada somam 30.850 posições por ano, ou 277.650
no período. Oito territórios mantêm cota pendente, sem população inventada.
Mantêm-se o padrão populacional anterior e as 68 cotas antigas. As fontes anuais
compartilham o corte de 15/10/2026; 2026 permanece parcial.

## Dados efetivamente incorporados

| Medida | Resultado |
|---|---:|
| Países/territórios cadastrados | 250 |
| Células país/ano cadastradas | 2.250 |
| Posições desejadas com cota definida | 277.650 |
| Vínculos observados importados | 92.000 |
| Vínculos anteriores preservados integralmente | 86.090 |
| Vínculos adicionais recuperados | 5.910 |
| Mercados com vínculos observados | 76 |
| Células com vínculos observados | 622 |
| Posições ainda sem dados observados | 185.650 |
| Posições sem evidência de ano calendário completo | 199.770 |
| Identidades candidatas, antes de adjudicação entre plataformas | 30.927 |
| Conflitos de fonte exportados para adjudicação | 224 |

Os novos vínculos são NG 1.300, PK 1.300, HK 1.080, KZ 700, VE 700,
UG 340, ZW 260, BY 120 e RS 110. Foram recuperados removendo o filtro antigo
de 68 mercados dos arquivos históricos já disponíveis. São 4.860 vínculos de
fontes com calendário completo **até o corte de cada ano**, incluindo 2026
parcial, e 1.050 vínculos provisórios de períodos incompletos. Estes últimos
não são rankings anuais certificados. As seleções antigas também contêm
provisórios; sua preservação não os promove a definitivos.

Distribuição das células: 531 com cota preenchida e calendário anual completo,
73 de 2026 parcial, 18 apenas provisórias, 1.556 sem fonte anual verificada e
72 com cota populacional pendente. O déficit de 185.650 é calculado contra
registros observados, inclusive provisórios; não mede certificação científica.

Os dados adicionais usam os arquivos semanais Spotify/YouTube do registro
Zenodo 23645386 e o cache diário Kaggle Gonzalopezgil v151 já baixados, sem
somar métricas de provedores ou frequências diferentes. Cada plataforma/célula
usa uma fonte inteira escolhida por qualidade de calendário e profundidade.
Identificadores YouTube `T:` não vazios são preservados como identificadores
opacos da fonte; não são convertidos em IDs de vídeo nem considerados gravações
canônicas confirmadas. IDs vazios e métricas conflitantes bloqueiam a célula.

As posições anuais representam a ordenação da soma das métricas **observadas
nos charts publicados**, como no padrão anterior. A censura dos charts Top-K
continua sendo uma limitação; calendário completo não prova a posição no
universo de todas as reproduções da plataforma. Os registros permanecem
sujeitos à adjudicação de gravação e ao gate de classificação.

## Implementação, persistência e arquivos

- `src/chart_observatory/ingestion/global_annual.py`: montagem integral da matriz,
  preservação das seleções, distinção de provisórios e persistência atômica por
  assinatura do conteúdo.
- `scripts/incorporate_global_annual.py`: reprocessamento histórico para todos os
  mercados da política mundial, exportação de nomes/posições, lacunas e conflitos.
- `scripts/verify_global_annual_import.py`: hashes, preservação das 86.090 linhas,
  todas as células, igualdade de todos os payloads PostgreSQL e idempotência.
- `scripts/resolve_global_annual_titles.py`: coleta pública limitada de metadados
  de candidatos novos, exclusivamente por URI Spotify exata, sem alterar ranks.

Diretório dos resultados:
`data/derived/annual_revision/global-2018-2026-20261108/`.

| Arquivo | Conteúdo |
|---|---|
| `ranked_titles.jsonl` | País, ano, posição, título, artista, provedor e estado da seleção |
| `combined.jsonl` | Vínculos completos, preservando os objetos da base anterior |
| `country_years.csv` e `.jsonl` | Todas as 2.250 células, cotas e posições faltantes |
| `historical_requests.jsonl` | Necessidade histórica e fontes nacionais candidatas por célula |
| `adjudication_tasks.jsonl` | Datas, IDs, posições publicadas e métricas conflitantes |
| `source_coverage.json` | Calendários e bloqueios dos novos mercados |
| `manifest.json` | Contagens, hashes dos insumos/resultados e bloqueios |
| `postgres_import.json` | Identificador da versão importada |
| `verification.json` | Resultado da verificação da importação efetiva |

Tabelas novas: `global_annual_import_runs`, `global_annual_import_countries`,
`global_annual_import_cells` e `global_annual_import_memberships`. Nenhuma
substitui tabelas do artigo, seleções anteriores, letras ou classificações.
Versões antigas são preservadas e uma importação idêntica não duplica linhas.

```powershell
.venv/Scripts/python.exe scripts/incorporate_global_annual.py --apply
.venv/Scripts/python.exe scripts/verify_global_annual_import.py
```

O processamento histórico não usa rede. A coleta auxiliar de metadados fez
19 solicitações públicas por URI exata; todas ficaram indisponíveis e foram
registradas, sem tentativas de contornar acesso. Permanecem 31 vínculos com
título ou artista ausente (30 novos e um anterior preservado). Não foram
substituídos por músicas abaixo da cota. As 5.400 posições de snapshots atuais
do lote anterior não foram reutilizadas como anos históricos.

## Limites que impedem declarar a coleta integral concluída

As fontes auditadas não fornecem dados históricos verificáveis suficientes para
as 185.650 posições restantes. Os arquivos existentes trazem conflitos em
algumas células, inclusive métricas diferentes para o mesmo identificador na
mesma semana. Há 224 casos explícitos para adjudicação, sem escolher um número
arbitrariamente. Outras células dependem de uma fonte nacional histórica ainda
não verificada. Não se pode preencher esses anos com o Top 100 atual, expandir
uma lista de 100 para uma cota de 260 ou replicar charts regionais em países.

Portanto, a implementação e a importação dos dados disponíveis foram feitas;
**a solicitação de todas as músicas em todos os países/anos permanece
incompleta por falta de evidência histórica suficiente nos insumos auditados**.
Os arquivos mostram exatamente onde e quanto falta, sem registrar a ausência
como falta de atividade musical.

Nenhuma chamada paga, aquisição de letras ou classificação foi iniciada. A união
de 30.927 candidatos ultrapassa o limite anterior de 30 mil; aquisição e
classificação permanecem bloqueadas, sem presumir novo orçamento autorizado.

Validação: 137 testes de ingestão/fontes aprovados; Ruff nos arquivos novos,
Mypy no módulo de incorporação e verificação da importação efetiva no PostgreSQL.
