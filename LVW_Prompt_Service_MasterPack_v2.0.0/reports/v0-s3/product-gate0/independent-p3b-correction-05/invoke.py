"""Outer process capture; never imports product/test modules."""
import json, subprocess, sys
from pathlib import Path
out = Path(__file__).resolve().parent
pack = out.parents[3]
runner = out.parent / 'implementation-p3b-correction-05/run_guarded_checks.py'
label, mode, *script = sys.argv[1:]
command = [sys.executable, '-B', str(runner), '--mode', mode, '--label', label, '--outdir', str(out)]
if script:
    command += ['--script', str(out / script[0])]
with (out / (label + '.runner.stdout.log')).open('wb') as stdout, (out / (label + '.runner.stderr.log')).open('wb') as stderr:
    result = subprocess.run(command, cwd=pack, stdout=stdout, stderr=stderr)
(out / (label + '.outer.json')).write_text(json.dumps({'command': command, 'cwd': str(pack), 'exit_code': result.returncode}, indent=2) + '\n')
print(label, 'outer exit', result.returncode)
sys.exit(result.returncode)
