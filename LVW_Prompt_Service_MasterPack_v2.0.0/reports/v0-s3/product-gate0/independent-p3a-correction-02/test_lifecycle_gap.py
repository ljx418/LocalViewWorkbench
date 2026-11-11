"""Narrow early-lifecycle assertion using real inherited preparation."""
import json
import os
import pytest
from LVW_V0_RuntimePatch.tests.test_s3_installed_runtime import fixture
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory
from tools.v0_s2_checkpoint_oracles import EvidenceError

def test_parent_replaced_during_complete_verification_has_zero_foreign_writes(fixture, monkeypatch):
    f = fixture
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    original = factory.verify_complete
    detached = f.root / 'review-original-evidence-parent'
    def change_namespace_during_verification():
        proof = original()
        f.directory.rename(detached)
        f.directory.mkdir()
        (f.directory / 'foreign-sentinel').write_bytes(b'FOREIGN PARENT')
        return proof
    monkeypatch.setattr(factory, 'verify_complete', change_namespace_during_verification)
    opened = []
    original_open = os.open
    def track(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        opened.append(fd)
        return fd
    monkeypatch.setattr(os, 'open', track)
    with pytest.raises(EvidenceError) as error:
        factory.prepare_default()
    assert str(error.value) == 'preparation parent identity drift'
    assert not {'comfy-start', 'ollama-start'} & set(f.helper.events)
    assert (detached / 'other-run/keep').read_bytes() == b'OTHER RUN'
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    assert (f.directory / 'foreign-sentinel').read_bytes() == b'FOREIGN PARENT'
    disk = json.loads((detached / 'default-preparation-failure.json').read_text())
    assert disk['error'] == str(error.value)
    assert disk['root_retained'] is None
    assert factory.preparation_failures['default']['persistence']['status'] == 'PERSISTED'
    assert factory._parent_fd is None and factory._root_fds == {}
    for fd in set(opened):
        with pytest.raises(OSError): os.fstat(fd)
    unexpected = sorted(p.name for p in f.directory.iterdir() if p.name != 'foreign-sentinel')
    print('INDEPENDENT_EARLY_LIFECYCLE ' + json.dumps({
        'replacement_entries': unexpected,
        'replacement_entries_are_empty_directories': all((f.directory / n).is_dir() and not list((f.directory / n).iterdir()) for n in unexpected),
        'services_started': 0, 'original_failure_record': disk,
        'captured_descriptors_closed': len(opened),
        'archive_leases': list(f.archive.leases)}, sort_keys=True))
    assert unexpected == [], 'temporary root was created in replacement parent before identity refusal'
