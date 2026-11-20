"""Review06 regression: exercise terminal owner and real Git-object comparison."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

PACK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('cleanup_v7_review06', PACK / 'reports/resource-cleanup/correction-05/live_harness_v7.py')
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)


@pytest.fixture
def terminal(tmp_path, monkeypatch):
    row = {'calls': 2, 'active': 1}; order = []
    monkeypatch.setattr(H, 'WRITE_ROOTS', (tmp_path,))
    monkeypatch.setattr(H, 'ledger_row', lambda _: row)
    def settle(run, count):
        prepared = json.loads((tmp_path / 'receipt.prepared.json').read_text())
        assert prepared['status'] == 'EVIDENCE_COMPLETE_PENDING_SETTLEMENT'
        assert prepared['settlement_expected']['actual_model_actions'] == count == 2
        order.append('settle'); row['active'] = 0
        return {'actual_model_actions': count}
    monkeypatch.setattr(H.authority, 'settle', settle)
    monkeypatch.setattr(H.authority, 'close_retaining_reservation', lambda _: row.update(active=2))
    return tmp_path, row, order


def test_complete_receipt_synced_before_settlement_and_finalized(terminal, monkeypatch):
    out, row, order = terminal
    fsync = os.fsync
    def observed(fd):
        order.append('fsync'); fsync(fd)
    monkeypatch.setattr(H.os, 'fsync', observed)
    result = {'status': 'PASS_REAL_LOADED_RESTART_IMAGE'}
    assert H.finish_receipt({'run_id': 'test'}, result, True, [], out)
    assert order.index('settle') >= 2 and row['active'] == 0
    assert json.loads((out / 'receipt.json').read_text())['known_terminal']


def test_evidence_failure_never_releases_reservation(terminal, monkeypatch):
    out, row, order = terminal
    original = H.write
    def fail_prepared(path, value):
        if path.name == 'receipt.prepared.json': raise OSError('disk fault')
        return original(path, value)
    monkeypatch.setattr(H, 'write', fail_prepared)
    result = {'status': 'PASS_REAL_LOADED_RESTART_IMAGE'}
    assert not H.finish_receipt({'run_id': 'test'}, result, True, [], out)
    assert row['active'] == 2 and not order and not result['known_terminal']


def test_final_receipt_failure_has_durable_evidence_but_cannot_pass(terminal, monkeypatch):
    out, row, order = terminal
    original = H.write
    def fail_final(path, value):
        if path.name == 'receipt.json': raise OSError('final write fault')
        return original(path, value)
    monkeypatch.setattr(H, 'write', fail_final)
    result = {'status': 'PASS_REAL_LOADED_RESTART_IMAGE'}
    assert not H.finish_receipt({'run_id': 'test'}, result, True, [], out)
    assert row['active'] == 0 and order == ['settle']
    assert (out / 'receipt.prepared.json').is_file() and not (out / 'receipt.json').exists()


@pytest.mark.parametrize('calls', [0, 1, 2])
def test_failed_scope_retains_full_reservation_even_after_later_good_probes(terminal, calls):
    out, row, order = terminal; row['calls'] = calls
    result = {'status': 'FAIL_OR_BLOCKED'}
    assert not H.finish_receipt({'run_id': 'test'}, result, True, [], out)
    assert row['active'] == 2 and not order and not (out / 'receipt.prepared.json').exists()


@pytest.mark.parametrize('pending,lease,accepted', [(None,None,True), ({},None,False), (None,('retained',{}),False), ({},('retained',{}),False)])
def test_pending_or_retained_lease_prevents_known_terminal(pending, lease, accepted):
    runtime = SimpleNamespace(_owned=lambda: False, _native=None, _cleanup_pending=pending)
    assert H.reconciled_runtime(runtime, SimpleNamespace(_lease=lease)) is accepted


@pytest.mark.parametrize('gpu,ram,baseline,accepted', [(1024,2048,0,True), (1025,2048,0,False),
    (1024,2047,0,False), (23551,2048,22528,True), (23552,2048,22528,False)])
def test_terminal_resource_exact_and_one_over(gpu, ram, baseline, accepted):
    assert H.terminal_sample_ok({'gpu_used_mib': gpu, 'available_ram_mib': ram}, {'gpu_used_mib': baseline}) is accepted


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path / 'repo'; root.mkdir()
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True).stdout.decode().strip()
    git('init', '-q')
    for name in ['template.txt', 'sample.png']: (root / name).write_bytes(b'candidate')
    git('add', 'template.txt', 'sample.png')
    git('-c', 'user.name=fixture', '-c', 'user.email=fixture@invalid', 'commit', '-q', '-m', 'fixture')
    entries = [{'path': name, 'sha256': H.authority.digest(root / name)} for name in ['template.txt', 'sample.png']]
    return root, git('rev-parse', 'HEAD'), entries


def test_git_candidate_matches_working_bytes(candidate):
    H.verify_candidate_files(*candidate)


@pytest.mark.parametrize('index', [0, 1])
def test_preseal_dirty_template_or_sample_cannot_be_relabelled(candidate, index):
    root, sha, entries = candidate
    target = root / entries[index]['path']; target.write_bytes(b'different working content')
    entries[index]['sha256'] = H.authority.digest(target)
    with pytest.raises(ValueError, match='CANDIDATE_WORKTREE_MISMATCH'):
        H.verify_candidate_files(root, sha, entries)


def test_untracked_manifest_item_has_no_candidate_provenance(candidate):
    root, sha, entries = candidate
    (root / 'untracked').write_bytes(b'new')
    entries.append({'path': 'untracked', 'sha256': H.authority.digest(root / 'untracked')})
    with pytest.raises(ValueError, match='CANDIDATE_BLOB_MISSING'):
        H.verify_candidate_files(root, sha, entries)


def test_private_linux_control_root_ignores_shared_application_directory(tmp_path, monkeypatch):
    from app.native_private import create_root
    import app.native_private as private
    monkeypatch.setattr(private.tempfile, 'gettempdir', lambda: str(tmp_path))
    root, script = create_root('nonce', lambda path: '\\\\wsl.localhost\\Ubuntu-24.04' + str(path))
    assert root.parent == tmp_path and root.stat().st_mode & 0o077 == 0
    assert root.stat().st_uid == os.geteuid() and not script


def test_private_root_alias_fails_before_native_start(tmp_path, monkeypatch):
    import app.native_private as private
    target = tmp_path / 'private'; target.mkdir(mode=0o700)
    alias = tmp_path / 'alias'; alias.symlink_to(target)
    monkeypatch.setattr(private.tempfile, 'gettempdir', lambda: str(tmp_path))
    monkeypatch.setattr(private.tempfile, 'mkdtemp', lambda **_: str(alias))
    with pytest.raises(ValueError, match='PRIVATE_ROOT_UNPROVEN'):
        private.create_root('nonce', lambda path: '\\\\wsl.localhost\\Ubuntu-24.04' + str(path))
