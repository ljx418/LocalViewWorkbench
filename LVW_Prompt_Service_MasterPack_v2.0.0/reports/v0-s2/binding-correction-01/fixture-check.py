"""Owned ordinary NTFS files only; no installed dependency, model or media probe."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types

from tools.v0_s2_execution_bindings import ExecutionBindings, Tree

root = Path.cwd()
parent = root.parent.parent/'.lvw-runtime/lvw-prompt-service'
parent.mkdir(parents=True, exist_ok=True)
module = types.ModuleType('_lvw_offline_previous_bindings')
sys.modules[module.__name__] = module
baseline = 'e75e722c060d2eb50026670ebceb4922da7743a0'
old = subprocess.check_output(['git', 'show', baseline+':LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s2_execution_bindings.py'])
exec(compile(old, 'offline_previous_bindings.py', 'exec'), module.__dict__)
with tempfile.TemporaryDirectory(prefix='offline-binding-fixture-', dir=parent) as temporary:
    fixture = Path(temporary).resolve(); code = fixture/'code'; nested = code/'one/two/three'
    nested.mkdir(parents=True); tool = fixture/'tool'; tool.write_bytes(b'owned fixture, not executable')
    for index in range(100): (nested/str(index)).write_bytes(('owned ordinary fixture '+str(index)).encode())
    results = []
    for name, cls, tree in [('previous', module.ExecutionBindings, module.Tree), ('corrected', ExecutionBindings, Tree)]:
        started = time.monotonic()
        value = cls(trees={'CODE': tree(code)}, files={'TOOL': tool}, authorize=lambda *args: None).capture()
        results.append({'implementation': name, 'seconds': time.monotonic()-started,
            'files': len(value['files']), 'bytes': value['bytes_hashed'], 'manifest_sha256': value['manifest_sha256']})
    assert results[0]['manifest_sha256'] == results[1]['manifest_sha256']
result = {'kind': 'OFFLINE_OWNED_NTFS_FIXTURE_NOT_INSTALLED_RUNTIME_ACCEPTANCE',
    'baseline_candidate': baseline, 'baseline_source_sha256': hashlib.sha256(old).hexdigest(),
    'corrected_source_sha256': hashlib.sha256((root/'tools/v0_s2_execution_bindings.py').read_bytes()).hexdigest(),
    'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'results': results, 'cleanup_proven': not fixture.exists(), 'model_calls': 0, 'service_starts': 0, 'external_calls': 0,
    'stage_pass_claim': False, 'same_complete_manifest': True}
print(json.dumps(result, sort_keys=True))
assert result['cleanup_proven']
