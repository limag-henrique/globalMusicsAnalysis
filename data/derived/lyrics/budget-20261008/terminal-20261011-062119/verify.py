import json
import shutil
from pathlib import Path
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID
from collections import Counter
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from chart_observatory.config import Settings
from chart_observatory.lyrics.brl_budget import BrlBudgetPolicy
from chart_observatory.lyrics.continuous import exclusive_controller_lock, TECHNICAL_RESPONSE_ERRORS

root = Path('D:/PromiscuidadeMusical')
out = Path(__file__).parent
checkpoint = root / 'data/derived/lyrics/overnight-20261007/status.json'
policy_path = root / 'data/derived/lyrics/budget-20261008/billing-policy.json'
audit_path = root / 'data/derived/research_quality/20261011-061304/audit.json'
with exclusive_controller_lock(checkpoint.with_name('continuous.lock')) as acquired:
    assert acquired, 'controller lock occupied; abort'
    state = json.loads(checkpoint.read_text(encoding='utf-8'))
    assert state['status'] == 'budget_exhausted' and not state.get('preparation_in_progress')
    shutil.copy2(checkpoint, out / 'checkpoint-before.json')
    shutil.copy2(policy_path, out / 'billing-policy-preserved.json')
    shutil.copy2(audit_path, out / 'audit-preserved.json')
    p = json.loads(policy_path.read_text(encoding='utf-8'))
    policy = BrlBudgetPolicy(
        Decimal(p['cap_brl']), Decimal(p['ancillary_reserve_brl']), Decimal(p['retry_reserve_brl']),
        Decimal(p['settled_cost_brl']), frozenset(UUID(v) for v in p['settled_run_ids']),
        datetime.fromisoformat(p['settled_cutoff_utc']), p['project_id'],
        max(Decimal(p['input_brl_per_million']) / Decimal('.375'), Decimal(p['output_brl_per_million']) / Decimal('1.875')),
        Decimal(p['current_account_usable_credit_brl']), frozenset(UUID(v) for v in p['account_baseline_run_ids']))
    settings = Settings.load(root)
    url = make_url(settings.database_url)
    assert url.host == '127.0.0.1' and url.port == 56433
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        version = session.scalar(text("SELECT current_setting('server_version_num')"))
        assert str(version).startswith('16')
        runs = [dict(r) for r in session.execute(text('''SELECT r.id,r.state,r.request_count,r.imported_count,r.summary_written,r.provider_job_name,r.submitted_at,r.job_error_code,
          (SELECT count(*) FROM lyric_classification_snapshots s WHERE s.batch_run_id=r.id) snapshots,
          (SELECT count(*) FROM lyric_classification_batch_items i WHERE i.batch_run_id=r.id AND i.snapshot_id IS NOT NULL) linked_items
          FROM lyric_classification_batch_runs r''')).mappings()]
        selected = [r for r in runs if str(r['id']) in state['retry_run_ids']]
        assert len(selected) == len(state['retry_run_ids'])
        assert all(r['state'] in ('imported','cleaned') and r['summary_written'] and not r['job_error_code'] and r['provider_job_name'] and r['request_count']==r['imported_count']==r['snapshots']==r['linked_items'] for r in selected)
        local_drafts = [r for r in runs if r['state'] in ('prepared','uploaded') and not r['provider_job_name'] and not r['submitted_at']]
        (out/'unsubmitted-drafts-preserved.json').write_text(json.dumps(local_drafts,indent=2,default=str)+'\n',encoding='utf-8')
        reconciled_historical = [r for r in runs if r['provider_job_name'] and r['state'] in ('failed','succeeded','expired','cancelled') and r['summary_written'] and r['request_count']==r['imported_count']==r['snapshots']==r['linked_items']]
        (out/'historical-terminal-states-preserved.json').write_text(json.dumps(reconciled_historical,indent=2,default=str)+'\n',encoding='utf-8')
        pending = [r for r in runs if r['provider_job_name'] and r['state'] not in ('imported','cleaned') and r not in reconciled_historical]
        if pending:
            print(json.dumps(pending,default=str))
        assert not pending, 'pending or unresolved provider jobs'
        failures = [r for r in runs if r['state']=='failed' and r not in reconciled_historical]
        assert all(r['job_error_code']=='batch_preparation_failed' and not r['submitted_at'] and not r['provider_job_name'] for r in failures)
        outcomes = list(session.execute(text('''SELECT batch_run_id,lyric_document_id,classification_status,error FROM lyric_classification_snapshots WHERE batch_run_id IS NOT NULL''')).mappings())
        execution = [r for r in outcomes if str(r['batch_run_id']) in state['retry_run_ids']]
        attempts = Counter(str(r['lyric_document_id']) for r in execution)
        statuses = Counter(r['classification_status'] for r in execution)
        errors = Counter(r['error'] for r in execution if r['classification_status']=='error')
        exhausted = {str(r['lyric_document_id']) for r in execution if r['classification_status']=='error' and attempts[str(r['lyric_document_id'])]>=2}
        assert max(attempts.values())<=2 and sum(statuses.values())==state['night_submitted_count']
        total, account_new = policy.commitments(session)
        known_usd = session.scalar(text('SELECT coalesce(sum(known_cost_usd),0) FROM lyric_classification_batch_runs WHERE NOT (id=ANY(CAST(:ids AS uuid[])))'), {'ids':list(p['settled_run_ids'])})
        known = policy.billing_anchor_brl + known_usd * policy.brl_per_ledger_usd
        reserve = policy.retry_reserve_brl + policy.ancillary_brl
        available = policy.remaining_ledger_usd(session)*policy.brl_per_ledger_usd
        financial = dict(verified_invoice_and_known_token_cost_brl=known,conservative_commitment_brl=total,unknown_cost_reserve_brl=total-known,retry_reserve_brl=policy.retry_reserve_brl,ancillary_reserve_brl=policy.ancillary_brl,total_conservative_with_reserves_brl=total+reserve,current_account_new_commitment_brl=account_new,conservative_available_brl=available,current_credit_revalidation_required=True,latest_observed_credit_brl='242.69',latest_observed_debit_brl='1518.41',known_cost_above_latest_displayed_debit_brl=known-Decimal('1518.41'))
        report = dict(verified_at=datetime.now(UTC).isoformat(),database_host=url.host,database_port=url.port,server_version_num=version,provider_calls=0,database_mutations=0,controller_lock_acquired=True,terminal_status=state['status'],preparation_in_progress=state.get('preparation_in_progress'),all_execution_runs_imported=True,execution_run_count=len(selected),pending_runs=pending,historical_failed_preparations=failures,execution_status_counts=dict(statuses),execution_error_codes=dict(errors),execution_documents=len(attempts),max_execution_attempts_per_document=max(attempts.values()),execution_error_documents_attempts_exhausted=len(exhausted),execution_runs=selected,financial=financial,final_audit_directory=str(audit_path.parent),final_audit=json.loads(audit_path.read_text(encoding='utf-8')),windows_process_evidence='Get-Process python/pythonw returned no processes; Win32_Process command-line query denied by Windows. Terminal checkpoint and exclusive lock independently confirmed.',automation_pause_pending=True)
        (out/'terminal-verification.json').write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('execution_runs','historical_failed_preparations','final_audit')},default=str))
        print('historical_failed_preparations='+str(len(failures)))
        print('unsubmitted_local_drafts='+str(len(local_drafts)))
