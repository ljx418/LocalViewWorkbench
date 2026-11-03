"""Fixed native warm phase, invoked only inside a sealed authorized parent run.

No CLI, automatic authorization, service startup or Stage PASS. Raw artifacts
stay below the run-owned temporary root for the parent to retain/redact safely.
The parent must own a concurrent resource abort guard, including during blocking
preloads, and terminal service cleanup. This phase alone is not a live runner.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import time

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.benchmark import validate_binding
from tools.v0_s2_driver import ROOT,base
from tools.v0_s2_runtime import read_jsonl
from tools.v0_s2_measurements import hot_record
from tools.v0_s2_checkpoint_oracles import performance_oracle

FIXED_CASES=tuple((f'{kind}-{index:02d}',kind) for kind in ('image','video') for index in range(1,11))


def json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode('utf-8')


def sha_file(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=256*1024*1024:
        raise base.StopProbe('WARM_SAMPLE_INVALID')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):digest.update(chunk)
    return digest.hexdigest()


class WarmPhase:
    def __init__(self,driver,worker,run_root,*,run_id,binding,samples,authorize):
        if not callable(authorize):raise ValueError('parent action authorization callback required')
        if not isinstance(run_id,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',run_id):
            raise ValueError('invalid run identity')
        for key,size in [('candidate_sha',40),('authorization_sha256',64),('model_digest',64),('nvidia_smi_sha256',64)]:
            if not isinstance(binding.get(key),str) or not re.fullmatch('[0-9a-f]{'+str(size)+'}',binding[key]):
                raise ValueError('invalid warm binding')
        # Structural lease validation only: actual freshness remains the
        # parent authorization callback's obligation before native actions.
        validate_binding(binding,binding.get('issued_at'))
        if set(samples)!={'image','video'}:raise ValueError('fixed image/video sources required')
        for kind,value in samples.items():
            reference=value.get('reference')
            if (not isinstance(reference,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,95}',reference)
                    or '..' in reference or not re.fullmatch('[0-9a-f]{64}',value.get('sha256',''))):
                raise ValueError('invalid staged sample binding')
            if Path(reference).suffix.lower() not in ({'.png','.jpg','.jpeg','.webp'} if kind=='image' else {'.mp4','.mov'}):
                raise ValueError('sample suffix mismatch')
        self.driver=driver;self.worker=worker;self.root=Path(run_root).resolve(strict=True)
        self.run_id=run_id;self.binding=copy.deepcopy(binding);self.samples=copy.deepcopy(samples)
        self.authorize=authorize;self.directory=self.root/'temp/warm-phase';self.executed=False
        self.ledger=[];self.artifacts=[];self.preload_owned=False;self.prompt_ids=set()

    def action(self,name,case_id,*,cleanup=False):
        # A refusal causes no action. Once granted, charge durably BEFORE the
        # external operation, including operations that later fail or time out.
        # Terminal cleanup of the parent-owned resources is already reserved
        # by that run; expiry/refusal of new work must never prevent cleanup.
        if not cleanup:self.authorize(name,case_id)
        entry={'ordinal':len(self.ledger)+1,'action':name,'case_id':case_id,'reserved_cleanup':cleanup}
        with (self.directory/'actions.jsonl').open('ab') as stream:
            stream.write(json_bytes(entry));stream.flush();os.fsync(stream.fileno())
        self.ledger.append(entry)

    def artifact(self,name,value):
        raw=json_bytes(value)
        if len(raw)>16*1024*1024:raise base.StopProbe('WARM_ARTIFACT_LIMIT')
        with (self.directory/name).open('xb') as stream:stream.write(raw)
        item={'name':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
        self.artifacts.append(item)
        return item

    def verify_source(self,kind):
        sample=self.samples[kind];path=self.root/'input'/sample['reference']
        path.resolve(strict=True).relative_to((self.root/'input').resolve(strict=True))
        if sha_file(path)!=sample['sha256']:raise base.StopProbe('WARM_SOURCE_BYTES_CHANGED')

    def events(self):return read_jsonl(self.root/'temp/lvw-warm-events.jsonl',limit=16*1024*1024)

    def history(self,prompt_id,case_id):
        # Literal UUID IDs only; do not allow path construction from arbitrary
        # public response text, even when a synthetic driver is used.
        if not re.fullmatch('[0-9a-fA-F-]{1,80}',prompt_id):raise base.StopProbe('PUBLIC_PROMPT_ID_INVALID')
        deadline=time.monotonic()+480
        last=self.driver.guard_point(after=None)['monotonic_seconds']
        while time.monotonic()<deadline:
            point=self.driver.guard_point(after=last);last=point['monotonic_seconds']
            self.action('history_read',case_id)
            value=self.driver._json_request(base.COMFY_URL+'/history/'+prompt_id,
                timeout=min(5,max(.001,deadline-time.monotonic())),observer=getattr(self.driver,'resource_observer',None))[1]
            if prompt_id in value:return value
        raise base.StopProbe('PUBLIC_HISTORY_TIMEOUT')

    def one(self,case_id,kind):
        self.verify_source(kind)
        old_events=self.events()
        expected_requests=len([e for e in old_events if e.get('event')=='request_started'])
        ordinal=next(index for index,case in enumerate(FIXED_CASES,1) if case[0]==case_id)
        if expected_requests!=ordinal-1:raise base.StopProbe('WARM_EVENT_PRELUDE_CONTAMINATED')
        self.action('preload_owner_proof',case_id)
        root=self.driver.owned_listener_birth(11434)
        if (root['pid'],root['start_ticks'])!=(self.binding['ollama_pid'],self.binding['ollama_start_ticks']):
            raise base.StopProbe('PRELOAD_OWNER_CHANGED')
        self.action('model_identity_read',case_id)
        if self.driver.verify_model().get('digest')!=self.binding['model_digest']:
            raise base.StopProbe('PRELOAD_MODEL_CHANGED')
        self.action('preload',case_id)
        self.preload_owned=True
        self.driver.preload(base.MODEL)
        self.action('provider_count_read',case_id);before=self.driver.chat_log_count()
        template=ROOT/'LVW_V0_RuntimePatch/workflows'/('image_reverse_prompt_v0.api.json' if kind=='image' else 'video_reverse_prompt_v0.api.json')
        graph=json.loads(template.read_text())
        graph['1']['inputs']['image_reference' if kind=='image' else 'video_reference']=self.samples[kind]['reference']
        self.artifact(case_id+'.graph.json',graph)
        # Start at a NEW actual sampler point, never shift/fabricate a point to
        # make the first elapsed time zero or subtract public queue/cleanup time.
        point=self.driver.guard_point(after=None)
        point=self.driver.guard_point(after=point['monotonic_seconds'])
        started=point['monotonic_seconds']
        self.action('public_submit',case_id);prompt_id=self.driver.submit(graph)
        if prompt_id in self.prompt_ids:raise base.StopProbe('PUBLIC_PROMPT_ID_REUSED')
        self.prompt_ids.add(prompt_id)
        history=self.history(prompt_id,case_id)
        if history[prompt_id]['prompt'][2]!=graph:raise base.StopProbe('PUBLIC_HISTORY_GRAPH_MISMATCH')
        self.artifact(case_id+'.history.json',history)
        self.action('native_clock_read',case_id);finished=self.driver.native_clock()['monotonic_seconds']
        if finished<=started:raise base.StopProbe('NATIVE_INTERVAL_INVALID')
        self.driver.guard_point(after=finished)
        self.action('provider_count_read',case_id);after=self.driver.chat_log_count()
        if after-before!=(1 if kind=='image' else 4):raise base.StopProbe('PROVIDER_CALL_COUNT_MISMATCH')
        events=self.events()[len(old_events):]
        self.artifact(case_id+'.events.json',events)
        if not events or any(event.get('request_number')!=ordinal for event in events):
            raise base.StopProbe('WARM_REQUEST_ORDER_INVALID')
        if (events[-1].get('event')!='request_finished' or events[-1].get('outcome')!='succeeded'
                or events[-1].get('resource_release',{}).get('state')!='released'):
            raise base.StopProbe('WARM_RESTORATION_UNPROVEN')
        self.verify_source(kind)
        value=dict(run_id=self.run_id,sample_run_id=case_id,candidate_sha=self.binding['candidate_sha'],
            authorization_sha256=self.binding['authorization_sha256'],kind=kind,binding=self.binding,
            history=history,prompt_id=prompt_id,source_sha256=self.samples[kind]['sha256'],
            chat_calls_before=before,chat_calls_after=after,warm_events=events,started=started,finished=finished)
        # Persist enough to recover a failure before the terminal sampler join.
        self.artifact(case_id+'.interval.json',{k:v for k,v in value.items() if k not in {'history','warm_events'}})
        self.preload_owned=False
        return value

    def run(self):
        if self.executed:raise ValueError('warm phase is one-shot')
        self.executed=True;self.directory.mkdir(exist_ok=False)
        result={'decision':'NO_GO','stage_pass_claim':False,'run_id':self.run_id,
            'candidate_sha':self.binding['candidate_sha'],'authorization_sha256':self.binding['authorization_sha256'],
            'test_counts':{'fixed':20,'PASS':0,'FAIL':0,'NOT_RUN':20},
            'cases':{case:{'status':'NOT_RUN','kind':kind} for case,kind in FIXED_CASES},'artifacts':self.artifacts}
        records=[];active=None;error=None;stop=None;interrupted=None
        try:
            if self.events():raise base.StopProbe('WARM_EVENT_PRELUDE_CONTAMINATED')
            for case,kind in FIXED_CASES:
                active=case
                record=self.one(case,kind);records.append(record)
                result['cases'][case]['status']='COLLECTED_PENDING_ORACLE'
            active=None
        except BaseException as exc:
            error=exc
            if active is not None:result['cases'][active].update(status='FAIL',error_type=type(exc).__name__)
            result['error_code']=getattr(exc,'reason',type(exc).__name__)
        finally:
            if self.preload_owned:
                try:
                    self.action('recover_owned_preload',active,cleanup=True)
                    result['preload_recovery']=self.driver.release_preload(self.binding,self.worker)
                except BaseException as exc:
                    result['preload_recovery']={'proven':False,'error_type':type(exc).__name__}
                    if isinstance(exc,(KeyboardInterrupt,SystemExit)):interrupted=exc
            try:
                self.action('stop_sampler',active,cleanup=True)
                stop=self.worker.stop();result['sampler_cleanup']=stop
                self.artifact('resource-trace.json',self.worker.points())
                self.artifact('sampler-stop.json',stop)
                self.artifact('warm-events-final.json',self.events())
            except BaseException as exc:
                result['sampler_cleanup']={'proven':False,'error_type':type(exc).__name__}
                if isinstance(exc,(KeyboardInterrupt,SystemExit)):interrupted=exc
            try:
                if error is None:
                    if not stop or stop.get('proven') is not True:raise base.StopProbe('SAMPLER_CLEANUP_UNPROVEN')
                    points=self.worker.points();joined=[]
                    for record in records:
                        joined.append(hot_record(**record,resource_samples=points,sampler_receipt=stop['receipt']))
                    result['performance']=performance_oracle(joined,run_id=self.run_id,
                        candidate_sha=self.binding['candidate_sha'],expected_model_digest=self.binding['model_digest'])
                    self.artifact('hot-records.json',joined)
                    for entry in result['cases'].values():entry['status']='PASS'
                    result['decision']='WARM_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE'
            except BaseException as exc:
                result['error_code']=getattr(exc,'reason',type(exc).__name__)
                if isinstance(exc,(KeyboardInterrupt,SystemExit)):interrupted=exc
                # The full phase never passes if any join/oracle is incomplete.
                result['decision']='NO_GO'
            statuses=[entry['status'] for entry in result['cases'].values()]
            result['test_counts']={'fixed':20,'PASS':statuses.count('PASS'),'FAIL':statuses.count('FAIL'),
                'NOT_RUN':statuses.count('NOT_RUN'),'COLLECTED_PENDING_ORACLE':statuses.count('COLLECTED_PENDING_ORACLE')}
            result['actions']=self.ledger
            self.artifact('phase-receipt.json',copy.deepcopy(result))
        if isinstance(error,(KeyboardInterrupt,SystemExit)):raise error
        if interrupted is not None:raise interrupted
        return result
