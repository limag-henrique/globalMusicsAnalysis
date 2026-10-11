# Indicadores contextuais por mercado

Escopo alinhado em 10/10/2026: integrar coleta reproduzível e CSV, usar mercados do
corpus, priorizar o histórico musical e manter coletas recentes separadas. São
aceitas exportações originais do Google Trends quando não houver acesso à alfa.

## Contrato

- Descobrir pares mercado/ano no CSV anual do corpus; excluir GLOBAL, HK e PR
  conforme os critérios do relatório. Não alterar o corpus musical.
- Planejar termos em inglês e nos idiomas principais de cada mercado. O léxico
  local é uma proposta para revisão linguística, não uma lista validada por nativos.
- Trends mede interesse relativo de busca; Radar mede participação geográfica
  nas consultas DNS ao 1.1.1.1 de cada domínio. Nenhum mede pessoas ou visitas.
- Preservar respostas brutas, hashes, período, fonte, escala e ausência de dados.
- Índices 0–100 de exportações locais não sustentam ranking entre países ou
  média entre consultas independentemente escaladas. Manter cada série separada.
- Radar usa janelas explícitas de até 31 dias por domínio, sem somar percentuais.
- Período final de 2022: até 13/03 inclusive; os anos anteriores são janelas
  anuais de contexto, sem afirmar que todos os mercados tiveram charts o ano todo.

## Interface e testes acordados

Uma interface de exportação produz plano de consultas, indicadores e manifesto.
Testes observam CSVs e validação das entradas nessa fronteira: país/período,
ausência versus zero, escala/proveniência e resposta realista do Radar através
de transporte HTTP controlado. Não testar implementação interna.

## Acesso e limites

Não foram encontradas credenciais das fontes nem exportações do Trends. O plano
e a matriz de cobertura podem ser produzidos agora; medições dependem desses
insumos. Não inventar endpoint da alfa ou usar scraping não oficial silencioso.
Similarweb e Semrush ficam fora da primeira etapa por ausência de acesso pago.

Atualização em 11/10/2026: usuário forneceu token Radar no `.env` e autorizou
automação das consultas Trends. O CLI lê o token local; Radar usa limite 200
confirmado pela resposta real. Implementado coletor retomável para endpoints da
interface pública, identificado como não oficial, com intervalo e parada em 429.
Na execução, o endpoint direto foi bloqueado; o navegador Edge conectado permitiu
exportar os CSVs originais. A fila de navegador agrupa até cinco termos por país,
usa toda a janela histórica daquele mercado e registra grupo de comparação.
Isso muda a escala: um ano recebe as amostras daquele ano, mas os índices continuam
normalizados pela janela completa e pelo lote de termos. Não confundir com os
índices das consultas anuais individuais. Termos-âncora repetidos não são somados.

Especificação local: o issue tracker e vocabulário de triagem exigidos pela skill
to-spec não estão configurados para esta sessão; nenhuma issue será publicada.

Fontes: https://developers.google.com/search/apis/trends ;
https://support.google.com/trends/answer/4365533?hl=pt-BR ;
https://developers.cloudflare.com/api/resources/radar/subresources/dns/subresources/top/methods/locations/
