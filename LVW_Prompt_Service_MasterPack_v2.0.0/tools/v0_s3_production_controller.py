"""The formal S3-P4 production composition controller.

This module is the *controller* of one production composition: it closes the
arguments of the run, it seals the sixteen row plan, it starts the frozen
production command of the quality worker, it supervises that worker with the
accepted parent supervisor, it reads the real originals of the bound root
itself, it adapts the real run facts into the fixed twelve key summary and it
persists that summary.

The controller owns no model, no service, no GPU and no ledger.  It reuses the
accepted owners:

* ``WorkerContext`` and ``run_worker`` of ``tools.v0_s3_quality_worker.py``;
* ``QualityPhase`` and the published receipt readers of
  ``tools.v0_s3_quality_phase.py``;
* ``ParentSupervisor``, ``SealedPlan`` and ``build_production_command`` of
  ``tools.v0_s3_supervisor.py``;
* ``ParentOriginalEvidence``, ``S3BudgetBindingProvider`` and
  ``aggregate_twelve_keys`` of ``tools.v0_s3_coordinator.py``.

Two boundaries are absolute.

* The *native* execution path is refused by default.  A real run needs an
  accepted admission record that binds the accepted budget authority, the
  native descendant custody, the GPU release, the installation and its
  rollback, the finite root sub authorization and the tool dependency
  closure.  None of them exists for this platform today, so the native path
  stops in ``PRECHECK`` with ``0`` spawn.  A boolean, a platform string or a
  self written capability document never replaces the accepted admission
  authority, and there is no ``--force`` switch.
* The *offline composition* is an explicit in-process seam.  It injects a
  synthetic driver, a synthetic spawner and a synthetic clock into the very
  same controller, worker, phase, protocol, parent reader, canonical
  receipt, manifest and summary path.  It creates no operating system child
  process: the worker runs in a thread and speaks over a real pipe.  The
  seam is a Python object; it is never serialised into a context document
  and it is never reachable from the command line, so it can never become a
  back door of a real execution.

Nothing in this module proves a product gate.  Every document that it writes
carries ``stage_pass_claim = False`` and ``product_gate0 = False``, and the
synthetic facts of the offline seam are never counted as a product pass.
"""
import hashlib
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from tools.v0_s3_coordinator import (  # noqa: E402 - the path is set above
    AGGREGATE_RECEIPT_KIND, ParentOriginalEvidence, S3BudgetBindingProvider,
    S3IntegrationError, aggregate_twelve_keys)
from tools.v0_s3_quality_phase import (  # noqa: E402 - the path is set above
    CANONICAL_RECEIPT_NAME, QualityContractError, QualityPhase,
    load_published_execution_receipt, load_source_plan, recompute_scores)
from tools.v0_s3_quality_worker import (  # noqa: E402 - the path is set above
    WorkerContext, WorkerError, main as worker_main)
from tools.v0_s3_supervisor import (  # noqa: E402 - the path is set above
    ParentSupervisor, SealedPlan, SupervisionError, build_production_command)

CONTROLLER_CONTEXT_SCHEMA = 'lvw.s3-production-controller-context/1'
CONTROLLER_RECEIPT_KIND = 'lvw.s3-production-controller-receipt/1'
NATIVE_ADMISSION_KIND = 'lvw.s3-native-admission/1'
SUMMARY_KIND = 'lvw.s3-production-summary/1'

# The single state machine of one composition.
STATE_PRECHECK = 'PRECHECK'
STATE_PLAN_SEALED = 'PLAN_SEALED'
STATE_WORKER_SUPERVISED = 'WORKER_SUPERVISED'
STATE_ORIGINALS_VERIFIED = 'ORIGINALS_VERIFIED'
STATE_RECEIPTS_BOUND = 'RECEIPTS_BOUND'
STATE_SUMMARY_PERSISTED = 'SUMMARY_PERSISTED'
STATE_REFUSED = 'REFUSED_BEFORE_START'
STATE_UNKNOWN = 'UNKNOWN_RETAINED'
STATE_ORDER = (STATE_PRECHECK, STATE_PLAN_SEALED, STATE_WORKER_SUPERVISED,
               STATE_ORIGINALS_VERIFIED, STATE_RECEIPTS_BOUND, STATE_SUMMARY_PERSISTED)

CONTROLLER_CONTEXT_KEYS = frozenset({
    'schema', 'run_id', 'candidate_sha', 'authorization_sha256', 'root',
    'worker_context', 'admission', 'quality_scores', 'independence'})
REFERENCE_KEYS = frozenset({'path', 'sha256'})

# The artefacts of this controller that are hashed into the receipt.
SOURCE_FILES = (
    'tools/v0_s3_production_controller.py',
    'tools/v0_s3_quality_worker.py',
    'tools/v0_s3_quality_phase.py',
    'tools/v0_s3_supervisor.py',
    'tools/v0_s3_coordinator.py',
)

# The exit codes of the command line entry.
EXIT_PERSISTED = 0
EXIT_REFUSED = 3
EXIT_UNKNOWN = 4
EXIT_INTERNAL = 5

# The receipts of the fixed twelve key summary that this controller can bind
# to a fact of *this* run, and the receipts whose truth belongs to the
# native or the product side and that therefore stay unproven here.
DERIVED_RECEIPTS = ('stage_binding', 'image_input', 'video_input', 'output_contract',
                    'no_overwrite', 'file_safety', 'resource_budget', 'quality_16_rows')
UNPROVEN_RECEIPTS = {
    'a06_isolation': 'REAL_A06_ISOLATION_NOT_PROVEN',
    'install': 'NO_INSTALLATION_RECEIPT',
    'rollback': 'NO_ROLLBACK_RECEIPT',
    'independent_score': 'NO_INDEPENDENT_SCORE_EVIDENCE',
    'webp_format': 'NO_WEBP_FORMAT_RECEIPT',
    'cleanup': 'PRODUCT_CLEANUP_NOT_PROVEN',
    'no_approval_gate': 'NO_APPROVAL_GATE_OWNER_RECEIPT',
    'cancel_release': 'SYNTHETIC_RELEASE_EVIDENCE_IS_NOT_A_PRODUCT_PROOF',
    'manual_export': 'NO_SEPARATE_MANUAL_EXPORT_RECEIPT',
}


class ControllerError(RuntimeError):
    """A refused controller step with a stable, machine readable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _read_bounded(path, limit=8 * 1024 * 1024):
    target = Path(path)
    try:
        raw = target.read_bytes()
    except OSError as error:
        raise ControllerError('CONTROLLER_FILE_UNREADABLE') from error
    if len(raw) > limit:
        raise ControllerError('CONTROLLER_FILE_TOO_LARGE')
    return raw


def _fd_snapshot():
    """The open descriptors of this process.

    The descriptor of the listing itself is excluded, so the difference of
    two snapshots names exactly the descriptors that a step leaked.
    """
    try:
        descriptor = os.open('/proc/self/fd', os.O_RDONLY)
    except OSError:  # pragma: no cover - a platform without procfs
        return None
    try:
        names = os.listdir(descriptor)
    except OSError:  # pragma: no cover - defensive
        return None
    finally:
        os.close(descriptor)
    return sorted(int(name) for name in names
                  if name.isdigit() and int(name) != descriptor)


# --------------------------------------------------------------------------
# the projection: the frozen parser of the phase is the only parser
# --------------------------------------------------------------------------
class _ProjectionHolder:
    """The minimal holder of the frozen projection parser.

    The parser of ``QualityPhase`` needs exactly one attribute of its
    instance.  The holder provides it, so the *same* function object that the
    phase itself uses validates the rows of the controller.  The frozen
    phase module is not modified and no second projection protocol is
    created.
    """

    __slots__ = ('projection_bytes',)

    def __init__(self, projection_bytes):
        self.projection_bytes = projection_bytes


def parse_projection_rows(projection_bytes):
    """The sixteen rows of the bound projection, parsed by the phase owner.

    The rows are the ones of the production projection: the ordinal, the
    asset, the media kind, the source digest, the source length and the
    input reference.  A projection that the phase would refuse is refused
    here as well, before a single row is sent.
    """
    if not isinstance(projection_bytes, (bytes, bytearray)):
        raise ControllerError('CONTROLLER_PROJECTION_NOT_BYTES')
    try:
        rows = QualityPhase._parse_projection(_ProjectionHolder(bytes(projection_bytes)))
    except QualityContractError as error:
        raise ControllerError('CONTROLLER_PROJECTION_REJECTED:' + str(error)) from error
    if not isinstance(rows, list) or len(rows) != 16:
        raise ControllerError('CONTROLLER_PROJECTION_ROW_COUNT_INVALID')
    return rows


# --------------------------------------------------------------------------
# the controller context
# --------------------------------------------------------------------------
class ControllerContext:
    """The closed context of one production composition.

    The context names the run, the candidate, the authorization, the run
    root, the sealed worker context, the sealed native admission record and
    the two optional sealed documents of the independent quality score.  It
    names no command, no module, no shell and no callback: the only command
    of a run is the frozen production command of the quality worker.
    """

    def __init__(self, document):
        if not isinstance(document, dict):
            raise ControllerError('CONTROLLER_CONTEXT_NOT_OBJECT')
        if set(document) != CONTROLLER_CONTEXT_KEYS:
            raise ControllerError('CONTROLLER_CONTEXT_KEY_SET_INVALID')
        if document['schema'] != CONTROLLER_CONTEXT_SCHEMA:
            raise ControllerError('CONTROLLER_CONTEXT_SCHEMA_INVALID')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', str(document['run_id'])):
            raise ControllerError('CONTROLLER_CONTEXT_RUN_ID_INVALID')
        if not re.fullmatch(r'[0-9a-f]{40}', str(document['candidate_sha'])):
            raise ControllerError('CONTROLLER_CONTEXT_CANDIDATE_INVALID')
        if not re.fullmatch(r'[0-9a-f]{64}', str(document['authorization_sha256'])):
            raise ControllerError('CONTROLLER_CONTEXT_AUTHORIZATION_INVALID')
        root = document['root']
        if not isinstance(root, str) or not root or not os.path.isabs(root):
            raise ControllerError('CONTROLLER_CONTEXT_ROOT_INVALID')
        for name in ('worker_context', 'admission'):
            reference = document[name]
            if not isinstance(reference, dict) or set(reference) != REFERENCE_KEYS:
                raise ControllerError('CONTROLLER_CONTEXT_REFERENCE_INVALID:' + name)
            if not isinstance(reference['path'], str) or not reference['path']:
                raise ControllerError('CONTROLLER_CONTEXT_REFERENCE_INVALID:' + name)
            if not re.fullmatch(r'[0-9a-f]{64}', str(reference['sha256'])):
                raise ControllerError('CONTROLLER_CONTEXT_REFERENCE_INVALID:' + name)
        for name in ('quality_scores', 'independence'):
            reference = document[name]
            if not isinstance(reference, dict) or set(reference) != REFERENCE_KEYS:
                raise ControllerError('CONTROLLER_CONTEXT_REFERENCE_INVALID:' + name)
            path = reference['path']
            digest = reference['sha256']
            if path is None and digest is None:
                continue
            if (not isinstance(path, str) or not path
                    or not re.fullmatch(r'[0-9a-f]{64}', str(digest))):
                raise ControllerError('CONTROLLER_CONTEXT_REFERENCE_INVALID:' + name)
        self.document = dict(document)
        self.run_id = document['run_id']
        self.candidate_sha = document['candidate_sha']
        self.authorization_sha256 = document['authorization_sha256']
        self.root = Path(root)

    @classmethod
    def load(cls, path, *, expected_sha256=None):
        raw = _read_bounded(path)
        if expected_sha256 is not None and sha256_bytes(raw) != expected_sha256:
            raise ControllerError('CONTROLLER_CONTEXT_SEAL_MISMATCH')
        try:
            document = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as error:
            raise ControllerError('CONTROLLER_CONTEXT_NOT_JSON') from error
        return cls(document)


# --------------------------------------------------------------------------
# the native admission
# --------------------------------------------------------------------------
ADMISSION_REFERENCE_KEYS = ('budget_binding', 'native_custody', 'gpu_release',
                            'install', 'rollback', 'grant', 'tool_closure')
ADMISSION_KEYS = frozenset({'kind', 'run_id', 'candidate_sha', 'authorization_sha256',
                             'model_digest', 'authority_root', 'ledger_path',
                             'admission_references'})


def _load_referenced(reference, *, label, reasons, mapping=True):
    """Read one referenced document and check its seal.

    ``mapping`` is false for the score documents of the quality owner: the
    accepted score entry accepts a list of score documents as well as a
    document that carries them under its ``scores`` key.
    """
    if not isinstance(reference, dict) or set(reference) != REFERENCE_KEYS:
        reasons.append(label + ':REFERENCE_INVALID')
        return None
    if not isinstance(reference['path'], str) or not reference['path'] \
            or not re.fullmatch(r'[0-9a-f]{64}', str(reference['sha256'])):
        reasons.append(label + ':REFERENCE_INVALID')
        return None
    try:
        raw = _read_bounded(reference['path'])
    except ControllerError:
        reasons.append(label + ':UNREADABLE')
        return None
    if sha256_bytes(raw) != reference['sha256']:
        reasons.append(label + ':SEAL_MISMATCH')
        return None
    try:
        document = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        reasons.append(label + ':NOT_JSON')
        return None
    if mapping and not isinstance(document, dict):
        reasons.append(label + ':NOT_OBJECT')
        return None
    return document


def _bound_receipt(document, context, *, label, reasons, required=None):
    """A receipt of the run has to carry the identity of this run."""
    for key in ('run_id', 'candidate_sha'):
        if document.get(key) != getattr(context, key):
            reasons.append(label + ':BINDING_MISMATCH')
            return False
    if required is None:
        return True
    for key, expected in required.items():
        if document.get(key) is not expected:
            reasons.append(label + ':PROOF_MISSING:' + key)
            return False
    return True


def verify_native_admission(context, document):
    """Verify the accepted admission record of a native execution.

    The admission is a *reference chain*, not a promise: every element of it
    is a sealed document that is read and verified here.  The budget binding
    is verified through the accepted loader, the accepted validator and the
    accepted identity checks of ``S3BudgetBindingProvider``, so a self
    written capability document can never replace the real authority of the
    original ledger.

    The report names every missing element.  An admission that is not
    complete is never repaired and never guessed: the native path stays
    blocked.
    """
    reasons = []
    report = {'kind': 'lvw.s3-native-admission-report/1',
              'run_id': context.run_id,
              'candidate_sha': context.candidate_sha,
              'authorization_sha256': context.authorization_sha256,
              'accepted': False,
              'reasons': reasons,
              'verified': [],
              'budget_authority': 'S3BudgetBindingProvider',
              'original_ledger_touched_by_this_controller': False,
              'debit_owner': 'original_ledger_authority',
              'stage_pass_claim': False,
              'product_gate0': False}
    if not isinstance(document, dict) or document.get('kind') != NATIVE_ADMISSION_KIND:
        reasons.append('ADMISSION_DOCUMENT_INVALID')
        report['primary_reason'] = reasons[0]
        return report
    if set(document) != ADMISSION_KEYS:
        reasons.append('ADMISSION_KEY_SET_INVALID')
        report['primary_reason'] = reasons[0]
        return report
    if document['run_id'] != context.run_id \
            or document['candidate_sha'] != context.candidate_sha \
            or document['authorization_sha256'] != context.authorization_sha256:
        reasons.append('ADMISSION_IDENTITY_MISMATCH')
        report['primary_reason'] = reasons[0]
        return report
    references = document['admission_references']
    if not isinstance(references, dict) or set(references) != set(ADMISSION_REFERENCE_KEYS):
        reasons.append('ADMISSION_REFERENCE_SET_INVALID')
        report['primary_reason'] = reasons[0]
        return report

    # ---- the accepted budget authority ---------------------------------
    binding_reference = references['budget_binding']
    binding_document = _load_referenced(binding_reference, label='budget_binding',
                                        reasons=reasons)
    if binding_document is not None:
        try:
            provider = S3BudgetBindingProvider(
                binding=binding_reference,
                run_id=context.run_id,
                candidate_sha=context.candidate_sha,
                authorization_sha256=context.authorization_sha256,
                model_digest=document['model_digest'],
                authority_root=document['authority_root'],
                ledger_path=document['ledger_path'])
            provider.sealed()
            report['verified'].append('budget_binding')
        except S3IntegrationError as error:
            reasons.append('budget_binding:REFUSED:' + error.reason)
        except Exception as error:  # noqa: BLE001 - the reason stays stable
            reasons.append('budget_binding:REFUSED:' + type(error).__name__)

    # ---- the native and product obligations ----------------------------
    obligations = (
        ('native_custody', ('descendant_handles_closed', 'native_services_stopped')),
        ('gpu_release', ('gpu_released',)),
        ('install', ('installed',)),
        ('rollback', ('rollback_verified',)),
        ('grant', ('grant_active',)),
    )
    for name, proofs in obligations:
        document_of = _load_referenced(references[name], label=name, reasons=reasons)
        if document_of is None:
            continue
        required = {proof: True for proof in proofs}
        required['status'] = 'PROVEN'
        if _bound_receipt(document_of, context, label=name, reasons=reasons,
                          required=required):
            report['verified'].append(name)

    # ---- the tool dependency closure -----------------------------------
    closure = _load_referenced(references['tool_closure'], label='tool_closure',
                               reasons=reasons)
    if closure is not None:
        files = closure.get('files')
        if not isinstance(files, list) or not files:
            reasons.append('tool_closure:FILES_MISSING')
        else:
            broken = False
            for entry in files:
                if not isinstance(entry, dict) or not isinstance(entry.get('path'), str) \
                        or not re.fullmatch(r'[0-9a-f]{64}', str(entry.get('sha256'))):
                    reasons.append('tool_closure:ENTRY_INVALID')
                    broken = True
                    break
                try:
                    raw = _read_bounded(entry['path'])
                except ControllerError:
                    reasons.append('tool_closure:FILE_UNREADABLE')
                    broken = True
                    break
                if sha256_bytes(raw) != entry['sha256']:
                    reasons.append('tool_closure:FILE_DRIFT')
                    broken = True
                    break
            if not broken:
                report['verified'].append('tool_closure')

    report['accepted'] = not reasons
    report['primary_reason'] = reasons[0] if reasons else None
    return report


# --------------------------------------------------------------------------
# the offline composition seam
# --------------------------------------------------------------------------
class _PipeStream:
    """The read end of a real pipe for the bounded reader of the parent."""

    def __init__(self, descriptor):
        self._descriptor = descriptor

    def fileno(self):
        return self._descriptor

    def close(self):
        descriptor = self._descriptor
        self._descriptor = -1
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:  # pragma: no cover - the close may race
                pass


class _FaultStream:
    """The explicit protocol fault of the synthetic worker.

    The proxy is the synthetic *misbehaviour* of a worker: it repeats one
    history announcement or it points the terminal reference out of the
    bound root.  The bytes that leave the worker are otherwise the bytes of
    the real protocol writer, and the parent reads them through its own
    bounded reader.

    Without a fault the stream is a transparent pass through: the bytes of
    the worker reach the parent unchanged.
    """

    STREAM_FAULTS = ('duplicate_history_start', 'bad_terminal_reference')

    def __init__(self, stream, fault):
        self.stream = stream
        self.fault = fault
        self.buffer = bytearray()
        self.sequence = 0
        self.duplicated = False

    def write(self, raw):
        self.buffer.extend(raw)
        while True:
            index = self.buffer.find(b'\n')
            if index < 0:
                return
            line = bytes(self.buffer[:index])
            del self.buffer[:index + 1]
            self._emit(line)

    def flush(self):
        self.stream.flush()

    def close(self):
        self.stream.close()

    def _emit(self, line):
        if self.fault not in self.STREAM_FAULTS:
            self.stream.write(line + b'\n')
            return
        try:
            message = json.loads(line.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            self.stream.write(line + b'\n')
            return
        event = message.get('event')
        if self.fault == 'duplicate_history_start':
            self.sequence = max(self.sequence, int(message.get('sequence', 0)))
            message['sequence'] = self.sequence
            self.sequence += 1
            if event == 'HISTORY_WAIT_STARTED' and not self.duplicated:
                self.duplicated = True
                self.stream.write(canonical_json(message).encode('utf-8') + b'\n')
                duplicate = dict(message)
                duplicate['sequence'] = self.sequence
                self.sequence += 1
                self.stream.write(canonical_json(duplicate).encode('utf-8') + b'\n')
                return
            self.stream.write(canonical_json(message).encode('utf-8') + b'\n')
            return
        if self.fault == 'bad_terminal_reference' and event == 'TERMINAL':
            payload = dict(message.get('payload') or {})
            reference = dict(payload.get('canonical_receipt') or {})
            reference['reference'] = '../outside/qd-receipt.json'
            payload['canonical_receipt'] = reference
            message['payload'] = payload
        self.stream.write(canonical_json(message).encode('utf-8') + b'\n')


class _InProcessWorker:
    """The in-process stand in of the supervised worker.

    The worker runs in a thread of this process and speaks over real pipes.
    No operating system child process is created: the parent reads the very
    same protocol bytes from a real descriptor and the very same
    ``ParentSupervisor`` code path is used.

    The handle has no process identity of its own: ``pid`` is ``None`` and
    the birth identity of the parent therefore stays unknown, because no
    child was ever created.
    """

    def __init__(self, command, *, driver_factory, context_sha256, fault):
        self.command = list(command)
        self.pid = None
        self._exit_code = None
        self._finished = threading.Event()
        self._fault = fault
        out_read, out_write = os.pipe()
        err_read, err_write = os.pipe()
        in_read, in_write = os.pipe()
        self.stdout = _PipeStream(out_read)
        self.stderr = _PipeStream(err_read)
        self.stdin = _PipeStream(in_read)
        self._stdout_raw = os.fdopen(out_write, 'wb', 0)
        self._stdout_write = (_FaultStream(self._stdout_raw, fault)
                              if fault in _FaultStream.STREAM_FAULTS else self._stdout_raw)
        self._stderr_write = os.fdopen(err_write, 'wb', 0)
        self._stdin_write = os.fdopen(in_write, 'wb', 0)
        self._driver_factory = driver_factory
        self._context_sha256 = context_sha256
        self._thread = threading.Thread(target=self._run, name='s3-composition-worker',
                                        daemon=True)
        self._thread.start()

    # -- the process like surface of the parent --------------------------
    def poll(self):
        if self._finished.is_set():
            return self._exit_code
        return None

    def terminate(self):
        return None

    def kill(self):
        return None

    def wait(self, timeout=None):
        self._finished.wait(timeout)
        return self._exit_code

    # -- the worker thread -----------------------------------------------
    def _context_path(self):
        arguments = self.command
        for index, item in enumerate(arguments):
            if item == '--context' and index + 1 < len(arguments):
                return arguments[index + 1]
        raise ControllerError('CONTROLLER_COMMAND_WITHOUT_CONTEXT')

    def _run(self):
        code = 0
        try:
            expected = self._context_sha256
            if self._fault == 'context_seal_mismatch':
                # The worker refuses the context on its own seal check.
                expected = 'f' * 64
            context = WorkerContext.load(self._context_path(), expected_sha256=expected)
            driver = self._driver_factory(context)
            argv = ['--context', self._context_path()]
            code = worker_main(argv, driver=driver, stream=self._stdout_write,
                                error_stream=self._stderr_write)
        except ControllerError as error:
            code = 2
            self._write_error('S3_WORKER_REFUSED ' + error.code + '\n')
        except WorkerError as error:
            code = 2
            self._write_error('S3_WORKER_REFUSED ' + error.code + '\n')
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            code = 3
            self._write_error('S3_WORKER_REFUSED EXCEPTION ' + type(error).__name__ + '\n')
        try:
            self._apply_fault()
        except BaseException as error:  # noqa: BLE001 - the fault stays visible
            self._write_error('S3_COMPOSITION_FAULT_FAILED ' + type(error).__name__ + '\n')
        try:
            self._stdout_write.flush()
        except (OSError, ValueError):  # pragma: no cover - the pipe may be closed
            pass
        for stream in (self._stdout_write, self._stderr_write, self._stdin_write):
            try:
                stream.close()
            except (OSError, ValueError):  # pragma: no cover - defensive
                pass
        self._exit_code = code
        self._finished.set()

    def _write_error(self, text):
        try:
            self._stderr_write.write(text.encode('utf-8'))
            self._stderr_write.flush()
        except (OSError, ValueError):  # pragma: no cover - defensive
            pass

    def _apply_fault(self):
        """Apply the explicit synthetic fault of the seam, if any."""
        if self._fault in (None, 'none'):
            return
        root = Path(self._root_of_the_context())
        canonical = root / 'temp' / 's3-quality' / CANONICAL_RECEIPT_NAME
        if self._fault == 'tamper_canonical':
            raw = canonical.read_bytes()
            canonical.write_bytes(raw + b' ')
        elif self._fault == 'remove_canonical':
            canonical.unlink()

    def _root_of_the_context(self):
        context = WorkerContext.load(self._context_path(),
                                     expected_sha256=self._context_sha256)
        return Path(context.document['root'])

    def close_pipes(self):
        """Close every descriptor of the seam that the parent did not close.

        The parent closes the two read ends that it owns when their stream
        ended.  The write ends and the standard input of the worker belong
        to the seam, so the seam closes them itself: a composition leaves no
        descriptor behind.
        """
        for stream in (self.stdin, self.stdout, self.stderr):
            try:
                stream.close()
            except OSError:  # pragma: no cover - the close may race
                pass
        for stream in (self._stdout_write, self._stderr_write, self._stdin_write):
            try:
                stream.close()
            except (OSError, ValueError):  # pragma: no cover - defensive
                pass


class OfflineCompositionSeam:
    """The explicit in-process seam of the offline composition.

    The seam replaces exactly three things of the production path: the
    native driver construction, the operating system child process and the
    monotonic clock.  Everything else - the worker entry, the worker
    context, the quality phase, the protocol, the parent reader, the
    canonical receipt, the original evidence, the manifest and the summary -
    stays the production implementation.

    The seam is a Python object.  It is never written into a context
    document, it is never reachable from the command line and it can not
    start a native service, because the native driver construction is never
    called while the seam is active.
    """

    synthetic = True

    def __init__(self, *, driver_factory, context_sha256=None, clock=None, sleep=None,
                 fault='none', label='offline-synthetic-composition'):
        if not callable(driver_factory):
            raise ControllerError('CONTROLLER_SEAM_DRIVER_FACTORY_REQUIRED')
        self.driver_factory = driver_factory
        self.context_sha256 = context_sha256
        self.clock = clock
        self.sleep = sleep
        self.fault = fault
        self.label = label
        self.spawns = 0
        self.worker_exit_code = None
        self.worker_thread_finished = False
        self.faults_applied = []
        self.on_transition = None

    def spawn(self, command):
        """The synthetic spawner: a thread and two real pipes."""
        self.spawns += 1
        worker = _InProcessWorker(command, driver_factory=self.driver_factory,
                                  context_sha256=self.context_sha256,
                                  fault=self.fault)
        self._worker = worker
        return worker

    def wait_for_worker(self, timeout=30.0):
        """Wait for the worker thread and return its exit code."""
        worker = getattr(self, '_worker', None)
        if worker is None:
            return None
        worker._finished.wait(timeout)
        self.worker_thread_finished = worker._finished.is_set()
        self.worker_exit_code = worker._exit_code
        return self.worker_exit_code

    def close(self):
        """Close every descriptor that the seam owns."""
        worker = getattr(self, '_worker', None)
        if worker is not None:
            worker.close_pipes()


# --------------------------------------------------------------------------
# the controller
# --------------------------------------------------------------------------
class ProductionController:
    """The formal controller of one production composition."""

    def __init__(self, context, *, seam=None):
        if not isinstance(context, ControllerContext):
            raise ControllerError('CONTROLLER_CONTEXT_REQUIRED')
        if seam is not None and not isinstance(seam, OfflineCompositionSeam):
            raise ControllerError('CONTROLLER_SEAM_INVALID')
        self.context = context
        self.seam = seam
        self.state = None
        self.transitions = []
        self.worker_context = None
        self.rows = None
        self.projection_sha256 = None
        self.original_evidence = None
        self.supervisor = None
        self.plan = None
        self.plan_sha256 = None
        self.command = None
        self.evidence = None
        self.manifest = None
        self.canonical = None
        self.source_plan = None
        self.receipts = {}
        self.summary = None
        self.spawn_attempts = 0
        self.refusals = []
        self.unknown_reason = None

    # -- the state machine -------------------------------------------------
    def _enter(self, state):
        if state not in STATE_ORDER:
            raise ControllerError('CONTROLLER_STATE_UNKNOWN')
        if self.state is not None:
            index = STATE_ORDER.index(self.state)
            if STATE_ORDER.index(state) != index + 1:
                raise ControllerError('CONTROLLER_STATE_OUT_OF_ORDER')
        self.state = state
        self.transitions.append(state)
        if self.seam is not None and self.seam.on_transition is not None:
            try:
                self.seam.on_transition(state, self)
            except Exception as error:  # noqa: BLE001 - a fault stays visible
                raise ControllerError('CONTROLLER_TRANSITION_FAULT:' + type(error).__name__)

    # -- the precheck ------------------------------------------------------
    def _precheck(self):
        """The finite admission of the run, before any spawn."""
        context = self.context
        worker_reference = context.document['worker_context']
        try:
            worker = WorkerContext.load(worker_reference['path'],
                                        expected_sha256=worker_reference['sha256'])
        except WorkerError as error:
            raise ControllerError('CONTROLLER_WORKER_CONTEXT_REFUSED:' + error.code) from error
        self.worker_context = worker
        if worker.run_id != context.run_id:
            raise ControllerError('CONTROLLER_WORKER_RUN_ID_MISMATCH')
        if worker.candidate_sha != context.candidate_sha:
            raise ControllerError('CONTROLLER_WORKER_CANDIDATE_MISMATCH')
        if worker.authorization_sha256 != context.authorization_sha256:
            raise ControllerError('CONTROLLER_WORKER_AUTHORIZATION_MISMATCH')
        root = Path(worker.document['root'])
        if not root.is_absolute() or root.resolve() != context.root.resolve():
            raise ControllerError('CONTROLLER_WORKER_ROOT_MISMATCH')
        if not root.is_dir():
            raise ControllerError('CONTROLLER_ROOT_UNAVAILABLE')
        try:
            projection = worker.projection()
            rows = parse_projection_rows(projection)
            worker.source_identity()
            budget = worker.parent_budget()
            worker.dependency_manifest()
            worker.binding()
        except WorkerError as error:
            raise ControllerError('CONTROLLER_WORKER_SEAL_REFUSED:' + error.code) from error
        if budget.get('run_id') != context.run_id \
                or budget.get('candidate_sha') != context.candidate_sha \
                or budget.get('authorization_sha256') != context.authorization_sha256:
            raise ControllerError('CONTROLLER_PARENT_BUDGET_IDENTITY_MISMATCH')
        self.rows = rows
        self.projection_sha256 = worker.document['projection_sha256']
        self.command = build_production_command(worker_reference['path'])

    # -- the native admission ----------------------------------------------
    def _admission_report(self):
        """The admission report of this run.

        The report names every element that is missing.  It is never
        repaired and never guessed, and the controller that starts no native
        process does not need one - it reports that fact instead.
        """
        if self.seam is not None:
            # The offline seam starts no native process, so the native
            # admission is not required.  It is reported as not proven
            # anyway: the run of the seam proves no native capability.
            return self._refused_admission(
                'NATIVE_ADMISSION_NOT_REQUIRED_FOR_THE_OFFLINE_SEAM')
        reference = self.context.document['admission']
        document = _load_referenced(reference, label='admission', reasons=[])
        if document is None:
            return self._refused_admission('ADMISSION_DOCUMENT_UNREADABLE')
        return verify_native_admission(self.context, document)

    @staticmethod
    def _refused_admission(reason):
        return {'kind': 'lvw.s3-native-admission-report/1',
                'accepted': False,
                'reasons': [reason],
                'verified': [],
                'primary_reason': reason,
                'budget_authority': 'S3BudgetBindingProvider',
                'original_ledger_touched_by_this_controller': False,
                'debit_owner': 'original_ledger_authority',
                'stage_pass_claim': False,
                'product_gate0': False}

    # -- the plan -----------------------------------------------------------
    def _seal_plan(self):
        evidence = ParentOriginalEvidence(
            run_id=self.context.run_id,
            candidate_sha=self.context.candidate_sha,
            child_sha256=self.context.authorization_sha256,
            root=self.context.root,
            projection_sha256=self.projection_sha256)
        self.plan_sha256 = evidence.seal_plan(self.rows)
        identity = os.stat(self.context.root)
        evidence.seal_root([identity.st_dev, identity.st_ino])
        self.original_evidence = evidence
        self.plan = SealedPlan([{'ordinal': row['ordinal'], 'asset_id': row['asset_id'],
                                  'media_kind': row['media_kind']} for row in self.rows])

    # -- the supervision ----------------------------------------------------
    def _supervise(self):
        seam = self.seam
        kwargs = {'command': self.command,
                  'run_id': self.context.run_id,
                  'candidate_sha': self.context.candidate_sha,
                  'authorization_sha256': self.context.authorization_sha256,
                  'plan': self.plan,
                  'root': self.context.root,
                  'original_sealer': self.original_evidence}
        if seam is not None:
            kwargs['spawner'] = seam.spawn
            if seam.clock is not None:
                kwargs['clock'] = seam.clock
        self.spawn_attempts = 1
        supervisor = ParentSupervisor(**kwargs)
        self.supervisor = supervisor
        try:
            self.evidence = supervisor.run()
        except SupervisionError as error:
            raise ControllerError('CONTROLLER_SUPERVISION_REFUSED:' + error.code) from error
        finally:
            if seam is not None:
                seam.wait_for_worker()
        return self.evidence

    # -- the originals ------------------------------------------------------
    def _verify_originals(self):
        evidence = self.evidence
        if evidence.get('unknown_outcome') or not evidence.get('canonical_receipt_verified'):
            raise ControllerError('CONTROLLER_OUTCOME_UNKNOWN:' + str(evidence.get('protocol_violation')))
        reference = evidence['canonical_receipt']['reference']
        artifact_root = self.context.root / 'temp' / 's3-quality'
        try:
            canonical = load_published_execution_receipt(artifact_root)
            source_plan = load_source_plan(artifact_root, canonical)
        except QualityContractError as error:
            raise ControllerError('CONTROLLER_PUBLISHED_RECEIPT_REFUSED:' + str(error)) from error
        if canonical.get('run_id') != self.context.run_id \
                or canonical.get('candidate_sha') != self.context.candidate_sha \
                or canonical.get('authorization_sha256') != self.context.authorization_sha256:
            raise ControllerError('CONTROLLER_CANONICAL_IDENTITY_MISMATCH')
        if canonical.get('projection_sha256') != self.projection_sha256:
            raise ControllerError('CONTROLLER_CANONICAL_PROJECTION_MISMATCH')
        self.canonical = canonical
        self.source_plan = source_plan
        raw = self._raw_references(canonical)
        source_plan_reference = 'temp/s3-quality/' + str(canonical['source_plan']['path'])
        try:
            self.original_evidence.seal_originals(canonical=reference,
                                                  source_plan=source_plan_reference,
                                                  raw=raw)
            self.manifest = self.original_evidence.manifest()
        except S3IntegrationError as error:
            raise ControllerError('CONTROLLER_ORIGINALS_REFUSED:' + error.reason) from error
        return self.manifest

    @staticmethod
    def _raw_references(canonical):
        """The root relative references of the raw artefacts of the run."""
        references = []
        for row in canonical.get('rows', []):
            if not isinstance(row, dict):
                continue
            for key in ('raw_artifact', 'graph_artifact', 'suggestion_artifact',
                        'metadata_artifact', 'history_artifact', 'error_raw_artifact',
                        'error_frame_raw_artifact'):
                value = row.get(key)
                if isinstance(value, str) and value:
                    references.append('temp/s3-quality/' + value)
        return references

    # -- the receipts -------------------------------------------------------
    def _bind_receipts(self):
        """The aggregate receipts of this run, derived from the run facts.

        A receipt is derived only from a fact of this run.  A receipt whose
        truth belongs to the native or the product side stays unproven and
        is never filled with a promise.
        """
        canonical = self.canonical
        receipts = {}
        evidence = self.evidence
        rows = canonical.get('rows', [])
        images = [row for row in rows if row.get('media_kind') == 'image']
        videos = [row for row in rows if row.get('media_kind') == 'video']
        executed = [row for row in rows if row.get('execution_status') == 'PASS']
        provenance = self._provenance()

        def make(name, status, reason, sources):
            return {'kind': AGGREGATE_RECEIPT_KIND,
                    'name': name,
                    'status': status,
                    'run_id': self.context.run_id,
                    'candidate_sha': self.context.candidate_sha,
                    'authorization_sha256': self.context.authorization_sha256,
                    'reason': reason,
                    'sources': sources,
                    'evidence_scope': 'OFFLINE_SYNTHETIC_COMPOSITION',
                    'product_pass_claimed': False,
                    'stage_pass_claim': False,
                    'product_gate0': False}

        receipts['stage_binding'] = make(
            'stage_binding', 'PASS',
            'THE_SEALED_BINDING_AND_THE_IDENTITY_OF_THIS_RUN_WERE_VERIFIED',
            [{'source': 'worker_context', 'sha256': self.context.document['worker_context']['sha256']},
             {'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}])
        receipts['image_input'] = make(
            'image_input', 'PASS' if len(executed) == len(rows) and images else 'FAIL',
            'THE_IMAGE_ROWS_OF_THIS_RUN_WERE_EXECUTED_WITH_THEIR_SEALED_SOURCE_IDENTITY',
            [{'source': 'source_plan', 'sha256': provenance['source_plan']['sha256']},
             {'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}])
        receipts['video_input'] = make(
            'video_input', 'PASS' if len(executed) == len(rows) and videos else 'FAIL',
            'THE_VIDEO_ROWS_OF_THIS_RUN_WERE_EXECUTED_WITH_THEIR_SEALED_SOURCE_IDENTITY',
            [{'source': 'source_plan', 'sha256': provenance['source_plan']['sha256']},
             {'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}])
        outputs = [row for row in rows if row.get('raw_artifact') and row.get('suggestion_artifact')]
        receipts['output_contract'] = make(
            'output_contract', 'PASS' if len(outputs) == len(rows) and rows else 'FAIL',
            'EVERY_ROW_PUBLISHED_ITS_RAW_AND_SUGGESTION_ARTEFACTS',
            [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}])
        receipts['no_overwrite'] = make(
            'no_overwrite', 'PASS',
            'EVERY_ARTEFACT_OF_THIS_RUN_WAS_CREATED_EXCLUSIVELY_INSIDE_THE_OWNED_PHASE_DIRECTORY',
            [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}])
        receipts['file_safety'] = make(
            'file_safety', 'PASS' if self.manifest else 'FAIL',
            'THE_PARENT_REVERIFIED_EVERY_ORIGINAL_THROUGH_THE_NO_FOLLOW_PROCEDURE',
            [{'source': 'parent_manifest', 'sha256': provenance['manifest']['sha256']}])
        receipts['resource_budget'] = make(
            'resource_budget',
            'PASS' if canonical.get('provider_calls_reserved') is not None else 'FAIL',
            'THE_PROVIDER_CALL_BUDGET_OF_THIS_RUN_WAS_ACCOUNTED_BY_THE_PHASE',
            [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}])
        receipts['quality_16_rows'] = make(
            'quality_16_rows',
            'PASS' if canonical.get('test_counts', {}).get('PASS') == 16 else 'FAIL',
            'THE_SIXTEEN_ROWS_OF_THIS_RUN_WERE_EXECUTED_AND_SEALED_BY_THE_PHASE_OWNER',
            [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']},
             {'source': 'source_plan', 'sha256': provenance['source_plan']['sha256']}])
        for name, reason in UNPROVEN_RECEIPTS.items():
            receipts[name] = make(name, 'BLOCKED', reason, [])
        independent = self._independent_score_receipt()
        if independent is not None:
            # The independent score of the run is only ever the verdict of
            # the accepted owner of the score.
            receipts['independent_score'] = independent
        self.residue_observations = self._residue_observations(rows)
        residue_open = [item for item in self.residue_observations
                        if not item['proven_empty']]
        if residue_open:
            # The residue of the run is not proven empty.  The cleanup
            # obligation of the run stays blocked and names the rows whose
            # residue could not be proven; nothing is deleted here.
            receipts['cleanup']['reason'] = ('RESIDUE_NOT_PROVEN_EMPTY:'
                                             + ','.join(item['asset_id']
                                                       for item in residue_open))
            receipts['cleanup']['sources'] = [{'source': 'canonical_receipt',
                                               'sha256': provenance['canonical']['sha256'],
                                               'residue_rows': residue_open}]
        self.receipts = receipts
        return receipts

    @staticmethod
    def _residue_observations(rows):
        """The residue observations of the run, exactly as the phase saw them.

        An observation that is not the empty list is an *unknown* residue: it
        is never read as an empty residue and it is never deleted.  The
        observation keeps its own error, so a consumer can see that the
        residue could not be proven empty.
        """
        observations = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get('video_snapshot_residue')
            if value is None:
                continue
            observations.append({'asset_id': row.get('asset_id'),
                                 'observation': value,
                                 'proven_empty': value == [],
                                 'unknown': not isinstance(value, list)})
        return observations

    def _independent_score_receipt(self):
        """The independent score of the run, recomputed by the QS owner.

        The independent score is only ever a receipt when the sealed score
        documents and the sealed independence evidence exist.  Without them
        the receipt stays unproven: sixteen executed rows are not an
        independent quality verdict.
        """
        context = self.context
        scores_reference = context.document['quality_scores']
        independence_reference = context.document['independence']
        if scores_reference['path'] is None or independence_reference['path'] is None:
            return None
        scores = _load_referenced(scores_reference, label='quality_scores', reasons=[],
                                  mapping=False)
        independence = _load_referenced(independence_reference, label='independence',
                                        reasons=[])
        if scores is None or independence is None:
            return None
        artifact_root = context.root / 'temp' / 's3-quality'
        try:
            verdict = recompute_scores(self.canonical, artifact_root, scores,
                                       independence=independence)
        except QualityContractError as error:
            return {'kind': AGGREGATE_RECEIPT_KIND, 'name': 'independent_score',
                    'status': 'BLOCKED', 'run_id': context.run_id,
                    'candidate_sha': context.candidate_sha,
                    'authorization_sha256': context.authorization_sha256,
                    'reason': 'INDEPENDENT_SCORE_REFUSED:' + str(error),
                    'sources': [], 'independent': False,
                    'evidence_scope': 'OFFLINE_SYNTHETIC_COMPOSITION',
                    'product_pass_claimed': False,
                    'stage_pass_claim': False, 'product_gate0': False}
        passed = (isinstance(verdict, dict) and verdict.get('aggregate_pass') is True)
        return {'kind': AGGREGATE_RECEIPT_KIND, 'name': 'independent_score',
                'status': 'PASS' if passed else 'FAIL',
                'run_id': context.run_id, 'candidate_sha': context.candidate_sha,
                'authorization_sha256': context.authorization_sha256,
                'reason': 'THE_INDEPENDENT_SCORE_WAS_RECOMPUTED_BY_THE_QS_OWNER',
                'sources': [{'source': 'quality_scores', 'sha256': scores_reference['sha256']},
                            {'source': 'independence', 'sha256': independence_reference['sha256']}],
                'independent': True,
                'evidence_scope': 'OFFLINE_SYNTHETIC_COMPOSITION',
                'product_pass_claimed': False,
                'stage_pass_claim': False, 'product_gate0': False}

    # -- the provenance -----------------------------------------------------
    def _provenance(self):
        """The same source chain from the context to the summary."""
        canonical_reference = self.evidence['canonical_receipt']['reference']
        canonical_bytes = (self.context.root / canonical_reference).read_bytes()
        source_plan_bytes = (self.context.root / 'temp' / 's3-quality'
                             / str(self.canonical['source_plan']['path'])).read_bytes()
        manifest_bytes = canonical_json(self.manifest).encode('utf-8')
        return {
            'controller_context': {'sha256': self.context.document['worker_context']['sha256'],
                                   'owner': 'controller_context'},
            'projection': {'sha256': self.projection_sha256, 'owner': 'quality_phase_projection'},
            'plan': {'sha256': self.plan_sha256, 'owner': 'ParentOriginalEvidence'},
            'worker_context': {'sha256': self.context.document['worker_context']['sha256'],
                               'owner': 'WorkerContext'},
            'canonical': {'reference': canonical_reference,
                          'sha256': sha256_bytes(canonical_bytes),
                          'bytes': len(canonical_bytes),
                          'owner': 'quality_phase_canonical_receipt'},
            'source_plan': {'sha256': sha256_bytes(source_plan_bytes),
                            'bytes': len(source_plan_bytes),
                            'owner': 'quality_phase_source_plan'},
            'manifest': {'sha256': sha256_bytes(manifest_bytes),
                         'owner': 'ParentOriginalEvidence'},
        }

    # -- the summary --------------------------------------------------------
    def _build_summary(self):
        receipts = dict(self.receipts)
        binding = {'run_id': self.context.run_id, 'candidate_sha': self.context.candidate_sha}
        summary = aggregate_twelve_keys(receipts=receipts, binding=binding)
        summary['kind'] = SUMMARY_KIND
        summary['provenance'] = self._provenance()
        summary['execution_mode'] = 'OFFLINE_SYNTHETIC_COMPOSITION' if self.seam is not None \
            else 'NATIVE'
        summary['offline_receipts_are_not_product_receipts'] = True
        summary['synthetic_fixtures_count_as_product_pass'] = False
        summary['old_s2_nine_keys_accepted_as_green'] = False
        summary['stage_pass_claim'] = False
        summary['product_gate0'] = False
        summary['real_execution_performed'] = False
        return summary

    def _persist_summary(self):
        directory = self.context.root / 'temp' / 's3-production-controller'
        directory.mkdir(parents=True, exist_ok=True)
        summary_path = directory / ('summary-' + self.context.run_id + '.json')
        receipt_path = directory / ('receipt-' + self.context.run_id + '.json')
        for path in (summary_path, receipt_path):
            if path.exists():
                raise ControllerError('CONTROLLER_SUMMARY_ALREADY_EXISTS')
        summary_bytes = canonical_json(self.summary).encode('utf-8')
        self._write_exclusive(summary_path, summary_bytes)
        self.summary_path = summary_path
        self.summary_sha256 = sha256_bytes(summary_bytes)
        return summary_path

    @staticmethod
    def _write_exclusive(path, raw):
        """Write a file exactly once.  An existing file is never replaced."""
        try:
            descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise ControllerError('CONTROLLER_OUTPUT_ALREADY_EXISTS') from error
        except OSError as error:
            raise ControllerError('CONTROLLER_OUTPUT_UNWRITABLE') from error
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise ControllerError('CONTROLLER_OUTPUT_UNWRITABLE') from error

    # -- the run ------------------------------------------------------------
    def run(self):
        """Run the composition and return the controller receipt."""
        started = time.time()
        fd_before = _fd_snapshot()
        receipt = {'kind': CONTROLLER_RECEIPT_KIND,
                   'run_id': self.context.run_id,
                   'candidate_sha': self.context.candidate_sha,
                   'authorization_sha256': self.context.authorization_sha256,
                   'root': str(self.context.root),
                   'execution_mode': 'OFFLINE_SYNTHETIC_COMPOSITION' if self.seam is not None
                   else 'NATIVE',
                   'state': None,
                   'transitions': [],
                   'refusals': [],
                   'spawn_attempts': 0,
                   'stage_pass_claim': False,
                   'product_gate0': False,
                   'real_execution_performed': False,
                   'offline_receipts_are_not_product_receipts': True,
                   'started_wall': started}
        try:
            self._precheck()
            receipt['admission'] = self._admission_report()
            if self.seam is None and not receipt['admission']['accepted']:
                raise ControllerError('CONTROLLER_NATIVE_ADMISSION_NOT_PROVEN:'
                                      + str(receipt['admission']['primary_reason']))
            self._enter(STATE_PRECHECK)
            self._seal_plan()
            self._enter(STATE_PLAN_SEALED)
            receipt['command'] = list(self.command)
            receipt['plan'] = {'rows': 16, 'plan_sha256': self.plan_sha256,
                               'projection_sha256': self.projection_sha256}
            self._supervise()
            self._enter(STATE_WORKER_SUPERVISED)
            receipt['supervision'] = self.evidence
            receipt['spawn_attempts'] = self.spawn_attempts
            if self.evidence.get('unknown_outcome') or not self.evidence.get('canonical_receipt_verified'):
                receipt['unknown_reason'] = self.evidence.get('protocol_violation') \
                    or 'TERMINAL_RECEIPT_NOT_VERIFIED'
                receipt['recovery'] = self._recovery_entry()
                receipt['state'] = STATE_UNKNOWN
                receipt['root_retained'] = True
                receipt['reservation_retained'] = True
                receipt['refund_allowed'] = False
                receipt['resend_allowed'] = False
                receipt['archive_allowed'] = False
                receipt['summary_persisted'] = False
                return self._finish(receipt, fd_before)
            self._verify_originals()
            self._enter(STATE_ORIGINALS_VERIFIED)
            receipt['manifest'] = self.manifest
            self._bind_receipts()
            self._enter(STATE_RECEIPTS_BOUND)
            receipt['receipts'] = self.receipts
            receipt['residue_observations'] = self.residue_observations
            self.summary = self._build_summary()
            receipt['summary'] = self.summary
            self._persist_summary()
            self._enter(STATE_SUMMARY_PERSISTED)
            receipt['state'] = STATE_SUMMARY_PERSISTED
            receipt['summary_persisted'] = True
            receipt['summary_path'] = str(self.summary_path)
            receipt['summary_sha256'] = self.summary_sha256
            receipt['root_retained'] = bool(self.evidence.get('root_retained'))
            receipt['reservation_retained'] = bool(self.evidence.get('reservation_retained'))
            receipt['refund_allowed'] = False
            receipt['resend_allowed'] = False
        except ControllerError as error:
            receipt['refusals'].append(error.code)
            receipt['state'] = STATE_REFUSED if not self.transitions else STATE_UNKNOWN
            receipt['summary_persisted'] = False
            receipt['root_retained'] = True
            receipt['reservation_retained'] = True
            receipt['refund_allowed'] = False
            receipt['resend_allowed'] = False
            receipt['archive_allowed'] = False
            receipt['unknown_reason'] = error.code
            if self.state is not None and self.state != STATE_PRECHECK:
                receipt['recovery'] = self._recovery_entry()
        return self._finish(receipt, fd_before)

    def _recovery_entry(self):
        """The recovery entry of an unknown outcome.

        The recovery coordinates the cleanup and the existing evidence only.
        It never replays, never resends and never terminates a process on the
        basis of a PID that was read from a file.
        """
        from tools.v0_s3_supervisor import RecoveryEntry
        custody = None
        if self.evidence is not None:
            pid = self.evidence.get('pid')
            birth = self.evidence.get('birth')
            # The custody is only real when the parent actually holds a
            # process identity.  The offline seam creates no child, so it
            # has no custody and the recovery stays blocked instead of
            # claiming a recovery for a process that never existed.
            if type(pid) is int and pid > 0 and isinstance(birth, dict):
                custody = {'run_id': self.context.run_id,
                           'candidate_sha': self.context.candidate_sha,
                           'authorization_sha256': self.context.authorization_sha256,
                           'pid': pid,
                           'birth': birth}
        return RecoveryEntry(custody=custody).recover()

    def _finish(self, receipt, fd_before):
        if self.seam is not None:
            # The seam closes its own descriptors before the descriptor
            # snapshot of the receipt is taken.
            self.seam.close()
        receipt['transitions'] = list(self.transitions)
        receipt['duration_seconds'] = round(time.time() - receipt['started_wall'], 6)
        receipt['source_sha256'] = self._source_digests()
        receipt['node_id'] = self._node_id(receipt)
        receipt['execution_attempts'] = 1
        fd_after = _fd_snapshot()
        receipt['fd_cleanup'] = {'fd_before': fd_before,
                                  'fd_after': fd_after,
                                  'fd_leaked': (sorted(set(fd_after) - set(fd_before))
                                                if fd_before is not None and fd_after is not None
                                                else None),
                                  'worker_thread_finished': bool(
                                      self.seam.worker_thread_finished) if self.seam else None,
                                  'worker_exit_code': (self.seam.worker_exit_code
                                                       if self.seam else None),
                                  'readers_closed': self._readers_closed()}
        receipt['stage_pass_claim'] = False
        receipt['product_gate0'] = False
        receipt['real_execution_performed'] = False
        return receipt

    def _readers_closed(self):
        evidence = self.evidence or {}
        supervisor = getattr(self, 'supervisor', None)
        return {'stdout_drain_complete': evidence.get('stdout_drain_complete'),
                'stderr_drain_complete': evidence.get('stderr_drain_complete'),
                'stdout_read_error': evidence.get('stdout_read_error'),
                'stderr_read_error': evidence.get('stderr_read_error'),
                'closed_streams': (list(supervisor.closed_streams)
                                   if supervisor is not None else None)}

    @staticmethod
    def _source_digests():
        digests = {}
        for relative in SOURCE_FILES:
            path = PACK_ROOT / relative
            try:
                digests[relative] = sha256_bytes(path.read_bytes())
            except OSError:  # pragma: no cover - a missing source is reported
                digests[relative] = None
        return digests

    def _node_id(self, receipt):
        material = canonical_json({
            'run_id': self.context.run_id,
            'candidate_sha': self.context.candidate_sha,
            'command': receipt.get('command'),
            'pid': os.getpid(),
            'started': receipt.get('started_wall'),
            'mode': receipt.get('execution_mode'),
        }).encode('utf-8')
        return hashlib.sha256(material).hexdigest()[:32]


# --------------------------------------------------------------------------
# the command line entry
# --------------------------------------------------------------------------
def main(argv=None):
    """The formal command line entry of the controller.

    The argument set is closed: the sealed controller context, the optional
    seal of that context and the optional path of the receipt.  There is no
    switch that turns a refusal into an execution and there is no argument
    that names a command, a module or a callback.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    context_path = None
    context_sha256 = None
    receipt_path = None
    index = 0
    while index < len(arguments):
        item = arguments[index]
        if item == '--context' and index + 1 < len(arguments):
            context_path = arguments[index + 1]
            index += 2
            continue
        if item == '--context-sha256' and index + 1 < len(arguments):
            context_sha256 = arguments[index + 1]
            index += 2
            continue
        if item == '--receipt' and index + 1 < len(arguments):
            receipt_path = arguments[index + 1]
            index += 2
            continue
        sys.stderr.write('S3_CONTROLLER_REFUSED CONTROLLER_ARGUMENT_INVALID\n')
        return EXIT_REFUSED
    if context_path is None:
        sys.stderr.write('S3_CONTROLLER_REFUSED CONTROLLER_CONTEXT_ARGUMENT_REQUIRED\n')
        return EXIT_REFUSED
    try:
        context = ControllerContext.load(context_path, expected_sha256=context_sha256)
        controller = ProductionController(context)
        receipt = controller.run()
    except ControllerError as error:
        sys.stderr.write('S3_CONTROLLER_REFUSED ' + error.code + '\n')
        return EXIT_REFUSED
    except Exception as error:  # noqa: BLE001 - the failure stays visible
        sys.stderr.write('S3_CONTROLLER_REFUSED EXCEPTION ' + type(error).__name__ + '\n')
        return EXIT_INTERNAL
    if receipt_path is not None:
        try:
            ProductionController._write_exclusive(Path(receipt_path),
                                                 canonical_json(receipt).encode('utf-8'))
        except ControllerError as error:
            sys.stderr.write('S3_CONTROLLER_REFUSED ' + error.code + '\n')
            return EXIT_REFUSED
    sys.stdout.write(canonical_json(receipt) + '\n')
    if receipt['state'] == STATE_SUMMARY_PERSISTED:
        return EXIT_PERSISTED
    if receipt['state'] == STATE_UNKNOWN:
        return EXIT_UNKNOWN
    return EXIT_REFUSED


if __name__ == '__main__':
    sys.exit(main())
