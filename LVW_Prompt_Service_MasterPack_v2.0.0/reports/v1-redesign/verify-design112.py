from pathlib import Path
import json,copy,hashlib
from jsonschema import Draft202012Validator
p=Path(__file__).resolve().parents[2]
r=[]
def load(f):return json.loads((p/f).read_text())
def ck(n,v):
 r.append({'check':n,'passed':bool(v)})
 if not v:raise AssertionError(n)
c=load('plans/v1-multishot-contract.json');a=load('contracts/v1-multishot.openapi-overlay.json');api=load('contracts/openapi.json');s=load('contracts/v1-multishot.schema.json');core=load('contracts/lvw.schema.json')
Draft202012Validator.check_schema(s)
ck('N2 exact additive path set',set(c['additive_paths'])==set(a['add_paths']))
ck('N2 exact additive operation set',{(o['path'],o['method'].lower()) for o in c['additive_operations']}=={(p,m) for p,ops in a['add_paths'].items() for m in ops})
merged=copy.deepcopy(api)
for path,ops in a['add_paths'].items():
 for m,op in ops.items():
  ck('add method without replacement '+path+' '+m,m not in merged['paths'].get(path,{}));merged['paths'].setdefault(path,{})[m]=copy.deepcopy(op)
ck('N3 exact reuse metadata paths',set(c['reuse_paths'])==set(a['metadata_only']))
for path,ops in a['metadata_only'].items():
 for m,values in ops.items():
  ck('N3 annotated existing method '+path+' '+m,m in api['paths'][path] and all(k.startswith('x-') and k not in api['paths'][path][m] for k in values));merged['paths'][path][m].update(values)
for path,ops in a['add_response_headers'].items():
 for m,rs in ops.items():
  for status,headers in rs.items():
   target=merged['paths'][path][m]['responses'][status];ck('N1 append absent header',not(set(headers)&set(target.get('headers',{}))));target.setdefault('headers',{}).update(headers)
for path,m in [('/api/v1/scenes/{id}','get'),('/api/v1/scenes/{id}','put'),('/api/v1/scenes/{id}/revision-info','get')]:
 h=merged['paths'][path][m]['responses']['200']['headers']['ETag'];v=Draft202012Validator(h['schema']);ck('N1 strong ETag '+m+path,v.is_valid('"scene:r:'+('a'*64)+'"') and not v.is_valid('W/"scene:r:'+('a'*64)+'"'))
for path,ops in api['paths'].items():
 for m,op in ops.items():
  updated=copy.deepcopy(merged['paths'][path][m]);old=copy.deepcopy(op)
  if path in a['metadata_only'] and m in a['metadata_only'][path]:
   for k in a['metadata_only'][path][m]:updated.pop(k)
  for status,headers in a['add_response_headers'].get(path,{}).get(m,{}).items():
   for k in headers:updated['responses'][status]['headers'].pop(k)
   if not updated['responses'][status]['headers']:updated['responses'][status].pop('headers')
  ck('canonical operation preserved '+m+path,updated==old)
for k in ['source_pts','time_base_num','time_base_den']:
 prop=s['$defs']['ShotFrameRef']['properties'][k];v=Draft202012Validator(prop);ck('N4 nonnull integer no dead branch '+k,'anyOf' not in prop and v.is_valid(1) and not v.is_valid(None) and not v.is_valid(True) and not v.is_valid(1.5))
 if k!='source_pts':ck('N4 timebase minimum '+k,not v.is_valid(0))
run=load('reports/unified-media/live-15/video-model-run.json');v=Draft202012Validator({'$ref':'#/$defs/ShotFrameRef','$defs':s['$defs']});cv=Draft202012Validator({'$ref':'#/$defs/FrameRef','$defs':core['$defs']});ck('retained actual frame compatibility',all(v.is_valid(f) and cv.is_valid(f) for f in run['frames']))
m=c['scene_hash']['column_mapping'];ck('N6 all11keys mapped',set(m)==set(c['scene_hash']['fields']));ck('N6 explicit SQL aliases',m['time_base_num']=='scene_revision.tb_num' and m['time_base_den']=='scene_revision.tb_den' and 'scene_revision.version' in m['revision'])
d=c['canonical_domain_mapping'];src=d['example']['source'];entries=[json.dumps({'kind':'character','ref':src['local_actor_id'],'lang':lang,'text':src['visible_appearance'][lang]},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False) for lang in d['language_order']];ck('N5 bilingual entry example matches serialization',entries==d['example']['observation']);ck('N5 explicit order no translation raw intact',all(x in json.dumps(d) for x in ['Unicode','zero-based','No translation','raw model response byte-for-byte','No translation']))
manifest=load('.agent-governance/stages/V1-D0/spec-manifest.json');ck('authority fence exact',all(hashlib.sha256((p/f).read_bytes()).hexdigest()==h for f,h in manifest['files'].items()))
report={'kind':'OWNER_DESIGN112_PROBES_NOT_PRODUCT_ACCEPTANCE','checks':r,'failed':sum(not x['passed'] for x in r),'product_actions':0,'limitations':'Design-only synthesis and schema probes; not production adapter/handler or actual media acceptance.'}
out=p/'reports/v1-redesign/design112-owner-checks.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'checks':len(r),'failed':report['failed']}))
