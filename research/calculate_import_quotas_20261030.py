"""Read-only source analysis: annual ranks and budgeted country import manifests.

No production database writes, network calls, lyrics acquisition or model calls.
Native IDs and metadata candidates are counted conservatively across platforms.
"""

import calendar
import csv
import gettext
import hashlib
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")
import polars as pl
import pycountry

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from import_web_chart_titles import validate_snapshot
from chart_observatory.ingestion.annual_selection import observation_key, song_key
from chart_observatory.sources.catalog import _country_aliases

OUT = ROOT / "data/derived/research_quality/import-quotas-20261030"
RAW = ROOT / "data/raw/annual_top80/20261021"
CUTOFF = date(2026, 10, 15)
MAX_RANK = 500
MARKETS = sorted(pl.read_parquet(ROOT / "research/article/analysis-final/country-metrics.parquet")["market_code"].to_list())
COUNTRY_TRANSLATION = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["pt_BR"], fallback=True)


def dump_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def historical():
    rows, coverage = [], []
    source = pl.concat([pl.scan_parquet(ROOT / f"data/normalized/{n}_observations.parquet")
                        for n in ("mgd", "kaggle_spotify")]).filter(
        (pl.col("origin_platform") == "SPOTIFY") & (pl.col("metric_type") == "STREAMS")
        & (pl.col("period_start") == pl.col("period_end"))
        & pl.col("chart_name").str.to_lowercase().str.contains("top")
    ).with_columns(
        pl.col("country_code").replace(_country_aliases()).alias("country"),
        pl.col("period_start").dt.year().alias("year"),
        pl.col("native_id").str.extract(r"(?:/track/)?([A-Za-z0-9]{22})(?:\?.*)?$", 1).alias("item_id"),
    ).filter(pl.col("country").is_in(MARKETS))
    for year in range(2017, 2027):
        daily = source.filter(pl.col("year") == year).group_by(
            "provider", "country", "period_start", "item_id"
        ).agg(
            pl.col("metric_value").n_unique().alias("variants"),
            pl.col("metric_value").max().alias("streams"),
            pl.col("track_title").sort().first().alias("title"),
            pl.col("artist").sort().first(),
        ).collect(engine="streaming")
        if not daily.height:
            continue
        for market in MARKETS:
            market_rows = daily.filter(pl.col("country") == market)
            if not market_rows.height:
                continue
            providers = []
            for (provider,), records in market_rows.partition_by("provider", as_dict=True).items():
                providers.append((records["period_start"].n_unique(), records.height, provider, records))
            days, _, provider, records = max(providers, key=lambda x: (x[0], x[1], x[2]))
            invalid = records.filter((pl.col("variants") != 1) | pl.col("streams").is_null()
                | (pl.col("streams") < 0) | pl.col("item_id").is_null()).height
            stop = min(date(year, 12, 31), CUTOFF) if year == 2026 else date(year, 12, 31)
            expected = (stop - date(year, 1, 1)).days + 1
            depths = records.group_by("period_start").agg(pl.len().alias("depth"))
            status = "COMPLETE" if days == expected and not invalid else "INCOMPLETE"
            if invalid:
                status = "CONFLICT_OR_INVALID"
            cov = dict(country_code=market, year=year, platform="SPOTIFY", provider=provider,
                       expected_periods=expected, collected_periods=days, coverage_status=status,
                       minimum_depth=int(depths["depth"].min()), invalid_items=invalid,
                       observed_start=str(records["period_start"].min()),
                       observed_end=str(records["period_start"].max()),
                       ranking_period_end=stop.isoformat(), metric_type="STREAMS",
                       identity_status="native_id_pending_recording_review")
            coverage.append(cov)
            if invalid:
                continue
            annual = records.group_by("item_id").agg(pl.col("streams").sum().alias("metric_value"),
                pl.col("title").sort().first(), pl.col("artist").sort().first()).sort(
                ["metric_value", "item_id"], descending=[True, False])
            total = annual["metric_value"].sum()
            cumulative = 0
            for rank, r in enumerate(annual.head(MAX_RANK).to_dicts(), 1):
                cumulative += r["metric_value"]
                rows.append(dict(country_code=market, year=year, platform="SPOTIFY",
                    provider=provider, position=rank, candidate_id=f'SPOTIFY:{r["item_id"]}',
                    title=r["title"], artist=r["artist"], metric_value=r["metric_value"],
                    cumulative_observed_share=cumulative / total if total else 0.0,
                    identity_status=cov["identity_status"]))
        print(json.dumps({"stage": "spotify", "year": year, "rank_rows": len(rows)}), flush=True)
    return rows, coverage


def youtube():
    periods, conflicts, errors = {}, set(), []
    for path in sorted(RAW.glob("YOUTUBE_CHARTS_WEB_*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            doc = validate_snapshot(raw)
            if doc.get("observed_country_code") != doc["country_code"]:
                raise ValueError("missing or conflicting observed country")
            end = date.fromisoformat(doc["period_end"])
            if end > CUTOFF or doc["country_code"] not in MARKETS:
                continue
            if any(type(r.get("metric_value")) is not int or r["metric_value"] < 0 for r in doc["rows"]):
                raise ValueError("missing metric")
            key = doc["country_code"], end.year, end.isoformat()
            signature = json.dumps(sorted((observation_key(r), song_key(r["title"], r["artist"]),
                                             r["metric_value"]) for r in doc["rows"]), ensure_ascii=False)
            if key in periods and periods[key][0] != signature:
                conflicts.add(key)
            else:
                periods[key] = signature, doc
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(dict(file=path.name, error=str(exc)))
    rows, coverage = [], []
    for market in MARKETS:
        for year in (2025, 2026):
            stop = CUTOFF if year == 2026 else date(year, 12, 31)
            start = date(year, 1, 1)
            required = set()
            day = start
            while day <= stop:
                if day.weekday() == 3:
                    required.add(day.isoformat())
                day += timedelta(days=1)
            docs = [doc for (m, y, end), (_, doc) in periods.items()
                    if m == market and y == year and end in required and (m, y, end) not in conflicts]
            if not docs:
                continue
            valid_ends = {doc["period_end"] for doc in docs}
            status = "COMPLETE" if valid_ends == required else "INCOMPLETE"
            has_conflict = any(m == market and y == year for m, y, _ in conflicts)
            if has_conflict:
                status = "CONFLICT_OR_INVALID"
            coverage.append(dict(country_code=market, year=year, platform="YOUTUBE", provider="YOUTUBE_CHARTS_WEB",
                expected_periods=len(required), collected_periods=len(docs), coverage_status=status,
                minimum_depth=min(len(d["rows"]) for d in docs), invalid_items=int(has_conflict),
                observed_start=min(d["period_start"] for d in docs), observed_end=max(valid_ends),
                ranking_period_end=stop.isoformat(), metric_type="VIEWS",
                identity_status="metadata_pending_canonical_reconciliation"))
            totals = {}
            for doc in docs:
                for r in doc["rows"]:
                    key = observation_key(r)
                    item = totals.setdefault(key, dict(title=r["title"], artist=r["artist"], metric_value=0))
                    item["metric_value"] += r["metric_value"]
            annual = sorted(totals.items(), key=lambda pair: (-pair[1]["metric_value"], pair[0]))
            total, cumulative = sum(r["metric_value"] for _, r in annual), 0
            for rank, (key, r) in enumerate(annual[:MAX_RANK], 1):
                cumulative += r["metric_value"]
                candidate = ("YOUTUBE:" + key[1]) if key[0] == "native" else "YOUTUBE_METADATA:" + hashlib.sha256(
                    json.dumps(key[1:], ensure_ascii=False).encode()).hexdigest()
                rows.append(dict(country_code=market, year=year, platform="YOUTUBE", provider="YOUTUBE_CHARTS_WEB",
                    position=rank, candidate_id=candidate, title=r["title"], artist=r["artist"],
                    metric_value=r["metric_value"], cumulative_observed_share=cumulative / total if total else 0.0,
                    identity_status="metadata_pending_canonical_reconciliation"))
    dump_csv(OUT / "snapshot_errors.csv", errors)
    return rows, coverage


def prepare_ranks():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "rankings.parquet").exists():
        return
    a, ac = historical()
    b, bc = youtube()
    pl.DataFrame(a + b).write_parquet(OUT / "rankings.parquet")
    dump_csv(OUT / "source_coverage.csv", ac + bc)
    print(json.dumps({"stage": "ranking_complete", "rows": len(a+b), "cells": len(ac+bc)}), flush=True)


def allocate():
    with (ROOT / "data/derived/research_quality/country-all-history-20261011-022524/population-worldbank-2024.json").open(encoding="utf-8") as handle:
        population_doc = json.load(handle)
    populations = {r["country"]["id"]: r["value"] for r in population_doc["response"][1]
                   if r["value"] is not None}
    populations["TW"] = 23_400_220
    with (ROOT / "research/annual_allocation_demographic_diversity_20261030.csv").open(encoding="utf-8-sig") as handle:
        diversity = {r["country_code"]: r for r in csv.DictReader(handle)}
    assert all(m in populations and m in diversity for m in MARKETS)
    ranked = pl.read_parquet(OUT / "rankings.parquet").to_dicts()
    with (OUT / "source_coverage.csv").open(encoding="utf-8-sig") as handle:
        source_coverage = list(csv.DictReader(handle))
    cov_by_cell, ranks_by_source = defaultdict(list), defaultdict(list)
    for r in source_coverage:
        r["year"] = int(r["year"])
        for k in ("expected_periods", "collected_periods", "minimum_depth", "invalid_items"):
            r[k] = int(r[k])
        cov_by_cell[r["country_code"], r["year"]].append(r)
    for r in ranked:
        ranks_by_source[r["country_code"], r["year"], r["platform"]].append(r)
    selected_sources, selected_rows = {}, {}
    for cell, options in cov_by_cell.items():
        # One platform per annual cell; complete calendars first, Spotify tie-break.
        valid = [r for r in options if r["coverage_status"] != "CONFLICT_OR_INVALID"]
        if not valid:
            continue
        chosen = max(valid, key=lambda r: (r["coverage_status"] == "COMPLETE", r["platform"] == "SPOTIFY"))
        selected_sources[cell] = chosen
        selected_rows[cell] = sorted(ranks_by_source[*cell, chosen["platform"]], key=lambda r: r["position"])
    def weights(use_diversity=True):
        return {m: math.sqrt(populations[m]/1_000_000) *
                (1 + .5*float(diversity[m]["allocation_diversity_value"]) if use_diversity else 1)
                for m in MARKETS}
    def quotas(coefficient, weight):
        return {m: min(500, 100 + 10*math.floor(coefficient*weight[m]/10 + 1e-12)) for m in MARKETS}
    def union_for(q, complete_only=False):
        return {r["candidate_id"] for cell, records in selected_rows.items()
                if not complete_only or selected_sources[cell]["coverage_status"] == "COMPLETE"
                for r in records[:q[cell[0]] ]}
    def fit(target, weight, membership_cap):
        low, high = 0., 10000.
        assert len(union_for(quotas(low, weight))) <= target, "base alone exceeds target"
        for _ in range(40):
            mid = (low+high)/2
            proposed = quotas(mid, weight)
            if len(union_for(proposed)) <= target and sum(proposed.values())*10 <= membership_cap:
                low = mid
            else:
                high = mid
        q = quotas(low, weight)
        return q, low, len(union_for(q))
    weight = weights()
    main, coefficient, main_count = fit(24_000, weight, 100_000)
    expansion, expansion_coefficient, expansion_count = fit(36_000, weight, 125_000)
    population_only, pop_coefficient, _ = fit(24_000, weights(False), 100_000)
    source_url = population_doc["url"]
    country_rows, cell_rows, import_rows, planning_rows = [], [], [], []
    for market in MARKETS:
        name = COUNTRY_TRANSLATION.gettext(pycountry.countries.get(alpha_2=market).name)
        name = {"TW": "Taiwan", "KR": "Coreia do Sul", "RU": "Rússia", "BO": "Bolívia"}.get(market, name)
        country_cells = []
        for year in range(2017, 2027):
            cell = market, year
            cov = selected_sources.get(cell)
            records = selected_rows.get(cell, [])
            ready = cov is not None and cov["coverage_status"] == "COMPLETE"
            chosen = records[:main[market]]
            deficit = max(0, main[market]-len(chosen)) if records else main[market]
            status = ("SEM_DADOS_LOCAIS" if not cov else "CALENDARIO_INCOMPLETO" if not ready
                      else "JANELA_PARCIAL_2026" if year == 2026 else "CALENDARIO_ANUAL_COMPLETO")
            if ready and deficit:
                status += "_COTA_MAIOR_QUE_QUADRO"
            row = dict(country_code=market, country_name=name, year=year, quota_main=main[market],
                quota_expansion=expansion[market], available_rank_items=len(records),
                selected_observed_items=len(chosen), import_calendar_eligible_items=len(chosen) if ready else 0,
                quota_shortfall=deficit, platform=cov["platform"] if cov else "",
                provider=cov["provider"] if cov else "", status=status,
                expected_periods=cov["expected_periods"] if cov else 0,
                collected_periods=cov["collected_periods"] if cov else 0,
                minimum_depth=cov["minimum_depth"] if cov else 0,
                period_end=cov["ranking_period_end"] if cov else (CUTOFF.isoformat() if year == 2026 else f"{year}-12-31"),
                selected_observed_share=chosen[-1]["cumulative_observed_share"] if chosen else None,
                identity_status=cov["identity_status"] if cov else "unavailable")
            cell_rows.append(row)
            country_cells.append(row)
            for r in chosen:
                output = dict(**r, calendar_status=status, period_end=row["period_end"],
                              quota_main=main[market], not_for_paid_submission=True)
                planning_rows.append(output)
                if ready:
                    import_rows.append(output)
        country_rows.append(dict(country_code=market, country_name=name, population_2024=populations[market],
            historical_ethnic_diversity=float(diversity[market]["allocation_diversity_value"]),
            diversity_reference_year=int(diversity[market]["ethnic_reference_year"]),
            allocation_weight=weight[market], quota_per_year_main=main[market],
            quota_per_year_expansion=expansion[market], quota_population_only=population_only[market],
            diversity_quota_difference=main[market]-population_only[market],
            calendar_eligible_years=";".join(str(r["year"]) for r in country_cells if r["import_calendar_eligible_items"]),
            calendar_eligible_memberships=sum(r["import_calendar_eligible_items"] for r in country_cells),
            observed_planned_memberships=sum(r["selected_observed_items"] for r in country_cells),
            years_without_local_data=";".join(str(r["year"]) for r in country_cells if not r["available_rank_items"]),
            population_source=("https://www.ris.gov.tw/documents/data/5/2/DemographicQuarterly_Winter2024.pdf" if market == "TW" else source_url),
            diversity_source=diversity[market]["source_url"]))
    country_rows.sort(key=lambda r: (-r["quota_per_year_main"], -r["population_2024"], r["country_code"]))
    dump_csv(OUT / "country_quotas.csv", country_rows)
    dump_csv(OUT / "country_year_import_plan.csv", cell_rows)
    dump_csv(OUT / "import_calendar_eligible.csv", import_rows)
    dump_csv(OUT / "selected_observed_planning.csv", planning_rows)
    for name, data in (("countries", country_rows), ("cells", cell_rows)):
        (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = dict(protocol="population-diversity-budgeted-annual-v1-draft", created_date="2026-10-30",
        candidate_years=[2017,2026], local_capture_cutoff=str(CUTOFF), markets=len(MARKETS),
        baseline_per_country_year=100, cap_per_country_year=500, rounding_step=10,
        formula="min(500,100+10*floor(coefficient*sqrt(population_2024/1e6)*(1+0.5*historical_ethnic_fractionalization)/10))",
        main_coefficient=coefficient, expansion_coefficient=expansion_coefficient,
        population_only_coefficient=pop_coefficient, total_budget_usd=150,
        unit_cost_assumption_usd=.001, target_unique_main=30_000, known_candidate_target_main=24_000,
        reserve_main_unknown_candidates=6_000, target_unique_expansion=45_000,
        known_candidate_target_expansion=36_000, reserve_expansion_unknown_candidates=9_000,
        memberships_if_all_68_markets_have_10_years_main=sum(main.values())*10,
        memberships_if_all_68_markets_have_10_years_expansion=sum(expansion.values())*10,
        main_no_overlap_cost_bound_at_assumed_rate_usd=round(sum(main.values())*10*.001,2),
        expansion_no_overlap_cost_bound_at_assumed_rate_usd=round(sum(expansion.values())*10*.001,2),
        unique_observed_candidates_main=main_count, unique_observed_candidates_expansion=expansion_count,
        unique_calendar_eligible_candidates=len({r["candidate_id"] for r in import_rows}),
        calendar_eligible_memberships=len(import_rows), all_observed_planning_memberships=len(planning_rows),
        calendar_eligible_cells=sum(r["import_calendar_eligible_items"]>0 for r in cell_rows),
        partial_2026_eligible_cells=sum(r["year"]==2026 and r["import_calendar_eligible_items"]>0 for r in cell_rows),
        incomplete_calendar_cells=sum(r["status"]=="CALENDARIO_INCOMPLETO" for r in cell_rows),
        cells_without_local_data=sum(r["status"]=="SEM_DADOS_LOCAIS" for r in cell_rows),
        estimated_main_observed_cost_usd=round(main_count*.001,3),
        estimated_expansion_observed_cost_usd=round(expansion_count*.001,3),
        diversity_warning="Alesina2003 ethnic measurements1981-2001: historical priority, not current demography or representativeness",
        counting_warning="candidate IDs, not verified unique lyrics; no cross-platform metadata-based merging",
        future_data_warning="Missing and incomplete years need recollection and reranking; quotas are targets, unknown new identities are not cost-certified. Recount global union before paid submissions; stop at30000, expansion45000.",
        identity_warning="Calendar eligibility does not certify source extraction or recording/lyric identity; manual review required",
        paid_calls=0, production_database_writes=0)
    (OUT / "allocation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    table = "\n".join(f'| {r["country_code"]} | {r["country_name"]} | {r["quota_per_year_main"]} | {r["quota_per_year_expansion"]} | {r["quota_population_only"]} |'
                      for r in country_rows)
    note = f'''# Cotas para nova importação de sucessos anuais — 30/10/2026

## Resultado e escopo

Plano para os 68 mercados já analisados, janela candidata 2017–2026. São cotas de músicas por país e ano, não por década e não por plataforma. Uma fonte principal é escolhida para cada célula: calendário completo primeiro; Spotify tem preferência em igualdade de completude. Spotify e YouTube não têm reproduções somadas. Provedores espelhados não são somados.

O cálculo reconstruiu {len(ranked):,} linhas de ranking até a posição 500. Os metadados históricos locais vêm de MGD e Kaggle para Spotify (2017–2022) e capturas web de YouTube (2025–2026). Isso comprova a presença de arquivos locais, não acesso gratuito atual a qualquer data de 2017–2026. A ausência local exige verificar a fonte e coletar, não significa indisponibilidade definitiva de uma API ou página web. Não houve coleta nova de rankings, importação em banco ou análise paga.

O corte das capturas utilizadas é 15/10/2026. Rankings de 2026 são acumulados parciais. YouTube usa o ano de encerramento da semana, inclusive semanas que cruzam a virada do ano. Calendário completo não prova profundidade integral, extração correta, identidade de gravação ou integridade da letra. Dias fora da parada não equivalem a zero streams: o total mede reproduções registradas enquanto a faixa esteve no quadro observado, não todo o consumo nacional.

## Regra de cálculo

Base de 100 por país/ano, teto 500, passos de 10. O peso é sqrt(população2024/1.000.000) × (1 + 0,5 × diversidade étnica histórica). A cota é min(500, 100 + 10 × floor(coeficiente × peso / 10)).

Coeficiente principal calibrado: {coefficient:.12f}. Expansão: {expansion_coefficient:.12f}. Os coeficientes foram encontrados por busca monotônica, sob dois limites simultâneos: união das identidades observadas e total máximo de participações país/ano para dez anos.

Principal: até 24.000 candidatos conhecidos, com 6.000 reservados na meta de 30.000; no máximo 100.000 participações se todos os 68 mercados tiverem dez anos. Expansão: até 36.000 conhecidos e meta de 45.000, com no máximo 125.000 participações. Os números de cotas são decisões operacionais explícitas, não precisão estatística garantida.

População: Banco Mundial 2024, SP.POP.TOTL, resposta local atualizada em 08/10/2026. Exceção Taiwan: 23.400.220 no registro domiciliar ao fim de 2024, Ministério do Interior, conceito diferente do residente de meio de ano do Banco Mundial. Fontes por linha nos arquivos de cotas.

Diversidade: Alesina et al. (2003), índice étnico dos autores, dados de 1981–2001 nos 68 mercados. Não é diversidade atual e não garante representação de grupos internos em uma parada nacional. Usado somente como prioridade histórica limitada. A sensibilidade só população foi recalibrada sob os mesmos limites; consta da tabela e da planilha. Não se misturaram as medidas linguística e religiosa ao índice étnico. Documentação e fontes: research/annual_allocation_demographic_sources_20261030.md.

## Volume e custo

- Principal observado: {len(planning_rows):,} participações país/ano e {main_count:,} identidades candidatas distintas.
- Destas, {len(import_rows):,} participações e {summary['unique_calendar_eligible_candidates']:,} candidatos estão em {summary['calendar_eligible_cells']} calendários elegíveis. Incluem {summary['partial_2026_eligible_cells']} janelas parciais de 2026 e {summary['calendar_eligible_cells']-summary['partial_2026_eligible_cells']} células anuais completas.
- Expansão observada: {expansion_count:,} identidades candidatas distintas.
- Hipótese fornecida pelo pesquisador: US$0,001 por música. Principal observado: US${main_count*.001:.3f}; expansão: US${expansion_count*.001:.3f}. Metas globais de 30.000 e 45.000 equivalem a US$30 e US$45 sob essa hipótese.
- Principal para todos os dez anos, sem qualquer reaproveitamento: {sum(main.values())*10:,} participações, equivalentes a US${sum(main.values())*10*.001:.2f} na mesma hipótese. Expansão: {sum(expansion.values())*10:,}, equivalentes a US${sum(expansion.values())*10*.001:.2f}. São limites aritméticos de uma classificação por participação ao custo assumido, não garantias de faturamento, e não incluem tentativas adicionais, múltiplas versões ou revisão humana.

Esses candidatos não são letras únicas validadas. IDs Spotify são reaproveitados entre países/anos; metadados YouTube normalizados são candidatos provisórios. Não se fundiram Spotify e YouTube por título/artista. Uma reconciliação correta pode reduzir duplicações entre plataformas, enquanto erros de identidade, variantes e novas coletas podem alterar a contagem. O orçamento de produção deve ser refeito sobre edições textuais validadas e piloto real. Teto total vigente informado pelo usuário: US$150; configurações de campanhas antigas não foram editadas.

Ao completar anos faltantes, reordenar o quadro anual inteiro e recalcular a união global. Não acrescentar simplesmente as novas músicas ao fim da lista antiga. A reserva de 6.000 não garante que todos os dados futuros caibam em 30.000; se a união exceder a meta, recalibrar antes de chamadas pagas. Não cobrar novas classificações incompatíveis como se fossem reaproveitamento do mesmo resultado.

## Disponibilidade

2017 e 2022 não têm células anuais completas no material analisado. Em 2018 há 48; em 2019, 53; em 2020, 60; em 2021, 11; em 2025, 50. Em 2026 há 48 janelas completas até o corte parcial. Não há arquivos de ranking usados neste cálculo para 2023–2024. A matriz contém 194 células sem dados locais e 216 com calendário incompleto. Uma cota de 230 não autoriza inventar as posições faltantes nem usar um snapshot diário como ranking anual.

Manter o mesmo critério de seleção antes de recuperar letras. Não substituir silenciosamente um sucesso por música inferior por falta de letra. Déficits de coleta, identidade e letra ficam explícitos. O estudo descreve sucessos selecionados, não uma amostra probabilística da população ou de toda a música de um país. Comparações devem usar denominadores e cobertura próprios, com uma análise comum do Top 100 quando disponível.

## Cotas completas

| ISO | Mercado | Principal por ano | Expansão por ano | Só população por ano |
| --- | --- | ---: | ---: | ---: |
{table}

## Arquivos e operação

- country_quotas.csv: regra por país.
- country_year_import_plan.csv: 680 células com cota, fonte e disponibilidade.
- import_calendar_eligible.csv: lista nominal, ordenada por ranking anual, apenas de calendários completos na janela correspondente. Inclui 2026 parcial e identidades pendentes.
- selected_observed_planning.csv: seleção observada para planejamento, incluindo calendários incompletos; não usar como ranking anual final.
- rankings.parquet e source_coverage.csv: base intermediária de análise.
- allocation_summary.json: parâmetros, estimativas e ressalvas.
- research/calculate_import_quotas_20261030.py: reprodução local sem rede ou banco.

Os importadores antigos mantêm limites fixos de 80/200 em alguns contratos. Este trabalho entrega cálculo e manifesto, não modifica esses importadores nem inicia a coleta. Não executar o comando antigo supondo que ele aplicará estas cotas. A nova execução deve consumir a política por país/ano e preservar as validações acima.

## Verificação

Verificados: 68 países únicos, 680 células únicas, cotas inteiras em passos de dez, ordenação decrescente, deduplicação das identidades e conciliação dos totais. O Top 230 do Brasil em 2019 foi conferido independentemente em pandas, com correspondência exata de IDs, ordem e reproduções com a agregação do MGD. A planilha Excel compara todas as fórmulas de cota às saídas do cálculo, passa por varredura de erros e é renderizada para inspeção. Nenhum gasto foi realizado.
'''
    (ROOT / "research/annual_import_quotas_20261030.md").write_text(note, encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    prepare_ranks()
    allocate()
