"""The identity of the 189 frozen nodes, in their frozen order.

The script is **static**: it reads the five modules as text, it parses
them with the standard ``ast`` module and it writes the identity of
every node.  It never imports, collects or executes a module.

The order is compared with the frozen order of the correction 18: the
189 node ids keep their identity **and** their order.

Usage::

    python3 -I node_identity.py <package-root> <output.json>
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

MODULES = (
    ('tools/test_v0_s3_native_custody.py', 117),
    ('tools/test_v0_s3_native_custody_regressions.py', 16),
    ('tools/test_v0_s3_native_custody_correction05.py', 24),
    ('tools/test_v0_s3_native_custody_correction07.py', 18),
    ('tools/test_v0_s3_native_custody_correction10.py', 14),
)

#: The frozen order of the correction 18: the reference of the order.
FROZEN_REFERENCE = ('reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-18/'
                    'node-identity.json')


def main(root, output):
    root = Path(root)
    nodeids = []
    modules = {}
    total = 0
    for name, count in MODULES:
        data = (root / name).read_bytes()
        tree = ast.parse(data.decode('utf-8'))
        found = []
        for item in tree.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith(
                    'test_'):
                found.append({
                    'name': item.name,
                    'args': [arg.arg for arg in item.args.args],
                    'decorators': [ast.dump(dec) for dec in item.decorator_list],
                    'lineno': item.lineno,
                })
                nodeids.append('%s::%s' % (name, item.name))
        skipped = []
        for item in ast.walk(tree):
            if isinstance(item, ast.Call) and isinstance(item.func,
                                                         ast.Attribute) \
                    and item.func.attr in ('skip', 'xfail', 'skipif'):
                skipped.append(item.func.attr)
        modules[name] = {
            'count': len(found),
            'expected': count,
            'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'nodes': found,
            'skip_or_xfail_calls': skipped,
        }
        total += len(found)
    frozen = json.loads((root / FROZEN_REFERENCE).read_text(encoding='utf-8'))
    reference = frozen['denominator']['frozen_order']
    document = {
        'kind': 'lvw.s3-native-custody-node-identity/1',
        'candidate': 'the correction 19 static candidate',
        'denominator': {
            'count': total,
            'unique': len(set(nodeids)),
            'frozen_order': nodeids,
        },
        'order_unchanged': nodeids == reference,
        'order_reference': FROZEN_REFERENCE,
        'order_reference_count': len(reference),
        'modules': modules,
    }
    Path(output).write_text(json.dumps(document, indent=1, sort_keys=True),
                             encoding='utf-8')
    print(json.dumps({'count': total, 'unique': len(set(nodeids)),
                      'order_unchanged': nodeids == reference,
                      'modules': {k: v['count'] for k, v in modules.items()}},
                     sort_keys=True))
    return 0 if (total == 189 and len(set(nodeids)) == 189
                 and nodeids == reference) else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
