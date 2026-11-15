# Disponibilidade e restrições das fontes — 11/11/2026

Esta avaliação acompanha a seleção v4-final-0002 e separa disponibilidade de dados,
integridade de extração e aprovação científica. Ela não reduz o denominador
mundial nem autoriza inferir valores de posições ausentes.

## Resultado local auditado

- Escopo congelado: 250 mercados, 2.250 células país/ano, 2018–2026 até
  15/10/2026, 277.650 posições previstas.
- Seleção v4-final-0002: 90.600 vínculos observados (32,63% bruto), sendo 74.140
  definitivos e 16.460 provisórios; 76 mercados e 615 células país/ano com
  posições.
- A v4 adiciona 560 participações ausentes da v3 (IL/2019–2021 e RU/2021).
  Seu relatório de cobertura de fontes tem 997 objetos validados. Os dados de
  posição não alteram o G1: nenhuma participação recebeu aprovação científica.
- A varredura local confirmou que o arquivo Kaggle v151 de 11,1 GB já está
  hash-verificado e contabilizado na cobertura da v4; ele não oferece posições
  marginais adicionais nesta recuperação.
- Auditoria de profundidade: 468 células e 22.351 períodos abaixo da
  profundidade Top-K esperada; 2.261 conflitos e seis pares empatados pendentes.
- G1: zero posições aprovadas cientificamente. Integridade dos arquivos, hashes,
  importação e reconstrução numérica não são adjudicação de identidade/ranking.
- O acervo local Zenodo 23645386 informa séries semanais YouTube Top 100 para
  43 países e Spotify Top 200 para 37. Em 36 mercados Spotify, a série preservada
  tem intervalo de quatro semanas; não basta, sozinha, para reconstruir a soma
  anual. A descrição local registra duplicatas, empates e identificadores vazios.
  Veja [README preservado](../../data/raw/historical_backfill/20261030/zenodo-23645386/README.md)
  e [registro Zenodo](https://zenodo.org/records/23645386).

## Limites de fontes públicas

A página oficial do [YouTube Charts](https://support.google.com/youtube/answer/9014376?hl=en)
lista 61 países/regiões atualmente e descreve Top Songs como visualizações
agregadas de vídeos oficiais, conteúdo de usuários com a gravação oficial e
vídeos de letra. Essa lista atual não prova que cada rota histórica exista para
todos os anos. O recorte de 250 mercados requer outras fontes primárias ou
arquivos licenciados por mercado.

O [Spotify Charts atual](https://charts.spotify.com/home) exige login para
acesso completo. A documentação oficial explica que os charts diários usam dias
em UTC e os semanais cobrem sexta a quinta-feira ([Spotify: Understanding
Charts](https://support.spotify.com/nr/artists/article/understanding-spotify-charts/)).
Ela não documenta um endpoint público de exportação histórica em lote; essa
conclusão decorre da documentação oficial consultada e não prova a inexistência
de acesso privado ou arquivos licenciados. A comunicação oficial de 2021 sobre
o relançamento descreveu Top 200 em 65 mercados principais e gráficos globais
([Spotify for Artists](https://artists.spotify.com/en/blog/celebrating-artist-success-with-spotify-charts)).
O Web API documentado serve catálogo e metadados; não foi localizada uma rota
pública oficial para reconstituir todo o histórico diário/semanal de charts nos
250 mercados.

A [API de charts da Apple](https://developer.apple.com/documentation/applemusicapi/charts)
consulta charts por storefront e aceita até 200 itens. A referência documenta
um endpoint de charts sem parâmetro de data; portanto, inferimos que ele pode
apoiar coleta atual/prospectiva, mas não reparar o histórico de 2018–2025. O
contrato do [Apple Music Feed](https://developer.apple.com/support/terms/apple-developer-program-license-agreement/)
restringe o conteúdo do Feed à promoção do conteúdo Apple dentro do aplicativo;
não o usar para análise interna sem base e autorização próprias.

Não foi localizada fonte primária pública que complete e comprove a profundidade
Top-K para 80% do universo mundial congelado. Isso não prova inexistência de
arquivos licenciados ou fontes nacionais privadas. A recuperação requer acesso
autorizado, prova de cobertura por período, profundidade, métrica, identidade e
termos de uso para cada mercado.

## Auditoria documental das cotas indefinidas

As 72 células sem cota correspondem a oito códigos ISO. A checagem de fontes
governamentais e estatísticas encontrou sete áreas sem população permanente e
uma área habitada:

| Código | Área | Evidência documental | Implicação para a cota |
|---|---|---|---|
| AQ | Antártica | A ONU descreve ausência histórica de população permanente; a população sazonal varia com as estações e bases científicas. ([ONU](https://digitallibrary.un.org/record/71429/files/A_39_583%28PartII%29%5EVol-I%5E-EN.pdf), [Programa Antártico Australiano](https://www.antarctica.gov.au/about-antarctica/people-in-antarctica/how-many/)) | Não usar população sazonal como residente; decisão de aplicabilidade ainda requer regra para mercados sem residentes. |
| BV | Ilha Bouvet | O governo norueguês identifica a ilha como desabitada. ([Regjeringen](https://www.regjeringen.no/no/dokumenter/meld.-st.-33-20142015/id2415895/?ch=2)) | Sem população residente própria para calcular cota. |
| GS | Geórgia do Sul e Sandwich do Sul | O governo do território informa que não há população humana permanente. ([GSGSSI](https://gov.gs/frequently-asked-questions/)) | Equipes sazonais e visitantes não equivalem a mercado residente. |
| HM | Heard e McDonald | O Programa Antártico Australiano informa que as ilhas não são ocupadas por humanos. ([Australian Antarctic Program](https://www.antarctica.gov.au/antarctic-operations/stations-and-field-locations/heard-island/)) | Sem população residente própria para calcular cota. |
| IO | Território Britânico do Oceano Índico | O governo britânico informa ausência de população permanente; há instalação militar em Diego Garcia. ([GOV.UK](https://www.gov.uk/government/publications/british-indian-ocean-territory-knowledge-base-profile/british-indian-ocean-territory-knowledge-base-profile)) | Presença militar não deve ser convertida em população de mercado. |
| TF | Terras Austrais e Antárticas Francesas | O Ministério francês informa ausência de população permanente e presença anual de equipes científicas e técnicas. ([Ministério dos Ultramar](https://www.outre-mer.gouv.fr/territoires/terres-australes-et-antarctiques-francaises)) | Equipes temporárias não fornecem denominador populacional comparável. |
| UM | Ilhas Menores Distantes dos EUA | O Census Bureau diz que essas ilhas geralmente não têm população durante todo o ano e não entram em produtos estatísticos padrão. ([U.S. Census Bureau](https://www2.census.gov/programs-surveys/decennial/2020/technical-documentation/island-areas-tech-docs/demographic_profile/2020-iac-dpsf-technical-documentation.pdf)) | Sem base de população residente anual para a cota atual. |
| SJ | Svalbard e Jan Mayen | Svalbard tinha 3.094 residentes no segundo semestre de 2023 e integra o Reino da Noruega; estatística da ONU registra que a população norueguesa das ilhas também é incluída na população de jure da Noruega. ([Sysselmesteren](https://www.sysselmesteren.no/siteassets/samfunnssikkerhet-og-beredskap/svalbardros-2022-2026---oppdatert-februar-2024.pdf), [UNdata](https://data.un.org/Data.aspx?d=POP&f=tableCode%3A1%3BcountryCode%3A744&q=Svalbard)) | Não marcar como inaplicável. Definir se a seleção representa um mercado separado ou parte da Noruega e evitar dupla contagem. |

Esta evidência permite propor a classificação metodológica de AQ, BV, GS, HM,
IO, TF e UM como territórios sem mercado residente independente; não transforma
essa proposta em decisão da pesquisa nem em zero músicas. SJ segue não resolvido.
As 72 células continuam explicitamente no relatório de cobertura e o gate G1
permanece bloqueado até que a regra de aplicabilidade seja formalmente registrada
e a matriz/quota versionada seja refeita. Nenhuma célula foi removida para
melhorar o percentual.

## Restrições antes do Vertex AI

- A [Política oficial de Desenvolvedores do Spotify](https://developer.spotify.com/policy)
  proíbe analisar Spotify Content/Service e usar ou ingerir Spotify Content em
  modelos de IA/ML; os [Termos de Desenvolvedor](https://developer.spotify.com/terms)
  incorporam essas condições. A aplicação a cada arquivo histórico de terceiro
  e a cada campo do payload exige revisão específica de direitos. Não enviar
  dados derivados de Spotify enquanto essa análise não estiver documentada.
- A documentação do [Google Cloud sobre retenção zero](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention)
  explica que prompt logging para monitoramento de abuso pode ocorrer e que ZDR
  depende de aprovação/configuração aplicável ao projeto e modelo. Não presumir
  retenção zero nem extrapolar configuração entre modelos/regiões.
- Antes de qualquer envio, registrar direitos de processamento para o texto e
  edição exatos, modelo, região, armazenamento temporário/saída, retenção,
  responsáveis e autorização financeira. As políticas do provedor não concedem
  direitos sobre letras de terceiros.

## Recuperação executável

1. Recuperar primeiro arquivos oficiais/autorizados com cobertura histórica por
   país e semana; guardar resposta original, URL/ID, data, hash, métrica e
   profundidade declarada.
2. Recalcular cada ano inteiro numa nova revisão de seleção. Não anexar linhas a
   uma seleção congelada nem misturar views, streams e plataformas.
3. Rejeitar períodos que não atinjam 100 posições YouTube ou 200 Spotify quando
   esse for o Top-K declarado; contar faixas únicas e manter duplicatas para
   adjudicação. Empates no limite da cota ficam pendentes.
4. Procurar fonte nacional primária/licenciada para os mercados restantes; não
   transferir cobertura entre países por idioma, popularidade ou plataforma.
5. Manter os oito territórios de cota indefinida no relatório até que a
   aplicabilidade seja documentada. Nenhuma célula pode sair do denominador para
   elevar o percentual.
6. Só calcular o gate G1 após reconstrução e adjudicação independente. Mesmo
   80% de G1 não comprova 80% acumulado das etapas seguintes.

## Evidências locais

- Seleção corrigida v4: `data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002/`.
- Profundidade, impacto por célula e hashes: `ranking_depth_audit.json`,
  `ranking_depth_impact_by_cell.csv`, `legacy_92k_depth_impact_by_cell.csv` e
  `ranking_depth_audit_manifest.json` nessa pasta.
- Avaliação e bloqueio atual de G1 pelo controlador v4:
  `data/runtime/research-flow-20261111/audit-v4-final-0003/` e
  `data/runtime/research-flow-20261111/progress-v4-final-0003/`.
- As evidências de letras permanecem no runtime privado; relatórios públicos
  devem conter hashes/contagens e filas sem os corpos das letras.
