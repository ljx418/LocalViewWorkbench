from pathlib import Path
import json,hashlib,subprocess,datetime
P=Path.cwd();O=P/'reports/v0-s3/product-gate0/independent-sequential-correction-02';h=lambda b:hashlib.sha256(b).hexdigest()
c=Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json');before=json.loads((O/'initial.json').read_text());assert h(c.read_bytes())==before['counter_sha256']
assert subprocess.check_output(['git','diff','--name-only'],text=True)==''
source=json.loads((O/'candidate-source-hashes.json').read_text());assert all(h((P/x['path']).read_bytes())==x['sha256'] for x in source)
for name in ['focused','guard','negative']:
 d=json.loads((O/(name+'.outer.json')).read_text());assert d['returncode']==0
 for s in ['stdout','stderr']:
  f=O/(name+('.outer.' if name!='negative' else '.')+s+'.log');assert h(f.read_bytes())==d[s+'_sha256']
receipt={'kind':'INDEPENDENT_SEQUENTIAL_CORRECTION_02_REVIEW','candidate_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'baseline_sha':'4e999043d08005829969bf5020048759557ecee9','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'findings':{'M1':'CLOSED','M2':'CLOSED','M3':'CLOSED'},'fatal':0,'major':0,'minor':0,'focused':{'count':25,'deselected':92,'skipped':0,'runs':1,'outer_returncode':0},'guard':{'refusals':4,'runs':1,'outer_returncode':0},'independent_matrix':{'observations':58,'failed_obligations':0,'runs':1,'outer_returncode':0},'candidate_sources':source,'counter_before_sha256':before['counter_sha256'],'counter_after_sha256':h(c.read_bytes()),'counter_unchanged':True,'process_binding_used':False,'real_fixture_handles':0,'stage_pass_claim':False,'product_gate0':False,'original4_closed_scope_unchanged':True,'notproven':['13 real fixtures','full I01-I24','Windows services/descendants/GPU/A06','native QualityPhase','original ledger','12 product quality obligations','human signoff'],'known_process_deviations':['Author early raw stdout overwritten or mismatched; disclosed and freshly replaced evidence independently verified','Author env-only cleanup was not coordinator cleanup; restoration already recorded','Reviewer build script transiently staged in /tmp then moved under this evidence directory'],'report_sha256':h((O/'review.md').read_bytes()),'outer_receipts':{n:json.loads((O/(n+'.outer.json')).read_text()) for n in ['focused','guard','negative']}}
(O/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
files={str(p.relative_to(O)): {'sha256':h(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(O.rglob('*')) if p.is_file() and p.name!='evidence-hashes.json'}
(O/'evidence-hashes.json').write_text(json.dumps(files,ensure_ascii=False,indent=2));print('sealed',len(files),'files',sum(x['bytes'] for x in files.values()),'bytes')
