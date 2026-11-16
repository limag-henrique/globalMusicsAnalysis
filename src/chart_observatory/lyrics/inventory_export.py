"""Export queue/change-ledger reports and refreshed dynamic HTML/JSON inventory."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chart_observatory.lyrics.corpus_quality import QUALITY_AUDIT_VERSION

PARSER_VERSION = f"quota-acquisition-v2+source-chain-v1+{QUALITY_AUDIT_VERSION}"


def candidate_technical_status(record: dict[str, Any]) -> str:
    """Return explicit technical verification state without implying G2 approval."""
    audit = record.get("audit") or {}
    if not record.get("text_sha256"):
        return "unavailable"
    quality_state = (audit.get("technical_verification") or {}).get("quality_state")
    if audit.get("source_quarantined"):
        return "quarantined_corrupt_source"
    if quality_state in {
        "source_declared_partial",
        "suspected_partial",
        "identity_conflict",
        "pending_adjudication",
        "acquired_unverified",
    }:
        return str(quality_state)
    flags = audit.get("text_quality_flags") or []
    return "pending_adjudication" if flags else "acquired_unverified"


def _automated_validation_status(record: dict[str, Any], dimension: str) -> str:
    audit = record.get("audit") or {}
    validation = audit.get("automated_validation") or {}
    section = validation.get(dimension) or {}
    return str(section.get("status", "pending"))


def _status_letra_label(record: dict[str, Any], technical_status: str) -> str:
    if not record.get("text_sha256"):
        return "Pendente de importacao de letra"
    labels = {
        "quarantined_corrupt_source": "Quarentena LETRAS; aguarda substituicao/validacao",
        "source_declared_partial": "Texto parcial declarado pela fonte; aguarda revisao",
        "suspected_partial": "Suspeita de texto parcial/residuo; aguarda revisao",
        "identity_conflict": "Conflito de identidade ou colisao; aguarda revisao",
        "pending_adjudication": "Texto importado com alertas; aguarda adjudicacao G2",
        "acquired_unverified": "Texto importado; aguarda validacao G2",
    }
    return labels.get(technical_status, "Texto importado; aguarda validacao")


def write_queues_and_change_ledger(
    output_dir: Path,
    v4_records: list[dict[str, Any]],
    v5_extra_records: list[dict[str, Any]],
    change_ledger_rows: list[dict[str, Any]],
    review_dir: Path,
) -> dict[str, Any]:
    """Emit pending/unavailable queue, change ledger, and human review summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    pending_rows: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    all_scope = [("v4", r) for r in sorted(v4_records, key=lambda x: x["candidate_id"])] + [
        ("v5_slovenia_provisional", r)
        for r in sorted(v5_extra_records, key=lambda x: x["candidate_id"])
    ]
    for scope_name, record in all_scope:
        tech_status = candidate_technical_status(record)
        audit = record.get("audit") or {}
        source_result = record.get("source_result") or {}
        payload = record.get("payload") or {}
        if tech_status == "acquired_unverified":
            continue
        errors = list(source_result.get("source_errors") or [])
        terminal_cause = errors[-1] if not record.get("text_sha256") and errors else tech_status
        reason_counts[tech_status] += 1
        pending_rows.append(
            {
                "scope": scope_name,
                "candidate_id": record["candidate_id"],
                "title": payload.get("title"),
                "artist": payload.get("artist"),
                "membership_count": len(payload.get("chart_bindings", [])),
                "chart_bindings": payload.get("chart_bindings", []),
                "acquisition_status": record.get("acquisition_status"),
                "technical_status": tech_status,
                "scientific_approval_status": "not_approved",
                "classification_eligibility": "blocked_pending_gates",
                "text_sha256": record.get("text_sha256"),
                "source_system": source_result.get("source"),
                "quality_flags": list(audit.get("text_quality_flags") or []),
                "source_quarantined": bool(audit.get("source_quarantined")),
                "terminal_cause": terminal_cause,
                "source_errors": errors[:12],
            }
        )

    pending_path = output_dir / "pending-and-unavailable-queue.jsonl"
    pending_bytes = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in pending_rows
    ).encode("utf-8")
    pending_path.write_bytes(pending_bytes)

    pending_summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(pending_rows),
        "by_technical_status": dict(reason_counts),
        "by_scope": dict(Counter(r["scope"] for r in pending_rows)),
        "pending_queue_sha256": hashlib.sha256(pending_bytes).hexdigest(),
    }
    (output_dir / "pending-and-unavailable-queue.json").write_text(
        json.dumps(pending_summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    ledger_path = output_dir / "change-ledger-v1-repairs.jsonl"
    ledger_bytes = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in sorted(change_ledger_rows, key=lambda x: x["candidate_id"])
    ).encode("utf-8")
    ledger_path.write_bytes(ledger_bytes)

    ledger_summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_entries": len(change_ledger_rows),
        "by_change_kind": dict(Counter(r["change_kind"] for r in change_ledger_rows)),
        "by_repair_method": dict(Counter(r["repair_method"] for r in change_ledger_rows)),
        "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
    }
    (output_dir / "change-ledger-v1-repairs.json").write_text(
        json.dumps(ledger_summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Lightweight static HTML review interface (reads user-loaded JSONL packets, zero auto-approval)
    review_html_path = review_dir / "review-interface.html"
    review_html = (
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
        "<title>Interface de Revisao Humana de Letras (G2)</title>"
        "<style>body{font:14px system-ui;max-width:1100px;margin:24px auto;padding:0 16px;"
        "background:#f8fafc;color:#0f172a}section{background:#fff;border:1px solid #cbd5e1;"
        "border-radius:8px;padding:16px;margin:14px 0}pre{white-space:pre-wrap;background:#f1f5f9;"
        "padding:10px;border-radius:6px}</style>"
        "<h1>Revisao Independente de Letras e Evidencias (Gate G2)</h1>"
        "<p>Carregue um arquivo JSONL de fila (<code>quality-review.jsonl</code>, "
        "<code>native-display-review.jsonl</code> ou <code>reviewer-A.jsonl</code>). "
        "As decisoes devem ser exportadas com identificacao do revisor e evidencias; "
        "nenhuma aprovacao e gerada automaticamente.</p>"
        "<section><input type='file' id='f' accept='.jsonl'> "
        "<button id='export'>Exportar decisoes preenchidas (JSONL)</button>"
        "<p id='meta'></p></section><div id='list'></div>"
        "<script>let rows=[],decisions={};"
        "document.getElementById('f').onchange=async e=>{\n"
        "const t=await e.target.files[0].text();"
        "rows=t.split(/\\r?\\n/).filter(Boolean).map(JSON.parse);\n"
        "document.getElementById('meta').textContent="
        "rows.length+' itens carregados (exibindo ate 100)';\n"
        "const d=document.getElementById('list');d.innerHTML='';"
        "rows.slice(0,100).forEach((r,i)=>{\n"
        "const el=document.createElement('section');"
        "const cid=r.candidate_id||'';const h=document.createElement('h3');\n"
        "h.textContent=cid+' - '+((r.title||'')+' / '+(r.artist||''));el.appendChild(h);\n"
        "const pre=document.createElement('pre');"
        "pre.textContent=JSON.stringify(r,null,2);el.appendChild(pre);\n"
        "const sel=document.createElement('select');"
        "['','approved','rejected','quarantined','manual_review'].forEach(v=>{\n"
        "const o=document.createElement('option');o.value=v;"
        "o.textContent=v||'Decisao...';sel.appendChild(o);});\n"
        "const rev=document.createElement('input');rev.placeholder='Revisor ID';\n"
        "const ev=document.createElement('input');ev.placeholder='URL evidencia oficial';\n"
        "sel.onchange=rev.oninput=ev.oninput=()=>{\n"
        "if(sel.value&&rev.value)decisions[cid]={candidate_id:cid,\n"
        "text_sha256:r.text_sha256||null,decision:sel.value,actor:rev.value,"
        "evidence_url:ev.value||null,decided_at:new Date().toISOString()};};\n"
        "el.append(sel,' ',rev,' ',ev);d.appendChild(el);});};\n"
        "document.getElementById('export').onclick=()=>{const b=new Blob(["
        "Object.values(decisions).map(x=>JSON.stringify(x)).join('\\n')+'\\n'],\n"
        "{type:'application/jsonl'});const a=document.createElement('a');\n"
        "a.href=URL.createObjectURL(b);a.download='human-review-decisions.jsonl';a.click();};\n"
        "</script></html>\n"
    )
    review_html_path.write_text(review_html, encoding="utf-8")

    return {
        "pending_queue_jsonl": str(pending_path),
        "pending_queue_summary": pending_summary,
        "change_ledger_jsonl": str(ledger_path),
        "change_ledger_summary": ledger_summary,
        "review_interface_html": str(review_html_path),
    }


def _build_scope_payload(
    selection_root: str,
    records_by_id: dict[str, dict[str, Any]],
    countries: list[dict[str, Any]],
    memberships: list[dict[str, Any]],
    country_names: dict[str, str],
) -> dict[str, Any]:
    quotas = {c["country_code"]: c["quota_per_year_main"] for c in countries}
    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in memberships:
        by_cell[(row["country_code"], int(row["year"]))].append(row)

    celulas: list[dict[str, Any]] = []
    occupied_cells = 0
    cells_80_plus = 0
    deficient_cells = 0
    for code in sorted(country_names):
        quota = quotas.get(code)
        cname = country_names[code]
        for year in range(2018, 2027):
            m_rows = by_cell.get((code, year), [])
            cids = {r["candidate_id"] for r in m_rows}
            com_texto = sum(1 for cid in cids if (records_by_id.get(cid) or {}).get("text_sha256"))
            pos_com_texto = sum(
                1 for r in m_rows if (records_by_id.get(r["candidate_id"]) or {}).get("text_sha256")
            )
            tech_flagged = sum(
                1
                for cid in cids
                if cid in records_by_id
                and candidate_technical_status(records_by_id[cid])
                in {
                    "pending_adjudication",
                    "suspected_partial",
                    "source_declared_partial",
                    "identity_conflict",
                }
            )
            quarantined = sum(
                1
                for cid in cids
                if cid in records_by_id
                and candidate_technical_status(records_by_id[cid]) == "quarantined_corrupt_source"
            )
            # No scientific G1/G2 approvals exist yet; keep explicit 0 from verified records
            prontas_vertex = 0
            sem_ranking = quota - len(m_rows) if isinstance(quota, int) else None
            if m_rows:
                occupied_cells += 1
                if pos_com_texto * 5 >= len(m_rows) * 4:
                    cells_80_plus += 1
                else:
                    deficient_cells += 1
            celulas.append(
                {
                    "pais": cname,
                    "codigo_pais": code,
                    "ano": year,
                    "participacoes": len(m_rows),
                    "candidatos_unicos": len(cids),
                    "com_texto": com_texto,
                    "pendentes_importacao": len(cids) - com_texto,
                    "prontas_vertex": prontas_vertex,
                    "alertas_tecnicos": tech_flagged,
                    "quarentena": quarantined,
                    "posicoes_sem_texto": len(m_rows) - pos_com_texto,
                    "posicoes_sem_ranking": sem_ranking,
                }
            )

    musicas: list[dict[str, Any]] = []
    pos_com_texto_total = 0
    for row in memberships:
        cid = row["candidate_id"]
        rec = records_by_id.get(cid)
        tem_staging = rec is not None
        tech_status = candidate_technical_status(rec) if rec else "not_staged"
        text_sha = rec.get("text_sha256") if rec else None
        tem_texto = bool(text_sha)
        if tem_texto:
            pos_com_texto_total += 1
        src_system = (rec.get("source_result") or {}).get("source") if rec else None
        automated = ((rec.get("audit") or {}).get("automated_validation") or {}) if rec else {}
        automated_identity = _automated_validation_status(rec, "identity") if rec else "pending"
        automated_completeness = (
            _automated_validation_status(rec, "completeness") if rec else "pending"
        )
        pronta_vertex = False
        musicas.append(
            {
                "pais": country_names.get(row["country_code"], row["country_code"]),
                "codigo_pais": row["country_code"],
                "ano": int(row["year"]),
                "posicao": int(row["position"]),
                "musica": row["title"],
                "artista": row["artist"],
                "candidate_id": cid,
                "plataforma": row["platform"],
                "fonte": row.get("provider"),
                "status_selecao": row.get("selection_status"),
                "status_letra": _status_letra_label(rec or {}, tech_status)
                if tem_staging
                else "Pendente de staging",
                "status_tecnico": tech_status,
                "fonte_letra": src_system,
                "elegivel_classificacao": "eligible" if pronta_vertex else "blocked_pending_gates",
                "tem_texto": tem_texto,
                "tem_staging": tem_staging,
                "pronta_vertex": pronta_vertex,
                "hash_letra": text_sha,
                "validacao_automatica_identidade": automated_identity,
                "validacao_automatica_completude": automated_completeness,
                "validacao_automatica_conjunta": automated.get(
                    "automated_overall", "pending_review"
                ),
            }
        )

    all_cids = {r["candidate_id"] for r in memberships}
    cids_com_texto = sum(1 for cid in all_cids if (records_by_id.get(cid) or {}).get("text_sha256"))
    cids_sem_staging = sum(1 for cid in all_cids if cid not in records_by_id)
    tech_counts = Counter(
        candidate_technical_status(records_by_id[cid]) for cid in all_cids if cid in records_by_id
    )
    auto_counts = Counter(
        (records_by_id[cid].get("audit") or {})
        .get("automated_validation", {})
        .get("automated_overall", "pending_review")
        for cid in all_cids
        if cid in records_by_id
    )
    auto_identity_counts = Counter(
        _automated_validation_status(records_by_id[cid], "identity")
        for cid in all_cids
        if cid in records_by_id
    )
    auto_completeness_counts = Counter(
        _automated_validation_status(records_by_id[cid], "completeness")
        for cid in all_cids
        if cid in records_by_id
    )

    resumo = {
        "participacoes": len(memberships),
        "candidatos_unicos": len(all_cids),
        "candidatos_com_texto": cids_com_texto,
        "candidatos_sem_texto": len(all_cids) - cids_com_texto,
        "candidatos_sem_staging": cids_sem_staging,
        "participacoes_com_texto": pos_com_texto_total,
        "participacoes_sem_texto": len(memberships) - pos_com_texto_total,
        "prontas_vertex": 0,
        "candidatos_limpos_nao_aprovados": tech_counts.get("acquired_unverified", 0),
        "candidatos_com_alertas": sum(
            tech_counts.get(k, 0)
            for k in (
                "pending_adjudication",
                "suspected_partial",
                "source_declared_partial",
                "identity_conflict",
            )
        ),
        "candidatos_quarentena": tech_counts.get("quarantined_corrupt_source", 0),
        "validacao_automatica_identidade_aprovada": auto_identity_counts.get("passed", 0),
        "validacao_automatica_completude_aprovada": auto_completeness_counts.get("passed", 0),
        "validacao_automatica_identidade_e_completude_aprovadas": auto_counts.get("passed", 0),
        "celulas_ocupadas": occupied_cells,
        "celulas_com_texto_80_pct": cells_80_plus,
        "celulas_deficientes": deficient_cells,
    }
    return {
        "selecao": selection_root,
        "resumo": resumo,
        "celulas": celulas,
        "musicas": musicas,
    }


def render_inventory_html(payload: dict[str, Any]) -> str:
    """Render dynamic HTML inventory without hardcoded Vertex or eligibility literals."""
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = """<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Inventário de músicas por país e ano</title><style>body{font:15px system-ui;max-width:1500px;margin:30px auto;padding:0 20px;color:#172538;background:#f6f8fb}h1{font-size:28px}section{background:white;padding:18px;margin:18px 0;border:1px solid #dce2eb;border-radius:10px}select,input,button{padding:9px;margin:4px;border:1px solid #bcc9db;border-radius:5px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;border-bottom:1px solid #e2e8f0;text-align:left}th{background:#eaf0f7;position:sticky;top:0}.scroll{overflow:auto;max-height:560px}.cards{display:flex;flex-wrap:wrap;gap:12px}.card{padding:14px;background:#eef3f9;min-width:165px}.card b{display:block;font-size:26px}.muted{color:#536378}a{color:#1455a0}</style><h1>Músicas por país e ano · 2018–2026</h1><p id="date"></p><section><strong id="readyBanner"></strong><p>As letras disponíveis permanecem em staging e aguardam validação de identidade, integridade e direitos. País significa mercado de circulação. 2026 tem corte em 15/10/2026.</p><p>A seleção v4 e a v5 (Eslovênia provisória) possuem staging isolados e verificados no PostgreSQL e SQLite local. Coorte importada histórica (canonical_tracks/lyric_documents) e escopo completo da pesquisa são contabilizados separadamente.</p><a href="inventario-completo.json" download>Baixar todos os dados e a proveniência (JSON)</a></section><section><label>Seleção <select id="scope"><option value="v5">v5 · mais recente · inclui Eslovênia provisória</option><option value="v4">v4 · seleção final de pesquisa</option></select></label><div class="cards" id="cards"></div></section><section><h2>Filtros</h2><select id="country"><option value="">Todos os países</option></select><select id="year"><option value="">Todos os anos</option></select><select id="status"><option value="">Todas as situações</option><option value="pending">Pendentes de importação</option><option value="text">Com texto, aguardam validação</option><option value="flagged">Com alertas/quarentena técnica</option><option value="ready">Prontas para Vertex AI</option></select><input id="search" placeholder="Música, artista ou ID" size="35"><p class="muted">Os totais por célula contam candidatos únicos dentro daquele país/ano. A lista mostra cada participação na seleção. Células sem ranking têm zero músicas identificadas, o que não significa coleta concluída.</p></section><section><h2>Totais por país e ano</h2><p id="cellcount"></p><div class="scroll"><table><thead><tr><th>País</th><th>Ano</th><th>Participações</th><th>Candidatos únicos</th><th>Com texto</th><th>Pendentes de letra</th><th>Prontas Vertex</th><th>Posições sem ranking</th></tr></thead><tbody id="cells"></tbody></table></div></section><section><h2>Lista completa de músicas</h2><p id="count"></p><button id="prev">Anterior</button><button id="next">Próxima</button><span id="pagination"></span><div class="scroll"><table><thead><tr><th>País</th><th>Ano</th><th>Posição</th><th>Música</th><th>Artista</th><th>Letra</th><th>Vertex</th><th>ID / fonte</th></tr></thead><tbody id="songs"></tbody></table></div></section><section><h2>Proveniência</h2><pre id="provenance" style="white-space:pre-wrap;word-break:break-all"></pre></section><script>const D=__DATA__;const $=id=>document.getElementById(id);const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const n=x=>Number(x??0).toLocaleString('pt-BR');let page=0,filtered=[];const size=100;$('date').textContent='Consulta: '+D.consultado_em;for(const c of D.v5.celulas.filter(x=>x.ano===2018))$('country').insertAdjacentHTML('beforeend','<option value="'+esc(c.codigo_pais)+'">'+esc(c.pais)+' ('+c.codigo_pais+')</option>');for(let y=2018;y<=2026;y++)$('year').insertAdjacentHTML('beforeend','<option>'+y+'</option>');function render(){const S=D[$('scope').value],t=S.resumo;$('readyBanner').textContent='Prontas para Vertex AI: '+n(t.prontas_vertex)+'.';$('cards').innerHTML=[['Candidatos únicos',t.candidatos_unicos],['Com texto importado',t.candidatos_com_texto],['Sem texto importado',t.candidatos_sem_texto],['Limpos (aguardam G2)',t.candidatos_limpos_nao_aprovados??0],['Alertas / Quarentena',(t.candidatos_com_alertas??0)+(t.candidatos_quarentena??0)],['Prontas Vertex',t.prontas_vertex],['Participações',t.participacoes]].map(([k,v])=>'<div class="card"><b>'+n(v)+'</b>'+k+'</div>').join('');const c=$('country').value,y=$('year').value,q=$('search').value.toLowerCase(),s=$('status').value;const cs=S.celulas.filter(r=>(!c||r.codigo_pais===c)&&(!y||r.ano==y));$('cells').innerHTML=cs.map(r=>'<tr>'+[r.pais+' ('+r.codigo_pais+')',r.ano,r.participacoes,r.candidatos_unicos,r.com_texto,r.pendentes_importacao,r.prontas_vertex??0,r.posicoes_sem_ranking??'Cota indefinida'].map(v=>'<td>'+esc(v)+'</td>').join('')+'</tr>').join('');$('cellcount').textContent=n(cs.length)+' células país/ano · '+n(cs.reduce((a,r)=>a+r.participacoes,0))+' participações · '+n(cs.reduce((a,r)=>a+r.posicoes_sem_texto,0))+' participações sem letra. Busca e situação filtram apenas a lista abaixo.';filtered=S.musicas.filter(r=>(!c||r.codigo_pais===c)&&(!y||r.ano==y)&&(!q||(r.musica+' '+r.artista+' '+r.candidate_id).toLowerCase().includes(q))&&(!s||(s==='pending'&&!r.tem_texto)||(s==='text'&&r.tem_texto)||(s==='flagged'&&(r.status_tecnico&&r.status_tecnico!=='acquired_unverified'&&r.status_tecnico!=='unavailable'))||(s==='ready'&&r.pronta_vertex)));page=0;draw();$('provenance').textContent=JSON.stringify({consultado_em:D.consultado_em,run_id:D.run_id,run_id_v5:D.run_id_v5,snapshot_criado_em:D.snapshot_criado_em,coorte_importada:D.coorte_importada,politica_portoes:D.politica_portoes,selecao:S.selecao,resumo:S.resumo,notas:D.notas},null,2)}function draw(){$('count').textContent=n(filtered.length)+' participações encontradas · '+n(new Set(filtered.map(r=>r.candidate_id)).size)+' candidatos únicos';$('songs').innerHTML=filtered.slice(page*size,(page+1)*size).map(r=>'<tr>'+[r.pais,r.ano,r.posicao,r.musica,r.artista,r.status_letra,r.pronta_vertex?'Pronta':'Bloqueada ('+(r.status_tecnico||'Pendente')+')',r.candidate_id+' / '+(r.fonte||'')+(r.fonte_letra?' ['+r.fonte_letra+']':'')].map(v=>'<td>'+esc(v)+'</td>').join('')+'</tr>').join('');$('pagination').textContent=' Página '+(page+1)+' de '+Math.max(1,Math.ceil(filtered.length/size));$('prev').disabled=page===0;$('next').disabled=(page+1)*size>=filtered.length}for(const id of ['scope','country','year','status'])$(id).onchange=render;$('search').oninput=render;$('prev').onclick=()=>{page--;draw()};$('next').onclick=()=>{page++;draw()};render();</script></html>\n"""  # noqa: E501
    template = template.replace(
        "<th>Letra</th><th>Vertex</th><th>ID / fonte</th>",
        "<th>Letra</th>"
        "<th>Identidade auto</th>"
        "<th>Completude auto</th>"
        "<th>Vertex</th><th>ID / fonte</th>",
    )
    template = template.replace(
        "r.status_letra,r.pronta_vertex?'Pronta':'Bloqueada ('+"
        "(r.status_tecnico||'Pendente')+')',r.candidate_id",
        "r.status_letra,r.validacao_automatica_identidade,"
        "r.validacao_automatica_completude,r.pronta_vertex?'Pronta':'Bloqueada ('+"
        "(r.status_tecnico||'Pendente')+')',r.candidate_id",
    )
    return template.replace("__DATA__", embedded, 1)


def rebuild_inventory_outputs(
    out_dir: Path,
    *,
    v4_selection_dir: Path,
    v5_selection_dir: Path,
    v4_run_id: str,
    v5_run_id: str,
    snapshot_created_at: str,
    v4_records_by_id: dict[str, dict[str, Any]],
    v5_records_by_id: dict[str, dict[str, Any]],
    cohort_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Regenerate inventario-completo.json and dynamic inventario.html."""
    out_dir.mkdir(parents=True, exist_ok=True)
    v4_countries = json.loads((v4_selection_dir / "countries.json").read_text(encoding="utf-8-sig"))
    v5_countries = json.loads((v5_selection_dir / "countries.json").read_text(encoding="utf-8-sig"))
    country_names = {c["country_code"]: c["country_name"] for c in v5_countries}
    v4_memberships = [
        json.loads(line)
        for line in (v4_selection_dir / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    v5_memberships = [
        json.loads(line)
        for line in (v5_selection_dir / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    v4_payload = _build_scope_payload(
        str(v4_selection_dir.resolve()),
        v4_records_by_id,
        v4_countries,
        v4_memberships,
        country_names,
    )
    v5_payload = _build_scope_payload(
        str(v5_selection_dir.resolve()),
        v5_records_by_id,
        v5_countries,
        v5_memberships,
        country_names,
    )

    data = {
        "consultado_em": datetime.now(UTC).isoformat(),
        "run_id": v4_run_id,
        "run_id_v5": v5_run_id,
        "snapshot_criado_em": snapshot_created_at,
        "sem_alteracao_banco": False,
        "adjudicacoes_canonicas": 0,
        "blobs_ausentes": 0,
        "politica_portoes": {
            "policy": "complete-rankings-lyrics80-v1",
            "G1": {"required": 1.0, "approved": 0, "state": "reprovado"},
            "G2": {"required": 0.8, "approved": 0, "state": "pendente"},
            "G3": {"required": 1.0, "prepared": 0, "state": "pendente"},
            "G4": {"independent_scientific_validation": True, "state": "pendente"},
            "G5": {"required": 0.8, "released_accepted": 0, "state": "pendente"},
        },
        "coorte_importada": cohort_metrics,
        "notas": [
            "Pais representa mercado da parada, nao nacionalidade do artista.",
            (
                "Contagens unicas usam candidate_id de plataforma; "
                "participacoes repetem musicas em paises/anos distintos."
            ),
            (
                "Texto importado e verificacao tecnica nao constituem "
                "aprovacao cientifica (Gate G2)."
            ),
            "Sem ranking nao e musica identificada pendente de letra.",
            "2026 parcial ate 15/10/2026.",
            (
                "Selecao v5 e provisoria (Eslovenia IPF 2018-2025) "
                "e possui staging proprio separado de v4."
            ),
        ],
        "v4": v4_payload,
        "v5": v5_payload,
    }
    json_path = out_dir / "inventario-completo.json"
    html_path = out_dir / "inventario.html"
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    json_path.write_bytes(json_bytes)
    html_bytes = render_inventory_html(data).encode("utf-8")
    html_path.write_bytes(html_bytes)

    return {
        "inventario_json": str(json_path),
        "inventario_json_sha256": hashlib.sha256(json_bytes).hexdigest(),
        "inventario_html": str(html_path),
        "inventario_html_sha256": hashlib.sha256(html_bytes).hexdigest(),
        "v4_resumo": v4_payload["resumo"],
        "v5_resumo": v5_payload["resumo"],
    }
