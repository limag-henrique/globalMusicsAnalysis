# Conferência do andamento — 10/11/2026

Inspeção somente de leitura em 10/11/2026, aproximadamente 19:36 BRT. Não foram
iniciados coletores, serviços, inferência ou escrita no banco de produção.

| Medida | Numerador / denominador | Percentual | O que significa |
| --- | --- | ---: | --- |
| Posições de ranking observadas | 92.000 / 277.650 | 33,14% | Disponibilidade; inclui provisórios e não equivale a posições certificadas |
| Mercados com algum vínculo | 76 / 250 | 30,40% | Algum dado disponível, sem comprovar completude por mercado |
| Células país/ano com algum vínculo | 622 / 2.250 | 27,64% | Algum dado disponível por célula |
| Candidatos com texto no staging local | 27.606 / 30.927 | 89,26% | Texto armazenado, sem validação de identidade/completude/direitos |
| Comparação web processada | 7.123 / 30.927 | 23,03% | Verificação da campanha histórica; zero aprovações declaradas |
| Portões aprovados no audit-0003 | 0 / 5 | 0% | Nenhuma etapa científica liberada pela evidência auditada |

Faltam 185.650 posições para preencher as cotas definidas e pelo menos 130.120
posições observadas adicionais para alcançar 80% global de disponibilidade. O
critério também exige aprovação em cada país/ano: esse cálculo global é apenas
um limite inferior, não uma previsão de aprovação de G1. Há 72 células com cota
indefinida. Permanecem 3.321 candidatos sem texto nesse snapshot de seleção.

Os percentuais têm denominadores e unidades distintos. Não podem ser somados
nem promediados para criar um percentual geral. O fluxo completo tem zero
resultados finais aprovados na auditoria; isso não afirma que os textos estejam
todos errados nem certifica o estado atual do banco indisponível. A quantidade
de testes técnicos aprovados também não mede validação científica.

## Processos e banco

`Win32_Process` não encontrou os PIDs históricos 1104, 9140, 24632 e 17232,
nem processos Python com os scripts relevantes de aquisição, comparação e
finalização pesquisados. Os status históricos não demonstram trabalho atual.

Foi tentada consulta PostgreSQL com conexão de cinco segundos, limite de
consulta de quinze segundos e transação `REPEATABLE READ READ ONLY`. A conexão
falhou com `OperationalError`; endereço, usuário e credenciais não foram
expostos. Não foi possível certificar uma fotografia atual do banco.

## Evidências locais

- `data/runtime/research-flow-20261110/audit-0003`: `verify_audit` concluiu sem
  divergências. G1 reprovado; G2–G5 pendentes; zero células aprovadas em G1.
- `data/derived/annual_revision/global-2018-2026-20261108/manifest.json`:
  SHA-256 `7326d355ec797a324afbcd7e985693c6528052c6352fe1b1796dee74090e9e88`.
- `data/runtime/global-lyrics-20261108/final-staging/status.json`: run
  `2115f77ad00d7dbf879e98beba453e894bcbd710d8adaae3e2862463ad805f7d`, atualizado
  em 08/11 às 20:41:22 BRT; SHA-256
  `0acdded8a76e0f343573ae9a35492b7d5997c04f14addedb8ea8c15a6ac9b68c`.
- `data/runtime/import-all-lyrics-web-comparison-global-20261108/status.json`:
  atualizado em 08/11 às 21:04:48 BRT; SHA-256
  `ad6f3c2799a84abd0f7ecac57a9a52b90c55645e665beef7443fb386bebde0d3`.
- O staging posterior em `publication/cycle-004610/staging/status.json` na
  mesma campanha repete o mesmo run e 27.606 textos, às 21:00:50 BRT de 08/11;
  SHA-256 `d8fad3284e46c6fa60c888370fbf49c75f492b628a3964ba6837927e6418992e`.

A auditoria de cadeia de fonte usa outro run e não foi misturada a esses totais.
