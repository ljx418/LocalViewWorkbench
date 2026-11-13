"""The fixed quality worker of the S3 parent supervision.

The worker rebuilds the *bound data context* of its run and it really invokes
the accepted ``QualityPhase``.  It never deserialises a Python callback: the
context document holds paths, digests and closed enumerations only, and every
file that it names is read and hashed again before it is used.

The worker speaks the bounded supervision protocol of the parent on its
standard output.  Its terminal event carries only the relative reference,
the length and the hash of the canonical receipt inside the bound root; the
parent reads the real bytes itself and never treats an in-memory claim of
this process as a result.

The production entry is exactly this module with one context document.  There
is no dynamic import of a caller supplied module and no arbitrary argument
vector.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from tools.v0_s3_controller_io import (  # noqa: E402 - the path is set above
    ControllerIOError, read_bounded_in_root, read_bounded_regular)
from tools.v0_s3_quality_phase import (  # noqa: E402 - the path is set above
    CANONICAL_RECEIPT_NAME, QualityPhase, QualityContractError)
from tools.v0_s3_supervisor import PROTOCOL_SCHEMA  # noqa: E402 - the path is set above

CONTEXT_SCHEMA = 'lvw.s3-quality-worker-context/1'

# The stable code of the one missing capability of this platform.  There
# is no accepted native execution backend today, so the *default* entry of
# the worker refuses before any native driver is constructed.  The typed
# offline driver of the composition is a Python object and is never
# reachable from the command line.
NATIVE_EXECUTION_BACKEND_NOT_READY = 'NATIVE_EXECUTION_BACKEND_NOT_READY'
CONTEXT_KEYS = frozenset({
    'schema', 'run_id', 'candidate_sha', 'authorization_sha256', 'root',
    'projection_path', 'projection_sha256', 'source_identity_path',
    'source_identity_sha256', 'parent_budget_path', 'parent_budget_sha256',
    'binding_path', 'binding_sha256', 'driver', 'driver_arguments',
    'dependency_manifest_path', 'dependency_manifest_sha256',
    'canonical_receipt_reference'})
DRIVERS = ('native', 'fixture')
DRIVER_ARGUMENT_KEYS = frozenset({'powershell', 'comfy_main', 'comfy_python',
                                   'ollama_exe', 'ffmpeg_exe', 'nvidia_exe'})
BINDING_KEYS = frozenset({'candidate_sha', 'authorization_sha256', 'ollama_pid',
                          'ollama_start_ticks', 'baseline_gpu_mib'})
DEPENDENCY_MANIFEST_SCHEMA = 'lvw.s3-dependency-path-manifest/1'
DEPENDENCY_MANIFEST_SCOPE = 'named_files_only_not_a_transitive_seal'
DEFAULT_CANONICAL_REFERENCE = 'temp/s3-quality/' + CANONICAL_RECEIPT_NAME



class WorkerError(RuntimeError):
    """A refused worker step with a stable, machine readable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _read_sealed(path, expected_sha256, limit=8 * 1024 * 1024):
    """Read one bounded file and check its seal again.

    The bytes are taken from the handle that was opened and verified, and
    the bound is applied to the bytes that are really requested from the
    kernel: an oversized file is refused without being read into the
    memory of the process, and a link or a special file is never read as
    a file.
    """
    target = Path(path)
    if not target.is_absolute():
        target = PACK_ROOT / target
    try:
        raw = read_bounded_regular(target, limit)
    except ControllerIOError as error:
        raise WorkerError('WORKER_FILE_' + error.code) from error
    if sha256_bytes(raw) != expected_sha256:
        raise WorkerError('WORKER_FILE_SEAL_MISMATCH')
    return raw


class WorkerContext:
    """The bound data context of one supervised quality run."""

    def __init__(self, document):
        if not isinstance(document, dict):
            raise WorkerError('WORKER_CONTEXT_NOT_OBJECT')
        if set(document) != CONTEXT_KEYS:
            raise WorkerError('WORKER_CONTEXT_KEY_SET_INVALID')
        if document['schema'] != CONTEXT_SCHEMA:
            raise WorkerError('WORKER_CONTEXT_SCHEMA_INVALID')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', str(document['run_id'])):
            raise WorkerError('WORKER_CONTEXT_RUN_ID_INVALID')
        if not re.fullmatch(r'[0-9a-f]{40}', str(document['candidate_sha'])):
            raise WorkerError('WORKER_CONTEXT_CANDIDATE_INVALID')
        if not re.fullmatch(r'[0-9a-f]{64}', str(document['authorization_sha256'])):
            raise WorkerError('WORKER_CONTEXT_AUTHORIZATION_INVALID')
        for key in ('projection_sha256', 'source_identity_sha256', 'parent_budget_sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}', str(document[key])):
                raise WorkerError('WORKER_CONTEXT_DIGEST_INVALID:' + key)
        if document['driver'] not in DRIVERS:
            raise WorkerError('WORKER_CONTEXT_DRIVER_INVALID')
        arguments = document['driver_arguments']
        if not isinstance(arguments, dict) or set(arguments) != DRIVER_ARGUMENT_KEYS \
                or any(not isinstance(value, str) or not value for value in arguments.values()):
            raise WorkerError('WORKER_CONTEXT_DRIVER_ARGUMENTS_INVALID')
        if not isinstance(document['root'], str) or not document['root']:
            raise WorkerError('WORKER_CONTEXT_ROOT_INVALID')
        reference = document['canonical_receipt_reference']
        if not isinstance(reference, str) or not reference:
            raise WorkerError('WORKER_CONTEXT_REFERENCE_INVALID')
        pure = Path(reference)
        if pure.is_absolute() or '..' in pure.parts:
            raise WorkerError('WORKER_CONTEXT_REFERENCE_INVALID')
        self.document = dict(document)
        self.run_id = document['run_id']
        self.candidate_sha = document['candidate_sha']
        self.authorization_sha256 = document['authorization_sha256']
        self.root = Path(document['root'])
        self.canonical_receipt_reference = reference
        # The digest and the length of the very bytes of this context.
        self.document_sha256 = None
        self.document_bytes = None

    @classmethod
    def load(cls, path, *, expected_sha256=None):
        if not expected_sha256:
            # The worker never computes the expectation itself: the hash of
            # the context is always given to it by the caller that sealed
            # it.
            raise WorkerError('WORKER_CONTEXT_HASH_REQUIRED')
        raw = _read_sealed(path, expected_sha256)
        try:
            document = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkerError('WORKER_CONTEXT_NOT_JSON') from error
        context = cls(document)
        context.document_sha256 = sha256_bytes(raw)
        context.document_bytes = len(raw)
        return context

    def projection(self):
        return _read_sealed(self.document['projection_path'],
                            self.document['projection_sha256'])

    def source_identity(self):
        raw = _read_sealed(self.document['source_identity_path'],
                            self.document['source_identity_sha256'])
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkerError('WORKER_SOURCE_IDENTITY_NOT_JSON') from error
        if not isinstance(value, dict):
            raise WorkerError('WORKER_SOURCE_IDENTITY_NOT_OBJECT')
        return value

    def parent_budget(self):
        raw = _read_sealed(self.document['parent_budget_path'],
                            self.document['parent_budget_sha256'])
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkerError('WORKER_PARENT_BUDGET_NOT_JSON') from error
        if not isinstance(value, dict):
            raise WorkerError('WORKER_PARENT_BUDGET_NOT_OBJECT')
        return value

    def dependency_manifest(self):
        """The sealed manifest of the existing dependency paths.

        The worker never downloads a dependency and it never trusts an
        environment variable: the manifest names the exact directory and the
        exact files, and every file is hashed again before it is used.
        """
        raw = _read_sealed(self.document['dependency_manifest_path'],
                           self.document['dependency_manifest_sha256'])
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkerError('WORKER_DEPENDENCY_MANIFEST_NOT_JSON') from error
        if not isinstance(value, dict) or value.get('schema') != DEPENDENCY_MANIFEST_SCHEMA:
            raise WorkerError('WORKER_DEPENDENCY_MANIFEST_INVALID')
        # The manifest binds the named files only.  It never claims a complete
        # transitive dependency closure, so the scope is part of the contract
        # and a claim of completeness is refused.
        if value.get('scope') != DEPENDENCY_MANIFEST_SCOPE:
            raise WorkerError('WORKER_DEPENDENCY_MANIFEST_SCOPE_INVALID')
        directory = value.get('path')
        files = value.get('files')
        if (not isinstance(directory, str) or not directory
                or not os.path.isabs(directory)
                or not isinstance(files, list) or not files):
            raise WorkerError('WORKER_DEPENDENCY_MANIFEST_INVALID')
        for entry in files:
            if (not isinstance(entry, dict) or not isinstance(entry.get('path'), str)
                    or not re.fullmatch('[0-9a-f]{64}', str(entry.get('sha256')))):
                raise WorkerError('WORKER_DEPENDENCY_MANIFEST_INVALID')
            target = Path(entry['path'])
            try:
                actual = sha256_bytes(read_bounded_regular(target))
            except ControllerIOError as error:
                if error.code == 'FILE_UNREADABLE' and error.detail == 'ENOENT':
                    raise WorkerError('WORKER_DEPENDENCY_FILE_MISSING') from error
                raise WorkerError('WORKER_DEPENDENCY_FILE_' + error.code) from error
            if actual != entry['sha256']:
                raise WorkerError('WORKER_DEPENDENCY_FILE_DRIFT')
        return value

    def binding(self):
        """The sealed native binding that the phase requires."""

        raw = _read_sealed(self.document['binding_path'], self.document['binding_sha256'])
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkerError('WORKER_BINDING_NOT_JSON') from error
        if not isinstance(value, dict) or set(value) != BINDING_KEYS:
            raise WorkerError('WORKER_BINDING_KEY_SET_INVALID')
        if value['candidate_sha'] != self.candidate_sha:
            raise WorkerError('WORKER_BINDING_CANDIDATE_MISMATCH')
        if value['authorization_sha256'] != self.authorization_sha256:
            raise WorkerError('WORKER_BINDING_AUTHORIZATION_MISMATCH')
        if type(value['ollama_pid']) is not int or value['ollama_pid'] <= 0:
            raise WorkerError('WORKER_BINDING_OLLAMA_PID_INVALID')
        if type(value['ollama_start_ticks']) is not int or value['ollama_start_ticks'] <= 0:
            raise WorkerError('WORKER_BINDING_OLLAMA_BIRTH_INVALID')
        if type(value['baseline_gpu_mib']) is not int or value['baseline_gpu_mib'] < 0:
            raise WorkerError('WORKER_BINDING_BASELINE_INVALID')
        return value


class ProtocolWriter:
    """The bounded protocol writer of the worker."""

    def __init__(self, stream, *, run_id, candidate_sha, authorization_sha256):
        self.stream = stream
        self.run_id = run_id
        self.candidate_sha = candidate_sha
        self.authorization_sha256 = authorization_sha256
        self.sequence = 0

    def emit(self, event, payload):
        self.sequence += 1
        message = {
            'schema': PROTOCOL_SCHEMA,
            'run_id': self.run_id,
            'candidate_sha': self.candidate_sha,
            'authorization_sha256': self.authorization_sha256,
            'sequence': self.sequence,
            'event': event,
            'payload': payload,
        }
        raw = canonical_json(message).encode('utf-8')
        if len(raw) > 32 * 1024:
            raise WorkerError('WORKER_MESSAGE_TOO_LARGE')
        self.stream.write(raw + b'\n')
        self.stream.flush()
        return message


def run_worker(context, *, driver=None, emit=None, authorize=None, clock=None, sleep=None):
    """Really invoke the accepted quality phase under the parent protocol.

    ``emit`` is the protocol sink of the worker: it receives the event name
    and the bounded payload.  ``driver`` is the runtime seam; the production
    entry builds the native driver from the bound context, the offline tests
    inject an explicit fake runtime seam.  In both cases the phase that runs
    is the accepted ``QualityPhase`` itself.
    """
    if emit is None:
        raise WorkerError('WORKER_EMIT_REQUIRED')
    if driver is None:
        raise WorkerError('WORKER_DRIVER_REQUIRED')
    projection = context.projection()
    source_identity = context.source_identity()
    parent_budget = context.parent_budget()
    manifest = context.dependency_manifest()
    directory = manifest['path']
    if directory not in sys.path:
        # The existing dependency directory is appended, never prepended: an
        # existing dependency must not shadow the standard library.
        sys.path.append(directory)
    if authorize is None:
        def authorize(action, subject):
            return None
    emit('STARTED', {'root': str(context.root),
                     'plan_rows': 16,
                     'driver': context.document['driver']})
    sink = lambda event, payload: emit(event, payload)  # noqa: E731 - a thin bridge
    phase = QualityPhase(driver, context.root, run_id=context.run_id,
                          candidate_sha=context.candidate_sha,
                          authorization_sha256=context.authorization_sha256,
                          projection=projection,
                          projection_sha256=context.document['projection_sha256'],
                          source_identity=source_identity, authorize=authorize,
                          binding=context.binding(), parent_budget=parent_budget,
                          clock=clock, sleep=sleep, progress_sink=sink)
    receipt = phase.run()
    reference = context.canonical_receipt_reference
    try:
        # The canonical receipt is read through the bound root, without
        # following a link and with a real bound.
        raw = read_bounded_in_root(context.root, reference)
    except ControllerIOError as error:
        raise WorkerError('WORKER_CANONICAL_RECEIPT_' + error.code) from error
    emit('TERMINAL', {'canonical_receipt': {'reference': reference,
                                            'bytes': len(raw),
                                            'sha256': sha256_bytes(raw)},
                      'decision': receipt.get('decision'),
                      'dependency_scope': manifest['scope'],
                      'dependency_transitive_seal_complete':
                          manifest.get('transitive_seal_complete') is True,
                      'stage_pass_claim': False,
                      'product_gate0': False})
    return receipt


def _write_refusal(stream, text):
    """Write one refusal to a text stream or to a binary stream.

    The exact code of the refusal is preserved in both cases.  A binary
    stream receives the UTF-8 bytes of the very same text, so a
    ``TypeError`` of the stream can never replace the code of the
    refusal with an exception of its own.
    """
    try:
        stream.write(text)
        return
    except TypeError:
        pass
    except (OSError, ValueError):
        return
    try:
        stream.write(text.encode('utf-8'))
    except (OSError, ValueError):
        pass


def main(argv=None, *, driver=None, stream=None, error_stream=None):
    """The production entry of the worker.

    The three keyword only arguments are the internal wiring of the
    composition: they let an in-process caller replace the *construction* of
    the native driver and the two output streams.  The command line entry
    passes none of them, so the command line path can never construct a
    native driver at all.

    The command line entry of this worker refuses the native execution
    with the stable code ``NATIVE_EXECUTION_BACKEND_NOT_READY``: there is
    no accepted native execution backend on this platform, so the refusal
    happens before any driver is constructed and before any model is
    touched.  The typed offline driver of the composition is a Python
    object that is never reachable from the command line and never
    serialised into a context document.

    The context of the worker is always loaded against the hash that the
    caller sealed.  The worker never computes the expectation itself, so
    a context that was replaced after the sealing is refused on every
    load.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    context_path = None
    context_sha256 = None
    target = stream if stream is not None else sys.stdout.buffer
    errors = error_stream if error_stream is not None else sys.stderr
    index = 0
    try:
        while index < len(arguments):
            if arguments[index] == '--context' and index + 1 < len(arguments):
                context_path = arguments[index + 1]
                index += 2
                continue
            if arguments[index] == '--context-sha256' and index + 1 < len(arguments):
                context_sha256 = arguments[index + 1]
                index += 2
                continue
            raise WorkerError('WORKER_ARGUMENT_INVALID')
        if context_path is None:
            raise WorkerError('WORKER_CONTEXT_ARGUMENT_REQUIRED')
        if context_sha256 is None:
            raise WorkerError('WORKER_CONTEXT_HASH_ARGUMENT_REQUIRED')
        if not re.fullmatch(r'[0-9a-f]{64}', context_sha256):
            raise WorkerError('WORKER_CONTEXT_HASH_INVALID')
        if driver is None:
            # The default entry of the worker refuses the native
            # execution before any driver is constructed.
            raise WorkerError(NATIVE_EXECUTION_BACKEND_NOT_READY)
        context = WorkerContext.load(context_path, expected_sha256=context_sha256)
        run_worker(context, driver=driver,
                   emit=ProtocolWriter(target, run_id=context.run_id,
                                       candidate_sha=context.candidate_sha,
                                       authorization_sha256=context.authorization_sha256
                                       ).emit)
    except WorkerError as error:
        _write_refusal(errors, 'S3_WORKER_REFUSED ' + error.code + '\n')
        return 2
    except QualityContractError as error:
        _write_refusal(errors, 'S3_WORKER_REFUSED QUALITY ' + str(error)[:120] + '\n')
        return 3
    except Exception as error:  # noqa: BLE001 - the failure stays visible
        _write_refusal(errors, 'S3_WORKER_REFUSED EXCEPTION ' + type(error).__name__ + '\n')
        return 3
    return 0


def build_native_driver(context):
    """Build the native runtime driver of the bound context.

    The native driver is the accepted ``NativeRuntime``.  It is only built
    from the bound context; nothing is imported dynamically and no service is
    started by this function.

    This function is the *future* interface of the native execution and it
    is not reachable from the command line of this worker: the default
    entry refuses the native execution with
    ``NATIVE_EXECUTION_BACKEND_NOT_READY`` before any driver is
    constructed.  A caller that reaches this function has already proved
    the admission of the native execution somewhere else.
    """
    from tools.v0_s2_runtime import NativeRuntime
    values = context.document['driver_arguments']
    arguments = type('NativeArguments', (), {
        'warm_benchmark': False, 'native_audit': True,
        'max_public_submissions': 45, 'max_loopback_requests': 8192,
        'max_native_clock_reads': 128, 'ffprobe_exe': None,
        'nvidia_exe': values['nvidia_exe'],
        'powershell': values['powershell'],
        'comfy_main': values['comfy_main'],
        'comfy_python': values['comfy_python'],
        'ollama_exe': values['ollama_exe'],
        'ffmpeg_exe': values['ffmpeg_exe'],
    })()
    evidence = {'owned_run_root': str(context.root)}
    return NativeRuntime(arguments, evidence)


if __name__ == '__main__':
    sys.exit(main())
