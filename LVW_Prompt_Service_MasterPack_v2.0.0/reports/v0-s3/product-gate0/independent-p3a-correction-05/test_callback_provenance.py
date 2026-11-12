"""Finite returned-context provenance checks; no native child execution."""
import json
import pytest
from LVW_V0_RuntimePatch.tests.test_s3_installed_runtime import fixture
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory
from tools.v0_s2_stage_runtime import TOOL_KEYS
from tools.v0_s2_checkpoint_oracles import EvidenceError

@pytest.mark.parametrize('callback', ['verify_bindings','authorize_launch'])
def test_returned_callback_cannot_adopt_other_prepared_label(fixture, callback):
    f=fixture
    observed=[]
    kwargs=dict(f.kwargs)
    kwargs['guard_critical']=lambda: {'complete_rehash':False,'manifest_sha256':'e'*64,
                                      'critical_files':[key.upper() for key in TOOL_KEYS]}
    def authority(*args):
        observed.append({'action':args[0],'pinned_labels':list(factory._root_fds)})
    kwargs['authorize']=authority
    factory=InstalledPackageRuntimeFactory(**kwargs)
    default=factory.prepare_default()
    original_root=default.root
    warm=factory.prepare_warm()
    # Only the public returned context field changes: both leases remain real,
    # and neither private identity records nor the inherited closures are edited.
    default.root=warm.root
    before=len(observed)
    error=None; result=None
    try:
        if callback=='verify_bindings':result=default.verify_bindings(default.browser_config,'cross-label')
        else:result=default.authorize_launch(default.browser_config)
    except (EvidenceError,OSError) as caught:
        error=caught
    print('RETURNED_CONTEXT_PROVENANCE '+json.dumps({'callback':callback,
        'context_root':str(default.root),'captured_original_root':str(original_root),
        'result':result,'error':None if error is None else str(error),
        'authority_after_swap':observed[before:],'archive_used':sorted(f.archive.used),
        'closed':factory._parent_fd is None and factory._root_fds=={}},sort_keys=True))
    assert factory._parent_fd is None and factory._root_fds=={} and not factory._archiving
    assert f.archive.used==set()
    assert original_root.is_dir() and warm.root.is_dir()
    assert f.sentinel.read_bytes()==b'UNRELATED ORIGINAL'
    assert (f.sibling/'keep').read_bytes()==b'OTHER RUN'
    assert error is not None, 'callback adopted warm identity while inherited closure verified default root'
