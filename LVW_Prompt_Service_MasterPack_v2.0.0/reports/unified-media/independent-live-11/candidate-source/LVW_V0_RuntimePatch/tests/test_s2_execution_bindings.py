"""Real temporary-file binding tests, no installed-code probe or process."""
import hashlib
import os
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

from tools.v0_s2_execution_bindings import ExecutionBindings, Tree, hashed_file, hashed_at, stamp, directory_handle
from tools.v0_s2_checkpoint_oracles import EvidenceError


class BindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.code = self.root/'code'; self.code.mkdir()
        (self.code/'main.py').write_bytes(b'print("bound")\n')
        (self.code/'cache.pyc').write_bytes(b'bytecode also matters')
        self.tool = self.root/'node'; self.tool.write_bytes(b'fixture executable')

    def bindings(self, **kwargs):
        return ExecutionBindings(trees={'CODE': Tree(self.code, ('private-models',))}, files={'NODE': self.tool},
            authorize=kwargs.pop('authorize', lambda *args: None), **kwargs)

    def test_complete_seal_rehash_and_short_guard_have_distinct_scopes(self):
        bindings = self.bindings(); original = bindings.capture()
        self.assertEqual({'CODE/cache.pyc', 'CODE/main.py', 'NODE'}, {row['alias'] for row in original['files']})
        self.assertTrue(bindings.verify()['complete_rehash'])
        self.assertFalse(bindings.guard(['NODE'])['complete_rehash'])
        original['files'].clear()  # Returned data cannot mutate the retained seal.
        self.assertEqual(3, len(bindings.seal['files']))
        with self.assertRaises(EvidenceError): bindings.capture()

    def test_changed_added_removed_or_replaced_files_fail_complete_verification(self):
        changes = ('changed', 'added', 'removed', 'replaced')
        for change in changes:
            with self.subTest(change=change):
                target = self.code/'main.py'; original = target.read_bytes(); bindings = self.bindings(); bindings.capture()
                if change == 'changed': target.write_bytes(b'wrong bytes')
                elif change == 'added': (self.code/'extra.js').write_text('extra')
                elif change == 'removed': target.unlink()
                else:
                    new = self.root/'replacement'; new.write_bytes(original); new.replace(target)
                with self.assertRaises((EvidenceError, FileNotFoundError)): bindings.verify()
                if (self.code/'extra.js').exists(): (self.code/'extra.js').unlink()
                target.write_bytes(original)

    def test_excluded_top_level_private_tree_is_not_visited_but_nested_names_are_bound(self):
        private = self.code/'private-models'; private.mkdir(); (private/'no-read').symlink_to('/not-authorized')
        nested = self.code/'nested/private-models'; nested.mkdir(parents=True); (nested/'entry.py').write_text('bound')
        value = self.bindings().capture()
        self.assertIn('CODE/nested/private-models/entry.py', {row['alias'] for row in value['files']})
        self.assertEqual({'CODE': ['private-models']}, value['excluded_top_level_roots'])

    def test_redirects_in_tree_named_file_or_ancestor_are_refused(self):
        link = self.code/'foreign'; link.symlink_to(self.tool)
        with self.assertRaises(EvidenceError): self.bindings().capture()
        link.unlink(); self.tool.unlink(); self.tool.symlink_to(self.code/'main.py')
        with self.assertRaises(EvidenceError): self.bindings().capture()
        parent = self.root/'alias'; parent.symlink_to(self.code, target_is_directory=True)
        with self.assertRaises(EvidenceError):
            ExecutionBindings(trees={'CODE': Tree(parent)}, files={'NODE': self.code/'main.py'}, authorize=lambda *args: None).capture()

    def test_exact_and_one_over_file_byte_and_entry_caps(self):
        total = sum(path.stat().st_size for path in (self.tool, self.code/'main.py', self.code/'cache.pyc'))
        self.bindings(max_files=3, max_bytes=total, max_entries=3).capture()
        for kwargs in ({'max_files': 2}, {'max_bytes': total-1}, {'max_entries': 2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(EvidenceError): self.bindings(**kwargs).capture()

    def test_denied_capture_and_missing_capture_guard_do_not_read_target(self):
        def deny(*args): raise EvidenceError('denied')
        bindings = self.bindings(authorize=deny)
        with patch.object(bindings, '_snapshot') as snapshot, self.assertRaises(EvidenceError): bindings.capture()
        snapshot.assert_not_called()
        with self.assertRaises(EvidenceError): self.bindings().guard(['NODE'])

    def test_guard_detects_same_length_edit_even_with_restored_mtime(self):
        bindings = self.bindings(); bindings.capture(); before = self.tool.stat()
        self.tool.write_bytes(b'x'*before.st_size); os.utime(self.tool, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaises(EvidenceError): bindings.guard(['NODE'])

    def test_descriptor_reader_refuses_replaced_parent_link_and_never_emits_bytes(self):
        path = self.code/'main.py'; before = stamp(path)
        moved = self.root/'moved'; self.code.rename(moved); self.code.symlink_to(moved, target_is_directory=True)
        emitted = []
        with self.assertRaises(OSError): hashed_file(path, before, float('inf'), write=emitted.append)
        self.assertEqual([], emitted)
        self.assertEqual(hashlib.sha256(b'print("bound")\n').hexdigest(), hashlib.sha256((moved/'main.py').read_bytes()).hexdigest())

    def test_many_files_share_parent_pinning_without_changing_complete_manifest(self):
        nested = self.code/'nested'; nested.mkdir()
        for index in range(200): (nested/str(index)).write_bytes(str(index).encode())
        with patch('tools.v0_s2_execution_bindings.directory_handle', wraps=directory_handle) as handles:
            result = self.bindings().capture()
        self.assertEqual(203, len(result['files']))
        self.assertEqual(1, sum(call.args[0] == nested for call in handles.call_args_list))
        expected = {('CODE/nested/'+str(i)): hashlib.sha256(str(i).encode()).hexdigest() for i in range(200)}
        self.assertEqual(expected, {row['alias']: row['sha256'] for row in result['files'] if '/nested/' in row['alias']})

    def test_parent_replacement_after_read_is_rejected_by_second_inventory(self):
        moved = self.root/'original'; replaced = False
        def read(*args, **kwargs):
            nonlocal replaced
            result = hashed_at(*args, **kwargs)
            if not replaced:
                replaced = True; self.code.rename(moved); shutil.copytree(moved, self.code)
            return result
        with patch('tools.v0_s2_execution_bindings.hashed_at', side_effect=read), self.assertRaises(EvidenceError):
            self.bindings().capture()

    def test_hash_deadline_is_distinct_and_prevents_even_empty_file_read(self):
        target = self.code/'empty'; target.touch()
        with patch('tools.v0_s2_execution_bindings.os.read') as read, self.assertRaisesRegex(EvidenceError, 'hash time budget exceeded'):
            hashed_file(target, stamp(target), -1)
        read.assert_not_called()

    def test_growing_file_has_distinct_size_error(self):
        target = self.code/'main.py'; before = stamp(target); original = os.read; appended = False
        def read(*args):
            nonlocal appended
            result = original(*args)
            if not appended:
                appended = True
                with target.open('ab') as output: output.write(b'extra')
            return result
        with patch('tools.v0_s2_execution_bindings.os.read', side_effect=read), self.assertRaisesRegex(EvidenceError, 'exceeded declared size'):
            hashed_file(target, before, float('inf'))

    def test_failed_snapshot_records_exact_alias_and_never_reports_complete(self):
        observations = []
        with patch('tools.v0_s2_execution_bindings.hashed_at', side_effect=EvidenceError('binding hash time budget exceeded')):
            with self.assertRaises(EvidenceError): self.bindings(observe=observations.append).capture()
        self.assertEqual('failed', observations[-1]['phase'])
        self.assertTrue(observations[-1]['current_alias'].startswith('CODE/'))
        self.assertIn('hash time budget exceeded', observations[-1]['error_code'])
        self.assertNotIn('complete', [row['phase'] for row in observations])


if __name__ == '__main__': unittest.main()
