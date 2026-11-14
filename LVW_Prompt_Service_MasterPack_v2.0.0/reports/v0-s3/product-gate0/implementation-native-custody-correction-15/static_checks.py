"""The static namespace and signature checks of the correction 15.

The checks are **static**: the two production modules are parsed with
the abstract syntax tree and the names and the signatures that the
correction relies on are read from the tree.  Nothing is imported, no
candidate module is executed, no primitive is called and no file of the
production is written.

Every check names a production owner that the correction of the
correction 15 uses, the method that it calls and the arguments that it
passes.  A check that fails means that the correction would drive an
owner that does not exist: it is a **FAIL** of the delivery and it is
never worked around.

The checks of the correction 14 are kept and the owners of the three
Majors of the correction 15 are added: the **attached** pump of a round
and its context, the **outcome** of a generation of a worker, the
**barrier** of the publication, the **registry** of the started owners
of a session and the **close** of a channel and of its endpoints.

Usage:

    python3 -I -B static_checks.py <pack-root>
"""
import ast
import json
import os
import sys

#: (module, class or None, method, the keyword arguments that are used)
CHECKS = (
    # -- the launcher, the aggregate of a launch and the table ---------
    ('tools/v0_s3_native_broker.py', None, 'launch_broker', ('context',)),
    ('tools/v0_s3_native_broker.py', '_LaunchAggregate', 'release',
     ('deadline', 'clock')),
    ('tools/v0_s3_native_broker.py', '_LaunchAggregate',
     'pending_raw_streams', ()),
    ('tools/v0_s3_native_broker.py', '_LaunchAggregate',
     'retain_raw_stream', ('name', 'stream')),
    ('tools/v0_s3_native_broker.py', '_LaunchAggregate',
     'forget_raw_stream', ('stream',)),
    ('tools/v0_s3_native_broker.py', '_LaunchAggregate', 'bind_process',
     ('process',)),
    ('tools/v0_s3_native_broker.py', '_LauncherCustody', 'release',
     ('deadline', 'context')),
    ('tools/v0_s3_native_broker.py', '_LauncherCustody', 'items', ()),
    ('tools/v0_s3_native_broker.py', '_LauncherCustody', 'retain',
     ('kind', 'resource', 'detail', 'launch')),
    ('tools/v0_s3_native_broker.py', '_LauncherCustody', 'forget',
     ('resource',)),
    ('tools/v0_s3_native_broker.py', '_LaunchProgress', 'fact', ('key',)),
    ('tools/v0_s3_native_broker.py', '_LaunchProgress', 'record', ()),
    # -- the channel, the endpoints and the workers --------------------
    ('tools/v0_s3_native_broker.py', 'StreamChannel', '__init__',
     ('clock', 'context', 'custody')),
    ('tools/v0_s3_native_broker.py', 'StreamChannel', 'read', ('timeout',)),
    ('tools/v0_s3_native_broker.py', 'StreamChannel', 'bind_deadline',
     ('deadline',)),
    ('tools/v0_s3_native_broker.py', 'StreamChannel', 'bind_context',
     ('context',)),
    ('tools/v0_s3_native_broker.py', 'StreamChannel', 'close', ()),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeEndpoint', '__init__',
     ('name', 'api', 'clock', 'handle', 'context')),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeEndpoint', 'read',
     ('deadline', 'cancel')),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeEndpoint', 'close', ()),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeEndpoint', 'bind_deadline',
     ('deadline',)),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeEndpoint', 'bind_context',
     ('context',)),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeWorker', 'outcome',
     ('generation',)),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeWorker', 'wait_done',
     ('generation', 'timeout')),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeWorker', 'join_bounded',
     ('seconds',)),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeWorker', 'stop_accepting',
     ()),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeWorker', 'submit',
     ('request',)),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeWorker', 'request_cancel',
     ('deadline',)),
    ('tools/v0_s3_native_broker.py', 'BrokerProcess', 'read', ('timeout',)),
    ('tools/v0_s3_native_broker.py', 'BrokerProcess', 'close', ('deadline',)),
    ('tools/v0_s3_native_broker.py', 'BrokerCore', '__init__',
     ('win32', 'plan', 'run_root', 'clock')),
    ('tools/v0_s3_native_broker.py', 'BrokerCore', 'bind_absolute_deadline',
     ('deadline',)),
    ('tools/v0_s3_native_broker.py', 'BrokerLoop', '__init__',
     ('core', 'transport', 'plan', 'nonce', 'clock', 'wall')),
    ('tools/v0_s3_native_broker.py', 'BrokerLoop', '_stop',
     ('reason', 'exit_code')),
    ('tools/v0_s3_native_broker.py', 'WindowsApi', 'bind_context',
     ('context',)),
    # -- the parent side of the round ----------------------------------
    ('tools/v0_s3_native_custody.py', 'NativeCustodySession', '__init__',
     ('plan', 'run_root', 'parent_child_remaining_seconds', 'launcher',
      'clock', 'wall', 'nonce')),
    ('tools/v0_s3_native_custody.py', 'NativeCustodySession', 'start', ()),
    ('tools/v0_s3_native_custody.py', 'NativeCustodySession', 'stop', ()),
    ('tools/v0_s3_native_custody.py', 'NativeCustodySession', '_read_reply',
     ('kinds', 'timeout')),
    ('tools/v0_s3_native_custody.py', 'NativeCustodySession', 'evidence',
     ()),
    ('tools/v0_s3_native_custody.py', 'NativeCustodySession',
     'remaining_seconds', ()),
    ('tools/v0_s3_native_custody.py', '_ChannelPump', '__init__',
     ('broker', 'decode', 'clock', 'on_error', 'context')),
    ('tools/v0_s3_native_custody.py', '_ChannelPump', 'run', ()),
    ('tools/v0_s3_native_custody.py', '_ChannelPump', 'take',
     ('kinds', 'deadline')),
    ('tools/v0_s3_native_custody.py', '_ChannelPump', 'stop', ()),
    ('tools/v0_s3_native_custody.py', '_ChannelPump', 'join_bounded',
     ('seconds',)),
    ('tools/v0_s3_native_custody.py', '_ReplyWaiter', '__init__', ('kinds',)),
    ('tools/v0_s3_native_custody.py', '_CustodyContext',
     'effective_deadline', ('call', 'bound')),
    ('tools/v0_s3_native_custody.py', '_CustodyContext',
     'publish_cleanup_deadline', ('value',)),
    ('tools/v0_s3_native_custody.py', '_CustodyContext',
     'bind_absolute_deadline', ('deadline',)),
    ('tools/v0_s3_native_custody.py', '_CustodyContext',
     'cleanup_deadline_value', ()),
)

#: The attributes of the production objects that the correction reads.
ATTRIBUTES = (
    ('tools/v0_s3_native_broker.py', '_LaunchAggregate',
     ('process', 'channel', 'workers', 'endpoints', 'raw_streams',
      'progress', 'facts', 'context')),
    ('tools/v0_s3_native_broker.py', '_LauncherCustody',
     ('_items', '_context')),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeWorker',
     ('outcome_published', '_submitted', '_outcomes', 'inside')),
    ('tools/v0_s3_native_broker.py', 'BrokerProcess', ('_channel',)),
    ('tools/v0_s3_native_broker.py', 'BrokerCore', ('context',)),
    ('tools/v0_s3_native_broker.py', 'StreamChannel',
     ('_thread', '_reader', '_writer', '_queue', '_context', '_deadline')),
    ('tools/v0_s3_native_broker.py', '_WindowsPipeEndpoint',
     ('_reader', '_writer', '_context', '_deadline', '_api')),
    ('tools/v0_s3_native_custody.py', 'NativeCustodySession',
     ('_pump', '_context', 'broker', 'state', '_background_threads',
      '_closer_threads', '_heartbeat')),
    ('tools/v0_s3_native_custody.py', '_ChannelPump',
     ('finished', 'error', 'alive', 'frames', '_pending', '_waiters',
      '_context', '_broker', '_decode', '_clock', '_finished', '_eof')),
    ('tools/v0_s3_native_custody.py', '_CustodyContext',
     ('clock', 'absolute_deadline', 'cleanup_deadline_value', 'cancel')),
    ('tools/v0_s3_native_custody.py', '_ReplyWaiter', ('event', 'reply')),
)


def _arguments(node):
    names = set()
    for argument in list(node.args.args) + list(node.args.kwonlyargs):
        names.add(argument.arg)
    return names


def _tree(pack_root, relative):
    path = os.path.join(pack_root, relative)
    with open(path, 'r', encoding='utf-8') as stream:
        return ast.parse(stream.read(), filename=path)


def main(argv):
    if len(argv) != 2:
        sys.stderr.write('usage: static_checks.py <pack-root>\n')
        return 2
    pack_root = argv[1]
    trees = {}
    results = []
    failures = 0
    for relative, class_name, method, keywords in CHECKS:
        if relative not in trees:
            trees[relative] = _tree(pack_root, relative)
        tree = trees[relative]
        owner = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                owner = node
                break
            if class_name is None and isinstance(node, ast.FunctionDef) \
                    and node.name == method:
                owner = node
                break
        if owner is None:
            results.append({'module': relative, 'owner': class_name,
                            'member': method, 'ok': False,
                            'detail': 'the owner does not exist'})
            failures += 1
            continue
        function = None
        if class_name is None:
            # The member is a module level function: the owner **is**
            # the member.
            function = owner
        else:
            for node in owner.body:
                if isinstance(node, ast.FunctionDef) and node.name == method:
                    function = node
                    break
        if function is None:
            results.append({'module': relative, 'owner': class_name,
                            'member': method, 'ok': False,
                            'detail': 'the member does not exist'})
            failures += 1
            continue
        names = _arguments(function)
        missing = [name for name in keywords if name not in names]
        ok = not missing
        if not ok:
            failures += 1
        results.append({'module': relative, 'owner': class_name,
                        'member': method, 'ok': ok,
                        'keywords': list(keywords),
                        'detail': ('missing arguments: %s'
                                   % ', '.join(missing)) if missing
                        else 'the signature carries the arguments'})
    for relative, class_name, attributes in ATTRIBUTES:
        if relative not in trees:
            trees[relative] = _tree(pack_root, relative)
        tree = trees[relative]
        owner = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                owner = node
                break
        found = set()
        if owner is not None:
            for node in ast.walk(owner):
                if isinstance(node, ast.Attribute) and \
                        isinstance(node.value, ast.Name) and \
                        node.value.id == 'self':
                    found.add(node.attr)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and \
                                isinstance(target.value, ast.Name) and \
                                target.value.id == 'self':
                            found.add(target.attr)
            # A **property** of the owner is an attribute of it too.
            for node in owner.body:
                if not isinstance(node, ast.FunctionDef):
                    continue
                for decorator in node.decorator_list:
                    name = getattr(decorator, 'id', None)
                    if name in ('property', 'cached_property'):
                        found.add(node.name)
        missing = [name for name in attributes if name not in found]
        ok = not missing
        if not ok:
            failures += 1
        results.append({'module': relative, 'owner': class_name,
                        'member': 'attributes', 'ok': ok,
                        'attributes': list(attributes),
                        'detail': ('missing attributes: %s'
                                   % ', '.join(missing)) if missing
                        else 'every attribute is written or read'})
    document = {'kind': 'LVW_N1_CORRECTION15_STATIC_CHECKS/1',
                'method': ('The two production modules are parsed with the '
                           'AST and the names, the signatures and the '
                           'attributes that the correction uses are read '
                           'from the tree.  Nothing is imported, no '
                           'candidate module is executed and no primitive '
                           'is called.'),
                'checks': results,
                'failed': failures,
                'passed': len(results) - failures}
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'static-checks.json')
    with open(target, 'w', encoding='utf-8') as stream:
        json.dump(document, stream, indent=1, sort_keys=True)
        stream.write('\n')
    sys.stdout.write(json.dumps({'passed': document['passed'],
                                  'failed': failures}) + '\n')
    for item in results:
        if not item['ok']:
            sys.stdout.write('FAILED %s %s %s: %s\n' % (
                item['module'], item['owner'], item['member'],
                item['detail']))
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
