# Painel histórico de interesse de busca e circulação musical

## Problema

A coleta possui escalas locais, censura e múltiplos lotes. Uma junção direta
com prevalências musicais multiplicaria registros e sugeriria comparações
internacionais inválidas. O usuário autorizou painel histórico e piloto comercial.

## Solução e histórias de uso

1. Consultar país/ano/termo/idioma/lote com denominadores musicais preservados.
2. Reconhecer períodos parciais, censura, zeros e lacunas de cobertura.
3. Recuperar a origem por hashes das observações e entradas.
4. Comparar mudanças dentro da mesma série e verificar sensibilidade à cobertura.
5. Examinar associações exploratórias com efeitos de país/ano e controles disponíveis.
6. Planejar visitas históricas sem fabricar dados na ausência de acesso comercial.
7. Retomar chamadas comerciais sem repetir respostas já obtidas.

## Decisões

Painel longo por país, ano, termo, idioma e lote. Buckets mensais/semanais têm
peso em dias; semanas atravessando dezembro são repartidas entre anos. Buckets
que ultrapassam o encerramento solicitado são excluídos. A cobertura é relativa
à interseção entre ano e janela solicitada. 2022 permanece descritivo e parcial.
Censura <1 produz limites [0,1); média pontual só existe sem censura e sem falhas.
Limites resumem os dias disponíveis, não estimam dias ausentes.

Associações principais usam porn/en de um lote canônico (menor identificador
lexicográfico por país), sem somar âncoras. Padronização por país usa apenas os
anos elegíveis 2017–2021: expressa mudança relativa local, não consumo nacional.
OLS exploratória com efeitos fixos de país/ano e erros agrupados por país;
mínimos de quatro anos por país, vinte países, 300 faixas classificadas,
80% de cobertura temporal e sensibilidades musicais de 50%/70%.
Modelo ajustado inclui log da renda PPC e usuários da internet, por ano exato.
Correção Benjamini–Hochberg na família de modelos estimados. Exportar amostra
de cada modelo, erros, intervalos e estados de elegibilidade. Não há inferência
causal; músicas compartilhadas entre mercados e poucos anos limitam a análise.

Piloto Semrush Trends Summary, três domínios e cinco mercados BR/US/GB/DE/JP.
Planejar meses completos compatíveis com o corpus, sem março/2022 parcial.
Credencial SEMRUSH_API_KEY no .env; coleta explícita e limitada, checkpoints,
validação de país/mês/domínio/dispositivo, zero distinto de resposta ausente.
Nenhum acesso comercial disponível em 11/10/2026: registrar pendência.

## Testes e escopo

Reutilizar a fronteira de exportação já aprovada: arquivos públicos, unicidade,
denominadores, cobertura, escala, ausência e origem. TDD por fatias verticais.
Transporte simulado só na fronteira externa da API. Sem alteração do banco,
ranking bruto de países, junção de Radar/2026 ao histórico, compra, commits ou
troca de branch. Especificação local; tracker/triagem não configurados.
