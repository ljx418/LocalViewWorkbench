"""Read-only frozen R1 recipe validation, before reserving or starting a real child."""
import hashlib
import json
from pathlib import Path

# Approved Gate0 packet; changing both a recipe and its local manifest cannot self-authorize.
PACKET_SHA256 = '38ca0ae572cc74a412a411635e04f21bce3fdcd29d51456fde677f188dd9f307'

CASES = {
    'NV-DURATION': ('duration', 'MEDIA_LIMIT_EXCEEDED'),
    'NV-CORRUPT': ('corrupt', 'MEDIA_INVALID'),
    'NV-FORMAT': ('format', 'MEDIA_INVALID'),
    'NV-TRUNCATED': ('corrupt', 'MEDIA_INVALID'),
    'NV-PIXELS': ('pixels', 'MEDIA_LIMIT_EXCEEDED'),
    'NV-BYTES': ('bytes', 'MEDIA_LIMIT_EXCEEDED'),
    'NV-EMPTY': ('empty', 'MEDIA_INVALID'),
}

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def load(root, active_program):
    root = Path(root)
    packet = root / '.agent-governance/stages/R1'
    control = json.loads((packet / 'stage-control.json').read_text())
    assert control['stage_packet_version'] == '1.0.4'
    assert active_program.get('global_only') is True, 'new recipe requires complete03'
    assert control['program_authorization'] == 'reports/authorization-program-v1-complete-03.approval.json'
    assert sha(packet / 'PAYLOAD_MANIFEST.sha256') == PACKET_SHA256, 'unreviewed packet amendment'
    leaves = set()
    for line in (packet / 'PAYLOAD_MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert name == Path(name).name and name not in leaves
        assert sha(packet / name) == digest, 'frozen packet digest mismatch'
        leaves.add(name)
    assert {p.name for p in packet.iterdir() if p.is_file() and p.name != 'PAYLOAD_MANIFEST.sha256'} == leaves
    assert control['real_acceptance_recipe'] == '09-real-acceptance-recipe.json'
    recipe_path = packet / control['real_acceptance_recipe']
    assert sha(recipe_path) == control['recipe_sha256']
    amendment_path = root / control['internal_amendment']
    assert control['internal_amendment'] == 'reports/unified-media/change-decision-owner-input-04.json'
    assert sha(amendment_path) == control['internal_amendment_sha256']
    amendment = json.loads(amendment_path.read_text())
    assert amendment['decision'] == 'APPROVED_FOR_INTERNAL_IMPLEMENTATION_NOT_STAGE_PASS'
    assert all(amendment[k] is False for k in ('public_schema_changed', 'fixed_denominator_changed', 'quality_resource_thresholds_changed', 'stage_pass_claim'))
    assert sha(root / amendment['authority']) == amendment['approval_sha256']
    for path, field in (('contracts/openapi.json', 'public_openapi_sha256'), ('contracts/lvw.schema.json', 'public_prompt_schema_sha256')):
        assert sha(root / path) == control[field], 'protected public contract changed'
    recipe = json.loads(recipe_path.read_text())
    validate_structure(recipe, json.loads((root / 'reports/unified-media/authorization-runtime-transition-01.request.json').read_text())['samples'])
    preparation = root / recipe['asset_preparation_receipt']
    assert recipe['asset_preparation_receipt'] == 'reports/unified-media/real-rejection-fixtures-04/receipt.json'
    assert sha(preparation) == recipe['asset_preparation_receipt_sha256']
    prep = json.loads(preparation.read_text())
    assert prep['decision'] == 'FIXTURES_READY_NOT_PRODUCT_PASS' and prep['artifacts_usable_for_acceptance'] is True
    assert prep['tool_cleanup_proven'] is True and prep['declared_input_retention'] is True
    external = Path(recipe['owned_external_input_root'])
    expected = root.parent.parent / '.lvw-runtime/lvw-prompt-service/R1-unified-fixtures/real-rejection-fixtures-04'
    assert external.samefile(expected) and not external.is_symlink()
    assert Path(prep['owned_artifact_root']).samefile(external)
    assert sha(external / 'owner.json') == recipe['owner_marker_sha256']
    external_items = {item['path']: item for item in prep['items']}
    for item in recipe['samples']:
        path = root / item['path']
        validate_sample_path(root, path, external)
        if Path(item['path']).is_absolute():
            assert {k: external_items[item['path']][k] for k in ('path', 'sha256', 'bytes')} == item
        assert path.is_file() and path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
    return recipe

def validate_structure(recipe, original_four):
    assert recipe['version'] == '1.0.4'
    samples = recipe['samples']
    assert len(samples) == 9 and len({s['path'] for s in samples}) == 9
    assert [{k:s[k] for k in ('path','sha256')} for s in samples[:4]] == original_four
    assert recipe['positive_samples'] == samples[:2]
    assert recipe['original_four_bindings_preserved'] is True
    assert recipe['source_video_quality_replacement_forbidden'] is True
    assert recipe['holdouts_model_calls'] == 0 and recipe['request_configuration_receipts_required'] is True
    assert recipe['cancellation_cases'] == ['queued', 'preparing', 'running']
    cases = recipe['negative_cases']
    assert len(cases) == 7 and {c['id'] for c in cases} == set(CASES)
    assert {c['category'] for c in cases} == set(recipe['required_negative_categories']) == {v[0] for v in CASES.values()}
    assert [{k:c[k] for k in ('path','sha256','bytes')} for c in cases] == samples[2:]
    for case in cases:
        assert (case['category'], case['expected_error']) == CASES[case['id']]
        assert case['expected_status'] == 422


def validate_sample_path(root, path, external):
    """Reject lexical traversal and symlink components before opening sample bytes."""
    root, path, external = Path(root), Path(path), Path(external)
    allowed = root if path.is_relative_to(root) else external
    assert '..' not in path.parts
    assert not path.is_symlink() and path.resolve().is_relative_to(allowed.resolve())
    cursor = path
    while cursor != allowed:
        assert not cursor.is_symlink(), 'symlink in controlled sample path'
        cursor = cursor.parent
        assert cursor != cursor.parent, 'sample path escaped owner root'
