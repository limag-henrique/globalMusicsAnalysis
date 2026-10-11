# Comparação exploratória de todo o histórico disponível

Retrato do banco em 10/10/2026 às 23:25 BRT. Havia 127.789 músicas classificadas; 127.776 permaneceram no resumo global após os filtros de integridade, autorização e quarentena. Não houve filtro por confiança. A confiança declarada pelo modelo não foi calibrada contra uma avaliação independente.

A comparação geográfica usa 126.536 IDs de gravações classificados em 68 mercados, considerando Spotify Top 200 e Viral 50, de 2017 a 2021 e parte de 2022 (até 13 de março). Os provedores MGD e Kaggle foram unidos por ID original normalizado. Cada ID recebe peso igual e conta uma única vez em cada mercado, mesmo quando reaparece em anos, fontes ou rankings distintos. Uma gravação pode aparecer em vários mercados. A unidade é o mercado de circulação, não a nacionalidade do artista.

Presença temática significa intensidade pelo menos 2 na escala 0–3. As porcentagens têm como denominador as músicas classificadas naquele mercado. Não classificados não recebem nota zero. A cobertura é o número classificado dividido pelo total de IDs distintos observados no mercado. Os rankings exigem pelo menos 300 músicas classificadas; GLOBAL, Hong Kong e Porto Rico não integram os 68 mercados apresentados. Taiwan permanece identificado como mercado.

Todas as fontes disponíveis foram inventariadas. Os dados de YouTube de 2026 não tinham ligação exata com as classificações, e os registros Pro-Música de 2026 não tinham ID de gravação que permitisse essa ligação. Esses registros não foram associados por aproximação. A união exata não constitui validação independente da identidade das letras.

O relatório usa as classificações já importadas, inclusive as produzidas com textos anteriores às correções locais. Não reanalisa semanticamente textos corrigidos. O resultado é informal e provisório: não estima características das populações, consumo de pornografia, exposição por streams ou elegibilidade científica estrita.

Arquivos: report.json contém totais, critérios, rankings e Brasil; all-history-country-metrics.csv contém numeradores, denominadores e cobertura de todos os mercados; annual-country-metrics.csv separa anos; source-specific-country-metrics.csv separa as fontes. Os arquivos de proveniência preservam os IDs e hashes utilizados, sem publicar os textos das letras. Foram feitas zero chamadas ao modelo e nenhuma alteração no banco.
