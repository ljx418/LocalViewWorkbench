"""The source pins of the correction 18 of the native custody.

The script is **static**: it reads the files as bytes and it writes their
sha256.  The baseline is read with a **read only** ``git show`` of the
exact blobs of the baseline commit: the script never imports, collects
or executes a module and it never writes into the repository.

Usage::

    python3 -I source_pins.py <package-root> <baseline-commit> <output.json>
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

#: The sources of the frozen denominator and of the production.
SOURCES = (
    'tools/v0_s3_native_broker.py',
    'tools/v0_s3_native_custody.py',
    'tools/test_v0_s3_native_custody.py',
    'tools/test_v0_s3_native_custody_regressions.py',
    'tools/test_v0_s3_native_custody_correction05.py',
    'tools/test_v0_s3_native_custody_correction07.py',
    'tools/test_v0_s3_native_custody_correction10.py',
)


def digest(data):
    return {'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'lines': data.count(b'\n')}


def repository_root(root):
    """The root of the repository that holds the package."""
    current = Path(root).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / '.git').exists():
            return candidate
    return current


def baseline_blob(root, commit, name):
    """The exact bytes of a file at the baseline commit (read only)."""
    base = repository_root(root)
    relative = Path(root).resolve().relative_to(base) / name
    result = subprocess.run(
        ['git', '-C', str(base), 'show',
         '%s:%s' % (commit, relative.as_posix())],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout


def main(root, commit, output):
    root = Path(root)
    pins = {}
    for name in SOURCES:
        now = digest((root / name).read_bytes())
        before = digest(baseline_blob(root, commit, name))
        pins[name] = {
            'before': before,
            'after': now,
            'changed': before['sha256'] != now['sha256'],
        }
    document = {
        'kind': 'lvw.s3-native-custody-source-pins/1',
        'baseline': commit,
        'baseline_read': 'read only git show of the exact blobs',
        'changed_files': [name for name, item in pins.items() if item['changed']],
        'unchanged_files': [name for name, item in pins.items()
                            if not item['changed']],
        'pins': pins,
    }
    Path(output).write_text(json.dumps(document, indent=1, sort_keys=True),
                             encoding='utf-8')
    print(json.dumps({'changed': document['changed_files'],
                      'unchanged': document['unchanged_files']},
                     indent=1, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
