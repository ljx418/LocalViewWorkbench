"""One deliberate owned Ollama death, then public CPU/manual/quarantine checks.

Must be the final default-runtime phase. No restart, new lease, CLI or Stage PASS;
the parent later proves final cleanup and creates a fresh warm runtime.
"""
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import valid_baseline
import copy
import hashlib
import json
import re
import time

from tools.v0_s2_cancel_phase import CancellationPhase
from tools.v0_s2_driver import base,ROOT
from tools.v0_s2_http import PinnedLoopbackClient,ControlError
from tools.v0_s2_public_phase import failure_oracle
from tools.v0_s2_fault_evidence import fault_trace
from tools.v0_s2_checkpoint_oracles import EvidenceError

FIXED_CASES=('provider-root-stop','manual-offline','quarantine-entry','adopt-denied')
FIELDS={'natural_zh':'模型中断后保留人工稿','natural_en':'Manual draft after interruption',
    'image_prompt':'local still life','video_prompt':'camera remains static','tags':'人工,local',
    'negative':'blur','edit_instruction':'保留构图'}


class FaultPhase(CancellationPhase):
    def __init__(self,*args,baseline_gpu_mib,**kwargs):
        super().__init__(*args,**kwargs)
        if type(baseline_gpu_mib) is not int or not valid_baseline(baseline_gpu_mib):raise ValueError('cold baseline required')
        self.baseline=baseline_gpu_mib;self.directory=self.root/'temp/fault-phase'

    def terminal(self,before,token,prompt_id):
        deadline=time.monotonic()+35
        for _ in range(180):
            if time.monotonic()>=deadline:break
            self.driver.resource_observer();events=self.delta(before)
            if any(e['event']=='run_finished' for e in events):
                history=self.request('/history/'+prompt_id,'provider-root-stop')[1]
                status=self.request('/lvw/v0/video/status','provider-root-stop')[1]
                if prompt_id in history and status.get('run_token')==token and status.get('status')=='failed':return events,history,status
            time.sleep(.2)
        raise base.StopProbe('FAULT_TERMINAL_TIMEOUT')

    def execute_fault(self):
        case='provider-root-stop';self.verify_source();roots=self.roots(case);self.artifact('roots-before.json',roots)
        worker=self.driver._resource_worker
        if (getattr(self.driver,'_fault_sampler_activated',False) is not True or worker.scope!='COMFY_ONLY_FAULT'
                or worker.pids!=[roots['8191']['pid']]):raise EvidenceError('explicit live-Comfy fault sampler required')
        if self.inventory(case).get('models')!=[]:raise EvidenceError('fault phase requires unloaded model')
        before=self.provider_prefix(case,'before');journal=self.journal();self.artifact('journal-before.json',journal)
        if ({e['run_token'] for e in journal if e['event']=='run_started'}
                !={e['run_token'] for e in journal if e['event']=='run_finished'}):raise EvidenceError('prior native run incomplete')
        graph=json.loads((ROOT/'LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.api.json').read_text())
        graph['1']['inputs']['video_reference']=self.reference;self.graph=graph;self.artifact('graph.json',graph)
        self.action('public_submit',case);prompt_id=self.driver.submit(graph)
        if not re.fullmatch('[0-9a-fA-F-]{1,80}',prompt_id):raise EvidenceError('fault prompt ID invalid')
        self.prompt_id=prompt_id
        # wait_window and the trace oracle both require an actual active send;
        # the inventory also proves the bound model is GPU resident.
        token,window=self.wait_window('provider',journal,roots['8191']['pid']);self.token=token;self.artifact('window.json',window)
        self.action('native_clock_before_stop',case);start=self.driver.native_clock()
        self.action('stop_owned_ollama',case);stop=self.driver.stop_ollama();self.artifact('owned-stop.json',stop)
        self.action('native_clock_after_stop',case);end=self.driver.native_clock();clocks={'before':start,'after':end};self.artifact('stop-clocks.json',clocks)
        events,history,status=self.terminal(journal,token,prompt_id)
        self.artifact('events.json',events);self.artifact('history.json',history);self.artifact('status.json',status)
        after=self.provider_prefix(case,'after')
        prepared=[e for e in events if e['event']=='source_prepared']
        if len(prepared)!=1 or prepared[0]['source_sha256']!=self.fixture['sha256']:raise EvidenceError('fault decoded another source')
        deadline=time.monotonic()+30;stable=0;point=None
        for _ in range(32):
            if time.monotonic()>=deadline:break
            point=self.driver.guard_point(after=point['monotonic_seconds'] if point is not None else end['monotonic_seconds'])
            if point['monotonic_seconds']-start['monotonic_seconds']>30:break
            stable=stable+1 if point['gpu_used_mib']<=self.baseline+1024 else 0
            if stable>=3:break
        samples=worker.points();self.artifact('resource-samples.json',samples)
        result=fault_trace(events,binding=self.binding,owner_pid=roots['8191']['pid'],token=token,before=before,after=after,
            stop=stop,clocks=clocks,resource_samples=samples,baseline_gpu_mib=self.baseline)
        terminal=events[-1]
        if status.get('resource_state')!='unknown' or status.get('error_code')!=terminal['error_code']:raise EvidenceError('public fault quarantine mismatch')
        # This helper checks graph/error/output identity; provider accounting is
        # independently proved by fault_trace, not by this negative's counters.
        record=history[prompt_id]
        if record['prompt'][2]!=graph or record['prompt'][1]!=prompt_id or record.get('outputs') or record['status']['status_str']!='error':
            raise EvidenceError('fault public history mismatch')
        errors=[e for name,e in record['status']['messages'] if name=='execution_error']
        if (len(errors)!=1 or str(errors[0]['node_id'])!='1' or errors[0]['node_type']!='LVWVideoPromptOwner'
                or errors[0]['prompt_id']!=prompt_id or json.loads(errors[0]['exception_message'])['code']!=terminal['error_code']):
            raise EvidenceError('fault lacks actual production error')
        self.verify_source()
        if list((self.root/'temp').glob('lvw-video-*')):raise EvidenceError('fault video snapshot remains')
        self.fault_roots=roots;self.fault_events=self.journal();self.fault_prefix=after
        return {'prompt_id':prompt_id,'run_token':token,'oracle':result,'public_status':status,'video_snapshots_absent':True}

    def unchanged(self,case):
        self.action('owned_comfy_proof',case)
        if self.driver.owned_listener_birth(8191)!=self.fault_roots['8191']:raise EvidenceError('manual peer changed')
        if self.journal()!=self.fault_events:raise EvidenceError('faulted runtime created new native work')
        current=self.provider_prefix(case,'after')
        if current!=self.fault_prefix:raise EvidenceError('offline/quarantine operation made provider calls')

    def execute_manual(self):
        case='manual-offline';status,value=self.request('/lvw/v0/video/workbench',case,payload={'action':'preview','fields':FIELDS})
        self.artifact(case+'.response.json',value);result=value['result'];expected={**FIELDS,'tags':['人工','local']}
        import jsonschema
        jsonschema.Draft202012Validator(json.loads((ROOT/'contracts/v0-result.schema.json').read_text())).validate(result)
        if (status!=200 or result.get('draft')!=expected or result.get('source_type')!='manual' or result.get('draft_origin')!='manual'
                or result.get('analysis_status')!='not_requested' or any(result.get(k) is not None for k in
                    ('raw_response','suggestion','run_id','source','model_tag','model_digest'))
                or any(v not in value.get('txt','') for k,v in FIELDS.items() if k!='tags')):
            raise EvidenceError('offline manual draft/serialization changed')
        self.unchanged(case)
        return {'draft_preserved':True,'manual_json_and_txt_available':True,'provider_calls':0,'browser_not_tested':True}

    def execute_quarantine(self):
        case='quarantine-entry';self.action('public_submit',case);prompt_id=self.driver.submit(self.graph)
        if not re.fullmatch('[0-9a-fA-F-]{1,80}',prompt_id) or prompt_id==self.prompt_id:raise EvidenceError('reused/invalid fault prompt')
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            history=self.request('/history/'+prompt_id,case)[1]
            if prompt_id in history:break
            time.sleep(.2)
        else:raise base.StopProbe('QUARANTINE_HISTORY_TIMEOUT')
        self.artifact(case+'.history.json',history)
        value=failure_oracle(history,prompt_id,self.graph,code='RESOURCE_BUSY',subcode='VIDEO_REQUEST_ACTIVE',
            chat_before=self.fault_prefix['chat_calls'],chat_after=self.driver.chat_log_snapshot()['chat_calls'])
        self.unchanged(case)
        return {'prompt_id':prompt_id,'oracle':value,'new_inference_blocked':True}

    def execute_adopt(self):
        case='adopt-denied';self.unchanged(case)
        try:self.request('/lvw/v0/video/workbench',case,payload={'action':'adopt','run_token':self.token})
        except ControlError as error:
            if (error.http_status!=409 or not isinstance(error.response,dict) or error.response.get('error',{}).get('code')!='ATTEMPT_STALE'
                    or not isinstance(error.response_raw,bytes) or json.loads(error.response_raw)!=error.response):raise
            self.artifact(case+'.response.json',{'http_status':409,'response':error.response,
                'raw_response':error.response_raw.decode('utf-8'),'raw_sha256':hashlib.sha256(error.response_raw).hexdigest()})
            # A 409 intentionally closes the pinned connection. No new work or
            # reconnect is attempted after this final public negative.
            if self.journal()!=self.fault_events or self.driver.chat_log_snapshot()!=self.fault_prefix:raise EvidenceError('failed adoption changed model state')
            return {'production_error':'ATTEMPT_STALE','result_adoption_rejected':True,'provider_calls':0}
        raise EvidenceError('failed job was adopted')

    def run(self):
        if self.executed:raise ValueError('fault phase is one-shot')
        self.executed=True;self.directory.mkdir(exist_ok=False)
        result={'run_id':self.run_id,'candidate_sha':self.binding['candidate_sha'],'authorization_sha256':self.binding['authorization_sha256'],
            'decision':'NO_GO','stage_pass_claim':False,'parent_cleanup_required':True,'in_process_recovery_claimed':False,
            'cases':{case:{'status':'NOT_RUN'} for case in FIXED_CASES}}
        client=None;original=self.driver.clients[base.COMFY_URL];active=None;interrupted=None
        try:
            self.verify_source();self.action('pin_public_control_session','provider-root-stop');client=PinnedLoopbackClient(base.COMFY_URL)
            self._session_proof=client.pin(lambda:self.driver.owned_listener_birth(8191));self.driver.clients[base.COMFY_URL]=client
            for active,execute in zip(FIXED_CASES,(self.execute_fault,self.execute_manual,self.execute_quarantine,self.execute_adopt)):
                row=execute();result['cases'][active]={'status':'PASS',**row};self.artifact(active+'.oracle.json',row)
            result['decision']='FAULT_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE'
        except BaseException as error:
            if active is not None:result['cases'][active]={'status':'FAIL','error_type':type(error).__name__}
            result['error_code']=getattr(error,'reason',str(error))
            try:self.artifact('failure-journal.json',self.journal())
            except Exception as capture:result['failure_journal_error']=type(capture).__name__
            if isinstance(error,(KeyboardInterrupt,SystemExit)):interrupted=error
        finally:
            self.driver.clients[base.COMFY_URL]=original
            if client is not None:
                client.close()
                if client.reap_pending(timeout=2):result.update(decision='NO_GO',error_code='PINNED_CONTROL_WORKER_REMAINS')
            statuses=[r['status'] for r in result['cases'].values()]
            result['test_counts']={'fixed':4,'PASS':statuses.count('PASS'),'FAIL':statuses.count('FAIL'),'NOT_RUN':statuses.count('NOT_RUN')}
            result['actions']=copy.deepcopy(self.actions);result['artifacts']=copy.deepcopy(self.artifacts);self.artifact('phase-receipt.json',result)
        if interrupted is not None:raise interrupted
        return result
