# Chart Observatory — estado após remediação de 06/11/2026

O gate obrigatório de identidade, integridade e adjudicação está implementado e testado em online, batch, force e estimate, incluindo revalidação na importação de novas anotações batch. **O projeto está preparado para revisão técnica e triagem humana; não está liberado para nova campanha paga ou conclusões de validação científica.**

O [relatório histórico](docs/audit/2026-11-06/REPORT.md) permanece preservado. O [relatório de execução e pacote para revisão independente](docs/operations/readiness-remediation-20261106.md) descreve alterações, comandos, backups, rollback e limitações. A [matriz das 18 questões](docs/audit/2026-11-06-remediation/questions.json) registra evidências e estados sem declarar validação inexistente.

| Medida | Antes → depois nesta rodada |
|---|---|
| Seleção congelada | 86.090 vínculos; 28.373 candidatos; 67/68 mercados; 587/612 células — preservada |
| Candidatos com texto local/staging | 22.289 → **22.293** |
| Candidatos sem texto local | 6.084 → **6.080** |
| Recuperação offline | 8.613 processados; cinco propostas aplicadas: quatro preenchimentos e um reparo; zero erros/rede |
| Tarefas históricas SQLite | **33.247 preservadas**; integridade quick_check=ok; segunda aplicação fez zero alterações |
| Suspeitos anteriores | 2.529 conciliados; um passou dos sinais de fonte para acquired_unverified, sem comprovação de completude |
| Colisões textuais | 112 grupos antes e depois; precisam de adjudicação |
| Letras completas verificadas/liberadas | **Zero comprovadas nesta campanha**; nenhum documento canônico recebeu aprovação automática |
| Textos distintos no staging | 19.798 → 19.797 hashes; não é perda de candidatos: quatro preenchimentos reaproveitaram blobs existentes, e um reparo deixou de referenciar um hash distinto no snapshot atual; os blobs e snapshots anteriores continuam preservados |
| Testes offline finais | **767 passaram**, dois avisos Polars de depreciação |
| PostgreSQL real | **41 passaram** em clone isolado; mais três de adjudicação/concorrência/rollback na base de testes; teste de lock da fila também passou |
| Artigo | Freeze de outubro preservado; **50/50 hashes** de inputs/outputs conferidos; 154.995 linhas documentais selecionadas; PDF de 11 páginas renderizado e inspecionado em contact sheet |
| Custo de inferência nesta execução | **Zero chamadas pagas** |

Snapshot anterior: `dc8f9e5c257837abe48ba69dfdaa22070dd30809340f3c3bfb7de6e2ebcad039`. Novo snapshot imutável: `bc7afdd8e7b3382d607584449a14117abd8de80b5b0f58a5b734d458ad04cdff`. Seleção e cotas não mudaram. Aquisição, staging, gravações, versões textuais e classificação continuam com denominadores distintos.

Screening posterior: 19.765 acquired_unverified; 1.911 pending_adjudication; 588 identity_conflict; 29 suspected_partial; 6.080 unavailable no acervo local. Os estados são sinais conservadores, não taxas confirmadas de erro. As 22.293 cadeias com texto conferem por hash entre blob local, SQLite e staging. Nenhuma transcrição foi certificada por heurística.

Foram implementadas adjudicação transacional com histórico/locks e correções de extração que preservam textos curtos, repetições e versos com frases semelhantes a metadados. Perfis de execução da preparação agora contemplam modelo resolvido, prompt/schema/configuração/preprocessing/protocolo; língua contextual invalida a assinatura. **A integração completa dessa assinatura com caches legados ainda está pendente**. Não há aprovação geral do legado.

Os dez cenários de quotas reproduziram o baseline sem alterá-lo: raiz sem diversidade resultou em 430/130 para Índia/Países Baixos e Jaccard de repertório 0,97199; política atual, 440/130. Isso mede sensibilidade operacional, não validade populacional ou efeitos temáticos.

Pendências principais: referência humana multilíngue, adjudicação de identidade/completude, direitos/provider documentados para os usos pretendidos, integração de assinatura completa no legado e manifesto financeiro único conciliado. O teto informado US$150 não autoriza herdar configurações antigas US$180. O corpus histórico do artigo não foi substituído pela campanha atual.

Evidências privadas e checkpoints: `data/runtime/remediation-20261106/`. Índice versionável: [artefatos e hashes](docs/audit/2026-11-06-remediation/artifacts.json). Backups/dumps/letras não devem ser publicados. A leitura do PDF não comprova reexecução de todos os modelos estatísticos; não foram inventados rótulos humanos, acurácia, concordância ou melhora temática.
