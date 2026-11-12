"""Reachable public context mismatch and archive reentry, with original closures."""
import json
import pytest
from LVW_V0_RuntimePatch.tests.test_s3_installed_runtime import fixture
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory
from tools.v0_s2_stage_runtime import TOOL_KEYS
from tools.v0_s2_checkpoint_oracles import EvidenceError

@pytest.mark.parametrize('fault',['public-root-mismatch','archive-reentry'])
def test_delayed_callback_refuses_mismatch_or_nested_archive(fixture, fault):
    f=fixture;actions=[]
    kwargs=dict(f.kwargs)
    def authority(*args):
        actions.append(args)
        if args[0]=='verify_browser_runtime_bindings' and fault=='archive-reentry':
            factory.archive(context, {})
    kwargs['authorize']=authority
    kwargs['guard_critical']=lambda: {'complete_rehash':False,'manifest_sha256':'e'*64,
                                      'critical_files':[key.upper() for key in TOOL_KEYS]}
    factory=InstalledPackageRuntimeFactory(**kwargs)
    context=factory.prepare_default();original=context.root
    before=len(actions)
    if fault=='public-root-mismatch': context.root=f.sibling
    expected='archive original preparation identity unavailable' if fault=='public-root-mismatch' else 'archive lifecycle reentry'
    with pytest.raises(EvidenceError,match=expected) as error:
        context.verify_bindings(context.browser_config,'independent-boundary')
    assert factory._parent_fd is None and factory._root_fds=={} and not factory._archiving
    assert f.archive.used==set() and original.is_dir()
    assert not (f.directory/'default-raw').exists()
    assert f.sentinel.read_bytes()==b'UNRELATED ORIGINAL' and (f.sibling/'keep').read_bytes()==b'OTHER RUN'
    assert len(actions)-before==(0 if fault=='public-root-mismatch' else 1)
    context.root=original
    assert factory.archive(context,context.driver.cleanup())['proven']
    print('REACHABLE_CALLBACK_BOUNDARY '+json.dumps({'fault':fault,'error':str(error.value),
          'subsequent_real_archive_proven':True,'closed':factory._parent_fd is None and factory._root_fds=={}}))
