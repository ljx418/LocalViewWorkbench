"""Persistent V0 verification authority; finite children never sign human gates."""
import json
import re
import time

PROGRAM='reports/authorization-program-v0-local-verification-01.json'
STATEMENT='我批准后续全部V0阶段的 显卡使用、代码验证相关授权 不需要再找我确认'


def validate(program,stage):
    if (program.get('status')!='ACTIVE' or program.get('authorization_id')!='AUTH-PROGRAM-V0-LOCAL-VERIFICATION-01'
            or program.get('granted_by')!='project_owner' or program.get('statement')!=STATEMENT
            or stage not in program.get('stages',[]) or stage not in {'V0-S0','V0-S1','V0-S2','V0-S3'}
            or program.get('stage_pass_claim') is not False):
        raise ValueError('V0 verification program absent, revoked or out of scope')


def child(program,*,stage,run_id,candidate,harness_sha256,program_sha256,budget,max_seconds):
    validate(program,stage)
    if (not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}',run_id)
            or not re.fullmatch('[0-9a-f]{40}',candidate)
            or any(not re.fullmatch('[0-9a-f]{64}',v) for v in (harness_sha256,program_sha256))
            or type(max_seconds) is not int or not 0<max_seconds<=21600
            or not isinstance(budget,dict) or any(type(v) is not int or v<0 for v in budget.values())
            or any(budget.get(k,0)!=0 for k in ('cloud_calls','paid_calls','downloads'))):
        raise ValueError('finite V0 child binding/budget invalid')
    now=time.time()
    return {'schema_version':'lvw.v0-verification-child/1','status':'ACTIVE_ONE_SHOT','stage_id':stage,'run_id':run_id,
            'candidate_sha':candidate,'harness_sha256':harness_sha256,'program':PROGRAM,'program_sha256':program_sha256,
            'issued_by':'controlled_executor_under_project_owner_program','budget':dict(budget),
            'issued_at':now,'expires_at':now+max_seconds,'stage_pass_claim':False}


def expire(value,decision,terminal):
    if value.get('status')!='ACTIVE_ONE_SHOT':raise ValueError('child already terminal')
    return dict(value,status='EXPIRED_'+decision,terminal=terminal)
