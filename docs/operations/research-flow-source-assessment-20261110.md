# Avaliação independente das fontes e da continuidade — 10/11/2026

Inspeção local de código, artefatos e processos, sem modificar coletores, banco,
status anteriores ou resultados. Não houve coleta web, upload ou inferência.

## Estado que as evidências permitem afirmar

| Objeto | Evidência local | Interpretação permitida |
| --- | --- | --- |
| Seleção mundial | `data/derived/annual_revision/global-2018-2026-20261108/manifest.json` | 250 entradas geográficas, 2.250 células, 277.650 posições com cota, 92.000 vínculos, 30.927 identidades candidatas; não representa cumprimento de 80% |
| Importação histórica | `verification.json` no mesmo diretório | Preservação/importação/idempotência verificadas na execução histórica; não adjudica a posição, a gravação ou a letra |
| Staging global final da aquisição | `data/runtime/global-lyrics-20261108/final-staging/status.json` | Run `2115f77ad00d7dbf879e98beba453e894bcbd710d8adaae3e2862463ad805f7d`, 30.927 candidatos, 27.606 com texto, 24.609 hashes textuais distintos, zero candidatos liberados; fotografia de 08/11/2026 às 20:41 BRT |
| Comparação web global | `data/runtime/import-all-lyrics-web-comparison-global-20261108/status.json` | 7.123 resultados, 208 propostas, 200 publicações, zero aprovações; última atualização 08/11 às 21:04 BRT |
| Auditoria de cadeia de fonte | `data/runtime/vertex-global-preparation-20261108/source-audit/status.json` | 30.927 examinados, 25.248 cadeias reproduzidas, 991 evidências brutas não resolvidas, 4.568 ausências e 120 vínculos com metadados pendentes; zero identidades/completudes validadas; run diferente do staging final |
| Dossiê anterior | `data/runtime/vertex-global-preparation-20261108/dossier-intake-0001/readiness.json` | 26.563 textos nessa fotografia mais antiga, zero documentos canônicos elegíveis; não usar como contagem atual |

As fotografias não devem ser combinadas como se pertencessem ao mesmo run. Em
particular, 27.606/30.927 (~89,26%) mede disponibilidade nesse staging, sem
comprovar identidade, integridade ou direitos. Não aprova G2.

Consulta `Win32_Process` não encontrou os PIDs históricos 17232 (finalizador),
24632 (comparação web) e 1104 (intake global). Nenhum desses arquivos é prova de
atividade atual. PIDs podem ser reutilizados; verificar também executável e
argumentos antes de qualquer ação sobre processo.

Foi tentada consulta PostgreSQL com `REPEATABLE READ READ ONLY`, timeout de
conexão de cinco segundos e de consulta de 30 segundos. A conexão retornou
`OperationalError`; credenciais e endereço não foram registrados. O estado
atual do PostgreSQL não foi certificado nesta inspeção. Não iniciar/restaurar ou
migrar banco apenas para contornar essa falta de evidência.

## Riscos concretos de integração

- O staging declara por constraints que identidade, completude e classificação
  são falsas e direitos `UNVERIFIED`. Não alterar essas constraints para promover
  dados. A aprovação deve produzir documento canônico com decisão rastreável.
- G2 e G3 devem medir participações país/ano, além dos totais de edições únicas.
  A mesma edição pode cobrir vários vínculos, mas só pode ser reaproveitada com
  associação de gravação confirmada. Metadados YouTube `T:` são opacos.
- Oito territórios têm cota indefinida. Zero ou ausência de denominador não é
  sucesso e não permite excluir silenciosamente essas 72 células do recorte.
- Em `global_annual.assemble`, mercados legados congelados não recebem novas
  posições. Recuperação histórica que altere esses mercados exige uma nova
  seleção versionada e reconstrução integral, preservando a anterior.
- `verify_global_annual_import.py` chama `persist` para verificar idempotência e
  regrava `verification.json`. É uma verificação operacional com possíveis
  escritas, não uma consulta estritamente somente de leitura.
- Calendário completo é diferente de profundidade/identidade corretas. A posição
  calculada pela soma de streams/views observados no Top-K não é o ranking do
  universo de todas as reproduções da plataforma.
- O gate canônico atual valida vínculo e declaração de uma adjudicação. Ele não
  autentica avaliadores, não exige sozinho dois pareceres independentes e não
  verifica os bytes da evidência referenciada. O controlador novo precisa
  acrescentar esses requisitos, sem presumir aprovação do legado.
- Os serviços de produção usam o contrato legado; `review_protocol.TOPICS`
  contém a revisão de 26 tópicos. A preparação nova não pode converter snapshots
  antigos nem liberar serviços legados por equivalência nominal.
- `compare_all_lyrics_web.py` conserva `campaign.json` e seu `ends_at`; uma
  campanha expirada não recebe novo prazo ao relançar o mesmo diretório.
  `finalize_vertex_dossier.py` também usa prazo da campanha de aquisição +27h
  quando existe comparação web. Alterar datas históricas invalidaria a evidência.
- Comparações de texto reproduzido, concordância no mesmo provedor e concordância
  entre sites não equivalem a revisão integral da gravação.

## Continuidade executável com os scripts existentes

Executar na raiz do projeto, com `.venv/Scripts/python.exe`. Os comandos abaixo
são receitas condicionais; não foram executados nesta inspeção. Manter acesso ao
PostgreSQL configurado por `Settings`, seleção/store explícitos, fontes permitidas
e nenhum coletor concorrente. Conservar o corte de 15/10/2026.

```powershell
$base = 'data/derived/annual_revision/global-2018-2026-20261108'
$store = 'data/derived/lyrics/global-20261108'
```

Para obter uma auditoria local nova, após recuperar a disponibilidade do banco:

```powershell
.venv/Scripts/python.exe scripts/audit_current_lyric_corpus.py --output data/runtime/research-flow-20261110/quality-audit --base-root $base --store-root $store
.venv/Scripts/python.exe scripts/verify_lyric_source_chains.py --output data/runtime/research-flow-20261110/source-audit --base-root $base
```

Essas duas auditorias fazem leituras de produção e escrevem somente suas saídas
locais/checkpoints. Usar diretórios novos, conferir `run_id`, `full_inventory` e
hashes antes de combinar conclusões.

Para comparar respostas web atuais, iniciar campanha nova e preservar a anterior:

```powershell
.venv/Scripts/python.exe scripts/compare_all_lyrics_web.py --state-root data/runtime/research-flow-20261110/web-comparison --base-root $base --store-root $store --hours 24
```

Esse comando consulta rede, publica propostas e pode atualizar staging; não
substitui auditoria somente de leitura e não produz aprovação humana. Não usar
`--wait-campaign` para a aquisição histórica já concluída. O reaproveitamento de
respostas só deve ser solicitado quando o verificador comprovar idade e bytes;
as respostas de 08/11 não devem ser tratadas como consultas atuais de 10/11.

Após obter uma fotografia estável e suas auditorias, preparar dossiê novo:

```powershell
.venv/Scripts/python.exe scripts/prepare_vertex_readiness.py --output data/runtime/research-flow-20261110/vertex-dossier --base-root $base
```

O script exige saída ainda inexistente e preços/configuração compatíveis. Ele
produz preparação local com bloqueios e não certifica G1–G5. Não relançar o
finalizador antigo com prazo expirado nem editar sua campanha para ocultar isso.

Recuperar posições ausentes exige as fontes anuais efetivas e nova reconstrução;
não há comando local capaz de criar a evidência histórica indisponível. A fila
de déficits do controlador deve orientar essa aquisição e conservar cada
tentativa, fonte e motivo de falha. Nenhum comando desta receita autoriza envio
Vertex ou elimina o teto de planejamento de US$150.

## Verificação independente do controlador implementado

O novo `tests/unit/test_research_flow.py` passou com 49 testes: fronteira exata
79/80%, reprovação de uma célula escondida por média global, denominadores
indefinidos, quotas inválidas, alteração dos insumos, reconstrução diária completa,
duas revisões independentes e adjudicação, aprovação revogada, ligação exata ao
documento/hash e ausência de escores antes de G4. Também verifica os vínculos das
predições às respostas preservadas e dos rótulos humanos às fichas, a fonte
principal única por célula, a definição territorial da fonte e a preservação de
todos os países/anos e os hashes das saídas, sem rede ou banco.

Três testes em `tests/integration/research/test_research_flow.py` passaram em um
PostgreSQL 16 descartável, vazio e separado, com dados estritamente sintéticos.
Foi comprovado `transaction_read_only=on` durante a consulta canônica, preservação
do estado retornado e bloqueio após revogação/direitos alterados e commit em outra
sessão. Não houve cópia, restauração, migração ou escrita do banco de origem.

Execução isolada: `9842267ee48e47b7a6c6ecf06d487f86`, porta de loopback 60687,
banco `research_flow_test_9842267ee48e47b7a6c6ecf06d487f86`. O cluster foi parado
ao final. Relatório, logs e JUnit ficaram preservados em
`C:/Users/marco/AppData/Local/ChartObservatory/research-flow-tests/9842267ee48e47b7a6c6ecf06d487f86/`.
Esses testes comprovam o comportamento técnico sobre fixtures, sem aprovar a
pesquisa, as fontes ou letras reais.
