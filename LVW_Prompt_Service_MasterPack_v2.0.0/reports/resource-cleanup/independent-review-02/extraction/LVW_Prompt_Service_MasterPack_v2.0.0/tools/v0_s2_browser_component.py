"""Directed real browser/model component. NEVER a complete Stage checkpoint.

Reuse the production runtime, browser worker, supervisor and nine local oracles.
Only dependency scope is smaller: critical tools/Comfy/browser/frontend/codecs,
not all Python and Ollama libraries. A later full fresh run remains mandatory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import threading

from tools import v0_s2_stage_checkpoint as cp
from tools import v0_s2_automatic_verification as admission
from tools import v0_verification_authority as authority
from tools.v0_s2_execution_bindings import ExecutionBindings,Tree,plain
from tools.v0_s2_seal import seal_candidate
from tools.v0_s2_stage_runtime import StageRuntimeFactory,TOOL_KEYS
from tools.v0_s2_stage_archive import OwnedArchive
from tools.v0_s2_browser_phase import run_browser_phase
from tools.v0_s2_browser_handlers import default_offline_runner
from tools.v0_s2_warm_phase import WarmPhase
from tools.v0_s2_stage_inputs import load_fixture_set
from tools.v0_s2_component_seeds import add_native_seed_files,verify_seed_identities
from tools.v0_s2_component_clearance import write_clearance

HARNESS='tools/v0_s2_browser_component.py'
SCOPE='DIRECTED_BROWSER_COMPONENT_DEPENDENCIES_NOT_FULL_STAGE_SEAL'
WARM_SCOPE='DIRECTED_WARM_COMPONENT_DEPENDENCIES_NOT_FULL_STAGE_SEAL'
SCOPES={'browser':SCOPE,'warm':WARM_SCOPE}
CASES=('V0-A01','V0-A02','V0-A03','V0-A04','V0-A05','V0-A07','V0-A08','V0-A09','V0-A10')


class Lease:
    def __init__(self,directory,child):
        self.directory=directory;self.child=child;self.actions=0;self.cleanup_only=False
        self.raw=(directory/'active-child.json').read_bytes()
        if json.loads(self.raw)!=child:raise ValueError('component child does not match persisted authority')
        self.lock=threading.RLock()
    def authorize(self,action,detail=None):
        with self.lock:return self._authorize(action,detail)
    def _authorize(self,action,detail):
        expected=SCOPES.get(self.child.get('run_id','').split('-')[0])
        reserved=action in cp.RESERVED
        if self.cleanup_only and not reserved:raise ValueError('component cleanup permits reserved archive only')
        if not reserved:
            authority.validate(cp.repository_json(authority.PROGRAM),'V0-S2')
            control=cp.repository_json('plans/execution-control.json')
            if (control['coordinate']['stage_id']!='V0-S2' or control.get('external_execution_hold',{}).get('active') is not False
                    or self.child.get('status')!='ACTIVE_ONE_SHOT' or self.child.get('scope')!=expected or expected is None
                    or cp.file_hash(cp.ROOT/authority.PROGRAM)!=self.child['program_sha256']
                    or (self.directory/'active-child.json').read_bytes()!=self.raw
                    or (self.directory/'lease.closed').read_bytes()!=b'0'
                    or cp.file_hash(cp.ROOT/HARNESS)!=self.child['harness_sha256']
                    or cp.file_hash(cp.ROOT/'.agent-governance/stages/V0-S2/stage-control.json')!=self.child['stage_packet_sha256']
                    or time.time()>=self.child['expires_at'] or self.actions>=20000):raise ValueError('component authority expired, changed, held or exhausted')
        self.actions+=1
        with (self.directory/'parent-actions.jsonl').open('ab') as output:
            output.write(cp.canonical({'ordinal':self.actions,'action':action,'detail_sha256':hashlib.sha256(cp.canonical(detail)).hexdigest()})+b'\n')
            output.flush();os.fsync(output.fileno())


def run(candidate,offline,run_id,phase='browser'):
    if phase not in SCOPES or not re.fullmatch(phase+'-component-[0-9]{2}',run_id):raise ValueError('directed component identity invalid')
    scope=SCOPES[phase]
    parent=cp.repository_json(authority.PROGRAM);authority.validate(parent,'V0-S2')
    identity=cp.source_gate(candidate,offline);seeds=cp.seed_values()
    budget={**cp.BUDGET,'stage_checkpoints':0,'comfy_starts':1,'ollama_starts':1,'resource_sampler_workers':2,
        'warm_public_submissions':20 if phase=='warm' else 0,'warm_preloads':20 if phase=='warm' else 0,
        'browser_starts':0 if phase=='warm' else 1,'installed_full_snapshots':0,'component_dependency_snapshots':4,'authorization_actions':20000}
    if phase=='warm':budget.update(public_submissions=20,default_public_submissions=0,provider_calls=50,resource_sampler_workers=1)
    child=authority.child(parent,stage='V0-S2',run_id=run_id,candidate=candidate,
        harness_sha256=cp.file_hash(cp.ROOT/HARNESS),program_sha256=cp.file_hash(cp.ROOT/authority.PROGRAM),budget=budget,max_seconds=21600)
    child.update(scope=scope,source_payload_sha256=identity['payload_sha256'],offline_receipt=offline,
        stage_packet_sha256=cp.file_hash(cp.ROOT/'.agent-governance/stages/V0-S2/stage-control.json'),
        offline_receipt_sha256=cp.file_hash(cp.ROOT/offline),samples=seeds['targets']['samples'],
        model_digest=seeds['model']['model_digest'],ports=[8191,11434],
        excluded_whole_dependency_trees=['COMFY_PYTHON_HOME','OLLAMA_HOME'],
        cleanup='original registered roots/PID/birth only, reserved cleanup after expiry; preserve uncertainty')
    directory=cp.STATE_ROOT/run_id
    with cp.complete_admission_guard():
        admission.require_closed_runs();directory.mkdir(exist_ok=False)
        cp.write_new(directory/'active-child.json',child);cp.write_new(directory/'claimed-child.json',child)
        (directory/'lease.closed').write_bytes(b'0')
    lease=Lease(directory,child);authorization_sha=cp.file_hash(directory/'claimed-child.json')
    result={'kind':scope,'run_id':run_id,'candidate_sha':candidate,'authorization_sha256':authorization_sha,'decision':'NO_GO','stage_pass_claim':False,
        'stage_checkpoint_consumed':False,'product_cases':dict.fromkeys(CASES,'NOT_RUN')}
    context=factory=None
    archive=OwnedArchive(directory,run_id=run_id,candidate_sha=candidate,authorization_sha256=authorization_sha,authorize=lease.authorize)
    try:
        lease.authorize('component_source_ready')
        paths,trees,files,metadata=cp.resolve_installed(lease,seeds)
        cp.write_new(directory/'metadata.json',metadata)
        trees={k:v for k,v in trees.items() if k not in {'COMFY_PYTHON_HOME','OLLAMA_HOME'}}
        site=paths['comfy_python'].parent/'Lib/site-packages'
        for key,relative in [('COMPONENT_FRONTEND','comfyui_frontend_package/static'),('COMPONENT_AV','av'),('COMPONENT_PIL','PIL')]:
            trees[key]=Tree(plain(site/relative))
        files,seed_aliases=add_native_seed_files(files,paths,seeds)
        bindings=ExecutionBindings(trees=trees,files=files,authorize=lease.authorize)
        snapshot=bindings.capture();cp.write_new(directory/'component-installed-bindings.json',snapshot)
        result['frozen_seed_checks']=verify_seed_identities(snapshot,seeds,metadata,seed_aliases)
        digests={key:next(row['sha256'] for row in snapshot['files'] if row['alias']==key.upper()) for key in TOOL_KEYS}
        samples=cp.actual_samples(child['samples'])
        frozen=cp.repository_json('reports/v0-s2/frozen-structural-inputs-02.json');plan=load_fixture_set(**frozen['binding_inputs'])
        if {k:v for k,v in frozen.items() if k!='binding_inputs'}!=plan:raise ValueError('frozen component inputs changed')
        snapshots=1
        def verify():
            nonlocal snapshots
            lease.authorize('verify_declared_component_dependencies')
            if snapshots>=4:raise ValueError('component snapshot budget')
            if seal_candidate(cp.ROOT,candidate,cp.SOURCE_PAYLOAD)!=identity:raise ValueError('component source changed')
            snapshots+=1;proof=bindings.verify()
            return {**proof,'candidate_sha':candidate,'binding_scope':scope,
                'tool_bindings':{key:{'path':str(path),'sha256':digests[key]} for key,path in paths.items()}}
        factory=StageRuntimeFactory(directory=directory,run_id=run_id,candidate_sha=candidate,authorization_sha256=authorization_sha,
            paths=paths,tool_sha256=digests,source_identity=identity,samples=samples,fixture_plan=plan,model_digest=child['model_digest'],archive=archive,
            authorize=lease.authorize,verify_complete=verify,guard_critical=lambda:bindings.guard([k.upper() for k in sorted(TOOL_KEYS)]),component_scope=scope)
        context=factory.prepare_warm() if phase=='warm' else factory.prepare_default()
        driver=context.driver;original=driver.resource_observer
        def observe():lease.authorize('component_resource_and_authority_guard');return original()
        driver.resource_observer=observe
        if phase=='warm':
            warm=WarmPhase(driver,context.worker,context.root,run_id=run_id,binding=context.binding,
                samples=context.samples,authorize=lease.authorize).run()
            result.update(warm=warm,dependency_snapshots=snapshots,runtime_counts=cp.terminal_counts(context))
            if warm['decision']=='WARM_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE':
                verify();result['dependency_snapshots']=snapshots
                result['decision']='DIRECTED_WARM_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE'
        else:
            fixture=plan['categories']['tracking']
            offline_runner=default_offline_runner(driver,context.root,run_id=run_id,binding=context.binding,fixture=fixture,
                reference=context.references['tracking'],baseline_gpu_mib=context.baseline_gpu_mib,nvidia_exe=context.nvidia_exe,
                nvidia_sha256=context.nvidia_sha256,authorize=lease.authorize)
            browser=run_browser_phase(driver,config=context.browser_config,binding=context.binding,fixture=fixture,
                node_executable=context.node_executable,node_sha256=context.node_sha256,authorize_launch=context.authorize_launch,
                authorize_action=lease.authorize,verify_bindings=context.verify_bindings,run_offline=offline_runner)
            result.update(browser=browser,dependency_snapshots=snapshots,runtime_counts=cp.terminal_counts(context))
            if browser['decision']=='BROWSER_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE':
                verify();result['dependency_snapshots']=snapshots
                result['decision']='DIRECTED_BROWSER_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE'
    except BaseException as error:result['error_code']=type(error).__name__+':'+str(error)
    finally:
        lease.cleanup_only=True
        if factory is not None:result['runtime_evidence']=factory.evidence
        if context is not None:
            try:
                result['cleanup']=context.driver.cleanup()
                if result['cleanup']['proven'] and (phase=='warm' or (result.get('browser',{}).get('browser_cleanup_proven') is True and result['browser'].get('callbacks_pending')==0)):
                    result['archive']=archive(context,result['cleanup'])
                else:result['decision']='NO_GO'
            except Exception as error:result.update(decision='NO_GO',cleanup_error=type(error).__name__+':'+str(error))
        result['authorization_actions']=lease.actions
        cp.write_new(directory/'terminal.json',result)
        clearance=write_clearance(directory)
        (directory/'lease.closed').write_bytes(b'1')
        cp.write_new(directory/'terminal-child.json',authority.expire(child,'COMPLETE' if result['decision'] in ('DIRECTED_BROWSER_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE','DIRECTED_WARM_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE') else 'NO_GO','terminal.json'))
        report=cp.ROOT/'reports/v0-s2'/run_id;report.mkdir(exist_ok=False)
        public={k:v for k,v in result.items() if k not in ['runtime_evidence','runtime_counts','browser','warm','cleanup']}
        public.update(raw_terminal_sha256=cp.file_hash(directory/'terminal.json'),browser_decision=result.get('browser',{}).get('decision'),warm_decision=result.get('warm',{}).get('decision'),
            cleanup_proven=result.get('cleanup',{}).get('proven',False),resource_clearance=clearance,
            evidence_scope='DIRECTED_ONLY_NO_STAGE_CASES_PASS')
        cp.write_new(report/'receipt.json',cp.base.redact_value(public,{str(cp.ROOT):'PACK_ROOT',str(cp.STATE_ROOT):'STATE',str(cp.SOURCE):'TEST_SOURCE'}))
    return public


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',required=True);parser.add_argument('--offline-receipt',required=True);parser.add_argument('--run-id',required=True)
    parser.add_argument('--phase',choices=tuple(SCOPES),default='browser')
    args=parser.parse_args();result=run(args.candidate,args.offline_receipt,args.run_id,args.phase);print(json.dumps(result))
    raise SystemExit(0 if result['decision'] in ('DIRECTED_BROWSER_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE','DIRECTED_WARM_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE') else 1)
