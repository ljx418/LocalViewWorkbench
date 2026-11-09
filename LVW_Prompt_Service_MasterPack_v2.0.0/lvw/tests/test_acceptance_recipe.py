"""CPU-only anti-shrink checks on the real-checkpoint recipe (no model or service)."""
import copy
import importlib
import json
from pathlib import Path
import pytest

recipe_module = importlib.import_module('reports.unified-media.acceptance_recipe')
ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / '.agent-governance/stages/R1/09-real-acceptance-recipe.json'
ORIGINAL = ROOT / 'reports/unified-media/authorization-runtime-transition-01.request.json'

def inputs():
    return json.loads(RECIPE.read_text()), json.loads(ORIGINAL.read_text())['samples']

def test_recipe_keeps_original_source_and_complete_real_cases():
    recipe_module.validate_structure(*inputs())

@pytest.mark.parametrize('mutation', ['missing_case','duplicate_case','changed_positive','wrong_error',
    'wrong_status','missing_category','missing_cancel_phase','replacement_tracking','missing_request_receipts',
    'holdout_calls','duplicate_sample'])
def test_recipe_cannot_shrink_or_replace(mutation):
    recipe, original = inputs()
    if mutation == 'missing_case': recipe['negative_cases'].pop()
    if mutation == 'duplicate_case': recipe['negative_cases'][-1] = copy.deepcopy(recipe['negative_cases'][0])
    if mutation == 'changed_positive': recipe['positive_samples'][0]['sha256'] = '0'*64
    if mutation == 'wrong_error': recipe['negative_cases'][0]['expected_error'] = 'MEDIA_INVALID'
    if mutation == 'wrong_status': recipe['negative_cases'][0]['expected_status'] = 200
    if mutation == 'missing_category': recipe['required_negative_categories'].pop()
    if mutation == 'missing_cancel_phase': recipe['cancellation_cases'].remove('preparing')
    if mutation == 'replacement_tracking':
        recipe['samples'][1]['sha256']='0'*64
        recipe['positive_samples'][1]['sha256']='0'*64
    if mutation == 'missing_request_receipts': recipe['request_configuration_receipts_required']=False
    if mutation == 'holdout_calls': recipe['holdouts_model_calls']=1
    if mutation == 'duplicate_sample': recipe['samples'][-1]=copy.deepcopy(recipe['samples'][0])
    with pytest.raises(AssertionError): recipe_module.validate_structure(recipe, original)

@pytest.mark.parametrize('program', [{}, {'global_only':False}])
def test_legacy_program_cannot_activate_new_recipe(program):
    with pytest.raises(AssertionError, match='complete03'): recipe_module.load(ROOT,program)

@pytest.mark.parametrize('kind',['outside','traversal','symlink','directory_symlink'])
def test_sample_cannot_escape_declared_owned_roots(tmp_path,kind):
    root=tmp_path/'repo';root.mkdir();external=tmp_path/'owned';external.mkdir()
    other=tmp_path/'outside';other.mkdir();(other/'x').write_bytes(b'x')
    if kind=='outside': path=other/'x'
    if kind=='traversal': path=root/'..'/'outside'/'x'
    if kind=='symlink':
        path=external/'link';path.symlink_to(other/'x')
    if kind=='directory_symlink':
        (external/'link').symlink_to(other,target_is_directory=True);path=external/'link'/'x'
    with pytest.raises(AssertionError):recipe_module.validate_sample_path(root,path,external)


def test_sample_stays_in_declared_roots(tmp_path):
    root=tmp_path/'repo';root.mkdir();external=tmp_path/'owned';external.mkdir()
    for base in [root,external]:
        path=base/'x';path.write_bytes(b'x');recipe_module.validate_sample_path(root,path,external)


def test_actual_owned_recipe_load_from_project_root_case_aliases():
    """Read-only asset/hash check; no reserve, model, decode or network operation."""
    recipe=json.loads(RECIPE.read_text())
    if not Path(recipe['owned_external_input_root']).exists():
        pytest.skip('machine-owned rejection inputs not present; real executor still fails closed')
    loaded=recipe_module.load(ROOT,{'global_only':True})
    assert len(loaded['samples'])==9
    lower=Path(str(ROOT).lower())
    if lower.exists() and lower.samefile(ROOT):
        assert recipe_module.load(lower,{'global_only':True})==loaded
