"""Read-only AST/hash/Git review; no pytest/product/test module import."""
import ast,hashlib,json,subprocess,importlib.util
from pathlib import Path
OUT=Path(__file__).resolve().parent;PACK=OUT.parents[3];REPO=PACK.parent
BASE='LVW_Prompt_Service_MasterPack_v2.0.0/'
COMMANDS=[]
def git(*args):
    p=subprocess.run(['git',*args],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    entry={'command':['git',*args],'exit_code':p.returncode,'stderr':p.stderr.decode()}
    if args[0]=='show' and args[-1].endswith('.py'):
        entry.update(stdout_retention='source read: hash/bytes only, no copied source artifact',stdout_sha256=hashlib.sha256(p.stdout).hexdigest(),stdout_bytes=len(p.stdout))
    else:entry['stdout']=p.stdout.decode()
    COMMANDS.append(entry)
    if p.returncode:raise RuntimeError(args)
    return p.stdout

def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
paths={'module':'tools/v0_s3_quality_phase.py','test':'tools/test_v0_s3_quality_phase.py','replay':'reports/v0-s3/product-gate0/implementation-p3b-correction-03/replay_correction02_probes.py','guarded_probe':'reports/v0-s3/product-gate0/implementation-p3b-correction-03/run_guarded_probe.py','contract':'reports/v0-s3/product-gate0/p3b-quality-contract.md','projection':'reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json','suite_runner':'reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py'}
expected={'module':'ca599e9da68c9a6f9405b9f89ae8bd999a43a1ecc237e469207ffede7ae98c42','test':'cd1eec5f8265e0e5e9e3ce49f35012f18236f8d3fe86719cfe851c3b333698d5','replay':'1babdad243f9194bcf4129d9d763c8020a365846de2a430108075bcfb8873d8b','guarded_probe':'c1f375c8030cae6daf75a23667b13debd0f3372ecdd4a6d31ab46b8c4cbfb81b','contract':'d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3','projection':'47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3'}
bindings={}
for key,path in paths.items():
    raw=(PACK/path).read_bytes();candidate=git('show','630853c:'+BASE+path)
    bindings[key]={'path':path,'sha256':sha(raw),'expected':expected.get(key),'matches_expected':sha(raw)==expected.get(key) if key in expected else None,'matches_candidate':raw==candidate}
manifest=json.loads((PACK/'.agent-governance/stages/V0-S3/production-quality/spec-manifest.json').read_text())
bindings['manifest']={p:{'actual':sha((PACK/p).read_bytes()),'expected':h,'matches':sha((PACK/p).read_bytes())==h} for p,h in manifest['files'].items()}
bindings['candidate_scope']=git('show','--format=fuller','--stat','630853c').decode()
bindings['inherited_merge_scope']=git('diff','--name-status','1290616','0e045c7').decode()
bindings['review_start_head']='12906163857a34bfc9afa8fa52a66dfa6fae296a'
bindings['merge_head']=git('rev-parse','HEAD').decode().strip()
bindings['initial_status']='clean (git status --short empty before merge)'
save('source-bindings.json',bindings)
# Frozen coordinate/warnings are git-show-only, retained as text evidence rather than metadata merge.
for path,dest in [('plans/execution-control.json','root-coordinate.json'),('reports/v0-s3/product-gate0/correction03-test-execution-warning-01.json','root-warning01.json'),('reports/v0-s3/product-gate0/correction03-test-execution-warning-02.json','root-warning02.json')]:
    (OUT/dest).write_bytes(git('show','4bcb640c:'+BASE+path))
adjudication=git('show','1294f0c:'+BASE+'reports/v0-s3/product-gate0/p3b-correction-03.adjudication.json')
save('adjudication-binding.json',{'commit':'1294f0c','sha256':sha(adjudication),'matches_inherited':adjudication==(PACK/'reports/v0-s3/product-gate0/p3b-correction-03.adjudication.json').read_bytes()})
old=git('show','1290616:'+BASE+paths['test']).decode();new=(PACK/paths['test']).read_text()
def functions(src):return {n.name:n for n in ast.parse(src).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')}
def dump(node):return ast.dump(node,include_attributes=False)
def assertions(node):return [dump(n) for n in ast.walk(node) if isinstance(n,ast.Assert)]
of=functions(old);nf=functions(new);nodeids=json.loads((OUT/'collected-nodeids.json').read_text());obligations=[]
for name,node in of.items():
    current=nf.get(name);o=assertions(node);n=assertions(current) if current else []
    obligations.append({'name':name,'old_line':node.lineno,'new_line':current.lineno if current else None,'present':current is not None,'assertions_identical':o==n,'old_assertions':o,'new_assertions':n,'function_identical':current is not None and dump(node)==dump(current),'collected_nodeids':[s for s in nodeids if s.split('::')[-1].split('[')[0]==name]})
old_instances=sum(len(x['collected_nodeids']) for x in obligations)
save('test-obligation-audit.json',{'old_function_count':len(of),'new_function_count':len(nf),'original_instances':old_instances,'new_instances':len(nodeids)-old_instances,'combined_instances':len(nodeids),'missing_originals':[x['name'] for x in obligations if not x['present']],'original_obligations':obligations,'changed_fixture_review':{'SyntheticDriver.release_preload':'Retains actual production node/BridgeOwner path. Adds baseline field and full raw samples; preserves all prior unproven/resident/nonfinite/bool failure branches. Adds baseline/cadence/samples/stability negatives. Synthetic values remain declared synthetic; no inference semantics replaced.','test_the_phase_deadline_blocks_the_remaining_rows':'Extends only parent proof expiry to 20000 to isolate unchanged 10800 deadline. Assertions identical.','test_correction02_m01_the_persisted_receipt_states_its_own_final_totals':'Two retained hardlink entries and double byte count replace one entry arithmetic; preserves actual disk equality and adds retained/publication assertions.','test_correction02_m01_the_receipt_caps_are_exact_and_one_over':'Uses receipt_document prefields; two entries in total/file calculations; all old accept-exact/reject-one-over assertions identical. Independent real caps observed separately.'}})
# Actual pytest -m startup chain, by reading installed source, never importing it.
pytest_path=Path(importlib.util.find_spec('pytest').origin)
init=pytest_path.read_text();main=(pytest_path.parent/'__main__.py').read_text();config=(pytest_path.parent.parent/'_pytest/config/__init__.py').read_text()
save('pytest-import-order.json',{'kind':'installed source audit, no pytest executed','files':{str(pytest_path):{'sha256':sha(init.encode()),'imports':[l for l in init.splitlines() if 'from _pytest.config import' in l]},str(pytest_path.parent/'__main__.py'):{'sha256':sha(main.encode()),'source':main},str(pytest_path.parent.parent/'_pytest/config/__init__.py'):{'sha256':sha(config.encode()),'relevant_lines':[{'line':i,'text':l} for i,l in enumerate(config.splitlines(),1) if any(x in l for x in ['def console_main','def main(','def _prepareconfig','def get_config','consider_preparse','load_setuptools_entrypoints','pytest_cmdline_parse','pytest_collection','import_plugin(spec)','PYTEST_DISABLE_PLUGIN_AUTOLOAD'])]}},'conclusion':'python -m pytest imports pytest in __main__ before console_main; pytest config/plugin loading precedes collection imports of the test module. Test module guard before its local import pytest cannot retroactively guard CLI startup or certify no earlier external actions.'})
# Retained diagnostics hashes and real exit receipts; no historical reruns.
impl=PACK/'reports/v0-s3/product-gate0/implementation-p3b-correction-03'
diagnostics=[]
for receipt in sorted((impl/'editing-diagnostics').glob('*.receipt.json')):
    doc=json.loads(receipt.read_text());label=receipt.name.split('.receipt')[0]
    streams={}
    for stream in ['stdout','stderr']:
        p=receipt.parent/(label+'.'+stream+'.log');raw=p.read_bytes();streams[stream]={'matches_hash':sha(raw)==doc[stream+'_sha256'],'matches_bytes':len(raw)==doc[stream+'_bytes'],'sha256':sha(raw),'bytes':len(raw)}
    diagnostics.append({'label':label,'exit_code':doc['exit_code'],'candidate_sha':doc['candidate_sha'],'command':doc['command'],'streams':streams})
final=json.loads((impl/'full-final.receipt.json').read_text())
final['stream_verification']={s:{'matches_sha256':sha((impl/('full-final.'+s+'.log')).read_bytes())==final[s+'_sha256'],'matches_bytes':(impl/('full-final.'+s+'.log')).stat().st_size==final[s+'_bytes']} for s in ['stdout','stderr']}
final['runner_hash']=bindings['suite_runner']['sha256'];final['runner_guard_before_import_verified_by_source']=True
save('historical-evidence-audit.json',{'admitted_unguarded_piped_pytest_rounds':10,'admitted_unguarded_debug_imports':2,'underlying_exit_codes':'UNKNOWN','historical_preimport_audit':'NOT_RETAINED','actual_forbidden_action_evidence':'NONE IDENTIFIED in retained diagnostics/source/warnings; historical zero events NOT PROVEN','unsupported_claim_location':'implementation-p3b-correction-03/report.md:156-159; receipt.json:321','guarded_diagnostics':diagnostics,'final':final,'source_binding_limit':'final receipt binds candidate by argument but does not retain before/after source hashes. Committed source equals candidate, counts and logs match final145; independent suite now executes pinned bytes with before/after hashes. This supports current code verification but cannot retrocertify historical imported bytes or early actions.'})
# Count actual retained/new replay observations, including the legacy receipt/report discrepancy.
replays={}
for label,path in [('new_replay',OUT/'replay.stdout.log'),('implementation_replay',impl/'correction02-probe-replay.stdout.log'),('previous_review_replay',PACK/'reports/v0-s3/product-gate0/independent-p3b-correction-02/replay.stdout.log'),('previous_focused',PACK/'reports/v0-s3/product-gate0/independent-p3b-correction-02/focused.stdout.log'),('previous_final_gap',PACK/'reports/v0-s3/product-gate0/independent-p3b-correction-02/final-gap.stdout.log')]:
    doc=json.loads(path.read_text());rows=doc.get('results',[]);names=[r['probe'] for r in rows]
    replays[label]={'count':len(rows),'unique_count':len(set(names)),'names':names,'sha256':sha(path.read_bytes())}
save('replay-count-erratum.json',{'actual':replays,'erratum':'The current correction03 replay has 22 unique observations. Previous correction02 replay stdout has its own actual count below; report/message21 and receipt22 must be interpreted against retained rows, without another replay. Cap probes named actual_* in implementation replay mutate constants; do not establish frozen real-cap boundaries.'})
save('git-read-commands.json',COMMANDS)
print(json.dumps({'bindings_match':all(v.get('matches_expected') is not False and v.get('matches_candidate') is not False for v in bindings.values() if isinstance(v,dict)),'original':old_instances,'new':len(nodeids)-old_instances,'changed_test_functions':[x['name'] for x in obligations if not x['function_identical']],'replay_counts':{k:v['count'] for k,v in replays.items()},'diagnostic_exit_codes':[d['exit_code'] for d in diagnostics]}))
