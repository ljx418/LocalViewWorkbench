"""Root-owned bounded CPU guard; pending independent review and canary tests.

Python audit protection for this cooperative test harness, not an OS sandbox.
Usage: python -I -B guard.py RUNNER RECEIPT FRESH_WRITE_ROOT
Relative dir_fd writes through os.open and new symlinks are unsupported/denied.
"""
import sys
import os
import json
import runpy
import time
import types
import stat
from pathlib import Path

if len(sys.argv) != 4:
    raise RuntimeError('ROOT_GUARD_ARGV')
write_root = os.path.abspath(sys.argv[3])
if os.path.realpath(write_root) != write_root:
    raise RuntimeError('ROOT_GUARD_ROOT_NOT_CANONICAL')
root_stat = os.stat(write_root, follow_symlinks=False)
if not stat.S_ISDIR(root_stat.st_mode):
    raise RuntimeError('ROOT_GUARD_ROOT_NOT_DIRECTORY')
root_identity = (root_stat.st_dev, root_stat.st_ino)
# Only the exact pre-existing virtual null sink is an open-write exception.
null_stat = os.lstat('/dev/null')
if not stat.S_ISCHR(null_stat.st_mode):
    raise RuntimeError('ROOT_GUARD_NULL_NOT_CHARACTER_DEVICE')
null_identity = (null_stat.st_dev, null_stat.st_ino, null_stat.st_rdev)
receipt = os.path.abspath(sys.argv[2])
if os.path.commonpath((write_root, receipt)) != write_root:
    raise RuntimeError('ROOT_GUARD_RECEIPT_OUTSIDE_ROOT')
attempts = []
preload_events = []
pytest_aliases = []
pytest_temp_identity = None
phase = 'NEW'
writing_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


def deny(event, args):
    record = {'event': event, 'args': repr(args)[:200]}
    if event.startswith('os.symlink') and len(args) >= 3:
        record['symlink'] = {'source': os.fsdecode(args[0]),
                             'destination': os.fsdecode(args[1]), 'dir_fd': args[2]}
    attempts.append(record)
    raise RuntimeError('ROOT_GUARD_DENIED:' + event)


def writable(event, path, directory_fd=None, protect_root=False):
    current = os.stat(write_root, follow_symlinks=False)
    if (current.st_dev, current.st_ino) != root_identity or not stat.S_ISDIR(current.st_mode):
        deny(event + '.root_identity', (path,))
    if isinstance(path, int):
        mode = os.fstat(path).st_mode
        if path in (0, 1, 2) or stat.S_ISFIFO(mode):
            return
        path = os.readlink('/proc/self/fd/' + str(path))
        if not os.path.isabs(path) or path.endswith(' (deleted)'):
            deny(event + '.unknown_fd', (path,))
    path = os.fsdecode(path)
    if directory_fd not in (None, -1) and not os.path.isabs(path):
        if not stat.S_ISDIR(os.fstat(directory_fd).st_mode):
            deny(event + '.not_directory_fd', (path, directory_fd))
        anchor = os.readlink('/proc/self/fd/' + str(directory_fd))
        if not os.path.isabs(anchor) or anchor.endswith(' (deleted)'):
            deny(event + '.unknown_directory_fd', (path, directory_fd))
        path = os.path.join(anchor, path)
    target = os.path.realpath(os.path.abspath(path))
    if os.path.commonpath((write_root, target)) != write_root:
        deny(event + '.outside_root', (path, directory_fd))
    if protect_root and target == write_root:
        deny(event + '.root_mutation', (path,))
    try:
        existing = os.stat(target)
    except FileNotFoundError:
        return
    if stat.S_ISREG(existing.st_mode) and existing.st_nlink > 1:
        deny(event + '.hardlink_alias', (path,))


def pytest_current_alias(args):
    """Only direct numbered-dir/current siblings under this run's pytest-temp."""
    global pytest_temp_identity
    source, destination, directory_fd = args
    if directory_fd not in (None, -1):
        deny('os.symlink.dir_fd_unsupported', args)
    source, destination = os.fsdecode(source), os.fsdecode(destination)
    if '..' in Path(source).parts or '..' in Path(destination).parts:
        deny('os.symlink.traversal', args)
    destination_path = Path(os.path.abspath(destination))
    temp = Path(write_root) / 'pytest-temp'
    if destination_path.parent != temp:
        deny('os.symlink.destination_not_pytest_sibling', args)
    if not os.path.isabs(source) and os.path.basename(source) != source:
        deny('os.symlink.relative_target_not_basename', args)
    source_path = Path(source) if os.path.isabs(source) else temp / source
    if source_path.parent != temp:
        deny('os.symlink.source_not_pytest_sibling', args)
    name = destination_path.name
    if not name.endswith('current') or not name[:-7]:
        deny('os.symlink.destination_not_current', args)
    prefix = name[:-7]
    suffix = source_path.name[len(prefix):] if source_path.name.startswith(prefix) else ''
    if not suffix or not suffix.isascii() or not suffix.isdecimal():
        deny('os.symlink.numbered_prefix_mismatch', args)
    try:
        temp_stat = temp.lstat()
        source_stat = source_path.lstat()
    except OSError:
        deny('os.symlink.source_or_parent_missing', args)
    if (not stat.S_ISDIR(temp_stat.st_mode) or temp.is_symlink() or
            os.path.realpath(temp) != str(temp) or
            not stat.S_ISDIR(source_stat.st_mode) or source_path.is_symlink()):
        deny('os.symlink.noncanonical_or_not_directory', args)
    identity = (temp_stat.st_dev, temp_stat.st_ino)
    if pytest_temp_identity is not None and pytest_temp_identity != identity:
        deny('os.symlink.pytest_parent_identity_changed', args)
    if os.path.lexists(destination_path):
        deny('os.symlink.destination_exists', args)
    writable('os.symlink.source', source_path, protect_root=True)
    writable('os.symlink.destination', destination_path, protect_root=True)
    pytest_temp_identity = identity
    pytest_aliases.append({'source': source, 'destination': destination,
                          'resolved_target': str(source_path), 'dir_fd': directory_fd,
                          'parent_identity': identity})


def audit(event, args):
    if event == 'os.symlink':
        pytest_current_alias(args)
        return
    if event == 'ctypes.dlopen' and phase == 'OPEN' and args == (None,):
        if preload_events:
            deny(event, args)
        preload_events.append({'event': event, 'name': None})
        return
    prohibited = (event.startswith(('subprocess.', 'socket.', 'os.exec', 'os.spawn',
                                   'os.posix_spawn', 'ctypes.dlsym')) or event in
                  ('os.system', 'os.fork', 'os.forkpty', 'pty.spawn', 'sqlite3.connect',
                   'ctypes.dlopen', 'os.dlopen', 'mmap.__new__', 'os.chown'))
    if event == 'open':
        name = str(args[0]).lower()
        prohibited = prohibited or ('shared-counter.json' in name or '/.lvw-runtime/' in name
                                    or 'program02.sqlite' in name or
                                    ('original.' in name and name.endswith(('.db', '.sqlite', '.sqlite3'))))
    if prohibited:
        deny(event, args)
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (flags & writing_flags):
            path = args[0]
            null_sink = isinstance(path, (str, bytes)) and os.fsdecode(path) == '/dev/null'
            if null_sink:
                current_null = os.lstat('/dev/null')
                if (not stat.S_ISCHR(current_null.st_mode) or
                        (current_null.st_dev, current_null.st_ino, current_null.st_rdev) != null_identity):
                    deny('open.null_identity_changed', (path,))
            else:
                writable(event, path)
    elif event == 'os.mkdir':
        writable(event, args[0], args[2])
    elif event in ('os.remove', 'os.rmdir'):
        writable(event, args[0], args[1], protect_root=True)
    elif event in ('os.rename', 'os.link'):
        writable(event, args[0], args[2], protect_root=True)
        writable(event, args[1], args[3], protect_root=True)
    elif event == 'os.chmod':
        writable(event, args[0], args[2])
    elif event == 'os.utime':
        writable(event, args[0], args[3])
    elif event == 'os.truncate':
        writable(event, args[0])


# CPython's open audit event omits dir_fd. Never resolve that write as cwd.
original_os_open = os.open


def guarded_os_open(path, flags, mode=0o777, *, dir_fd=None):
    if flags & writing_flags and dir_fd is not None and not os.path.isabs(path):
        deny('open.relative_dir_fd_unsupported', (path, dir_fd))
    return original_os_open(path, flags, mode, dir_fd=dir_fd)


def begin():
    global phase
    if phase != 'NEW':
        raise RuntimeError('PRELOAD_WINDOW_CANNOT_REOPEN')
    phase = 'OPEN'


def finish():
    global phase
    phase = 'CLOSED'
    if len(preload_events) != 1:
        raise RuntimeError('PRELOAD_EVENT_COUNT')


os.open = guarded_os_open
sys.addaudithook(audit)
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
sys.modules['lvw_root_preload_control'] = types.SimpleNamespace(
    begin=begin, finish=finish, events=preload_events)
started = time.time()
selftest = []
try:
    for event in ['subprocess.Popen', 'socket.__new__', 'os.fork', 'os.exec',
                  'os.system', 'sqlite3.connect', 'ctypes.dlopen', 'ctypes.dlsym']:
        try:
            sys.audit(event, 'guard_selftest')
        except RuntimeError:
            selftest.append(event)
        else:
            raise RuntimeError('GUARD_SELFTEST_MISSING:' + event)
    attempts.clear()
    runpy.run_path(sys.argv[1], run_name='__main__')
finally:
    Path(receipt).write_text(json.dumps({
        'guard_precedes_candidate_and_pytest': True,
        'selftest_denials': selftest,
        'runtime_denials': attempts,
        'preload_events': preload_events,
        'preload_window_final_state': phase,
        'write_root': write_root,
        'write_root_identity': root_identity,
        'relative_dir_fd_open_write': 'DENIED_UNSUPPORTED',
        'new_symlinks': 'ONLY_OWNED_PYTEST_DIRECT_NUMBERED_CURRENT_SIBLINGS',
        'allowed_pytest_aliases': pytest_aliases,
        'wall_seconds': time.time() - started,
        'clean_runtime_denial_ledger': not attempts,
        'is_adversarial_os_sandbox': False,
    }, indent=2) + '\n')
