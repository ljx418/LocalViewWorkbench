#!/usr/bin/env python3
"""Bounded V2 design consistency checks; no application imports or real media/DB."""
import sys

def deny_external(event, args):
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn')) or event in ('os.system','os.fork','os.forkpty'):
        raise RuntimeError('DESIGN_CHECK_EXTERNAL_ACTION_FORBIDDEN:' + event)
sys.addaudithook(deny_external)
sys.dont_write_bytecode = True
from pathlib import Path
import copy
import hashlib
import json
import re
import sqlite3
import argparse

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'plans/candidates/v2-library'
C = ROOT / 'contracts/candidates/v2-library'
R = ROOT / 'reports/v2-library-design-2026-11-12'

def load(p):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out: raise ValueError('duplicate key:' + k)
            out[k] = v
        return out
    return json.loads(p.read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def structural_errors(requirements, cases, gates, tasks, samples, overlay):
    errors = []
    ids = [x['requirement_id'] for x in requirements['requirements']]
    cids = [x['case_id'] for x in cases['cases']]
    rn = ['RN%02d' % i for i in range(1,19)]
    if ids != ['R%d' % i for i in range(23,31)]: errors.append('requirement IDs')
    if cids != rn: errors.append('fixed RN18')
    covered = {n for x in requirements['requirements'] for n in x['acceptance_ids']}
    if covered != set(rn): errors.append('requirement coverage')
    for case in cases['cases']:
        if case['status'] != 'NOT_RUN' or not all(case.get(k) for k in ('owner_entry','steps','assertions','negative_cases','terminal_oracle','cleanup_oracle','evidence_required')): errors.append('case obligation:' + case['case_id'])
    for version,count in [('V2',56),('V3',65)]:
        g = gates['gates'][version]
        if g['effective_required_cases'] != g['retain_required_cases'] + rn or len(g['effective_required_cases']) != count or len(set(g['effective_required_cases'])) != count: errors.append('cumulative:' + version)
    work = tasks['workpacks']; names = {x['id'] for x in work}; done = set(tasks['external_prerequisites'])
    for _ in work:
        for x in work:
            if set(x['depends_on']) <= done: done.add(x['id'])
    if not names <= done: errors.append('workpack DAG')
    if len(samples['samples']) != 30 or len({x['sample_id'] for x in samples['samples']}) != 30: errors.append('fixed30')
    if sum(x['split']=='development' for x in samples['samples']) != 18 or sum(x['split']=='independent_holdout' for x in samples['samples']) != 12: errors.append('18/12 isolation')
    if any(x['path'] is not None or x['sha256'] is not None or x['labels_sha256'] is not None for x in samples['samples']): errors.append('unapproved sample materialization')
    for path,ops in overlay['add_paths'].items():
        for method,op in ops.items():
            if not op.get('x-local-session-required'): errors.append('session:' + path)
            if method in ('post','delete','put','patch'):
                headers = {x['name']:x for x in op['parameters'] if x['in']=='header'}
                for name in ('Idempotency-Key','X-LVW-CSRF'):
                    if not headers.get(name,{}).get('required'): errors.append('write header:' + path + name)
                if '{id}' in path and not headers.get('If-Match',{}).get('required'): errors.append('CAS:' + path)
    return errors

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--self-test',action='store_true'); args=ap.parse_args()
    checks=[]
    def ck(name,ok,detail=''): checks.append({'check':name,'passed':bool(ok),'detail':str(detail)})
    try:
        req, cases, gates, tasks, samples, overlay = [load(x) for x in (P/'requirements.json',P/'acceptance_cases.json',P/'release_gates.overlay.json',P/'tasks.json',P/'sample-design.json',C/'openapi-overlay.json')]
        errors=structural_errors(req,cases,gates,tasks,samples,overlay);ck('candidate structure/coverage/DAG',not errors,errors)
        base=load(R/'baseline.json'); live=load(ROOT/'plans/execution-control.json')
        for key in ('coordinate','target_version','development_outline','last_passed_gate','current_blocking_gate','implementation_routing'): ck('current V1 preserved:'+key,live[key]==base[key])
        for path,want in base['source_sha256'].items(): ck('protected hash:'+path,digest(ROOT/path)==want)
        canonical=load(ROOT/'plans/release_gates.json')
        ck('base gate pin',digest(ROOT/'plans/release_gates.json')==gates['base_sha256'])
        for v in ('V2','V3'): ck('base gate prefix:'+v,gates['gates'][v]['retain_required_cases']==canonical['gates'][v]['required_cases'])
        ck('V1 unchanged29',gates['V1_unchanged_required_cases']==canonical['gates']['V1']['required_cases'] and len(canonical['gates']['V1']['required_cases'])==29)
        activation=load(P/'activation.json');ck('candidate not runtime authorization',activation['status']=='DESIGN_CANDIDATE_NOT_ACTIVE' and all(activation[k] is None for k in ('runtime_authorization','private_sample_paths','write_scope','pilot_or_quality_threshold_approval')))
        schema=load(C/'library.schema.json')
        # Dependency is already installed or validation fails explicitly. No install/network fallback.
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(schema);ck('candidate metaschema',True)
        defs=schema['$defs']; ids=[]; effective=copy.deepcopy(load(ROOT/'contracts/openapi.json'))
        def refs(x):
            if isinstance(x,dict):
                if '$ref' in x: yield x['$ref']
                for v in x.values(): yield from refs(v)
            elif isinstance(x,list):
                for v in x: yield from refs(v)
        def rewrite(x):
            if isinstance(x,dict): return {k:('#/components/schemas/Library_'+v.split('/')[-1] if k=='$ref' and v.startswith('#/$defs/') else rewrite(v)) for k,v in x.items()}
            if isinstance(x,list): return [rewrite(v) for v in x]
            return x
        for name,body in defs.items():
            n='Library_'+name;ck('component disjoint:'+n,n not in effective['components']['schemas']);effective['components']['schemas'][n]=rewrite(body)
        for path,ops in overlay['add_paths'].items():
            ck('additive path:'+path,path not in effective['paths']);effective['paths'][path]=copy.deepcopy(ops)
            for method,op in ops.items():
                ids.append(op['operationId']);ck('path params:'+path,{p['name'] for p in op['parameters'] if p['in']=='path'}==set(re.findall(r'{([^}]+)}',path)))
        for pointer in refs(effective):ck('resolved ref:'+pointer,pointer.startswith('#/components/schemas/') and pointer.rsplit('/',1)[-1] in effective['components']['schemas'])
        old=load(ROOT/'contracts/openapi.json');ck('original API exact after merge',all(effective['paths'][k]==v for k,v in old['paths'].items()) and all(effective['components']['schemas'][k]==v for k,v in old['components']['schemas'].items()))
        ck('unique new operation IDs',len(ids)==len(set(ids)) and not (set(ids)&{o['operationId'] for ops in old['paths'].values() for o in ops.values()}))
        def valid(name,value):return Draft202012Validator({'$defs':defs,'$ref':'#/$defs/'+name}).is_valid(value)
        scan={'root_id':'r','recursive':True,'profile':'library-scan/0.1'}
        ck('positive DTO scan',valid('ScanRequest',scan));ck('no absolute-path browser field',not valid('ScanRequest',dict(scan,path='C:\\private')))
        apay={'plan_revision_id':'p','plan_hash':'a'*64,'item_ids':['i'],'selection_hash':'b'*64,'confirmation_token':'c'*32}
        ck('positive DTO apply',valid('ApplyPlan',apay))
        for name,value in [('missing confirmation',{k:v for k,v in apay.items() if k!='confirmation_token'}),('duplicate selected',{**apay,'item_ids':['i','i']}),('unknown field',{**apay,'absolute_path':'C:\\x'}),('empty selection',{**apay,'item_ids':[]})]:ck('negative apply:'+name,not valid('ApplyPlan',value))
        fileprops=defs['SourceFile']['properties'];ck('no public absolute root',all('canonical_path' not in defs[n]['properties'] for n in ('SourceRoot','SourceFile','PlanItem')))
        for n in ('SourceFilePage','PlanItemPage'):ck('page bounded200:'+n,defs[n]['properties']['items']['maxItems']==200)
        for x in load(C/'mcp-additions.json')['tools']:ck('MCP ID-only:'+x['name'],x['scope'] in ('read','analyze','naming_preview'))
        ck('no MCP write tools',load(C/'mcp-additions.json')['write_tools']==[])
        for row in load(P/'requirement_coverage.json')['coverage']:
            ck('coverage paths:'+row['requirement_id'],all((ROOT/x).is_file() for x in row['docs']+row['contracts']))
        sql=(C/'storage-additions.sql').read_text();ck('DDL no external access',not re.search(r'\b(ATTACH|VACUUM|load_extension|readfile|writefile)\b',sql,re.I))
        db=sqlite3.connect(':memory:');db.execute('PRAGMA foreign_keys=ON');db.executescript((ROOT/'contracts/storage.sql').read_text());db.executescript(sql)
        ck('incremental DDL memory only',db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
        db.execute("INSERT INTO asset VALUES('a','image','m','title','[]','{}',0)")
        db.execute("INSERT INTO asset_description_revision VALUES('d','a',NULL,NULL,'[]','[]','[]',NULL,'hash','human','now')")
        for command in ("UPDATE asset_description_revision SET facts_json='{}' WHERE id='d'","DELETE FROM asset_description_revision WHERE id='d'"):
            try:db.execute(command);ck('immutable description:'+command,False)
            except sqlite3.IntegrityError:ck('immutable description:'+command,True)
        try:db.execute("INSERT INTO asset_description_revision VALUES('bad','missing',NULL,NULL,'[]','[]','[]',NULL,'x','human','now')");ck('foreign key rejects missing asset',False)
        except sqlite3.IntegrityError:ck('foreign key rejects missing asset',True)
        ck('foreign keys intact',not db.execute('PRAGMA foreign_key_check').fetchall());db.close()
        for path in [ROOT/'README.md',*sorted((ROOT/'docs').rglob('*.md')),P/'prompts.md']:
            for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
                if target.startswith(('#','https:','http:','mailto:')):continue
                ck('link:'+str(path.relative_to(ROOT))+':'+target,(path.parent/target.split('#')[0]).exists())
        if args.self_test:
            altered=copy.deepcopy(gates);altered['gates']['V2']['effective_required_cases'].pop();ck('negative shrink denominator',bool(structural_errors(req,cases,altered,tasks,samples,overlay)))
            altered=copy.deepcopy(overlay);altered['add_paths']['/api/v2/rename-plans/{id}/apply']['post']['parameters']=[];ck('negative remove write guards',bool(structural_errors(req,cases,gates,tasks,samples,altered)))
            altered=copy.deepcopy(samples);altered['samples'][0]['path']='private.mp4';ck('negative unbound private sample',bool(structural_errors(req,cases,gates,tasks,altered,overlay)))
            altered=copy.deepcopy(tasks);altered['workpacks'][0]['depends_on']=['R4-L4'];ck('negative workpack cycle',bool(structural_errors(req,cases,gates,altered,samples,overlay)))
    except Exception as error:
        ck('validation exception',False,type(error).__name__+':'+str(error))
    failed=[x for x in checks if not x['passed']]
    print(json.dumps({'kind':'V2_DESIGN_CONSISTENCY_NOT_PRODUCT_ACCEPTANCE','checks':len(checks),'failed':failed,'passed':len(checks)-len(failed),'product_gate0':False,'runtime_actions':0},ensure_ascii=False,indent=2))
    return 1 if failed else 0

if __name__=='__main__':raise SystemExit(main())
