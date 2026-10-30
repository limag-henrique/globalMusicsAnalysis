# Verificação de custos para classificação v2 — 25/10/2026

Fontes primárias consultadas: [preços Gemini](https://ai.google.dev/gemini-api/docs/pricing) e [contagem de tokens](https://ai.google.dev/gemini-api/docs/tokens).

Valores publicados por milhão de tokens de texto, entrada/saída:

| Modelo | Standard | Batch |
|---|---:|---:|
| `gemini-3.8-flash` | US$0,75 / US$3,75 | US$0,375 / US$1,875 |
| `gemini-3.5-flash-lite` | US$0,30 / US$2,50 | US$0,15 / US$1,25 |
| `gemini-3.1-flash-lite` | US$0,25 / US$1,50 | US$0,125 / US$0,75 |
| `gemini-2.5-flash-lite` | US$0,10 / US$0,40 | US$0,05 / US$0,20 |

Batch reduz estas tarifas em 50%. Saída inclui thinking faturável. As tarifas 3.8 consultadas vigoram até 31/12/2026; confirmar disponibilidade efetiva e preços no início da execução. `count_tokens` mede entrada antes do envio; registrar o uso efetivo da resposta, incluindo saída, thinking, cache e ferramentas. Não executar grounding ou buscas por música no classificador.

## Estimativa própria, sem garantia de viabilidade ou qualidade

Com 20.000 textos únicos, média hipotética de 3.000 tokens de entrada e 1.000 tokens de saída faturável por texto, o custo Batch 3.8 seria US$60; Batch 3.1 Flash-Lite seria US$22,50. Com 40.000 textos, seriam US$120 e US$45. Estas médias precisam ser medidas num piloto multilíngue e não autorizam usar o modelo barato sem validação.

Divisão proposta do teto TOTAL: piloto US$10; classificação principal US$120; revisão automática direcionada US$25; retentativas e contingência US$25. Deduzir qualquer gasto já imputável à campanha. Se revisão humana for remunerada, deduzir também sua remuneração e recalcular; voluntariado não deve ser confundido com custo de trabalho inexistente.

Reservar antes do envio o custo máximo configurado para entrada, saída e thinking, incluindo lotes em andamento. Não exceder US$180 nem consumir a reserva em processamento principal. Não garantir cobertura universal, 80 textos elegíveis em toda célula ou determinada acurácia antes de confirmar fontes, letras, contagem única, disponibilidade dos avaliadores e projeção real.

Nenhuma chamada paga foi realizada nesta checagem.
