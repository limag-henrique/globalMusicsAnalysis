# Preparação local do próximo envio — 10/10/2026

Plano: `data/derived/lyrics/followup-20261010-final/plan.json`.
Interface pública: `scripts/prepare_lyrics_followup.py`.
Especificação: `docs/superpowers/specs/2026-10-10-lyrics-followup-preparation.md`.

## Seleção e artefatos

| Grupo | Documentos | Reserva conservadora projetada BRL |
| --- | ---: | ---: |
| Pendentes elegíveis para tentativa técnica | 35.677 | 1.027,17 |
| Reanálise separada de resultados válidos com textos corrigidos | 17.409 | 512,69 |

Os valores são projeções conservadoras pelos bytes dos requests e limite de saída, usando somente SKUs BRL autenticados. Não representam despesas realizadas nem reservas liberadas pelo controlador. O plano utiliza Gemini 3.8 Flash, LOW e saída 1024. Contém 25.638 requests com texto corrigido. Resultados válidos sem alteração foram reutilizados na seleção, sem novo envio. Fragmentos possíveis, textos muito curtos, identidades em quarentena e resultados fora do retry técnico permitido ficam separados. A confiança declarada pelo modelo não é uma medição de acurácia calibrada.

Os JSONL são privados e contêm letras autorizadas. Os 53.086 requests foram verificados contra hashes do manifesto, tamanho e SHA-256 integral dos arquivos. As chaves UUID4 são únicas, os grupos não compartilham documentos originais e o limite de duas tentativas preserva a linhagem original. Nenhum job foi registrado no banco, reservado, enviado ou carregado ao GCS. Os identificadores planejados e flags não equivalem a autorização de submissão. Custo adicional da preparação: R$ 0.

`preparation-verification.json` registra a conferência integral. Os testes da interface pública cobrem correção dos textos, separação da reanálise, orçamento e bloqueios por atividade, ambiguidade, tentativas e direitos; suíte local de lyrics: 195 testes aprovados. Ruff e mypy aprovados para o novo comando.

## Encerramento da execução corrente

Auditoria preservada em `data/derived/research_quality/post-current-20261010-1545/`.
O checkpoint chegou a `budget_exhausted`, motivo `current_account_reservation_margin_insufficient`. O PID foi conferido pelo Windows e o controlador não está vivo. Os 92 runs da execução, totalizando 36.449 requests, estão importados e vinculados aos snapshots; não há jobs enviados pendentes. O monitor `classifica-o-noturna-das-m-sicas` foi pausado após a preservação da auditoria. O corpus inteiro não está concluído: há 116.898 documentos classificados, correspondendo a 116.867 músicas, e 40.571 documentos com erro.

Custos observados locais: R$ 1.322,43; compromisso conservador: R$ 1.323,14, incluindo R$ 0,71 de componente desconhecido ou retido. Reservas acessórias e de retry: R$ 146,76. A dedução de segurança de crédito da conta é R$ 35,00, separada das reservas. A margem calculada para novo compromisso na conta atual é R$ 0,0167, insuficiente para retomada. A observação autenticada do saldo às 13:21 UTC deve ser renovada antes de qualquer envio; os R$ 1.700 da segunda conta continuam sem vínculo/crédito verificados.

O histórico preserva 61 preparações falhas sem job remoto: sua evidência local exige auditoria dos prefixes e custos antes de retomada. Não devem ser repetidas automaticamente nem tratadas como jobs enviados. Nenhuma reserva desconhecida foi liberada.

## Condições para envio

O plano é um rascunho verificável, com `ready_to_submit=false`. Antes de qualquer envio: atualizar a seleção com o banco após o encerramento, reconciliar preparações falhas e ambiguidades, verificar saldo corrente e validade mensal dos SKUs, registrar versões de documentos/linhagem e IDs/flags no ledger e executar `BrlBudgetPolicy.guard` por lote, mantendo custos desconhecidos e reservas. Apenas o controlador exclusivo pode submeter, com até quatro jobs e consulta a cada 30 segundos. A troca de conta é humana e não zera o histórico financeiro. O teto acumulado segue R$ 3.500.

A reanálise está planejada separadamente e não recebe autorização de gasto da política de retry técnico. Não reutilizar nem repetir `reanalysis_run_ids`. Os custos projetados dos dois grupos não autorizam consumir o saldo anunciado da segunda conta. Não houve geração online, alteração de branch ou commit.
