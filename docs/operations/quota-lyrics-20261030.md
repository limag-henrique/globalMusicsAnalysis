# Aquisição de letras após o ranking anual — 30/10/2026

Solicitação: recuperar letras das músicas selecionadas pelas cotas país/ano,
sem repetir downloads, preservando a versão musical e o texto integral.

O recálculo/importação terminou com 22.835 candidatos e 58.290 participações
país/ano, em 2018–2026, corte 15/10/2026. 214 células continuam com lacunas;
essas lacunas não foram preenchidas com rankings de calendários incompletos.

## Processo ativo

`scripts/acquire_quota_lyrics.py` foi iniciado em segundo plano com janela oculta.
Ele espera o resultado persistido da importação antes de montar a fila.
O primeiro estado observado foi `reconciling_local_library`, com os 22.835
candidatos da seleção nova. Nenhum Gemini ou download de áudio é acionado.

Fluxo: seleção nova → vínculos exatos de plataforma → documentos existentes →
ledger de aquisição anterior → consultas de candidatos ainda sem texto local.

- Reuso de documentos por vínculo a gravação, sem fusão por título parecido.
  Mapeamento canônico ambíguo não autoriza deduplicação de gravações.
- Como o banco recuperado não contém vínculos em `platform_items`, a consulta
  também reaproveita textos candidatos por título **e artista exatamente iguais**.
  Isso evita novo download, mas é explicitamente marcado
  `cached_exact_metadata_not_recording_validation`; não cria vínculo canônico.
- Reuso de documentos locais exige hash correto, direitos já autorizados,
  ausência na quarentena e ausência de sinais de contaminação textual.
- Resultados anteriores de aquisição continuam candidatos, sem validação fictícia.
- Uma tarefa durável por identidade; reserva transacional antes de consultar.
  Reiniciar não envia novamente tarefas já reservadas/concluídas. Uma interrupção
  durante tarefa deixa estado `running` para revisão, evitando repetição cega.
- Texto completo extraído é armazenado em arquivo endereçado por SHA-256;
  dois vínculos com texto idêntico apontam ao mesmo arquivo.
- País/ano/posição/cota e identidades originais são preservados no payload SQLite.

## Fontes e identidade

Consultas sequenciais por tarefa: LRCLIB, Genius, Letras.mus.br, AZLyrics e
Musixmatch público. Para o LRCLIB, título e artista precisam coincidir
estritamente; edições textuais divergentes ficam pendentes. Não se removem os
qualificadores remix, ao vivo, clean/explicit para forçar correspondência.

Nas páginas HTML, a extração exige título e artista nos metadados estruturados
da música; AZLyrics permite também a identificação explícita no título da página.
Só os contêineres próprios de letras são extraídos, incluindo todos os blocos.
Não se usam snippets de busca, texto gerado ou expansão inventada de refrões.
Respostas parciais explicitamente identificadas como snippets são rejeitadas.
Musixmatch não recebe chave inventada nem tem limitações de acesso contornadas.

As páginas podem não fornecer metadados suficientes ou podem bloquear acesso;
esses casos permanecem `not_found_or_unverified`, sem associação automática.
Letras continua em quarentena para uso científico conforme o registro anterior;
eventual coleta nova é marcada `quarantined_source`, sem promoção automática.

**Limite da automação:** correspondência de metadados e extração de todos os
contêineres não comprovam equivalência com a gravação nem que a transcrição da
fonte esteja completa. Todos os resultados conservam `identity_validated=false`,
`completeness_validated=false` e `classification_ready=false` até evidência real
de integridade e identidade, conforme o protocolo do projeto. Texto curto,
resíduos de interface, versões divergentes e outras sinalizações ficam registrados.

## Recursos e acompanhamento

Máquina inspecionada: 12 processadores lógicos e aproximadamente 16 GB RAM.
Aquisição usa seis trabalhadores, no máximo duas requisições por domínio e
intervalo de 0,5 s entre inícios. Cache HTTP conserva respostas bem-sucedidas.
401/403/429 impõem pausa de 15 minutos no domínio; não há contorno de bloqueios.

```powershell
Get-Content data/runtime/quota-lyrics-20261030/status.json
Get-Content data/runtime/quota-lyrics-20261030/errors.log -Tail 20
```

Acervo de candidatos:

- `data/derived/lyrics/quota-20261030/acquisition.sqlite`
- `data/derived/lyrics/quota-20261030/texts/<sha256>.txt`
- `data/derived/lyrics/quota-20261030/http-cache/`

Para retomar após verificar o estado e encerrar qualquer proprietário anterior:

```powershell
. .\scripts\research_environment.ps1
uv run --frozen python -u scripts/acquire_quota_lyrics.py
```

O lock de arquivo impede dois executores simultâneos. Não usar atualização em
massa de `running` para `pending`: pode repetir uma requisição cujo resultado
ainda não foi reconciliado.

Doze testes passaram, cobrindo cache HTTP, reservas persistentes, blob único,
rejeição de versão divergente, preservação do último verso e pausa por domínio.
Ruff passou. A aquisição continua distinta da validação e classificação.

Na verificação após essa otimização, 7.372 candidatos haviam sido reaproveitados
do acervo e 88 recuperados da rede; a fila continuava ativa. Esses números são um
snapshot operacional e não contagens de letras cientificamente validadas.
