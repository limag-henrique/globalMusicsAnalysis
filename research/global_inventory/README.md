# Inventário mundial de mercados musicais — 08/11/2026

O universo geográfico agora contém **249 países/territórios ISO 3166-1**, mais
**Kosovo (XK) como exceção explícita não ISO**: 250 entradas e 2.250 células para
2018–2026. Isso amplia o inventário de pesquisa, não a seleção operacional ou
a cobertura comprovada de rankings. As cotas e as 86.090 participações da seleção
congelada foram preservadas; nenhum novo ranking foi importado ou enviado à IA.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| [countries_20261108.tsv](countries_20261108.tsv) | Tabela pesquisável dos 250 países/territórios, situação local, fontes/pistas e ação seguinte |
| [countries_20261108.json](countries_20261108.json) | Mesmo inventário com listas estruturadas |
| [country_years_20261108.tsv](country_years_20261108.tsv) | 2.250 células país/ano, presença na seleção local e estado não verificado da expansão |
| [source_registry_20261108.json](source_registry_20261108.json) | 27 registros com links de evidência, métrica, abrangência, restrições e status documental |
| [apple_country_chart_directory_20261108.json](apple_country_chart_directory_20261108.json) | 52 rótulos territoriais de playlists oficiais Apple, incluindo links individuais; diretório parcialmente visível, não catálogo mundial completo |
| [manifest_20261108.json](manifest_20261108.json) | Hashes de inputs, resumo por região e contagens de preservação |
| [EXPANSION_PLAN_20261108.md](EXPANSION_PLAN_20261108.md) | Resultados da investigação, comparação entre fontes e plano de incorporação |
| [../geography/un_m49_20261108.json](../geography/un_m49_20261108.json) | 248 linhas da tabela oficial M49 da ONU, data e hash da captura |
| [../geography/iso_3166_20261108.json](../geography/iso_3166_20261108.json) | Snapshot ISO do pycountry, com versão do pacote |

## Leitura correta

`national_documented_source_ids` significa que há documentação de um chart
nacional ou rotulado por país em uma plataforma. Não significa representatividade
da população, aprovação de acesso, coleta completa ou disponibilidade 2018–2026.
Mdundo, por exemplo, ainda requer confirmação da base geográfica da audiência.

`regional_context_source_ids` não pode virar ranking nacional. As playlists Apple
são identificadas pelo país no nome, não pelo storefront no URL: uma URL `/ba/`
pode exibir o chart do Nepal. `unverified_discovery_routes` são tarefas de pesquisa,
não fontes já disponíveis para o país. Ausência de evidência nesta investigação
não prova inexistência de rankings. Nenhuma linha nova tem `ingestion_ready=true`.

O inventário conserva Taiwan como entrada ISO, mas sua classificação regional é
política explícita do projeto, pois não consta como linha própria na tabela M49
capturada. XK não recebe códigos ISO3/M49 inventados. A Antártida permanece como
referência, fora do alvo de mercado musical. Territórios não são fundidos com a
metrópole. As classificações não expressam posição sobre soberania.

## Reprodução offline

```powershell
.\.venv\Scripts\python.exe scripts/build_global_music_inventory.py
.\.venv\Scripts\python.exe -m pytest tests/unit/sources/test_global_inventory.py -q
```

O gerador só lê snapshots e a seleção congelada local; escreve nesta pasta. Não
consulta APIs, não altera o PostgreSQL, não modifica cotas e não inicia aquisição
ou classificação. As páginas de evidência foram pesquisadas em 08/11/2026; seus
dados de método não substituem uma auditoria completa de calendário e profundidade.

Validação desta entrega: **64 testes passaram**, incluindo oito novos casos do
inventário, mais os testes existentes de fontes/corpus selecionados. Ruff passou;
Mypy do novo módulo passou com `--follow-imports=silent --no-incremental`. Foram
conferidos 250 códigos e 2.250 células únicas, hashes de todos os inputs e a
preservação dos 86.090 vínculos. Dois avisos de depreciação Polars são preexistentes
nos leitores MGD/Kaggle. Não houve teste de APIs autenticadas ou coleta histórica.
