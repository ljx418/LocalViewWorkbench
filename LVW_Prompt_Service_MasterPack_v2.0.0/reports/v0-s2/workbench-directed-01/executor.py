"""Recorded offline executor. No service, browser, media or provider execution."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.v0_s2_seal import seal_candidate

DIRECTORY=Path(__file__).resolve().parent
if (DIRECTORY/'receipt.json').exists():raise SystemExit('one-shot evidence slot already terminal')
candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
payload=['LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge',
    'LVW_V0_RuntimePatch/tests/test_s2_video_workbench.py','LVW_V0_RuntimePatch/tests/test_s2_video_request.py',
    'LVW_V0_RuntimePatch/tests/test_s2_video_api.py','LVW_V0_RuntimePatch/tests/test_s2_http.py',
    'tools/v0_s2_http.py','tools/v0_s2_video_controls_test.cjs','.agent-governance/stages/V0-S2',
    'reports/v0-s2/change-request-video-workbench-01.json','reports/v0-s2/change-decision-video-workbench-01.json']
commands=[('directed_unit',[sys.executable,'-B','-m','unittest',
    'LVW_V0_RuntimePatch.tests.test_s2_video_workbench','LVW_V0_RuntimePatch.tests.test_s2_video_request',
    'LVW_V0_RuntimePatch.tests.test_s2_video_api','LVW_V0_RuntimePatch.tests.test_s2_http','-q']),
    ('production_ui_module',['node','--experimental-vm-modules','tools/v0_s2_video_controls_test.cjs']),
    ('governance',[sys.executable,'-B','tools/verify_governance.py','--self-test'])]
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'schema_version':'lvw.s2.workbench-directed/1','project_id':'lvw-prompt-service','stage_id':'V0-S2',
    'workpack_id':'WP-S2-02','candidate_sha':candidate,'spec_version':'V0-S2/1.0.2',
    'acceptance_hash':'32a72139e0c12e0e6d040274024b53bb2dba2f2864b68b840aa215cf739a2a7f',
    'harness_sha256':digest(Path(__file__)),'harness_binding':'Recorded executor stored in evidence; separate from product candidate',
    'decision':'NO_GO','stage_pass_claim':False,'stage_checkpoint_consumed':False,
    'service_starts':0,'provider_calls':0,'browser_runs':0,'check_results':[]}
try:
    identity=seal_candidate(ROOT,candidate,payload);result['identity']=identity
    for name,command in commands:
        process=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=180,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        entry={'name':name,'command':command,'exit_code':process.returncode,'passed':process.returncode==0}
        for label,raw in [('stdout',process.stdout),('stderr',process.stderr)]:
            path=DIRECTORY/(name+'.'+label+'.log')
            path.write_text(raw.decode('utf-8','replace').replace(str(ROOT),'PACK_ROOT'))
            entry[label+'_original_sha256']=hashlib.sha256(raw).hexdigest()
            entry[label+'_artifact']=str(path.relative_to(ROOT));entry[label+'_artifact_sha256']=digest(path)
        if name=='directed_unit':
            summary=process.stderr.decode('utf-8','replace')
            counts=re.findall(r'^Ran ([0-9]+) tests? in ',summary,re.M)
            entry['tests_executed']=int(counts[0]) if len(counts)==1 else None
            entry['passed']=entry['passed'] and bool(entry['tests_executed']) and bool(re.search(r'^OK\s*$',summary,re.M))
        result['check_results'].append(entry)
        (DIRECTORY/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    if seal_candidate(ROOT,candidate,payload)!=identity:raise ValueError('SOURCE_CHANGED_DURING_CHECKS')
    if digest(Path(__file__))!=result['harness_sha256']:raise ValueError('EXECUTOR_CHANGED_DURING_CHECKS')
    if all(c['passed'] for c in result['check_results']):result['decision']='DIRECTED_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE'
except Exception as error:
    result['error_type']=type(error).__name__
finally:
    (DIRECTORY/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'decision':result['decision'],'candidate_sha':candidate,'stage_pass_claim':False}))
raise SystemExit(0 if result['decision']=='DIRECTED_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE' else 1)
