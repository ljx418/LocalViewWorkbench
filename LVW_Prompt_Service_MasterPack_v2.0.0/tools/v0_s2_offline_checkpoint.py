"""Candidate-bound sequential offline checks, with original command receipts.

No product service, model, media decode or Stage PASS is authorized here.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

from tools.v0_s2_seal import seal_candidate
from tools.v0_s2_stage_checkpoint import SOURCE_PAYLOAD

ROOT=Path(__file__).resolve().parents[1]
PAYLOAD=[*SOURCE_PAYLOAD,'plans/execution-control.json','MANIFEST.sha256',
         'reports/v0-s2/fixture-preparation-01','reports/v0-s2/authorization-fixtures-01.json',
         'reports/v0-s2/offline-checkpoint-08/receipt.json']
CHECKS=[
    ('v0_subtree',[sys.executable,'-B','-m','unittest','discover','-s','LVW_V0_RuntimePatch/tests','-p','test_*.py','-q'],600),
    ('native_ui_module',['node','--experimental-vm-modules','tools/v0_s2_video_controls_test.cjs'],60),
    ('pack_contracts',[sys.executable,'-B','tools/verify_pack.py','--schema'],600),
    ('governance',[sys.executable,'-B','tools/verify_governance.py','--self-test'],120),
    ('whitespace',['git','diff','--check'],120),
]


def packet_binding():
    control=json.loads((ROOT/'.agent-governance/stages/V0-S2/stage-control.json').read_text())
    return {'spec_version':'V0-S2/'+control['stage_packet_version'],'gate_version':control['gate_version'],
            'acceptance_hash':control['acceptance_hash']}


def execute(run_id):
    if not re.fullmatch(r'offline-checkpoint-[0-9]{2}',run_id):raise ValueError('INVALID_OFFLINE_RUN_ID')
    candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,timeout=60).strip()
    directory=ROOT/'reports/v0-s2'/run_id;directory.mkdir(exist_ok=False)
    identity=None
    result={'schema_version':'lvw.s2.offline-checkpoint/1','project_id':'lvw-prompt-service',
        'stage_id':'V0-S2','workpack_id':'WP-S2-04','run_id':run_id,'candidate_sha':candidate,
        'spec_version':None,'gate_version':None,
        'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'acceptance_hash':'32a72139e0c12e0e6d040274024b53bb2dba2f2864b68b840aa215cf739a2a7f',
        'identity':None,'preflight_status':'NOT_RUN','environment':{'python':platform.python_version(),'platform':platform.system()},
        'check_results':[],'decision':'NO_GO','stage_pass_claim':False,
        'live_stage_checkpoint_consumed':False,'provider_calls':0,'service_starts':0,
        'product_cases':{case:'NOT_RUN' for case in ('V0-A02','V0-A07','V0-A09','V0-A10')}}
    try:
        identity=seal_candidate(ROOT,candidate,PAYLOAD)
        packet=packet_binding()
        if packet['acceptance_hash']!=result['acceptance_hash']:raise ValueError('FROZEN_ACCEPTANCE_HASH_CHANGED')
        result.update(packet)
        result.update(identity=identity,preflight_status='PASS')
        # Sequential: historical test fixtures must be gone before pack rglob.
        for name,command,timeout in CHECKS:
            entry={'name':name,'command':command,'exit_code':None}
            result['check_results'].append(entry)
            try:
                process=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=timeout,
                    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
                stdout,stderr=process.stdout,process.stderr;entry['exit_code']=process.returncode
            except subprocess.TimeoutExpired as exc:
                stdout,stderr=exc.stdout or b'',exc.stderr or b''
                entry.update(exit_code=124,error='CHECK_TIMEOUT_CHILD_CLEANUP_UNPROVEN')
            for label,raw in [('stdout',stdout),('stderr',stderr)]:
                entry[label+'_original_sha256']=hashlib.sha256(raw).hexdigest()
                text=raw.decode('utf-8','replace').replace(str(ROOT),'PACK_ROOT')
                path=directory/(name+'.'+label+'.log')
                path.write_text(text)
                entry[label+'_artifact']=str(path.relative_to(ROOT))
                entry[label+'_artifact_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            entry['passed']=entry['exit_code']==0
            if name=='v0_subtree':
                summary=stderr.decode('utf-8','replace')
                counts=re.findall(r'^Ran ([0-9]+) tests? in ',summary,re.M)
                entry['unit_tests_executed']=int(counts[0]) if len(counts)==1 else None
                if (not entry['unit_tests_executed'] or not re.search(r'^OK\s*$',summary,re.M)):
                    entry.update(passed=False,oracle_error='MISSING_OR_INCOMPLETE_UNIT_TEST_SUMMARY')
            (directory/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
            if entry['exit_code']==124:break
        # Seal again: no source mutation while checks were executing.
        if seal_candidate(ROOT,candidate,PAYLOAD)!=identity:raise ValueError('PAYLOAD_CHANGED_DURING_CHECKS')
        if len(result['check_results'])==len(CHECKS) and all(item['passed'] for item in result['check_results']):
            result['decision']='OFFLINE_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE'
    except Exception as exc:
        if result['preflight_status']!='PASS':result['preflight_status']='FAIL'
        result['error_code']=type(exc).__name__+':'+str(exc).replace(str(ROOT),'PACK_ROOT')
    finally:
        results=result['check_results']
        result['test_counts']={'fixed_checks':len(CHECKS),'PASS':sum(item.get('passed') is True for item in results),
            'FAIL':sum(item.get('passed') is False for item in results),
            'BLOCKED':sum(type(item.get('passed')) is not bool for item in results),'SKIPPED':0,
            'NOT_RUN':len(CHECKS)-len(results)}
        result['finished_at']=datetime.now(timezone.utc).isoformat()
        (directory/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
    result=execute(args.run_id)
    print(json.dumps({key:result[key] for key in ('decision','candidate_sha','stage_pass_claim')}))
    raise SystemExit(0 if result['decision']=='OFFLINE_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE' else 1)
