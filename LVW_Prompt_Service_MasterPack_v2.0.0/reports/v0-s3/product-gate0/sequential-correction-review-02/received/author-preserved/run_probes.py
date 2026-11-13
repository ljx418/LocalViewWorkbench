#!/usr/bin/env python3
"""The outer runner of the round two failure matrix.

It runs the probe **once** and keeps its raw streams, its true outer exit
code and the digests of both streams.  The probe itself installs the
pre-import boundary before it imports the candidate, so the candidate never
starts a real child process and never opens a socket.

The exit code of the probe is zero when every converted oracle held: the
semantics are the opposite of the first round, where a zero exit meant
that a defect had been reproduced.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROBE = OUT / 'sequential_correction_02_probes.py'


def main():
    command = [sys.executable, '-B', str(PROBE)]
    stdout_path = OUT / 'sequential-correction-02-negative.stdout.log'
    stderr_path = OUT / 'sequential-correction-02-negative.stderr.log'
    environment = dict(os.environ)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    with stdout_path.open('wb') as out, stderr_path.open('wb') as err:
        result = subprocess.run(command, cwd=str(OUT), stdout=out, stderr=err,
                                env=environment)
    record = {
        'kind': 'LVW_S3_SEQUENTIAL_CORRECTION_02_MATRIX_OUTER/1',
        'command': command,
        'working_directory': str(OUT),
        'outer_returncode': result.returncode,
        'outer_returncode_semantics': (
            'the true outer exit code of the probe; zero means that every '
            'converted oracle held, it is not a statement about the product'),
        'stdout_file': str(stdout_path),
        'stderr_file': str(stderr_path),
        'stdout_sha256': hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
        'stderr_sha256': hashlib.sha256(stderr_path.read_bytes()).hexdigest(),
        'stdout_bytes': stdout_path.stat().st_size,
        'stderr_bytes': stderr_path.stat().st_size,
        'probe_sha256': hashlib.sha256(PROBE.read_bytes()).hexdigest(),
        'boundary_sha256': hashlib.sha256(
            (OUT / 'outer_boundary.py').read_bytes()).hexdigest(),
        'real_execution_performed': False,
        'root_counter_touched': False,
        'stage_pass_claim': False,
        'product_gate0': False,
    }
    (OUT / 'sequential-correction-02-negative.outer.json').write_text(
        json.dumps(record, indent=2, sort_keys=True) + '\n')
    sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
