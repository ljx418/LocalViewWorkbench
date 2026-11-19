"""Read-only evidence reconciliation, independent of candidate Python imports."""
import hashlib,json,re,sqlite3,subprocess
from pathlib import Path
from PIL import Image
D=Path(__file__).resolve().parent
R=Path('/mnt/c/workspace/videoworkline/localviewworkbench')
P='LVW_Prompt_Service_MasterPack_v2.0.0'
C='94f92bedb391f2cdcca869df10360e9b116a7c1a'
F=R/P/'reports/resource-cleanup'
A=F/'correction-01'
def sha(b): return hashlib.sha256(b).hexdigest()
def digest(p): return sha(p.read_bytes())
def obj(rel,rev=C): return subprocess.check_output(['git','-C',str(R),'show',f'{rev}:{P}/{rel}'])
def j(p): return json.loads(p.read_bytes())
def put(n,v): (D/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def bind(rel,wanted,rev=C):
    actual=sha(obj(rel,rev))
    return dict(path=rel,expected=wanted,actual=actual,match=actual==wanted)
ack=j(A/'root-ack.json')
out={'root_ack':{rev:[bind(rel,h,rev) for rel,h in ack['source_hashes'].items()] for rev in (C,'dc7e6d71')}}
out['root_hashes']={str(p.relative_to(F)):digest(p) for p in sorted(F.rglob('*')) if p.is_file()}
out['extract_mismatches']=[p for p,h in j(D/'source-hashes.json').items() if sha(obj(p))!=h]
out['candidate_root_evidence_mismatches']=[str(p.relative_to(A)) for p in (list((A/'cpu').rglob('*'))+[A/'root-ack.json',A/'decision.md',A/'live_harness_v2.py']) if p.is_file() and obj(p.relative_to(R/P))!=p.read_bytes()]
def check(request,folder):
    ctl=j(folder/'receipt.json')
    logs={k:(folder/k).read_text() for k in ['stdout.log','stderr.log']}
    return dict(argv=ctl['argv'],intent_matches=j(request)==j(folder/'intent.json'),request_fields_match=all(ctl[k]==j(request)[k] for k in ['argv','cwd','environment']),identity_matches=all(ctl[k]==v for k,v in j(folder/'child.json').items()),receipt=ctl,logs=logs,pytest_success_markers=sum(len(m) for m in re.findall(r'^([.]+) +\[',logs['stdout.log'],re.M)))
out['cpu']={p.name:check(A/'cpu'/('request-'+p.name[-2:]+'.json'),p) for p in sorted((A/'cpu').glob('check-*'))}
out['independent']=check(D/'request.json',D/'cpu')
out['live']={}
for p in sorted((A/'runs').iterdir()):
    child=j(p/'authorization.json')
    ledger=Path(child['budget_ledger'])
    with sqlite3.connect(ledger.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=dict(db.execute('select * from children where run=?',(child['run_id'],)).fetchone())
    tools=j(p/'tool-bindings.json')
    view={}
    for file in sorted(p.glob('*.png')):
        with Image.open(file) as im:
            view[file.name]=im.size
            im.verify()
    out['live'][p.name]=dict(frozen=[bind(x['path'],x['sha256']) for x in child['frozen_files']], tools={k:dict(**v,current_sha256=digest(Path(v['path']))) for k,v in tools.items()},ledger=row,db_bindings_match=(row['child_hash']==digest(p/'authorization.json') and row['child_path']==str(p/'authorization.json') and row['bindings_path']==str(p/'tool-bindings.json') and row['bindings_hash']==digest(p/'tool-bindings.json')),grant=bind(child['program'],child['program_sha256']),claim_matches=(p/'run.claim').read_text()==child['run_id'],controller=check(p/'request.json',p/'controller'),images=view,receipt=j(p/'receipt.json'),verdict=j(p/'cleanup-response.json')['data'],native_final=j(p/'native-final.json'))
put('audit.json',out)
print('ack mismatches',[(r,sum(not i['match'] for i in s)) for r,s in out['root_ack'].items()],'extraction',out['extract_mismatches'],'root',out['candidate_root_evidence_mismatches'])
for k,y in out['live'].items():
    print(k,y['db_bindings_match'],y['ledger']['calls'],y['ledger']['active'],len(y['frozen']),all(x['match'] for x in y['frozen']),all(v['sha256']==v['current_sha256'] for v in y['tools'].values()),y['images'])
