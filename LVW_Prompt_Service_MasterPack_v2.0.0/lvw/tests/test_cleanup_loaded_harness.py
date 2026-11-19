"""CPU-only profile and reconciliation cases for the finite loaded validation runner."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

PACK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('cleanup_loaded_validation', PACK / 'reports/resource-cleanup/loaded-validation-01/live_harness_v6.py')
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)


@pytest.mark.parametrize('calls,status,known,expected', [
    (2, 'PASS_REAL_LOADED_RESTART_IMAGE', True, True),
    (1, 'PASS_REAL_LOADED_RESTART_IMAGE', True, False),
    (0, 'PASS_REAL_LOADED_RESTART_IMAGE', True, False),
    (3, 'FAIL_OR_BLOCKED', True, False),
    (1, 'FAIL_OR_BLOCKED', True, True),
    (0, 'FAIL_OR_BLOCKED', True, True),
    (2, 'FAIL_OR_BLOCKED', False, False),
    (None, 'FAIL_OR_BLOCKED', True, False),
])
def test_actual_debit_settlement_and_no_false_loaded_pass(monkeypatch, calls, status, known, expected):
    row = {'calls': calls, 'active': 1}; settled = []
    monkeypatch.setattr(H, 'ledger_row', lambda _: row)
    monkeypatch.setattr(H.authority, 'settle', lambda run, count: settled.append(count) or row.update(active=0))
    monkeypatch.setattr(H.authority, 'close_retaining_reservation', lambda _: row.update(active=2))
    result = {'status': status}; errors = []
    assert H.finalize_budget({'run_id': 'synthetic'}, result, known, errors) is expected
    if expected:
        assert settled == [calls] and row['active'] == 0 and result['model_actions'] == calls
    else:
        assert not settled and row['active'] == 2 and result['status'] == 'FAIL_OR_BLOCKED'


@pytest.mark.parametrize('change,expected', [('none', True), ('nonce', False), ('pid', False),
    ('birth', False), ('missing_start', False), ('late_start', False), ('wrapper_alive', False), ('extra_generation', False)])
def test_both_native_generations_require_independent_start_and_actual_exit(tmp_path, monkeypatch, change, expected):
    monkeypatch.setattr(H, 'WRITE_ROOTS', (tmp_path,))
    history, captured = [], {}
    for index in range(2):
        native = {'nonce': str(index), 'owner': tmp_path / f'{index}.json'}
        start = dict(nonce=str(index), pid=321 + index, birth_ticks=12345 + index,
                     state='listening', listener_owned=True)
        terminal = {**start, 'state': 'exited', 'listener_owned': False}
        H.write(native['owner'], terminal)
        history.append(native)
        captured[str(index)] = {'native': native, 'identity': start, 'wrapper': SimpleNamespace(returncode=0)}
    record = captured['1']
    if change == 'nonce': record['identity']['nonce'] = 'wrong'
    if change == 'pid': record['identity']['pid'] += 1
    if change == 'birth': record['identity']['birth_ticks'] += 1
    if change == 'missing_start': del captured['1']
    if change == 'late_start': record['identity']['state'] = 'exited'
    if change == 'wrapper_alive': record['wrapper'].returncode = None
    if change == 'extra_generation': history.append({'nonce': 'unknown', 'owner': tmp_path / 'unknown'})
    errors = []
    actual, _ = H.native_terminal(SimpleNamespace(_native_history=history), captured, tmp_path, errors)
    assert actual is expected
    if change != 'extra_generation':
        archived = json.loads((tmp_path / 'native-final.json').read_text())
        assert len(archived['generations']) == 2 and archived['matched'] is expected

from test_cleanup_validation_harness import seal


@pytest.mark.parametrize('change', ['valid', 'second_start', 'wrong_count', 'wrong_cap', 'fixture', 'budget', 'sample', 'model'])
def test_loaded_seal_before_start_and_second_generation(seal, monkeypatch, change):
    path, child, row, frozen, _ = seal
    root = frozen.parent
    monkeypatch.setattr(H, 'ROOT', root)
    monkeypatch.setattr(H, 'BASE', path.parent.parent.parent)
    monkeypatch.setattr(H.authority, 'approved', lambda _: {})
    monkeypatch.setattr(H, 'ledger_row', lambda _: row)
    bindings_path = Path(row['bindings_path']); bindings = json.loads(bindings_path.read_text())
    for key in ['ollama', 'powershell', 'wslpath']:
        tool = root / key; tool.write_text('synthetic tool')
        bindings[key] = {'path': str(tool), 'sha256': H.authority.digest(tool)}
    bindings_path.write_text(json.dumps(bindings)); row['bindings_hash'] = H.authority.digest(bindings_path)
    monkeypatch.setattr(H, 'actual_tools', lambda _: {k: v['path'] for k, v in bindings.items()})
    image = root / 'reports/unified-media/dev-image.png'; image.parent.mkdir(parents=True); image.write_bytes(b'fixture')
    child.update(kind='RESOURCE_CLEANUP_V6_LOADED_CHILD/1', fixture=False,
        model_tag='gemma4:26b', model_digest='5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251',
        harness_sha256=H.authority.digest(Path(H.__file__)),
        samples=[{'path': 'reports/unified-media/dev-image.png', 'sha256': H.authority.digest(image)}],
        budget={'model_calls': 2, 'provider_calls': 2, 'api_starts': 1, 'ollama_starts': 2, 'headless_browser_starts': 1, 'full_checkpoints': 0})
    row['cap'] = 2
    if change in {'second_start', 'wrong_count'}: row['calls'] = 1
    if change == 'wrong_cap': row['cap'] = 3
    if change == 'fixture': child['fixture'] = True
    if change == 'budget': child['budget']['ollama_starts'] = 3
    if change == 'sample': child['samples'][0]['sha256'] = '0' * 64
    if change == 'model': child['model_digest'] = '0' * 64
    path.write_text(json.dumps(child)); row['child_hash'] = H.authority.digest(path)
    if change in {'valid', 'second_start'}:
        assert H.validate(path, 1 if change == 'second_start' else 0)['run_id'] == 'test'
    else:
        with pytest.raises(ValueError): H.validate(path)
