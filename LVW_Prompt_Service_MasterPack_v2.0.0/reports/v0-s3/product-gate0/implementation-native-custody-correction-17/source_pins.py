"""The source pins of the correction 17 of the native custody.

The script is **static**: it reads the files as bytes and it writes their
sha256.  It never imports, collects or executes a module.

Usage::

    python3 -I source_pins.py <package-root> <baseline-root> <output.json>
"""
import hashlib
import json
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


def digest(path):
    data = Path(path).read_bytes()
    return {'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'lines': data.count(b'\n')}


def main(root, baseline, output):
    root = Path(root)
    baseline = Path(baseline)
    pins = {}
    for name in SOURCES:
        now = digest(root / name)
        before = digest(baseline / name)
        pins[name] = {
            'before': before,
            'after': now,
            'changed': before['sha256'] != now['sha256'],
        }
    document = {
        'kind': 'lvw.s3-native-custody-source-pins/1',
        'baseline': '4dafa1f316242d8bd348b81c52f375aa37254754',
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
