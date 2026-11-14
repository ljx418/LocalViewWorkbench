"""The exact identity and the exact order of the 189 nodes of the batch.

The check is **static**: the node ids are extracted with the abstract
syntax tree of the five modules of the batch.  Nothing is imported, no
collection is run, no candidate module is executed, no primitive is
called and no file of the batch is written by this script.  The script
reads the source of the five modules and the frozen list of the plan of
the root and it writes **one** JSON document.

The frozen list is the list of the plan of the root of the correction
13 (``native-custody-correction-13/validation-plan-01/plan.json``).
The copy that is read here is the list that the correction 14 proved to
be equal to it (``implementation-native-custody-correction-14/
node-identity.json``).  It is read only and it is never rewritten.

Usage:

    python3 -I -B node_identity.py <pack-root> <frozen-node-identity.json>
"""
import ast
import json
import os
import sys

#: The five modules of the batch in the order of the frozen list.
MODULES = (
    'tools/test_v0_s3_native_custody.py',
    'tools/test_v0_s3_native_custody_regressions.py',
    'tools/test_v0_s3_native_custody_correction05.py',
    'tools/test_v0_s3_native_custody_correction07.py',
    'tools/test_v0_s3_native_custody_correction10.py',
)


def derived_nodeids(pack_root):
    """The node ids of the five modules, in the order of the definitions."""
    nodeids = []
    for relative in MODULES:
        path = os.path.join(pack_root, relative)
        with open(path, 'r', encoding='utf-8') as stream:
            tree = ast.parse(stream.read(), filename=path)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith('test_'):
                continue
            nodeids.append('%s::%s' % (relative, node.name))
    return nodeids


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: node_identity.py <pack-root> '
                         '<frozen-node-identity.json>\n')
        return 2
    pack_root, frozen_path = argv[1], argv[2]
    with open(frozen_path, 'r', encoding='utf-8') as stream:
        frozen_document = json.load(stream)
    frozen = list(frozen_document['nodeids'])
    derived = derived_nodeids(pack_root)
    added = [node for node in derived if node not in frozen]
    removed = [node for node in frozen if node not in derived]
    document = {
        'kind': 'LVW_N1_CORRECTION15_NODE_IDENTITY/1',
        'coordinate': 'V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION',
        'method': ('The node ids of the five modules were extracted with '
                   'the AST (no collection, no import, no execution) in '
                   'the order of the definitions and compared with the '
                   'frozen list of the plan of the root of the correction '
                   '13 (carried by the proved list of the correction 14).'),
        'frozen_source': os.path.abspath(frozen_path),
        'frozen_count': len(frozen),
        'derived_count': len(derived),
        'identical': derived == frozen,
        'order_preserved': derived == frozen,
        'node_order_is_binding': True,
        'added': added,
        'removed': removed,
        'nodeids': derived,
    }
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'node-identity.json')
    with open(target, 'w', encoding='utf-8') as stream:
        json.dump(document, stream, indent=1, sort_keys=True)
        stream.write('\n')
    sys.stdout.write(json.dumps({key: document[key] for key in
                                  ('frozen_count', 'derived_count',
                                   'identical', 'order_preserved',
                                   'added', 'removed')},
                                 sort_keys=True) + '\n')
    return 0 if document['identical'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
