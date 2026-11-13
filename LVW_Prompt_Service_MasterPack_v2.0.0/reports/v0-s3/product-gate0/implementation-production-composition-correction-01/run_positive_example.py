"""The positive example of this correction, with its real artefacts.

The example drives the *formal* command line entry of the controller with
the offline seam injected at the Python construction site.  The run root
of the example is a real directory of this report, so every artefact of
the run - the sealed contexts, the projection, the canonical receipt, the
parent manifest, the summary and the receipt of the run - stays where it
was written and can be recomputed by the independent review.

The example creates no operating system child process: the worker runs in
a thread of this process and speaks over a real pipe.
"""
import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from tools import test_v0_s3_production_composition as data  # noqa: E402
from tools import v0_s3_production_controller as controller  # noqa: E402

REPORT = Path(__file__).resolve().parent
RUN_ROOT = REPORT / 'run-root'


def main():
    if RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True)
    composition = data._build_composition(RUN_ROOT, name='run')
    seam = controller.OfflineCompositionSeam(
        driver_factory=lambda ctx: data._helpers().SyntheticDriver(
            Path(ctx.document['root']), None),
        context_sha256=composition['worker_context_sha256'])
    original = controller.ProductionController

    class Injected(original):
        def __init__(self, context):
            super().__init__(context, seam=seam)

    output = io.StringIO()
    errors = io.StringIO()
    controller.ProductionController = Injected
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = controller.main(['--context', str(composition['controller_context_path']),
                                    '--context-sha256',
                                    data._digest_of(composition['controller_context_path'])])
    finally:
        controller.ProductionController = original
    receipt = json.loads(output.getvalue()) if output.getvalue().strip() else None
    (REPORT / 'positive-example.receipt.json').write_text(
        json.dumps({'exit': code, 'receipt': receipt, 'stderr': errors.getvalue(),
                    'seam_spawns': seam.spawns,
                    'run_root': str(RUN_ROOT),
                    'synthetic_identity_only': True,
                    'product_pass_claimed': False,
                    'stage_pass_claim': False,
                    'product_gate0': False}, indent=2), encoding='utf-8')
    print('positive example exit', code, 'state', receipt['state'] if receipt else None)
    return 0 if code == controller.EXIT_PERSISTED else 1


if __name__ == '__main__':
    raise SystemExit(main())
