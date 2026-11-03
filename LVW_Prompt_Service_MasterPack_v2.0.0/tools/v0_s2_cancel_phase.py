"""One-shot public preparation/provider cancellation phase for a sealed parent.

No CLI, authorization, service startup or Stage decision. On failure the parent
must clean its owned runtime; this helper never retries a missed cancel window.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import time

from tools.v0_s2_driver import ROOT,base
from tools.v0_s2_runtime import read_jsonl
from tools.v0_s2_http import PinnedLoopbackClient
from tools.v0_s2_public_phase import encoded
from tools.v0_s2_cancel_evidence import cancellation_trace,count
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_evidence import validate_binding

FIXED_CASES=('preparation','provider')


def cancelled_history(history,prompt_id,graph):
    try:
        record=history[prompt_id]
        if (record['prompt'][1]!=prompt_id or record['prompt'][2]!=graph or record.get('outputs')
                or record['status']['status_str']!='error'):raise ValueError('wrong public terminal')
        errors=[payload for name,payload in record['status']['messages'] if name=='execution_error']
        if len(errors)!=1:raise ValueError('public error denominator')
        error=errors[0]
        if (str(error['node_id'])!='1' or error['node_type']!='LVWVideoPromptOwner' or error['prompt_id']!=prompt_id
                or json.loads(error['exception_message'])['code']!='JOB_CANCELLED'):raise ValueError('wrong cancellation error')
        return {'production_error':'JOB_CANCELLED','outputs_absent':True}
    except (KeyError,TypeError,ValueError) as error:raise EvidenceError('public history lacks actual cancelled owner') from error


class CancellationPhase:
    def __init__(self,driver,run_root,*,run_id,binding,fixture,reference,authorize):
        if (not callable(authorize) or not callable(getattr(driver,'resource_observer',None))
                or getattr(driver,'warm_benchmark',False) is not False or getattr(driver,'native_audit',False) is not True):
            raise ValueError('owned monitored native-audit default runtime required')
        validate_binding(binding,binding['issued_at'])
        if (not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',run_id)
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,95}',reference) or '..' in reference
                or not isinstance(fixture,dict) or type(fixture.get('bytes')) is not int
                or not 0<fixture['bytes']<=8*1024*1024 or not re.fullmatch('[0-9a-f]{64}',fixture.get('sha256',''))):
            raise ValueError('cancellation identity/source invalid')
        self.driver=driver;self.root=Path(run_root).resolve(strict=True);self.directory=self.root/'temp/cancel-phase'
        self.run_id=run_id;self.binding=copy.deepcopy(binding);self.fixture=copy.deepcopy(fixture)
        self.reference=reference;self.authorize=authorize;self.actions=[];self.artifacts=[];self.executed=False;self.seen=set()

    def action(self,name,case):
        self.authorize(name,case)
        row={'ordinal':len(self.actions)+1,'action':name,'case_id':case}
        with (self.directory/'actions.jsonl').open('ab') as stream:
            stream.write(encoded(row));stream.flush();os.fsync(stream.fileno())
        self.actions.append(row)

    def artifact(self,name,value):
        raw=encoded(value)
        if len(raw)>24*1024*1024:raise base.StopProbe('CANCEL_ARTIFACT_LIMIT')
        with (self.directory/name).open('xb') as stream:stream.write(raw)
        self.artifacts.append({'file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})

    def request(self,path,case,*,payload=None,timeout=2):
        self.action('control:'+path,case)
        return self.driver._json_request(base.COMFY_URL+path,payload=payload,timeout=timeout,
                                        observer=self.driver.resource_observer)

    def journal(self):
        return read_jsonl(self.root/'temp/lvw-native-events.jsonl',limit=8*1024*1024)

    def delta(self,before):
        now=self.journal()
        if now[:len(before)]!=before:raise EvidenceError('native journal prefix replaced')
        return now[len(before):]

    def verify_source(self):
        binding_file=self.root/'temp/lvw-native-profile.json'
        if (binding_file.is_symlink() or binding_file.stat().st_size>4096
                or getattr(binding_file.stat(),'st_file_attributes',0)&0x400
                or json.loads(binding_file.read_bytes())!=self.binding):raise EvidenceError('cancellation lease file changed')
        path=self.root/'input'/self.reference
        if path.is_symlink() or not path.is_file():raise EvidenceError('cancellation source missing/reparse')
        path.resolve(strict=True).relative_to((self.root/'input').resolve(strict=True))
        if path.stat().st_size!=self.fixture['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=self.fixture['sha256']:
            raise EvidenceError('cancellation source changed')

    def roots(self,case):
        self.action('owned_listener_proof',case)
        value={str(port):self.driver.owned_listener_birth(port) for port in (8191,11434)}
        root=value['11434']
        if (root['pid'],root['start_ticks'])!=(self.binding['ollama_pid'],self.binding['ollama_start_ticks']):
            raise EvidenceError('native cancellation binding root changed')
        if value['8191']!=self._session_proof:raise EvidenceError('pinned public owner changed')
        return value

    def inventory(self,case):
        self.action('model_inventory',case)
        return self.driver._json_request(base.OLLAMA_URL+'/api/ps',timeout=2,
                                         observer=self.driver.resource_observer)[1]

    def provider_prefix(self,case,position):
        self.action('independent_provider_prefix',case);value=self.driver.chat_log_snapshot();count(value)
        self.artifact(case+'.provider-'+position+'.json',value)
        return value

    def wait_window(self,case,before,owner_pid):
        deadline=time.monotonic()+420
        for _ in range(2200):
            if time.monotonic()>=deadline:break
            self.driver.resource_observer()
            status=self.request('/lvw/v0/video/status',case)[1];events=self.delta(before)
            starts=[e for e in events if e['event']=='run_started']
            if len(starts)>1:raise EvidenceError('unexpected concurrent native run')
            if starts:
                start=starts[0];token=start['run_token']
                if (start['candidate_sha']!=self.binding['candidate_sha']
                        or start['authorization_sha256']!=self.binding['authorization_sha256'] or start['owner_pid']!=owner_pid
                        or any(e['run_token']!=token for e in events)):
                    raise EvidenceError('new run owner/source binding mismatch')
                if status.get('run_token')==token:
                    names=[e['event'] for e in events]
                    if status['status'] in ('cancelled','failed','succeeded') or 'run_finished' in names:
                        raise EvidenceError('cancellation window missed')
                    if case=='preparation':
                        if status['status']!='preparing' or 'gpu_admission_started' in names or 'provider_attempt' in names:
                            raise EvidenceError('preparation cancellation window missed')
                        return token,{'status':status,'events':events}
                    sent=[e for e in events if e['event']=='provider_request_sent']
                    closed={e.get('call_index') for e in events if e['event']=='provider_connection_closed'}
                    active=[e for e in sent if e['call_index'] not in closed]
                    if len(active)>1:raise EvidenceError('overlapping provider windows')
                    if active:
                        ps=self.inventory(case);models=ps.get('models')
                        if not isinstance(models,list):raise EvidenceError('invalid live inventory')
                        if models:
                            model=models[0]
                            if (len(models)!=1 or model.get('model',model.get('name'))!=base.MODEL
                                    or model.get('digest')!=self.binding['model_digest']
                                    or type(model.get('size_vram')) is not int or model['size_vram']<=0):
                                raise EvidenceError('wrong resident model')
                            # Re-read after the live-model request: never cancel an
                            # already completed frame merely because an older log
                            # snapshot showed it active.
                            latest=self.delta(before)
                            if not any(e['event']=='provider_connection_closed' and e.get('call_index')==active[0]['call_index'] for e in latest):
                                return token,{'status':status,'events':latest,'api_ps':ps,'active_call_index':active[0]['call_index']}
            time.sleep(.01 if case=='preparation' else .2)
        raise base.StopProbe('CANCEL_WINDOW_TIMEOUT')

    def wait_terminal(self,case,before,token,prompt_id):
        deadline=time.monotonic()+35
        for _ in range(180):
            if time.monotonic()>=deadline:break
            self.driver.resource_observer();events=self.delta(before)
            if any(e['event']=='run_finished' for e in events):
                history=self.request('/history/'+prompt_id,case)[1]
                status=self.request('/lvw/v0/video/status',case)[1]
                if prompt_id in history and status.get('run_token')==token and status.get('resource_state')=='released':
                    return events,history,status
            time.sleep(.2)
        raise base.StopProbe('CANCEL_TERMINAL_TIMEOUT')

    def execute_case(self,case):
        self.verify_source()
        self.action('pin_public_control_session',case)
        client=PinnedLoopbackClient(base.COMFY_URL);original=self.driver.clients[base.COMFY_URL]
        try:
            self._session_proof=client.pin(lambda:self.driver.owned_listener_birth(8191))
            self.artifact(case+'.control-peer.json',self._session_proof)
            self.driver.clients[base.COMFY_URL]=client
            return self._execute_case(case)
        finally:
            self.driver.clients[base.COMFY_URL]=original
            client.close()
            if client.reap_pending(timeout=2):raise base.StopProbe('PINNED_CONTROL_WORKER_REMAINS')

    def _execute_case(self,case):
        self.verify_source();roots=self.roots(case);self.artifact(case+'.roots-before.json',roots)
        if self.inventory(case).get('models')!=[]:raise EvidenceError('cancel phase requires unloaded model')
        before=self.provider_prefix(case,'before');journal_before=self.journal()
        self.artifact(case+'.journal-before.json',journal_before)
        # A queued previous run would make the next start ambiguous; reject it.
        starts={e['run_token'] for e in journal_before if e['event']=='run_started'}
        finishes={e['run_token'] for e in journal_before if e['event']=='run_finished'}
        if starts!=finishes:raise EvidenceError('prior native run incomplete')
        graph=json.loads((ROOT/'LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.api.json').read_text())
        graph['1']['inputs']['video_reference']=self.reference;self.artifact(case+'.graph.json',graph)
        self.action('public_submit',case);prompt_id=self.driver.submit(graph)
        if not re.fullmatch('[0-9a-fA-F-]{1,80}',prompt_id) or prompt_id in self.seen:raise EvidenceError('cancel prompt ID invalid/reused')
        self.seen.add(prompt_id);self.artifact(case+'.prompt-id.json',{'prompt_id':prompt_id})
        token,window=self.wait_window(case,journal_before,roots['8191']['pid']);self.artifact(case+'.window.json',window)
        # Precharge outside the measured round trip; fsync is not cancellation
        # feedback. Exactly one effective cancel action, never a window retry.
        self.action('control:/lvw/v0/video/cancel',case);started=time.monotonic()
        http_status,response=self.driver._json_request(base.COMFY_URL+'/lvw/v0/video/cancel',payload={'run_token':token},
            timeout=2,observer=self.driver.resource_observer)
        ack={'http_status':http_status,'response':response,'elapsed_seconds':time.monotonic()-started}
        self.artifact(case+'.ack.json',ack)
        events,history,status=self.wait_terminal(case,journal_before,token,prompt_id)
        self.artifact(case+'.events.json',events);self.artifact(case+'.history.json',history);self.artifact(case+'.status.json',status)
        after=self.provider_prefix(case,'after');self.action('independent_resource_samples',case)
        samples=self.driver._resource_worker.points();self.artifact(case+'.resource-samples.json',samples)
        value=cancellation_trace(events,binding=self.binding,token=token,owner_pid=roots['8191']['pid'],kind=case,
            ack=ack,before=before,after=after,resource_samples=samples)
        value['public_failure']=cancelled_history(history,prompt_id,graph)
        if (status.get('status')!='cancelled' or status.get('error_code')!='JOB_CANCELLED'
                or status.get('cancel_epoch')!=1):raise EvidenceError('public cancelled terminal mismatch')
        if self.inventory(case).get('models')!=[]:raise EvidenceError('cancelled model remains loaded')
        if self.roots(case)!=roots:raise EvidenceError('cancel root identity changed')
        self.verify_source()
        if list((self.root/'temp').glob('lvw-video-*')):raise EvidenceError('cancel snapshot remains')
        return {'run_token':token,'prompt_id':prompt_id,'oracle':value,'source_sha256':self.fixture['sha256'],
            'owned_listeners':roots,'model_inventory_empty':True,'video_snapshots_absent':True}

    def run(self):
        if self.executed:raise ValueError('cancel phase is one-shot')
        self.executed=True;self.directory.mkdir(exist_ok=False)
        result={'run_id':self.run_id,'candidate_sha':self.binding['candidate_sha'],'authorization_sha256':self.binding['authorization_sha256'],
            'decision':'NO_GO','stage_pass_claim':False,'parent_cleanup_required':True,
            'cases':{case:{'status':'NOT_RUN'} for case in FIXED_CASES}}
        active=None;interrupted=None
        try:
            for case in FIXED_CASES:
                active=case;row=self.execute_case(case);result['cases'][case]={'status':'PASS',**row}
                self.artifact(case+'.oracle.json',row)
            result['decision']='CANCELLATION_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE'
        except BaseException as error:
            if active is not None:result['cases'][active]={'status':'FAIL','error_type':type(error).__name__}
            result['error_code']=getattr(error,'reason',str(error))
            # Preserve raw native terminal/partial evidence on failures too.
            try:self.artifact('failure-journal.json',self.journal())
            except Exception as capture:result['failure_journal_error']=type(capture).__name__
            if isinstance(error,(KeyboardInterrupt,SystemExit)):interrupted=error
        finally:
            statuses=[r['status'] for r in result['cases'].values()]
            result['test_counts']={'fixed':2,'PASS':statuses.count('PASS'),'FAIL':statuses.count('FAIL'),'NOT_RUN':statuses.count('NOT_RUN')}
            result['actions']=copy.deepcopy(self.actions);result['artifacts']=copy.deepcopy(self.artifacts)
            self.artifact('phase-receipt.json',result)
        if interrupted is not None:raise interrupted
        return result
