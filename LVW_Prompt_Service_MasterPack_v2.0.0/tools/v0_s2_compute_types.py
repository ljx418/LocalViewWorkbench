"""One bounded NVIDIA XML observation under the V0 verification program."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

from tools import v0_verification_authority as auth
from tools import v0_s2_stage_checkpoint as cp
from tools.v0_s2_seal import seal_candidate
from tools.v0_s2_execution_bindings import plain
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_process import run_bounded

HARNESS='tools/v0_s2_compute_types.py'


def process_types(raw):
    if len(raw)>262144:raise ValueError('NVIDIA XML bound')
    root=ET.fromstring(raw);gpus=root.findall('gpu')
    if len(gpus)!=1:raise ValueError('single GPU required')
    rows=[]
    for p in gpus[0].findall('./processes/process_info'):
        pid=int(p.findtext('pid','0'));kind=p.findtext('type','').strip()
        if pid<=0 or kind not in {'C','G','C+G','G+C','M'}:raise ValueError('NVIDIA process type unproven')
        rows.append({'pid':pid,'type':kind})
    if len(rows)>64 or len({p['pid'] for p in rows})!=len(rows):raise ValueError('NVIDIA process set invalid')
    return rows


def run(candidate):
    program=cp.repository_json(auth.PROGRAM);auth.validate(program,'V0-S2')
    identity=seal_candidate(cp.ROOT,candidate,['tools',auth.PROGRAM,'reports/v0-s1/wp-s1-03-phase-a/live_probe.py'])
    run_id='compute-type-snapshot-01';budget={'native_nvidia_calls':1,'provider_calls':0,'media_reads':0,'browser_starts':0,'cloud_calls':0,'paid_calls':0,'downloads':0}
    child=auth.child(program,stage='V0-S2',run_id=run_id,candidate=candidate,harness_sha256=cp.file_hash(cp.ROOT/HARNESS),program_sha256=cp.file_hash(cp.ROOT/auth.PROGRAM),budget=budget,max_seconds=180)
    source=cp.STATE_ROOT/'full-profile-lifecycle-correction-01/terminal.json'
    public=cp.repository_json('reports/v0-s2/full-profile-lifecycle-correction-01/receipt.json')
    if cp.file_hash(source)!=public['raw_terminal_sha256']:raise ValueError('original tool binding changed')
    tool=json.loads(source.read_bytes())['runtime_evidence']['default']['binding_proof']['tool_bindings']['nvidia_exe']
    child.update(source_payload_sha256=identity['payload_sha256'],tool=tool,argv=[tool['path'],'-q','-x'])
    directory=cp.STATE_ROOT/run_id;directory.mkdir(exist_ok=False);cp.write_new(directory/'active-child.json',child)
    (directory/'lease.closed').write_bytes(b'0')
    result={'run_id':run_id,'candidate_sha':candidate,'decision':'NO_GO','stage_pass_claim':False,**budget}
    try:
        if cp.file_hash(plain(Path(tool['path'])))!=tool['sha256']:raise ValueError('NVIDIA binary changed')
        if time.time()>=child['expires_at'] or cp.file_hash(cp.ROOT/auth.PROGRAM)!=child['program_sha256']:raise ValueError('child changed or expired')
        def record(p):
            result['exit_code']=p.returncode
            for stream,data in [('stdout',p.stdout),('stderr',p.stderr)]:
                (directory/(stream+'.log')).write_bytes(data);result[stream+'_sha256']=hashlib.sha256(data).hexdigest()
        output=run_bounded(child['argv'],timeout_seconds=15,output_limit=262144,on_result=record)
        result['processes']=process_types(output.stdout)
        result['decision']='COMPUTE_TYPE_OBSERVED_NOT_PRODUCT_ACCEPTANCE'
    except Exception as error:result['raw_error']=type(error).__name__+':'+str(error)
    finally:
        cp.write_new(directory/'terminal.json',result);(directory/'lease.closed').write_bytes(b'1')
        cp.write_new(directory/'terminal-child.json',auth.expire(child,'COMPLETE' if result['decision'].startswith('COMPUTE_TYPE') else 'NO_GO','terminal.json'))
        counts={}
        for row in result.get('processes',[]):counts[row['type']]=counts.get(row['type'],0)+1
        receipt={'run_id':run_id,'candidate_sha':candidate,'decision':result['decision'],'types':counts,'provider_calls':0,'media_reads':0,'service_starts':0,'stage_pass_claim':False,'raw_terminal_sha256':cp.file_hash(directory/'terminal.json')}
        report=cp.ROOT/'reports/v0-s2'/run_id;report.mkdir(exist_ok=False);cp.write_new(report/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);args=p.parse_args()
    print(json.dumps(run(args.candidate)))
