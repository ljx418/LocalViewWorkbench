"""Trusted finite guard selftest launcher, never a product checkpoint."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

plan_path = Path(sys.argv[1])
plan = json.loads(plan_path.read_text())
for name, digest in plan['pins'].items():
    if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
        raise RuntimeError('SELFTEST_PIN_DRIFT:' + name)
parent = Path(plan['fresh_parent'])
parent.mkdir(exist_ok=False)
root = parent / 'run'
root.mkdir()
outside = parent / 'outside-canary.txt'
canary = b'LVW-owned-canary-no-private-content\n'
outside.write_bytes(canary)
os.symlink(outside, root / 'escape')
os.link(outside, root / 'hardlink')
environment = os.environ.copy()
environment.update({'PYTHONDONTWRITEBYTECODE': '1', 'LVW_GUARD_CANARY_ROOT': str(root),
                    'LVW_GUARD_CANARY_OUTSIDE': str(outside)})
started = time.monotonic()
result = {'kind': 'TRUSTED_GUARD_SELFTEST_NOT_PRODUCT_ACCEPTANCE',
          'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
          'candidate_imported': False, 'product_runtime_executed': False,
          'passed': False}
try:
    with (root / 'stdout.log').open('wb') as stdout, (root / 'stderr.log').open('wb') as stderr:
        process = subprocess.run(plan['argv'], cwd=plan['cwd'], env=environment,
                                 stdout=stdout, stderr=stderr, timeout=plan['max_seconds'])
    guard = json.loads((root / 'guard.json').read_text())
    payload = json.loads((root / 'canary-result.json').read_text())
    result.update({'exit_code': process.returncode, 'outside_unchanged': outside.read_bytes() == canary,
                   'runtime_denial_count': len(guard['runtime_denials']),
                   'old_guard_denial_count': len(guard['selftest_denials']),
                   'check_count': len(payload['checks']),
                   'canary_sha256': hashlib.sha256(canary).hexdigest()})
    assert process.returncode == 0
    assert result['outside_unchanged'] and result['runtime_denial_count'] == 9
    assert result['old_guard_denial_count'] == 8
    assert result['check_count'] == 10 and all(c['passed'] for c in payload['checks'])
    assert guard['clean_runtime_denial_ledger'] is False  # expected only in this negative selftest
    assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest() == h for n, h in plan['pins'].items())
    result['passed'] = True
finally:
    # Only these three trusted setup canaries, created above, are removed.
    for path in [root / 'escape', root / 'hardlink', outside]:
        path.unlink()
    owned = root / 'owned'
    if owned.is_dir() and not list(owned.iterdir()):
        owned.rmdir()
    result['setup_canaries_removed'] = not any(p.exists() or p.is_symlink() for p in
                                              [root / 'escape', root / 'hardlink', outside])
    result['wall_seconds'] = time.monotonic() - started
    (root / 'outer-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
