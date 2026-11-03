"""Recompute deliberate owned-provider death; never claim in-process recovery."""
import re
from tools.v0_s2_cancel_evidence import number,count
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.benchmark import validate_lineage
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_evidence import validate_binding


def fault_trace(events,*,binding,owner_pid,token,before,after,stop,clocks,resource_samples,baseline_gpu_mib):
    try:
        validate_binding(binding,binding['issued_at'])
        if (type(owner_pid) is not int or owner_pid<=0 or type(baseline_gpu_mib) is not int
                or not 0<=baseline_gpu_mib<=4096 or not isinstance(events,list) or not 5<=len(events)<=1024):raise ValueError()
        previous=None
        allowed={'run_started','source_prepared','gpu_admission_started','gpu_admission_completed','provider_attempt',
            'provider_owner_verified','provider_request_sent','provider_response','provider_connection_closed',
            'release_owner_verified','unload_acknowledged','model_inventory_empty','physical_release','run_finished'}
        for event in events:
            if event['event'] not in allowed:raise ValueError('unfrozen fault event')
            t=number(event['monotonic_seconds']);wall=number(event['wall_seconds'])
            if (event['candidate_sha']!=binding['candidate_sha'] or event['authorization_sha256']!=binding['authorization_sha256']
                    or event['owner_pid']!=owner_pid or event['run_token']!=token
                    or type(event['run_number']) is not int or not 1<=event['run_number']<=binding['max_runs']
                    or event['run_number']!=events[0]['run_number'] or (previous is not None and t<previous)):
                raise ValueError('cross-run fault evidence')
            if event['event'] in ('run_started','provider_attempt','provider_owner_verified','provider_request_sent'):
                if not binding['issued_at']<=wall<binding['expires_at']:raise ValueError('expired new work')
            if event['event'] in ('provider_attempt','provider_owner_verified','release_owner_verified'):
                proof=event['root_proof']
                if proof['verified_compute_pids']!=[]:raise ValueError('unfrozen proof scope')
                validate_lineage(proof['snapshot'],binding,[],owner_pid)
            if event['event']=='provider_attempt' and not re.fullmatch('[0-9a-f]{64}',event['payload_sha256']):raise ValueError('payload hash missing')
            previous=t
        names=[e['event'] for e in events];terminal=events[-1]
        if (names[0]!='run_started' or names[-1]!='run_finished' or names.count('run_started')!=1 or names.count('run_finished')!=1
                or 'cancel_accepted' in names or terminal['status']!='failed' or terminal['resource_state']!='unknown'
                or terminal['error_code'] not in ('MODEL_UNAVAILABLE','PARSE_PARTIAL','RESOURCE_RELEASE_PENDING')
                or terminal['result_published'] is not False or type(terminal['cancel_epoch']) is not int or terminal['cancel_epoch']!=0):
            raise ValueError('fault must fail closed without publishing/recovering')
        root=stop['root_stop']
        if (stop['port']!=11434 or stop['owned_listener_pid']!=binding['ollama_pid'] or stop['lineage_reproven'] is not True
                or stop['terminal_absent'] is not True or stop['unknown_descendants_absent'] is not True
                or root['pid']!=binding['ollama_pid'] or root['state']!='STOPPED' or root['termination_requested'] is not True
                or root['original_absent'] is not True or type(root['target_start_ticks']) is not int
                or not 0<=root['target_start_ticks']-binding['ollama_start_ticks']<10):raise ValueError('owned root stop not proven')
        children=stop['descendants_before_stop'];states=stop['descendant_terminal_states']
        if len(children)>16 or len(states)!=len(children) or len({v['pid'] for v in children})!=len(children):raise ValueError('child denominator')
        expected={v['pid']:v['process_start_ticks'] for v in children}
        if (len({v['pid'] for v in states})!=len(states) or any(v['pid'] not in expected or v['target_start_ticks']!=expected[v['pid']]
                or v['original_absent'] is not True or v['state'] not in ('STOPPED','ABSENT','REPLACED') for v in states)):
            raise ValueError('owned child exit missing')
        requested=number(root['stop_requested_wall_seconds']);confirmed=number(root['exit_confirmed_wall_seconds'])
        start=number(clocks['before']['monotonic_seconds']);end=number(clocks['after']['monotonic_seconds'])
        if (end<start or not number(clocks['before']['wall_seconds'])<=requested<=confirmed<=number(clocks['after']['wall_seconds'])):
            raise ValueError('fault clock bracket invalid')
        attempts=[e for e in events if e['event']=='provider_attempt'];sent=[e for e in events if e['event']=='provider_request_sent']
        if (not 1<=len(sent)<=len(attempts)<=4 or terminal['provider_attempts']!=len(attempts)
                or [e['call_index'] for e in attempts]!=list(range(len(attempts))) or len({e['call_index'] for e in sent})!=len(sent)):
            raise ValueError('provider denominator')
        active=[]
        for event in sent:
            i=event['call_index'];verified=[e for e in events if e['event']=='provider_owner_verified' and e.get('call_index')==i]
            closed=[e for e in events if e['event']=='provider_connection_closed' and e.get('call_index')==i]
            if (type(i) is not int or not 0<=i<len(attempts) or len(verified)!=1 or len(closed)!=1
                    or not attempts[i]['monotonic_seconds']<=verified[0]['monotonic_seconds']<=event['monotonic_seconds']<=closed[0]['monotonic_seconds']):
                raise ValueError('owned request path missing')
            if event['wall_seconds']<=requested<=closed[0]['wall_seconds']:
                if any(e['event']=='provider_response' and e.get('call_index')==i for e in events):raise ValueError('completed response is not interrupted')
                active.append(i)
        if len(active)!=1:raise ValueError('root not stopped within one active call')
        delta=count(after)-count(before)
        # A killed server may never flush the final GIN line. Keep its actual
        # prefix; prove the interrupted send using native events and root stop.
        if not after['raw_log'].startswith(before['raw_log']) or not len(sent)-1<=delta<=len(sent):raise ValueError('provider log inconsistent')
        previous=None;stable=[];witness=None
        for sample in resource_samples:
            t=number(sample['monotonic_seconds']);gpu=sample['gpu_used_mib'];ram=sample['available_ram_mib']
            if (type(gpu) is not int or not 0<=gpu<23552 or type(ram) is not int or ram<2048
                    or (previous is not None and not 1-1e-6<=t-previous<=1.5)
                    or set(sample['private_bytes'])!={str(owner_pid)} or any(type(v) is not int or v<0 for v in sample['private_bytes'].values())):
                raise ValueError('fault-only sampler invalid')
            if t>=end:stable=stable+[sample] if gpu<=baseline_gpu_mib+1024 else []
            if len(stable)>=3 and witness is None:witness=t
            previous=t
        if witness is None or witness-start>30:raise ValueError('release after owned stop unproven')
        return {'kind':'FAULT_TRACE_VERIFIED_NOT_STAGE_ACCEPTANCE','stage_pass_claim':False,'provider_sends':len(sent),
            'completed_provider_log_delta':delta,'interrupted_call_index':active[0],'in_process_quarantine':True,
            'physical_release_monotonic':witness,'release_from_stop_bracket_seconds':witness-start,
            'exact_kernel_stop_timestamp_claimed':False,'remaining_obligations':['manual_offline','adopt_rejection','quarantine_entry','browser','final_cleanup','independent_review']}
    except (KeyError,TypeError,ValueError,IndexError,BridgeError) as error:
        raise EvidenceError('native owned-provider fault trace invalid: '+type(error).__name__) from error
