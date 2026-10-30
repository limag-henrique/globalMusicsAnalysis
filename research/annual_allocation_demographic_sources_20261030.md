# Fontes demográficas para o cálculo de cotas

Pesquisa em 30/10/2026. Nenhum banco, ranking ou classificação foi modificado. A aplicação abaixo é uma preferência de alocação de esforço, não um desenho representativo de pessoas ou grupos internos dos países.

## Diversidade: dados efetivamente recuperados

Fonte primária: Alesina, Devleeschauwer, Easterly, Kurlat e Wacziarg (2003), *Fractionalization*, Journal of Economic Growth 8(2):155–194. O arquivo é disponibilizado pelo coautor Romain Wacziarg na UCLA:

- [Página de pesquisa do autor, seção Fractionalization](https://www.anderson.ucla.edu/faculty_pages/romain.wacziarg/papersum.html).
- [Planilha original dos autores](https://www.anderson.ucla.edu/faculty_pages/romain.wacziarg/downloads/2003_fractionalization.xls).
- [Artigo no repositório de Harvard](https://dash.harvard.edu/entities/publication/73120378-8680-6bd4-e053-0100007fdf3b).

Arquivo local: `research/annual_allocation_alesina_original_20261030.xls`.
SHA-256: `50f08c149be7d9c53d41bc02278ba88b0fb5a5aa25582bcc0982bb1a0f6905d0`.

A aba `Fractionalization Measures` contém medidas étnica, linguística e religiosa separadas. A tabela normalizada está em `research/annual_allocation_demographic_diversity_20261030.csv`, com 68 mercados do arquivo `research/article/analysis-final/country-metrics.csv`. Todos têm valor étnico numérico entre 0 e 1; não foi necessário imputar ausências. Foram conservados o nome original, o ano da medição étnica e o código da fonte subjacente. As correspondências especiais de nomes foram Coreia do Sul, Eslováquia, Taiwan, Turquia e Vietnã; os demais foram associados por identificadores ISO do pacote pycountry.

Índices de fracionalização expressam a probabilidade de duas pessoas sorteadas pertencerem a grupos diferentes. A medida étnica do estudo inclui características raciais e linguísticas; não deve ser confundida com apenas diversidade de idiomas. Não foi calculada média arbitrária de etnia, idioma e religião.

Para executar a fórmula já proposta na conversa, `allocation_diversity_value` reproduz a coluna étnica, sem reescalonamento relativo aos 68 países. O multiplicador `1 + 0,5D` fica entre 1 e 1,5. Isso dá uma bonificação moderada ao esforço de seleção, sem transformar o índice em medida de qualidade ou valor de um país.

**Limitação importante:** são medições históricas, publicadas em 2003, e não demografia observada de 2017–2026. O ano específico consta de cada linha. A página oficial do instituto curador QoG explica que a série repetida ao longo dos anos deve ser interpretada como variável histórica, não como atualização anual: [QoG: Fractionalization](https://datafinder.qog.gu.se/dataset/al). O uso como critério estático de prioridade precisa ser rotulado assim. Recomenda-se comparar as cotas com uma simulação que use só população; divergências não podem ser apresentadas como evidência de diversidade atual.

Também foi examinada a fonte primária [Historical Index of Ethnic Fractionalization, HIEF, de Lenka Dražanová](https://doi.org/10.7910/DVN/4JQRCL). A edição mais recente do arquivo é 2013 e não cobre Índia, França, Islândia e Luxemburgo. Para evitar mistura de conceitos e fontes com substituições não comparáveis, ela não foi usada na tabela principal.

## População e Taiwan

O projeto já conserva a resposta do Banco Mundial para 2024 em `data/derived/research_quality/country-all-history-20261011-022524/population-worldbank-2024.json`, indicador SP.POP.TOTL. Taiwan não está nessa resposta.

Complemento primário disponível: Ministério do Interior de Taiwan, *Demography Quarterly, Winter 2024*, publicado em fevereiro de 2025. A página 6 impressa (página 11 do PDF, índice 10) registra **23.400.220 pessoas ao final de dezembro de 2024**. [PDF oficial](https://www.ris.gov.tw/documents/data/5/2/DemographicQuarterly_Winter2024.pdf). Também consta da [divulgação oficial de 10/01/2025](https://www.ris.gov.tw/info-liferay/app/channel/newsDetail/25010858).

Trata-se de população do registro domiciliar ao final do ano. A nota explicativa do PDF restringe o universo aos nacionais com registro domiciliar interno; não é exatamente o conceito de população residente de meio de ano do Banco Mundial. O complemento é adequado como aproximação explícita para uma cota operacional, mas não para inferências demográficas comparativas sem harmonização. O cálculo deve registrar essa exceção em vez de chamá-la de dado do Banco Mundial.

## Validação

- Planilha recuperada diretamente do domínio do coautor, com conteúdo Excel válido e quatro abas.
- 68/68 códigos de mercado presentes, sem duplicações ou valores étnicos ausentes.
- Todos os índices étnicos usados estão em [0,1].
- Valores ilustrativos: Brasil 0,540836; República Dominicana 0,4294; Estados Unidos 0,490111; Índia 0,4182; Indonésia 0,735134.
- A extração foi feita com pandas e xlrd; o leitor xlrd foi carregado de wheel temporário, sem editar dependências do projeto.
- Não se verificou associação entre essas medidas e diversidade de letras; o índice apenas operacionaliza a prioridade demográfica solicitada.
