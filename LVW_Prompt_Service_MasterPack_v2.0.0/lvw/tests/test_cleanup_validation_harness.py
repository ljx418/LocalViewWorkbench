"""Reject stale or altered validation packets before product imports/process starts."""
import importlib.util
import json
from pathlib import Path
import time
import asyncio

import pytest

PACK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('cleanup_harness_v2_test', PACK / 'reports/resource-cleanup/correction-01/live_harness_v2.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


@pytest.fixture
def seal(tmp_path, monkeypatch):
    root = tmp_path / 'pack'; root.mkdir()
    base = tmp_path / 'harness'; base.mkdir()
    out = base / 'runs/test'; out.mkdir(parents=True)
    grant = root / HARNESS.authority.COMPLETE_APPROVAL; grant.parent.mkdir(parents=True); grant.write_text('grant')
    private = tmp_path / 'lvw-cleanup-v2-owned'; private.mkdir(mode=0o700)
    marker = '{"run":"test"}'; (private / 'owner-marker.json').write_text(marker)
    stat = private.stat()
    frozen = root / 'source.py'; frozen.write_text('frozen source')
    tools = {}
    for name in ['python', 'chromium', 'nvidia-smi']:
        path = root / name; path.write_text('tool')
        tools[name] = {'path': str(path), 'sha256': HARNESS.authority.digest(path)}
    tool_file = out / 'bindings.json'; tool_file.write_text(json.dumps(tools))
    child_path = out / 'authorization.json'
    child = {'kind': 'RESOURCE_CLEANUP_V2_CHILD/1', 'run_id': 'test', 'program': HARNESS.authority.COMPLETE_APPROVAL,
        'program_sha256': HARNESS.authority.digest(grant), 'fixture': True,
        'expires_at': time.time() + 60, 'budget': {'model_calls': 0, 'provider_calls': 0},
        'frozen_files': [{'path': 'source.py', 'sha256': HARNESS.authority.digest(frozen)}],
        'harness_sha256': HARNESS.authority.digest(Path(HARNESS.__file__)), 'private_root': str(private),
        'private_marker': marker, 'private_identity': [stat.st_dev, stat.st_ino, stat.st_uid], 'data_root': str(private / 'data')}
    child_path.write_text(json.dumps(child))
    row = {'active': 1, 'calls': 0, 'expires': time.time() + 60, 'child_path': str(child_path),
           'child_hash': HARNESS.authority.digest(child_path), 'bindings_path': str(tool_file),
           'bindings_hash': HARNESS.authority.digest(tool_file)}
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


@pytest.mark.parametrize('change', ['expired', 'model_calls', 'child_hash', 'inactive', 'source_drift', 'tool_drift', 'root_identity', 'marker', 'symlink', 'data_path'])
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
    path.write_text(json.dumps(child))
    if change != 'child_hash': row['child_hash'] = HARNESS.authority.digest(path)
    with pytest.raises(ValueError): HARNESS.validate(path)
