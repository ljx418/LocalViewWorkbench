"""Recompute cancellation facts from native owner/transport events and raw logs.

Does not attest browser drafts, final process cleanup or a Stage decision.
Connection close is deliberately never treated as a GPU-stop witness.
"""
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import valid_baseline
import hashlib
import math

from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.benchmark import validate_lineage
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_evidence import validate_binding


def number(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('invalid time/metric')
    return value


def count(snapshot):
    raw=snapshot['raw_log'].encode('utf-8')
    if raw and not raw.endswith(b'\n'):raise ValueError('incomplete provider prefix')
    observed=sum('POST' in line and '"/api/chat"' in line for line in snapshot['raw_log'].splitlines())
    if (len(raw)!=snapshot['source_log_bytes'] or hashlib.sha256(raw).hexdigest()!=snapshot['source_log_sha256']
            or type(snapshot['chat_calls']) is not int or snapshot['chat_calls']!=observed):raise ValueError('provider prefix invalid')
    return observed


def cancellation_trace(events,*,binding,token,owner_pid,kind,ack,before,after,resource_samples):
    try:
        if kind not in ('preparation','provider') or not isinstance(events,list) or not 3<=len(events)<=1024:raise ValueError('trace required')
        validate_binding(binding,binding['issued_at'])
        if type(owner_pid) is not int or owner_pid<=0:raise ValueError('native owner required')
        allowed={'run_started','source_prepared','gpu_admission_started','gpu_admission_completed','provider_attempt',
            'provider_owner_verified','provider_request_sent','provider_response','provider_connection_closed',
            'release_owner_verified','unload_acknowledged','model_inventory_empty','physical_release','cancel_accepted','run_finished'}
        previous=None
        for event in events:
            if event['event'] not in allowed:raise ValueError('unfrozen native event')
            t=number(event['monotonic_seconds']);number(event['wall_seconds'])
            if (event['candidate_sha']!=binding['candidate_sha'] or event['authorization_sha256']!=binding['authorization_sha256']
                    or event['run_token']!=token or type(event['owner_pid']) is not int or event['owner_pid']!=owner_pid
                    or type(event['run_number']) is not int or not 1<=event['run_number']<=binding['max_runs']
                    or event['run_number']!=events[0]['run_number'] or (previous is not None and t<previous)):
                raise ValueError('cross-run, owner or time mismatch')
            if event['event'] in ('run_started','provider_attempt','provider_owner_verified','provider_request_sent'):
                if not binding['issued_at']<=event['wall_seconds']<binding['expires_at']:raise ValueError('new work outside lease')
            if 'root_proof' in event:
                proof=event['root_proof']
                if proof['verified_compute_pids']!=[]:raise ValueError('ownership scope mismatch')
                validate_lineage(proof['snapshot'],binding,[],owner_pid)
            elif event['event'] in ('provider_attempt','provider_owner_verified','release_owner_verified'):
                raise ValueError('ownership proof missing')
            previous=t
        names=[event['event'] for event in events]
        if names[0]!='run_started' or names[-1]!='run_finished' or names.count('run_started')!=1 or names.count('run_finished')!=1:
            raise ValueError('terminal denominator')
        terminal=events[-1]
        if (terminal['status']!='cancelled' or terminal['resource_state']!='released' or terminal['error_code']!='JOB_CANCELLED'
                or terminal['cancel_epoch']!=1 or type(terminal['cancel_epoch']) is not int or terminal['result_published'] is not False):
            raise ValueError('cancel not safely terminal')
        accepted=[e for e in events if e['event']=='cancel_accepted']
        if len(accepted)!=1 or accepted[0]['cancel_epoch']!=1:raise ValueError('cancel acknowledgement event missing')
        requested=number(accepted[0]['observed_monotonic_seconds'])
        if not events[0]['monotonic_seconds']<=requested<=accepted[0]['monotonic_seconds']:raise ValueError('cancel time fabricated')
        response=ack['response'];elapsed=number(ack['elapsed_seconds'])
        if (ack['http_status']!=200 or elapsed>1 or response['run_token']!=token or response['cancel_epoch']!=1
                or response['status']!='cancelling' or response['resource_state']!='releasing'):
            raise ValueError('cancel feedback not proven')
        calls=count(after)-count(before)
        if not after['raw_log'].startswith(before['raw_log']):raise ValueError('provider log replaced')
        attempts=[e for e in events if e['event']=='provider_attempt'];sent=[e for e in events if e['event']=='provider_request_sent']
        if terminal['provider_attempts']!=len(attempts) or type(terminal['provider_attempts']) is not int:raise ValueError('attempt denominator')
        result={'kind':'CANCELLATION_TRACE_VERIFIED_NOT_STAGE_ACCEPTANCE','stage_pass_claim':False,
            'cancel_feedback_seconds':elapsed,'provider_calls':calls,'result_published':False,
            'remaining_obligations':['browser_draft_safety','final_owned_process_and_temp_cleanup','privacy','independent_review']}
        if kind=='preparation':
            if attempts or sent or calls!=0 or 'gpu_admission_started' in names or terminal['resource_release'].get('state')!='not_requested':
                raise ValueError('preparation cancellation entered inference')
            return result
        if not 1<=calls==len(sent)<=len(attempts)<=4:raise ValueError('real provider cancellation not reached')
        if [e['call_index'] for e in attempts]!=list(range(len(attempts))):raise ValueError('attempt identities invalid')
        if len({e['call_index'] for e in sent})!=len(sent):raise ValueError('duplicate provider send')
        active=[]
        for event in sent:
            index=event['call_index']
            if type(index) is not int or not 0<=index<len(attempts):raise ValueError('provider attempt missing')
            verified=[e for e in events if e['event']=='provider_owner_verified' and e.get('call_index')==index]
            if (len(verified)!=1 or not attempts[index]['monotonic_seconds']<=verified[0]['monotonic_seconds']<=event['monotonic_seconds']):
                raise ValueError('pre-send owner verification missing')
            closed=[e for e in events if e['event']=='provider_connection_closed' and e.get('call_index')==index]
            if len(closed)!=1:raise ValueError('owned connection terminal missing')
            if event['monotonic_seconds']<=requested<=closed[0]['monotonic_seconds']:active.append((index,closed[0]))
        if len(active)!=1:raise ValueError('cancel not within exactly one active provider window')
        index,closed=active[0]
        empty=[e for e in events if e['event']=='model_inventory_empty' and e.get('call_index')==index]
        released=[e for e in events if e['event']=='physical_release' and e.get('call_index')==index]
        unload=[e for e in events if e['event']=='unload_acknowledged' and e.get('call_index')==index]
        if len(empty)!=1 or len(released)!=1 or len(unload)!=1 or unload[0]['response'].get('done') is not True or empty[0]['api_ps'].get('models')!=[]:
            raise ValueError('model stop/release witnesses missing')
        controls=[e for e in events if e['event']=='release_owner_verified'
                  and closed['monotonic_seconds']<=e['monotonic_seconds']<=unload[0]['monotonic_seconds']]
        if not controls:raise ValueError('unload owner verification missing')
        stop=number(empty[0]['observed_monotonic_seconds']);finished=number(released[0]['monotonic_seconds'])
        release=released[0]['release'];baseline=release['baseline_gpu_mib'];start=number(release['started_monotonic_seconds'])
        if (not closed['monotonic_seconds']<=start<=unload[0]['monotonic_seconds']<=stop<=finished<=terminal['monotonic_seconds']
                or not stop<=empty[0]['monotonic_seconds']<=finished
                or release['state']!='released' or release['loaded_models']!=0 or release['model_inventory_empty_monotonic']!=stop
                or type(baseline) is not int or not valid_baseline(baseline) or finished-requested>30
                or number(release['elapsed_seconds'])>30 or abs(start+release['elapsed_seconds']-finished)>1e-6
                or terminal['resource_release']!=release):raise ValueError('physical release origin/deadline mismatch')
        samples=release['gpu_samples']
        if not isinstance(samples,list) or not 3<=len(samples)<=31:raise ValueError('physical samples missing')
        last=None
        for sample in samples:
            t=number(sample['elapsed_seconds']);used=sample['gpu_used_mib']
            if type(used) is not int or used<0 or t>release['elapsed_seconds'] or (last is not None and t-last<1-1e-6):
                raise ValueError('physical cadence invalid')
            last=t
        if abs(last-release['elapsed_seconds'])>1e-6 or any(s['gpu_used_mib']>baseline+1024 for s in samples[-3:]):raise ValueError('stability incomplete')
        lower=start+samples[-3]['elapsed_seconds'];previous=None
        for sample in resource_samples:
            observed=number(sample['monotonic_seconds'])
            if previous is not None and observed-previous<1-1e-6:raise ValueError('independent cadence invalid')
            previous=observed
        stable=[s for s in resource_samples if lower<=s['monotonic_seconds']<=finished]
        if len(stable)<2 or any(type(s['gpu_used_mib']) is not int or not 0<=s['gpu_used_mib']<=baseline+1024 for s in stable):
            raise ValueError('independent sampler disagrees')
        result.update(model_stop_confirmed_monotonic=stop,physical_release_monotonic=finished,
            release_from_cancel_seconds=finished-requested,stop_witness='owned_unload_ack_and_empty_inventory',
            actual_gpu_kernel_stop_timestamp_claimed=False)
        return result
    except (KeyError,TypeError,ValueError,IndexError,BridgeError) as error:
        raise EvidenceError('native cancellation trace invalid: '+type(error).__name__) from error
