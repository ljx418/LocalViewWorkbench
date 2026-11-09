from pathlib import Path
import importlib,json,ast,hashlib,subprocess
from types import SimpleNamespace
import sys
R=Path.cwd();sys.path.insert(0,str(R));O=R/'reports/unified-media/owner-split-c2-code-review-04/recheck';O.mkdir(exist_ok=True);recipe=importlib.import_module('reports.unified-media.acceptance_recipe');checks=importlib.import_module('reports.unified-media.checkpoint_checks');from tools.local_program_authority import approved
results={'packet_manifest_sha256':recipe.sha(R/'.agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256')};active=approved()
try:
 data=recipe.load(R,active);results['actual_workspace_recipe_load']='PASS'
except AssertionError as error:
 control=json.loads((R/'.agent-governance/stages/R1/09-real-acceptance-recipe.json').read_text());declared=Path(control['owned_external_input_root']);expected=R.parent.parent/'.lvw-runtime/lvw-prompt-service/R1-unified-fixtures/real-rejection-fixtures-04';results['actual_workspace_recipe_load']={'status':'FAIL','exception':type(error).__name__,'declared_resolve':str(declared.resolve()),'expected_resolve':str(expected.resolve()),'samefile':declared.samefile(expected),'declared_symlink':declared.is_symlink()};data=recipe.load(Path(str(R).lower()),active);results['lowercase_alias_recipe_load']='PASS'
results['lowercase_alias_equal']=recipe.load(Path(str(R).lower()),active)==data
results.update(complete03_selected=active.get('global_only') is True,recipe_load_with_actual_active_program='PASS',sample_count=len(data['samples']),negative_count=len(data['negative_cases']),cancellation_cases=data['cancellation_cases'],source_tracking=data['positive_samples'][1],external_owner_sha256=recipe.sha(Path(data['owned_external_input_root'])/'owner.json'),samples=[{'path':i['path'],'bytes':(R/i['path']).stat().st_size,'sha256':recipe.sha(R/i['path'])} for i in data['samples']])
# Counterexample: failure before JSON decode must never pass; record exact diagnostic retention limit.
fixture=O/'synthetic-rejection.mp4';fixture.write_bytes(b'controlled synthetic CPU oracle input');out=O/'invalid-json-case';out.mkdir(exist_ok=True);owned=O/'owned';owned.mkdir(exist_ok=True);before=checks.residue;checks.residue=lambda *args:{'media_and_temp':[],'owned_open_files':[]}
class InvalidJSON:
 status_code=503
 text='<html>synthetic server error diagnostic</html>'
 content=text.encode()
 def json(self):raise ValueError('not JSON')
try:
 checks.negative_uploads(owned,123,[{'id':'NV-CPU','path':str(fixture),'expected_status':422,'expected_error':'MEDIA_INVALID'}],lambda *a,**kw:InvalidJSON(),out,R)
except ValueError as error:results['invalid_json_case']={'raised':type(error).__name__,'report':json.loads((out/'negative-results.json').read_text()),'response_body_retained':any(InvalidJSON.text in p.read_text() for p in out.iterdir() if p.is_file()),'raw_response_file_exists':(out/'NV-CPU-response.json').exists()}
finally:checks.residue=before
# Evaluate only one pure expression; never execute the renderer, which writes production HTML.
tree=ast.parse((R/'reports/unified-media/build_handoff.py').read_text());expression=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='completion_note' for t in n.targets));results['handoff_counterexample']={'has_outputs':True,'cancellation_result':'FAIL_OR_MISSING','completion_note':eval(compile(ast.Expression(expression),'<pure completion_note expression>','eval'),{'has_outputs':True})}
syntax=subprocess.run(['node','--check','reports/unified-media/live_browser.cjs'],capture_output=True,text=True);(O/'node-check.stdout.log').write_text(syntax.stdout);(O/'node-check.stderr.log').write_text(syntax.stderr);results['node_syntax_command']={'command':['node','--check','reports/unified-media/live_browser.cjs'],'exit_code':syntax.returncode}
results['python_ast_syntax']={f:'PASS' for f in json.loads((O.parent/'recheck-source-before.json').read_text()) if f.endswith('.py') and ast.parse((R/f).read_text())}
assert results['invalid_json_case']['report']['cases'][0]['actual_status']==503
assert results['invalid_json_case']['response_body_retained'] is True
assert results['actual_workspace_recipe_load']=='PASS' and results['lowercase_alias_equal'] is True
(O/'independent-checks.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({k:v for k,v in results.items() if k!='samples'},indent=2))
