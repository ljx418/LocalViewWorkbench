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
assert not (root / 'stolen').exists()
assert not (root / 'new-link').exists()
assert outside.read_bytes() == original
(root / 'canary-result.json').write_text(json.dumps({
    'kind': 'GUARD_CANARY_SELFTEST_NOT_PRODUCT_ACCEPTANCE',
    'checks': checks,
    'outside_unchanged': True,
    'expected_denial_count': 9,
    'candidate_imported': False,
    'product_runtime_executed': False,
}, indent=2) + '\n')
