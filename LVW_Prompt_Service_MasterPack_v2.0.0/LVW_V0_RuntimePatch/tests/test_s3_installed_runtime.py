"""Real Git build/install/prepare; only native service boundaries are synthetic."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

import pytest

from tools import v0_incremental_package as package
from tools import v0_s2_stage_runtime as legacy
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory
from tools.v0_s2_stage_archive import OwnedArchive
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.tests import test_s2_stage_runtime as native_fixture
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import MODEL_DIGEST


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def fixture(monkeypatch):
    with tempfile.TemporaryDirectory(prefix='lvw-p3a-owned-') as temporary:
        root = Path(temporary).resolve()
        repo = root / 'synthetic-git'; repo.mkdir()
        pack = repo / 'pack'; pack.mkdir()
        original_popen = subprocess.Popen
        def guarded(command, *args, **kwargs):
            assert isinstance(command, list) and command[0] == 'git', 'host subprocess forbidden'
            assert not kwargs.get('shell'), 'shell forbidden'
            cwd = Path(kwargs.get('cwd', repo)).resolve()
            assert cwd == repo or cwd.is_relative_to(repo), 'only synthetic Git allowed'
            if '-C' in command:
                assert Path(command[command.index('-C') + 1]).resolve() == repo
            return original_popen(command, *args, **kwargs)
        monkeypatch.setattr(subprocess, 'Popen', guarded)
        monkeypatch.setattr(os, 'system', lambda *a: pytest.fail('shell forbidden'))
        def git(*args):
            return subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True).stdout.decode().strip()
        payload = {
            package.BRIDGE_SOURCE_DIR + '/__init__.py': b'# synthetic bridge\n',
            package.BRIDGE_SOURCE_DIR + '/core.py': b'SYNTHETIC = True\n',
            package.BRIDGE_SOURCE_DIR + '/web/panel.js': b'// synthetic panel\n',
            package.WORKFLOWS_SOURCE_DIR + '/video_reverse_prompt_v0.ui.json': b'{"synthetic":true}\n',
            package.WORKFLOWS_SOURCE_DIR + '/manual.json': b'{"synthetic":"manual"}\n',
        }
        for name, raw in payload.items():
            path = pack / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        tool = pack / 'tools/v0_incremental_package.py'; tool.parent.mkdir(); tool.write_text('# synthetic packaged tool identity\n')
        git('init', '-q'); git('add', '.')
        git('-c', 'user.name=ljx418', '-c', 'user.email=1173696783@qq.com', 'commit', '-qm', 'synthetic payload')
        candidate = git('rev-parse', 'HEAD')
        # Relocate module metadata for its existing repository-prefix resolver;
        # all build/install/validation functions remain the real owners.
        monkeypatch.setattr(package, '__file__', str(tool))
        archive_path = root / 'payload.zip'
        build = package.command_build(SimpleNamespace(repo=repo, commit=candidate, out=archive_path, receipt_out=None, redact_root=[]))
        assert build['package']['size_bytes'] <= package.SIZE_LIMIT_BYTES
        assert build['payload']['expanded_bytes'] <= package.SIZE_LIMIT_BYTES
        # The installed bytes must come from Git/archive, never this dirty source.
        for name in payload:
            (pack / name).write_bytes(b'DIRTY SOURCE MUST NEVER BE COPIED\n')
        directory = root / '隔离 runtime'; directory.mkdir()
        marker = directory / package.SANDBOX_MARKER_NAME
        marker.write_text(json.dumps({'magic': package.SANDBOX_MARKER_MAGIC, 'tool': package.TOOL_NAME}))
        sentinel = root / 'unrelated.txt'; sentinel.write_bytes(b'UNRELATED ORIGINAL')
        sibling = directory / 'other-run'; sibling.mkdir(); (sibling / 'keep').write_bytes(b'OTHER RUN')
        paths = {}
        for key in legacy.TOOL_KEYS:
            path = root / key; path.write_bytes(b'synthetic tool only'); paths[key] = path
        samples = {}
        for kind in ('image', 'video'):
            path = root / (kind + '.dat'); raw = ('synthetic ' + kind).encode(); path.write_bytes(raw)
            samples[kind] = dict(path=str(path), bytes=len(raw), sha256=sha(raw))
        plan = {'categories': {}, 'negatives': {}}
        for group, names in [('categories', ['static', 'tracking', 'fast-cut', 'vfr']),
                             ('negatives', ['over-duration', 'fake-extension.mp4', 'corrupt.mp4', 'truncated.mov'])]:
            for index, name in enumerate(names):
                path = pack / (group + str(index) + '.dat'); raw = ('synthetic ' + name).encode(); path.write_bytes(raw)
                plan[group][name] = dict(path=path.name, bytes=len(raw), sha256=sha(raw))
        identity = {'candidate_sha': candidate, 'execution_artifact_sha256': {name: sha(raw) for name, raw in payload.items()}}
        identity['execution_artifact_sha256'].update({'tools/v0_s2_browser_acceptance.cjs': 'c'*64,
                                                     'tools/v0_s2_browser_policy.cjs': 'd'*64})
        archive = OwnedArchive(directory, run_id='p3a-fixture', candidate_sha=candidate,
                               authorization_sha256='b'*64, authorize=lambda *a: None)
        helper = native_fixture.FactoryTests()
        helper.directory = directory; helper.events = []; helper.failure = None
        kwargs = dict(directory=directory, run_id='p3a-fixture', candidate_sha=candidate,
                      authorization_sha256='b'*64, paths=paths, tool_sha256={key: sha(path.read_bytes()) for key, path in paths.items()},
                      source_identity=identity, samples=samples, fixture_plan=plan, model_digest=MODEL_DIGEST,
                      archive=archive, authorize=lambda *a: None,
                      guard_critical=lambda: None, package_path=archive_path,
                      package_sha256=build['package']['sha256'], manifest_sha256=build['manifest']['sha256'])
        kwargs['verify_complete'] = lambda: dict(complete_rehash=True, candidate_sha=kwargs['candidate_sha'], manifest_sha256='e'*64,
            tool_bindings={key: dict(path=str(path), sha256=kwargs['tool_sha256'][key]) for key, path in paths.items()})
        monkeypatch.setattr(legacy, 'ROOT', pack)
        def native(args, evidence):
            driver = helper.native(args, evidence)
            powershell = driver._powershell
            def quoted(script):
                if 'CommandLine' in script:
                    values = [driver._windows_path(args.comfy_python), '-s', '-B', driver._windows_path(args.comfy_main),
                              '--listen', '127.0.0.1', '--port', '8191', '--base-directory', driver._windows_path(str(driver.root)),
                              '--user-directory', driver._windows_path(str(driver.root / 'user')), '--disable-auto-launch',
                              '--disable-api-nodes', '--disable-all-custom-nodes', '--whitelist-custom-nodes', 'lvw_v0_bridge']
                    return ' '.join('"' + value + '"' for value in values)
                return powershell(script)
            driver._powershell = quoted
            start = driver.start_comfy
            def start_comfy(target, log):
                assert evidence['deployment']['status'] == 'VERIFIED'
                assert evidence['deployment']['target'] == str(target)
                return start(target, log)
            driver.start_comfy = start_comfy
            return driver
        monkeypatch.setattr(legacy, 'NativeRuntime', native)
        monkeypatch.setattr(legacy.StageRuntimeFactory, '_deploy', lambda *a: pytest.fail('source copy forbidden'))
        state = SimpleNamespace(**locals())
        yield state
        # This owned synthetic fixture (including retained negative roots) is
        # removed by TemporaryDirectory, never promoted to product evidence.
    assert not root.exists()


def assert_failure(f, factory):
    with pytest.raises((EvidenceError, package.PackageError, OSError, ValueError)):
        factory.prepare_default()
    assert 'ollama-start' not in f.helper.events and 'comfy-start' not in f.helper.events
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    assert (f.sibling / 'keep').read_bytes() == b'OTHER RUN'
    failure = json.loads((f.directory / 'default-preparation-failure.json').read_text())
    assert failure['stage_pass_claim'] is False
    assert failure['root_retained'] or failure['archive']['proven']
    assert failure['evidence']['candidate_sha'] == factory.candidate
    return failure


def test_inherited_default_then_warm_install_exact_runtime_root(fixture):
    f = fixture
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    assert InstalledPackageRuntimeFactory._prepare is legacy.StageRuntimeFactory._prepare
    for label in ('default', 'warm'):
        context = factory.prepare_default() if label == 'default' else factory.prepare_warm()
        receipt = json.loads((f.directory / (label + '-package-install.json')).read_text())
        assert receipt['target'] == str(context.root) == str(context.driver.root)
        assert f.archive.lease(label) == context.root
        assert context.binding['candidate_sha'] == f.candidate
        assert factory.evidence[label]['deployment']['status'] == 'VERIFIED'
        assert factory.evidence[label]['deployment']['payload_files'] == len(f.payload)
        assert (context.root / package.OWNERSHIP_FILE_NAME).exists()
        for item in f.build['payload']['items']:
            raw = (context.root / item['install_path']).read_bytes()
            assert raw == f.payload[item['source_path']]
            assert (sha(raw), len(raw)) == (item['sha256'], item['length'])
        assert f.archive(context, context.driver.cleanup())['proven']
        assert not context.root.exists()
        assert (f.directory / (label + '-raw') / package.OWNERSHIP_FILE_NAME).exists()
    assert f.helper.events.count('comfy-start') == 2


@pytest.mark.parametrize('case', ['old-candidate', 'package-hash', 'manifest-hash', 'bad-digest',
    'missing-bridge', 'extra-bridge', 'bridge-hash', 'workflow-unsealed', 'workflow-hash',
    'missing-marker', 'invalid-marker', 'marker-link', 'package-link', 'package-oversize'])
def test_preinstall_refusals_persist_and_never_start(fixture, case):
    f = fixture; kwargs = f.kwargs
    sealed = kwargs['source_identity']['execution_artifact_sha256']
    if case == 'old-candidate':
        kwargs['candidate_sha'] = 'a'*40; kwargs['source_identity']['candidate_sha'] = 'a'*40
    elif case == 'package-hash': kwargs['package_sha256'] = '0'*64
    elif case == 'manifest-hash': kwargs['manifest_sha256'] = '0'*64
    elif case == 'bad-digest': kwargs['package_sha256'] = 'not a hash'
    elif case == 'missing-bridge': sealed.pop(package.BRIDGE_SOURCE_DIR + '/core.py')
    elif case == 'extra-bridge': sealed[package.BRIDGE_SOURCE_DIR + '/extra.py'] = '0'*64
    elif case == 'bridge-hash': sealed[package.BRIDGE_SOURCE_DIR + '/core.py'] = '0'*64
    elif case == 'workflow-unsealed': sealed.pop(package.WORKFLOWS_SOURCE_DIR + '/manual.json')
    elif case == 'workflow-hash': sealed[package.WORKFLOWS_SOURCE_DIR + '/manual.json'] = '0'*64
    elif case == 'missing-marker': f.marker.unlink()
    elif case == 'invalid-marker': f.marker.write_text('{}')
    elif case == 'marker-link':
        original = f.root / 'marker'; f.marker.rename(original); f.marker.symlink_to(original)
    elif case == 'package-link':
        link = f.root / 'linked.zip'; link.symlink_to(f.archive_path); kwargs['package_path'] = link
    elif case == 'package-oversize':
        with f.archive_path.open('wb') as stream: stream.truncate(package.SIZE_LIMIT_BYTES + 1)
    assert_failure(f, InstalledPackageRuntimeFactory(**kwargs))


@pytest.mark.parametrize('case', ['bridge-bytes', 'workflow-bytes', 'extra-file', 'missing-file',
    'payload-link', 'owner-bytes', 'receipt-identity', 'marker-drift', 'install-failure'])
def test_installer_and_postinstall_refusals_before_start(fixture, monkeypatch, case):
    f = fixture; install = package.command_install
    def changed(args):
        receipt = install(args)
        target = Path(args.target)
        bridge = target / package.BRIDGE_INSTALL_DIR / 'core.py'
        if case == 'bridge-bytes': bridge.write_bytes(b'changed')
        elif case == 'workflow-bytes': (target / package.WORKFLOWS_INSTALL_DIR / 'manual.json').write_bytes(b'changed')
        elif case == 'extra-file': (bridge.parent / 'extra.py').write_bytes(b'extra')
        elif case == 'missing-file': bridge.unlink()
        elif case == 'payload-link': bridge.unlink(); bridge.symlink_to(f.sentinel)
        elif case == 'owner-bytes': (target / package.OWNERSHIP_FILE_NAME).write_bytes(b'{}')
        elif case == 'receipt-identity': receipt['target'] = str(f.sibling)
        elif case == 'marker-drift': f.marker.write_text(f.marker.read_text() + '\n')
        return receipt
    if case == 'install-failure':
        rename = package.os.rename
        def fail_owned(source, target, *a, **kw):
            if (str(target).endswith(package.WORKFLOWS_INSTALL_DIR)
                    or (str(target) == 'lvw' and kw.get('dst_dir_fd') is not None)):
                raise OSError('synthetic install transaction failure')
            return rename(source, target, *a, **kw)
        monkeypatch.setattr(package.os, 'rename', fail_owned)
    else:
        monkeypatch.setattr(package, 'command_install', changed)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    assert result['evidence']['deployment']['status'] == 'FAILED'
    if case != 'install-failure': assert (f.directory / 'default-package-install.json').exists()
    if case == 'payload-link': assert result['root_retained']


@pytest.mark.parametrize('case', ['directory', 'outside', 'symlink', 'unregistered', 'child-link', 'replaced-root'])
def test_prepare_rejects_wrong_registered_target(fixture, monkeypatch, case):
    f = fixture
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    original = factory._deploy
    def redirect(root):
        if case == 'directory': target = f.directory
        elif case == 'outside': target = f.root
        elif case == 'symlink':
            target = f.directory / 'redirect'; target.symlink_to(root, target_is_directory=True)
        elif case == 'child-link':
            (root / 'custom_nodes').rmdir()
            (root / 'custom_nodes').symlink_to(f.sibling, target_is_directory=True)
            target = root
        elif case == 'replaced-root':
            root.rename(f.directory / 'original-registered-root')
            root.mkdir(); target = root
        else: target = f.sibling
        original(target)
    monkeypatch.setattr(factory, '_deploy', redirect)
    assert_failure(f, factory)
