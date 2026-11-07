# Gate único de classificação de letras

Implementado em 06/11/2026. Versão: `lyrics-classification-gate-v1`.

## Comportamento

`ClassificationGate`, em `src/chart_observatory/lyrics/classification_gate.py`,
decide a elegibilidade de cada documento. Online, `--only-unclassified`,
`--force`, `--estimate-cost`, reserva/retry batch, exportação, contagem de tokens,
upload e submissão batch usam a mesma decisão positiva.

Direitos autorizados continuam necessários, mas não suficientes. O gate exige:

1. Documento fora da quarentena e fonte não suspensa.
2. Nenhum relato `pending_adjudication` para o documento e hash atuais, inclusive
   relatos positivos ainda não adjudicados.
3. Texto armazenado disponível e SHA256 dos bytes UTF-8 igual ao hash declarado.
4. Adjudicação explícita aprovada, com identidade e integridade verificadas.
5. IDs de documento/gravação, fonte e hash exatamente correspondentes.
6. Método de evidência admitido, URL HTTPS, hash da evidência, avaliador e datas
   com timezone; adjudicação não pode anteceder a verificação.

`force` só muda o reuso do resultado, nunca a qualidade exigida.
`include_identity_holds=True` é mantido por compatibilidade de assinatura e não
libera documentos retidos. Falta/corrupção de arquivos de política interrompe o
fluxo antes de token counting ou geração. Ausência de aprovação exclui o documento
da seleção, sem criar anotação artificial ou alterar seus registros.

## Registro positivo, sem migração destrutiva

O registro fica em `LyricDocument.metadata_json["classification_adjudication"]`.
Nenhum registro foi preenchido automaticamente nesta implementação. A identidade
`confirmed_match` antiga, sucesso de download, flag de provider, comprimento,
aprovação de piloto ou um resultado Gemini anterior não substituem adjudicação.

O formato é validado por `ClassificationAdjudication`; campos extras são recusados:

```json
{
  "gate_version": "lyrics-classification-gate-v1",
  "adjudication_id": "IDENTIFICADOR_DA_DECISAO_REAL",
  "document_id": "UUID_DO_DOCUMENTO",
  "recording_id": "UUID_DA_GRAVACAO",
  "lyrics_hash": "SHA256_UTF8_DO_TEXTO_REAL",
  "source": "FONTE_EXATA_DO_DOCUMENTO",
  "status": "approved",
  "identity_verified": true,
  "integrity_verified": true,
  "method": "human_audio_verification",
  "evidence_url": "https://FONTE_AUTORIZADA/EVIDENCIA",
  "evidence_sha256": "SHA256_DA_EVIDENCIA_PRESERVADA",
  "verified_at": "DATA_ISO8601_COM_TIMEZONE",
  "adjudicated_at": "DATA_ISO8601_COM_TIMEZONE",
  "adjudicator": "RESPONSAVEL_PELA_DECISAO"
}
```

Esse exemplo contém placeholders e é deliberadamente inválido como aprovação.
Os métodos admitidos são `human_audio_verification` e `official_transcription`.
Os booleanos são estritos: strings `"true"` e inteiros `1` não aprovam.

O registro deve ser gravado somente por um processo de revisão autorizado após
conferência real da gravação e transcrição; não deve ser preenchido por scraping,
metadados recebidos de um fornecedor ou inferência do modelo. O gate valida o
vínculo e a declaração; não autentica o avaliador nem verifica remotamente a URL.
Não há nessa alteração uma UI de adjudicação ou promoção automática do staging.

Preservar os demais metadados ao anexar uma decisão. Guardar a evidência original
e o histórico da revisão. Se existir relato pendente para esse hash, resolvê-lo
por adjudicação documentada; anexar uma aprovação não apaga o bloqueio do relato.
Nunca copiar aprovações para outra letra, gravação, fonte ou documento.

## Revalidação e histórico

- Contagem da fila e seleção online usam o mesmo iterador e o mesmo gate.
- Antes de contar tokens/gerar, online recarrega o documento e revalida evidência,
  hash, gravação, texto e idioma em relação ao candidato selecionado.
- Batch valida na reserva, retry, exportação, antes da tokenização e novamente
  antes de upload/submissão. Uma mudança posterior à preparação bloqueia o envio.
- Itens reservados devem corresponder ao documento/hash atual. Antes de enviar,
  o batch recompõe o request e exige seu SHA256 igual ao request congelado,
  contagem integral dos itens e configuração compatível. Uma alteração de idioma
  também invalida o request congelado.
- Rejeição na submissão mantém batch já enviado ao storage como `uploaded`, sem
  modificar letras, apagar o artefato ou chamar Vertex. Preparações novas com
  falha usam o mecanismo existente de rollback/limpeza e estado de falha.
- Jobs já submetidos podem continuar sendo consultados/reconciliados. O gate não
  apaga ou reescreve snapshots e não impede contabilização histórica de custos.

A remediação posterior acrescentou a mesma verificação antes de importar uma
**nova** anotação batch. Uma aprovação revogada gera `BatchIntegrityError` e
retém o output privado para revisão; não cria rótulo científico. Snapshots já
reconciliados permanecem intactos. `lyrics/adjudication.py` registra decisões
transacionais, histórico e compare-and-set por hash/decisão anterior, com locks
PostgreSQL; nenhuma aprovação real foi preenchida automaticamente.

As verificações são feitas nas fronteiras de despacho; não cancelam chamadas já
em voo nem substituem o controle de acesso ao banco e às políticas. Mudanças de
evidência precisam ser persistidas para a revalidação entre sessões observá-las.

Os fluxos sem documento adjudicado `GeminiAnnotationClient.annotate` e
`LyricsEngine.annotate` recusam geração. O backfill exige `--skip-gemini` antes
de iniciar trabalho. Aquisição e interpretação passam a ser operações separadas.
O adaptador baixo nível `GeminiLyricsClassifier` continua disponível para o
serviço controlado e seus testes; não é uma interface alternativa de campanha.

Não foram alteradas tabelas, migrations, cotas, dados reais, autorizações,
orçamentos, prompts ou taxonomia. As restrições de orçamento/protocolo anteriores
continuam valendo depois do gate. Letras históricas sem a nova prova ficam
preservadas e indisponíveis para novas chamadas até revisão explícita.

## Verificação offline

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/lyrics -q --basetemp tmp/pytest-gate-all-lyrics
```

O basetemp no volume do projeto respeita a política existente de temporários
batch no mesmo drive. Os testes usam SQLite temporário e adapters falsos, sem
autenticação, aquisição externa ou chamadas pagas. Fixtures positivas adicionam
aprovações reais do schema somente a textos sintéticos de teste; os testes de
segurança criam documentos sem aprovação e verificam o bloqueio efetivo.

Validação executada em 06/11/2026:

- `tests/unit/lyrics`: 468 passaram, incluindo 44 casos novos do gate.
- `tests/unit`: 723 passaram em 56,59 s; dois avisos de depreciação já existentes
  em leitores CSV Polars (MGD/Kaggle).
- Ruff passou nos arquivos Python alterados.
- Mypy do novo `classification_gate.py` passou com imports seguidos em modo
  silencioso (`--follow-imports=silent --no-incremental`).
- Não foram executados testes live, chamadas Vertex, migrações ou alterações em
  dados reais. A integração PostgreSQL não foi exercitada nesta validação.

Validação posterior no mesmo dia: **41 testes de integração passaram em uma
cópia PostgreSQL 16.15**, com esquema e triggers restaurados, origem acessada
somente em leitura e adapters externos falsos. Consulte o
[procedimento e evidências PostgreSQL](postgres-gate-integration.md).
