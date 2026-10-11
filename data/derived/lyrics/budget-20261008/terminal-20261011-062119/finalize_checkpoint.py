import importlib.util
import json
import shutil
from pathlib import Path
from datetime import UTC, datetime
from chart_observatory.lyrics.continuous import exclusive_controller_lock

root=Path('D:/PromiscuidadeMusical')
out=Path(__file__).parent
path=root/'data/derived/lyrics/overnight-20261007/status.json'
spec=importlib.util.spec_from_file_location('terminal_controller_helpers',root/'scripts/run_continuous_lyrics.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with exclusive_controller_lock(path.with_name('continuous.lock')) as acquired:
    assert acquired, 'controller lock occupied'
    state=json.loads(path.read_text(encoding='utf-8'))
    report=json.loads((out/'terminal-verification.json').read_text(encoding='utf-8'))
    original=json.loads((out/'checkpoint-before.json').read_text(encoding='utf-8'))
    assert state==original and state['status']=='budget_exhausted'
    assert report['all_execution_runs_imported'] and not report['pending_runs']
    rejection='MCP tool call requires approval, but approval policy is never'
    state.update(stop_reason='current_account_reservation_margin_insufficient',
        pending_imports_confirmed=0,
        final_audit_directory='data/derived/research_quality/20261011-061304',
        final_terminal_verification=str((out/'terminal-verification.json').relative_to(root)),
        final_financial_summary=report['financial'],current_credit_revalidation_required=True,
        automation_status='ACTIVE',automation_pause_required=True,
        automation_pause_failure=rejection,
        automation_pause_attempted_utc=datetime.now(UTC).isoformat(),
        last_monitor_inspection_utc=datetime.now(UTC).isoformat(),
        controller_restart_blocked=True)
    module.write_state(path,state)
    shutil.copy2(path,out/'checkpoint-final.json')
    report.update(automation_pause_pending=True,automation_pause_attempted=True,
        automation_pause_rejection=rejection,automation_status='ACTIVE',
        checkpoint_final=str(out/'checkpoint-final.json'),
        unsubmitted_local_drafts_evidence=str(out/'unsubmitted-drafts-preserved.json'),
        historical_terminal_states_evidence=str(out/'historical-terminal-states-preserved.json'))
    (out/'terminal-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':state['status'],'pending_imports':0,'automation_pause_required':True,'evidence':str(out)}))
