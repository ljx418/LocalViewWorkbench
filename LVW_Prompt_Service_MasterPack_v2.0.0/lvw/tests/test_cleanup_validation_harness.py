"""Reject stale or altered validation packets before product imports/process starts."""
import importlib.util
import json
from pathlib import Path
import time
import asyncio

import pytest

PACK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('cleanup_harness_v3_test', PACK / 'reports/resource-cleanup/correction-02/live_harness_v3.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


@pytest.fixture
def seal(tmp_path, monkeypatch):
    root = tmp_path / 'pack'; root.mkdir()
    base = tmp_path / 'harness'; base.mkdir()
    out = base / 'runs/test'; out.mkdir(parents=True)
    grant = root / HARNESS.authority.COMPLETE_APPROVAL; grant.parent.mkdir(parents=True); grant.write_text('grant')
    private = tmp_path / 'lvw-cleanup-v3-owned'; private.mkdir(mode=0o700)
    marker = '{"run":"test"}'; (private / 'owner-marker.json').write_text(marker)
    stat = private.stat()
    frozen = root / 'source.py'; frozen.write_text('frozen source')
    critical = [frozen]
    for relative in HARNESS.CRITICAL_INPUTS:
        item = root / relative; item.parent.mkdir(parents=True, exist_ok=True); item.write_text('trusted helper'); critical.append(item)
    data = private / 'data'; data.mkdir(mode=0o700); ds = data.stat()
    tools = {}
    for name in ['python', 'chromium', 'nvidia-smi']:
        path = root / name; path.write_text('tool')
        tools[name] = {'path': str(path), 'sha256': HARNESS.authority.digest(path)}
    tool_file = out / 'bindings.json'; tool_file.write_text(json.dumps(tools))
    child_path = out / 'authorization.json'
    child = {'kind': 'RESOURCE_CLEANUP_V3_CHILD/1', 'run_id': 'test', 'program': HARNESS.authority.COMPLETE_APPROVAL,
        'program_sha256': HARNESS.authority.digest(grant), 'fixture': True,
        'expires_at': time.time() + 60, 'budget': {'model_calls': 0, 'provider_calls': 0},
        'frozen_files': [{'path': str(item.relative_to(root)), 'sha256': HARNESS.authority.digest(item)} for item in critical],
        'chromium_executable': str(root / 'chromium'), 'data_identity': [ds.st_dev, ds.st_ino, ds.st_uid],
        'harness_sha256': HARNESS.authority.digest(Path(HARNESS.__file__)), 'private_root': str(private),
        'private_marker': marker, 'private_identity': [stat.st_dev, stat.st_ino, stat.st_uid], 'data_root': str(private / 'data')}
    child_path.write_text(json.dumps(child))
    row = {'active': 1, 'calls': 0, 'expires': time.time() + 60, 'child_path': str(child_path),
           'child_hash': HARNESS.authority.digest(child_path), 'bindings_path': str(tool_file),
           'bindings_hash': HARNESS.authority.digest(tool_file)}
    monkeypatch.setattr(HARNESS, 'WRITE_ROOTS', (out, private))
    monkeypatch.setattr(HARNESS, 'actual_tools', lambda child: {**{name: item['path'] for name, item in tools.items()}, 'chromium': child['chromium_executable']})
    monkeypatch.setattr(HARNESS, 'ROOT', root)
    monkeypatch.setattr(HARNESS, 'BASE', base)
    monkeypatch.setattr(HARNESS.authority, 'approved', lambda _: {})
    monkeypatch.setattr(HARNESS, 'ledger_row', lambda _: row)
    monkeypatch.setenv('LVW_AUTHORIZATION_CHILD', str(child_path))
    return child_path, child, row, frozen, private


def test_valid_packet_passes_prestart_without_importing_product(seal):
    path, child, *_ = seal
    assert HARNESS.validate(path)['run_id'] == child['run_id']


def test_claim_replay_refused_before_product_or_process_start(seal):
    path, *_ = seal
    (path.parent / 'run.claim').write_text('already claimed')
    with pytest.raises(FileExistsError): asyncio.run(HARNESS.run(path))


@pytest.mark.parametrize('change', ['expired', 'model_calls', 'child_hash', 'inactive', 'source_drift', 'tool_drift', 'root_identity', 'marker', 'symlink', 'data_path', 'data_symlink', 'descendant_symlink', 'chromium_path', 'data_preexisting', 'critical_manifest'])
def test_prestart_refuses_changed_or_unauthorized_inputs(seal, change):
    path, child, row, frozen, private = seal
    if change == 'expired': child['expires_at'] = time.time() - 1
    if change == 'model_calls': child['budget']['model_calls'] = 1
    if change == 'child_hash': row['child_hash'] = 'bad'
    if change == 'inactive': row['active'] = 0
    if change == 'source_drift': frozen.write_text('changed')
    if change == 'tool_drift': (frozen.parent / 'python').write_text('changed tool')
    if change == 'root_identity': child['private_identity'][1] += 1
    if change == 'marker': (private / 'owner-marker.json').write_text('other owner')
    if change == 'symlink':
        renamed = private.with_name(private.name + '-old'); private.rename(renamed); private.symlink_to(renamed)
    if change == 'data_path': child['data_root'] = str(private.parent / 'other')
    if change == 'data_symlink':
        data = private / 'data'; data.rmdir(); outside = private.parent / 'outside'; outside.mkdir(); data.symlink_to(outside)
    if change == 'descendant_symlink':
        (private / 'data/media').symlink_to(private.parent)
    if change == 'chromium_path': child['chromium_executable'] = str(frozen)
    if change == 'data_preexisting': (private / 'data/unexpected').write_text('user material')
    if change == 'critical_manifest': child['frozen_files'] = [item for item in child['frozen_files'] if item['path'] == 'source.py']
    path.write_text(json.dumps(child))
    if change != 'child_hash': row['child_hash'] = HARNESS.authority.digest(path)
    with pytest.raises(ValueError): HARNESS.validate(path)


@pytest.mark.parametrize('fault', ['nonzero', 'ledger_read', 'settle', 'retain'])
def test_terminal_faults_are_nonzero_unknown_or_actual_not_fabricated_zero(seal, monkeypatch, fault):
    path, child, row, *_ = seal
    row['calls'] = 1 if fault in {'nonzero', 'retain'} else 0
    def read(_):
        if fault == 'ledger_read': raise OSError('ledger down')
        return row
    def settle(*_):
        if fault == 'settle': raise OSError('settlement down')
        row['active'] = 0
        return {'settled': True}
    def retain(*_):
        if fault == 'retain': raise OSError('retain down')
        row['active'] = 2
    monkeypatch.setattr(HARNESS, 'ledger_row', read)
    monkeypatch.setattr(HARNESS.authority, 'settle', settle)
    monkeypatch.setattr(HARNESS.authority, 'close_retaining_reservation', retain)
    result = {'status': 'PASS_FIXTURE_ONLY'}; errors = []
    assert not HARNESS.finalize_budget(child, result, True, errors)
    assert result['status'] == 'FAIL_OR_BLOCKED' and errors
    assert result['model_actions'] is None if fault == 'ledger_read' else result['model_actions'] == row['calls']
    if fault == 'retain': assert any(error['step'] == 'budget.retain' for error in errors)
    HARNESS.write(path.parent / 'receipt.json', result)
    assert json.loads((path.parent / 'receipt.json').read_text())['status'] == 'FAIL_OR_BLOCKED'


def test_success_requires_successful_exact_zero_settlement(seal, monkeypatch):
    _, child, row, *_ = seal
    monkeypatch.setattr(HARNESS.authority, 'settle', lambda *args: {'settled': True})
    result = {'status': 'PASS_FIXTURE_ONLY'}; errors = []
    assert HARNESS.finalize_budget(child, result, True, errors)
    assert result['model_actions'] == 0 and result['authorization_terminal']['settled']


def test_start_failure_preserves_native_history_identity_and_proof(seal):
    from types import SimpleNamespace
    path, _, _, _, private = seal
    native = {'nonce': 'known', 'owner': private / 'data/owner.json'}
    value = {'nonce': 'known', 'pid': 321, 'birth_ticks': 12345, 'state': 'exited', 'listener_owned': False}
    HARNESS.write(native['owner'], value)
    runtime = SimpleNamespace(_native_history=[native], _native=None)
    errors = []
    known, actual = HARNESS.native_terminal(runtime, None, {}, path.parent, errors)
    assert known and actual == value and not errors
    proof = json.loads((path.parent / 'native-final.json').read_text())
    assert proof['identity_retained_in_runtime_history'] and proof['matched']


def test_bad_native_proof_archival_does_not_skip_terminal_receipt(seal, monkeypatch):
    from types import SimpleNamespace
    path, _, _, _, private = seal
    native = {'nonce': 'known', 'owner': private / 'data/owner.json'}
    HARNESS.write(native['owner'], {'nonce': 'known', 'pid': 321, 'birth_ticks': 12345,
                                 'state': 'exited', 'listener_owned': False})
    original = HARNESS.write
    def write(dest, value):
        if dest.name == 'native-final.json': raise OSError('proof file denied')
        return original(dest, value)
    monkeypatch.setattr(HARNESS, 'write', write)
    errors = []
    known, _ = HARNESS.native_terminal(SimpleNamespace(_native_history=[native], _native=None), None, {}, path.parent, errors)
    assert not known and errors[0]['step'] == 'native.proof_or_archive'
    HARNESS.write(path.parent / 'receipt.json', {'status': 'FAIL_OR_BLOCKED', 'errors': errors})
    assert (path.parent / 'receipt.json').is_file()


def test_unknown_prepared_native_is_not_classified_as_never_spawned(seal):
    from types import SimpleNamespace
    path, _, _, _, private = seal
    native = {'nonce': 'known', 'owner': private / 'data/missing-owner.json'}
    known, value = HARNESS.native_terminal(SimpleNamespace(_native_history=[native], _native=None), None, {}, path.parent, [])
    assert not known and value == {}


def test_safe_output_refuses_symlink_and_hardlink(seal):
    path, _, _, _, private = seal
    user_file = private / 'original'; user_file.write_text('untouched')
    alias = path.parent / 'receipt.json'; alias.symlink_to(user_file)
    with pytest.raises(OSError): HARNESS.write(alias, {'unsafe': True})
    alias.unlink(); alias.hardlink_to(user_file)
    with pytest.raises(ValueError): HARNESS.write(alias, {'unsafe': True})
    assert user_file.read_text() == 'untouched'
