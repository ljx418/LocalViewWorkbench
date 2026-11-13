"""The offline integration obligations of the S3-P4-OFFLINE workpack.

Section A: the *first* profile binding of the S3 budget regime, the default
S2 behaviour and the reuse of the accepted installed-package factory.

Section C: the controlled video snapshot residue accessor, the parent own
original evidence and the fixed V0-A01..A12 aggregation.

Every test here is offline.  No service is started, no model is called, no
ledger row is written and no host process is spawned.  The runtime seams are
explicit: only the operating system bound primitives of the native runtime
are replaced, while the production profile writers, the production residue
accessor and the accepted quality phase stay the real implementation.
"""
import hashlib
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

import pytest

from tools import v0_s2_stage_runtime as s2_stage
from tools.v0_s2_runtime import NativeRuntime
from tools.v0_s2_stage_runtime import StageRuntimeFactory
from tools.v0_s3_coordinator import (
    AGGREGATE_RECEIPT_KIND, ParentOriginalEvidence, S3BudgetBindingProvider,
    S3InstalledRuntimeFactory, S3IntegrationError, TWELVE_KEYS, aggregate_twelve_keys)
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import program_budget as budget
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import (
    HARD_PEAK_MIB, MODEL_DIGEST, MODEL_TAG)

PACK_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SHA = 'a' * 40
CHILD_SHA = 'b' * 64
RUN_ID = 's3-integration-offline'


# ---------------------------------------------------------------- helpers
def digest_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def synthetic_binding(root, *, run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                      child_sha=CHILD_SHA, model=MODEL_TAG, model_digest=MODEL_DIGEST,
                      issued_at=None, expires_at=None, transport='local-fixture'):
    """A synthetic, sealed S3 budget binding.

    The identities are synthetic on purpose: the real original ledger of
    this package is never opened by this batch.
    """
    root = Path(root)
    for name in ('tools/local_program_authority.py', 'tools/v0_s3_budget_authority.py',
                 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PACK_ROOT / name, target)
    authority = root / 'tools/local_program_authority.py'
    shim = root / 'tools/v0_s3_budget_authority.py'
    protocol = root / 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py'
    ledger = root / 'original.sqlite'
    ledger.write_bytes(b'')
    execution_path = root / 'execution.json'

    def role(path):
        return {'path': str(path), 'client_path': str(path), 'sha256': digest_of(path)}

    roles = {'authority': role(authority), 'shim': role(shim),
             'python': role(Path(sys.executable).resolve()), 'wsl': None}
    execution = {'s3_' + key: {'path': value['path'], 'sha256': value['sha256']}
                 for key, value in roles.items() if value is not None}
    execution['s3_protocol'] = {'path': str(protocol), 'sha256': digest_of(protocol)}
    execution_path.write_text(json.dumps(execution))
    now = time.time() if issued_at is None else issued_at
    expiry = (now + 3600) if expires_at is None else expires_at
    binding_path = root / 'binding.json'
    document = {
        'schema': 'lvw.s3-budget/1', 'program': budget.PROGRAM,
        'approval_sha256': 'c' * 64, 'run_id': run_id, 'stage_id': 'V0-S3',
        'candidate_sha': candidate_sha, 'child_path': str(root / 'child.json'),
        'child_sha256': child_sha, 'ledger_path': str(ledger),
        'execution_path': str(execution_path),
        'execution_sha256': digest_of(execution_path), 'authority_root': str(root),
        'tools': roles, 'issued_at': now, 'expires_at': expiry, 'transport': transport,
        'harness_transport': 'local-fixture' if transport.endswith('fixture') else 'local-wsl',
        'distribution': None, 'binding_path': str(binding_path),
        'client_binding_path': str(binding_path), 'model': model,
        'model_digest': model_digest, 'ollama_pid': 4242, 'ollama_start_ticks': 99,
    }
    binding_path.write_text(json.dumps(document))
    return {'path': str(binding_path), 'sha256': digest_of(binding_path)}, root, document


class FakeArchive:
    """The owned archive seam of the offline tests."""

    def __init__(self):
        self.used = set()
        self.leases = {}
        self.registered = []

    def register(self, root, label, *, _parent_fd=None, _root_fd=None):
        info = Path(root).stat()
        self.leases[label] = (Path(root), info.st_dev, info.st_ino)
        self.used.add(label)
        self.registered.append((label, str(root)))
        return {'label': label, 'root': str(root)}

    def lease(self, label):
        return self.leases[label][0]

    def authorize(self, *args, **kwargs):
        return True

    def __call__(self, context, cleanup):
        # The owned archive closes the root of the finished preparation.  The
        # fake archive owner removes it exactly as the real owner does, so
        # the accepted order rule of the warm preparation stays honest.
        shutil.rmtree(context.root, ignore_errors=True)
        return {'archived': True, 'root': str(context.root)}


class FakeNativeRuntime(NativeRuntime):
    """The explicit fake runtime seam of the offline tests.

    Only the operating system bound primitives are replaced: the listener
    birth, the native clock, the service start, the registry read, the
    sampler and the resource observer.  The production profile writers, the
    production residue accessor and every verification stay untouched.
    """

    def __init__(self, args, evidence):
        super().__init__(args, evidence)
        self.profile_writes = []
        self.comfy_root = None
        self.sampler = None
        self.resource_observer = lambda: {'observed': True}

    def owned_listener_birth(self, port):
        return {'pid': 4242, 'start_ticks': 99, 'name': 'ollama.exe'}

    def native_clock(self):
        return {'platform': 'win32', 'clock_basis': 'native_python_monotonic',
                'monotonic_seconds': time.monotonic(), 'wall_seconds': time.time()}

    def preflight(self):
        return {'max_used_mib': 1024, 'available_ram_mib': 4096,
                'process_match_count': 0, 'target_listener_count': 0}

    def _powershell(self, script):
        if 'FreePhysicalMemory' in script:
            return '4194304'
        raise AssertionError('unexpected native shell request in the offline seam')

    def start_ollama(self, log_path):
        self.ollama_log = Path(log_path)

    def no_cloud_remote_gate(self):
        return {'status': 'LOCAL_ONLY'}

    def verify_model(self):
        return {'model': MODEL_TAG, 'digest': MODEL_DIGEST}

    def start_comfy(self, root, log_path):
        self.comfy_root = Path(root)
        (Path(root) / 'user').mkdir(exist_ok=True)

    def registry(self):
        return {name: {'class_type': name} for name in s2_stage.REQUIRED_NODES}

    def start_sampler(self, run_root, **kwargs):
        self.sampler = kwargs
        return {'stopped': True}

    def ownership_summary(self):
        return {'owned': True}


def build_factory(tmp_path, *, factory_class, provider=None, label='factory'):
    """Build a factory whose preparation can run without a Windows host.

    Three seams are replaced explicitly, because each of them needs a Windows
    host process or a package installation: the protected deployment, the
    public reference preparation and the Comfy CLI identity check.  The
    profile write path itself is never replaced.
    """
    directory = tmp_path / label
    directory.mkdir(parents=True, exist_ok=True)
    directory = directory.resolve()
    image = directory / 'sample.png'
    video = directory / 'sample.mp4'
    image.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 32)
    video.write_bytes(b'\x00\x00\x00\x18ftypmp42' + b'0' * 32)
    paths = {key: directory / (key + '.exe') for key in s2_stage.TOOL_KEYS}
    tool_sha256 = {key: 'd' * 64 for key in s2_stage.TOOL_KEYS}
    archive = FakeArchive()
    calls = []

    def authorize(action, subject):
        calls.append((action, subject))

    def verify_complete():
        return {'binding_scope': None, 'complete_rehash': True,
                'candidate_sha': CANDIDATE_SHA, 'manifest_sha256': 'f' * 64,
                'tool_bindings': {key: {'path': str(path), 'sha256': tool_sha256[key]}
                                  for key, path in paths.items()}}

    artifacts = {'tools/v0_s2_browser_acceptance.cjs': '1' * 64,
                 'tools/v0_s2_browser_policy.cjs': '2' * 64,
                 'LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.ui.json': '3' * 64}
    kwargs = dict(directory=directory, run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                  authorization_sha256=CHILD_SHA, paths=paths, tool_sha256=tool_sha256,
                  source_identity={'candidate_sha': CANDIDATE_SHA,
                                   'execution_artifact_sha256': artifacts},
                  samples={'image': {'path': str(image), 'sha256': digest_of(image),
                                     'bytes': image.stat().st_size},
                           'video': {'path': str(video), 'sha256': digest_of(video),
                                     'bytes': video.stat().st_size}},
                  fixture_plan={'categories': {
                      'tracking': {'path': str(image), 'sha256': digest_of(image),
                                   'bytes': image.stat().st_size},
                      'static': {'path': str(image), 'sha256': digest_of(image),
                                 'bytes': image.stat().st_size}}},
                  model_digest=MODEL_DIGEST, archive=archive, authorize=authorize,
                  verify_complete=verify_complete, guard_critical=lambda: {})
    if issubclass(factory_class, InstalledPackageRuntimeFactory):
        kwargs.update(package_path=directory / 'package.zip', package_sha256='1' * 64,
                      manifest_sha256='2' * 64)
    if factory_class is S3InstalledRuntimeFactory:
        kwargs['s3_budget_provider'] = provider
    factory = factory_class(**kwargs)
    factory._deploy = lambda root: None
    factory._references = lambda driver, root: {'tracking': 'sample.png'}
    factory._user_root = lambda driver, root: {'pid': 4242, 'start_ticks': 99}
    factory._runtime_seam = FakeNativeRuntime
    factory.authorize_calls = calls
    factory.archive_seam = archive
    return factory, directory


def patch_runtime(monkeypatch, factory):
    monkeypatch.setattr(s2_stage, 'NativeRuntime', factory._runtime_seam)


@pytest.fixture
def s2_factory(tmp_path):
    """A plain, accepted S2 factory whose preparation runs offline."""
    factory, directory = build_factory(tmp_path, factory_class=StageRuntimeFactory,
                                       label='s2-factory')
    return factory


# ------------------------------------------------------- A: the first write
def test_s2_private_profile_hook_is_empty_and_changes_no_call():
    """I05: the accepted S2 behaviour of the new hook is the empty mapping."""
    factory = StageRuntimeFactory.__new__(StageRuntimeFactory)
    assert factory._profile_binding_parameters(root=Path('/tmp'), label='default',
                                               baseline=0) == {}


def test_s2_default_preparation_writes_the_plain_profile(s2_factory, monkeypatch):
    """I05: the default S2 preparation writes the unchanged LOCAL01 profile."""
    patch_runtime(monkeypatch, s2_factory)
    context = s2_factory.prepare_default()
    profile = json.loads((Path(context.root) / 'temp/lvw-native-profile.json').read_text())
    assert profile['scope'] == 'V0_S2_NATIVE_CHECKPOINT'
    assert profile['program_authorization_id'] == 'AUTH-PROGRAM-V1-LOCAL-01'
    assert 's3_budget_binding' not in profile
    assert 'child_sha256' not in profile
    assert profile['max_runs'] == 19
    assert s2_factory.authorize_calls[0] == ('prepare_bound_native_runtime', 'default')


def test_s3_first_profile_write_carries_the_budget_binding(tmp_path, monkeypatch):
    """I01: the S3 binding is part of the first exclusive profile write."""
    reference, root, document = synthetic_binding(tmp_path / 'authority')
    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=root, ledger_path=root / 'original.sqlite')
    factory, directory = build_factory(tmp_path, factory_class=S3InstalledRuntimeFactory,
                                       provider=provider)
    patch_runtime(monkeypatch, factory)
    context = factory.prepare_default()
    profile = json.loads((Path(context.root) / 'temp/lvw-native-profile.json').read_text())
    assert profile['scope'] == 'V0_S3_NATIVE_CHECKPOINT'
    assert profile['program_authorization_id'] == budget.PROGRAM
    assert profile['run_id'] == RUN_ID
    assert profile['candidate_sha'] == CANDIDATE_SHA
    assert profile['authorization_sha256'] == CHILD_SHA
    assert profile['child_sha256'] == CHILD_SHA
    assert profile['budget_binding_sha256'] == reference['sha256']
    assert profile['expires_at'] == document['expires_at']
    # The write is the first and only profile: the exclusive create refuses
    # a second write, so there is no LOCAL01 profile that was overwritten.
    with pytest.raises(FileExistsError):
        (Path(context.root) / 'temp/lvw-native-profile.json').open('x')
    assert not (Path(context.root) / 'temp/lvw-warm-profile.json').exists()


def test_s3_warm_first_profile_write_carries_the_budget_binding(tmp_path, monkeypatch):
    """I02: the warm preparation carries the binding on its first write."""
    reference, root, document = synthetic_binding(tmp_path / 'authority')
    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=root, ledger_path=root / 'original.sqlite')
    factory, directory = build_factory(tmp_path, factory_class=S3InstalledRuntimeFactory,
                                       provider=provider)
    patch_runtime(monkeypatch, factory)
    # The accepted factory closes the default root before the warm
    # preparation, so the warm preparation is the second one of the batch.
    # The accepted factory closes the default root before the warm
    # preparation, so the warm preparation is the second one of the batch.
    default_context = factory.prepare_default()
    factory.archive(default_context, {'proven': True})
    context = factory.prepare_warm()
    profile = json.loads((Path(context.root) / 'temp/lvw-warm-profile.json').read_text())
    assert profile['scope'] == 'V0_S3_WARM_BENCHMARK'
    assert profile['run_id'] == RUN_ID
    assert profile['budget_binding_sha256'] == reference['sha256']
    assert not (Path(context.root) / 'temp/lvw-native-profile.json').exists()


def test_s3_factory_inherits_the_accepted_installed_factory():
    """I06: the accepted installed-package factory is inherited, not copied."""
    assert issubclass(S3InstalledRuntimeFactory, InstalledPackageRuntimeFactory)
    assert S3InstalledRuntimeFactory.__mro__[1] is InstalledPackageRuntimeFactory
    source = (PACK_ROOT / 'tools/v0_s3_stage_runtime.py').read_text()
    assert 'class InstalledPackageRuntimeFactory(StageRuntimeFactory)' in source
    assert 'sourcecopy' not in source.lower()


@pytest.mark.parametrize('field,value', [
    ('run_id', 'other-run'),
    ('candidate_sha', 'c' * 40),
    ('authorization_sha256', 'd' * 64),
    ('model_digest', 'e' * 64),
    ('model', 'other-model'),
])
def test_provider_refuses_a_wrong_identity(tmp_path, field, value):
    """I03/I04: a wrong run, candidate, child, model or authority is refused."""
    reference, root, document = synthetic_binding(tmp_path / 'authority')
    arguments = {'binding': reference, 'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA,
                 'authorization_sha256': CHILD_SHA, 'model_digest': MODEL_DIGEST,
                 'model': MODEL_TAG, 'authority_root': root,
                 'ledger_path': root / 'original.sqlite'}
    arguments[field] = value
    provider = S3BudgetBindingProvider(**arguments)
    with pytest.raises(S3IntegrationError) as error:
        provider.parameters(root=Path('/tmp'), label='default', baseline=0)
    assert error.value.reason.startswith('S3_BUDGET_')


def test_provider_refuses_a_missing_binding(tmp_path):
    """I03: a missing budget capability is refused before the first send."""
    provider = S3BudgetBindingProvider(binding=None, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=PACK_ROOT)
    with pytest.raises(S3IntegrationError) as error:
        provider.parameters(root=Path('/tmp'), label='default', baseline=0)
    assert error.value.reason == 'S3_BUDGET_BINDING_CAPABILITY_INVALID'


def test_provider_refuses_a_foreign_authority_and_ledger(tmp_path):
    """I04: a foreign authority root or ledger identity is refused."""
    reference, root, document = synthetic_binding(tmp_path / 'authority')
    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=tmp_path / 'elsewhere',
                                        ledger_path=root / 'original.sqlite')
    with pytest.raises(S3IntegrationError) as error:
        provider.parameters(root=Path('/tmp'), label='default', baseline=0)
    assert error.value.reason == 'S3_BUDGET_AUTHORITY_ROOT_MISMATCH'

    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=root,
                                        ledger_path=root / 'other.sqlite')
    with pytest.raises(S3IntegrationError) as error:
        provider.parameters(root=Path('/tmp'), label='default', baseline=0)
    assert error.value.reason == 'S3_BUDGET_LEDGER_MISMATCH'


def test_provider_refuses_an_expired_binding(tmp_path):
    """I23: an expired binding is refused."""
    now = time.time()
    reference, root, document = synthetic_binding(tmp_path / 'authority',
                                                   issued_at=now - 7200, expires_at=now - 60)
    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=root,
                                        ledger_path=root / 'original.sqlite')
    with pytest.raises(S3IntegrationError) as error:
        provider.parameters(root=Path('/tmp'), label='default', baseline=0)
    assert error.value.reason.startswith('S3_BUDGET_')


def test_provider_refuses_a_drifted_tool(tmp_path):
    """I23: a drifted tool implementation is refused."""
    reference, root, document = synthetic_binding(tmp_path / 'authority')
    (root / 'tools/v0_s3_budget_authority.py').write_text('# drifted\n')
    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=root,
                                        ledger_path=root / 'original.sqlite')
    with pytest.raises(S3IntegrationError) as error:
        provider.parameters(root=Path('/tmp'), label='default', baseline=0)
    assert error.value.reason.startswith('S3_BUDGET_')


def test_provider_returns_only_the_one_allowed_parameter(tmp_path):
    """I01: the provider returns exactly one additional profile parameter."""
    reference, root, document = synthetic_binding(tmp_path / 'authority')
    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=root,
                                        ledger_path=root / 'original.sqlite')
    parameters = provider.parameters(root=Path('/tmp'), label='default', baseline=0)
    assert set(parameters) == {'s3_budget_binding'}
    assert parameters['s3_budget_binding'] == reference


def test_no_real_model_or_ledger_action(tmp_path, monkeypatch):
    """I22: the offline batch performs no model call and no ledger action."""
    calls = []
    monkeypatch.setattr(budget, 'authorize_model_action',
                        lambda *args, **kwargs: calls.append(args))
    reference, root, document = synthetic_binding(tmp_path / 'authority')
    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=root,
                                        ledger_path=root / 'original.sqlite')
    provider.parameters(root=Path('/tmp'), label='default', baseline=0)
    assert calls == []
    assert not (root / 'original.sqlite').stat().st_size


# ------------------------------------------- C: the controlled residue accessor
def make_runtime(root):
    """A native runtime whose only bound root is the given directory."""
    arguments = type('Args', (), {'max_public_submissions': 45, 'warm_benchmark': False,
                                  'native_audit': True, 'max_loopback_requests': 8192,
                                  'max_native_clock_reads': 128, 'ffprobe_exe': None,
                                  'nvidia_exe': '/tmp/nvidia-smi', 'powershell': '/tmp/powershell',
                                  'comfy_main': '/tmp/main.py', 'comfy_python': '/tmp/python',
                                  'ollama_exe': '/tmp/ollama', 'ffmpeg_exe': '/tmp/ffmpeg'})()
    return NativeRuntime(arguments, {'owned_run_root': str(root)})


def test_residue_reports_an_empty_root(tmp_path):
    """I17: an empty residue is an empty list, not an unknown."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    runtime = make_runtime(root)
    runtime.bind_video_snapshot_root(root)
    assert runtime.video_snapshot_residue() == []


def test_residue_reports_the_matching_names(tmp_path):
    """I17: the matching first level names are reported."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    (root / 'temp/lvw-video-0001').mkdir()
    (root / 'temp/lvw-video-0002').mkdir()
    (root / 'temp/other').mkdir()
    runtime = make_runtime(root)
    runtime.bind_video_snapshot_root(root)
    assert runtime.video_snapshot_residue() == ['lvw-video-0001', 'lvw-video-0002']


def test_residue_refuses_an_unbound_root(tmp_path):
    """I17: an unbound accessor is refused."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    runtime = make_runtime(root)
    with pytest.raises(Exception) as error:
        runtime.video_snapshot_residue()
    assert 'VIDEO_SNAPSHOT_ROOT_NOT_BOUND' in str(error.value)


def test_residue_refuses_a_foreign_root(tmp_path):
    """I17: a root that is not the owned run root is refused."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    other = tmp_path / 'other'
    (other / 'temp').mkdir(parents=True)
    runtime = make_runtime(root)
    with pytest.raises(Exception) as error:
        runtime.bind_video_snapshot_root(other)
    assert 'VIDEO_SNAPSHOT_ROOT_NOT_FACTORY_OWNED' in str(error.value)


def test_residue_refuses_a_missing_root(tmp_path):
    """I17: a missing root is refused, never an empty residue."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    runtime = make_runtime(root)
    runtime.bind_video_snapshot_root(root)
    shutil.rmtree(root / 'temp')
    with pytest.raises(Exception) as error:
        runtime.video_snapshot_residue()
    assert 'VIDEO_SNAPSHOT' in str(error.value)


def test_residue_refuses_a_replaced_root(tmp_path):
    """I18: a replaced root is refused."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    runtime = make_runtime(root)
    runtime.bind_video_snapshot_root(root)
    shutil.rmtree(root)
    (root / 'temp').mkdir(parents=True)
    with pytest.raises(Exception) as error:
        runtime.video_snapshot_residue()
    assert 'VIDEO_SNAPSHOT' in str(error.value)


def test_residue_refuses_a_symlinked_match(tmp_path):
    """I18: a symbolic link at a matching name is refused, not skipped."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    (tmp_path / 'outside').mkdir()
    (root / 'temp/lvw-video-0001').symlink_to(tmp_path / 'outside')
    runtime = make_runtime(root)
    runtime.bind_video_snapshot_root(root)
    with pytest.raises(Exception) as error:
        runtime.video_snapshot_residue()
    assert 'VIDEO_SNAPSHOT_RESIDUE_REDIRECT_FORBIDDEN' in str(error.value)


def test_residue_boundaries_are_exact_and_one_over(tmp_path):
    """I18: the internal resource boundaries are exact and one over."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    for index in range(512):
        (root / ('temp/filler-%04d' % index)).mkdir()
    runtime = make_runtime(root)
    runtime.bind_video_snapshot_root(root)
    assert runtime.video_snapshot_residue() == []
    (root / 'temp/filler-0512').mkdir()
    with pytest.raises(Exception) as error:
        runtime.video_snapshot_residue()
    assert 'VIDEO_SNAPSHOT_ENTRY_BUDGET_EXCEEDED' in str(error.value)


def test_residue_name_boundary_is_exact_and_one_over(tmp_path):
    """I18: the residue name boundary is exact and one over."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    for index in range(256):
        (root / ('temp/lvw-video-%04d' % index)).mkdir()
    runtime = make_runtime(root)
    runtime.bind_video_snapshot_root(root)
    assert len(runtime.video_snapshot_residue()) == 256
    (root / 'temp/lvw-video-0256').mkdir()
    with pytest.raises(Exception) as error:
        runtime.video_snapshot_residue()
    assert 'VIDEO_SNAPSHOT_RESIDUE_BUDGET_EXCEEDED' in str(error.value)


def test_residue_binds_once(tmp_path):
    """I17: the accessor binds exactly once."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    runtime = make_runtime(root)
    runtime.bind_video_snapshot_root(root)
    with pytest.raises(Exception) as error:
        runtime.bind_video_snapshot_root(root)
    assert 'VIDEO_SNAPSHOT_ROOT_ALREADY_BOUND' in str(error.value)


def test_s3_factory_binds_the_residue_root_on_its_own_evidence(tmp_path, monkeypatch):
    """I17: the S3 factory binds the accessor on the root that it verified."""
    reference, root, document = synthetic_binding(tmp_path / 'authority')
    provider = S3BudgetBindingProvider(binding=reference, run_id=RUN_ID,
                                        candidate_sha=CANDIDATE_SHA,
                                        authorization_sha256=CHILD_SHA,
                                        model_digest=MODEL_DIGEST, model=MODEL_TAG,
                                        authority_root=root,
                                        ledger_path=root / 'original.sqlite')
    factory, directory = build_factory(tmp_path, factory_class=S3InstalledRuntimeFactory,
                                       provider=provider)
    patch_runtime(monkeypatch, factory)
    context = factory.prepare_default()
    runtime = context.driver
    binding = factory.bind_video_snapshot_root(runtime, 'default')
    assert binding['root'] == str(context.root)
    assert runtime.video_snapshot_residue() == []


# ------------------------------------------- C: the parent original evidence
def sixteen_rows():
    return [{'ordinal': index + 1, 'asset_id': 'asset-%02d' % (index + 1),
             'media_kind': 'image' if index < 10 else 'video',
             'source_sha256': '%064x' % (index + 1), 'source_bytes': 10 + index,
             'input_reference': 'sample-%02d' % (index + 1)} for index in range(16)]


def test_parent_seals_the_plan_and_the_originals(tmp_path):
    """I16: the parent seals the plan, the root and the real original bytes."""
    root = tmp_path / 'run'
    (root / 'temp/s3-quality').mkdir(parents=True)
    (root / 'temp/s3-quality/qd-receipt.json').write_bytes(b'{"rows": []}')
    (root / 'temp/s3-quality/source-plan.json').write_bytes(b'{"plan": 1}')
    (root / 'temp/s3-quality/raw-00.bin').write_bytes(b'raw')
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    plan = evidence.seal_plan(sixteen_rows())
    assert len(plan) == 64
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    originals = evidence.seal_originals(canonical='temp/s3-quality/qd-receipt.json',
                                        source_plan='temp/s3-quality/source-plan.json',
                                        raw=['temp/s3-quality/raw-00.bin'])
    assert originals['canonical'][0]['bytes'] == 12
    assert originals['raw'][0]['sha256'] == hashlib.sha256(b'raw').hexdigest()
    manifest = evidence.manifest()
    assert manifest['row_count'] == 16
    assert manifest['stage_pass_claim'] is False
    # the manifest is the consumption boundary: it re-checks the root and
    # every original before it hands the document out
    assert manifest['reverification']['verified'] is True
    assert len(manifest['reverification']['checked']) == 3


def test_parent_refuses_an_ancestor_link_out_of_the_bound_root(tmp_path):
    """O: an ancestor that points out of the bound root is refused."""
    root = tmp_path / 'run'
    root.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'canonical.json').write_bytes(b'{"rows": []}')
    (outside / 'source.json').write_bytes(b'{"plan": []}')
    (outside / 'raw.bin').write_bytes(b'EXTERNAL')
    (root / 'redirect').symlink_to(outside, target_is_directory=True)
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    with pytest.raises(S3IntegrationError) as error:
        evidence.seal_originals(canonical='redirect/canonical.json',
                                source_plan='redirect/source.json',
                                raw=['redirect/raw.bin'])
    assert error.value.reason == 'S3_ORIGINAL_REDIRECT_FORBIDDEN:canonical'
    # nothing of the escape was sealed
    assert evidence.originals == {}


def test_parent_refuses_a_link_on_the_artifact_itself(tmp_path):
    """O: a link on the artifact itself is refused."""
    root = tmp_path / 'run'
    root.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'canonical.json').write_bytes(b'{"rows": []}')
    (root / 'canonical.json').symlink_to(outside / 'canonical.json')
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    with pytest.raises(S3IntegrationError) as error:
        evidence.seal_originals(canonical='canonical.json',
                                source_plan='canonical.json')
    assert error.value.reason == 'S3_ORIGINAL_REDIRECT_FORBIDDEN:canonical'


def test_the_manifest_refuses_an_original_that_changed_after_the_seal(tmp_path):
    """O: the re-check refuses an original that was rewritten."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    (root / 'temp' / 'raw.bin').write_bytes(b'raw')
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    evidence.seal_originals(canonical='temp/raw.bin', source_plan='temp/raw.bin')
    (root / 'temp' / 'raw.bin').write_bytes(b'REWRITTEN')
    with pytest.raises(S3IntegrationError) as error:
        evidence.manifest()
    assert error.value.reason.startswith('S3_ORIGINAL_')


def test_the_manifest_refuses_an_original_that_was_replaced(tmp_path):
    """O: the re-check refuses an original that was replaced by another file."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    (root / 'temp' / 'raw.bin').write_bytes(b'raw')
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    evidence.seal_originals(canonical='temp/raw.bin', source_plan='temp/raw.bin')
    # the same bytes in another object: the identity of the original changed
    (root / 'temp' / 'raw.bin').unlink()
    (root / 'temp' / 'raw.bin').write_bytes(b'raw')
    with pytest.raises(S3IntegrationError) as error:
        evidence.manifest()
    assert error.value.reason == 'S3_ORIGINAL_REPLACED:canonical'


def test_the_manifest_refuses_an_original_that_vanished(tmp_path):
    """O: the re-check refuses an original that is gone."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    (root / 'temp' / 'raw.bin').write_bytes(b'raw')
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    evidence.seal_originals(canonical='temp/raw.bin', source_plan='temp/raw.bin')
    (root / 'temp' / 'raw.bin').unlink()
    with pytest.raises(S3IntegrationError) as error:
        evidence.manifest()
    assert error.value.reason == 'S3_ORIGINAL_UNREADABLE:canonical'


def test_the_manifest_refuses_a_replaced_root(tmp_path):
    """O: the re-check refuses a root that was replaced after the seal."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    (root / 'temp' / 'raw.bin').write_bytes(b'raw')
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    evidence.seal_originals(canonical='temp/raw.bin', source_plan='temp/raw.bin')
    replacement = tmp_path / 'replacement'
    replacement.mkdir()
    shutil.rmtree(root)
    os.rename(replacement, root)
    with pytest.raises(S3IntegrationError) as error:
        evidence.manifest()
    assert error.value.reason == 'S3_SELECTED_ROOT_REPLACED'


def test_the_manifest_refuses_an_ancestor_link_after_the_seal(tmp_path):
    """O: the re-check refuses an original that was redirected after the seal."""
    root = tmp_path / 'run'
    (root / 'temp').mkdir(parents=True)
    (root / 'temp' / 'raw.bin').write_bytes(b'raw')
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    evidence.seal_originals(canonical='temp/raw.bin', source_plan='temp/raw.bin')
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'raw.bin').write_bytes(b'raw')
    shutil.rmtree(root / 'temp')
    (root / 'temp').symlink_to(outside, target_is_directory=True)
    with pytest.raises(S3IntegrationError) as error:
        evidence.manifest()
    assert error.value.reason == 'S3_ORIGINAL_REDIRECT_FORBIDDEN:canonical'


def test_parent_refuses_an_incomplete_plan(tmp_path):
    """I16: a plan that is not the complete sixteen rows is refused."""
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=tmp_path,
                                       projection_sha256='a' * 64)
    with pytest.raises(S3IntegrationError) as error:
        evidence.seal_plan(sixteen_rows()[:15])
    assert error.value.reason == 'S3_PLAN_INCOMPLETE'


def test_parent_refuses_a_foreign_or_changed_original(tmp_path):
    """I16: a foreign, missing or redirected original is refused."""
    root = tmp_path / 'run'
    (root / 'temp/s3-quality').mkdir(parents=True)
    (root / 'temp/s3-quality/qd-receipt.json').write_bytes(b'{"rows": []}')
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    with pytest.raises(S3IntegrationError) as error:
        evidence.seal_originals(canonical='../outside.json',
                                source_plan='temp/s3-quality/qd-receipt.json')
    assert error.value.reason == 'S3_ORIGINAL_REFERENCE_INVALID'
    with pytest.raises(S3IntegrationError) as error:
        evidence.seal_originals(canonical='temp/s3-quality/missing.json',
                                source_plan='temp/s3-quality/qd-receipt.json')
    assert error.value.reason == 'S3_ORIGINAL_UNREADABLE:canonical'


def test_parent_refuses_a_replaced_selected_root(tmp_path):
    """I16: a replaced selected root is refused."""
    root = tmp_path / 'run'
    root.mkdir()
    evidence = ParentOriginalEvidence(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                                       child_sha256=CHILD_SHA, root=root,
                                       projection_sha256='a' * 64)
    evidence.seal_plan(sixteen_rows())
    identity = os.stat(root)
    evidence.seal_root([identity.st_dev, identity.st_ino])
    # The replacement is allocated while the original still exists, so its
    # object identity is guaranteed to differ from the sealed one.
    replacement = tmp_path / 'replacement'
    replacement.mkdir()
    shutil.rmtree(root)
    os.rename(replacement, root)
    with pytest.raises(S3IntegrationError) as error:
        evidence.verify_selected_root(root)
    assert error.value.reason == 'S3_SELECTED_ROOT_REPLACED'


# ------------------------------------------- C: the twelve key aggregation
def receipt(name, *, status='PASS', run_id=RUN_ID, candidate_sha=CANDIDATE_SHA, **extra):
    document = {'kind': AGGREGATE_RECEIPT_KIND, 'name': name, 'status': status,
                'run_id': run_id, 'candidate_sha': candidate_sha,
                'stage_pass_claim': False, 'product_gate0': False}
    document.update(extra)
    return document


def complete_receipts():
    """Every required receipt of the twelve keys, including the cleanup.

    The cleanup receipt is the legal one of this round: the same kind, the
    same status, the same stage claim flag, the same run and candidate
    binding and the strict boolean proof of the cleanup.
    """
    receipts = {'stage_binding': receipt('stage_binding')}
    for name in ('image_input', 'video_input', 'output_contract', 'manual_export',
                 'no_overwrite', 'file_safety', 'no_approval_gate', 'resource_budget',
                 'cancel_release', 'quality_16_rows'):
        receipts[name] = receipt(name)
    receipts['a06_isolation'] = receipt('a06_isolation', real_isolation=True)
    receipts['install'] = receipt('install')
    receipts['rollback'] = receipt('rollback')
    receipts['independent_score'] = receipt('independent_score', independent=True)
    receipts['webp_format'] = receipt('webp_format')
    receipts['cleanup'] = receipt('cleanup', cleanup_proven=True)
    return receipts


def test_twelve_keys_are_exactly_twelve_and_complete():
    """I19: the summary has exactly the fixed twelve keys."""
    summary = aggregate_twelve_keys(receipts=complete_receipts(),
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert list(summary['keys']) == list(TWELVE_KEYS)
    assert summary['key_count'] == 12
    assert summary['pass_count'] == 12
    assert summary['stage_pass_claim'] is False
    assert summary['product_gate0'] is False


def test_the_cleanup_is_a_required_receipt_of_every_key():
    """C: every key of the summary names the cleanup receipt."""
    for key, entry in aggregate_twelve_keys(
            receipts=complete_receipts(),
            binding={'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA})['keys'].items():
        assert 'cleanup' in entry['required_receipts'], key


def test_a_missing_cleanup_keeps_every_key_not_run():
    """C: without the cleanup receipt no key is green."""
    receipts = complete_receipts()
    del receipts['cleanup']
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['pass_count'] == 0
    assert summary['not_run_count'] == 12
    assert summary['cleanup_proven'] is False
    for entry in summary['keys'].values():
        assert entry['status'] == 'NOT_RUN'
        assert 'cleanup:RECEIPT_MISSING' in entry['reasons']


def test_a_cleanup_without_a_proof_blocks_every_key():
    """C: a cleanup receipt that does not prove the cleanup blocks every key."""
    receipts = complete_receipts()
    receipts['cleanup'] = receipt('cleanup', cleanup_proven=False)
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['pass_count'] == 0
    assert summary['blocked_count'] == 12
    assert summary['cleanup_proven'] is False
    for entry in summary['keys'].values():
        assert entry['status'] == 'BLOCKED'
        assert 'cleanup:CLEANUP_UNPROVEN' in entry['reasons']


def test_a_cleanup_that_only_claims_the_proof_as_a_string_blocks_every_key():
    """C: the string ``true`` is not the proof of a cleanup."""
    receipts = complete_receipts()
    receipts['cleanup'] = receipt('cleanup', cleanup_proven='true')
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['pass_count'] == 0
    assert summary['cleanup_proven'] is False
    for entry in summary['keys'].values():
        assert entry['status'] == 'BLOCKED'
        assert 'cleanup:CLEANUP_UNPROVEN' in entry['reasons']


def test_a_cleanup_without_the_proof_field_blocks_every_key():
    """C: a cleanup receipt that does not state the proof blocks every key."""
    receipts = complete_receipts()
    receipts['cleanup'] = receipt('cleanup')
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['pass_count'] == 0
    assert summary['blocked_count'] == 12


def test_a_failed_cleanup_fails_every_key():
    """C: a failed cleanup keeps the failure of the run."""
    receipts = complete_receipts()
    receipts['cleanup'] = receipt('cleanup', status='FAIL', cleanup_proven=False)
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['pass_count'] == 0
    assert summary['fail_count'] == 12
    for entry in summary['keys'].values():
        assert entry['status'] == 'FAIL'


def test_a_cleanup_of_another_candidate_fails_every_key():
    """C: a cleanup receipt of another candidate never fills the key."""
    receipts = complete_receipts()
    receipts['cleanup'] = receipt('cleanup', candidate_sha='c' * 40, cleanup_proven=True)
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['pass_count'] == 0
    assert summary['fail_count'] == 12
    for entry in summary['keys'].values():
        assert entry['status'] == 'FAIL'
        assert 'cleanup:BINDING_MISMATCH' in entry['reasons']


def test_a_cleanup_of_a_foreign_kind_never_fills_a_green_key():
    """C: a document of another kind is not the cleanup receipt."""
    receipts = complete_receipts()
    receipts['cleanup'] = {'kind': 'S2_PHASE_RECEIPT', 'status': 'PASS',
                           'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA,
                           'stage_pass_claim': False, 'cleanup_proven': True}
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['pass_count'] == 0
    for entry in summary['keys'].values():
        assert entry['status'] == 'NOT_RUN'
        assert 'cleanup:RECEIPT_KIND_NOT_ACCEPTED' in entry['reasons']


def test_a_cleanup_that_claims_a_stage_pass_is_refused():
    """C: a cleanup receipt that claims a stage pass is not accepted."""
    receipts = complete_receipts()
    receipts['cleanup'] = receipt('cleanup', stage_pass_claim=True, cleanup_proven=True)
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['pass_count'] == 0
    for entry in summary['keys'].values():
        assert entry['status'] == 'BLOCKED'
        assert 'cleanup:RECEIPT_STAGE_PASS_CLAIM_INVALID' in entry['reasons']


def test_old_s2_nine_keys_cannot_fill_a_green_key():
    """I19: an old S2 phase receipt is never an accepted aggregate receipt."""
    receipts = complete_receipts()
    receipts['image_input'] = {'kind': 'S2_PHASE_RECEIPT', 'status': 'PASS',
                               'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA,
                               'stage_pass_claim': False}
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['keys']['V0-A01']['status'] == 'NOT_RUN'
    assert summary['old_s2_nine_keys_accepted_as_green'] is False
    assert summary['old_s2_submissions_accepted_as_budget'] is False


def test_a_missing_receipt_keeps_the_key_not_run():
    """I19: a missing receipt keeps the key NOT_RUN."""
    receipts = complete_receipts()
    del receipts['independent_score']
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['keys']['V0-A11']['status'] == 'NOT_RUN'
    assert summary['keys']['V0-A12']['status'] == 'NOT_RUN'


def test_a_missing_independent_score_blocks_the_quality_keys():
    """I20: without an independent quality score the quality keys stay BLOCKED."""
    receipts = complete_receipts()
    receipts['independent_score'] = receipt('independent_score', independent=False)
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['keys']['V0-A11']['status'] == 'BLOCKED'
    assert summary['keys']['V0-A12']['status'] == 'BLOCKED'


def test_a_missing_real_isolation_blocks_the_migration_key():
    """I20: without a real A06 isolation the migration key stays BLOCKED."""
    receipts = complete_receipts()
    receipts['a06_isolation'] = receipt('a06_isolation', real_isolation=False)
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['keys']['V0-A06']['status'] == 'BLOCKED'


def test_a_failed_receipt_fails_the_key():
    """I19: a failed receipt fails its key."""
    receipts = complete_receipts()
    receipts['file_safety'] = receipt('file_safety', status='FAIL')
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['keys']['V0-A07']['status'] == 'FAIL'
    assert summary['fail_count'] == 1


def test_a_receipt_of_another_candidate_fails_the_key():
    """I19: a receipt of another candidate never fills the key."""
    receipts = complete_receipts()
    receipts['video_input'] = receipt('video_input', candidate_sha='c' * 40)
    summary = aggregate_twelve_keys(receipts=receipts,
                                    binding={'run_id': RUN_ID,
                                             'candidate_sha': CANDIDATE_SHA})
    assert summary['keys']['V0-A02']['status'] == 'FAIL'
