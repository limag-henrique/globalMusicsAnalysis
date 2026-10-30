# Revisão das letras após avaliações humanas — 23/10/2026

Estado: aquisição convencional em andamento; classificação e artigo revisados ainda pendentes.
O congelamento anterior é preservado. Não houve commit nem mudança de branch.

## Evidência e resultados reproduzidos

Os oito documentos contestados têm o mesmo hash no artefato histórico, no banco,
no snapshot indicado pelo portal e na seleção do artigo. A falha já está no
artefato de aquisição; o HTML histórico não permite atribuir uma causa única.

A auditoria observou 159.114 documentos. Há 32.904 alvos com sinais textuais;
30.313 pertencem à seleção do artigo. Sinais não comprovam incompletude.
`enrich_recovery_targets.py` resolveu os artistas de todos os alvos sem escrever
no banco. O corpus continua sendo maior que a fila prioritária de recuperação.

`analyze_review_comparison.py` encontrou 34 diferenças de intensidade em 208 pares
de escores e sete diferenças na presença temática, usando o limiar >=2 do artigo.
As unidades independentes são oito músicas, não 208 dimensões. Duas avaliações
foram expostas à IA; nenhuma das oito é padrão definitivo de acurácia.

`compare_revision_rankings.py` reproduziu os denominadores e as contagens positivas
dos 68 mercados e das 26 dimensões antes de gerar sensibilidades. A exclusão dos
oito textos altera 20 posições entre 1.768 células mercado/dimensão, no máximo
uma posição. A exclusão de todos os sinalizados altera até nove posições. São
cenários de exclusão, não rankings corrigidos com novas classificações.

## Aquisição e retomada

O processo é uma execução local única, sem chamadas de IA. Usa LRCLIB e Genius,
cache das respostas, até quatro tarefas ativas e duas requisições por domínio,
com início espaçado e retentativas limitadas. Guarda variantes divergentes;
não escolhe a letra pelo comprimento. Esses provedores não substituem a
verificação de uma fonte oficial do artista ou da edição musical.

A descoberta direta pelo Google extrai somente links, nunca snippets. O teste
real retornou páginas dinâmicas sem links utilizáveis. A busca complementar de
“Culpable” encontrou “Culpables”, cuja identidade permanece pendente.

O lote inicial de 100 músicas produziu 99 candidatos e um não encontrado.
Houve duas fontes para 59 músicas e sequência de palavras igual em seis.
Concordância entre provedores não comprova completude ou independência.

A execução ampliada cobre os 32.904 alvos prioritários. Seu registro atual está em
`expanded-process.json`, na pasta privada de artefatos desta conversa:

`C:/Users/Henrique Lima/.codex/visualizations/2026/10/23/01a1693f-5895-73d2-b03a-cc3df735fce2/corpus-revision/`

O campo `output` desse registro identifica o diretório vigente. Os diretórios
anteriores são preservados. `process.json` registra início e comando, não é um
indicador de atividade em tempo real. Consulte o PID e os logs antes de retomar.

Para uma observação somente leitura, use:

```powershell
.venv/Scripts/python scripts/report_lyrics_recovery.py --targets "CAMINHO/recovery-targets-enriched.jsonl" --ledger "DIRETORIO_VIGENTE/acquisition.jsonl" --output "DIRETORIO_VIGENTE/progress.json"
```

Depois de confirmar que o processo anterior terminou, retome com o mesmo alvo,
diretório e cache:

```powershell
.venv/Scripts/python scripts/recover_reviewed_lyrics.py --targets-jsonl "CAMINHO/recovery-targets-enriched.jsonl" --output-dir "DIRETORIO_VIGENTE" --cache-dir "DIRETORIO_VIGENTE/http-cache" --limit 32904 --workers 4 --all-sources
```

Uma cauda incompleta é preservada antes da retomada; corrupção no meio do registro
interrompe o processamento. A deduplicação usa identidade de gravação e hash,
preservando todos os documentos de origem. Título e artista iguais não fundem
gravações diferentes. Falhas de HTTP permanecem elegíveis para nova tentativa.

O cache pausa abaixo de 1 GiB livre e grava por substituição de arquivo temporário.
Havia aproximadamente 35 GB em temporários LFS durante a execução. Oito cópias
byte a byte idênticas foram removidas após nova verificação, preservando o arquivo
integral e o registro de hashes no C:. A coleta foi retomada no C: para evitar essa
pressão de espaço; nenhuma outra importação foi parada.

## Classificação e critérios para a próxima etapa

Os oito textos reportados estão bloqueados na seleção científica e na fila de
novas classificações pagas. Uma classificação nunca é reaproveitada para outro hash.
O prompt v3 mantém 26 dimensões, esclarece fronteiras e não reconstrói versos.

Os batches v3 têm teto conjunto de US$300. A divisão inicial reserva US$100 para
2026 e limita a revisão histórica a US$200; gastos anteriores não são cobrados
novamente. Reservas em aberto contam antes de outro lote, e as proteções de
conta injetadas continuam aplicáveis. A extensão de 2026 usa `revision_phase="2026"`.
Nenhum envio Gemini foi feito nesta revisão.

Após a coleta: conferir identidade, edição e completude; registrar a fonte e o
hash escolhidos; importar derivados sem sobrescrever originais; contar tokens e
verificar as tarifas da modalidade usada antes do piloto Gemini. As divergências
não resolvidas continuam pendentes. Só depois preparar a nova amostra cega, com
dois avaliadores e adjudicação, recalcular resultados e produzir outra edição do
artigo e dos pacotes. Letras e caches privados não entram nos pacotes públicos.


Artefatos transferidos com verificacao SHA-256 para `D:\PromiscuidadeMusical\data\derived\research_quality\corpus-revision-20261023`; coleta retomada no D:. Referencias historicas: `relocation.json`.
