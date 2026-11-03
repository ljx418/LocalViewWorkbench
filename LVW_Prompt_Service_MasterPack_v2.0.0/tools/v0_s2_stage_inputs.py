"""Validate frozen structural inputs before a later authorized product run.

Reads repository evidence only: no decoder, model, network or service action.
Output is a bound input plan, never a product acceptance decision.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

from tools.v0_s2_bindings import ROOT,file_hash
from tools.v0_s2_fixtures import RECIPES,BUDGET,structural_oracle

CATEGORIES=('static','tracking','fast-cut','vfr')
NEGATIVES=('over-duration','fake-extension.mp4','corrupt.mp4','truncated.mov')


def read_bound(relative,digest,*,limit=2*1024*1024):
    if not isinstance(relative,str):raise ValueError('INPUT_BINDING_PATH_INVALID')
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative:raise ValueError('INPUT_BINDING_PATH_INVALID')
    cursor=ROOT
    for part in path.parts:
        cursor=cursor/part
        if cursor.is_symlink():raise ValueError('INPUT_BINDING_SYMLINK')
    cursor.resolve(strict=True).relative_to(ROOT.resolve(strict=True))
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('INPUT_BINDING_HASH_INVALID')
    if not cursor.is_file() or cursor.stat().st_size>limit:raise ValueError('INPUT_BINDING_SIZE_LIMIT')
    raw=cursor.read_bytes()
    if len(raw)>limit or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('INPUT_BINDING_BYTES_CHANGED')
    return raw


def load_fixture_set(*,receipt_path,receipt_sha256,authorization_path,authorization_sha256,require_vfr_rounding=True):
    """Expected hashes must come from the frozen parent, never these files."""
    if type(require_vfr_rounding) is not bool:raise ValueError('VFR_ROUNDING_POLICY_INVALID')
    if receipt_path not in ('reports/v0-s2/fixture-preparation-01/receipt.json','reports/v0-s2/fixture-preparation-02/receipt.json'):
        raise ValueError('FIXTURE_RECEIPT_PATH_FORBIDDEN')
    ordinal='01' if '/fixture-preparation-01/' in receipt_path else '02'
    if authorization_path!='reports/v0-s2/authorization-fixtures-'+ordinal+'.json':raise ValueError('FIXTURE_AUTHORIZATION_PATH_MISMATCH')
    receipt=json.loads(read_bound(receipt_path,receipt_sha256))
    auth=json.loads(read_bound(authorization_path,authorization_sha256))
    if (receipt.get('decision')!='FIXTURE_SET_VERIFIED_NOT_STAGE_ACCEPTANCE'
            or receipt.get('eligible_as_frozen_structural_samples') is not True or receipt.get('cleanup_proven') is not True
            or any(type(receipt.get(k)) is not int or receipt[k]!=0 for k in ('provider_calls','service_starts','gpu_probes'))
            or receipt.get('stage_pass_claim') is not False or receipt.get('stage_checkpoint_consumed') is not False
            or auth.get('status')!='EXPIRED_FIXTURE_SET_VERIFIED_NOT_STAGE_ACCEPTANCE'
            or auth.get('source_program_authorization')!='AUTH-PROGRAM-V1-LOCAL-01' or auth.get('stage_id')!='V0-S2'
            or auth.get('scope')!='CPU_FIXED_FIXTURE_PREPARATION_ONLY' or auth.get('budget')!=BUDGET
            or not re.fullmatch('[0-9a-f]{64}',auth.get('recipe_sha256','')) or auth.get('terminal_receipt')!=receipt_path
            or auth.get('candidate_sha')!=receipt.get('candidate_sha') or auth.get('authorization_id')!=receipt.get('authorization_id')
            or auth.get('run_id')!=receipt.get('run_id') or receipt['run_id']!='fixture-preparation-'+ordinal):
        raise ValueError('FIXTURE_PROVENANCE_INVALID')
    if not re.fullmatch(r'reports/v0-s2/offline-checkpoint-[0-9]{2}/receipt[.]json',auth['offline_receipt']):
        raise ValueError('FIXTURE_OFFLINE_RECEIPT_PATH_INVALID')
    offline=json.loads(read_bound(auth['offline_receipt'],auth['offline_receipt_sha256']))
    if (offline.get('decision')!='OFFLINE_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE'
            or offline.get('candidate_sha')!=receipt['candidate_sha']):raise ValueError('FIXTURE_OFFLINE_PROVENANCE_INVALID')
    identity=receipt['identity']
    if (identity['candidate_sha']!=receipt['candidate_sha']
            or identity['execution_artifact_sha256'].get('tools/v0_s2_fixtures.py')!=auth['harness_sha256']):
        raise ValueError('FIXTURE_HARNESS_PROVENANCE_INVALID')
    for name,digest in identity['execution_artifact_sha256'].items():
        if offline['identity']['execution_artifact_sha256'].get(name)!=digest:raise ValueError('FIXTURE_OFFLINE_SOURCE_MISMATCH')
    expected=[]
    for name in RECIPES:
        expected.extend([(name+'-generate','ffmpeg'),(name+'-probe','ffprobe')])
        if name!='over-duration':expected.append((name+'-decode','ffmpeg'))
    commands=receipt['commands']
    if [(entry.get('label'),entry.get('kind')) for entry in commands]!=expected:raise ValueError('FIXTURE_COMMAND_DENOMINATOR_INVALID')
    directory=Path(receipt_path).parent;logs={}
    for entry in commands:
        if type(entry.get('exit_code')) is not int or entry['exit_code']!=0 or entry.get('cleanup_proven') is not True:
            raise ValueError('FIXTURE_COMMAND_NOT_SUCCESSFUL')
        for stream in ('stdout','stderr'):
            name=entry[stream+'_artifact']
            if name!=entry['label']+'.'+stream+'.log':raise ValueError('FIXTURE_LOG_PATH_INVALID')
            if not re.fullmatch('[0-9a-f]{64}',entry[stream+'_original_sha256']):raise ValueError('FIXTURE_ORIGINAL_LOG_HASH_INVALID')
            logs[(entry['label'],stream)]=read_bound(str(directory/name),entry[stream+'_artifact_sha256'],limit=1024*1024)
    if set(receipt['fixtures'])!=set(CATEGORIES+NEGATIVES):raise ValueError('FIXTURE_SET_DENOMINATOR_INVALID')
    result={'kind':'FROZEN_STRUCTURAL_INPUT_PLAN_NOT_ACCEPTANCE','stage_pass_claim':False,
        'fixture_receipt_sha256':receipt_sha256,'fixture_authorization_sha256':authorization_sha256,
        'categories':{},'negatives':{}}
    for name,row in receipt['fixtures'].items():
        expected_name=RECIPES[name]['file'] if name in RECIPES else name
        if row['file']!=expected_name:raise ValueError('FIXTURE_FILENAME_INVALID')
        path=directory/'fixtures'/row['file'];raw=read_bound(str(path),row['sha256'],limit=BUDGET['max_output_file_bytes'])
        if type(row['bytes']) is not int or len(raw)!=row['bytes']:raise ValueError('FIXTURE_BYTE_COUNT_INVALID')
        value={'path':str(path),'sha256':row['sha256'],'bytes':len(raw)}
        if name in RECIPES:
            parsed=json.loads(logs[(name+'-probe','stdout')]);decoded=logs.get((name+'-decode','stdout'),b'').decode('ascii')
            oracle=structural_oracle(name,parsed,decoded)
            if row['oracle']!=oracle:raise ValueError('FIXTURE_ORACLE_CHANGED')
            value['oracle']=oracle
        if name in CATEGORIES:
            duration=Fraction(parsed['format']['duration']);basis=Fraction(oracle['time_base'])
            targets=[duration*Fraction(2*index+1,8) for index in range(4)]
            value['expected_sample_pts']=[next(p for p in oracle['pts'] if p*basis>=target) for target in targets]
            if len(set(value['expected_sample_pts']))!=4:raise ValueError('FIXTURE_SAMPLE_PTS_NOT_DISTINCT')
            result['categories'][name]=value
        else:result['negatives'][name]=value
    vfr=result['categories']['vfr'];basis=Fraction(vfr['oracle']['time_base'])
    duration=Fraction(vfr['oracle']['duration_seconds'])
    rounding=all(p*basis>duration*Fraction(2*index+1,8) for index,p in enumerate(vfr['expected_sample_pts']))
    result['vfr_sampling_exercises_rounding']=rounding
    if require_vfr_rounding and not rounding:raise ValueError('VFR_SAMPLE_WINDOWS_DO_NOT_EXERCISE_ROUNDING')
    if not require_vfr_rounding:result['kind']='HISTORICAL_STRUCTURAL_INSPECTION_NOT_RUN_READY'
    return result
