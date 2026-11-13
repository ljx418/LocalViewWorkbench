"""The identity of the candidate of this correction.

The candidate is the base commit plus the changed sources of this
correction.  The identity of the candidate is the digest of the digests:
every changed source is hashed, and the canonical document of those
hashes is hashed again.  The frozen sources that this correction did not
touch are listed with their digests as well, so that the independent
review can see that they are unchanged.
"""
import hashlib
import json
import subprocess
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
REPORT = Path(__file__).resolve().parent
BASE = '7c27a11111ede5bb2eb449211f5450270d884ee3'

CHANGED = (
    'tools/v0_s3_controller_io.py',
    'tools/v0_s3_production_controller.py',
    'tools/v0_s3_quality_worker.py',
    'tools/v0_s3_supervisor.py',
    'tools/test_v0_s3_production_composition.py',
    'tools/test_v0_s3_supervisor.py',
)

FROZEN = (
    'tools/v0_s3_quality_phase.py',
    'tools/v0_s3_coordinator.py',
    'tools/v0_s3_runtime_binding.py',
    'tools/v0_s3_stage_runtime.py',
    'tools/v0_s3_budget_authority.py',
    'tools/local_program_authority.py',
    'tools/v0_s2_runtime.py',
)


def digest_of(relative):
    path = PACK_ROOT / relative
    raw = path.read_bytes()
    return {'path': relative, 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def git(*arguments):
    process = subprocess.run(['git', '-C', str(PACK_ROOT)] + list(arguments),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return process.stdout.decode('utf-8', 'replace').strip()


def main():
    changed = [digest_of(relative) for relative in CHANGED]
    frozen = [digest_of(relative) for relative in FROZEN]
    identity = hashlib.sha256(json.dumps(
        {'base': BASE, 'changed': changed}, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()
    document = {
        'kind': 'lvw.s3-production-composition-correction-candidate/1',
        'base_candidate_sha': BASE,
        'candidate_identity_sha256': identity,
        'candidate_identity_is': ('the digest of the canonical document of the '
                                   'digests of the changed sources over the base commit'),
        'changed_sources': changed,
        'frozen_sources': frozen,
        'git_head': git('rev-parse', 'HEAD'),
        'git_branch': git('rev-parse', '--abbrev-ref', 'HEAD'),
        'git_status_porcelain': git('status', '--porcelain'),
        'git_diff_stat': git('diff', '--stat'),
        'committed_by_this_run': False,
        'commit_is_the_decision_of_the_root': True,
        'stage_pass_claim': False,
        'product_gate0': False,
    }
    (REPORT / 'candidate.json').write_text(json.dumps(document, indent=2), encoding='utf-8')
    print('candidate identity', identity)


if __name__ == '__main__':
    main()
