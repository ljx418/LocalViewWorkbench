#!/usr/bin/env python3
"""Validate documentation integrity and design artifacts, not the application."""
from pathlib import Path
import argparse,json,hashlib,sqlite3,tempfile,re,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--schema',action='store_true');ap.add_argument('--write-report',action='store_true');args=ap.parse_args();checks=[]
 def ck(name,condition,detail=''):
  checks.append({'check':name,'passed':bool(condition),'detail':str(detail)})
 data={}
 for f in sorted(ROOT.rglob('*.json')):
  if f.parent.name in ['reports','previews'] and f.name not in ['product-results.template.json']:continue
  try:data[str(f.relative_to(ROOT))]=json.loads(f.read_text(encoding='utf-8'));ck('json:'+str(f.relative_to(ROOT)),True)
  except Exception as exc:ck('json:'+str(f.relative_to(ROOT)),False,exc)
 req=data['plans/requirements.json']['requirements'];tasks=data['plans/tasks.json']['stages'];cases=data['plans/acceptance_cases.json']['cases']
 rids={r['requirement_id'] for r in req};sids={t['stage_id'] for t in tasks};cids={c['case_id'] for c in cases}
 for name,items,ids in [('req',req,rids),('stages',tasks,sids),('cases',cases,cids)]:ck('unique:'+name,len(items)==len(ids))
 ck('legacyR retained',all(f'R{x:02}' in rids for x in range(1,21)))
 ck('legacyA retained',all(f'A{x:02}' in cids for x in range(1,23)))
 ck('legacyF retained',all(f'F{x:02}' in cids for x in range(1,8)))
 for r in req:
  ck('coverage:'+r['requirement_id'],bool(r['stages']) and set(r['stages'])<=sids and bool(r['acceptance_ids']) and set(r['acceptance_ids'])<=cids)
 for t in tasks:
  ck('stage:'+t['stage_id'],set(t['depends_on'])<=sids and set(t['requirements'])<=rids and set(t['work_on_cases'])<=cids and (ROOT/t['implementation_doc']).is_file())
 # DAG traversal
 done=set()
 for _ in range(len(tasks)+1):
  for t in tasks:
   if set(t['depends_on'])<=done:done.add(t['stage_id'])
 ck('stage dependency DAG',done==sids)
 for c in cases:ck('case-detail:'+c['case_id'],all(c.get(k) for k in ['preconditions','steps','assertions','evidence_required']) and c['status']=='NOT_RUN')
 for g,spec in data['plans/release_gates.json']['gates'].items():ck('gate:'+g,bool(spec['required_cases']) and set(spec['required_cases'])<=cids)
 for item in data['plans/requirement_coverage.json']['coverage']:
  ck('requirement-docs:'+item['requirement_id'],all((ROOT/x).is_file() for x in item['docs']+item['contracts']))
 for row in data['plans/legacy_file_map.json']['files']:ck('legacy-file-map:'+row['source_file'],(ROOT/row['target']).is_file())
 for b in data['sources/baselines.json']['actual_read_archives']:
  f=ROOT/b['archive'];ck('baseline hash '+b['name'],f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest()==b['sha256'])
 # OpenAPI all refs/ids/path params
 api=data['contracts/openapi.json'];opids=[]
 def walk(x):
  if isinstance(x,dict):
   if '$ref' in x:yield x['$ref']
   for y in x.values():yield from walk(y)
  elif isinstance(x,list):
   for y in x:yield from walk(y)
 for r in walk(api):ck('openapi ref '+r,r.startswith('#/components/schemas/') and r.rsplit('/',1)[-1] in api['components']['schemas'])
 for path,ops in api['paths'].items():
  for method,op in ops.items():
   opids.append(op['operationId']);names={p['name'] for p in op['parameters'] if p['in']=='path'}
   ck(method+' '+path,names==set(re.findall(r'{([^}]+)}',path)) and bool(op.get('responses')) and op['x-product-version'] in ['V1','V2','V3'])
 ck('unique API operation IDs',len(opids)==len(set(opids)))
 # file links in markdown (non-code URLs intentionally allowed)
 for f in list((ROOT/'docs').glob('*.md'))+[ROOT/'README.md',ROOT/'CODEX_START.md']:
  for target in re.findall(r'\]\(([^)]+)\)',f.read_text()):
   if target.startswith(('http:','https:','#','mailto:')):continue
   ck('link:'+str(f.relative_to(ROOT))+':'+target,(f.parent/target.split('#')[0]).exists())
 # Schema validation of canonical definitions and example positive/negative.
 if args.schema:
  try:
   from jsonschema import Draft202012Validator,FormatChecker
   core=data['contracts/lvw.schema.json'];Draft202012Validator.check_schema(core);ck('core schema metaschema',True)
   pairs=[('examples/valid/prompt-spec.json','PromptSpec'),('examples/valid/v0-manual-result.json','V0Result'),('examples/valid/scene.json','Scene'),('examples/valid/revision.json','Revision'),('examples/invalid/result-invalid-status.json','V0Result'),('examples/invalid/spec-invalid-version.json','PromptSpec')]
   for fn,name in pairs:
    validator=Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':core['$defs']},format_checker=FormatChecker());errs=list(validator.iter_errors(data[fn]));ck('schema-example:'+fn,bool(errs) if '/invalid/' in fn else not errs,str(errs[:1]))
   for p in (ROOT/'contracts').glob('*.schema.json'):Draft202012Validator.check_schema(json.loads(p.read_text()));ck('schema-metaschema:'+p.name,True)
  except Exception as exc:ck('jsonschema validation',False,exc)
 # Execute DDL, assert immutable revision and invalid scene bounds.
 try:
  con=sqlite3.connect(':memory:');con.executescript((ROOT/'contracts/storage.sql').read_text());ck('DDL executes',True)
  con.execute("INSERT INTO shot VALUES ('s','t',NULL,'{}','e',NULL,'now')")
  con.execute("INSERT INTO prompt_revision VALUES ('r','s',NULL,'human','{}','hash','now','key')")
  try:con.execute("UPDATE prompt_revision SET spec_json='x' WHERE id='r'");ck('immutable revision trigger',False)
  except sqlite3.IntegrityError:ck('immutable revision trigger',True)
  try:con.execute("INSERT INTO scene_revision VALUES('z','missing',1,4,2,0,1,25,'human')");ck('scene invariant DB rejection',False)
  except sqlite3.IntegrityError:ck('scene invariant DB rejection',True)
  ck('SQLite integrity',con.execute('PRAGMA integrity_check').fetchone()[0]=='ok');con.close()
 except Exception as exc:ck('DDL checks',False,exc)
 # HTML static resources no network dependencies
 for p in [ROOT/'START_HERE.html',ROOT/'prototype/index.html']:
  text=p.read_text();ck('HTML no remote runtime assets '+p.name,not re.search(r'<(?:script|link|img)[^>]+(?:src|href)=[\"\']https?://',text,re.I))
  ck('HTML labelled design '+p.name,'演示' in text and '产品' in text)
 ck('no product PASS inherited',all(c['status']=='NOT_RUN' for c in data['reports/product-results.template.json']['cases']))
 manifest=ROOT/'MANIFEST.sha256'
 if manifest.exists():
  for line in manifest.read_text(encoding='utf-8').splitlines():
   if not line.strip():continue
   digest,rel=line.split('  ',1);p=ROOT/rel
   ck('manifest:'+rel,p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest)
 result={'kind':'DOCUMENT_AND_CONTRACT_VALIDATION_NOT_PRODUCT_ACCEPTANCE','passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks),'checks':checks,'scope':{'requirements':len(req),'stages':len(tasks),'test_groups':len(cases),'api_operations':len(opids)},'target_hardware_tested':False}
 if args.write_report:(ROOT/'reports/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
 for c in checks:
  if not c['passed']:print('FAIL',c)
 return 1 if result['failed'] else 0
if __name__=='__main__':sys.exit(main())
