import json,hashlib,subprocess
from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parents[3];P=O.parent
load=lambda p:json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
counts=load(O/'combined-counts.json');run=load(O/'combined-receipt.json');probes=load(O/'directed-independent-probes.json');verification=load(O/'verification.json')
assert counts['collected']==237 and len(counts['results'])==237 and all(x['outcome']=='passed' for x in counts['results'])
assert run['exit']==0 and run['removed'] and run['parser_invocations']==1 and not run['denied']
assert len(probes)==3 and all(p['removed'] and p['oracle'].startswith('PASS') for p in probes)
assert load(P/'runtime-binding-correction-03.child.json')['status']=='DRAFT_NOT_AUTHORIZED'
files=['tools/v0_s3_runtime_binding.py','tools/test_v0_s3_runtime_binding.py','plans/execution-control.json','reports/v0-s3/product-gate0/p2-binding-correction-05.contract.md','reports/v0-s3/product-gate0/offline-parser-allowance-05.json','reports/v0-s3/product-gate0/runtime-binding-correction-03.child.json']
command=load(O/'combined-command.json')
files+= [x for x in command['pytest_argv'] if x.endswith('.py') and x not in files]
files+= ['reports/v0-s3/product-gate0/independent-p2-binding-correction-04/'+n for n in ('review.md','probe.py','probe-receipt.json','archive-review.json','archive-refs.json')]
files+=['reports/v0-s3/product-gate0/implementation-p2-binding-correction-05/'+n for n in ('receipt.json','review-handoff.md','runner.py','combined-counts.json')]
save('candidate-spec-hashes.json',dict(candidate='da6e7b5ed351baca3b74f003cfcf3622c4b382d6',base='57373135ab629bcd08c429fd18477fb516c94dfb',initial_head='bf1767e',merge='clean fast-forward no conflicts',hashes={f:sha(R/f) for f in files},historical_archives=[dict(path=str(p.relative_to(R)),sha256=sha(p),bytes=p.stat().st_size,review='independent-p2-binding-correction-04/archive-review.json; no member reinspection') for p in sorted((P/'implementation-p2-binding-correction-04').glob('*.tar.gz'))]))
impl=load(P/'implementation-p2-binding-correction-05/receipt.json')
save('oracle-migration.json',dict(old_nodeids_retained=227,new_nodeids=sorted(set(load(O/'combined-collection.json')['nodeids'])-{x['nodeid'] for x in load(P/'independent-p2-binding-correction-04/combined-counts.json')['results']}),schema=impl['schema'],migrations=impl['oracle_migrations'],reviewed_diff='candidate.diff',original_failure='independent-p2-binding-correction-04/probe-receipt.json'))
ctrl=load(R/'plans/execution-control.json')
save('receipt.json',dict(disposition='ACCEPT_LOCAL_CORRECTION_RECOMMENDED_TO_ROOT',candidate='da6e7b5ed351baca3b74f003cfcf3622c4b382d6',findings=dict(Fatal=0,Major=0,Minor=0),original_M1='CLOSED_BY_CODE_AND_INDEPENDENT_PUBLIC_IO_REPLAY',tests=dict(collected=237,passed=237,failed=0,skipped=0,elapsed=run['elapsed'],exit=run['exit'],old_retained=227,new=10),independent_probes=3,parser_invocations=1,owned_cleanup=True,actual03='DRAFT_NOT_AUTHORIZED',no_actual_driver_wsl_hosthash_realclaim_motherledger_oldroots_media_gpu_network_download_checkpoint=True,verification='verification.json',probes='directed-independent-probes.json',schema=impl['schema'],limits=impl['risks'],coordinate=impl['coordinate'],development_outline=ctrl['development_outline'],next_action='Root may accept localized correction and separately freeze/rebind a future finite child; do not execute current DRAFT child or sign any product gate'))
(O/'candidate.diff').write_bytes(subprocess.check_output(['git','diff','57373135ab629bcd08c429fd18477fb516c94dfb','da6e7b5ed351baca3b74f003cfcf3622c4b382d6','--',str(R/'tools/v0_s3_runtime_binding.py'),str(R/'tools/test_v0_s3_runtime_binding.py')]))
print(json.dumps({'tests':237,'independent_probes':3,'F':0,'M':0,'m':0,'elapsed':run['elapsed']}))
