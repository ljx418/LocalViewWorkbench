"""Bounded independent assertions for corrected factory context lifetimes."""
import json
from types import SimpleNamespace
import pytest
from LVW_V0_RuntimePatch.tests.test_s3_installed_runtime import fixture
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory
from tools.v0_s2_stage_runtime import TOOL_KEYS
from tools.v0_s2_checkpoint_oracles import EvidenceError

@pytest.mark.parametrize('callback', ['verify_bindings', 'authorize_launch'])
def test_returned_browser_context_remains_usable_after_prepare(fixture, monkeypatch, callback):
    f = fixture
    actions = []
    kwargs = dict(f.kwargs)
    kwargs['authorize'] = lambda *args: actions.append(args)
    kwargs['guard_critical'] = lambda: {'complete_rehash':False, 'manifest_sha256':'e'*64,
                                      'critical_files':[key.upper() for key in TOOL_KEYS]}
    factory = InstalledPackageRuntimeFactory(**kwargs)
    context = factory.prepare_default()
    assert factory._parent_fd is None and factory._root_fds == {}
    before = len(actions)
    try:
        if callback == 'verify_bindings':
            result = context.verify_bindings(context.browser_config, 'independent-probe')
        else:
            result = context.authorize_launch(context.browser_config)
    except Exception as error:
        print('RETURNED_BROWSER_CONTEXT ' + json.dumps({'callback':callback,
            'error_type':type(error).__name__, 'error':str(error),
            'authority_calls_after_prepare':len(actions)-before,
            'parent_fd':factory._parent_fd, 'root_exists':context.root.exists()},sort_keys=True))
        raise
    assert result['owned_run_root'] == str(context.root)
    assert result['ephemeral_user_root_verified'] is True
    assert len(actions) > before
    assert factory.archive(context, context.driver.cleanup())['proven']

@pytest.mark.parametrize('field', ['candidate_sha','authorization_sha256','run_id'])
def test_archive_context_mismatch_refused_before_owner_side_effects(fixture, field):
    f = fixture
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    context = factory.prepare_default()
    cleanup = context.driver.cleanup()
    bad = SimpleNamespace(root=context.root, driver=context.driver, binding={**context.binding,field:'foreign'})
    with pytest.raises(EvidenceError, match='archive preparation binding mismatch'):
        factory.archive(bad, cleanup)
    assert not (f.directory / 'default-raw').exists()
    assert f.archive.used == set()
    assert context.root.is_dir()
    assert factory._parent_fd is None and factory._root_fds == {} and not factory._archiving
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    assert (f.sibling / 'keep').read_bytes() == b'OTHER RUN'
    assert factory.archive(context, cleanup)['proven']
    print('ARCHIVE_CONTEXT_REFUSAL ' + json.dumps({'field':field,'rejected':True,'valid_original_after_refusal':True}))

def test_successful_archive_cannot_be_replayed(fixture):
    f = fixture
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    context = factory.prepare_default()
    cleanup = context.driver.cleanup()
    assert factory.archive(context, cleanup)['proven']
    manifest = f.directory / 'default-raw/ARCHIVE_MANIFEST.json'
    before = manifest.read_bytes()
    with pytest.raises((EvidenceError, OSError)) as error:
        factory.archive(context, cleanup)
    assert manifest.read_bytes() == before
    assert factory._parent_fd is None and factory._root_fds == {} and not factory._archiving
    assert f.archive.used == {'default'}
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    print('ARCHIVE_REPLAY_REFUSED ' + json.dumps({'error':str(error.value),'manifest_unchanged':True}))
