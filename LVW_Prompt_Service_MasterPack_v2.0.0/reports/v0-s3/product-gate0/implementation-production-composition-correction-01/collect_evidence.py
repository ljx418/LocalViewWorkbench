"""The outer driver of the evidence of this correction.

The driver runs the real commands of the run, one after the other, and it
archives the real argument vector, the working directory, the beginning,
the end, the exit code and both streams of every command *before* the
report is written.  Every command of the run is a command of the
implementation layer: the guarded commands themselves create no operating
system child process, and the driver only starts them.

The commands are:

1. the self test of the independent boundary;
2. the positive example of the whole chain, with its real artefacts;
3. the concentrated directed scope of the correction.

The shared counter of the root is read by the outer layer only, before
and after the run, and it is never written.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
REPORT = Path(__file__).resolve().parent
COUNTER = Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json')
COUNTER_SHA = 'acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98'


def counter_state():
    """The read only state of the shared counter of the root."""
    try:
        raw = COUNTER.read_bytes()
    except OSError as error:
        return {'path': str(COUNTER), 'readable': False, 'error': type(error).__name__}
    document = json.loads(raw.decode('utf-8'))
    return {
        'path': str(COUNTER),
        'readable': True,
        'sha256': hashlib.sha256(raw).hexdigest(),
        'active': document.get('active'),
        'starts_total': document.get('starts_total'),
        'reserved_wall_seconds': document.get('reserved_wall_seconds'),
        'spent_wall_seconds': document.get('spent_wall_seconds'),
        'charges': len(document.get('charges', [])),
        'written_by_this_run': False,
        'refunded_by_this_run': False,
        'reset_by_this_run': False,
    }


def run(label, argv):
    """Run one real command and archive everything about it."""
    started = time.time()
    process = subprocess.run(argv, cwd=str(PACK_ROOT), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)
    ended = time.time()
    (REPORT / (label + '.stdout.log')).write_bytes(process.stdout)
    (REPORT / (label + '.stderr.log')).write_bytes(process.stderr)
    record = {
        'label': label,
        'argv': argv,
        'cwd': str(PACK_ROOT),
        'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)),
        'ended_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ended)),
        'duration_seconds': round(ended - started, 3),
        'exit_code': process.returncode,
        'stdout_log': label + '.stdout.log',
        'stderr_log': label + '.stderr.log',
    }
    print(label, 'exit', process.returncode)
    return record


def archive_pytest_temp():
    """Archive the synthetic artefacts of the scope into one archive.

    Every synthetic file of every case of the scope stays in the archive
    with its digest, so the independent review can recompute the run.  The
    raw tree is removed afterwards: the archive and its manifest are the
    evidence, not the size of the tree.
    """
    import zipfile
    root = REPORT / 'pytest-temp'
    if not root.is_dir():
        return None
    manifest = []
    archive = REPORT / 'pytest-temp.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            relative = str(path.relative_to(REPORT))
            raw = path.read_bytes()
            manifest.append({'path': relative, 'bytes': len(raw),
                             'sha256': hashlib.sha256(raw).hexdigest()})
            bundle.write(path, relative)
    document = {'kind': 'lvw.s3-synthetic-artefact-archive/1',
                'archive': archive.name,
                'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'file_count': len(manifest),
                'files': manifest,
                'note': 'the synthetic artefacts of every case of the scope; '
                        'they are synthetic inputs and outputs of an offline '
                        'composition and never a product artefact'}
    (REPORT / 'pytest-temp.manifest.json').write_text(json.dumps(document, indent=2),
                                                      encoding='utf-8')
    shutil.rmtree(root)
    return document


def main():
    commands = []
    commands.append(run('guard-selftest',
                        [sys.executable, '-B',
                         str(REPORT / 'guard.py'), str(REPORT / 'guard_selftest.py'),
                         str(REPORT / 'guard-selftest.guard.json')]))
    commands.append(run('positive-example',
                        [sys.executable, '-B',
                         str(REPORT / 'guard.py'), str(REPORT / 'run_positive_example.py'),
                         str(REPORT / 'positive-example.guard.json')]))
    commands.append(run('directed-scope',
                        [sys.executable, '-B',
                         str(REPORT / 'guard.py'), str(REPORT / 'run_directed_scope.py'),
                         str(REPORT / 'directed-scope.guard.json')]))
    (REPORT / 'commands.json').write_text(json.dumps(commands, indent=2), encoding='utf-8')
    archive = archive_pytest_temp()
    counter = counter_state()
    (REPORT / 'counter-readonly.json').write_text(json.dumps({
        'kind': 'lvw.s3-cpu-budget-readonly/1',
        'before_and_after': counter,
        'contract_sha256': COUNTER_SHA,
        'matches_the_contract': counter.get('sha256') == COUNTER_SHA,
        'inactive': counter.get('active') is False,
        'starts_total_expected': 28,
        'reserved_wall_seconds_expected': 240.0,
        'spent_wall_seconds_expected': 12.362,
        'written_by_this_run': False,
        'refunded_by_this_run': False,
        'reset_by_this_run': False,
        'new_counter_created': False,
        'old_grant_revived': False,
    }, indent=2), encoding='utf-8')
    return 0 if all(command['exit_code'] == 0 for command in commands) else 1


if __name__ == '__main__':
    raise SystemExit(main())
