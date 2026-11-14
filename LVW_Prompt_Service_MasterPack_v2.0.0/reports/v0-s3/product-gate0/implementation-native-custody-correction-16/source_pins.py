"""The source pins of the correction 16 (a static check).

The pins bind the bytes of the sources that the correction touches and
of the sources that it must **not** touch.  The production files and
the four other test modules are compared with the **candidate base**
of the correction: they are byte for byte the files of the base and
the correction changed only the file that it was allowed to change.

Nothing is imported, nothing is executed, no file of the pack is
written by this script and no candidate module is compiled.

Usage:

    python3 -I -B source_pins.py <pack-root> <base-sha>
"""
import hashlib
import json
import os
import subprocess
import sys

#: The files that the correction 16 binds.
BOUND = (
    'tools/v0_s3_native_broker.py',
    'tools/v0_s3_native_custody.py',
    'tools/test_v0_s3_native_custody.py',
    'tools/test_v0_s3_native_custody_regressions.py',
    'tools/test_v0_s3_native_custody_correction05.py',
    'tools/test_v0_s3_native_custody_correction07.py',
    'tools/test_v0_s3_native_custody_correction10.py',
)

#: The files that the correction 16 must not change.
UNCHANGED = BOUND[:-1]


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _read(path):
    with open(path, 'rb') as stream:
        return stream.read()


def _git_show(repository, base, relative):
    result = subprocess.run(
        ['git', '-C', repository, 'show',
         '%s:LVW_Prompt_Service_MasterPack_v2.0.0/%s' % (base, relative)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout if result.returncode == 0 else None


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: source_pins.py <pack-root> <base-sha>\n')
        return 2
    pack_root = argv[1]
    base = argv[2]
    repository = os.path.dirname(os.path.abspath(pack_root))
    files = {}
    for relative in BOUND:
        path = os.path.join(pack_root, relative)
        data = _read(path)
        base_data = _git_show(repository, base, relative)
        entry = {
            'path': relative,
            'sha256': _digest(data),
            'bytes': len(data),
            'lines': data.count(b'\n'),
            'base_sha256': _digest(base_data) if base_data else None,
            'base_bytes': len(base_data) if base_data else None,
            'base_lines': (base_data.count(b'\n')
                           if base_data is not None else None),
            'unchanged_from_base': base_data == data,
        }
        files[relative] = entry
    document = {
        'kind': 'LVW_N1_CORRECTION16_SOURCE_PINS/1',
        'candidate_base': base,
        'method': ('The bytes of the seven bound sources were hashed '
                   'and compared with the bytes of the same paths in '
                   'the candidate base of the correction.  Nothing was '
                   'imported, no candidate module was executed and no '
                   'file of the pack was written by this script.'),
        'changed_by_this_correction': [
            relative for relative in BOUND
            if not files[relative]['unchanged_from_base']],
        'unchanged': [relative for relative in UNCHANGED
                      if files[relative]['unchanged_from_base']],
        'production_changed': any(
            not files[relative]['unchanged_from_base']
            for relative in ('tools/v0_s3_native_broker.py',
                             'tools/v0_s3_native_custody.py')),
        'files': files,
    }
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'source-pins.json')
    with open(target, 'w', encoding='utf-8') as stream:
        json.dump(document, stream, indent=1, sort_keys=True)
        stream.write('\n')
    sys.stdout.write(json.dumps({
        'changed_by_this_correction': document['changed_by_this_correction'],
        'production_changed': document['production_changed'],
        'unchanged': len(document['unchanged']),
    }, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
