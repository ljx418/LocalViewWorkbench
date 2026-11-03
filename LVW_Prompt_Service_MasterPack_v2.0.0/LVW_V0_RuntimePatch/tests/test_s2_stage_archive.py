"""Actual bounded copy/delete on fresh temp roots; synthetic terminal services."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.v0_s2_stage_archive import OwnedArchive
from tools import v0_s2_stage_archive as archive_module
from tools.v0_s2_checkpoint_oracles import EvidenceError


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve(); self.root = self.parent/'default'; self.root.mkdir()
        self.destination = self.parent/'receipts'; self.destination.mkdir()
        self.context = SimpleNamespace(root=self.root, binding={'candidate_sha': 'a'*40, 'authorization_sha256': 'b'*64},
            driver=SimpleNamespace(listener_proofs={8191: {}, 11434: {}}, owned=[object(), object()]))
        self.cleanup = {'proven': True, 'owned_count': 2, 'final_target_listener_count': 0, 'http_workers_pending': {},
            'owned_listener_terminal_states': [{'port': port, 'terminal_absent': True, 'unknown_descendants_absent': True} for port in (8191, 11434)],
            'owned_wrapper_terminal_states': [dict(exited=True, native_wrapper_absent=True) for _ in range(2)]}

    def archive(self, **kwargs):
        return OwnedArchive(self.destination, run_id='archive-test', candidate_sha='a'*40,
            authorization_sha256='b'*64, authorize=kwargs.pop('authorize', lambda *args: None), **kwargs)

    def populate(self):
        (self.root/'temp').mkdir(); (self.root/'input').mkdir(); (self.root/'custom_nodes').mkdir()
        (self.root/'temp/raw.json').write_bytes(b'{"raw":"actual fixture bytes"}\n')
        (self.root/'comfy.log').write_bytes(b'fixture service log\n')
        (self.root/'input/oversize.mp4').write_bytes(b'staged source is not evidence')
        (self.root/'custom_nodes/node.py').write_bytes(b'bound by parent candidate')

    def test_archive_rereads_copied_bytes_and_manifest_before_owned_root_removal(self):
        archive = self.archive(); archive.register(self.root, 'default'); self.populate()
        result = archive(self.context, self.cleanup)
        self.assertTrue(result['proven']); self.assertFalse(self.root.exists()); self.assertEqual(2, result['files'])
        manifest_path = self.destination/result['manifest_file']; raw = manifest_path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['manifest_sha256'])
        manifest = json.loads(raw)
        self.assertEqual(['input', 'custom_nodes'], manifest['excluded_trees'])
        for row in manifest['files']:
            actual = (manifest_path.parent/row['file']).read_bytes()
            self.assertEqual(len(actual), row['bytes']); self.assertEqual(hashlib.sha256(actual).hexdigest(), row['sha256'])
        with self.assertRaises(EvidenceError): archive(self.context, self.cleanup)

    def test_only_declared_owned_reparse_fixture_is_removed_without_following_it(self):
        archive = self.archive(); archive.register(self.root, 'default'); self.populate()
        outside = self.root/'outside-input'; outside.mkdir(); (outside/'source.mp4').write_bytes(b'nonprivate fixture')
        (self.root/'input/redirect').symlink_to(outside, target_is_directory=True)
        result = archive(self.context, self.cleanup); self.assertTrue(result['proven'])
        self.assertEqual(b'nonprivate fixture', (self.destination/'default-raw/outside-input/source.mp4').read_bytes())

    def test_unknown_redirect_in_excluded_tree_blocks_deletion_and_preserves_foreign_target(self):
        archive = self.archive(); archive.register(self.root, 'default'); self.populate()
        foreign = self.parent/'foreign'; foreign.mkdir(); (foreign/'keep').write_bytes(b'keep')
        (self.root/'input/unexpected').symlink_to(foreign, target_is_directory=True)
        with self.assertRaises(EvidenceError): archive(self.context, self.cleanup)
        self.assertTrue(self.root.exists()); self.assertEqual(b'keep', (foreign/'keep').read_bytes())
        with self.assertRaises(EvidenceError): archive(self.context, self.cleanup)

    def test_bad_cleanup_identity_or_authorization_does_not_create_archive_or_remove_root(self):
        for failure in ('cleanup', 'identity', 'authorization'):
            with self.subTest(failure=failure):
                archive = self.archive(); archive.register(self.root, 'default')
                if failure == 'cleanup': self.cleanup['proven'] = False
                elif failure == 'identity': self.context.binding['candidate_sha'] = 'c'*40
                else: archive.authorize = lambda *args: (_ for _ in ()).throw(EvidenceError('denied'))
                with self.assertRaises(EvidenceError): archive(self.context, self.cleanup)
                self.assertTrue(self.root.exists()); self.assertFalse((self.destination/'default-raw').exists())
                self.cleanup['proven'] = True; self.context.binding['candidate_sha'] = 'a'*40

    def test_nonempty_or_replaced_root_cannot_obtain_or_use_lease(self):
        (self.root/'old').write_bytes(b'old')
        with self.assertRaises(EvidenceError): self.archive().register(self.root, 'default')
        (self.root/'old').unlink(); archive = self.archive(); archive.register(self.root, 'default')
        self.root.rename(self.parent/'original'); self.root.mkdir()
        with self.assertRaises(EvidenceError): archive(self.context, self.cleanup)
        self.assertFalse((self.destination/'default-raw').exists())

    def test_exact_and_one_over_copy_budgets(self):
        archive = self.archive(max_files=4, max_file_bytes=31, max_bytes=51)
        archive.register(self.root, 'default'); self.populate()
        total = sum(path.stat().st_size for path in (self.root/'temp/raw.json', self.root/'comfy.log'))
        archive.max_file_bytes = (self.root/'temp/raw.json').stat().st_size
        archive.max_bytes = total; self.assertTrue(archive(self.context, self.cleanup)['proven'])
        # Separate fresh root/label isolates the failed attempt and its evidence.
        self.root.mkdir(); failed = self.archive(max_bytes=total-1); failed.register(self.root, 'warm'); self.populate()
        with self.assertRaises(EvidenceError): failed(self.context, self.cleanup)
        self.assertTrue(self.root.exists())

    def test_one_over_total_file_count_and_individual_file_size_preserve_source(self):
        for limit in ('count', 'file-size'):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as temporary:
                self.root = Path(temporary).resolve()/'source'; self.root.mkdir(); self.context.root = self.root
                archive = self.archive(max_files=3 if limit == 'count' else 4, max_file_bytes=1 if limit == 'file-size' else 100)
                archive.register(self.root, 'warm' if limit == 'count' else 'default'); self.populate()
                with self.assertRaises(EvidenceError): archive(self.context, self.cleanup)
                self.assertTrue(self.root.exists())

    def test_corrupted_archive_copy_is_detected_before_source_root_is_removed(self):
        archive = self.archive(); archive.register(self.root, 'default'); self.populate()
        original = archive_module.hashed_file
        def corrupt(path, before, deadline, **kwargs):
            if path == self.destination/'default-raw/comfy.log' and not kwargs:
                path.write_bytes(b'corrupted destination')
            return original(path, before, deadline, **kwargs)
        with patch.object(archive_module, 'hashed_file', side_effect=corrupt), self.assertRaises(EvidenceError):
            archive(self.context, self.cleanup)
        self.assertTrue(self.root.exists()); self.assertEqual(b'fixture service log\n', (self.root/'comfy.log').read_bytes())


if __name__ == '__main__': unittest.main()
