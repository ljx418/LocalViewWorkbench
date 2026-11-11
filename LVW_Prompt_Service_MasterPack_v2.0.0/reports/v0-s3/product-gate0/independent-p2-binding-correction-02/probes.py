"""Offline independent probes: original candidate remains unmodified."""
import errno
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import pytest
from tools import v0_s3_runtime_binding as h
from tools import test_v0_s3_runtime_binding as tests

blocked = []
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        p = os.fsdecode(args[0])
        if p.startswith('/mnt/') or p.lower().startswith('c:'):
            blocked.append(p)
            raise RuntimeError('independent outer guard: forbidden host open')
sys.addaudithook(audit)

def guard():
    # Invoke exactly the candidate fixture generator, including copied authority.
    with pytest.MonkeyPatch.context() as mp:
        gen = tests.factory_pair.__wrapped__(mp)
        pair = next(gen)
        normal, helper, *_ = pair
        try:
            try:
                Path(h.FIXED['wsl']).open('rb')
            except AssertionError as e:
                assert str(e) == 'offline test accessed host path'
            else:
                raise AssertionError('fixture host guard did not stop open')
            assert not blocked, 'outer guard reached: fixture guard failed'
            print(json.dumps({'fixture_guard': 'PASS_before_OS_open', 'copied_authority': 'factory completed with synthetic WSL digest', 'roots': [str(normal), str(helper)]}))
        finally:
            try: next(gen)
            except StopIteration: pass
        assert not normal.exists() and not helper.exists()
    print(json.dumps({'fixture_cleanup': True, 'outer_guard_events': blocked}))

def observer():
    # One bounded deterministic exception/scheduling matrix, no historical PIDs.
    results = {}
    with tempfile.TemporaryDirectory(prefix='lvw-s3-p2b-review-observer-', dir='/tmp') as tmp:
        root = Path(tmp); (root/'.s3-synthetic-fixture').touch()
        directory = root/'.s3-owned-requests'; directory.mkdir()
        rid = '00000000-0000-0000-0000-000000000001'
        journal = directory/(rid+'.json')
        value = dict(request_id=rid, pid=os.getpid(), birth={'linux_start_ticks': 1}, binding_sha256='b', state='ENTERED')
        journal.write_text(json.dumps(value))
        for exc in (FileNotFoundError, ProcessLookupError, PermissionError):
            def birth(pid):
                assert pid == os.getpid()
                raise exc({FileNotFoundError: errno.ENOENT, ProcessLookupError: errno.ESRCH, PermissionError: errno.EACCES}[exc], 'injected proc disappearance/access failure')
            with patch.object(h, 'protocol', return_value=SimpleNamespace(process_birth=birth)):
                o=h.Observer(root,'b');o.stop.set();o.thread.start();r=o.finish()
            results[exc.__name__]=r
            assert r['two_absences'] == (exc is FileNotFoundError)
            assert bool(r['error']) == (exc is not FileNotFoundError)
        # Reused PID with different start ticks is same-birth absence, not a live owner.
        value['state']='FAULT_HELPER_RETURNED';journal.write_text(json.dumps(value))
        with patch.object(h,'protocol',return_value=SimpleNamespace(process_birth=lambda pid:{'linux_start_ticks':2})):
            o=h.Observer(root,'b');o.stop.set();o.thread.start();r=o.finish()
        results['first_sample_after_return_pid_reused']=r
        assert r['two_absences'] and not r['entered'] and r['error'] is None
        # Missing first ENTERED alone cannot explain historical two_absences=False.
        # Inject malformed journal to verify failclosed, not a success or kill.
        journal.write_text('{')
        o=h.Observer(root,'b');o.stop.set();o.thread.start();r=o.finish()
        results['malformed_journal']=r
        assert r['error'].startswith('JSONDecodeError') and not r['two_absences']
    print(json.dumps({'observer_matrix':results,'root_removed':not root.exists(),'historical_root_cause':'UNPROVEN; historical failing observation was not printed'},indent=2))

if __name__ == '__main__':
    {'guard': guard, 'observer': observer}[sys.argv[1]]()
