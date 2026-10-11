# Cruzamentos do artigo: contrato de importação

Alinhamento de 10/10/2026: usar o período da captação dos rankings, descoberto
nos pares mercado/ano do relatório histórico mais recente. Entrega autorizada:
CSV/Parquet auditáveis e tabela de cruzamentos. A fronteira de teste acordada
é a exportação: países/anos, ausência distinta de zero e junção sem duplicação.

## Problema e solução

As prevalências de temas nas letras precisam de contexto nacional com fontes,
datas e lacunas verificáveis. Importar indicadores externos em arquivos separados,
preservar respostas brutas e hashes, e juntar por mercado e ano de referência.

## Histórias de uso

1. Identificar quais mercados e anos realmente possuem rankings.
2. Consultar indicadores econômicos, de gênero, violência e acesso digital.
3. Distinguir observação zero, ausência na fonte e falha de coleta.
4. Recuperar cada observação no arquivo bruto e endpoint original.
5. Cruzar prevalências anuais sem multiplicar registros do corpus.
6. Verificar ondas WVS/SIGI sem inventar observações anuais.
7. Preservar composição de gêneros e persistência musical por fonte.
8. Reconhecer os cruzamentos ainda dependentes de acesso ou dados indisponíveis.

## Decisões

Mercado de circulação não representa nacionalidade ou características individuais.
Excluir GLOBAL e HK conforme o relatório existente (PR se aparecer). Taiwan é um
mercado próprio; não substituir seu indicador por China. Janela 2017–2021 e 2022
até 13/03. Indicadores anuais de 2022 representam o ano completo e são explicitados
como contexto posterior ao encerramento musical. Não interpolar, carregar o último
valor ou fabricar valores. SIGI permanece por edição e WVS por ano de campo/onda;
nenhuma associação temporal automática. Homicídio feminino não equivale a feminicídio.
OONI mede testes em redes voluntárias: anomalia não confirma bloqueio nem prevalência
populacional. Fontes pagas ou restritas ficam com status explícito.

O importador produz observações longas, matriz completa de cobertura e junção larga
com prevalências. Não altera banco de letras ou dados musicais. Correlações são
exploratórias, acompanhadas de tamanho da amostra e sem alegações causais.
Gêneros multirrótulo não são uma partição; persistência disponível não comprova
impulso TikTok. Não aplicar modelos causais ou apresentar achados como confirmatórios.

## Testes

Testar a interface de exportação com exemplos independentes: zero observado,
valor ausente, indicador fora do ano e duplicata. Validar também unicidade,
intervalos e hashes na coleta real. TDD red/green em uma fronteira pública.

## Notas

As skills to-spec e tdd foram lidas. A fronteira foi confirmada pelo usuário.
O destino de issues e vocabulário de triagem não estão configurados; esta especificação
é local. O recorte geral 2021+ não substitui a janela real explicitamente escolhida.
Não criar commits, mudar branches ou publicar dados.
