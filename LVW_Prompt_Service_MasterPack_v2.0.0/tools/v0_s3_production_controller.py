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

Three boundaries are absolute.

* The *native* execution path is refused by default.  There is no accepted
  native execution backend on this platform: no accepted admission
  authority, no accepted finite grant, no accepted native descendant
  custody and no accepted GPU release exist.  The controller and the
  worker therefore refuse with the stable code
  ``NATIVE_EXECUTION_BACKEND_NOT_READY`` before any spawn and before any
  native driver is constructed.  A boolean, a platform string, a self
  written capability document or a self computed hash never replaces the
  missing authority, and there is no ``--force`` switch.
* The *offline composition* is an explicit in-process seam.  It injects a
  synthetic driver, a synthetic spawner and a synthetic clock into the very
  same controller, worker, phase, protocol, parent reader, canonical
  receipt, manifest and summary path.  It creates no operating system child
  process: the worker runs in a thread and speaks over a real pipe.  The
  seam is a Python object; it is never serialised into a context document
  and it is never reachable from the command line, so it can never become a
  back door of a real execution.
* Every *input* of the controller is bounded and safe.  The reads are
  bounded before the bytes are taken, they never follow a link and they
  never read a special file as a file; the summary and the reservation are
  written exclusively inside the bound root, and the originals are
  re-verified at the consumption boundary before anything is published.

Nothing in this module proves a product gate.  Every document that it writes
carries ``stage_pass_claim = False`` and ``product_gate0 = False``, and the
synthetic facts of the offline seam are never counted as a product pass.
"""
import errno
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

from tools.v0_s3_controller_io import (  # noqa: E402 - the path is set above
    ControllerIOError, ensure_directory_chain, errno_name, exists_at,
    open_root_directory_chain, read_bounded_in_root_at, read_bounded_regular,
    verify_directory_chain, verify_directory_identity, write_exclusive_at,
    write_exclusive_path)
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
RESERVATION_KIND = 'lvw.s3-controller-reservation/1'

# The stable code of the one missing capability of this platform.
#
# There is no accepted native execution backend today: no accepted
# admission authority, no accepted finite grant, no accepted native
# descendant custody and no accepted GPU release exist for this
# platform.  The native path therefore refuses *before* any spawn and
# before any native driver is constructed, and the refusal is the same
# stable code on the controller side and on the worker side.  A self
# written capability document, a boolean, a platform string or a self
# computed hash never replaces the missing authority.
NATIVE_EXECUTION_BACKEND_NOT_READY = 'NATIVE_EXECUTION_BACKEND_NOT_READY'

# The directory of this controller inside the bound run root.  Every
# component is opened or created relative to the descriptor of its own
# parent, so a link in the chain is never followed.
CONTROLLER_DIRECTORY_PARTS = ('temp', 's3-production-controller')

# The keys of a row of the canonical receipt that name an artefact of the
# run.  They are the references that the parent seals and that the
# ``no_overwrite`` obligation is about.
ROW_ARTEFACT_KEYS = ('raw_artifact', 'graph_artifact', 'suggestion_artifact',
                      'metadata_artifact', 'history_artifact', 'error_raw_artifact',
                      'error_frame_raw_artifact')

# The artefact of a row and the digest that the row claims for it.  The
# parent sealed the real bytes of every artefact of the run, so the digest
# of the seal and the digest of the row have to be the same.
ROW_ARTEFACT_DIGEST_KEYS = (('raw_artifact', 'raw_sha256'),
                             ('graph_artifact', 'graph_sha256'),
                             ('suggestion_artifact', 'suggestion_sha256'),
                             ('metadata_artifact', 'metadata_sha256'),
                             ('history_artifact', 'history_sha256'))

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

# The formal obligations of the three product keys that a run of this
# controller can not prove.  The obligation of a key is the *complete*
# obligation of the product, not the subset that one synthetic run happens
# to observe.  A receipt of one of these names is therefore never a pass
# of the run: the run can only show that a necessary sub-condition of the
# obligation failed, or that the obligation has no evidence at all.
FORMAL_OBLIGATIONS = {
    'output_contract': {
        'product_key': 'V0-A03',
        'obligation': ('THE_FORMAL_OUTPUT_CONTRACT_REQUIRES_THE_FOUR_VIEWS_OF_EVERY_ROW,'
                       'THE_JSON_AND_TXT_EXPORTS_AND_A_FORMAT_SWITCH_WITHOUT_EXTRA_INFERENCE'),
        'missing': ('THE_FOUR_VIEWS_THE_JSON_AND_TXT_EXPORTS_AND_THE_FORMAT_SWITCH_'
                    'WITHOUT_EXTRA_INFERENCE_ARE_NOT_PROVEN'),
    },
    'no_overwrite': {
        'product_key': 'V0-A05',
        'obligation': ('THE_FORMAL_NO_OVERWRITE_REQUIRES_THE_PROTECTION_OF_AN_EXISTING_'
                       'HUMAN_DRAFT_UNDER_INVALID_JSON_TIMEOUT_OOM_AND_NO_ANSWER_AND_'
                       'THE_CONTINUED_EXPORT'),
        'missing': ('THE_PROTECTION_OF_AN_EXISTING_HUMAN_DRAFT_AND_THE_CONTINUED_'
                    'EXPORT_ARE_NOT_PROVEN'),
    },
    'resource_budget': {
        'product_key': 'V0-A09',
        'obligation': ('THE_FORMAL_RESOURCE_BUDGET_REQUIRES_THE_TARGET_MACHINE_RESOURCE_'
                       'AND_PERFORMANCE_MATRIX'),
        'missing': ('THE_TARGET_GPU_RAM_THERMAL_COLD_WARM_P95_AND_ZERO_OOM_MATRIX_'
                    'IS_NOT_PROVEN'),
    },
}

# The facts that a synthetic run really observed.  They are *not* the
# formal obligations above: they have their own kind, their own names and
# their own scope, and they are listed separately, so a fact of a run can
# never fill a formal receipt of the same name.
COMPOSITION_FACT_KIND = 'lvw.s3-composition-fact/1'
COMPOSITION_FACT_SCOPE = 'OFFLINE_SYNTHETIC_COMPOSITION'


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
    """Read one explicit entry file with a real bound.

    The bytes are taken from the handle that was opened and verified, and
    the bound is applied to the bytes that are really requested from the
    kernel.  An oversized file is therefore refused without being read
    into the memory of the process, and a link or a special file is never
    read as a file.
    """
    try:
        return read_bounded_regular(path, limit)
    except ControllerIOError as error:
        raise ControllerError('CONTROLLER_' + error.code) from error


def _fd_snapshot():
    """The descriptors that are really open in this process.

    The enumeration of ``/proc/self/fd`` is not a proof: ``os.listdir`` of
    a descriptor copies that descriptor for the duration of the listing
    and closes the copy again, so the listing names a descriptor that is
    closed already.  Every name is therefore verified with ``fstat``
    before it is recorded.

    * a name whose descriptor is closed (``EBADF``) is dropped and
      reported as a closed entry - it was never an open descriptor;
    * a name that can not be verified for another reason is **kept** and
      reported, so an unknown or a refused descriptor never becomes a
      false empty;
    * the enumeration resource of this snapshot belongs to the snapshot
      itself and is never recorded.

    The snapshot also carries the stable identity and the type of every
    recorded descriptor, so a later comparison names the very object and
    not only a number.
    """
    try:
        descriptor = os.open('/proc/self/fd', os.O_RDONLY)
    except OSError:  # pragma: no cover - a platform without procfs
        return None
    try:
        try:
            names = os.listdir(descriptor)
        except OSError:  # pragma: no cover - defensive
            return None
    finally:
        os.close(descriptor)
    opened = []
    closed = []
    unverified = []
    identity = {}
    for name in names:
        if not name.isdigit():
            continue
        number = int(name)
        if number == descriptor:
            # the enumeration resource of this snapshot belongs to the
            # snapshot itself and is closed with it
            continue
        try:
            info = os.fstat(number)
        except OSError as error:
            if error.errno == errno.EBADF:
                # the listing named a descriptor that is closed already
                closed.append(number)
                continue
            # An unknown or a refused descriptor is never an empty: it is
            # kept and reported, so the comparison stays conservative.
            unverified.append({'fd': number, 'error': errno_name(error)})
            opened.append(number)
            continue
        opened.append(number)
        identity[number] = {'device': int(info.st_dev),
                            'inode': int(info.st_ino),
                            'mode': int(info.st_mode)}
    return {'open': sorted(opened),
            'closed_entries': sorted(closed),
            'unverified_entries': unverified,
            'identity': identity}


class _SealedBytesBoundary:
    """The byte serving boundary of the two published documents.

    The owner of the canonical receipt and of the source plan verifies its
    documents through a boundary that it owns.  This adapter serves the
    *very bytes* that the controller read through the bound root, so the
    owner validates the same bytes that the controller hashes and that the
    parent seals.  The adapter never touches the file system for these two
    documents: a document that was parsed from other bytes can not reach
    the controller, because the controller cross-checks the decoded bytes
    against the returned document with a strict comparison of the type and
    of the value.

    The run root of the adapter is the root of this run, so the owner of
    the documents still verifies the binding of the run root.
    """

    def __init__(self, run_root_path, run_root_identity):
        self.run_root_path = Path(run_root_path)
        self.run_root_identity = (int(run_root_identity[0]), int(run_root_identity[1]))
        self._entries = {}

    def add(self, relative, raw):
        """Bind one artifact relative name to the bytes that were read."""
        self._entries[str(relative)] = bytes(raw)

    def read(self, relative, max_bytes):
        raw = self._entries.get(str(relative))
        if raw is None:
            raise QualityContractError('QS_BOUND_DOCUMENT_NOT_BOUND:' + str(relative))
        if len(raw) > max_bytes:
            raise QualityContractError('QS_BOUND_DOCUMENT_TOO_LARGE:' + str(relative))
        return raw

    def verify(self):
        """The hierarchy of this boundary is verified by the controller."""
        return None

    def close(self):
        """This boundary owns no descriptor."""
        return None


def _decode_bound_bytes(raw, label):
    """The strict decoding of the bytes that the controller consumed."""
    try:
        document = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as error:
        raise ControllerError('CONTROLLER_' + label + '_NOT_JSON') from error
    if not isinstance(document, dict):
        raise ControllerError('CONTROLLER_' + label + '_NOT_OBJECT')
    return document


def _same_document(left, right):
    """Whether two documents are the same type and the same value.

    The comparison is a comparison of the canonical form of both
    documents, so a boolean is never the number one and the number one is
    never the boolean true.
    """
    return canonical_json(left) == canonical_json(right)


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
        # The digest and the length of the very bytes of this context.
        # They are the identity of the controller context itself and not
        # the identity of the worker context that it names.
        self.document_sha256 = None
        self.document_bytes = None

    @classmethod
    def load(cls, path, *, expected_sha256=None):
        raw = _read_bounded(path)
        digest = sha256_bytes(raw)
        if expected_sha256 is not None and digest != expected_sha256:
            raise ControllerError('CONTROLLER_CONTEXT_SEAL_MISMATCH')
        try:
            document = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as error:
            raise ControllerError('CONTROLLER_CONTEXT_NOT_JSON') from error
        context = cls(document)
        context.document_sha256 = digest
        context.document_bytes = len(raw)
        return context


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
    """A receipt of the run has to carry the identity of this run.

    The comparison of a *value* is a comparison of the type and of the
    value: a string is compared with ``==`` and not with an identity
    test, so a string that was decoded from a JSON document is equal to
    the expected literal.  A boolean is compared with its identity, so
    the number one and the string ``"true"`` are never a proof.

    The comparison of a value proves nothing about the *truth* of a
    receipt.  The admission of this platform stays refused in any case:
    see :func:`verify_native_admission`.
    """
    for key in ('run_id', 'candidate_sha'):
        if document.get(key) != getattr(context, key):
            reasons.append(label + ':BINDING_MISMATCH')
            return False
    if required is None:
        return True
    for key, expected in required.items():
        actual = document.get(key)
        if isinstance(expected, bool):
            # A boolean proof is compared with its identity: the type
            # has to be exactly ``bool`` and the value has to be the very
            # same object.
            if type(actual) is not bool or actual is not expected:
                reasons.append(label + ':PROOF_MISSING:' + key)
                return False
            continue
        if type(actual) is not str or type(expected) is not str or actual != expected:
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

    The verification of this function is a *diagnostic* and never an
    execution permission.  There is no accepted native execution backend
    on this platform, so the report is never accepted: the stable code
    ``NATIVE_EXECUTION_BACKEND_NOT_READY`` is the primary reason of every
    report, whatever the elements of the chain say.  A document that names
    a status of ``PROVEN`` and that carries the right strings is not a
    proof of a native custody, of a budget balance or of a finite grant.

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
              'verified_scope': 'SHAPE_AND_IDENTITY_OF_SEALED_DOCUMENTS_ONLY',
              'budget_authority': 'S3BudgetBindingProvider',
              'budget_binding_scope': ('SEALED_BINDING_SHAPE_ONLY_'
                                       'NOT_BALANCE_NOT_AUTHORIZATION_NOT_CUSTODY'),
              'native_execution_backend_ready': False,
              'native_execution_backend_code': NATIVE_EXECUTION_BACKEND_NOT_READY,
              'original_ledger_touched_by_this_controller': False,
              'debit_owner': 'original_ledger_authority',
              'stage_pass_claim': False,
              'product_gate0': False}
    if not isinstance(document, dict) or document.get('kind') != NATIVE_ADMISSION_KIND:
        reasons.append('ADMISSION_DOCUMENT_INVALID')
        return _close_admission_report(report, reasons)
    if set(document) != ADMISSION_KEYS:
        reasons.append('ADMISSION_KEY_SET_INVALID')
        return _close_admission_report(report, reasons)
    if document['run_id'] != context.run_id \
            or document['candidate_sha'] != context.candidate_sha \
            or document['authorization_sha256'] != context.authorization_sha256:
        reasons.append('ADMISSION_IDENTITY_MISMATCH')
        return _close_admission_report(report, reasons)
    references = document['admission_references']
    if not isinstance(references, dict) or set(references) != set(ADMISSION_REFERENCE_KEYS):
        reasons.append('ADMISSION_REFERENCE_SET_INVALID')
        return _close_admission_report(report, reasons)

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

    return _close_admission_report(report, reasons)


def _close_admission_report(report, reasons):
    """Close an admission report that can never be accepted.

    The missing native execution backend is the primary reason of every
    report, whatever the elements of the chain say.  The chain is only a
    diagnostic: it names what a future admission would have to bind, and
    it never authorises an execution.
    """
    if NATIVE_EXECUTION_BACKEND_NOT_READY not in reasons:
        reasons.append(NATIVE_EXECUTION_BACKEND_NOT_READY)
    report['accepted'] = False
    report['primary_reason'] = NATIVE_EXECUTION_BACKEND_NOT_READY
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


class SeamCancelled(RuntimeError):
    """The cooperative cancel of the offline seam."""


class _CancellableDriver:
    """The driver of the seam with a cooperative cancel boundary.

    The proxy delegates every attribute to the synthetic driver, but it
    checks the cancel event *before* every controlled call of the phase.
    The cancel is therefore checked before the next submission is
    allowed, and the worker stops on its own.

    A driver that does not cooperate - a driver that is blocked inside
    its own callback - is never killed here: a thread of this process can
    not be killed safely.  Such a driver stays retained and the run stays
    unknown; the seam reports the retention instead of pretending that the
    worker is gone.
    """

    def __init__(self, driver, cancel_event):
        self._driver = driver
        self._cancel_event = cancel_event

    def __getattr__(self, name):
        return getattr(self._driver, name)

    def _check(self):
        if self._cancel_event.is_set():
            raise SeamCancelled('SEAM_COOPERATIVE_CANCEL')

    def submit(self, graph):
        self._check()
        return self._driver.submit(graph)

    def chat_log_snapshot(self):
        self._check()
        return self._driver.chat_log_snapshot()

    def resource_observer(self):
        self._check()
        return self._driver.resource_observer()

    def owned_listener_birth(self, port):
        self._check()
        return self._driver.owned_listener_birth(port)

    def release_preload(self, binding, worker):
        self._check()
        return self._driver.release_preload(binding, worker)

    def video_snapshot_residue(self):
        self._check()
        return self._driver.video_snapshot_residue()

    def _json_request(self, *args, **kwargs):
        self._check()
        return self._driver._json_request(*args, **kwargs)


class _InProcessWorker:
    """The in-process stand in of the supervised worker.

    The worker runs in a thread of this process and speaks over real pipes.
    No operating system child process is created: the parent reads the very
    same protocol bytes from a real descriptor and the very same
    ``ParentSupervisor`` code path is used.

    The handle has no process identity of its own: ``pid`` is ``None`` and
    the birth identity of the parent therefore stays unknown, because no
    child was ever created.

    The thread is not a daemon.  The lifecycle of the worker is the
    cooperative cancel and the join, and never the daemon flag: a daemon
    thread is not an exit proof.
    """

    def __init__(self, command, *, driver_factory, context_sha256, fault,
                 cancel_event=None):
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
        self._cancel_event = cancel_event if cancel_event is not None else threading.Event()
        self._thread = threading.Thread(target=self._run, name='s3-composition-worker',
                                        daemon=False)
        self._thread.start()

    # -- the process like surface of the parent --------------------------
    def poll(self):
        if self._finished.is_set():
            return self._exit_code
        return None

    def terminate(self):
        """The cooperative cancel of the worker.

        A thread of this process can not be terminated like a child
        process.  The only safe request is the cooperative one: the
        standard input of the worker is closed and the worker stops on
        its own.  The method reports that the request was made and never
        that the worker is gone.
        """
        self._cancel_event.set()
        try:
            self.stdin.close()
        except OSError:  # pragma: no cover - the close may race
            pass
        return True

    def kill(self):
        """A thread of this process can not be killed.

        The refusal is explicit, so the parent records a failed kill
        instead of a successful one.
        """
        raise OSError('LVW_S3_THREAD_CANNOT_BE_KILLED')

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

    def _command_context_hash(self):
        """The pre-sealed hash of the worker context, as the command carries it.

        The expected hash is never computed here: it is taken from the
        command that the controller built from the sealed reference, so
        the worker can not replace the expectation with its own
        recomputation.
        """
        arguments = self.command
        for index, item in enumerate(arguments):
            if item == '--context-sha256' and index + 1 < len(arguments):
                return arguments[index + 1]
        raise ControllerError('CONTROLLER_COMMAND_WITHOUT_CONTEXT_HASH')

    def _run(self):
        code = 0
        try:
            expected = self._command_context_hash()
            if self._context_sha256 is not None and expected != self._context_sha256:
                # The command does not carry the pre-sealed hash of the
                # seam: the worker refuses before it touches anything.
                raise ControllerError('CONTROLLER_CONTEXT_HASH_MISMATCH')
            if self._fault == 'context_seal_mismatch':
                # The worker refuses the context on its own seal check.
                expected = 'f' * 64
            context = WorkerContext.load(self._context_path(), expected_sha256=expected)
            driver = self._driver_factory(context)
            driver = _CancellableDriver(driver, self._cancel_event)
            argv = ['--context', self._context_path(), '--context-sha256', expected]
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
                                     expected_sha256=self._command_context_hash())
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

    The seam owns the *lifecycle* of the worker thread.  The cancel is a
    cooperative request that is checked before every controlled call of the
    phase, and the thread is joined when it ends.  A worker that does not
    cooperate can not be killed: it stays retained, the seam reports the
    retention, and the run stays unknown.
    """

    synthetic = True

    def __init__(self, *, driver_factory, context_sha256=None, clock=None, sleep=None,
                 fault='none', label='offline-synthetic-composition',
                 worker_wait_timeout=5.0):
        if not callable(driver_factory):
            raise ControllerError('CONTROLLER_SEAM_DRIVER_FACTORY_REQUIRED')
        self.driver_factory = driver_factory
        self.context_sha256 = context_sha256
        self.clock = clock
        self.sleep = sleep
        self.fault = fault
        self.label = label
        self.worker_wait_timeout = worker_wait_timeout
        self.spawns = 0
        self.worker_exit_code = None
        self.worker_thread_finished = False
        self.worker_thread_retained = False
        self.cooperative_cancel_requested = False
        self.cooperative_cancel_observed = False
        self.faults_applied = []
        self.on_transition = None
        self._cancel_event = threading.Event()

    def spawn(self, command):
        """The synthetic spawner: a thread and two real pipes."""
        self.spawns += 1
        worker = _InProcessWorker(command, driver_factory=self.driver_factory,
                                  context_sha256=self.context_sha256,
                                  fault=self.fault, cancel_event=self._cancel_event)
        self._worker = worker
        return worker

    def cancel(self):
        """The cooperative cancel of the worker.

        The request is checked before every controlled call of the phase,
        so the worker stops before its next submission.  It is a request
        and not a proof that the worker is gone.
        """
        self.cooperative_cancel_requested = True
        self._cancel_event.set()
        worker = getattr(self, '_worker', None)
        if worker is not None:
            try:
                worker.stdin.close()
            except OSError:  # pragma: no cover - the close may race
                pass
        return True

    def wait_for_worker(self, timeout=None):
        """Wait for the worker thread and return its exit code.

        The wait is bounded.  A thread that is still running after the
        bound is reported as *not finished* and as *retained*: the run
        never claims that the worker is gone.
        """
        worker = getattr(self, '_worker', None)
        if worker is None:
            return None
        if timeout is None:
            timeout = self.worker_wait_timeout
        worker._finished.wait(timeout)
        self.worker_thread_finished = worker._finished.is_set()
        self.worker_exit_code = worker._exit_code
        self.worker_thread_retained = not self.worker_thread_finished
        self.cooperative_cancel_observed = self._cancel_event.is_set()
        return self.worker_exit_code

    def release_and_join(self, timeout=30.0):
        """The bounded, cooperative end of the worker thread.

        The cancel is requested, the thread is joined and the result is
        reported honestly.  A thread that does not end inside the bound is
        *retained*: it is not killed and it is not forgotten.
        """
        worker = getattr(self, '_worker', None)
        if worker is None:
            return True
        if not worker._finished.is_set():
            self.cancel()
        worker._thread.join(timeout)
        self.worker_thread_finished = worker._finished.is_set()
        self.worker_thread_retained = not self.worker_thread_finished
        self.worker_exit_code = worker._exit_code
        return self.worker_thread_finished

    def close(self):
        """Close every descriptor that the seam owns."""
        worker = getattr(self, '_worker', None)
        if worker is not None:
            worker.close_pipes()

    def lifecycle(self):
        """The honest lifecycle facts of the worker thread."""
        worker = getattr(self, '_worker', None)
        alive = bool(worker is not None and worker._thread.is_alive())
        return {
            'worker_thread_alive': alive,
            'worker_thread_finished': bool(self.worker_thread_finished),
            'worker_thread_retained': bool(self.worker_thread_retained or alive),
            'worker_thread_killable': False,
            'cooperative_cancel_requested': bool(self.cooperative_cancel_requested),
            'cooperative_cancel_observed': bool(self.cooperative_cancel_observed),
            'late_write_after_return_is_possible': alive,
            'lifecycle_owner': 'offline_seam',
        }


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
        self.composition_facts = []
        self.summary = None
        self.spawn_attempts = 0
        self.refusals = []
        self.unknown_reason = None
        self.reservation = None
        self.reservation_acquired = False
        self.summary_path = None
        self.summary_sha256 = None
        self.receipt_path = None
        self.receipt_persisted = False
        self.receipt_persistence_error = None
        self.consumption_reverified = False
        self.consumption_reverification = None
        self.canonical_bytes = None
        self.canonical_digest = None
        self.source_plan_bytes = None
        self.source_plan_digest = None
        # The bound identity of the root and of the output directory.  The
        # descriptors are opened once, at the precheck, and they are held
        # for the whole run: every write of the run happens through the
        # descriptor of the directory that was verified, and the identity
        # of the root, of its ancestors and of the output directory is
        # verified again before every write.
        self._root_descriptor = None
        self._root_chain = None
        self._root_identity = None
        self._controller_descriptor = None
        self._controller_chain = None

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
        # The bound identity of the root is established here, before any
        # artefact of the run is written.  The root is opened level by
        # level from the file system root, so an ancestor of the root that
        # is a link is refused here, and the observed identity of every
        # level is held for the whole run.
        self._bind_root_identity()
        # The fixed production command carries the *pre-sealed* hash of the
        # worker context down to the worker.  The worker never recomputes
        # the expectation itself: it verifies every load against the hash
        # that this command carries.
        self.command = build_production_command(worker_reference['path'],
                                                context_sha256=worker_reference['sha256'])

    # -- the bound identity of the root and of the output directory ---------
    def _bind_root_identity(self):
        """Open the bound root and hold the identity of its whole chain.

        The root is opened from the file system root, level by level, and
        every level is opened without following a link.  The observed
        identity of every level is held, so a root or an ancestor that was
        replaced after this moment is refused before any write of the run.
        """
        try:
            descriptor, chain = open_root_directory_chain(self.context.root)
        except ControllerIOError as error:
            raise ControllerError('CONTROLLER_' + error.code) from error
        self._root_descriptor = descriptor
        self._root_chain = chain
        self._root_identity = (chain[-1]['device'], chain[-1]['inode'])

    def _verify_root_identity(self):
        """Verify that the root still names the object that was observed."""
        if self._root_chain is None:
            raise ControllerError('CONTROLLER_ROOT_NOT_BOUND')
        try:
            verify_directory_chain(self._root_chain)
        except ControllerIOError as error:
            raise ControllerError('CONTROLLER_ROOT_IDENTITY_CHANGED:' + error.code) from error
        return True

    def _controller_directory_descriptor(self):
        """The descriptor of the output directory of this controller.

        The directory is created once, relative to the descriptor of the
        bound root, and the descriptor is held for the whole run: every
        artefact of the controller is written through the descriptor of the
        directory that was verified, never through a path that was opened
        again.  The identity of every level of the chain is recorded, so a
        directory that was replaced after its creation is refused.
        """
        if self._controller_descriptor is None:
            if self._root_descriptor is None:
                raise ControllerError('CONTROLLER_ROOT_NOT_BOUND')
            try:
                descriptor = ensure_directory_chain(self._root_descriptor,
                                                    CONTROLLER_DIRECTORY_PARTS)
            except ControllerIOError as error:
                raise ControllerError('CONTROLLER_' + error.code) from error
            self._controller_descriptor = descriptor
            self._controller_chain = self._observe_controller_chain()
        return self._controller_descriptor

    def _observe_controller_chain(self):
        """The observed identity of every level of the output directory."""
        chain = []
        walked = Path(self.context.root)
        for part in CONTROLLER_DIRECTORY_PARTS:
            walked = walked / part
            try:
                info = os.lstat(str(walked))
            except OSError as error:
                raise ControllerError('CONTROLLER_DIRECTORY_UNUSABLE:'
                                      + errno_name(error)) from error
            chain.append({'path': str(walked),
                          'identity': (int(info.st_dev), int(info.st_ino))})
        return chain

    def _verify_controller_identity(self):
        """Verify the root, its ancestors and the output directory.

        Every write of the run is bound to the identity that was observed
        at the precheck: a root that was replaced, a ``temp`` directory
        that was replaced, an output directory that was replaced and a
        symlinked ancestor of the root are all refused, and nothing is
        written into a new root or outside of the bound root.
        """
        self._verify_root_identity()
        if self._controller_chain is None:
            return True
        for entry in self._controller_chain:
            try:
                verify_directory_identity(entry['path'], entry['identity'])
            except ControllerIOError as error:
                raise ControllerError('CONTROLLER_DIRECTORY_IDENTITY_CHANGED:'
                                      + error.code) from error
        return True

    def _release_anchors(self):
        """Close the descriptors that this run held.

        The descriptors of the bound root and of the output directory are
        the only descriptors that this controller keeps open between two
        steps.  They are closed at the end of the run, and the receipt
        names them, so the difference of the two descriptor snapshots
        stays exact.
        """
        for attribute in ('_controller_descriptor', '_root_descriptor'):
            descriptor = getattr(self, attribute, None)
            if descriptor is None:
                continue
            setattr(self, attribute, None)
            try:
                os.close(descriptor)
            except OSError:  # pragma: no cover - the close may race
                pass

    def _record_post_release_cleanup(self, receipt, fd_before):
        """The descriptor accounting after this run released its own descriptors.

        This is a *second* observation point.  The receipt that was
        persisted carries the snapshot of the end of the run body
        (``PRE_RELEASE``); this one carries the snapshot after the run
        released the descriptors it held (``POST_RELEASE``).  The
        persisted receipt is never rewritten, and the copy on the disk is
        never claimed to carry this snapshot.
        """
        snapshot = _fd_snapshot()
        leaked = None
        if fd_before is not None and snapshot is not None:
            leaked = sorted(set(snapshot['open']) - set(fd_before['open']))
        receipt['fd_cleanup_post_release'] = {
            'observation_point': 'POST_RELEASE: the snapshot is taken after this run '
                                 'released the descriptors that it held',
            'snapshot': snapshot,
            'fd_leaked': leaked,
            'the_persisted_receipt_carries': 'PRE_RELEASE',
            'stage_pass_claim': False,
            'product_gate0': False,
        }

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
                'verified_scope': 'SHAPE_AND_IDENTITY_OF_SEALED_DOCUMENTS_ONLY',
                'primary_reason': reason,
                'budget_authority': 'S3BudgetBindingProvider',
                'budget_binding_scope': ('SEALED_BINDING_SHAPE_ONLY_'
                                         'NOT_BALANCE_NOT_AUTHORIZATION_NOT_CUSTODY'),
                'native_execution_backend_ready': False,
                'native_execution_backend_code': NATIVE_EXECUTION_BACKEND_NOT_READY,
                'original_ledger_touched_by_this_controller': False,
                'debit_owner': 'original_ledger_authority',
                'stage_pass_claim': False,
                'product_gate0': False}

    # -- the execution right of this run -----------------------------------
    def _acquire_reservation(self):
        """Take the exclusive execution right of this run.

        The reservation is taken *after* the precheck and *before* any
        worker is sent.  It is an exclusive creation inside the bound
        root, so a second run of the same run id finds the reservation of
        the first one and refuses instead of sending the sixteen rows a
        second time.  An existing summary of the same run is a terminal
        state as well and is refused before the reservation is taken.

        The reservation is never deleted here.  A failed or unknown run
        keeps its reservation, so the history of the run stays visible and
        a retry can not silently replace it.

        The reservation is written through the descriptor of the output
        directory that was created inside the bound root, and the identity
        of the root and of the output directory is verified before the
        write: a root that was replaced after the precheck is refused and
        the reservation is never written into the new root.
        """
        self._verify_root_identity()
        directory = self._controller_directory_descriptor()
        self._verify_controller_identity()
        summary_name = 'summary-' + self.context.run_id + '.json'
        if exists_at(directory, summary_name):
            raise ControllerError('CONTROLLER_SUMMARY_ALREADY_EXISTS')
        name = 'reservation-' + self.context.run_id + '.json'
        document = canonical_json({
            'kind': RESERVATION_KIND,
            'run_id': self.context.run_id,
            'candidate_sha': self.context.candidate_sha,
            'authorization_sha256': self.context.authorization_sha256,
            'root': str(self.context.root),
            'reserved_wall': time.time(),
            'stage_pass_claim': False,
            'product_gate0': False,
        }).encode('utf-8')
        try:
            write_exclusive_at(directory, name, document)
        except ControllerIOError as error:
            if error.code == 'OUTPUT_ALREADY_EXISTS':
                raise ControllerError('CONTROLLER_RESERVATION_ALREADY_EXISTS') from error
            raise ControllerError('CONTROLLER_RESERVATION_UNWRITABLE:' + error.code) from error
        self.reservation = name
        self.reservation_acquired = True
        return self.reservation

    # -- the plan -----------------------------------------------------------
    def _seal_plan(self):
        evidence = ParentOriginalEvidence(
            run_id=self.context.run_id,
            candidate_sha=self.context.candidate_sha,
            child_sha256=self.context.authorization_sha256,
            root=self.context.root,
            projection_sha256=self.projection_sha256)
        self.plan_sha256 = evidence.seal_plan(self.rows)
        # The root that is sealed is the root that was bound at the
        # precheck, not the object that the path of the root happens to
        # name now.  A root that was replaced after the precheck is
        # therefore detected by the consumption boundary of the parent.
        evidence.seal_root([self._root_identity[0], self._root_identity[1]])
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
        self.spawn_attempts = 0
        supervisor = ParentSupervisor(**kwargs)
        self.supervisor = supervisor
        try:
            self.evidence = supervisor.run()
        except SupervisionError as error:
            raise ControllerError('CONTROLLER_SUPERVISION_REFUSED:' + error.code) from error
        finally:
            if seam is not None:
                seam.wait_for_worker()
                # The number of the sends of this run is the number of the
                # workers that the seam really started.  It is never a
                # promise and never a guess.
                self.spawn_attempts = seam.spawns
        return self.evidence

    # -- the originals ------------------------------------------------------
    def _read_bound_reference(self, relative):
        """Read one root relative reference through the bound root.

        The reference is read through the descriptor of the root that was
        bound at the precheck, so the bytes come from the very object that
        this run bound and never from a root that was opened again.
        """
        try:
            return read_bounded_in_root_at(self._root_descriptor, relative)
        except ControllerIOError as error:
            raise ControllerError('CONTROLLER_' + error.code) from error

    def _verify_originals(self):
        evidence = self.evidence
        if evidence.get('unknown_outcome') or not evidence.get('canonical_receipt_verified'):
            raise ControllerError('CONTROLLER_OUTCOME_UNKNOWN:' + str(evidence.get('protocol_violation')))
        reference = evidence['canonical_receipt']['reference']
        artifact_root = self.context.root / 'temp' / 's3-quality'
        # The bytes of the canonical receipt are read *once*, through the
        # bound root, and the frozen owner validates exactly these bytes.
        # The document that is adapted, scored and published is therefore
        # the document of the bytes that this controller hashes and that
        # the parent seals: an old parse of an old document can never be
        # published with the seal of a new document.
        canonical_bytes = self._read_bound_reference(reference)
        boundary = _SealedBytesBoundary(self.context.root, self._root_identity)
        boundary.add(CANONICAL_RECEIPT_NAME, canonical_bytes)
        try:
            canonical = load_published_execution_receipt(artifact_root, boundary=boundary)
        except QualityContractError as error:
            raise ControllerError('CONTROLLER_PUBLISHED_RECEIPT_REFUSED:' + str(error)) from error
        decoded = _decode_bound_bytes(canonical_bytes, 'CANONICAL')
        if not _same_document(canonical, decoded):
            # The owner returned a document that is not the document of the
            # bytes that this controller consumed: the run is refused and
            # nothing is published.
            raise ControllerError('CONTROLLER_CANONICAL_PARSE_NOT_BOUND_TO_BYTES')
        if canonical.get('run_id') != self.context.run_id \
                or canonical.get('candidate_sha') != self.context.candidate_sha \
                or canonical.get('authorization_sha256') != self.context.authorization_sha256:
            raise ControllerError('CONTROLLER_CANONICAL_IDENTITY_MISMATCH')
        if canonical.get('projection_sha256') != self.projection_sha256:
            raise ControllerError('CONTROLLER_CANONICAL_PROJECTION_MISMATCH')
        self.canonical = canonical
        raw = self._raw_references(canonical)
        source_plan_name = str((canonical.get('source_plan') or {}).get('path') or '')
        if (not source_plan_name or os.path.isabs(source_plan_name)
                or '..' in Path(source_plan_name).parts):
            raise ControllerError('CONTROLLER_SOURCE_PLAN_REFERENCE_INVALID')
        source_plan_reference = 'temp/s3-quality/' + source_plan_name
        # The bytes of the source plan are read once as well and the frozen
        # owner validates exactly these bytes.
        source_plan_bytes = self._read_bound_reference(source_plan_reference)
        boundary.add(source_plan_name, source_plan_bytes)
        try:
            source_plan = load_source_plan(artifact_root, canonical, boundary=boundary)
        except QualityContractError as error:
            raise ControllerError('CONTROLLER_PUBLISHED_RECEIPT_REFUSED:' + str(error)) from error
        decoded_plan = _decode_bound_bytes(source_plan_bytes, 'SOURCE_PLAN')
        if not _same_document(source_plan, decoded_plan.get('rows')):
            raise ControllerError('CONTROLLER_SOURCE_PLAN_PARSE_NOT_BOUND_TO_BYTES')
        self.source_plan = source_plan
        self.canonical_bytes = canonical_bytes
        self.canonical_digest = sha256_bytes(canonical_bytes)
        self.source_plan_bytes = source_plan_bytes
        self.source_plan_digest = sha256_bytes(source_plan_bytes)
        try:
            self.original_evidence.seal_originals(canonical=reference,
                                                  source_plan=source_plan_reference,
                                                  raw=raw)
            self.manifest = self.original_evidence.manifest()
        except S3IntegrationError as error:
            raise ControllerError('CONTROLLER_ORIGINALS_REFUSED:' + error.reason) from error
        sealed_canonical = self.manifest['originals']['canonical'][0]
        sealed_source_plan = self.manifest['originals']['source_plan'][0]
        if sealed_canonical['sha256'] != self.canonical_digest \
                or sealed_source_plan['sha256'] != self.source_plan_digest:
            # The owner sealed a different content than the content that
            # this controller consumed: the run is refused, never repaired.
            raise ControllerError('CONTROLLER_ORIGINALS_CHANGED_BEFORE_SEAL')
        # The consumption boundary of the originals: the parent re-reads
        # every sealed original through its own verified handle right after
        # the seal, so an original that changed inside the seal window is
        # refused here.
        return self._reverify_consumption_boundary()

    def _reverify_consumption_boundary(self):
        """Re-verify the root, the manifest and the originals before the write.

        The manifest is the consumption boundary of the originals.  The
        parent re-reads every sealed original through its own verified
        handle right before the summary is built, so an original that
        changed after the first verification is refused here and the run
        stays unknown.  The boundary is the last real observation of the
        originals: it is not a promise about a later change and it is not
        an atomic snapshot of a batch.
        """
        try:
            manifest = self.original_evidence.manifest()
        except S3IntegrationError as error:
            raise ControllerError('CONTROLLER_ORIGINALS_CHANGED_AT_CONSUMPTION:'
                                  + error.reason) from error
        self.manifest = manifest
        self.consumption_reverified = True
        self.consumption_reverification = manifest.get('reverification')
        return manifest

    @staticmethod
    def _raw_references(canonical):
        """The root relative references of the raw artefacts of the run."""
        return ProductionController._artefact_references(canonical.get('rows', []))

    # -- the receipts -------------------------------------------------------
    def _bind_receipts(self):
        """The aggregate receipts of this run, derived from the run facts.

        A receipt is derived only from a fact of this run, and it is only
        a pass when the *complete* obligation of that receipt is proven by
        the machine evidence of this run.  The existence of a file and a
        count that is not ``None`` are never a proof: a receipt whose
        evidence is incomplete is a failure, and a receipt whose truth
        belongs to the native or the product side stays unproven and is
        never filled with a promise.

        The outer status of the run never hides an inner fact: an inner
        receipt that failed is a failure here, whatever the outer state
        of the run is.
        """
        canonical = self.canonical
        receipts = {}
        rows = canonical.get('rows', [])
        total = len(rows)
        passed = [row for row in rows if row.get('execution_status') == 'PASS']
        all_passed = total == 16 and len(passed) == total
        counts = canonical.get('test_counts') or {}
        phase_pass = counts.get('PASS')
        phase_fail = counts.get('FAIL')
        images = [row for row in rows if row.get('media_kind') == 'image']
        videos = [row for row in rows if row.get('media_kind') == 'video']
        provenance = self._provenance()

        def make(name, status, reason, sources, obligation=None):
            document = {'kind': AGGREGATE_RECEIPT_KIND,
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
            if obligation is not None:
                document['obligation'] = obligation
            return document

        # -- the artefacts of the run ---------------------------------------
        artefact_references = self._artefact_references(rows)
        sealed_raw = {}
        if self.manifest:
            sealed_raw = {entry['reference']: entry['sha256']
                          for entry in self.manifest['originals']['raw']}
        unique_artefacts = len(set(artefact_references)) == len(artefact_references)
        inside_phase = all(reference.startswith('temp/s3-quality/')
                           for reference in artefact_references)
        covered_by_manifest = bool(artefact_references) \
            and set(artefact_references) <= set(sealed_raw)
        # The digest that the parent sealed for every artefact and the
        # digest that the row claims for it have to be the same.  The
        # artefacts of the run are therefore the bytes that the parent
        # re-verified, and not only the names that the phase wrote.
        digests_agree = bool(rows)
        for row in rows:
            if not isinstance(row, dict):
                digests_agree = False
                continue
            for artefact_key, digest_key in ROW_ARTEFACT_DIGEST_KEYS:
                artefact = row.get(artefact_key)
                claimed = row.get(digest_key)
                if not isinstance(artefact, str) or not artefact:
                    continue
                reference = 'temp/s3-quality/' + artefact
                if sealed_raw.get(reference) != claimed:
                    digests_agree = False
        ownership = canonical.get('ownership_assurance') or {}
        exclusive_single_write = ownership.get('exclusive_single_write') is True
        descriptor_relative_writes = ownership.get('descriptor_relative_writes') is True
        outputs = [row for row in rows
                   if row.get('raw_artifact') and row.get('suggestion_artifact')]
        reserved = canonical.get('provider_calls_reserved')
        capacity = canonical.get('parent_budget_capacity')
        budget_accounted = (type(reserved) is int and reserved >= 0
                            and type(capacity) is int and reserved <= capacity
                            and phase_fail in (0, None))

        receipts['stage_binding'] = make(
            'stage_binding', 'PASS',
            'THE_SEALED_BINDING_AND_THE_IDENTITY_OF_THIS_RUN_WERE_VERIFIED',
            [{'source': 'controller_context', 'sha256': provenance['controller_context']['sha256']},
             {'source': 'worker_context', 'sha256': self.context.document['worker_context']['sha256']},
             {'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}],
            'THE_IDENTITY_OF_THIS_RUN_MATCHES_EVERY_SEALED_DOCUMENT')
        receipts['image_input'] = make(
            'image_input', 'PASS' if all_passed and images else 'FAIL',
            'THE_IMAGE_ROWS_OF_THIS_RUN_WERE_EXECUTED_WITH_THEIR_SEALED_SOURCE_IDENTITY',
            [{'source': 'source_plan', 'sha256': provenance['source_plan']['sha256']},
             {'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}],
            'EVERY_IMAGE_ROW_OF_THIS_RUN_EXECUTED_AND_PUBLISHED')
        receipts['video_input'] = make(
            'video_input', 'PASS' if all_passed and videos else 'FAIL',
            'THE_VIDEO_ROWS_OF_THIS_RUN_WERE_EXECUTED_WITH_THEIR_SEALED_SOURCE_IDENTITY',
            [{'source': 'source_plan', 'sha256': provenance['source_plan']['sha256']},
             {'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}],
            'EVERY_VIDEO_ROW_OF_THIS_RUN_EXECUTED_AND_PUBLISHED')
        receipts['output_contract'] = self._formal_receipt(
            make, 'output_contract',
            all_passed and len(outputs) == total and total == 16
            and covered_by_manifest and digests_agree,
            'THE_SIXTEEN_ROWS_DID_NOT_PUBLISH_BOTH_ARTEFACTS_WITH_THEIR_SEALED_DIGESTS',
            [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']},
             {'source': 'parent_manifest', 'sha256': provenance['manifest']['sha256']}])
        receipts['no_overwrite'] = self._formal_receipt(
            make, 'no_overwrite',
            all_passed and exclusive_single_write and descriptor_relative_writes
            and unique_artefacts and inside_phase and covered_by_manifest
            and digests_agree,
            'THE_ARTEFACTS_OF_THIS_RUN_WERE_NOT_CREATED_EXCLUSIVELY_INSIDE_THE_OWNED_PHASE_DIRECTORY',
            [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']},
             {'source': 'parent_manifest', 'sha256': provenance['manifest']['sha256']}])
        receipts['file_safety'] = make(
            'file_safety',
            'PASS' if self.manifest and self.consumption_reverified
            and (self.manifest.get('reverification') or {}).get('verified') is True else 'FAIL',
            'THE_PARENT_REVERIFIED_EVERY_ORIGINAL_THROUGH_THE_NO_FOLLOW_PROCEDURE',
            [{'source': 'parent_manifest', 'sha256': provenance['manifest']['sha256']}],
            'EVERY_ORIGINAL_WAS_REVERIFIED_AT_THE_CONSUMPTION_BOUNDARY')
        receipts['resource_budget'] = self._formal_receipt(
            make, 'resource_budget', all_passed and budget_accounted,
            'THE_PROVIDER_CALL_BUDGET_OF_THIS_RUN_WAS_NOT_FULLY_ACCOUNTED_BY_THE_PHASE',
            [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']}])
        receipts['quality_16_rows'] = make(
            'quality_16_rows',
            'PASS' if phase_pass == 16 and counts.get('fixed') == 16 and total == 16 else 'FAIL',
            'THE_SIXTEEN_ROWS_OF_THIS_RUN_WERE_EXECUTED_AND_SEALED_BY_THE_PHASE_OWNER',
            [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']},
             {'source': 'source_plan', 'sha256': provenance['source_plan']['sha256']}],
            'THE_FIXED_DENOMINATOR_OF_SIXTEEN_ROWS_WAS_EXECUTED')
        for name, reason in UNPROVEN_RECEIPTS.items():
            receipts[name] = make(name, 'BLOCKED', reason, [])
        receipts['cleanup']['cleanup_proven'] = False
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
        self.composition_facts = self._composition_facts(
            outputs=outputs, total=total, covered_by_manifest=covered_by_manifest,
            digests_agree=digests_agree, exclusive_single_write=exclusive_single_write,
            descriptor_relative_writes=descriptor_relative_writes,
            unique_artefacts=unique_artefacts, inside_phase=inside_phase,
            reserved=reserved, capacity=capacity, budget_accounted=budget_accounted,
            provenance=provenance)
        self.receipts = receipts
        return receipts

    @staticmethod
    def _formal_receipt(make, name, subset_holds, failed_subcondition, sources):
        """One formal product obligation of this run.

        The obligation of a product key is the *complete* obligation of the
        product, not the subset that one synthetic run happens to observe.
        A receipt of such a name is therefore never a pass of this run:

        * a necessary sub-condition that demonstrably failed is a failure,
          and the failure names the sub-condition;
        * a run without such a failure leaves the complete obligation
          unproven, so the receipt is blocked and names what is missing.

        The facts that this run really observed are listed separately, see
        :meth:`_composition_facts`; they never fill this receipt.
        """
        formal = FORMAL_OBLIGATIONS[name]
        if not subset_holds:
            return make(name, 'FAIL',
                        'FORMAL_OBLIGATION_NOT_MET:' + failed_subcondition,
                        sources, formal['obligation'])
        return make(name, 'BLOCKED',
                    'FORMAL_OBLIGATION_NOT_PROVEN:' + formal['missing'],
                    sources, formal['obligation'])

    def _composition_facts(self, *, outputs, total, covered_by_manifest,
                           digests_agree, exclusive_single_write,
                           descriptor_relative_writes, unique_artefacts,
                           inside_phase, reserved, capacity,
                           budget_accounted, provenance):
        """The facts that this synthetic run really observed.

        These facts are *not* the formal obligations of the product keys.
        They have their own kind, their own names and their own scope and
        they are listed separately from the receipts, so a fact of a run
        can never fill a formal receipt of the same name and a narrowed
        obligation can never be published under an approved name.
        """
        sources = [{'source': 'canonical_receipt', 'sha256': provenance['canonical']['sha256']},
                   {'source': 'parent_manifest', 'sha256': provenance['manifest']['sha256']}]

        def fact(name, observed, detail):
            return {'kind': COMPOSITION_FACT_KIND,
                    'name': name,
                    'status': 'OBSERVED' if observed else 'NOT_OBSERVED',
                    'observed': bool(observed),
                    'detail': detail,
                    'run_id': self.context.run_id,
                    'candidate_sha': self.context.candidate_sha,
                    'authorization_sha256': self.context.authorization_sha256,
                    'sources': list(sources),
                    'scope': COMPOSITION_FACT_SCOPE,
                    'not_a_formal_product_obligation': True,
                    'product_pass_claimed': False,
                    'stage_pass_claim': False,
                    'product_gate0': False}

        artefacts_present = len(outputs) == total and total == 16
        exclusive_creation = (exclusive_single_write and descriptor_relative_writes
                               and unique_artefacts and inside_phase)
        return [
            fact('composition_fact_output_artifacts_present',
                 artefacts_present and covered_by_manifest and digests_agree,
                 'the rows of this run published a raw and a suggestion artefact '
                 'whose digests agree with the sealed manifest'),
            fact('composition_fact_exclusive_creation_of_this_run',
                 exclusive_creation,
                 'the artefacts of this run were created exclusively inside the '
                 'owned phase directory of this run'),
            fact('composition_fact_provider_call_accounting_of_this_run',
                 budget_accounted,
                 'the provider calls of this run were reserved inside the '
                 'accepted capacity of this run: reserved=' + str(reserved)
                 + ' capacity=' + str(capacity)),
        ]

    @staticmethod
    def _artefact_references(rows):
        """The root relative references of every artefact of the run."""
        references = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in ROW_ARTEFACT_KEYS:
                value = row.get(key)
                if isinstance(value, str) and value:
                    references.append('temp/s3-quality/' + value)
        return references

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
        """The same source chain from the context to the summary.

        Every digest of this chain comes from the *owner* of the artefact:
        the controller context from the bytes that were read and verified,
        the canonical receipt and the source plan from the sealed manifest
        of the parent, the manifest from the document of the parent.  The
        controller never reads an original a second time on its own, so
        the provenance can not contradict the manifest.
        """
        canonical_entry = self._sealed_entry('canonical')
        source_plan_entry = self._sealed_entry('source_plan')
        manifest_bytes = canonical_json(self.manifest).encode('utf-8')
        return {
            'controller_context': {'sha256': self.context.document_sha256,
                                   'bytes': self.context.document_bytes,
                                   'owner': 'controller_context'},
            'projection': {'sha256': self.projection_sha256, 'owner': 'quality_phase_projection'},
            'plan': {'sha256': self.plan_sha256, 'owner': 'ParentOriginalEvidence'},
            'worker_context': {'sha256': self.context.document['worker_context']['sha256'],
                               'owner': 'WorkerContext'},
            'canonical': {'reference': canonical_entry['reference'],
                          'sha256': canonical_entry['sha256'],
                          'bytes': canonical_entry['bytes'],
                          'owner': 'quality_phase_canonical_receipt'},
            'source_plan': {'sha256': source_plan_entry['sha256'],
                            'bytes': source_plan_entry['bytes'],
                            'owner': 'quality_phase_source_plan'},
            'manifest': {'sha256': sha256_bytes(manifest_bytes),
                         'owner': 'ParentOriginalEvidence'},
        }

    def _sealed_entry(self, category):
        """The sealed entry of one category of the manifest of the parent."""
        if not self.manifest:
            raise ControllerError('CONTROLLER_MANIFEST_MISSING')
        entries = (self.manifest.get('originals') or {}).get(category) or []
        if len(entries) != 1:
            raise ControllerError('CONTROLLER_MANIFEST_ENTRY_INVALID:' + category)
        return entries[0]

    # -- the summary --------------------------------------------------------
    def _build_summary(self):
        # The consumption boundary: the root, the manifest and every
        # original are re-verified right before the summary is built.
        self._reverify_consumption_boundary()
        receipts = dict(self.receipts)
        binding = {'run_id': self.context.run_id, 'candidate_sha': self.context.candidate_sha}
        summary = aggregate_twelve_keys(receipts=receipts, binding=binding)
        summary['kind'] = SUMMARY_KIND
        summary['provenance'] = self._provenance()
        # The facts of this run are listed separately from the receipts of
        # the twelve keys: they are observations of a synthetic run and
        # they never fill a formal obligation of a product key.
        summary['composition_facts'] = list(self.composition_facts)
        summary['composition_facts_are_not_product_receipts'] = True
        summary['execution_mode'] = 'OFFLINE_SYNTHETIC_COMPOSITION' if self.seam is not None \
            else 'NATIVE'
        summary['offline_receipts_are_not_product_receipts'] = True
        summary['synthetic_fixtures_count_as_product_pass'] = False
        summary['old_s2_nine_keys_accepted_as_green'] = False
        summary['stage_pass_claim'] = False
        summary['product_gate0'] = False
        summary['real_execution_performed'] = False
        summary['native_execution_backend_ready'] = False
        summary['native_execution_backend_code'] = NATIVE_EXECUTION_BACKEND_NOT_READY
        return summary

    def _persist_summary(self):
        """Write the summary exactly once, inside the bound root.

        The write happens through the descriptor of the output directory
        that was created inside the bound root, and the identity of the
        root, of its ancestors and of the output directory is verified
        before the write.  The leaf is created with ``O_EXCL``, so a
        summary is never written outside the root and an existing summary
        is never replaced.
        """
        directory = self._controller_directory_descriptor()
        self._verify_controller_identity()
        name = 'summary-' + self.context.run_id + '.json'
        summary_bytes = canonical_json(self.summary).encode('utf-8')
        try:
            write_exclusive_at(directory, name, summary_bytes)
        except ControllerIOError as error:
            raise ControllerError('CONTROLLER_SUMMARY_' + error.code) from error
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            # A storage failure that is not an operating system error is an
            # ordinary exception of the run: it is named, it is never
            # swallowed and it never escapes the run as a generic text.
            raise ControllerError('CONTROLLER_SUMMARY_PERSISTENCE_FAILED:'
                                  + type(error).__name__) from error
        self.summary_path = self.context.root.joinpath(*CONTROLLER_DIRECTORY_PARTS) / name
        self.summary_sha256 = sha256_bytes(summary_bytes)
        return self.summary_path

    def _persist_receipt(self, receipt):
        """Write the receipt of this run exactly once, inside the bound root.

        The receipt is written when the run took its execution right, so a
        refused run that never sent a worker leaves no artefact in the
        root.  A receipt that can not be written is reported as *not
        persisted*: the failure is never hidden behind a success.

        Every ordinary failure of this write - an operating system error,
        a refused identity and a storage error that is not an operating
        system error - is caught here and is reported as a not persisted
        receipt.  The failure of the write never escapes the run, so the
        caller always receives the structured state of the run.
        """
        if not self.reservation_acquired:
            self.receipt_persisted = False
            self.receipt_persistence_error = 'CONTROLLER_RECEIPT_NOT_APPLICABLE_NO_RESERVATION'
            return False
        receipt['receipt_persistence_intent'] = 'WRITTEN_WITH_O_EXCL'
        try:
            directory = self._controller_directory_descriptor()
            self._verify_controller_identity()
            name = 'receipt-' + self.context.run_id + '.json'
            raw = canonical_json(receipt).encode('utf-8')
            write_exclusive_at(directory, name, raw)
            self.receipt_path = self.context.root.joinpath(*CONTROLLER_DIRECTORY_PARTS) / name
            self.receipt_sha256 = sha256_bytes(raw)
            self.receipt_persisted = True
            self.receipt_persistence_error = None
            return True
        except ControllerIOError as error:
            self.receipt_persisted = False
            self.receipt_persistence_error = 'CONTROLLER_RECEIPT_' + error.code
            return False
        except ControllerError as error:
            self.receipt_persisted = False
            self.receipt_persistence_error = error.code
            return False
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            # The persistence of the terminal receipt failed with an
            # ordinary exception.  The failure is named, the receipt stays
            # *not persisted* and the run keeps its unknown state.
            self.receipt_persisted = False
            self.receipt_persistence_error = ('CONTROLLER_RECEIPT_PERSISTENCE_FAILED:'
                                              + type(error).__name__)
            return False

    @staticmethod
    def _write_exclusive(path, raw):
        """Write one explicit output file exactly once.

        The file is never replaced.  This is the output of an explicit
        entry point of a trusted local caller; every artefact of the run
        itself is written inside the bound root.
        """
        try:
            write_exclusive_path(path, raw)
        except ControllerIOError as error:
            raise ControllerError('CONTROLLER_' + error.code) from error

    # -- the run ------------------------------------------------------------
    def run(self):
        """Run the composition and return the controller receipt.

        Every ordinary exception of the run ends in a *persisted unknown*:
        the receipt keeps the state of the run, the reservation is kept,
        the partial evidence is kept and the descriptors of this run are
        closed in a bounded way.  A cancellation - ``KeyboardInterrupt``
        or ``SystemExit`` - is never swallowed: it is re-raised after the
        bounded cleanup.
        """
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
                   'native_execution_backend_ready': False,
                   'native_execution_backend_code': NATIVE_EXECUTION_BACKEND_NOT_READY,
                   'started_wall': started}
        try:
            try:
                self._precheck()
                receipt['admission'] = self._admission_report()
                if self.seam is None:
                    # There is no accepted native execution backend on this
                    # platform.  The native path refuses here, before any
                    # spawn and before any native driver is constructed, and
                    # the refusal has the same stable code on the worker
                    # side.
                    raise ControllerError('CONTROLLER_' + NATIVE_EXECUTION_BACKEND_NOT_READY)
                self._enter(STATE_PRECHECK)
                # The exclusive execution right of this run is taken before
                # any worker is sent.
                self._acquire_reservation()
                receipt['reservation'] = self.reservation
                self._seal_plan()
                self._enter(STATE_PLAN_SEALED)
                receipt['command'] = list(self.command)
                receipt['plan'] = {'rows': 16, 'plan_sha256': self.plan_sha256,
                                   'projection_sha256': self.projection_sha256}
                self._supervise()
                self._enter(STATE_WORKER_SUPERVISED)
                receipt['supervision'] = self.evidence
                receipt['spawn_attempts'] = self.spawn_attempts
                if self.evidence.get('unknown_outcome') \
                        or not self.evidence.get('canonical_receipt_verified'):
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
                    return receipt
                self._verify_originals()
                self._enter(STATE_ORIGINALS_VERIFIED)
                receipt['manifest'] = self.manifest
                self._bind_receipts()
                self._enter(STATE_RECEIPTS_BOUND)
                receipt['receipts'] = self.receipts
                receipt['residue_observations'] = self.residue_observations
                self.summary = self._build_summary()
                receipt['summary'] = self.summary
                receipt['consumption_reverified'] = self.consumption_reverified
                self._persist_summary()
                self._enter(STATE_SUMMARY_PERSISTED)
                receipt['state'] = STATE_SUMMARY_PERSISTED
                receipt['summary_persisted'] = True
                receipt['summary_path'] = str(self.summary_path)
                receipt['summary_sha256'] = self.summary_sha256
                # The root and the reservation are retained whenever the
                # cleanup of the product is not proven.  The exit of the
                # worker proves the worker and never the cleanup of a
                # native service that was never started here.
                receipt['cleanup_proven'] = False
                receipt['root_retained'] = True
                receipt['reservation_retained'] = True
                receipt['root_retained_reason'] = 'PRODUCT_CLEANUP_NOT_PROVEN'
                receipt['refund_allowed'] = False
                receipt['resend_allowed'] = False
            except ControllerError as error:
                receipt['refusals'].append(error.code)
                # A refusal that happened before any worker was sent is a
                # refusal of the run, not an unknown outcome: nothing was
                # started and nothing can arrive late.
                receipt['state'] = STATE_REFUSED if self.spawn_attempts == 0 else STATE_UNKNOWN
                receipt['summary_persisted'] = False
                receipt['cleanup_proven'] = False
                receipt['root_retained'] = True
                receipt['reservation_retained'] = True
                receipt['refund_allowed'] = False
                receipt['resend_allowed'] = False
                receipt['archive_allowed'] = False
                receipt['unknown_reason'] = error.code
                if self.state is not None and self.state != STATE_PRECHECK:
                    receipt['recovery'] = self._recovery_entry()
            except Exception as error:  # noqa: BLE001 - the failure stays visible
                # An ordinary exception of the run is an unknown outcome of
                # the run, never a success and never a silent exit.
                code = 'CONTROLLER_UNEXPECTED_EXCEPTION:' + type(error).__name__
                receipt['refusals'].append(code)
                receipt['state'] = STATE_UNKNOWN
                receipt['summary_persisted'] = False
                receipt['cleanup_proven'] = False
                receipt['root_retained'] = True
                receipt['reservation_retained'] = True
                receipt['refund_allowed'] = False
                receipt['resend_allowed'] = False
                receipt['archive_allowed'] = False
                receipt['unknown_reason'] = code
                receipt['exception_detail'] = repr(error)[:400]
                if self.state is not None and self.state != STATE_PRECHECK:
                    receipt['recovery'] = self._recovery_entry()
            finally:
                # The bounded end of the run.  Neither the cleanup nor the
                # persistence of the terminal receipt may escape the run as
                # an exception: a run that failed stays a structured run
                # with a named reason, a retained root, a retained
                # reservation and an explicit *not persisted* receipt.
                try:
                    self._finish(receipt, fd_before)
                except Exception as error:  # noqa: BLE001 - the cleanup stays bounded
                    receipt.setdefault('cleanup_failures', []).append(
                        'FINISH:' + type(error).__name__)
                try:
                    self._persist_receipt(receipt)
                except Exception as error:  # noqa: BLE001 - the persistence stays bounded
                    self.receipt_persisted = False
                    self.receipt_persistence_error = ('CONTROLLER_RECEIPT_PERSISTENCE_FAILED:'
                                                      + type(error).__name__)
                receipt['receipt_persisted'] = self.receipt_persisted
                receipt['receipt_persistence_error'] = self.receipt_persistence_error
                receipt['receipt_path'] = str(self.receipt_path) if self.receipt_path else None
                receipt['composition_facts'] = list(self.composition_facts)
                self._release_anchors()
                # The second observation point of the descriptor accounting:
                # it is taken after this run released its own descriptors
                # and it is *not* written into the persisted receipt.
                self._record_post_release_cleanup(receipt, fd_before)
        except (KeyboardInterrupt, SystemExit):
            # A cancellation is never swallowed and never turned into a
            # success.  The bounded cleanup already happened in the inner
            # ``finally``.
            raise
        return receipt

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
        """The bounded end of the run.

        The descriptors of this run are closed here and the facts of the
        cleanup are recorded here.  A worker thread that did not end is
        *retained* and reported as retained: the run never claims that
        nothing can write after it returned.

        The two descriptors that this controller holds between two steps -
        the bound root and the output directory - are named in the receipt
        and are closed when the run returns.  They are excluded from the
        leak computation and they are never silently forgotten.
        """
        if self.seam is not None:
            # The seam closes its own descriptors before the descriptor
            # snapshot of the receipt is taken.
            try:
                self.seam.close()
            except Exception:  # noqa: BLE001 - the cleanup stays bounded
                pass
        receipt['transitions'] = list(self.transitions)
        receipt['spawn_attempts'] = self.spawn_attempts
        receipt['duration_seconds'] = round(time.time() - receipt['started_wall'], 6)
        receipt['source_sha256'] = self._source_digests()
        receipt['node_id'] = self._node_id(receipt)
        receipt['execution_attempts'] = 1
        fd_after = _fd_snapshot()
        anchors = sorted(descriptor for descriptor in
                         (self._root_descriptor, self._controller_descriptor)
                         if descriptor is not None)
        leaked = None
        if fd_before is not None and fd_after is not None:
            leaked = sorted(set(fd_after['open']) - set(fd_before['open']) - set(anchors))
        receipt['fd_cleanup'] = {'fd_before': fd_before,
                                  'fd_after': fd_after,
                                  'fd_leaked': leaked,
                                  'observation_point': (
                                      'PRE_RELEASE: the snapshot is taken at the end of the '
                                      'run body, before this run releases the descriptors it '
                                      'held; the descriptors of this run are named below and '
                                      'are excluded from the leak set'),
                                  'controller_anchor_descriptors': anchors,
                                  'controller_anchor_descriptors_scope': (
                                      'THE_BOUND_ROOT_AND_THE_OUTPUT_DIRECTORY_OF_THIS_RUN;'
                                      'THEY_ARE_HELD_BY_THE_RUN_AND_CLOSED_WHEN_THE_RUN_RETURNS'),
                                  'worker_thread_finished': bool(
                                      self.seam.worker_thread_finished) if self.seam else None,
                                  'worker_exit_code': (self.seam.worker_exit_code
                                                       if self.seam else None),
                                  'readers_closed': self._readers_closed(),
                                  'worker_lifecycle': (self.seam.lifecycle()
                                                       if self.seam else None)}
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

    The argument set is closed: the sealed controller context, the *exact*
    seal of that context and the optional path of the receipt.  The seal is
    not optional: the entry never computes the expectation itself, so a
    context that was replaced between the sealing and the start is refused
    here and not later.  There is no switch that turns a refusal into an
    execution and there is no argument that names a command, a module or a
    callback.
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
    if context_sha256 is None:
        sys.stderr.write('S3_CONTROLLER_REFUSED CONTROLLER_CONTEXT_HASH_ARGUMENT_REQUIRED\n')
        return EXIT_REFUSED
    if not re.fullmatch(r'[0-9a-f]{64}', context_sha256):
        sys.stderr.write('S3_CONTROLLER_REFUSED CONTROLLER_CONTEXT_HASH_INVALID\n')
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
    try:
        sys.stdout.write(canonical_json(receipt) + '\n')
        sys.stdout.flush()
    except Exception as error:  # noqa: BLE001 - the failure stays visible
        # The receipt of the run is persisted inside the bound root, so the
        # state of the run stays available.  The failure of the standard
        # output is named, it names the state of the run as well and it
        # never hides the run behind an empty output.
        sys.stderr.write('S3_CONTROLLER_REFUSED STDOUT_WRITE_FAILED:'
                         + type(error).__name__
                         + ' STATE:' + str(receipt.get('state')) + '\n')
        return EXIT_INTERNAL
    if receipt['state'] == STATE_SUMMARY_PERSISTED:
        return EXIT_PERSISTED
    if receipt['state'] == STATE_UNKNOWN:
        return EXIT_UNKNOWN
    return EXIT_REFUSED


if __name__ == '__main__':
    sys.exit(main())
