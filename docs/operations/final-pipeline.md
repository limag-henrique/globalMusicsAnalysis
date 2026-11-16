# Execução consolidada em três tarefas

Esta entrada preserva as versões anteriores e não modifica os workers do
AntiGravity. O catálogo único fica em `data/runtime/final-pipeline/catalog.sqlite`.
O PostgreSQL e as pastas de recuperação existentes não são copiados nem apagados.
As letras recuperadas são referenciadas pelo caminho e SHA-256 originais.
O arquivo de configuração já aponta para as seleções v4/v5 e para os stores
do Batch 2 e das recuperações anteriores. Stores ausentes aparecem no relatório.

Execute na raiz do projeto, usando o ambiente existente:

```powershell
.venv/Scripts/python.exe scripts/run_final_pipeline.py rankings
.venv/Scripts/python.exe scripts/run_final_pipeline.py lyrics
.venv/Scripts/python.exe scripts/run_final_pipeline.py vertex
```

Cada etapa retorna **0** quando seu universo está pronto e **2** quando existem
pendências. Um relatório produzido com sucesso não significa cobertura completa.
Os relatórios ficam em `rankings-report.json`, `lyrics-report.json` e
`vertex-report.json`, dentro da pasta do catálogo.

## 1. Rankings

O coletor descobre mercados nos índices públicos do Kworb, fonte já usada pelo
projeto para Spotify e YouTube. Captura posição original, artistas, título,
identificador quando disponível, streams, data da parada, URL e resposta bruta
comprimida e hashada. Kworb é um espelho, não a API oficial das plataformas.
O YouTube desse espelho não fornece ID nativo; a vinculação à gravação permanece
pendente. Nunca se deduplicam plataformas distintas apenas por título/artista.

Em `config/final_pipeline.json`, `top_n` define a profundidade padrão e
`country_top_n` permite cotas individuais, por exemplo `{"BR": 130, "US": 200}`.
O padrão de 200 é uma escolha operacional explícita, não uma cota científica
recalculada. A profundidade disponível pode ser menor; o relatório mostra o déficit.
`--countries BR,US` limita uma execução. Sem esse filtro, todos os códigos ISO
constam do diagnóstico, incluindo mercados sem fonte disponível.

Os limites de antiguidade são quatro dias para Spotify diário e dez dias para
YouTube semanal. Data ausente, futura, antiga, posições duplicadas ou com lacunas
reprovam o snapshot. Um ranking diário/semanal atual **não** substitui um anual.

`--selection PASTA` pode ser repetido para incorporar seleções históricas
imutáveis com o protocolo já existente. Os hashes são conferidos; cada versão
mantém suas posições, denominadores e lacunas. Metadados ficam no catálogo comum,
mas os rankings de versões diferentes não são somados como uma mesma amostra.

## 2. Letras completas

`--store PASTA` pode ser repetido para reutilizar stores `acquisition.sqlite`
do AntiGravity. A leitura usa uma transação SQLite somente leitura, inclusive
durante o Batch 2. A execução não escreve nos stores externos. Só incorpora
resultados com a mesma identidade de gravação e metadados compatíveis, verificando
o SHA-256 do texto. Não adota letras da versão 1 apenas por nomes semelhantes.
Os runs imutáveis de staging configurados são indexados por banco, run e candidato;
seus textos e resultados de fonte continuam no SQLite original. Quando um candidato
já preenchido recebe um resultado mais recente, o pipeline compara o score de
evidência e os hashes (`validate_text`), só substitui se houver ganho comprovado
de evidência e registra a versão anterior na tabela `replacement_ledger`. A cada
auditoria, o conteúdo referenciado é relido e seu hash é conferido, e a etapa
determinística de identificação de idioma (`language_identification`) registra
idioma, método e confiança antes dos gates científicos. A exclusão desse banco
ou de uma letra referenciada interrompe a validação, em vez de aprovar texto ausente.

Em seguida, a cadeia existente tenta LRCLIB e fontes HTML públicas, com cache,
controle de frequência e respeito aos bloqueios HTTP. Por padrão, percorre os
candidatos ainda não tentados, até 150.000 tentativas. `--limit 100` limita uma
execução menor; `--retry` retenta os casos anteriormente processados.
`--limit 0` apenas incorpora e audita o material existente, sem aquisição de rede.
Para uma conferência pequena, `--limit 0 --audit-limit 100` audita até cem textos;
os restantes aparecem explicitamente como não auditados, sem aprovação por amostra.

A auditoria reextrai o texto da resposta preservada e aplica os verificadores
existentes de identidade, créditos, integridade, indicação de trecho, início
ausente, conteúdo curto, resíduos e duplicação. Refrões repetidos não são removidos
para simular integridade. Uma tentativa malsucedida não substitui uma letra já
armazenada. A fila `lyric-review-queue.jsonl` identifica as pendências por música.

Passar na integridade do campo do provedor não comprova equivalência com o áudio
de uma edição específica. A etapa não fabrica aprovação científica nem promete
80% de aproveitamento onde as evidências ainda não sustentam esse percentual.

## 3. Preparação Vertex AI: máximo de 150.000 músicas

Sem evidência aprovada, a terceira tarefa produz o contrato de 26 tópicos e um
relatório bloqueado, sem gerar solicitações executáveis, uploads ou cobrança.
Para preparar JSONL real com o perfil e a rubrica aprovados do fluxo existente:

```powershell
.venv/Scripts/python.exe scripts/run_final_pipeline.py vertex --audit PASTA_AUDITORIA_G3 --prepared PASTA_PREPARACAO/requests.private.jsonl
```

O programa revalida G3, estado canônico, hash do texto, elegibilidade e escopo
Vertex; também exige que cada request conste da tabela aprovada. O ledger local
deduplica edições entre execuções e limita o total preparado a **150.000**.
Mudanças de perfil para a mesma edição não entram silenciosamente como novo lote.
Cada saída privada contém JSONL no envelope `request`, mapa de IDs e relatório.

Este comando prepara; não despacha inferência. O despachante existente ainda deve
revalidar os gates e o orçamento monetário antes de cobrar. O teto de 150 mil
músicas não altera automaticamente o antigo limite financeiro de US$150 nem
garante que esse valor pague 150 mil classificações. Comandos legados continuam
existindo; o ledger desta entrada controla seus próprios pacotes preparados.

## Armazenamento e concorrência

Um lock do sistema operacional impede duas operações desta entrada de escrever
no mesmo catálogo. Ele não interfere no lock dos workers do AntiGravity.
Os corpos de rankings são comprimidos e endereçados por conteúdo. As letras
existentes não são duplicadas; os caminhos originais precisam continuar disponíveis.
Nenhuma limpeza dos 167 GB ou do PostgreSQL externo é executada implicitamente.
Esta consolidação reduz novas cópias; ela não resolve por si só as lacunas de
fontes históricas nem converte os dados existentes em resultado científico final.
