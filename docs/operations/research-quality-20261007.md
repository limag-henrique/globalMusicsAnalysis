# Auditoria da qualidade para o artigo — 7 de outubro de 2026

As correções reduzem erros técnicos identificados. Não demonstram ausência de
erro de mensuração nem representatividade da população geral. A população dos
países é o alvo interpretativo; a população observada consiste em músicas nos
rankings de plataformas, mercados e períodos específicos. Reprodução não é
ouvinte único; ouvir não demonstra concordância com o texto.

## Estado observado e preservado

O PostgreSQL recuperado contém 159.111 documentos de letras e 168.152 snapshots
imutáveis. A seleção do último snapshot por documento/modelo/taxonomia/prompt
contém 67.550 resultados `classified`, 90.433 erros e 1.128 outros estados.
Os 200 resultados do retry desta noite foram importados, sem erros individuais;
o custo com telemetria foi US$ 0,379518375. Isso valida execução e esquema,
sem demonstrar acurácia semântica.

As tabelas de rankings e de vínculos com itens de plataforma estão vazias nesse
banco. Os rankings existem nos Parquets: 47.434.073 observações, incluindo fontes
Spotify sobrepostas, YouTube e uma série agregada brasileira. Não são 47 milhões
de pessoas nem observações independentes. Fontes sobrepostas devem ser tratadas
como alternativas de cobertura, nunca somadas como públicos distintos. `GLOBAL`
e territórios não devem ser apresentados automaticamente como países soberanos.

O importador legado criou UUIDs por título/artista e perdeu o `song_id` no banco.
Não há IDs compartilhados diretamente com os 126.213 registros de `track_master`.
A auditoria recuperou 93.908 associações de documentos através do identificador
original, título/artista e hash exato do documento. Esse resultado comprova a
linhagem de importação; não comprova que o provedor retornou a letra correta.
65.181 registros originais não têm `song_id` no cadastro atual, 28 divergem nos
metadados e um registro JSONL não pôde ser interpretado. Nenhum foi corrigido
por adivinhação ou sobrescrito.

Existem também 108.986 pares candidatos por título/artista normalizados. São
candidatos, não confirmações de gravação. O arquivo original de letras permanece
privado e preservado; os produtos da auditoria não contêm letras.

## Correções implementadas

- Append de snapshot exige hash e faixa compatíveis com o documento.
- Retry exclui resolução válida da mesma assinatura, reserva ativa, fontes
  suspensas, quarentena e documentos sem direitos autorizados.
- Painéis balanceados intersectam períodos efetivamente observados.
- Conteúdo informa denominadores observados, anotados e faltantes; ausência de
  anotação produz valor ausente, não score zero. Anotações múltiplas de uma faixa
  exigem seleção explícita antes do cálculo.
- Conteúdo, renovação e distâncias de gênero preservam fonte/plataforma/chart
  e duração nativa quando disponíveis. Renovação não atravessa lacunas quando
  o fim do período anterior é conhecido.
- Peso inverso de rank recebe identificação explícita como proxy ordinal, sem
  interpretação como percentual de habitantes ou parcela dos streams.
- Seleção dos snapshots explicita fonte, status, esquema, hash, identidade e
  versões de modelo/taxonomia/prompt. Não converte a taxonomia da IA na antiga
  taxonomia manual implicitamente.

## Liberação científica

56.723 resultados passam pelas verificações técnicas para exploração, incluindo
exclusão de fonte suspensa e quarentena. Atualmente nenhum tem confirmação de
identidade válida registrada para a amostra principal. Isso **não significa que
todas as letras estejam erradas**: significa que a validação necessária não foi
documentada. Elegibilidade técnica não garante vinculação a ranking nem acurácia
dos scores; a análise principal exige essas evidências adicionais.

A amostra `identity_review_sample.csv` seleciona até 40 documentos classificados
por fonte, por ordenação SHA-256 com prefixo fixo `research-review-v1:`. Tem 164
documentos, incluindo controles da fonte suspensa. Ela serve ao diagnóstico;
as taxas agregadas exigem ponderação pelo tamanho de cada estrato. Não é amostra
representativa dos países. Os campos de revisão estão deliberadamente vazios.

Antes de publicar:

1. Dois revisores independentes verificam letra, artista, faixa e versão usando
   evidência documentada; resolvem discordâncias por adjudicação. Se a fonte
   continuar suspensa, confirmação de um registro não libera a fonte inteira.
2. Validam também os rótulos da IA, com instruções estáveis e revisores capazes
   de compreender os idiomas. Medem concordância e erros por dimensão, idioma e
   fonte, com incerteza. Confiança declarada pela IA não substitui isso. O idioma
   está ausente em todos os documentos do banco recuperado.
3. Confirmam vínculos aos rankings, escolhem fontes e frequências comparáveis e
   reportam cobertura por país/plataforma/ano. Não extrapolam cobertura global do
   corpus para cada país. Sem vínculo validado, não existe resultado por país.
4. Recalculam resultados com/sem suspeitos, versões alternativas, fontes e
   limiares; avaliam concentração por artista e dependência entre aparições.
   Reportam tamanhos de efeito e intervalos; corrigem comparações múltiplas.
5. Tratam associações musicais como propriedades do repertório observado.
   Inferências sobre a população geral exigem dados adicionais de audiência,
   representatividade e validação externa. Não derivam características intrínsecas
   de povos ou concordância individual com temas a partir dos rankings.

O Spotify informa que seus charts usam streams elegíveis filtrados, de modo que
nem toda reprodução entra no ranking: [documentação oficial](https://support.spotify.com/dm/artists/article/understanding-spotify-charts/).
Isso reforça que o ranking não é um censo de habitantes.

## Artefatos e reprodução

Executar, no repositório e com o endpoint recuperado em `.env`:

```powershell
.venv\Scripts\python.exe scripts/audit_research_quality.py
```

O script lê banco e artefatos; não altera documentos/snapshots, não chama APIs
e não imprime letras ou credenciais. Recria em
`data/derived/research_quality/20261007/`:

- `audit.json`: contagens, motivos não exclusivos e impedimentos;
- `snapshot_eligibility.csv`: decisão e proveniência por snapshot selecionado;
- `original_id_lineage.parquet`: associação original com hash e linha de origem;
- `identity_crosswalk_candidates.parquet`: correspondências textuais não verificadas;
- `ranking_inventory.parquet`: inventário por fonte/plataforma/mercado/chart;
- `identity_review_sample.csv`: amostra de revisão com campos ainda não preenchidos.

Esses arquivos são produtos de auditoria, não tabelas finais de resultados do
artigo. Nenhum agregado antigo foi promovido a resultado validado ou reescrito.

## Operação e gastos

Custos batch conhecidos: US$ 129,244997625. Compromisso conservador, incluindo
reservas sem telemetria: US$ 598,651911. O limite continua US$ 600; o restante
conservador é US$ 1,348089. A auditoria fez zero chamadas pagas.

Todos os jobs novos desta execução foram reconciliados. Novos envios ficam
suspensos por qualidade, registrados em `quality_hold` no estado noturno, para
priorizar validação sobre novas classificações. O acompanhamento noturno fica
pausado, sem apagar jobs, resultados, buckets ou bancos. A troca de conta pelo
usuário não reinicia o teto acumulado. Retomar exige respeitar o estado persistido,
as exclusões, uma tentativa por erro técnico e o mesmo ledger conservador.

A pedido expresso do usuário, a classificação exploratória foi retomada depois
desta auditoria em 7 de outubro de 2026. A pausa operacional descrita acima é
histórica; o estado atual está em `status.json` e na seção de retomada do runbook
noturno. Os requisitos de validação científica e as exclusões permanecem.


## Operação vigente: orçamento em reais e corpus completo

A autorização posterior do usuário substitui os tetos USD e permite LETRAS
na classificação exploratória. Consulte [operação BRL](brl-full-corpus-20261008.md)
e `data/derived/lyrics/budget-20261008/billing-policy.json`. Quarentena e
elegibilidade científica permanecem estritas; não usar classificações como
validação da ligação ao ranking ou evidência da população geral.
