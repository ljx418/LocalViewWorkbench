"""Architecture probes only: candidate schemas, budget arithmetic and in-memory DDL."""
from pathlib import Path
import json,hashlib,sqlite3,copy
from jsonschema import Draft202012Validator
r=Path(__file__).resolve().parents[2];out=Path(__file__).parent;checks=[]
def ck(name,value):
 checks.append({'check':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
schema=json.loads((r/'contracts/v1-multishot.schema.json').read_text());Draft202012Validator.check_schema(schema);ck('metaschema',True)
core=json.loads((r/'contracts/lvw.schema.json').read_text());ck('canonical scene alias exact',schema['$defs']['CoreScene']==core['$defs']['Scene'])
run=json.loads((r/'reports/unified-media/live-15/video-model-run.json').read_text())
validator=Draft202012Validator({'$ref':'#/$defs/ShotFrameRef','$defs':schema['$defs']})
for frame in run['frames']:validator.validate(frame)
ck('all4 retained real frame references also valid ShotFrameRef',True)
samples=json.loads((r/'plans/v1-multishot-sample-design.json').read_text());ck('12 clips47shots21cuts',len(samples['clips'])==12 and sum(x['shots'] for x in samples['clips'])==47 and sum(x['hard_cut_annotations'] for x in samples['clips'])==21)
quality=samples['quality_subset'];ck('explicit18selected12simple3ambiguous3static',len(quality)==18 and {k:sum(x['category']==k for x in quality) for k in samples['quality_counts']}==samples['quality_counts'])
ck('quality indices resolve before materialization',all(1<=int(x['shot_id'][1:])<=next(c['shots'] for c in samples['clips'] if c['id']==x['clip_id']) for x in quality))
plan=json.loads((r/'plans/v1-revised-plan.json').read_text());b=plan['checkpoint_budget'];estimate=53*300+12*180+65*30+300+7*35+180;ck('budget estimate arithmetic20735',estimate==b['estimated_total_seconds']==20735 and estimate<=b['wall_seconds']==21600)
ck('largest parent covers12hard child caps plus90',450*12+90==5490)
overlay=json.loads((r/'contracts/v1-multishot.openapi-overlay.json').read_text());api=json.loads((r/'contracts/openapi.json').read_text())
ck('overlay replaces no existing method',all(method not in api['paths'].get(path,{}) for path,ops in overlay['add_paths'].items() for method in ops))
ck('generic V2batch untouched','/api/v1/jobs/batch' not in overlay['add_paths'])
def hash_scene(*args):
 keys=['media_ref_id','media_sha256','revision','start_pts','end_pts','origin_pts','time_base_num','time_base_den','editor','time_basis','verified'];data=dict(zip(keys,args));data['verified']=bool(data['verified'])
 if data['editor'] not in ['algorithm','human']:raise ValueError('invalid legacy editor')
 return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
base=(r/'contracts/storage.sql').read_text();migration=(r/'contracts/v1-multishot-migration.sql').read_text()
def fixture(bad=False):
 c=sqlite3.connect(':memory:');c.executescript(base);c.execute("INSERT INTO schema_version VALUES(1,'before')")
 c.execute("INSERT INTO media_ref VALUES('m',?,'video','{}',NULL,NULL,'before')",('invalid' if bad else 'a'*64,))
 c.execute("INSERT INTO scene_revision VALUES('s','m',1,0,10,0,1,25,'algorithm')")
 c.execute("INSERT INTO shot VALUES('manual','title',NULL,'{}','etag',NULL,'before')")
 c.execute("INSERT INTO prompt_revision VALUES('r','manual',NULL,'human','{}','unchanged','before','key')");c.commit();c.create_function('lvw_scene_hash',11,hash_scene,deterministic=True);return c
c=fixture();c.executescript(migration);ck('candidate migration executes',True)
ck('old manual revision retained',c.execute("SELECT content_sha256 FROM prompt_revision WHERE id='r'").fetchone()[0]=='unchanged')
ck('manual/image shot not force-bound',c.execute('SELECT count(*) FROM shot_scene_binding').fetchone()[0]==0)
row=c.execute('SELECT scene_id,verified,time_basis,content_sha256 FROM scene_revision_meta').fetchone();ck('old scene id retained but not falsely verified',row[:3]==('s',0,'unverified'))
ck('exact scene hash derivation',row[3]==hash_scene('m','a'*64,1,0,10,0,1,25,'algorithm','unverified',0))
try:c.execute("UPDATE scene_revision SET end_pts=20 WHERE id='s'");ck('scene immutable trigger',False)
except sqlite3.IntegrityError:ck('scene immutable trigger',True)
for name in ['parent','child']:
 c.execute('INSERT INTO job VALUES(?,?,?, ?,?,NULL,0,?,NULL,?,?)',(name,'batch' if name=='parent' else 'analyze','queued',name,name,'{}','before','before'))
c.execute("INSERT INTO shot_batch_parent VALUES('parent',?,1,'before','deadline',540,NULL)",('b'*64,))
try:c.execute("INSERT INTO shot_batch_seal VALUES('parent',?,'now')",('b'*64,));ck('missing child cannot seal',False)
except sqlite3.IntegrityError:ck('missing child cannot seal',True)
c.execute("INSERT INTO shot_batch_item VALUES('parent',0,'child','manual','s',?,?,?,NULL)",('c'*64,'a'*64,'d'*64))
c.execute("INSERT INTO shot_batch_seal VALUES('parent',?,'now')",('b'*64,));ck('complete ordered structural plan seals',True)
try:c.execute("DELETE FROM shot_batch_item WHERE parent_job_id='parent'");ck('sealed plan cannot shrink',False)
except sqlite3.IntegrityError:ck('sealed plan cannot shrink',True)
ck('foreign key integrity',c.execute('PRAGMA foreign_key_check').fetchall()==[]);c.close()
c=fixture(True)
try:c.executescript(migration);ck('bad legacy hash failclosed',False)
except sqlite3.IntegrityError:
 c.rollback();ck('bad legacy hash failclosed',True);ck('failed migration rolls back DDL and version',c.execute("SELECT count(*) FROM sqlite_master WHERE name='scene_head'").fetchone()[0]==0 and c.execute('SELECT max(version) FROM schema_version').fetchone()[0]==1)
c.close()
(out/'design11-checks.json').write_text(json.dumps({'kind':'ARCHITECTURE_PROBES_NOT_PRODUCT_ACCEPTANCE','checks':checks,'failed':sum(not x['passed'] for x in checks),'product_actions':0,'limits':'SQL probes only structural constraints, not unimplemented application handlers; samples not yet materialized'},indent=2)+'\n')
print(json.dumps({'checks':len(checks),'failed':0,'product_actions':0}))
