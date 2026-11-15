# Integração exploratória de listas anuais publicadas — 15/11/2026

O novo snapshot `data/derived/annual_revision/global-rescan-2018-2026-20261115-v5-published-provisional-0003` acrescenta 880 participações provisórias da Eslovênia: posições 1–110 de cada ano de 2018 a 2025. São 91.480 observações de 277.650 posições com cota conhecida (32,947956%); permanecem 186.170 posições ausentes. A matriz conserva os 250 mercados, 2.250 células e todas as cotas anteriores.

## Conteúdo e limite de uso

As 4.000 linhas das listas IPF (500 por ano) foram preservadas anteriormente. O novo suplemento vincula os anos dessas listas ao exercício de janeiro a dezembro definido no artigo 2 das versões oficiais das regras da IPF. As páginas relevantes dos PDFs foram renderizadas e lidas; essa conferência assistida por IA não constitui adjudicação humana. A associação entre ano da tabela estatística e exercício definido nas regras é registrada como inferência documental, ainda pendente de revisão.

As linhas incorporadas têm o estado `PROVISIONAL_SOURCE_PERIOD_BINDING_REVIEW_REQUIRED`. São identificadores nativos de entradas de chart; a gravação e a edição textual continuam pendentes. As métricas permanecem nulas. O estrato é de estatísticas nacionais de execução pública da IPF e precisa de revisão metodológica antes de uso conjunto com os demais estratos. Não há aprovação científica, letra aprovada ou autorização de envio derivada dessa integração.

## Artefatos para conferência

- Seleção anterior, preservada: `data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002`.
- Suplemento documental: `data/derived/annual_revision/ipf-si-calendar-documented-2018-2025-20261115-0002`.
- Documentos primários, hashes e páginas renderizadas: `data/raw/published_annual/ipf-period-evidence-20261115-0003`.
- Nova seleção: `data/derived/annual_revision/global-rescan-2018-2026-20261115-v5-published-provisional-0003`.
- Fila de revisão: `published_annual_review_queue.jsonl`, com 880 entradas dentro da nova seleção.
- Auditoria das 2.250 células: `cell_semantics_audit.json`, com zero divergências.
- Conferência da preservação e dos incrementos: `overlay_audit_report.json`.
- Avaliação dos portões: `data/runtime/research-execution-20261115/audit-v5-published-provisional-0003`; G1 reprovado, numerador zero; G2–G5 pendentes.

Os arquivos `combined.jsonl` e `ranked_titles.jsonl` preservam os bytes anteriores como prefixo. Os cinco outros artefatos não alterados mantêm os hashes. Apenas as oito células IPF têm seus contadores modificados. Todas as 880 novas observações contam como provisórias e nenhuma como cobertura de calendário completo aprovada. A tabela de fontes passa de 997 para 1.005 objetos válidos.

## Reprodução

```powershell
& .venv/Scripts/python.exe scripts/build_published_annual_overlay.py --parent data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002 --supplement data/derived/annual_revision/ipf-si-calendar-documented-2018-2025-20261115-0002 --output data/derived/annual_revision/NOVA-REVISAO-IMUTAVEL
```

O destino deve ser novo. O integrador confere os hashes do suplemento, os documentos primários, as páginas de origem e a vinculação ao manifesto do pai. Ele rejeita células já ocupadas, cotas incompletas, posições repetidas, identidade divergente entre a seleção e a lista integral, datas incompatíveis e métricas sintéticas. Ao final, executa `load_selection` sobre o resultado.

Validação executada: 19 testes de lista publicada e integração passaram; Ruff passou. Os testes cobrem colisões, lista integral truncada, subcota, métricas incompatíveis, identidade, período, posição duplicada, aprovação herdada e contagem de posições provisórias.

## Fontes que não representam incremento

Os nove arquivos anuais de YouTube do Zenodo 23645386 já estavam vinculados por SHA-256 ao manifesto v4. A auditoria `data/runtime/zenodo-existing-coverage-audit-20261115-0002` confrontou os MD5 publicados na API atual, tamanhos e hashes locais: 1.944.951 linhas examinadas, das quais 1.900.751 nacionais, em 387 células nacionais. Incremento observado: zero.

A página da Mix FM 102.3, no Chipre, foi registrada em `research/global_inventory/source_registry_20261115_ipf_mixfm.json`. Ela anuncia Top 100 anuais de 2019 a 2025. Trata-se de chart de uma emissora e não demonstra consumo nacional. O registro permanece sem prontidão de incorporação, com sua página preservada em `data/raw/published_annual/mixfm-source-context-20261115-0001`.
