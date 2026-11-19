"""One public native Comfy decoder component run, no inference or Stage PASS."""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

from tools.v0_s2_bindings import ROOT,SOURCE,TARGETS,file_hash,native_package_inventory
from tools.v0_s2_driver import S2SystemDriver,base
from tools.v0_s2_seal import seal_candidate

PAYLOAD=['LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge','tools/v0_s2_native_component.py',
         'tools/v0_s2_driver.py','tools/v0_s2_http.py','tools/v0_s2_bindings.py','tools/v0_s2_seal.py',
         'reports/v0-s1/wp-s1-03-phase-a/live_probe.py']
BUDGET={'comfy_starts':1,'ollama_starts':0,'public_submissions':1,'loopback_requests':1024,
        'video_decodes':1,'metadata_probe_processes':1,'frame_decoder_processes':4,
        'native_package_snapshots':2,'nvidia_smi_queries':3,'provider_calls':0,
        'browser_runs':0,'downloads':0,'cloud_calls':0,'stage_checkpoints':0}


def authority(auth,program):
    if (program.get('status')!='ACTIVE' or program.get('authorization_id')!='AUTH-PROGRAM-V1-LOCAL-01'
            or 'V0-S2' not in program.get('stages',[]) or auth.get('source_program_authorization')!=program['authorization_id']
            or auth.get('status')!='ACTIVE_ONE_SHOT' or auth.get('stage_id')!='V0-S2'
            or auth.get('scope')!='NATIVE_PUBLIC_DECODER_COMPONENT_ONLY' or auth.get('budget')!=BUDGET
            or auth.get('run_id') not in {'native-component-01','native-component-02'}
            or auth.get('ports')!=[8191,11434]):raise ValueError('NATIVE_COMPONENT_AUTHORITY_MISMATCH')


def metadata_oracle(value,*,sample_sha256,sample_bytes):
    if (value.get('source_sha256')!=sample_sha256 or value.get('bytes')!=sample_bytes
            or value.get('decoder_backend')!='ffmpeg-cli/pyav-probe' or len(value.get('frames',[]))!=4):
        raise ValueError('NATIVE_COMPONENT_SOURCE_OR_BACKEND_MISMATCH')
    duration=value.get('duration_seconds')
    if type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=60:
        raise ValueError('NATIVE_COMPONENT_DURATION_INVALID')
    previous=None;origin=None;basis=None
    for index,frame in enumerate(value['frames']):
        if frame.get('index')!=index or type(frame.get('index')) is not int:
            raise ValueError('NATIVE_COMPONENT_FRAME_INDEX_INVALID')
        if any(type(frame.get(key)) is not int for key in ('pts','time_base_num','time_base_den')):
            raise ValueError('NATIVE_COMPONENT_PTS_INVALID')
        if min(frame['time_base_num'],frame['time_base_den'])<=0:raise ValueError('NATIVE_COMPONENT_TIMEBASE_INVALID')
        current_basis=Fraction(frame['time_base_num'],frame['time_base_den']);seconds=frame.get('time_seconds')
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not duration*(2*index+1)/8<=seconds<=duration:
            raise ValueError('NATIVE_COMPONENT_SAMPLE_WINDOW_INVALID')
        current_origin=frame['pts']*current_basis-Fraction(str(seconds))
        if (previous is not None and frame['pts']<=previous) or (basis is not None and basis!=current_basis):
            raise ValueError('NATIVE_COMPONENT_TIMELINE_INVALID')
        if origin is not None and abs(float(current_origin-origin))>1e-9:raise ValueError('NATIVE_COMPONENT_ORIGIN_INVALID')
        if not re.fullmatch('[0-9a-f]{64}',frame.get('sha256','')):raise ValueError('NATIVE_COMPONENT_FRAME_HASH_INVALID')
        previous=frame['pts'];origin=current_origin;basis=current_basis
    return {'frame_count':4,'source_sha256':sample_sha256,'decoder_backend':value['decoder_backend'],
            'duration_seconds':duration,'frames':value['frames'],'stage_pass_claim':False}


def package_map(snapshot):return {item['alias']:(item['sha256'],item['bytes']) for item in snapshot['files']}


def execute(auth_relative):
    auth_path=ROOT/auth_relative;auth=json.loads(auth_path.read_text())
    program_path=ROOT/'reports/authorization-program-v1-local-01.json'
    program=json.loads(program_path.read_text());authority(auth,program)
    if file_hash(program_path)!=auth['program_sha256']:raise ValueError('PROGRAM_HASH_MISMATCH')
    directory=ROOT/'reports/v0-s2'/auth['run_id'];directory.mkdir(exist_ok=False)
    result={'schema_version':'lvw.s2.native-component/1','run_id':auth['run_id'],'candidate_sha':auth['candidate_sha'],
        'authorization_id':auth['authorization_id'],'decision':'NO_GO','stage_pass_claim':False,
        'stage_checkpoint_consumed':False,'provider_calls':0,'service_starts':0,'public_submissions':0,
        'product_cases':{key:'NOT_RUN' for key in ('V0-A02','V0-A07','V0-A09','V0-A10')}}
    run_root=None;driver=None;aliases={str(ROOT):'PACK_ROOT',str(SOURCE):'TEST_SOURCE'}
    try:
        identity=seal_candidate(ROOT,auth['candidate_sha'],PAYLOAD)
        if file_hash(__file__)!=auth['harness_sha256']:raise ValueError('HARNESS_HASH_MISMATCH')
        result['identity']=identity
        offline_path=ROOT/auth['offline_receipt']
        if file_hash(offline_path)!=auth['offline_receipt_sha256']:raise ValueError('OFFLINE_RECEIPT_HASH_MISMATCH')
        offline=json.loads(offline_path.read_text())
        if offline['decision']!='OFFLINE_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE':raise ValueError('OFFLINE_GATE_NOT_PASSED')
        for path,digest in identity['execution_artifact_sha256'].items():
            if offline['identity']['execution_artifact_sha256'].get(path)!=digest:
                raise ValueError('CURRENT_PAYLOAD_NOT_COVERED_BY_OFFLINE_GATE')
        package_path=ROOT/auth['package_receipt']
        if file_hash(package_path)!=auth['package_receipt_sha256']:raise ValueError('PACKAGE_RECEIPT_HASH_MISMATCH')
        expected=json.loads(package_path.read_text())['native_decoder_packages']
        current=native_package_inventory(TARGETS['COMFY_PYTHON'].parent)
        if package_map(expected)!=package_map(current):raise ValueError('NATIVE_PACKAGE_BYTES_CHANGED')
        for key in ('COMFY_MAIN','COMFY_PYTHON'):
            if file_hash(TARGETS[key])!=auth['target_sha256'][key]:raise ValueError('TARGET_IDENTITY_MISMATCH')
        binary_alias=auth['ffmpeg_alias']
        if binary_alias not in package_map(expected) or not binary_alias.startswith('COMFY_PYTHON_HOME/'):
            raise ValueError('FFMPEG_BINDING_INVALID')
        ffmpeg=TARGETS['COMFY_PYTHON'].parent/binary_alias.removeprefix('COMFY_PYTHON_HOME/')
        candidates=[]
        for index,path in enumerate(SOURCE.rglob('*')):
            if index>=4096:raise ValueError('SOURCE_CATALOG_LIMIT')
            if path.suffix.lower() in {'.mp4','.mov'}:candidates.append(path)
        sample=sorted(candidates)[0]
        sample.resolve(strict=True).relative_to(SOURCE.resolve(strict=True))
        if sample.is_symlink() or sample.stat().st_size!=auth['sample_bytes'] or file_hash(sample)!=auth['sample_sha256']:
            raise ValueError('SAMPLE_BINDING_MISMATCH')
        run_root=Path(tempfile.mkdtemp(prefix='lvw-s2-native-',dir=ROOT/'reports/v0-s2'))
        aliases[str(run_root)]='RUN_TEMP'
        for name in ('input','output','temp','custom_nodes'):(run_root/name).mkdir()
        shutil.copytree(ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge',run_root/'custom_nodes/lvw_v0_bridge',
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for relative,digest in identity['execution_artifact_sha256'].items():
            prefix='LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'
            if relative.startswith(prefix) and file_hash(run_root/'custom_nodes/lvw_v0_bridge'/relative.removeprefix(prefix))!=digest:
                raise ValueError('DEPLOYED_PAYLOAD_BYTES_MISMATCH')
        reference='authorized'+sample.suffix.lower();shutil.copyfile(sample,run_root/'input'/reference)
        if file_hash(run_root/'input'/reference)!=auth['sample_sha256']:raise ValueError('STAGED_SAMPLE_MISMATCH')
        args=SimpleNamespace(powershell='powershell.exe',run_id=auth['run_id'],max_public_submissions=1,max_loopback_requests=1024,
            comfy_main=str(TARGETS['COMFY_MAIN']),comfy_python=str(TARGETS['COMFY_PYTHON']),ffmpeg_exe=str(ffmpeg),ffprobe_exe=None)
        driver=S2SystemDriver(args,result)
        result['preflight']=driver.preflight()
        result['preflight']['available_ram_mib']=int(driver._powershell('(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'))//1024
        if result['preflight']['available_ram_mib']<2048:raise ValueError('HOST_RAM_BELOW_LIMIT')
        result['comfy_start_attempts']=1
        driver.start_comfy(run_root,run_root/'comfy.log')
        result['service_starts']=1
        result['ownership']=driver.ownership_summary()
        registry=driver.registry()
        if 'LVWControlledVideoInput' not in registry:raise ValueError('PUBLIC_INPUT_NODE_MISSING')
        graph={'1':{'class_type':'LVWControlledVideoInput','inputs':{'video_reference':reference}}}
        prompt_id=driver.submit(graph);result['public_submissions']=driver.submissions
        history=driver.history(prompt_id);text=base.workflow_oracle(history,prompt_id,'1')
        if len(text)!=1:raise ValueError('PUBLIC_COMPONENT_METADATA_MISSING')
        metadata=json.loads(text[0]);result['component_oracle']=metadata_oracle(metadata,
            sample_sha256=auth['sample_sha256'],sample_bytes=auth['sample_bytes'])
        result['public_trace']={'prompt_id':prompt_id,'graph':graph,'metadata':metadata}
        result['runtime_guard']=driver.runtime_guard()
        if package_map(native_package_inventory(TARGETS['COMFY_PYTHON'].parent))!=package_map(expected):
            raise ValueError('NATIVE_PACKAGE_BYTES_CHANGED_DURING_RUN')
        if seal_candidate(ROOT,auth['candidate_sha'],PAYLOAD)!=identity:raise ValueError('PAYLOAD_CHANGED_DURING_RUN')
        result['decision']='NATIVE_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE'
    except Exception as exc:
        result['error_code']=getattr(exc,'reason',str(exc) if isinstance(exc,ValueError) else type(exc).__name__)
    finally:
        cleanup={'proven':driver is None}
        if driver is not None:
            try:cleanup=driver.cleanup() if driver.owned else {'proven':True,'owned_count':0}
            except Exception as exc:cleanup={'proven':False,'error_type':type(exc).__name__}
            result['request_ledger']=driver.request_ledger
        if run_root is not None:
            log=run_root/'comfy.log'
            if log.exists():(directory/'comfy.redacted.log').write_text(base.redact(log.read_text(encoding='utf-8',errors='replace'),aliases))
            if cleanup.get('proven'):
                try:shutil.rmtree(run_root)
                except OSError:cleanup['proven']=False
            cleanup['run_temp_absent']=not run_root.exists()
            if not cleanup['run_temp_absent']:cleanup['retained_run_temp']=str(run_root.relative_to(ROOT))
        result['cleanup']=cleanup
        if not cleanup.get('proven'):result['decision']='NO_GO'
        result['finished_at']=datetime.now(timezone.utc).isoformat()
        result=base.redact_value(result,aliases)
        (directory/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
        auth.update(status='EXPIRED_'+result['decision'],terminal_receipt=str((directory/'receipt.json').relative_to(ROOT)))
        auth_path.write_text(json.dumps(auth,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',required=True)
    parser.add_argument('--execute-native-component',action='store_true');args=parser.parse_args()
    if not args.execute_native_component:parser.error('explicit native component flag required')
    value=execute(args.authorization)
    print(json.dumps({key:value[key] for key in ('decision','stage_pass_claim','stage_checkpoint_consumed')}))
    raise SystemExit(0 if value['decision']=='NATIVE_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE' else 1)
