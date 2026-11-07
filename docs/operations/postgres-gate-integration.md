# Validação isolada do gate em PostgreSQL

## Procedimento reproduzível

Executar `scripts/validate_postgres_gate.py` com o Python do ambiente do projeto.
O script aceita somente a origem local configurada em `127.0.0.1:55433`. Ele não
inicia, para ou reconfigura esse servidor. Credenciais da origem ficam apenas em
memória/ambiente do subprocesso e não são escritas nos relatórios/comandos.

```powershell
.\.venv\Scripts\python.exe scripts/validate_postgres_gate.py
```

A origem deve estar disponível. O procedimento:

1. Abre transações de leitura com `default_transaction_read_only=on`, timezone UTC
   e isolamento repeatable read para o manifesto de dados.
2. Executa `pg_dump` custom, sem owners/privilégios, com sessão somente leitura e
   snapshot consistente. Não executa DML/DDL na origem.
3. Inicializa um cluster PostgreSQL 16 independente, em diretório ASCII específico
   em `%LOCALAPPDATA%/ChartObservatory/gate-validation/<run_id>/cluster`.
4. Inicia somente a cópia em `127.0.0.1:55439`, sem preload de extensões, sem
   archiving e com transações somente leitura por padrão.
5. Restaura o dump completo em `gate_source_<run_id>` e verifica os manifestos.
6. Restaura o esquema real `public`, incluindo FKs, sequências e triggers, em
   `gate_integration_<run_id>`, reservado aos registros sintéticos dos testes.
7. Executa a suíte PostgreSQL do gate e o teste existente do advisory lock.
8. Confere a cópia de pesquisa e a origem novamente e para somente o cluster
   isolado, inclusive quando ocorre falha.

O cluster de cópia usa autenticação trust apenas em loopback para uma execução
local temporária, sem escutar interfaces externas. Não é configuração de serviço
de produção. O diretório é novo por execução, e os testes exigem nome exato do
banco, porta, marcador de execução, comentário do banco e data_directory
compatíveis. Um endpoint arbitrário, inclusive o real, é recusado.

O caminho ASCII evita problemas do PostgreSQL Windows com o nome acentuado do
workspace. Temporários de artefatos batch continuam no volume D do projeto para
respeitar a política existente. stdout/stderr de `pg_ctl` vão a arquivos: pipes
herdados por processos do servidor podem impedir o retorno do inicializador.

## O que os testes exercitam

- Online, force, estimate e seleção de não classificados: evidência ausente,
  pendente, revogada, fonte suspensa e hash divergente bloqueiam geração/tokens.
- Aprovação explícita permite classificação com adapter falso; repetição reutiliza
  o resultado; force acrescenta histórico e mantém a ligação com o snapshot anterior.
- Estimativa aprovada conta tokens no adapter falso e não gera classificação.
- PostgreSQL confirma UUID/FK reais e trigger de imutabilidade, inclusive contra
  UPDATE SQL direto. Os testes não usam `Base.metadata.create_all()` para substituir
  o esquema restaurado.
- Batch passa por preflight offline, reserva, JSONL, estimativa, upload falso e
  submissão falsa. Ausência/revogação/pendência/suspensão bloqueiam antes de tokens
  e upload; alterações posteriores ao upload bloqueiam antes de verificar storage
  ou submeter a Vertex.
- Retry reavalia a adjudicação, inclusive com `include_identity_holds=True`.
- Revogação persistida por uma segunda conexão é observada antes de gerar.
- Advisory lock continua exclusivo após commit e é liberado ao terminar.
- Dez documentos reais da cópia são avaliados somente em leitura. O banco copiado
  rejeita UPDATE por sua configuração somente leitura.

Os testes não usam SQLite nesses fluxos. Os commits da aplicação são
exercitados com PostgreSQL e savepoints sob uma transação externa dos testes;
rollback remove os registros sintéticos sem apagar snapshots imutáveis por DELETE.
O teste entre conexões deixa um documento sintético revogado apenas no banco de
teste. Os bancos de pesquisa original e restaurado não recebem fixtures.

## Ausência de chamadas pagas

Adapters de classificação, tokens, GCS e Vertex são falsos. HTTP (`httpx`/requests),
ADC e criação de cliente GenAI real são substituídos por funções que falham. Não
se realiza login nem consulta de cobrança. As políticas de orçamento não são
certificadas por essa suíte: o orçamento também é falso e não atesta o ledger real.

A assinatura atual v3 mantém sua proibição de despacho online. Para exercitar
os caminhos online positivos, a suíte altera somente a constante em memória do
processo de testes para v2, com adapter falso; não modifica configuração, prompt
ou registros reais. Batch exercita o protocolo atual com orçamento offline falso.

## Evidência e limites

O manifesto compara contagens de `canonical_tracks`, `lyric_documents`,
`lyric_classification_snapshots`, `quota_lyric_staging_candidates` e
`quota_lyric_staging_blobs`, além da versão Alembic. Para todas as gravações,
documentos e snapshots, calcula SHA256 da sequência ordenada de `id:md5(row_json)`.
Isso detecta alterações lógicas em qualquer coluna desses registros sem publicar
as letras. As tabelas de staging são conciliadas por contagem; não se afirma que
todos os seus campos foram hashados. Não são hashes físicos de arquivos ou uma
auditoria completa de todos os objetos do banco.

Um dump pode ser reutilizado sem nova exportação:

```powershell
.\.venv\Scripts\python.exe scripts/validate_postgres_gate.py --snapshot-from DIRETORIO_DA_EXECUCAO
```

Reuso exige marcador correto, SHA256 integral do dump e manifesto da origem ainda
igual ao da exportação. A origem pode ter outros clientes: mudança concorrente dos
registros observados faz a conciliação falhar, sem interromper esses clientes.

Dump completo, cluster, logs e XML ficam privados no diretório temporário de
execução. Não versionar ou publicar esses arquivos, pois contêm letras e dados
operacionais. O relatório público deve conter somente contagens, hashes e
resultados. As cópias são preservadas paradas, sem exclusão automática.

## Resultado observado — 06/11/2026

Execução `8e930ac099db495c89d67c6a10b46637`, concluída às 22:24:55 BRT.
Servidor isolado PostgreSQL **16.15**, esquema de origem Alembic
`0015_gemini_batch`. **41 testes passaram em 3,79 s, sem skips.** Ruff passou
nos dois arquivos Python adicionados; não foi necessário alterar o gate para
que funcionasse no PostgreSQL.

Foram conciliados antes/depois, na origem e na cópia:

| Tabela | Registros preservados |
|---|---:|
| canonical_tracks | 159.080 |
| lyric_documents | 159.111 |
| lyric_classification_snapshots | 167.952 |
| quota_lyric_staging_candidates | 766.071 |
| quota_lyric_staging_blobs | 27.094 |

As contagens de staging abrangem os snapshots históricos, não apenas os
candidatos da última seleção. Os manifestos de todos os registros de gravações,
letras e classificações permaneceram iguais. O dump custom completo tem
537.095.312 bytes e SHA256
`530d7e43c0bcc5883c2526d24ffbf174b6b5393be0c9c2101fcc78ea6efa844a`.

A porta isolada 55439 estava fechada após a execução; a origem em 55433
continuava disponível. Não houve chamadas pagas, DML/DDL na origem, mudança de
configuração do servidor real ou concessão de aprovação a documentos reais.

Evidência pública sem letras/credenciais:
[manifesto de preservação e execução](../audit/2026-11-06/postgres-gate-validation.json)
e [resultado individual dos testes](../audit/2026-11-06/postgres-gate-test-results.json).

A preparação inicial recusou copiar um cluster que passou a estar ativo. O
procedimento final usou dump lógico somente leitura. Dois ajustes de infraestrutura
foram necessários antes da execução bem-sucedida: diretório ASCII no Windows e
redirecionamento de pg_ctl para arquivos em vez de pipes herdáveis. Não foram
falhas de elegibilidade ou de dados. O dump foi reaproveitado com hash e manifesto
conferidos, sem nova exportação da origem.
