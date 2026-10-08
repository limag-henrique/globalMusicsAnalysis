# Qualidade do corpus para o artigo

Escopo autorizado em 2026-10-07: usar os rankings e artefatos existentes, melhorar
qualidade técnica e reduzir gasto API desnecessário. A população geral dos países
é o alvo de interpretação, mas a unidade observada continua sendo a música nos
rankings por plataforma, território e período. Não estimar proporção de habitantes
ou adesão aos temas a partir de contagens de streams/rank.

## Contrato

- Preservar documentos, snapshots imutáveis e bancos. Sem commits ou troca de branch.
- Canary/piloto e taxonomia permanecem vigentes; não executar novas chamadas pagas
  para esta auditoria. Reconciliar jobs já enviados; segurar novos envios durante fixes.
- Testar interfaces públicas de append, seleção/retry, painel e exportação.
- Append deve vincular hash ao documento; retries devem excluir resultado válido
  de mesma assinatura, qualquer reserva ativa e direitos não autorizados.
- Painel balanceado deve intersectar períodos observados. Nunca preencher ausência
  com zero, nem misturar frequências ou plataformas como um mesmo construto.
- Comparações de conteúdo e turnover preservam a célula de fonte/plataforma/chart.
  Pesos ordinais são proxies de rank; não são ouvintes, streams ou população.
- A seleção científica dos snapshots explicita status, validação Pydantic, identidade,
  fonte/quarentena, hash, modelo/prompt/taxonomia e faltantes. Não promover candidatos
  de correspondência textual a gravações confirmadas.
- Diagnóstico local atualizado deve reportar cobertura e impedimentos, sem letras ou
  inferências de nacionalidade. Ligação de corpus legado aos rankings exige evidência
  auditável; o importador atual gerou UUIDs diferentes e descartou identificadores.

## Entregáveis

Correções verificadas nas interfaces acima, relatório reproduzível do banco e dos
artefatos, seleção com proveniência e lista de correspondências candidatas para
validação. Documentar lacunas que dados disponíveis não permitem resolver e critérios
de liberação científica. Validação humana independente não será inventada.

## Fundamentação

Spotify explica que streams elegíveis para charts são um subconjunto filtrado:
https://support.spotify.com/dm/artists/article/understanding-spotify-charts/
Erros de mensuração exigem validação e análise de sensibilidade:
https://pmc.ncbi.nlm.nih.gov/articles/PMC7450672/
https://pmc.ncbi.nlm.nih.gov/articles/PMC7272296/
