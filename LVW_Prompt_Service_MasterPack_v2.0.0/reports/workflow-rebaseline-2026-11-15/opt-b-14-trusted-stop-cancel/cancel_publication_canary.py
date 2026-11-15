"""Frozen control-only regression: real child, real signals before publication.

No candidate module is imported. This adapter retains the real Popen solely for
an independent oracle/fallback; fallback cleanup can never turn failure into PASS.
"""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

source, request_path, oracle_path = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location('lvw_trusted_stop', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
held = []
fallback_used = False
controller_exit = None
errors = []


def observe_real_creation(*args, **kwargs):
    proc = subprocess.Popen(*args, **kwargs)
    held.append(proc)
    # The real constructor returned here, but the controller's local assignment
    # has not run. Ordinary signals must be deferred rather than lose this owner.
    os.kill(os.getpid(), signal.SIGTERM)
    os.kill(os.getpid(), signal.SIGINT)
    return proc


try:
    controller_exit = module.main(request_path, popen_factory=observe_real_creation)
except BaseException as error:
    errors.append(repr(error))
finally:
    for proc in held:
        if proc.poll() is None:
            fallback_used = True
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    proc.send_signal(sig)
                    proc.wait(timeout=0.3)
                    break
                except subprocess.TimeoutExpired:
                    continue
                except BaseException as error:
                    errors.append(repr(error))
                    break
request = json.loads(request_path.read_text())
receipt_path = Path(request['output_dir']) / 'receipt.json'
receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
facts = {'kind': 'REAL_PREPUBLICATION_CANCEL_REGRESSION',
         'actual_created_pids': [proc.pid for proc in held],
         'controller_exit': controller_exit, 'fallback_used': fallback_used,
         'errors': errors, 'receipt': receipt,
         'passed': (len(held) == 1 and not fallback_used and not errors
                    and controller_exit == 1 and receipt.get('status') == 'CANCELLED'
                    and receipt.get('pid') == held[0].pid
                    and receipt.get('cancel_signals') == [signal.SIGTERM, signal.SIGINT]
                    and receipt.get('reaped') is True
                    and receipt.get('returncode') == held[0].returncode
                    and held[0].returncode in (-signal.SIGTERM, -signal.SIGKILL))}
with oracle_path.open('x', encoding='utf-8') as stream:
    json.dump(facts, stream, indent=2)
    stream.write('\n')
sys.exit(0 if facts['passed'] else 1)
