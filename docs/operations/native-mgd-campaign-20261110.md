# Reconstrução nativa MGD em campanha retomável — 10/11/2026

O novo executor `scripts/run_native_mgd_evidence.py` prepara evidências para G1
em todas as células cuja fonte principal congelada é MGD/Spotify. A seleção atual
contém 154 células em 61 mercados, correspondentes a 22.810 posições já
observadas. Isso não acrescenta músicas inexistentes nem preenche outros mercados.

## Executar e retomar

```powershell
.venv/Scripts/python.exe -u scripts/run_native_mgd_evidence.py --selection data/derived/annual_revision/global-2018-2026-20261108 --output data/runtime/native-mgd-campaign-20261110 --limit 154 --workers 3
```

Repetir o mesmo comando retoma somente os itens não concluídos. O limite padrão
é 20 células e pode ser ampliado sem repetir os anteriores. Há no máximo três
workers. A conexão SQLite de propriedade mantém um lock do sistema operacional;
uma segunda execução concorrente é recusada, e um crash libera o lock sem
excluir arquivos nem adivinhar o estado de um PID antigo.

O executor valida o manifesto congelado, a fonte por país no inventário MGD e
os hashes do código. Cada tentativa usa um diretório novo. A retomada verifica
os bytes de todos os artefatos e insumos antes de reutilizar uma célula. Alterar
a seleção, o inventário ou a implementação exige uma campanha nova.

## Acompanhamento

`data/runtime/native-mgd-campaign-20261110/status.json` é substituído atomicamente
a cada resultado. Contém as células concluídas, falhas por tipo, evidência por
célula e os denominadores. `campaign.json` preserva o plano de todas as células;
`cells.jsonl` registra o resultado consolidado ao terminar.

Indicadores separados:

- posições selecionadas examinadas;
- coincidência de posição e soma de métricas;
- coincidência literal dos metadados;
- células com reconstrução estrutural íntegra;
- número de observações nativas examinadas;
- participação do diagnóstico sobre as 92.000 posições observadas e sobre as
  277.650 previstas;
- posições cientificamente aprovadas, mantidas em zero até adjudicação real.

Os nomes diferentes e ausentes permanecem explícitos. Confirmação numérica não
certifica autoria, edição textual, qualidade da letra ou direitos. O executor
não fabrica assinatura de avaliador nem muda os estados de G1–G5.

## Limitações preservadas

Esta campanha lê arquivos locais e escreve somente em runtime. Não usa rede,
não altera PostgreSQL, não inicia Vertex nem gera custo de inferência. O valor
`production_writes=0` se refere ao banco da pesquisa; o SQLite local é apenas o
lock do executor.

Mesmo a reconstrução de todas as 22.810 posições MGD representa somente 8,22%
das 277.650 previstas. Essa quantidade pertence à cobertura já observada,
não é backfill de posições faltantes. O mínimo mundial de 80% e a aprovação de
cada país/ano continuam dependendo das fontes faltantes e de evidência científica.
Nenhum território é retirado do denominador para fazer a meta passar.
