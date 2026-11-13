"""The outer runner of the N1 native custody correction 03 batch.

The runner is the *outer* boundary of the batch.  It owns the order of
the run and it owns the evidence of the run.

Its order is fixed and every step is guarded on its own.

1.  The plan of the batch is read and its own identity is checked.
2.  The original shared counter is opened **read only** and it is read
    once.  This happens *before* the guard is installed, because the guard
    refuses the open of that counter without any exemption: the counter
    of the historical batches is observed by the outer layer only, and it
    is never written, never refunded and never revived.
3.  The offline guard is installed.  It is installed before pytest, before
    any plugin and before any import of a candidate module.  Its activity
    is proved by a handshake and its boundary is proved by a self test
    that uses ``sys.audit`` only.
4.  The interpreter, the ``ctypes`` module of the standard library and
    the ``_ctypes`` extension are verified against their digests.
5.  The **preload window** of the standard library is opened, ``ctypes``
    is imported once and the window is closed for good.  The count of the
    events of the window is recorded separately.  A count that is not
    exactly one, a name that is not the image of the process itself or a
    refusal of the window stops the batch before any test is called.
6.  The sealed dependency path is appended to ``sys.path`` **explicitly**.
    No ``site.main`` and no ``.pth`` file is used, so the installed
    dependencies of this machine are the ones that are already sealed.
7.  The pins are verified **after** the guard is installed: the sources,
    the tool and the named dependencies.  Any drift refuses the run
    before a single test is called.
8.  The file descriptors and the threads are inventoried, with the real
    identity of every descriptor and not only a count.
9.  ``pytest.main`` is called **once**, with the exact nodes of the plan.
    The collection is compared with the plan, item by item and in order,
    and a mismatch leaves the session before any test is called.
10. The file descriptors and the threads are inventoried again, the
    counter is read again and the receipt is written.

The runner never starts a native service, never opens a socket, never
touches a database and never reads the original budget ledger.  It is a
report script: it runs the offline validation of this package and it
writes down what happened.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent
PACK_ROOT = REPORT_DIR.parents[3]


def _load_guard():
    """Load the guard of the batch from this directory, by its path."""
    path = REPORT_DIR / 'guard.py'
    spec = importlib.util.spec_from_file_location('lvw_s3_native_custody_guard', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


# -- the inventory of the file descriptors ----------------------------------

def fd_inventory():
    """The identity of every open file descriptor of this process.

    The inventory is the real identity of a descriptor and not only a
    count: the device, the inode and the mode of the target of every
    descriptor.  A descriptor that disappears while the directory is
    enumerated is reported as filtered, and a descriptor whose identity
    cannot be read is reported as unknown.  Neither of them is silently
    dropped and neither of them is reported as an empty inventory.
    """
    entries = {}
    filtered = []
    unknown = []
    try:
        names = os.listdir('/proc/self/fd')
    except OSError as error:
        return {'available': False, 'error_type': type(error).__name__,
                'descriptors': {}, 'filtered': [], 'unknown': []}
    for name in names:
        try:
            number = int(name)
        except ValueError:
            continue
        try:
            info = os.fstat(number)
        except OSError as error:
            if error.errno == 9:
                filtered.append({'fd': number, 'reason': 'EBADF'})
            else:
                unknown.append({'fd': number, 'reason': type(error).__name__})
            continue
        entries[number] = {'dev': info.st_dev, 'inode': info.st_ino,
                            'mode': stat.S_IFMT(info.st_mode),
                            'is_regular': stat.S_ISREG(info.st_mode),
                            'is_directory': stat.S_ISDIR(info.st_mode)}
    return {'available': True, 'descriptors': entries, 'filtered': filtered,
            'unknown': unknown}


def fd_comparison(before, after):
    """The identity comparison of the descriptors before and after.

    A descriptor number that exists before and after with a *different*
    identity is a reused number and it is reported as such: the number
    alone never proves that the target is the same.
    """
    first = before.get('descriptors', {}) if before.get('available') else {}
    second = after.get('descriptors', {}) if after.get('available') else {}
    reused = []
    for number in sorted(set(first) & set(second)):
        if first[number] != second[number]:
            reused.append({'fd': number, 'before': first[number], 'after': second[number]})
    return {
        'before_count': len(first),
        'after_count': len(second),
        'closed_numbers': sorted(set(first) - set(second)),
        'new_numbers': sorted(set(second) - set(first)),
        'reused_numbers': reused,
        'same_identity_numbers': len([n for n in set(first) & set(second)
                                      if first[n] == second[n]]),
        'filtered_before': before.get('filtered', []),
        'filtered_after': after.get('filtered', []),
        'unknown_before': before.get('unknown', []),
        'unknown_after': after.get('unknown', []),
        'inventory_empty': not first and not second,
    }


def thread_inventory():
    """The named threads of this process and whether they are retained."""
    threads = []
    for thread in threading.enumerate():
        threads.append({'name': thread.name, 'daemon': thread.daemon,
                        'alive': thread.is_alive(), 'ident': thread.ident})
    threads.sort(key=lambda item: (item['name'], str(item['ident'])))
    return {'count': len(threads), 'threads': threads,
            'retained_alive': [item['name'] for item in threads if item['alive']]}


# -- the pins ----------------------------------------------------------------

def dependency_inventory(sealed_path):
    """The named installed dependencies of the sealed path.

    The inventory is read from the ``dist-info`` directories themselves:
    the name and the version come from the METADATA of the distribution
    and the digest is the digest of that METADATA file.  Nothing is
    imported from the sealed path and nothing is executed from it.
    """
    from email.parser import BytesParser
    found = {}
    root = Path(sealed_path)
    if not root.is_dir():
        return found
    for entry in sorted(root.glob('*.dist-info')):
        metadata = entry / 'METADATA'
        if not metadata.is_file():
            continue
        raw = metadata.read_bytes()
        headers = BytesParser().parsebytes(raw)
        name = headers.get('Name')
        version = headers.get('Version')
        if not name or not version:
            continue
        found[name] = {'version': version, 'metadata_sha256': sha256_bytes(raw),
                       'metadata_path': str(metadata)}
    return found


def verify_pins(plan):
    """Verify the sources, the tool and the named dependencies.

    The verification runs after the guard is installed.  A drift refuses
    the run before a single test is called and it never repairs a pin.
    """
    failures = []
    sources = plan.get('source_pins', {})
    for relative, digest in sorted(sources.items()):
        path = PACK_ROOT / relative
        if not path.is_file():
            failures.append({'kind': 'source', 'path': relative, 'reason': 'MISSING'})
            continue
        actual = sha256_file(path)
        if actual != digest:
            failures.append({'kind': 'source', 'path': relative,
                             'reason': 'DIGEST_DRIFT', 'expected': digest, 'actual': actual})
    tool = plan.get('tool', {})
    tool_path = Path(tool.get('path', ''))
    if not tool_path.is_file():
        failures.append({'kind': 'tool', 'path': str(tool_path), 'reason': 'MISSING'})
    else:
        actual = sha256_file(tool_path)
        if actual != tool.get('sha256'):
            failures.append({'kind': 'tool', 'path': str(tool_path),
                             'reason': 'DIGEST_DRIFT', 'expected': tool.get('sha256'),
                             'actual': actual})
    sealed = plan.get('dependency_path', '')
    expected = plan.get('dependency_pins', {})
    if sealed:
        found = dependency_inventory(sealed)
        for name, item in sorted(expected.items()):
            actual = found.get(name)
            if actual is None:
                failures.append({'kind': 'dependency', 'name': name, 'reason': 'MISSING'})
                continue
            if actual['version'] != item['version']:
                failures.append({'kind': 'dependency', 'name': name,
                                 'reason': 'VERSION_DRIFT',
                                 'expected': item['version'], 'actual': actual['version']})
            elif actual['metadata_sha256'] != item['metadata_sha256']:
                failures.append({'kind': 'dependency', 'name': name,
                                 'reason': 'METADATA_DRIFT',
                                 'expected': item['metadata_sha256'],
                                 'actual': actual['metadata_sha256']})
        extra = sorted(set(found) - set(expected) - set(plan.get('dependency_excludes', [])))
        if extra:
            failures.append({'kind': 'dependency_set', 'reason': 'UNEXPECTED_MEMBERS',
                             'count': len(extra), 'names': extra[:20]})
    return failures


def verify_stdlib_pins(plan):
    """Verify the interpreter and the standard library of the preload.

    The preload of the standard library is only allowed when the
    interpreter, the ``ctypes`` module and the ``_ctypes`` extension are
    exactly the ones that the plan named.
    """
    failures = []
    for kind, item in sorted(plan.get('stdlib_pins', {}).items()):
        path = Path(item.get('path', ''))
        if not path.is_file():
            failures.append({'kind': kind, 'path': str(path), 'reason': 'MISSING'})
            continue
        actual = sha256_file(path)
        if actual != item.get('sha256'):
            failures.append({'kind': kind, 'path': str(path),
                             'reason': 'DIGEST_DRIFT', 'expected': item.get('sha256'),
                             'actual': actual})
    return failures


def preload_ctypes(guard):
    """The one finite preload of the standard library.

    The window is opened, ``ctypes`` is imported once and the window is
    closed for good.  The count of the events of the window and the name
    that was loaded are recorded: a count that is not exactly one or a
    name that is not the image of the process itself stops the batch.
    """
    state = guard.state()
    if state['preload_window_closed']:
        return {'ok': False, 'reason': 'WINDOW_ALREADY_CLOSED'}
    guard.open_preload_window()
    try:
        import ctypes  # noqa: F401 - the import IS the preload
    except Exception as error:  # noqa: BLE001 - the failure stops the batch
        guard.close_preload_window()
        return {'ok': False, 'reason': 'IMPORT_FAILED:' + type(error).__name__}
    guard.close_preload_window()
    after = guard.state()
    events = after['preload_events']
    ok = (len(events) == 1 and not after['preload_refusals']
          and after['preload_window_closed'] is True
          and after['preload_window_open'] is False)
    return {'ok': ok,
            'events': events,
            'refusals': after['preload_refusals'],
            'window_open_after': after['preload_window_open'],
            'window_closed_after': after['preload_window_closed'],
            'reason': 'OK' if ok else 'PRELOAD_COUNT_OR_NAME'}


# -- the runner --------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    arguments = parser.parse_args(argv)
    plan_path = Path(arguments.plan)
    if not plan_path.is_absolute():
        sys.stderr.write('the plan path must be absolute\n')
        return 2
    if not plan_path.is_file():
        sys.stderr.write('the plan of the batch is missing\n')
        return 2
    plan_raw = plan_path.read_bytes()
    plan = json.loads(plan_raw.decode('utf-8'))
    label = plan.get('label', 'native-custody-correction-03')
    outdir = REPORT_DIR
    stdout_path = outdir / (label + '.stdout.log')
    stderr_path = outdir / (label + '.stderr.log')
    receipt_path = outdir / (label + '.receipt.json')

    cwd = Path(plan.get('cwd', str(PACK_ROOT)))
    if not cwd.is_dir():
        sys.stderr.write('the working directory of the plan does not exist\n')
        return 2
    if Path.cwd().resolve() != cwd.resolve():
        sys.stderr.write('the working directory of this run is not the one of the plan\n')
        return 2
    script_argv = list(plan.get('script_argv', []))
    argv_matches = (not script_argv) or (script_argv == list(sys.argv))
    if not argv_matches:
        sys.stderr.write('the arguments of this run are not the ones of the plan\n')
        return 2
    argv_actual = [sys.executable] + list(sys.argv)

    # The counter of the historical batches is opened and read here, before
    # the guard exists.  The guard refuses its open without any exemption,
    # so the outer layer is the only layer that may observe it.
    counter_path = plan.get('counter', {}).get('path')
    counter_fd = None
    counter_before = None
    counter_error = None
    if counter_path:
        try:
            counter_fd = os.open(counter_path, os.O_RDONLY)
            raw = os.pread(counter_fd, 1 << 20, 0)
            counter_before = {'path': counter_path,
                              'sha256': sha256_bytes(raw),
                              'bytes': len(raw),
                              'mode': 'READ_ONLY_OUTSIDE_THE_GUARDED_BATCH'}
        except OSError as error:
            counter_error = type(error).__name__

    guard = _load_guard()
    forbidden = list(plan.get('forbidden_paths', []))
    try:
        owner = guard.install(forbidden)
    except guard.GuardInstallationError as error:
        sys.stderr.write('the offline guard of this process is not proven active: '
                         + str(error) + '\n')
        return 5
    selftest = guard.selftest()
    not_blocked = sorted(name for name, value in selftest.items() if value != 'REFUSED')
    if not_blocked:
        sys.stderr.write('the offline guard of this process does not refuse: '
                         + ', '.join(not_blocked) + '\n')
        return 5

    # The standard library of the preload is verified before the window is
    # opened and before any candidate or pytest import.
    stdlib_failures = verify_stdlib_pins(plan)
    if stdlib_failures:
        sys.stderr.write('the standard library of the preload drifted: '
                         + json.dumps(stdlib_failures)[:400] + '\n')
        return 6
    preload = preload_ctypes(guard)
    if not preload.get('ok'):
        sys.stderr.write('the preload of the standard library failed: '
                         + json.dumps(preload)[:400] + '\n')
        return 6

    # The sealed dependencies are appended explicitly.  No site.main and no
    # .pth file is used.
    dependency_path = plan.get('dependency_path')
    if dependency_path and dependency_path not in sys.path:
        sys.path.append(dependency_path)
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.dont_write_bytecode = True

    pin_failures = verify_pins(plan)
    if pin_failures:
        sys.stderr.write('the pins of the batch drifted: '
                         + json.dumps(pin_failures)[:400] + '\n')
        return 6

    expected_nodes = list(plan.get('nodeids', []))
    before_fds = fd_inventory()
    before_threads = thread_inventory()
    started = time.time()
    exit_code = 0
    collected = []
    collection_error = None
    stdout_handle = open(stdout_path, 'wb')
    stderr_handle = open(stderr_path, 'wb')
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    os.dup2(stdout_handle.fileno(), 1)
    os.dup2(stderr_handle.fileno(), 2)
    try:
        import pytest

        class Collection:
            """The exact collection of the plan, item by item and in order."""

            def pytest_collection_finish(self, session):
                collected.extend(item.nodeid for item in session.items)
                if collected != expected_nodes:
                    raise RuntimeError(
                        'COLLECTION_MISMATCH:expected=%d:actual=%d:missing=%s:unexpected=%s'
                        % (len(expected_nodes), len(collected),
                           [item for item in expected_nodes if item not in collected],
                           [item for item in collected if item not in expected_nodes]))

        argv_pytest = list(expected_nodes) + ['-q', '-p', 'no:cacheprovider',
                                              '--no-header', '-rN',
                                              '--basetemp', str(outdir / 'pytest-temp')]
        exit_code = int(pytest.main(argv_pytest, plugins=[Collection()]))
    except BaseException as error:  # noqa: BLE001 - the failure must be recorded
        collection_error = type(error).__name__ + ':' + str(error)[:400]
        exit_code = 3
    finally:
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        stdout_handle.close()
        stderr_handle.close()
    duration = round(time.time() - started, 3)
    after_fds = fd_inventory()
    after_threads = thread_inventory()
    comparison = fd_comparison(before_fds, after_fds)

    counter_after = None
    if counter_fd is not None:
        try:
            raw = os.pread(counter_fd, 1 << 20, 0)
            counter_after = {'path': counter_path, 'sha256': sha256_bytes(raw),
                             'bytes': len(raw),
                             'mode': 'READ_ONLY_OUTSIDE_THE_GUARDED_BATCH'}
        except OSError as error:
            counter_after = {'path': counter_path, 'error_type': type(error).__name__}
        finally:
            os.close(counter_fd)

    budget = plan.get('max_seconds', 300)
    budget_exceeded = duration > float(budget)
    threads_clean = (not after_threads['retained_alive']
                     and not before_threads['retained_alive'])
    if exit_code == 0 and collection_error is None and not budget_exceeded \
            and not comparison['reused_numbers'] and threads_clean:
        outcome = 'PASS'
    else:
        outcome = 'FAIL'
    receipt = {
        'kind': 'S3_N3_NATIVE_CUSTODY_CORRECTION_03_GUARDED_CHECK_RECEIPT',
        'label': label,
        'plan_path': str(plan_path),
        'plan_sha256': sha256_bytes(plan_raw),
        'plan_kind': plan.get('kind'),
        'argv': argv_actual,
        'argv_matches_the_plan': argv_matches,
        'cwd': str(Path.cwd().resolve()),
        'selected_nodeids': expected_nodes,
        'collected_nodeids': collected,
        'collected_count': len(collected),
        'collection_matches_the_plan': collected == expected_nodes,
        'collection_error': collection_error,
        'exit_code': exit_code,
        'outcome': outcome,
        'duration_seconds': duration,
        'max_seconds': budget,
        'budget_exceeded': budget_exceeded,
        'guard': dict(guard.state(), selftest=selftest,
                      selftest_not_blocked=not_blocked,
                      installed_before_pytest=True,
                      installed_before_any_candidate_import=True),
        'stdlib_preload': dict(preload,
                               stdlib_pins=plan.get('stdlib_pins', {}),
                               stdlib_pin_failures=stdlib_failures,
                               before_any_candidate_import=True,
                               before_any_pytest_import=True,
                               window_closed_after=True),
        'pins': {'verified_after_the_guard': True,
                 'source_count': len(plan.get('source_pins', {})),
                 'dependency_count': len(plan.get('dependency_pins', {})),
                 'dependency_path': dependency_path,
                 'failures': pin_failures},
        'file_descriptors': {'before': before_fds, 'after': after_fds,
                             'comparison': comparison},
        'threads': {'before': before_threads, 'after': after_threads,
                    'clean': threads_clean},
        'counter': {'before': counter_before, 'after': counter_after,
                    'error': counter_error,
                    'unchanged': (isinstance(counter_before, dict)
                                  and isinstance(counter_after, dict)
                                  and counter_before.get('sha256') == counter_after.get('sha256')),
                    'written_by_this_run': False, 'refunded_by_this_run': False,
                    'reset_by_this_run': False, 'new_counter_created': False},
        'stdout_file': str(stdout_path.relative_to(PACK_ROOT)),
        'stderr_file': str(stderr_path.relative_to(PACK_ROOT)),
        'stdout_bytes': stdout_path.stat().st_size,
        'stderr_bytes': stderr_path.stat().st_size,
        'stdout_sha256': sha256_file(stdout_path),
        'stderr_sha256': sha256_file(stderr_path),
        'real_execution_performed': False,
        'native_execution_proven': False,
        'stage_pass_claim': False,
        'product_gate0': False,
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                                       indent=2) + '\n', encoding='utf-8')
    sys.stdout.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + '\n')
    sys.stdout.flush()
    return exit_code if exit_code else (0 if outcome == 'PASS' else 1)


if __name__ == '__main__':
    sys.exit(main())
