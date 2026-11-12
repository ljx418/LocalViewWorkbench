"""Independent design-only static/schema and SQLite :memory: probe; no app imports."""
import sys
sys.dont_write_bytecode = True
def guard(event, args):
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn')) or event in ('os.system', 'os.fork', 'os.forkpty'):
        raise RuntimeError('REVIEW_EXTERNAL_ACTION_FORBIDDEN:' + event)
sys.addaudithook(guard)
import json
import hashlib
import sqlite3
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
C = ROOT / 'contracts/candidates/v2-library'
read = lambda name: json.loads((C / name).read_text())
defs = read('library.schema.json')['$defs']
overlay = read('openapi-overlay.json')['add_paths']
rules = read('semantic-rules.json')
projection = read('job-compatibility.json')
checks = []
def ck(name, condition, actual=None):
    checks.append({'check':name, 'passed':bool(condition), 'actual':actual})
def valid(name, value):
    return Draft202012Validator({'$defs':defs, '$ref':'#/$defs/'+name}).is_valid(value)
def etag(material):
    return '"lh:' + hashlib.sha256(json.dumps(material, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest() + '"'

cas = rules['head_cas']
for name in ('example', 'next'):
    ck('M01 normative '+name+' ETag', etag(cas[name+'_material']) == cas[name+'_etag'])
for path, method in [('/api/v2/assets/{id}/description','get'), ('/api/v2/assets/{id}/description/revisions','post'),
                     ('/api/v2/naming-templates/{id}','get'), ('/api/v2/naming-templates/{id}/revisions','post'), ('/api/v2/naming-templates','post')]:
    header = overlay[path][method]['responses']['200']['headers']['ETag']
    validator = Draft202012Validator(header['schema'])
    ck('M01 required strong header '+path, header['required'] and validator.is_valid(cas['example_etag']))
    ck('M01 invalid ETag values rejected '+path, all(not validator.is_valid(v) for v in ('W/'+cas['example_etag'], '*', cas['example_etag']+', '+cas['next_etag'], 'lh:'+'a'*64)))

db = sqlite3.connect(':memory:')
db.execute('PRAGMA foreign_keys=ON')
db.executescript((ROOT/'contracts/storage.sql').read_text())
db.executescript((C/'storage-additions.sql').read_text())
db.execute("INSERT INTO source_root(id,canonical_path,display_name,volume_serial,root_file_id,scope_json,permission_epoch,state,etag,created_at) VALUES('r','server-only','root','v','rid','[]',1,'active','e','now')")
for n in ('1','2'):
    db.execute("INSERT INTO asset(id,kind,target_id,title,tags_json,provenance_json,archived) VALUES(?,'image','m','title','[]','{}',0)",('a'+n,))
    db.execute("INSERT INTO source_file(id,root_id,relative_path,path_key,volume_serial,physical_file_id,content_sha256,byte_count,creation_ticks,write_ticks,change_ticks,identity_version,availability,etag) VALUES(?,'r',?,?,'v',?,'hash',1,'1','1','1',1,'available','e')", ('s'+n, 'old'+n+'.jpg', 'old'+n+'.jpg', 'physical'+n))

desc_insert = 'INSERT INTO asset_description_revision(id,asset_id,parent_id,model_run_id,facts_json,unknowns_json,locked_fields_json,analysis_key,content_sha256,author,created_at) VALUES(?,?,?,NULL,\'[]\',\'[]\',\'[]\',NULL,?,\'human\',\'now\')'
for n in ('1','2'):
    db.execute(desc_insert, ('d'+n,'a'+n,None,'a'*64))
ck('tags_json omitted-column default is empty array', db.execute("SELECT tags_json FROM asset_description_revision WHERE id='d1'").fetchone()[0] == '[]')
db.execute("INSERT INTO naming_template_head(id,head_revision_id,etag) VALUES('t',NULL,'initial')")
db.execute("INSERT INTO naming_template_revision(id,template_id,parent_id,body_json,content_sha256,created_at) VALUES('tr1','t',NULL,'{}',?,'now')", ('a'*64,))

# SQL illustrates the specified short transaction, not production service behavior.
for kind, table, aggregate, first, second, rejected in [('description','asset_description_head','a1','d1','d3','d4'), ('template','naming_template_head','t','tr1','tr2','tr3')]:
    material = dict(cas['example_material'], aggregate_kind=kind, aggregate_id=aggregate, head_revision_id=first)
    old_tag = etag(material)
    key = 'asset_id' if kind == 'description' else 'id'
    if kind == 'description':
        db.execute('INSERT INTO asset_description_head(asset_id,head_revision_id,etag,head_sequence) VALUES(?,?,?,1)', (aggregate,first,old_tag))
    else:
        db.execute('UPDATE naming_template_head SET head_revision_id=?,etag=?,head_sequence=1 WHERE id=?', (first,old_tag,aggregate))
    def append(revision, parent):
        if kind == 'description':
            db.execute(desc_insert,(revision,aggregate,parent,'b'*64))
        else:
            db.execute('INSERT INTO naming_template_revision(id,template_id,parent_id,body_json,content_sha256,created_at) VALUES(?,?,?,\'{}\',?,\'now\')',(revision,aggregate,parent,'b'*64))
    newer = dict(material,head_revision_id=second,head_sequence=2,head_content_sha256='b'*64)
    db.execute('SAVEPOINT positive')
    append(second, first)
    changed = db.execute('UPDATE '+table+' SET head_revision_id=?,etag=?,head_sequence=2 WHERE '+key+'=? AND etag=?',(second,etag(newer),aggregate,old_tag)).rowcount
    db.execute('RELEASE positive')
    ck('M01 positive CAS '+kind, changed==1 and db.execute('SELECT head_revision_id,etag,head_sequence FROM '+table+' WHERE '+key+'=?',(aggregate,)).fetchone()==(second,etag(newer),2))
    db.execute('SAVEPOINT stale')
    append(rejected, second)
    changed = db.execute('UPDATE '+table+' SET head_revision_id=? WHERE '+key+'=? AND etag=?',(rejected,aggregate,old_tag)).rowcount
    if changed == 0: db.execute('ROLLBACK TO stale')
    db.execute('RELEASE stale')
    revisions = 'asset_description_revision' if kind=='description' else 'naming_template_revision'
    ck('M01 stale rollback '+kind, changed==0 and db.execute('SELECT COUNT(*) FROM '+revisions+' WHERE id=?',(rejected,)).fetchone()[0]==0 and db.execute('SELECT head_revision_id FROM '+table+' WHERE '+key+'=?',(aggregate,)).fetchone()[0]==second)

db.execute("INSERT INTO rename_plan_head(id,head_revision_id,etag) VALUES('p',NULL,'e')")
db.execute("INSERT INTO rename_plan_revision(id,plan_id,revision,parent_id,direction,undo_of_operation_id,template_revision_id,plan_hash,body_json,created_at) VALUES('pr','p',1,NULL,'forward',NULL,'tr1','hash','{}','now')")
for n in ('1','2'):
    db.execute("INSERT INTO rename_plan_item(plan_revision_id,id,source_file_id,description_revision_id,target_root_id,target_path_key,ordinal,item_json) VALUES('pr',?,?,?,'r','same.jpg',?,'{}')",('i'+n,'s'+n,'d'+n,int(n)))
ck('M02 both duplicate-target preview rows persisted', db.execute('SELECT COUNT(*) FROM rename_plan_item').fetchone()[0]==2)
db.execute("INSERT INTO job(id,kind,state,idempotency_key,payload_hash,payload_json,created_at,updated_at) VALUES('j','batch','queued','key','hash','{}','now','now')")
def operation(name):
    db.execute("INSERT INTO file_operation(id,job_id,plan_revision_id,plan_hash,selection_hash,session_id,route,idempotency_key,payload_sha256,state,created_at,updated_at) VALUES(?,'j','pr','hash','selection','session','apply',?,'hash','queued','now','now')", (name,name))
def reserve(op,item):
    db.execute("INSERT INTO file_target_reservation(operation_id,item_id,purpose,volume_serial,parent_file_id,target_path_key) VALUES(?,?,'final','v','parent','same.jpg')", (op,item))
db.execute('SAVEPOINT duplicate_selection')
try:
    operation('bad');reserve('bad','i1');reserve('bad','i2');error=None
except sqlite3.IntegrityError as exc:
    error=str(exc);db.execute('ROLLBACK TO duplicate_selection')
db.execute('RELEASE duplicate_selection')
ck('M02 duplicate selected targets rejected by SQL', error is not None, error)
ck('M02 failed selection leaves no operation/reservation',db.execute('SELECT COUNT(*) FROM file_operation').fetchone()[0]==0 and db.execute('SELECT COUNT(*) FROM file_target_reservation').fetchone()[0]==0)
ck('M02 full preview preserved after rollback',db.execute('SELECT COUNT(*) FROM rename_plan_item').fetchone()[0]==2)
operation('good');reserve('good','i1')
ck('M02 single selected target can reserve',db.execute('SELECT COUNT(*) FROM file_target_reservation').fetchone()[0]==1)
db.execute('SAVEPOINT concurrent_claim')
try:
    operation('other');reserve('other','i2');error=None
except sqlite3.IntegrityError as exc:
    error=str(exc);db.execute('ROLLBACK TO concurrent_claim')
db.execute('RELEASE concurrent_claim')
ck('M02 conflicting second operation rolls back without clearing old reservation',error is not None and db.execute('SELECT operation_id FROM file_target_reservation').fetchall()==[('good',)] and db.execute("SELECT COUNT(*) FROM file_operation WHERE id='other'").fetchone()[0]==0)
ck('memory DDL integrity and FK',db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall())
db.close()

intent={'schema_version':'lvw.library-intent/1','job_id':'j','intent_kind':'scan','subject_ref':'root-id','payload_sha256':'a'*64,'profile_version':'library-scan/0.1','permission_epochs':[{'root_id':'r','epoch':1}]}
ck('m02 complete typed intent positive',valid('LibraryIntent',intent))
ck('m02 typed intent rejects added absolute path',not valid('LibraryIntent',dict(intent,absolute_path='C:/private')))
job_schema=json.loads((ROOT/'contracts/job.schema.json').read_text())['$defs']['Job']
for kind,mapped in projection['kind_projection'].items():
    for state,status in projection['status_projection'].items():
        job={'id':'j','kind':mapped,'status':status,'resource_state':'unknown' if kind=='describe' else 'released','attempt_id':None,'cancel_epoch':0,'progress_done':1,'progress_total':2,'result_ref':None,'error_code':projection['error_projection'].get(state)}
        ck('m02 strict Job '+kind+'/'+state,Draft202012Validator(job_schema).is_valid(job))

identity={'volume_serial':'a'*16,'file_id_128':'b'*32,'content_sha256':'c'*64,'bytes':1,'creation_ticks':'1','write_ticks':'1','change_ticks':'1'}
item={'id':'retry-i1','source_file_id':'s1','source_identity_version':1,'identity':identity,'source_root_id':'r','source_relative_path':'frozen-temp.jpg','target_root_id':'r','target_relative_path':'final.jpg','source_root_epoch':1,'target_root_epoch':1,'description_revision_id':'d1','description_revision_sha256':'a'*64,'seq':1,'temp_relative_path':None,'depends_on':[],'conflicts':[],'unknowns':[],'retry_of_item_id':'i1','retry_from_event_seq':3}
plan={'id':'new-pr','plan_id':'p2','revision':1,'parent_id':None,'direction':'forward','undo_of_operation_id':None,'template_revision_id':'tr1','template_revision_sha256':'a'*64,'compiler_version':'compiler-v1','vocabulary_revision':'v1','items':[item],'plan_hash':'b'*64,'etag':'e','retry_of_operation_id':'failed-op','retry_base_event_seq':3}
ck('m03 complete staged forward retry plan',valid('RenamePlanRevision',plan))
undo=dict(plan,direction='undo',undo_of_operation_id='original-forward',retry_of_operation_id='failed-undo')
ck('m03 undo retry keeps both distinct lineage references',valid('RenamePlanRevision',undo))
ck('m03 undo requires original forward reference',not valid('RenamePlanRevision',dict(undo,undo_of_operation_id=None)))
ck('m03 lineage event required when retry operation set',not valid('RenamePlanRevision',dict(plan,retry_base_event_seq=None)))
ck('m03 item lineage event required',not valid('PlanItem',dict(item,retry_from_event_seq=None)))
ck('m03 retry request complete and duplicate rejected',valid('RetryPlanRequest',{'item_ids':['i1'],'last_event_seq':3}) and not valid('RetryPlanRequest',{'item_ids':['i1','i1'],'last_event_seq':3}))

tag={'label':'蓝色灯光','language':'zh','source_kind':'observed','source_ref':'frame-ref','source_revision':'frame-v1','confirmation':'confirmed','coverage':['f1']}
fact={'field':'DJ','value':'User supplied name','language':'und','source_kind':'user_confirmed','source_ref':'user-evidence','source_revision':'evidence-v1','confirmation':'confirmed','coverage':[]}
edit={'facts':[fact],'tags':[tag],'unknowns':[],'locked_fields':['tags']}
revision={'id':'desc','asset_id':'a1','parent_id':None,'facts':[fact],'tags':[tag],'unknowns':[],'locked_fields':['tags'],'analysis_key':None,'model_run_id':None,'content_sha256':'a'*64}
ck('goal2 complete description/edit with typed locked tags',valid('AssetDescriptionRevision',revision) and valid('DescriptionEdit',edit))
for name,mutation in [('creative',{'source_kind':'creative_intent'}),('no provenance',{'source_ref':None}),('no revision',{'source_revision':None}),('no coverage',{'coverage':[]}),('bad language',{'language':'unvalidated-language'}),('empty label',{'label':''}),('overlong label',{'label':'x'*81}),('extra field',{'absolute_path':'C:/private'})]:
    ck('goal2 typed tag rejects '+name,not valid('TagFact',dict(tag,**mutation)))
ck('goal2 missing tags rejected with otherwise complete description',not valid('AssetDescriptionRevision',{k:v for k,v in revision.items() if k!='tags'}))
ck('goal2 complete inferred DJ negative and confirmed positive',not valid('FieldFact',dict(fact,source_kind='inference')) and valid('FieldFact',fact))

times={name:None for name in defs['LibraryAccounting']['properties']['phase_times']['properties']}
account={'task_id':'j','snapshot_id':'s','is_final':False,'accounting_complete':False,'planned_assets':2,'discovered_assets':2,'reused_assets':0,'model_attempted_assets':0,'failed_assets':0,'not_attempted_assets':2,'provider_attempts':0,'provider_calls_observed':None,'elapsed_ms':None,'phase_times':times}
row={'asset_id':'a1','source_file_id':'s1','child_job_id':None,'attempt_id':None,'model_run_id':None,'analysis_key':None,'outcome':'not_attempted','provider_action_ids':[],'provider_attempts':0,'provider_calls_observed':None,'elapsed_ms':None,'phase_times':times}
ck('m04 complete unknown accounting and item positive',valid('LibraryAccounting',account) and valid('LibraryAccountingItem',row))
ck('m04 known observed calls and times positive',valid('LibraryAccounting',dict(account,provider_attempts=2,provider_calls_observed=1,elapsed_ms=10)))
ck('m04 negative calls/time rejected',not valid('LibraryAccounting',dict(account,provider_calls_observed=-1)) and not valid('LibraryAccountingItem',dict(row,elapsed_ms=-1)))
ck('m04 bounded 200 item page positive, 201 negative',valid('LibraryAccountingItemPage',{'items':[row]*200,'next_cursor':None,'snapshot_id':'s'}) and not valid('LibraryAccountingItemPage',{'items':[row]*201,'next_cursor':None,'snapshot_id':'s'}))
ck('m01 summary-only with bounded items and exact exports',overlay['/api/v2/rename-plans/{id}']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('PlanSummary') and 'items' not in defs['PlanSummary']['properties'] and defs['PlanItemPage']['properties']['items']['maxItems']==200 and '/api/v2/rename-plans/{id}/exports' in overlay)

failed=[x for x in checks if not x['passed']]
print(json.dumps({'kind':'FOCUSED_INDEPENDENT_D0_DESIGN_NOT_RUNTIME','checks':len(checks),'passed':len(checks)-len(failed),'failed':failed,'details':checks,'product_gate0':False,'application_imports':False,'database':':memory:','disk_actions':0},ensure_ascii=False,indent=2))
raise SystemExit(1 if failed else 0)
