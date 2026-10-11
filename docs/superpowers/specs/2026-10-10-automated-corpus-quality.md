# Correção automatizada da qualidade do corpus

Escopo confirmado pelo usuário em 10/10/2026: corrigir aquisição/limpeza,
testar interfaces públicas com fixtures locais e produzir derivados versionados.
Não haverá avaliação humana. Confiança declarada é critério operacional,
sem alegação de calibração ou acurácia medida.

## Contrato

- Banco, documentos, snapshots, manifesto, controlador vivo e suas entradas
  permanecem intactos. Nenhum envio, reanálise paga ou chamada de aquisição real.
- Testes nas interfaces `GeniusClient.fetch`, `LetrasClient.fetch`,
  `legacy_annotation_candidate` e no comando local de correção/auditoria.
- Extração deve preservar todos os contêineres/seções e decodificar entidades.
  HTML aninhado não pode encerrar artificialmente o primeiro contêiner.
- Remover rodapé somente com assinatura extensa e posição terminal; não apagar
  palavras ou versos por tema. Texto curto/segunda seção são sinais, não prova.
- Derivado mantém ID/hash original, hash novo, versão, razões e direitos.
  Resultado do texto original não é promovido a classificação do derivado.
- Validação automatizada de esquema, status, uso/custo, ID/hash, resíduos,
  possíveis fragmentos, quarentena, duplicação e incoerência de stance.
- Comparar todas as categorias e intensidades dos duplicados, não só os escores.
  Não escolher uma nota correta pela confiança nem sobrescrever divergências.
- Confiança >=0,80 é filtro operacional explícito (faixa de evidência clara do
  prompt atual), ajustável na CLI; não supera erros ou falta de identidade.
- Não alterar taxonomia/prompt/modelo durante execução; dúvidas semânticas ficam
  em diagnóstico automatizado, sem escores fabricados.
- Relatório define seleção exploratória operacional separada da elegibilidade
  científica estrita vigente. Sem inferência populacional ou ligação inventada
  aos rankings.

## Saída e performance

Novo diretório exclusivo, manifesto JSONL sem letras e derivados textuais apenas
em Parquet local, direitos preservados, sem upload. Leitura PostgreSQL 16 somente
leitura em snapshot consistente, colunas mínimas, streaming; nenhuma rede paga.
Publicar relatório de antes/depois e pendências automáticas. Reexecutar apenas
em diretório novo. Atualizar Graphify local, sem LLM, commits ou troca de branch.

## Reprodução e diagnóstico

Fixtures devem tornar vermelhos os casos observados: perda de texto em HTML
aninhado e rodapé/entidades em aquisição. Hipóteses: (1) regex termina no primeiro
`</div>` interno; (2) limpeza não reconhece o rodapé terminal; (3) substituições
manuais não decodificam entidades numéricas; (4) importação descarta proveniência.
Nenhuma hipótese identifica automaticamente a origem de cada documento legado.
