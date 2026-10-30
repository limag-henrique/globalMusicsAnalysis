# Fontes e decisões metodológicas para seleção anual de músicas

Data: 2026-10-30. Pesquisa documental, sem alteração do importador. Os percentuais e procedimentos propostos abaixo são decisões analíticas a calibrar; não são um padrão universal publicado para estudos de letras.

## Conclusão

Importar todos os metadados de ranking disponíveis e separar essa operação da recuperação e classificação das letras. Para estudar exposição a conteúdo, definir por país, plataforma e ano uma cobertura comum da massa de reproduções observadas, deixando o número de músicas resultar da distribuição. Para estudar a diversidade do repertório, usar censo do quadro observado ou amostragem probabilística estratificada; o mesmo desenho não responde automaticamente às duas perguntas.

## Evidência primária verificada

- [Statistics Canada: Selection of a sample](https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/sample-echantillon/5214900-eng.htm): objetivos, população, unidades, precisão e desenho precedem o tamanho amostral. Variabilidade e desenho importam; populações grandes não exigem amostras proporcionais ao seu tamanho. Aplicação: população humana do país não justifica diretamente uma cota de músicas.
- [Statistics Canada: Non-probability sampling](https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/nonprob/5214898-eng.htm): seleção não aleatória limita inferência e mensuração de erro amostral. Aplicação: um top-N pode ser um recorte descritivo legítimo, mas não recebe automaticamente a margem de erro de uma amostra aleatória.
- [US Census Bureau: Statistical Quality Standard A3](https://www.census.gov/about/policies/quality/standards/standarda3.html): desenho e quadro devem atender ao objetivo; a norma inclui seleção para análise secundária e avaliações. Aplicação: documentar quadro, população observável, duplicações e regra de seleção antes da classificação.
- [Spotify: Understanding Spotify charts](https://support.spotify.com/us/artists/article/understanding-spotify-charts/): a plataforma filtra reproduções elegíveis para as paradas, usa períodos diários/semanais definidos e distingue pico de posição e sequência de presença. Aplicação: pico não é posição anual; somar registros de parada não equivale a obter todo o consumo nacional ou todos os streams da plataforma.
- [Pangakis, Wolken e Fasching: Automated Annotation with Generative AI Requires Validation](https://arxiv.org/abs/2306.00176): resultados de anotação dependem de tarefa e dados; os autores defendem validação contra rótulos humanos. Aplicação: validar Gemini na rubrica de letras, com diversidade linguística e classes relevantes; não transportar a acurácia de outra tarefa.
- [Angelopoulos et al.: Prediction-Powered Inference](https://arxiv.org/abs/2301.09633): inferência que combina previsões e dados de referência rotulados permite incorporar erros de previsão à estimação. Aplicação: uma auditoria humana probabilística pode sustentar correção e intervalos; despejar previsões de IA como se fossem verdade não faz isso. A aplicação concreta exige respeitar o desenho e suas hipóteses.

## Derivação própria: cobertura e limite da parte não classificada

Considere um quadro finito anual completo dos registros observados, com pesos não negativos w_i (reproduções observadas), W = soma(w_i), e classe binária verdadeira y_i em {0,1}. Para o conjunto K efetivamente classificado, sejam C = soma_K(w_i)/W e A = soma_K(w_i*y_i)/W. Então a prevalência ponderada do quadro inteiro está em [A, A + (1-C)]. A prova é apenas que a contribuição dos itens desconhecidos está entre zero e seu peso total.

O intervalo é um limite determinístico da informação faltante, não intervalo de confiança. Pressupõe rótulos conhecidos corretos; não inclui erro do Gemini, erro de identidade ou falhas no quadro. Se a prevalência conhecida normalizada é p_K, A=C*p_K. C=80% deixa largura de 20 pontos percentuais; C=95% deixa 5 pontos. O erro máximo de usar p_K como estimativa do quadro inteiro é no máximo 1-C. Para uma diferença entre dois países, as larguras de identificação se somam. Letras ausentes ou ambíguas contam como massa desconhecida, mesmo se a música já estiver selecionada.

Uma política inicial justificável é testar 90%, 95% e 97,5% e escolher a cobertura em função da diferença substantiva mínima que a pesquisa pretende distinguir e do custo de letras únicas. Não tratar 80% ou 95% como números cientificamente obrigatórios. Não impor teto escondido: se o orçamento impedir a cobertura, registrar cobertura menor e resultado inconclusivo quando necessário.

## Restrição central: quadro anual truncado

Se o quadro vem da união de top-200 diários, o total anual de uma música soma somente dias em que ela foi observada. Dias fora da parada não provam zero reproduções. A reconstrução é um ranking por reproduções registradas na parada, não necessariamente o ranking anual oficial. Falta de uma data inteira é um problema distinto de censura abaixo do corte. Um total conhecido somente das primeiras N músicas também não permite calcular a participação dessas N no consumo de todo o mercado.

Por isso os denominadores devem ser: mesma plataforma, mesmo país, mesmo período e unidade, sem mistura de fontes duplicadas ou frequências sobrepostas. Anos incompletos precisam ser sinalizados e não podem simular anos completos por normalização arbitrária. Rankings sem contagens de reprodução exigem análise própria por posições ou recorte fixo; pesos sintéticos de posição não devem ser chamados de streams.

## Desenho operacional proposto

1. Construir e validar o quadro anual inteiro antes de recuperar letras. Manter IDs nativos e linhagem de origem.
2. Ordenar por reproduções anuais comparáveis e calcular n(C) para vários C, sem quotas por população ou país nomeado. Consolidar versões apenas com evidência de identidade compatível.
3. Orçar a união global de edições textuais únicas selecionadas; uma letra validada pode ser reutilizada em vários países/anos, preservando os pesos de cada observação.
4. Selecionar por ranking, independentemente de disponibilidade de letra. Não substituir silenciosamente um sucesso sem letra pela próxima música disponível.
5. Validar anotação humana em dados diversos; separar auditoria representativa da revisão direcionada a erros. Duas pessoas e adjudicação são uma proposta de controle, não exigência das fontes.
6. Publicar prevalência ponderada por reproduções como exposição observada, prevalência por música como repertório, cobertura temporal, massa classificada, perdas de letras e limitações da plataforma.
7. Se o objetivo exige generalização ao repertório observado e o censo for inviável, manter sucessos como estrato de inclusão certa e sortear probabilisticamente a cauda; registrar probabilidades e usar estimadores/variâncias apropriados. Não anexar músicas de cauda sem ponderação e depois interpretar a média simples como a população.

## Validação desta nota

Foram abertas as seis fontes primárias listadas. As proposições algébricas foram explicitamente separadas das afirmações documentais. Não foram buscados preços ou capacidades atuais do Gemini; o orçamento deve vir do piloto real do projeto. Não houve mudança de código, branch ou commit.
