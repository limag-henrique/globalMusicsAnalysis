# Modelos candidatos para codificação de letras

Consulta às documentações oficiais em 10 de setembro de 2026. Esta é uma recomendação de candidatos para validação, não um ranking de precisão em letras: não foi identificado aqui um benchmark comparativo que demonstre qual desses modelos classifica melhor gírias, ironia e narrativas musicais brasileiras.

## Escolha proposta

| Provedor | Candidato ao piloto | Candidato econômico, condicionado à validação |
|---|---|---|
| OpenAI | GPT-6 Astra (`gpt-6-astra`), ou GPT-5.6 Sol se o orçamento limitar | GPT-5.6 Terra e GPT-5.6 Luna |
| Anthropic | Claude Opus 5 (`claude-opus-5`) | Claude Sonnet 5; Haiku 4.5 apenas se mantiver desempenho nas categorias difíceis |
| Google | Gemini 3.8 Flash (`gemini-3.8-flash`), estável no catálogo consultado | Gemini 3.5 Flash-Lite, após teste direto |

Os nomes acima foram verificados, e não inferidos de versões antigas. O [catálogo OpenAI](https://developers.openai.com/api/docs/models) apresenta Astra como modelo principal, Terra para equilíbrio entre custo e capacidade e Luna para volume. A [ficha Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) confirma saída estruturada e texto como entrada/saída; não aceita áudio diretamente. O [catálogo Anthropic](https://platform.claude.com/docs/en/models/overview) confirma Opus 5, Sonnet 5 e Haiku 4.5, todos com capacidades multilíngues. O [catálogo Gemini](https://ai.google.dev/gemini-api/docs/models) apresenta Gemini 3.8 Flash estável; sua [ficha técnica](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) confirma saída estruturada. Gemini 3.1 Pro aparece como preview: não o escolheria automaticamente apenas por ter “Pro” no nome.

A indicação é metodológica: três fornecedores diferentes ampliam a diversidade de sistemas, mas não tornam seus erros independentes. Rodar três modelos caros no piloto permite medir se modelos menores preservam a qualidade. Não é necessário escolher três modelos premium para todo o corpus.

## Saída e execução

Os três provedores documentam saída condicionada a JSON Schema: [OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs), [Anthropic](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) e [Google](https://ai.google.dev/gemini-api/docs/structured-output). Isso facilita validar tipos, campos obrigatórios e categorias; não garante correção semântica. Usar o mesmo esquema conceitual nos três provedores, adaptando apenas o subconjunto técnico aceito por cada API.

Registrar por dimensão: presença, intensidade, centralidade, postura narrativa, identificadores das linhas que sustentam a classificação, ambiguidade e necessidade de revisão. Não pedir reprodução integral da letra na resposta. Uma letra completa deve entrar em cada requisição: classificar linhas isoladas pode perder negação, mudança de narrador e ironia. A interpretação por trecho deve conservar o contexto integral da obra.

Há processamento assíncrono em lote nos três provedores: [OpenAI Batch](https://developers.openai.com/api/docs/guides/batch), [Anthropic Message Batches](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Gemini Batch](https://ai.google.dev/gemini-api/docs/batch-api). Confirmar suporte do modelo e da conta antes de congelar o protocolo. O guia Gemini informa janela alvo de 24 horas e suporte a saída estruturada; atualmente orienta usar generateContent. Não confundir batch com colocar centenas de letras numa única conversa.

## Reprodutibilidade e falhas

Fixar ID exato do modelo, versão do prompt e manual, esquema, parâmetros, data, SDK, hash da letra e resposta bruta. Usar snapshots quando oferecidos. A [documentação Anthropic de versões](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) esclarece que IDs sem data a partir da geração 4.6 são snapshots fixos; infraestrutura de atendimento ainda pode mudar. Não inventar um sufixo datado quando o fornecedor não o disponibiliza.

Recusas, bloqueios, truncamentos e erros técnicos devem gerar status próprios, nunca nota zero. O piloto deve conter conteúdo sexual explícito e violência, pois uma taxa desigual de recusas por país/gênero pode enviesar comparações. Realizar repetições em uma subamostra para medir estabilidade; temperatura baixa não prova determinismo. Desativar busca externa durante a classificação e retirar popularidade, ranking e país do cabeçalho entregue aos modelos, quando não necessários à interpretação. A língua ainda oferece pistas de origem: não alegar cegamento perfeito.

## Decisão com evidência

Criar conjunto humano de referência, estratificado por idioma, gênero e categorias raras, com revisão de falantes familiarizados com as variedades locais. Separar exemplos usados para ajustar o manual e o prompt do teste final. Comparar macro-F1 e precisão/recall por categoria, erro ordinal e concordância apropriada, além da taxa de recusas por estrato. Escolher o trio final pelo desempenho local e custo observado.

Não usar a média dos três modelos como verdade: para categorias nominais, registrar votos e divergência; para escores ordinais, conservar a distribuição e considerar mediana acompanhada de discordância. A agregação deve ser definida antes da análise e validada contra humanos. Unanimidade entre modelos pode continuar errada. Auditar também uma amostra de consensos.

## Orçamento de referência

Estimativa em 2026-09-10, em USD, para 126.213 letras únicas, uma chamada por modelo para cada letra, 4.000 tokens de entrada e 1.000 tokens de saída por chamada. São 504,852 milhões de tokens de entrada e 126,213 milhões de saída por provedor. O cálculo usa Batch, quando disponível, e não inclui retries, revisão humana, aquisição de letras, impostos ou variação cambial.

| Provedor/modelo | Tarifa Batch usada (entrada/saída por 1M) | Custo estimado |
|---|---:|---:|
| OpenAI GPT-6 Astra | US$ 5 / US$ 25 | US$ 5,68 |
| Anthropic Claude Opus 5 | US$ 2,50 / US$ 12,50 | US$ 5,68 |
| Google Gemini 3.8 Flash (introductório até 31/12/2026) | US$ 0,375 / US$ 1,875 | US$ 0,43 |
| **Trio** |  | **US$ 11,79** |

As tarifas Batch da Anthropic e do Google são 50% das tarifas padrão ([Anthropic](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Google](https://ai.google.dev/gemini-api/docs/batch-api)). Para a OpenAI, conferir na conta a tarifa Batch efetiva antes do envio; a página de modelos publica as tarifas por token e a disponibilidade de Batch ([catálogo OpenAI](https://developers.openai.com/api/docs/models)).

Uma reserva operacional de 30% coloca o trio em aproximadamente **US$ 15,33**. Para execução síncrona, sem desconto Batch, a mesma hipótese dá aproximadamente US$ 23,57 antes da reserva. Se apenas 50.000 letras tiverem texto elegível, multiplique esses valores por 50.000/126.213. Cada 10.000 letras no cenário Batch custa aproximadamente US$ 0,45 no Astra, US$ 0,45 no Opus e US$ 0,034 no Gemini 3.8 Flash.

Esses valores são uma ordem de grandeza, não um crédito recomendado sem piloto: modelos de raciocínio podem consumir tokens internos, prompts maiores elevam a entrada, respostas inválidas e adjudicações geram novas chamadas, e o catálogo de letras pode ser menor ou maior que o número de gravações canônicas. Fixar limites de gasto por provedor e carregar primeiro somente o piloto; depois aumentar o saldo conforme o consumo observado.

Para uma primeira carga integral com uma margem prática para retries e pequenas revisões, a sugestão é reservar **US$ 15 na OpenAI, US$ 15 na Anthropic e US$ 3 no Google**. Isso não é previsão de consumo: é um teto operacional arredondado para o cenário acima. Se a produção usar uma segunda passada completa, duplique aproximadamente essas reservas; se usar modelos econômicos depois do piloto, recalcule com os preços efetivos escolhidos.
