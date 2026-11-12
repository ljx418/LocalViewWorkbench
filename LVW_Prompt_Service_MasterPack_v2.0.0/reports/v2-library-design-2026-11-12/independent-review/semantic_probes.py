"""Bounded review evidence: JSON/schema/static inspection and SQLite :memory: only.

Exit 1 means the two reviewed design-contract obligations are not satisfied;
it is not an application/runtime/native test result. No application imports.
"""
import sys
sys.dont_write_bytecode = True
def deny_external(event, args):
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn')) or event in ('os.system', 'os.fork', 'os.forkpty'):
        raise RuntimeError('REVIEW_EXTERNAL_ACTION_FORBIDDEN:' + event)
sys.addaudithook(deny_external)
import json
import sqlite3
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
C = ROOT / 'contracts/candidates/v2-library'
schema = json.loads((C / 'library.schema.json').read_text())
overlay = json.loads((C / 'openapi-overlay.json').read_text())
observations = []
def record(name, value):
    observations.append({'name': name, 'actual': value})

for path, definition in [('/api/v2/assets/{id}/description', 'AssetDescriptionRevision'),
                         ('/api/v2/naming-templates/{id}', 'NamingTemplateRevision')]:
    response = overlay['add_paths'][path]['get']['responses']['200']
    body = schema['$defs'][definition]
    record(definition + ':body_etag_declared', 'etag' in body['properties'])
    record(definition + ':response_etag_header_declared', any(k.lower() == 'etag' for k in response.get('headers', {})))
    record(definition + ':additional_properties', body['additionalProperties'])

db = sqlite3.connect(':memory:')
db.execute('PRAGMA foreign_keys=ON')
db.executescript((ROOT / 'contracts/storage.sql').read_text())
db.executescript((C / 'storage-additions.sql').read_text())
db.execute("INSERT INTO source_root VALUES ('r','server-only-root','root','v','root-id','[]',1,'active','e','now')")
for suffix in ('1', '2'):
    db.execute("INSERT INTO asset VALUES(?, 'image', 'm', 'title', '[]', '{}', 0)", ('a'+suffix,))
    db.execute("INSERT INTO source_file VALUES(?, 'r', ?, ?, 'v', ?, 'hash', 1, '1', '1', '1', 1, 'available', 'e')", ('s'+suffix, 'original'+suffix+'.jpg', 'original'+suffix+'.jpg', 'physical'+suffix))
    db.execute("INSERT INTO asset_description_revision VALUES(?, ?, NULL, NULL, '[]', '[]', '[]', NULL, 'hash', 'human', 'now')", ('d'+suffix, 'a'+suffix))
db.execute("INSERT INTO naming_template_head VALUES('t',NULL,'e')")
db.execute("INSERT INTO naming_template_revision VALUES('tr','t',NULL,'{}','hash','now')")
db.execute("INSERT INTO rename_plan_head VALUES('p',NULL,'e')")
db.execute("INSERT INTO rename_plan_revision VALUES('pr','p',1,NULL,'forward',NULL,'tr','hash','{}','now')")
db.execute("INSERT INTO rename_plan_item VALUES('pr','i1','s1','d1','r','same.jpg',1,'{}')")
try:
    db.execute("INSERT INTO rename_plan_item VALUES('pr','i2','s2','d2','r','same.jpg',2,'{}')")
    collision_error = None
except sqlite3.IntegrityError as error:
    collision_error = str(error)
record('duplicate-target-preview-second-row', collision_error)
record('duplicate-target-preview-retained-row-count', db.execute('SELECT COUNT(*) FROM rename_plan_item').fetchone()[0])
record('memory-ddl-integrity', db.execute('PRAGMA integrity_check').fetchone()[0])
record('memory-ddl-foreign-key-errors', db.execute('PRAGMA foreign_key_check').fetchall())
db.close()

defs = schema['$defs']
record('GET-plan-response-schema', overlay['add_paths']['/api/v2/rename-plans/{id}']['get']['responses']['200']['content']['application/json']['schema'])
record('PlanSummary-has-items', 'items' in defs['PlanSummary']['properties'])
record('PlanSummary-additional-properties', defs['PlanSummary']['additionalProperties'])
record('bounded-items-route-exists', '/api/v2/rename-plans/{id}/items' in overlay['add_paths'])
record('CreatePlan-properties', list(defs['CreatePlan']['properties']))
record('RenamePlanRevision-properties', list(defs['RenamePlanRevision']['properties']))
record('LibraryTask-properties', list(defs['LibraryTask']['properties']))
record('LibraryTask-states', defs['LibraryTask']['properties']['state']['enum'])
job = json.loads((ROOT / 'contracts/job.schema.json').read_text())['$defs']['Job']
record('canonical-Job-kinds', job['properties']['kind']['enum'])
record('canonical-Job-states', job['properties']['status']['enum'])
record('LibraryIntent-schema-defined', 'LibraryIntent' in defs)

fact = {'field':'DJ','value':'unconfirmed person','source_kind':'inference','source_ref':'r','source_revision':'v','confirmation':'confirmed','coverage':[]}
valid = lambda n, v: Draft202012Validator({'$defs':defs,'$ref':'#/$defs/'+n}).is_valid(v)
record('unconfirmed-inference-DJ-cannot-be-confirmed', not valid('FieldFact', fact))
record('creative_intent-field-rejected', not valid('FieldFact', {**fact, 'field':'creative_intent'}))
record('MCP-write-tools', json.loads((C / 'mcp-additions.json').read_text())['write_tools'])
print(json.dumps({'kind':'INDEPENDENT_D0_SEMANTIC_EVIDENCE_NOT_RUNTIME', 'observations':observations,
                  'design_obligations_unsatisfied':['M01_ETAG_TRANSPORT','M02_CONFLICT_PREVIEW_STORAGE'],
                  'product_gate0':False, 'native_actions':0}, ensure_ascii=False, indent=2))
raise SystemExit(1)
