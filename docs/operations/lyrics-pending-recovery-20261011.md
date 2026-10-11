# Recuperação das pendências e das letras — 11/10/2026

## Evidência atual

A contagem de 22.173 músicas corresponde à auditoria de 01h34 BRT, não ao estado
atual. A consulta PostgreSQL somente leitura, às 11h10 BRT, encontrou 19.671
músicas sem resultado `classified`: 17.635 erros técnicos, 1.378 textos
insuficientes, 604 instrumentais, 40 idiomas não suportados, 10 ambiguidades e
4 bloqueios. Resultado instrumental é um desfecho válido; não deve ser convertido
artificialmente em classificação de uma letra inexistente.

Artefatos privados: `data/derived/lyrics/pending-recovery-20261011/`.
`audit.json` registra a observação; `pending-documents.jsonl` preserva os textos,
IDs, hashes e estados observados. `search-targets.jsonl` contém 5.729 documentos
com sinal de texto curto, início ausente ou desfecho que exige verificação.

## Busca e preparação

A interface operacional local `acquire.py` faz somente GETs ao LRCLIB. Consulta
`/api/search`, com oito workers, intervalo global
mínimo de 0,2 segundo, timeouts e duas tentativas limitadas. Confere título e
artista principal normalizados. Na busca, edições duplicadas são aceitas somente
quando a sequência de palavras da letra é igual, ignorando diferenças de caixa,
pontuação e espaços; textos divergentes permanecem separados. Resultados da
primeira passagem via `/api/get` estão preservados no ledger, mas exigem a
revalidação v2 da lista de edições antes de gerar requests. Falhas de rede
continuam elegíveis na retomada. Uma última linha interrompida é preservada em
backup e removida da cauda; corrupção em linhas anteriores bloqueia a retomada.
Um instrumental informado pelo provedor é registrado como evidência, sem gerar
texto. A busca pública de Bambina também localizou sua página no Genius.

`acquisition.jsonl` é o ledger local retomável, uma linha por documento.
`acquisition-status.json` registra progresso e conclusão. Nenhum resultado desses
arquivos altera automaticamente documentos ou snapshots no banco. "Candidata
encontrada" significa texto recuperado, não classificação Gemini concluída nem
garantia de completude musical. Flags persistentes, textos iguais ou sem melhora
demonstrável e versões divergentes não são liberados como correções.

Ao terminar, o processo gera `recovered.requests.jsonl` e
`recovered.selection.jsonl`. Cada nova letra recebe hash, UUID planejado,
linhagem até o documento original, fonte e chave opaca. Somente os direitos
autorizados e documentos fora da quarentena permitem preparação. O exportador e
o validador públicos conferem os requests canônicos: Gemini 3.8 Flash, LOW,
saída 1024, esquema vigente, somente letra no conteúdo visível ao modelo.
Os novos documentos ainda precisam ser registrados e reconciliados antes de
qualquer upload ou submissão.

O piloto inicial de 12 documentos recuperou 10 candidatas melhores e gerou 10
requests com formato válido. Esses requests foram retirados enquanto se
revalida a identidade entre edições. Bambina: 49 → 816 caracteres;
Outta Space: 1.551 → 2.258.
Os 32 testes existentes de aquisição, adaptador Gemini e JSONL passaram.

Retomada, somente se o processo de aquisição não estiver vivo:

```powershell
.\.venv\Scripts\python.exe data/derived/lyrics/pending-recovery-20261011/acquire.py
```

O lock de aquisição é independente do controlador Gemini e impede duas buscas
simultâneas na mesma pasta. A retomada preserva o ledger concluído. O processo
oculto em Windows tem PID wrapper em `acquisition.pid`; conferir também o filho
real e sua linha de comando. Não iniciar outra cópia enquanto estiver vivo.

## Erros técnicos e orçamento

O controlador Gemini existente permanece ativo, com quatro jobs e 6.297
documentos em andamento na observação de 11h18 BRT. Seus payloads, snapshots,
reservas e checkpoint foram preservados.

`current-followup/plan.json` atualiza o planejamento somente local: 10.016
requests técnicos, reserva conservadora estimada de R$287,41, já excluindo as
reservas ativas. O grupo adicional de 21.585 reanálises de resultados anteriores
é saída informativa do planejador existente, não escopo autorizado para envio.
Não submeter nenhum desses grupos diretamente. Quando uma nova letra substitui
um documento desse plano, excluir seu request antigo da seleção combinada;
nunca enviar as duas versões para resolver a mesma pendência.

Às 11h19 BRT, a guarda BRL observou somente R$0,2576534458537116 de margem livre,
com os quatro jobs ainda reservados. Não é saldo atualizado do Console. Há
compromisso conservador global de R$1.760,36418818547783685248; custos desconhecidos
continuam retidos. `financial-observation.json` guarda essa evidência.

Após a conclusão dos jobs, renovar seleção, orçamento e evidências de crédito,
preservar custos desconhecidos e registrar linhagem e ledger das letras novas.
Usar apenas o controlador exclusivo para submissão, dentro do teto BRL vigente.
Troca de conta e liberação de orçamento permanecem decisões humanas.

Não foram feitos novos envios à Gemini por esta recuperação. Não houve mudança
de branch nem commit. A conclusão da busca é independente da conclusão das
classificações; consultar os dois estados antes de informar pendências resolvidas.

## Escopo confirmado e correção da interface pública

O usuário confirmou **corrigir e preparar, deixando os envios para depois**, e
aprovou a validação da interface pública `LrclibClient.fetch`. O cliente agora
recupera edições com a mesma sequência de palavras, consulta a edição resolvida
em `/api/get` e confere novamente título, artista, texto e indicação instrumental.
Edições com letras divergentes continuam retidas. Se a consulta da edição falhar
por indisponibilidade ou timeout, uma letra já verificada como igual entre as
edições pode ser reutilizada, preservando os metadados do registro de busca.
Não se acrescentam palavras nem se combinam letras de versões diferentes.

Testes na interface pública reproduziram a rejeição indevida de edições iguais
antes da correção. Cobrem recuperação, variações de formatação, outro artista,
versão ao vivo, texto divergente, indicação instrumental contraditória, timeout
e indisponibilidade do endpoint. Validação final: 207 testes de letras, Ruff e
mypy aprovados.

O marcador independente `controller.stop` registra a escolha de preparação
sem novas submissões. O checkpoint confirmou `stopped` às 11h40 BRT, com motivo
`controller_stop_requested`. Os jobs remotos existentes não foram cancelados;
seus registros e reservas continuam preservados para reconciliação. O controlador
pode ainda estar encerrando sua auditoria local após escrever o estado terminal.
Uma retomada de envios exige uma decisão humana posterior, além das verificações
financeiras e de seleção. A busca GET-only continua independente desse bloqueio.

## Retomada autorizada às 12h00 BRT

O usuário solicitou explicitamente iniciar o controlador de envio à API. O
preflight confirmou ADC, banco, bucket, modelo e LOW. A reconciliação somente
leitura confirmou 181 runs no checkpoint: 177 importados e quatro em andamento,
sem preparação interrompida, reserva preparada para envio ou outro controlador.
Os quatro jobs e seus 6.297 documentos foram preservados, junto com todas as
reservas e a política BRL. A margem observada antes de reconciliar esses jobs era
R$0,2576534458537116; não foi criada autorização para ultrapassá-la.

Evidências em `pending-recovery-20261011/resume-145941/`: checkpoint e política
anteriores, marcador de parada preservado, reconciliação, checkpoint ativado e
confirmação de lançamento. O marcador foi retirado sob lock exclusivo e o estado
reativado pela autorização humana. Processo real 13628, wrapper 19232, Windows
oculto, quatro jobs e polling de 30 segundos. A guarda financeira e os limites
de tentativas continuam vigentes. As letras novas nos artefatos de aquisição
continuam separadas; esta retomada não registra nem submete esses arquivos.
