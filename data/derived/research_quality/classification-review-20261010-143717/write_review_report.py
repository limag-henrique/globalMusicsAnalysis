"""Record local diagnostic observations, never human gold labels or lyric bodies."""
import json
from pathlib import Path

OUT = Path(__file__).parent
samples = json.loads((OUT/'selected-for-initial-review.json').read_text(encoding='utf-8'))
observations = [
    'Sexualidade e ostentação plausíveis; transactional_sex=1 merece revisão por falta de troca explícita; crime/armas misturam metáfora e referência literal.',
    'Romance plausível; reciprocidade/consentimento mútuo podem ser inferidos do desejo unilateral. Texto curto; completude não verificada.',
    'Desilusão e referência a drogas plausíveis; misoginia versus insulto individual depende de definição operacional.',
    'Leitura metafórica plausível sem codificar violência literal; rodapé de interface confirmado.',
    'Romance plausível; reciprocidade=3 merece revisão; rodapé e entidades HTML confirmados.',
    'Romance plausível; reciprocidade=2 pode exceder evidência de mutualidade; rodapé e entidades HTML confirmados.',
    'Tema romântico aparente; requer anotador de indonésio para nuance e intensidade. Não é validação linguística independente.',
    'Romance/desilusão aparentes; requer anotador de árabe. Não é validação linguística independente.',
    'Sensualidade e álcool aparentes; romance/reciprocidade exigem contexto em chinês. Não é validação linguística independente.',
    'Conselho de buscar relação recíproca pode ser confundido com reciprocidade observada; texto não confirma versão com participações dos metadados.',
    'Referências de carreira/rap plausíveis; armas, violência e ato sexual podem ser metáforas supercodificadas. Revisão necessária, sem erro confirmado.',
    'Desejo e possibilidade de romance plausíveis; reciprocidade e consentimento mútuo podem exceder perspectiva unilateral.',
    'Transliteração punjabi/hindi: não emitir veredito sem competência linguística independente.',
    'Transliteração tâmil: possível intoxicação metafórica exige revisão linguística, sem erro confirmado.',
    'Transliteração telugu: referências locais/festa exigem revisão linguística, sem erro confirmado.',
    'Transliteração tâmil: romance/desilusão exigem revisão linguística, sem erro confirmado.',
    'Crítica a abuso e culpabilização da vítima; crime/violência condemned é plausível. Misoginia/objectificação indicam tema retratado, não endosso do narrador. Começa na segunda seção.',
    'Crítica à culpabilização/assédio plausível; pontuações de gênero não devem ser interpretadas como endosso. Texto armazenado contém refrão/ponte, completude não verificada.',
    'Shona e outras línguas: consentimento nonconsensual requer anotador competente; não certificar com base em confiança 0,85.',
    'Intensidades todas zero mas crime/violência condemned: coerência conceitual a revisar; referências abstratas não provam violência literal. Começa na segunda seção.',
    'Intensidade de violência zero com stance condemned: coerência conceitual a revisar; aventura infantil não implica automaticamente violência literal.',
    'Intensidades todas zero com violência condemned: mensagem inclusiva/metáforas; coerência conceitual a revisar. Começa na segunda seção.',
]
assert len(samples) == len(observations) == 22
notes = []
for index, (record, observation) in enumerate(zip(samples, observations)):
    notes.append({'index': index, 'document_id': record['document_id'],
        'snapshot_id': record['snapshot_id'], 'title': record['title'], 'artists': record['artists'],
        'source': record['source'], 'observation': observation,
        'review_method': 'AI-assisted local diagnostic inspection of supplied stored text',
        'human_gold_label': None, 'independent_identity_validation': False})
(OUT/'initial-semantic-observations.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding='utf-8')

report = '''# Qualidade das classificações e do corpus — 10/10/2026

O corpus apresenta boa integridade estrutural dos resultados classificados, mas ainda não tem qualidade científica demonstrada para sustentar o artigo. Os obstáculos principais são validade do conteúdo/identidade, possível incompletude das letras e ausência de validação humana das pontuações. Não há base para informar um percentual de acurácia sem um conjunto de referência independente.

## Método e corte temporal

Auditoria PostgreSQL 16 em `127.0.0.1:56433`, transações somente leitura e snapshot consistente de 10/10/2026 às **11:38:48 BRT** (`14:38:48 UTC`). Selecionado o último snapshot por documento/modelo/taxonomia/prompt, usando `append_order`. Existe uma combinação: `gemini-3.8-flash`, `lyrics-classification-v1`, `lyrics-classification-prompt-v2`. Histórico preservado: 209.793 snapshots; este número não é quantidade de músicas classificadas.

Validado o esquema de todos os resultados `classified`, vínculos de ID/hash ao documento, status, confiança e presença de telemetria/custo. A correspondência do hash no snapshot é diferente de recalcular todos os textos: recálculo SHA-256 foi feito apenas nos 22 documentos inspecionados, todos coincidentes. Agregações adicionais de higiene/duplicação estão em outro snapshot posterior, com timestamp próprio nos JSONs; a automação continuou ativa.

Preparados 52 candidatos por seleção determinística estratificada por fonte (12 por fonte quando disponíveis; manual=4), mais seis casos dirigidos, total de 58. **Inspecionados os textos de 22**: 16 dos candidatos estratificados (três por fonte não manual e quatro manuais) e seis dirigidos. Esta inspeção assistida por IA não é anotação humana, não é cega, não verifica identidades externamente e não estima acurácia populacional. Idiomas não dominados foram encaminhados para revisão linguística, sem veredito de correção.

Nenhuma geração, submissão, consulta paga ao modelo, reclassificação, alteração de letras ou checkpoint operacional. Custos adicionais de API: **R$ 0**. PID 3880 e comando do controlador confirmados via Windows; permaneceu ativo, com `quality_hold=false` e `controller_stop_requested=false`.

## Cobertura e integridade técnica

| Medida | Resultado no corte |
|---|---:|
| Faixas canônicas | 159.080 |
| Documentos de letras | 159.111 |
| Documentos com último resultado `classified` | 108.646 |
| Faixas distintas com `classified` | 108.615 (68,28%) |
| Últimos resultados `error` | 48.903 |
| `insufficient_text` | 1.068 |
| `instrumental` | 456 |
| `language_unsupported` / `ambiguous` / `blocked` | 29 / 6 / 3 |
| Esquema válido entre os classificados | 108.646/108.646 (100%) |
| Inconsistência de status/confiança ou vínculo ID/hash | 0 detectada |
| Classificados sem telemetria de uso/custo | 0 detectado |
| Elegíveis pelo seletor exploratório estrito atual | 92.212 |
| Elegíveis pelo seletor científico primário atual | 0 |

Os 48.903 erros são estados técnicos pendentes no corte, não 48.903 classificações semânticas erradas: 48.655 respostas malformadas, 212 incompletas, 20 saídas ausentes, 10 sem uso, quatro erros do provedor e dois de validação de esquema. Não autorizam retries adicionais além da política vigente. `instrumental` e `insufficient_text` também precisam de verificação de conteúdo; não devem ser somados automaticamente a músicas analisadas corretamente.

| Fonte | Documentos | Classificados |
|---|---:|---:|
| GENIUS | 124.591 | 87.014 |
| LETRAS | 26.540 | 16.429 |
| LRCLIB | 7.039 | 4.506 |
| LYRICS_OVH | 937 | 693 |
| GOOGLE_MANUAL | 4 | 4 |

Os 159.111 documentos têm `language_code` ausente. Existem zero ligações registradas em `platform_item_track_links`. O seletor primário retorna zero por identidade não verificada no manifesto atual; isso demonstra **falta de evidência registrada**, não que todas as identidades estejam erradas. LETRAS permanece excluído cientificamente, apesar da autorização posterior para classificação exploratória. Essa autorização não mudou nesta auditoria.

## Qualidade do texto e estabilidade

**Resíduo de interface confirmado:** 26.539/26.540 documentos LETRAS (99,996%) contêm simultaneamente as assinaturas de favoritos e rolagem automática; 14.724 têm entidades HTML. A inspeção dos três itens LETRAS confirmou rodapé e, em dois, entidades. O detector literal e sua consulta estão salvos em `additional_checks.py`. O relatório histórico de 27/09 usava outros detectores e não havia reconciliado uma contagem ampla anterior; esta contagem nova é reproduzível com uma assinatura explícita, não substituição retroativa daquele método. Resíduo não prova que o modelo classificou errado, mas indica que a entrada não é letra limpa.

**Possível incompletude:** 9.195/124.591 GENIUS (7,38%) começam em marcadores específicos de segunda seção (`Verse 2`, `Куплет 2`, `Vers 2`, `Ritornello 2`). É triagem conservadora, não diagnóstico definitivo: uma letra pode começar assim legitimamente. Há ainda 13.899 GENIUS com menos de 300 caracteres. Os conjuntos se sobrepõem e não devem ser somados. A revisão encontrou textos apenas com seções finais/refrão/ponte. Sem cópia autorizada integral ou página bruta preservada, não se identifica o trecho faltante nem a causa. O scraper usa regex sobre contêineres HTML, que merece diagnóstico específico, mas não foi reproduzida aqui a causa upstream.

**Reprodutibilidade das pontuações:** entre 1.846 grupos de texto exatamente igual e versões iguais, presentes em faixas distintas classificadas (4.689 documentos), 887 grupos (48,05%) têm alguma diferença nas 26 intensidades. Em 886 desses grupos o máximo é um ponto; em um, dois pontos. A análise não compara categorias de consentimento, gênero ou stance; portanto não mede toda divergência possível. A igualdade é de texto/hash/configuração de versões, não um experimento controlado de repetição no mesmo job. Como o prompt recebe letra e idioma e todos os idiomas registrados são nulos, os títulos distintos não são contexto fornecido ao modelo.

O caso de diferença de dois pontos usa o mesmo texto LETRAS ligado a “Neginha”, “Batida Do Pai”, “Rosinha” e “Balança”, de MC LEO, com algumas participações de DJ FIRE: `territorial_identity` varia de 0 a 2. IDs, hashes e pontuações estão em `duplicate-disagreements.json`. Há simultaneamente risco de identidade e instabilidade do rótulo; não se conclui qual identidade ou nota é correta apenas pelo hash. A taxa 48,05% descreve grupos duplicados selecionados, **não a taxa de erro do corpus**.

## Inspeção semântica inicial

Os temas amplos de romance, desilusão, sexualidade e ostentação frequentemente são plausíveis nos textos examinados. A amostra não permite medir a precisão por dimensão. Os principais pontos para revisão são:

- **Reciprocidade e consentimento:** “I Believe”, “Eu, Você, O Mar e Ela” e “Know Your Worth” levantam a distinção entre desejo/conselho de reciprocidade e reciprocidade efetivamente narrada. O desejo unilateral não basta para comprovar consentimento mútuo.
- **Troca sexual versus atração por status:** `transactional_sex=1` em “Tá com o Papato” requer evidência de troca, sem assumir equivalência automática com riqueza e desejo.
- **Metáfora versus ato literal:** rap e linguagem figurada podem produzir sobrecodificação de crime, arma, violência ou ato sexual. Os casos não foram declarados erros confirmados.
- **Tema retratado versus endosso:** “Strawberry Shortcake” e “Подруга” criticam culpabilização/abuso. `misogyny`/`objectification` podem registrar o conteúdo retratado, mas não autorizam chamar o narrador ou artista de misógino. A taxonomia não registra stance específico dessas dimensões de gênero, exigindo definição analítica explícita.
- **Intensidade zero com stance não neutro:** 15 classificados têm esse sinal; três foram inspecionados (“Giocattoli”, “Här kommer Bumbibjörnarna”, “BlimE”). É ambiguidade de coerência conceitual que requer manual de anotação; o esquema permite a combinação. Não é falha de JSON.
- **Competência linguística:** casos em árabe, indonésio, chinês, shona e transliterações sul-asiáticas não receberam selo de correção. Requerem revisores competentes no idioma e referências culturais.

As observações item a item estão em `initial-semantic-observations.json`, sem corpos das letras. Há 9.491 classificados com todas as intensidades zero; isso é válido para textos fora dos temas e não constitui erro por si só. Foram encontrados 192 com consentimento coercivo/não consensual; são candidatos importantes para revisão devido à sensibilidade da inferência.

**Confiança não calibrada:** 41.934 classificados (38,60%) declaram confiança ≥0,95; 66.040 estão em 0,80–0,94 e 672 em 0,51–0,79. Não há conjunto humano para demonstrar que 0,95 corresponde a 95% de acerto. O resultado fornece escores estruturados, mas não evidências textuais por dimensão que permitam auditar automaticamente cada nota.

## Evidência anterior de identidade

O relatório local `docs/operations/lyrics-identity-audit-2026-09-27.md`, na seção final de validação independente, registrou 179 itens, com 131 comparações verificáveis. Em LETRAS, 16/65 comparações verificáveis foram classificadas como identidade incorreta (24,6%; intervalo Wilson registrado 15,8–36,3%). É evidência anterior de correspondência letra–faixa, não medição nova e nem teste das intensidades temáticas. A amostra era desproporcional por fonte; o número não pode ser aplicado aos 26.540 documentos ou a todo o corpus. Não confundir esse resultado final com a primeira passagem histórica sem comparações, também preservada no documento.

## Prioridades para uso no artigo

1. Separar conclusão operacional de validade científica: terminar jobs não demonstra análise correta de todas as músicas. Preservar corpus exploratório, quarentena e ineligibilidade sem evidência de identidade/ranking.
2. Validar completude e identidade das entradas, começando por resíduos LETRAS, segunda seção GENIUS, versões e hashes compartilhados. Correções devem criar derivados versionados e manter original/proveniência; nada foi corrigido ou reenviado nesta auditoria.
3. Definir manual de anotação por dimensão: presença versus endosso, metáfora, escala 0–3, reciprocidade, consentimento e regras para stance com intensidade zero. Os exemplos acima são candidatos, não rótulos humanos.
4. Concluir avaliação cega por dois revisores independentes, com competência linguística, estratificada por fonte/idioma e níveis 0–3, incluindo casos negativos e difíceis. Separar amostra aleatória para estimativa de desempenho dos casos dirigidos para diagnóstico. As 58 linhas preparadas servem a triagem inicial, não bastam para concluir acurácia por idioma/dimensão.
5. Reportar concordância, confusões por dimensão, sensibilidade a identidade/completude e calibração da confiança contra consenso humano. Ajustes futuros de corpus/prompt exigem nova versão e comparação controlada; não reanalisar indiscriminadamente dentro do orçamento atual.

**Parecer:** integridade estrutural dos classificados está demonstrada no corte; cobertura ainda parcial; qualidade semântica e validade científica permanecem não demonstradas. O uso atual é exploratório e condicionado à seleção estrita. Não foi imposto hold ao controlador por flags semânticos que ainda exigem revisão, nem houve despesa adicional.
'''
(OUT/'report.md').write_text(report,encoding='utf-8')
print(str(OUT/'report.md'))
