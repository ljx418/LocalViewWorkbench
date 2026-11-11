"""Read-only Git and SHA binding recomputation; writes only this review's raw/."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

REVIEW = Path(__file__).resolve().parent
ROOT = REVIEW.parents[3]
PREFIX = ROOT.name + '/'
CANDIDATE = '5497bd1860ae895f394ece23a1ddb5e0b22fad92'
CONTRACT = 'a3361b5f6e43b6a3f8b0f57fd2faa5fc7ffe4822'

def git(name, args, save=True):
    command = ['git', *args]
    p = subprocess.run(command, cwd=ROOT.parent, capture_output=True)
    if save:
        (REVIEW/'raw'/f'{name}.command.json').write_text(json.dumps({'argv': command, 'cwd': str(ROOT.parent)}) + '\n')
        (REVIEW/'raw'/f'{name}.stdout.log').write_bytes(p.stdout)
        (REVIEW/'raw'/f'{name}.stderr.log').write_bytes(p.stderr)
        (REVIEW/'raw'/f'{name}.exit.log').write_text(str(p.returncode) + '\n')
    assert p.returncode == 0, (name, p.stderr)
    return p.stdout

def blob(commit, path):
    # Do not persist source/fixture snapshots; only derived hashes/results.
    return git('blob', ['show', commit + ':' + PREFIX + path], save=False)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

implementation = ROOT/'reports/v0-s3/product-gate0/implementation-p3a-correction-01'
receipt = json.loads((implementation/'receipt.json').read_text())
sources = []
for name, expected in receipt['source_sha256'].items():
    raw = (ROOT/name).read_bytes()
    sources.append({'path': name, 'expected': expected, 'actual': sha(raw),
                    'candidate_blob_sha256': sha(blob(CANDIDATE, name))})
evidence = []
for directory in (implementation, ROOT/'reports/v0-s3/product-gate0/independent-p3a'):
    for line in (directory/'SHA256SUMS').read_text().splitlines():
        expected, name = line.split(None, 1)
        path = directory/name.strip()
        evidence.append({'path': str(path.relative_to(ROOT)), 'expected': expected,
                         'actual': sha(path.read_bytes())})
changed = git('candidate-stat', ['diff', '--stat', CONTRACT, CANDIDATE])
git('candidate-worktree-diff', ['diff', CANDIDATE, '--', *[PREFIX+n for n in receipt['source_sha256']]])
unchanged = ['tools/v0_s2_stage_runtime.py', 'tools/test_v0_incremental_package.py',
             'LVW_V0_RuntimePatch/tests/test_s2_stage_runtime.py',
             'LVW_V0_RuntimePatch/tests/test_s2_browser_component.py',
             'reports/v0-s3/product-gate0/independent-p3a',
             'reports/v0-s3/product-gate0/implementation-p3a',
             'reports/v0-s3/product-gate0/p3-installed-runtime.contract.md',
             'reports/v0-s3/product-gate0/p3a-correction-01.contract.md']
git('immutable-boundaries', ['diff', CONTRACT, 'HEAD', '--', *[PREFIX+n for n in unchanged]])
git('status', ['status', '--short'])
name = 'tools/v0_incremental_package.py'
old_tree = ast.parse(blob(CONTRACT, name))
new_tree = ast.parse((ROOT/name).read_bytes())
old = {n.name: n for n in old_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
new = {n.name: n for n in new_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
modified = [n for n in old if ast.dump(old[n]) != ast.dump(new[n])]
default_install_equal = ([ast.dump(n) for n in old['command_install'].body]
                         == [ast.dump(n) for n in new['command_install'].body[2:]])
coord_raw = blob('f2ba889', 'plans/execution-control.json')
coord = json.loads(coord_raw)
(REVIEW/'raw/coordinate-extract.json').write_text(json.dumps({k: coord[k] for k in
    ('coordinate', 'development_outline', 'last_passed_gate', 'current_blocking_gate')}, indent=2, ensure_ascii=False) + '\n')
summaries = []
for p in sorted((implementation/'raw').glob('*.stdout.log')):
    if p.name.split('-')[0] in ('targeted', 'regression', 'owner', 'probes'):
        summaries.append({'run': p.name, 'last_line': p.read_text().splitlines()[-1],
                          'exit': int(p.with_name(p.name.replace('.stdout.log', '.exit.log')).read_text())})
result = {'sources': sources, 'checksums': evidence,
          'all_match': all(x['expected'] == x['actual'] for x in sources+evidence)
                       and all(x['actual'] == x['candidate_blob_sha256'] for x in sources),
          'preexisting_package_functions_modified': modified,
          'default_command_install_after_opt_in_prologue_ast_identical': default_install_equal,
          'coordinate_sha256': sha(coord_raw), 'historical_raw_summaries': summaries}
(REVIEW/'raw/binding-recomputation.json').write_text(json.dumps(result, indent=2) + '\n')
assert result['all_match'] and default_install_equal
assert modified == ['_validate_archive', 'command_install']
print(json.dumps({'source_blobs': len(sources), 'checksum_entries': len(evidence), 'all_match': result['all_match'],
                  'changed_existing_package_functions': modified, 'default_install_unchanged': default_install_equal,
                  'coordinate': coord['coordinate'], 'historical_runs': summaries}, indent=2))
