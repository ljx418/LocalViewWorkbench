"""CLI lifecycle negatives on a tiny isolated Git tree, no target/native I/O.

Reuse actual historical offline receipt/logs for the single selected source
byte fixture. Deliberately narrow test-only payload/root patches are not a full
gate and cannot prove native acceptance. No execution logs are fabricated.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import v0_s2_stage_checkpoint as checkpoint
from tools.v0_s2_checkpoint_oracles import EvidenceError


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve(); self.root = self.directory/'candidate'; self.root.mkdir()
        self.real_root = checkpoint.ROOT
        self.offline = 'reports/v0-s2/offline-checkpoint-15/receipt.json'
        historical = json.loads((self.real_root/self.offline).read_text())
        relative = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py'
        prefix = subprocess.check_output(['git', 'rev-parse', '--show-prefix'], cwd=self.real_root, text=True).strip()
        raw = subprocess.check_output(['git', 'show', historical['candidate_sha']+':'+prefix+relative], cwd=self.real_root)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), historical['identity']['execution_artifact_sha256'][relative])
        target = self.root/relative; target.parent.mkdir(parents=True); target.write_bytes(raw)
        for name in (self.offline, checkpoint.PROGRAM, 'plans/execution-control.json', '.agent-governance/stages/V0-S2/stage-control.json', *checkpoint.SEEDS.values()):
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(self.real_root/name, path)
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.root, capture_output=True, check=True, timeout=30)
        git('init', '-q'); git('add', '.')
        git('-c', 'user.name=ljx418', '-c', 'user.email=1173696783@qq.com', 'commit', '-qm', 'isolated lifecycle fixture')
        self.candidate = git('rev-parse', 'HEAD').stdout.decode().strip()
        self.state = self.directory/'controlled-state'
        for key, value in (('ROOT', self.root), ('STATE_ROOT', self.state), ('SOURCE_PAYLOAD', [relative]), ('HARNESS', relative)):
            current = patch.object(checkpoint, key, value); current.start(); self.addCleanup(current.stop)

    def prepare(self): return checkpoint.prepare('full-checkpoint-01', self.candidate, self.offline)

    def test_prepare_creates_bound_child_without_reading_installed_tools_or_samples(self):
        with patch.object(checkpoint, 'resolve_installed') as resolve, patch.object(checkpoint, 'actual_samples') as samples:
            value = self.prepare()
        resolve.assert_not_called(); samples.assert_not_called(); self.assertFalse(self.state.exists())
        self.assertEqual('ACTIVE_ONE_SHOT', value['status']); self.assertEqual(65, value['budget']['public_submissions'])
        self.assertEqual([8191, 11434], value['ports']); self.assertFalse(value['stage_pass_claim'])
        with self.assertRaises(EvidenceError): self.prepare()

    def test_unclaimed_source_replacement_preserves_old_grant_and_never_resets_a_claim(self):
        self.prepare(); path = checkpoint.child_path('full-checkpoint-01'); original = path.read_bytes()
        (self.root/'offline-correction-note.txt').write_text('test-only source revision; no native action')
        subprocess.run(['git', 'add', '.'], cwd=self.root, capture_output=True, check=True)
        subprocess.run(['git', '-c', 'user.name=ljx418', '-c', 'user.email=1173696783@qq.com', 'commit', '-qm', 'unclaimed fixture correction'],
            cwd=self.root, capture_output=True, check=True)
        corrected = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.root, text=True).strip()
        value = checkpoint.prepare('full-checkpoint-01', corrected, self.offline, replace_unclaimed=True)
        self.assertNotEqual(json.loads(original)['authorization_id'], value['authorization_id'])
        digest = hashlib.sha256(original).hexdigest(); self.assertEqual(digest, value['previous_unclaimed_authorization_sha256'])
        archived = self.root/'reports/v0-s2/unclaimed-authorizations'/('full-checkpoint-01-'+digest+'.json')
        self.assertEqual(original, archived.read_bytes()); self.assertFalse((self.state/'full-checkpoint-01').exists())
        (self.state/'full-checkpoint-01').mkdir()
        with self.assertRaises(EvidenceError): checkpoint.prepare('full-checkpoint-01', 'f'*40, self.offline, replace_unclaimed=True)

    def test_target_binding_refusal_expires_child_and_atomically_prevents_replay(self):
        self.prepare(); path = checkpoint.child_path('full-checkpoint-01'); original = path.read_bytes()
        with patch.object(checkpoint, 'resolve_installed', side_effect=EvidenceError('synthetic metadata refusal before target I/O')) as resolve:
            result = checkpoint.execute('full-checkpoint-01')
        self.assertEqual(1, resolve.call_count); self.assertEqual('NO_GO', result['decision'])
        self.assertEqual(b'1', (self.state/'full-checkpoint-01/lease.closed').read_bytes())
        expired = json.loads(path.read_text()); self.assertEqual('EXPIRED_NO_GO', expired['status'])
        self.assertTrue((self.root/expired['terminal_receipt']).is_file())
        # Even an accidentally restored ACTIVE file cannot reset the state claim.
        path.write_bytes(original)
        shutil.rmtree(self.root/'reports/v0-s2/full-checkpoint-01')  # Simulate checkout dropping public files; state is outside it.
        with patch.object(checkpoint, 'resolve_installed') as resolve, self.assertRaises(FileExistsError):
            checkpoint.execute('full-checkpoint-01')
        resolve.assert_not_called()

    def test_public_receipt_disk_failure_still_closes_reserved_byte_and_expires_permission(self):
        self.prepare(); original_writer = checkpoint.write_new
        def failing(path, value):
            if path == self.root/'reports/v0-s2/full-checkpoint-01/receipt.json': raise OSError('synthetic disk full')
            return original_writer(path, value)
        with patch.object(checkpoint, 'resolve_installed', side_effect=EvidenceError('no target action')), \
             patch.object(checkpoint, 'write_new', side_effect=failing), self.assertRaises(OSError):
            checkpoint.execute('full-checkpoint-01')
        self.assertEqual(b'1', (self.state/'full-checkpoint-01/lease.closed').read_bytes())
        self.assertEqual('EXPIRED_NO_GO', json.loads(checkpoint.child_path('full-checkpoint-01').read_text())['status'])

    def test_changed_budget_paths_or_expiry_refuse_before_any_target_query(self):
        value = self.prepare(); path = checkpoint.child_path('full-checkpoint-01')
        for mutation in (lambda auth: auth['budget'].update(provider_calls=84),
                lambda auth: auth.update(state_root='/not-owned'), lambda auth: auth.update(expires_at=auth['issued_at']-1)):
            changed = copy.deepcopy(value); mutation(changed); path.write_bytes(checkpoint.canonical(changed))
            with self.subTest(mutation=mutation), patch.object(checkpoint, 'resolve_installed') as resolve, self.assertRaises(EvidenceError):
                checkpoint.execute('full-checkpoint-01')
            resolve.assert_not_called(); self.assertFalse(self.state.exists())

    def test_missing_raw_checks_or_wrong_unit_denominator_cannot_authorize_child(self):
        path = self.root/self.offline; receipt = json.loads(path.read_text())
        for mutation in (lambda data: data['check_results'].pop(),
                lambda data: data['check_results'][0].update(unit_tests_executed=367),
                lambda data: data['check_results'][0].update(stderr_artifact_sha256='0'*64),
                lambda data: data.update(stage_pass_claim=True)):
            value = copy.deepcopy(receipt); mutation(value); path.write_text(json.dumps(value))
            with self.subTest(mutation=mutation), self.assertRaises((EvidenceError, ValueError)): self.prepare()
            self.assertFalse(checkpoint.child_path('full-checkpoint-01').exists())

    def test_recheck_requires_different_corrected_candidate_and_no_third_slot_exists(self):
        with self.assertRaises(FileNotFoundError): checkpoint.prepare('full-recheck-01', self.candidate, self.offline)
        self.prepare()
        with patch.object(checkpoint, 'resolve_installed', side_effect=EvidenceError('no target action')):
            checkpoint.execute('full-checkpoint-01')
        with self.assertRaises(EvidenceError): checkpoint.prepare('full-recheck-01', self.candidate, self.offline)
        with self.assertRaises(EvidenceError): checkpoint.child_path('full-recheck-02')

    def test_revocation_and_terminal_close_deny_new_work_but_keep_owned_cleanup_reserved(self):
        self.prepare(); path = checkpoint.child_path('full-checkpoint-01'); lease = checkpoint.ChildLease(path, path.read_bytes())
        directory = self.directory/'lease-fixture'; directory.mkdir(); (directory/'lease.closed').write_bytes(b'0'); lease.directory = directory
        lease.authorize('unit-readonly-action', None)
        (self.root/checkpoint.PROGRAM).write_text('{}')
        with self.assertRaises(EvidenceError): lease.authorize('new-work', None)
        lease.authorize('archive_owned_terminal_root', 'registered-root-only')
        lease.close()
        with self.assertRaises(EvidenceError): lease.authorize('new-work', None)
        self.assertEqual(b'1', (directory/'lease.closed').read_bytes())


class TerminalBudgetTests(unittest.TestCase):
    def context(self, root, warm, events, *, tail=b''):
        (root/'temp').mkdir(exist_ok=True)
        path = root/('temp/lvw-warm-events.jsonl' if warm else 'temp/lvw-native-events.jsonl')
        path.write_bytes(b''.join(checkpoint.canonical(value) for value in events)+tail)
        driver = SimpleNamespace(warm_benchmark=warm, submissions=20 if warm else 45,
            preloads=20 if warm else 0, request_ledger=[], owned=[object(), object()])
        return SimpleNamespace(root=root, driver=driver)

    def test_default_and_warm_attempt_caps_exact_and_one_over(self):
        for warm, maximum in ((False, 32), (True, 50)):
            with self.subTest(warm=warm), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                events = [{'event': 'before_call' if warm else 'provider_attempt',
                    'request_number' if warm else 'run_token': index//4+1 if warm else f'{index//4+1:032x}',
                    'call_index': index%4} for index in range(maximum)]
                context = self.context(root, warm, events)
                result = checkpoint.terminal_counts(context)
                self.assertEqual(50 if warm else 33, result['provider_attempt_upper_bound'])
                events.append({'event': 'before_call' if warm else 'provider_attempt',
                    'request_number' if warm else 'run_token': 100 if warm else 'f'*32, 'call_index': 0})
                self.context(root, warm, events)
                with self.assertRaises(EvidenceError): checkpoint.terminal_counts(context)

    def test_duplicate_or_incomplete_native_terminal_log_cannot_be_counted_as_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); row = {'event': 'provider_attempt', 'run_token': 'a'*32, 'call_index': 0}
            for events, tail in (([row, row], b''), ([row], b'{"event":')):
                with self.subTest(tail=tail):
                    context = self.context(root, False, events, tail=tail)
                    with self.assertRaises(EvidenceError): checkpoint.terminal_counts(context)


if __name__ == '__main__': unittest.main()
