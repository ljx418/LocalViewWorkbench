"""Actual-operation selftest payload; owned canaries prepared by frozen launcher.

Never imports product code. A pass here is only evidence about this guard.
"""
import os
import json
from pathlib import Path

root = Path(os.environ['LVW_GUARD_CANARY_ROOT'])
outside = Path(os.environ['LVW_GUARD_CANARY_OUTSIDE'])
original = outside.read_bytes()
checks = []

# pytest logging uses this exact virtual sink; never allow arbitrary /dev paths.
with open('/dev/null', 'wb') as null_sink:
    assert null_sink.write(b'LVW-owned-null-sink-probe') == 25
checks.append({'case': 'exact_virtual_null_sink_write', 'passed': True})


def rejected(name, operation):
    try:
        operation()
    except RuntimeError as error:
        assert str(error).startswith('ROOT_GUARD_DENIED:'), repr(error)
    else:
        raise AssertionError('WRITE_BOUNDARY_MISSING:' + name)
    assert outside.read_bytes() == original, name
    checks.append({'case': name, 'passed': True})


owned = root / 'owned'
owned.mkdir()
(owned / 'a').write_bytes(b'owned-positive')
assert (owned / 'a').read_bytes() == b'owned-positive'
(owned / 'a').rename(owned / 'b')
(owned / 'b').unlink()
checks.append({'case': 'owned_create_write_read_rename_remove', 'passed': True})
rejected('outside_absolute_overwrite', lambda: outside.write_bytes(b'bad'))
rejected('outside_relative_overwrite', lambda: Path(os.path.relpath(outside)).write_bytes(b'bad'))
rejected('outside_delete', outside.unlink)
rejected('outside_rename', lambda: outside.rename(root / 'stolen'))
rejected('symlink_escape_write', lambda: (root / 'escape').write_bytes(b'bad'))
fd = os.open(outside.parent, os.O_RDONLY | os.O_DIRECTORY)
try:
    rejected('relative_dir_fd_write', lambda: os.open(outside.name, os.O_WRONLY | os.O_TRUNC, dir_fd=fd))
    rejected('relative_dir_fd_remove', lambda: os.unlink(outside.name, dir_fd=fd))
finally:
    os.close(fd)
rejected('hardlink_alias_write', lambda: (root / 'hardlink').write_bytes(b'bad'))
rejected('new_symlink_unsupported', lambda: os.symlink(outside, root / 'new-link'))
# Compatibility is limited to existing numbered dirs and direct current siblings.
import shutil
pytest_temp = root / 'pytest-temp'
pytest_temp.mkdir()
numbered = pytest_temp / 'sample0'
numbered.mkdir()
current = pytest_temp / 'samplecurrent'
os.symlink(str(numbered), current)
(current / 'probe').write_bytes(b'owned-alias-probe')
assert (numbered / 'probe').read_bytes() == b'owned-alias-probe'
(current / 'probe').unlink()
current.unlink()
checks.append({'case': 'owned_absolute_pytest_alias_write_remove', 'passed': True})
os.symlink('sample0', current)
assert current.resolve() == numbered.resolve()
checks.append({'case': 'owned_relative_pytest_alias', 'passed': True})
rejected('alias_outside_target', lambda: os.symlink(str(outside), pytest_temp / 'outsidecurrent'))
rejected('alias_outside_destination', lambda: os.symlink(str(numbered), outside.parent / 'samplecurrent'))
nested = pytest_temp / 'nested'
nested.mkdir()
(nested / 'sample0').mkdir()
rejected('alias_wrong_source_parent', lambda: os.symlink(str(nested / 'sample0'), current))
rejected('alias_wrong_prefix', lambda: os.symlink(str(numbered), pytest_temp / 'othercurrent'))
rejected('alias_missing_numbered_directory', lambda: os.symlink(str(pytest_temp / 'missing0'), pytest_temp / 'missingcurrent'))
regular = pytest_temp / 'regular0'
regular.write_bytes(b'owned-regular-not-directory')
rejected('alias_regular_file_target', lambda: os.symlink(str(regular), pytest_temp / 'regularcurrent'))
rejected('alias_symlink_parent', lambda: os.symlink(str(numbered), current / 'samplecurrent'))
pytest_fd = os.open(pytest_temp, os.O_RDONLY | os.O_DIRECTORY)
try:
    rejected('alias_unsupported_dir_fd', lambda: os.symlink('sample0', 'samplecurrent', dir_fd=pytest_fd))
finally:
    os.close(pytest_fd)
rejected('alias_traversal_even_if_same_root', lambda: os.symlink(str(pytest_temp / '..' / 'pytest-temp' / 'sample0'), pytest_temp / 'samplecurrent'))
# All aliases are self-owned; rmtree does not follow them to external content.
shutil.rmtree(pytest_temp)
checks.append({'case': 'owned_pytest_tree_cleanup', 'passed': not pytest_temp.exists()})
assert not (root / 'stolen').exists()
assert not (root / 'new-link').exists()
assert outside.read_bytes() == original
(root / 'canary-result.json').write_text(json.dumps({
    'kind': 'GUARD_CANARY_SELFTEST_NOT_PRODUCT_ACCEPTANCE',
    'checks': checks,
    'outside_unchanged': True,
    'expected_denial_count': 18,
    'candidate_imported': False,
    'product_runtime_executed': False,
}, indent=2) + '\n')
