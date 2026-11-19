"""One identity-bound CPU decoder integration run; never a Stage checkpoint."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from tools.v0_s2_bindings import ROOT,SOURCE,file_hash
from tools.v0_s2_seal import seal_candidate


PAYLOAD=['LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge',
         'tools/v0_s2_decoder_probe.py','tools/v0_s2_seal.py','tools/v0_s2_bindings.py']
DECODERS={'ffmpeg':Path('/usr/bin/ffmpeg'),'ffprobe':Path('/usr/bin/ffprobe')}
BUDGET={'video_decodes':1,'ffprobe_calls':1,'ffmpeg_calls':4,'provider_calls':0,
        'service_starts':0,'gpu_probes':0,'browser_runs':0,'downloads':0,'cloud_calls':0,'stage_checkpoints':0}


def authority(auth,program):
    if (program.get('status')!='ACTIVE' or program.get('authorization_id')!='AUTH-PROGRAM-V1-LOCAL-01'
            or 'V0-S2' not in program.get('stages',[])
            or auth.get('source_program_authorization')!=program['authorization_id']
            or auth.get('status')!='ACTIVE_ONE_SHOT' or auth.get('stage_id')!='V0-S2'
            or auth.get('scope')!='CPU_DECODER_INTEGRATION_ONLY' or auth.get('budget')!=BUDGET
            or not re.fullmatch(r'cpu-decoder-[0-9]{2}',auth.get('run_id',''))
            or not re.fullmatch('[0-9a-f]{64}',auth.get('sample_sha256',''))):
        raise ValueError('CPU_PROBE_AUTHORITY_MISMATCH')


def execute(auth_path):
    auth_path=ROOT/auth_path;auth=json.loads(auth_path.read_text())
    program_path=ROOT/'reports/authorization-program-v1-local-01.json'
    program=json.loads(program_path.read_text());authority(auth,program)
    if file_hash(program_path)!=auth.get('program_sha256'):raise ValueError('PROGRAM_HASH_MISMATCH')
    # Identity checks precede all media/executable access.
    sealed=seal_candidate(ROOT,auth['candidate_sha'],PAYLOAD)
    if file_hash(__file__)!=auth['harness_sha256']:raise ValueError('HARNESS_HASH_MISMATCH')
    directory=ROOT/'reports/v0-s2'/auth['run_id'];directory.mkdir(exist_ok=False)
    result={'schema_version':'lvw.s2.cpu-decoder-probe/1','run_id':auth['run_id'],
            'authorization_id':auth['authorization_id'],'candidate_sha':auth['candidate_sha'],
            'payload_sha256':sealed['payload_sha256'],'decision':'NO_GO','stage_pass_claim':False,
            'stage_checkpoint_consumed':False,'provider_calls':0,'service_starts':0,'commands':[]}
    run_root=None
    try:
        executable_hashes={name:file_hash(path) for name,path in DECODERS.items()}
        if 'executable_sha256' in auth and executable_hashes!=auth['executable_sha256']:
            raise ValueError('DECODER_HASH_MISMATCH')
        # The child explicitly permits these two read-only metadata bindings.
        # Persist them before any media decode process may be created.
        auth['executable_sha256']=executable_hashes
        auth_path.write_text(json.dumps(auth,indent=2)+'\n')
        result['executable_sha256']=executable_hashes
        candidates=[]
        for index,path in enumerate(SOURCE.rglob('*')):
            if index>=4096:raise ValueError('SOURCE_CATALOG_LIMIT')
            if path.suffix.lower() in {'.mp4','.mov'}:candidates.append(path)
        source=sorted(candidates)[0]
        if source.is_symlink() or source.stat().st_size!=auth['sample_bytes'] or file_hash(source)!=auth['sample_sha256']:
            raise ValueError('SAMPLE_BINDING_MISMATCH')
        source.resolve(strict=True).relative_to(SOURCE.resolve(strict=True))
        run_root=Path(tempfile.mkdtemp(prefix='lvw-s2-cpu-',dir=ROOT/'reports/v0-s2'))
        inputs=run_root/'input';inputs.mkdir();temporary=run_root/'temp';temporary.mkdir()
        reference='authorized'+source.suffix.lower();shutil.copyfile(source,inputs/reference)
        if file_hash(inputs/reference)!=auth['sample_sha256']:raise ValueError('STAGED_SAMPLE_MISMATCH')
        from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_decoder import VideoDecoder
        from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_process import run_bounded
        def runner(argv,**kwargs):
            kind=next((name for name,path in DECODERS.items() if argv[0]==str(path)),None)
            if kind is None or sum(item['kind']==kind for item in result['commands'])>=BUDGET[kind+'_calls']:
                raise ValueError('DECODER_PROCESS_BUDGET_EXCEEDED')
            if file_hash(DECODERS[kind])!=auth['executable_sha256'][kind]:
                raise ValueError('DECODER_HASH_CHANGED_BEFORE_EXECUTION')
            entry={'kind':kind,'argv':[arg.replace(str(run_root),'RUN_TEMP') for arg in argv]}
            result['commands'].append(entry)
            value=run_bounded(argv,**kwargs)
            entry.update(exit_code=value.returncode,stdout_sha256=hashlib.sha256(value.stdout).hexdigest(),
                         stderr_sha256=hashlib.sha256(value.stderr).hexdigest(),
                         stderr=value.stderr.decode('utf-8','replace').replace(str(run_root),'RUN_TEMP')[:16384])
            return value
        decoded=VideoDecoder(input_root=inputs,temp_parent=temporary,ffprobe=DECODERS['ffprobe'],ffmpeg=DECODERS['ffmpeg'],runner=runner).decode(reference)
        if decoded.source_sha256!=auth['sample_sha256'] or len(decoded.frames)!=4 or list(temporary.iterdir()):
            raise ValueError('DECODE_OR_CLEANUP_ORACLE_FAILED')
        result.update(decision='CPU_DECODE_VERIFIED_NOT_STAGE_ACCEPTANCE',frames=decoded.manifest,
                      source_sha256=decoded.source_sha256,duration_seconds=decoded.duration_seconds)
    except Exception as exc:
        result['error_code']=getattr(exc,'code',str(exc) if isinstance(exc,ValueError) else type(exc).__name__)
        details=getattr(exc,'details',{})
        if details.get('subcode'):result['error_subcode']=details['subcode']
    finally:
        try:
            if run_root is not None:shutil.rmtree(run_root)
            result['cleanup_proven']=run_root is None or not run_root.exists()
        except OSError:
            result.update(cleanup_proven=False,decision='NO_GO',error_code='CPU_TEMP_CLEANUP_FAILED')
        result['finished_at']=datetime.now(timezone.utc).isoformat()
        (directory/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
        auth.update(status='EXPIRED_'+result['decision'],terminal_receipt=str((directory/'receipt.json').relative_to(ROOT)))
        auth_path.write_text(json.dumps(auth,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',required=True)
    parser.add_argument('--execute-cpu-probe',action='store_true');args=parser.parse_args()
    if not args.execute_cpu_probe:parser.error('explicit CPU probe flag required')
    value=execute(args.authorization)
    print(json.dumps({key:value[key] for key in ('decision','cleanup_proven','stage_checkpoint_consumed')}))
    raise SystemExit(0 if value['decision']=='CPU_DECODE_VERIFIED_NOT_STAGE_ACCEPTANCE' else 1)
