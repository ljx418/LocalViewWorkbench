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
    ControllerIOError, open_child_directory, open_directory_chain,
    open_read_only_directory, open_root_directory_chain, read_bounded_at,
    read_bounded_regular, verify_directory_chain, verify_directory_identity)
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
    'canonical_receipt_reference', 'reference_anchors'})
# The kinds of a declared anchor of a reference.  The run root is the
# anchor of the artefacts of the run; a read-only directory is the anchor
# of a legitimate dependency that lives outside of the sealed run root.
# Every anchor is named by the sealed context document, so the source of
# every reference is explicit and closed.
ANCHOR_KINDS = ('RUN_ROOT', 'READ_ONLY_DIRECTORY')
ANCHOR_KEYS = frozenset({'name', 'kind', 'path'})
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


def _anchor_error(error):
    """The stable code of one refused anchored read.

    The detail of the refusal is kept, so a missing file and a refused
    link stay distinguishable without a second reading of the file.
    """
    if error.detail:
        return 'WORKER_ANCHOR_' + error.code + ':' + str(error.detail)
    return 'WORKER_ANCHOR_' + error.code


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _read_sealed(path, expected_sha256, limit=8 * 1024 * 1024):
    """Read one bounded file of a *trusted local entry* and check its seal.

    This is the entry point of the context document itself.  The path is
    an explicit entry of the trusted caller and it is read with the leaf
    bound of the safe reader; the seal that the caller gave is verified
    against the bytes, so a replaced document is refused here.  Every
    *data reference* of the context is read differently: it is read
    through a declared anchor, see :meth:`WorkerContext._read_anchored`.
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
        # The declared anchors of the data references.  Every reference of
        # this context is read through one of them, so the source of every
        # reference is explicit and a reference that leaves its anchor is
        # refused instead of being read on an arbitrary parent path.
        self.anchors = self._declared_anchors(document['reference_anchors'])
        run_root_anchor = [anchor for anchor in self.anchors
                           if anchor['kind'] == 'RUN_ROOT'][0]
        if run_root_anchor['base'] != os.path.normpath(document['root']):
            # The run root anchor and the root of the context are the same
            # directory: the artefacts of the run are never read through a
            # different anchor than the root of the run.
            raise WorkerError('WORKER_CONTEXT_RUN_ROOT_ANCHOR_MISMATCH')
        # The digest and the length of the very bytes of this context.
        self.document_sha256 = None
        self.document_bytes = None

    @staticmethod
    def _declared_anchors(declared):
        """The closed set of the declared anchors of this context.

        The run root is always one of the anchors and it is the root of
        the context.  Every other anchor is a read-only directory that the
        sealed context names explicitly; the worker never adopts a path
        that the context did not declare.
        """
        if not isinstance(declared, list) or not declared:
            raise WorkerError('WORKER_CONTEXT_ANCHORS_INVALID')
        anchors = []
        names = set()
        run_root = None
        for entry in declared:
            if not isinstance(entry, dict) or set(entry) != ANCHOR_KEYS:
                raise WorkerError('WORKER_CONTEXT_ANCHORS_INVALID')
            name = entry['name']
            kind = entry['kind']
            path = entry['path']
            if not isinstance(name, str) or not name or name in names:
                raise WorkerError('WORKER_CONTEXT_ANCHORS_INVALID')
            if kind not in ANCHOR_KINDS:
                raise WorkerError('WORKER_CONTEXT_ANCHORS_INVALID')
            if not isinstance(path, str) or not path or not os.path.isabs(path):
                raise WorkerError('WORKER_CONTEXT_ANCHORS_INVALID')
            names.add(name)
            anchor = {'name': name, 'kind': kind, 'path': path,
                      'base': os.path.normpath(path)}
            if kind == 'RUN_ROOT':
                if run_root is not None:
                    raise WorkerError('WORKER_CONTEXT_ANCHORS_INVALID')
                run_root = anchor
            anchors.append(anchor)
        if run_root is None:
            raise WorkerError('WORKER_CONTEXT_RUN_ROOT_ANCHOR_INVALID')
        return anchors

    def _anchor_of(self, path):
        """The declared anchor that contains one reference and its name.

        The comparison is lexical and never resolves a link: the identity
        of a reference is its literal location inside a declared anchor,
        not the object that a resolved path happens to name.
        """
        literal = os.path.normpath(str(path))
        if not os.path.isabs(literal):
            raise WorkerError('WORKER_REFERENCE_NOT_ABSOLUTE')
        selected = None
        for anchor in self.anchors:
            base = anchor['base']
            if literal == base:
                raise WorkerError('WORKER_REFERENCE_IS_AN_ANCHOR')
            prefix = base + os.sep
            if not literal.startswith(prefix):
                continue
            # The most specific anchor wins: a reference is read through
            # the anchor that contains it most closely.
            if selected is None or len(base) > len(selected['base']):
                selected = anchor
        if selected is None:
            raise WorkerError('WORKER_REFERENCE_OUTSIDE_DECLARED_ANCHORS')
        prefix = selected['base'] + os.sep
        parts = [part for part in literal[len(prefix):].split(os.sep)
                 if part not in ('', '.')]
        if not parts:
            raise WorkerError('WORKER_REFERENCE_INVALID')
        return selected, parts

    def _anchor_by_path(self, path):
        """The declared anchor whose path is exactly the given path."""
        literal = os.path.normpath(str(path))
        for anchor in self.anchors:
            if anchor['base'] == literal:
                return anchor
        raise WorkerError('WORKER_REFERENCE_OUTSIDE_DECLARED_ANCHORS')

    def _read_through_anchor(self, anchor, parts, limit=8 * 1024 * 1024):
        """Read one reference through its declared anchor.

        The run root is walked level by level from the file system root,
        so a link in the chain is refused and never walked.  A read-only
        anchor is opened without following a link and its identity is
        verified again after the read, so a replaced anchor is refused.
        The bytes are always read through the descriptor of the verified
        directory, never through a path that was resolved away.
        """
        if anchor['kind'] == 'RUN_ROOT':
            try:
                descriptor, chain = open_root_directory_chain(anchor['path'])
            except ControllerIOError as error:
                raise WorkerError(_anchor_error(error)) from error
            try:
                directory = open_directory_chain(descriptor, parts[:-1])
                try:
                    raw = read_bounded_at(directory, parts[-1], limit)
                finally:
                    os.close(directory)
                verify_directory_chain(chain)
                return raw
            except ControllerIOError as error:
                raise WorkerError(_anchor_error(error)) from error
            finally:
                os.close(descriptor)
        try:
            descriptor, identity = open_read_only_directory(anchor['path'])
        except ControllerIOError as error:
            raise WorkerError(_anchor_error(error)) from error
        opened = []
        try:
            directory = descriptor
            for part in parts[:-1]:
                child = open_child_directory(directory, part)
                opened.append(child)
                directory = child
            raw = read_bounded_at(directory, parts[-1], limit)
            verify_directory_identity(anchor['path'], identity)
            return raw
        except ControllerIOError as error:
            raise WorkerError(_anchor_error(error)) from error
        finally:
            for child in reversed(opened):
                os.close(child)
            os.close(descriptor)

    def _read_anchored(self, path, expected_sha256, limit=8 * 1024 * 1024):
        """Read one data reference through its anchor and check its seal."""
        anchor, parts = self._anchor_of(path)
        raw = self._read_through_anchor(anchor, parts, limit)
        if sha256_bytes(raw) != expected_sha256:
            raise WorkerError('WORKER_FILE_SEAL_MISMATCH')
        return raw

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
        return self._read_anchored(self.document['projection_path'],
                                   self.document['projection_sha256'])

    def source_identity(self):
        raw = self._read_anchored(self.document['source_identity_path'],
                                  self.document['source_identity_sha256'])
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkerError('WORKER_SOURCE_IDENTITY_NOT_JSON') from error
        if not isinstance(value, dict):
            raise WorkerError('WORKER_SOURCE_IDENTITY_NOT_OBJECT')
        return value

    def parent_budget(self):
        raw = self._read_anchored(self.document['parent_budget_path'],
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

        The directory that the manifest names is the anchor of its files.
        It has to be an anchor that the sealed context declared, so a
        dependency is never read through an arbitrary parent path and the
        resolved path of a link is never adopted as the identity of a
        dependency.
        """
        raw = self._read_anchored(self.document['dependency_manifest_path'],
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
        anchor = self._anchor_by_path(directory)
        for entry in files:
            if (not isinstance(entry, dict) or not isinstance(entry.get('path'), str)
                    or not re.fullmatch('[0-9a-f]{64}', str(entry.get('sha256')))):
                raise WorkerError('WORKER_DEPENDENCY_MANIFEST_INVALID')
            try:
                file_anchor, parts = self._anchor_of(entry['path'])
            except WorkerError as error:
                raise WorkerError('WORKER_DEPENDENCY_FILE_OUTSIDE_THE_DECLARED_ANCHOR') from error
            if file_anchor['name'] != anchor['name']:
                # The file of the manifest has to live in the directory that
                # the manifest itself declares.
                raise WorkerError('WORKER_DEPENDENCY_FILE_OUTSIDE_THE_DECLARED_ANCHOR')
            try:
                actual = sha256_bytes(self._read_through_anchor(anchor, parts))
            except WorkerError as error:
                if error.code.endswith(':ENOENT'):
                    raise WorkerError('WORKER_DEPENDENCY_FILE_MISSING') from error
                raise error
            if actual != entry['sha256']:
                raise WorkerError('WORKER_DEPENDENCY_FILE_DRIFT')
        return value

    def binding(self):
        """The sealed native binding that the phase requires."""

        raw = self._read_anchored(self.document['binding_path'],
                                  self.document['binding_sha256'])
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
        # The canonical receipt is read through the bound root anchor,
        # without following a link and with a real bound.
        anchor, parts = context._anchor_of(context.root.joinpath(reference))
        raw = context._read_through_anchor(anchor, parts)
    except ControllerIOError as error:
        raise WorkerError('WORKER_CANONICAL_RECEIPT_' + error.code) from error
    except WorkerError as error:
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
