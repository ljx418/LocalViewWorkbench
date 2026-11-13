"""The Windows side broker of the parent owned native custody.

The broker is the only creator of the native services of one round.  The
parent starts it, keeps its original handle and talks to it over a private
channel; the broker creates the services itself, holds their original
handles and stops them again.

Four properties of the broker are the reason it exists at all.

* **Suspend first, adopt second.**  Every service is created with
  ``CREATE_SUSPENDED``.  The broker holds the original process and thread
  handle, it assigns the process to the job object of the round and only
  then it resumes the thread.  A service is never started first and
  adopted afterwards: a process that already ran could have broken away
  from the job before the adoption.

* **The job belongs to the round.**  One job object is created per round
  with ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` and without
  ``JOB_OBJECT_LIMIT_BREAKAWAY_OK``.  The children of the services inherit
  that constraint.  When the broker closes the job handle, the round is
  gone.  The broker is the only owner of that handle and of the stop.

* **Nothing else is inherited.**  The services get their standard output
  and their standard error and the null device as their standard input.
  They never get the control channel of the broker, the job handle or any
  other handle of the broker.  On Windows the inheritance set is not
  trusted to the default: it is passed explicitly as the handle list of
  the process attributes, and every handle of that list is created as
  inheritable while every other handle is not.

* **Only what was created is stopped.**  The broker has no notion of a
  process name, of a pid or of a record of another owner.  It stops the
  handles that it holds and the job that it created, and nothing else.

Nothing in this module has ever run on Windows.  Every native claim of
this package therefore stays ``NOT_PROVEN``: the Windows path is written
from the documented behaviour of the API and it is not a measurement.
"""
import hashlib
import json
import math
import os
import queue
import re
import select
import subprocess
import sys
import threading
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from tools.v0_s3_native_custody import (  # noqa: E402 - the path is set above
    CHANNEL_SCHEMA, CustodyError, MAX_DESCENDANTS, MAX_FRAME_BYTES, MAX_FRAMES,
    MAX_NEW_TEXT_BYTES, MAX_STREAM_BYTES, decode_command, validate_launch_plan)

# The bounded limits of the broker.  They are internal limits of this
# foundation; they are not a claim about any native Windows behaviour.
WAIT_MILLISECONDS = 5000
HEARTBEAT_TIMEOUT_SECONDS = 120
CLOSE_JOIN_SECONDS = 5.0
READER_JOIN_SECONDS = 2.0
# The ONE cleanup budget of a round.  The stop and the cleanup of a round
# share ONE absolute deadline: the deadline is generated once, at the
# first stop or at the first failure of the cleanup, and it is the same
# value in every layer of the cleanup.  No layer adds a budget of its own
# and no layer starts a new wait with a fresh timeout.
CLEANUP_BUDGET_SECONDS = 5.0
# The number of the startup results that the in-flight owner of a startup
# step may carry.  The channel is bounded: a startup owner that produced
# more than one result at a time would be an unbounded queue.
STARTUP_INFLIGHT_SLOTS = 1
# The bounded wait for a startup step that did not end before the
# deadline of the round.  A step that is still running after this wait
# keeps its owner and the round stays unknown: the round never claims a
# cleanup that it cannot prove.
STARTUP_SETTLE_SECONDS = 1.0
MAX_PLAN_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 1024 * 1024
POLL_SECONDS = 0.25

# The bounded waits of the private channel.  The pipe is polled in slices
# of at most 50 milliseconds, so that the cancel flag and the absolute
# deadline of the round are observed even while a peer is silent.
POLL_SLICE_SECONDS = 0.05
PIPE_READ_BYTES = 65536
# The number of the frames of the channel that is reserved for the
# terminal exchange of the round.  The heartbeat may not spend them: a
# round that reached its frame budget has to fail closed and it may not
# reconnect and it may not renew its lease.
RESERVED_TERMINAL_FRAMES = 8

# The frozen environment of every child.  The variables that the existing
# authorised launch wrappers remove are removed here as well, so that a
# child never inherits a proxy, a user site directory or a start-up file.
REMOVED_ENVIRONMENT = ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONINSPECT',
                        'PYTHONUSERBASE', 'PYTHONOPTIMIZE', 'HTTP_PROXY', 'HTTPS_PROXY',
                        'ALL_PROXY')


class BrokerError(RuntimeError):
    """A refused broker step with a stable, machine readable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


# -- the one context of a round ---------------------------------------------

class _RoundContext:
    """The ONE finite startup and cleanup context of one round.

    The context holds the four things that every layer of a round has to
    share and that may never be copied from one layer into the next one.

    * The **clock** of the round.  Every deadline of the round is
      expressed in it, so that a deadline of one domain is never
      compared with a clock of another one.

    * The **absolute deadline** of the round.  It is bound once and it
      may only be shortened.

    * The **one cleanup deadline**.  It is published **once**, by the
      first caller that enters the cleanup, and every later caller
      reuses that very value: two callers that entered the cleanup at the
      same moment always see the same number, and the publication is one
      atomic step under the lock of the context.

    * The three **one way latches** of the round: the cancel, the stop
      and the unknown.  A latch that was set is never cleared, and a
      late event may never overwrite the unknown of the round.

    Every layer of the round holds this **one object**: the core, the
    loop, the transport of the channel and the endpoints of the channel.
    A layer that only copied the number of a deadline would be a layer
    with a deadline of its own, and two layers with two deadlines are
    two budgets.
    """

    def __init__(self, *, clock=None, wall=None):
        self.clock = clock or time.monotonic
        self.wall = wall or time.time
        self._lock = threading.RLock()
        self._absolute_deadline = None
        self._cleanup_deadline = None
        self._inflight = []
        self._inflight_lock = threading.Lock()
        # The one way latches of the round.
        self.cancel = threading.Event()
        self.stopping = threading.Event()
        self.unknown = threading.Event()

    # -- the deadlines ----------------------------------------------------
    def bind_absolute_deadline(self, deadline):
        """Bind the absolute deadline of the round.  It may only shorten."""
        value = _require_deadline(deadline)
        if value is None:
            return self._absolute_deadline
        with self._lock:
            if self._absolute_deadline is None or value < self._absolute_deadline:
                self._absolute_deadline = value
            return self._absolute_deadline

    @property
    def absolute_deadline(self):
        with self._lock:
            return self._absolute_deadline

    def cleanup_deadline_value(self):
        """The published cleanup deadline, or ``None`` before the first."""
        with self._lock:
            return self._cleanup_deadline

    def cleanup_deadline(self, deadline=None):
        """Publish the ONE cleanup deadline of the round, atomically.

        The deadline is the earlier of the absolute deadline of the
        round, the fixed cleanup budget of the round and the deadline
        that the caller brought.  It is generated **once**: every later
        caller receives the very same value and may never extend it and
        may never replace it.
        """
        with self._lock:
            if self._cleanup_deadline is None:
                value = self.clock() + CLEANUP_BUDGET_SECONDS
                if self._absolute_deadline is not None:
                    value = min(value, self._absolute_deadline)
                candidate = _require_deadline(deadline)
                if candidate is not None:
                    value = min(value, candidate)
                self._cleanup_deadline = value
            return self._cleanup_deadline

    def remaining_cleanup(self, deadline=None):
        """The seconds that are left until the cleanup deadline.

        The value is recomputed on every call: a wait that already
        consumed part of the budget never receives the whole budget
        again.
        """
        value = self.cleanup_deadline(deadline)
        return max(0.0, value - self.clock())

    def cleanup_expired(self):
        """Whether the shared cleanup deadline of the round arrived."""
        with self._lock:
            value = self._cleanup_deadline
        if value is None:
            return False
        return self.clock() >= value

    def remaining_absolute(self):
        """The seconds that are left until the absolute deadline.

        The value is recomputed on every call and it is read from the
        **one** context of the round: a layer that copied the number of
        the deadline would have a deadline of its own.  ``None`` means
        that the round did not bind an absolute deadline at all.
        """
        with self._lock:
            value = self._absolute_deadline
        if value is None:
            return None
        return max(0.0, value - self.clock())

    # -- the one way latches ----------------------------------------------
    def request_cancel(self):
        """Ask for the cancellation of the round.  One way."""
        self.cancel.set()

    def request_stop(self):
        """Ask for the stop of the round.  One way."""
        self.stopping.set()

    def latch_unknown(self):
        """Latch the unknown state of the round.  One way.

        The first caller learns that it latched the state and every later
        caller learns that the state was already latched.  A late event
        may never clear the latch and may never replace it.
        """
        if self.unknown.is_set():
            return False
        self.unknown.set()
        return True

    def is_unknown(self):
        """Whether the unknown state of the round was latched."""
        return self.unknown.is_set()

    # -- the owners of the operations in flight ---------------------------
    def register_inflight(self, owner):
        """Take the ownership of one operation that is in flight."""
        with self._inflight_lock:
            if owner not in self._inflight:
                self._inflight.append(owner)
        return owner

    def release_inflight(self, owner):
        """Give the ownership of one operation back."""
        with self._inflight_lock:
            if owner in self._inflight:
                self._inflight.remove(owner)

    def inflight(self):
        """The owners of the operations that are in flight."""
        with self._inflight_lock:
            return list(self._inflight)


# -- the Windows primitive table -------------------------------------------

def _windows_command_line(executable, arguments):
    """Build the command line of one child.

    The quoting is the quoting of the Microsoft C runtime: a backslash run
    in front of a quote is doubled and a trailing backslash run is doubled
    as well, so that a path with a backslash is never truncated by the
    parser of the child.
    """
    parts = [_quote_windows_argument(executable)]
    parts.extend(_quote_windows_argument(item) for item in arguments)
    return ' '.join(parts)


def _quote_windows_argument(value):
    text = str(value)
    if text and not any(character in text for character in ' \t"'):
        return text
    quoted = ['"']
    backslashes = 0
    for character in text:
        if character == '\\':
            backslashes += 1
            continue
        if character == '"':
            quoted.append('\\' * (backslashes * 2 + 1))
            quoted.append('"')
            backslashes = 0
            continue
        if backslashes:
            quoted.append('\\' * backslashes)
            backslashes = 0
        quoted.append(character)
    quoted.append('\\' * (backslashes * 2))
    quoted.append('"')
    return ''.join(quoted)


def _environment_block(environment):
    """Build the Unicode environment block of one child."""
    if environment is None:
        return None
    import ctypes
    items = sorted(environment.items(), key=lambda item: item[0].casefold())
    raw = ''.join('%s=%s\0' % (key, value) for key, value in items) + '\0'
    return ctypes.create_unicode_buffer(raw)


def _windows_api_types():
    """The pure declaration of the Windows structures of the broker.

    The declaration is built **without** a native library.  It declares
    the layout of the structures and it returns them together with the
    ``ctypes`` module that built them, so that the layout can be measured
    and checked off Windows and so that the loaded primitive table uses
    exactly this declaration.

    The fixed width types are declared **explicitly**.  ``ctypes.wintypes``
    is a module of the host: its ``BOOL`` is a ``c_long`` and its
    ``DWORD`` is a ``c_uint``, and the size of a ``c_long`` is not the
    size of a Windows ``BOOL`` on every host.  A layout that was built
    from the types of the host would therefore be a layout of the host
    and not the layout of Windows.  Here a ``DWORD`` and a ``BOOL`` are
    always 32 bit, a ``WORD`` is always 16 bit and a handle and a
    ``SIZE_T`` have the width of a pointer.

    A name of a class body is resolved in the class namespace and in the
    global namespace only.  A class body therefore never assigns a name
    that shadows an enclosing local: ``kernel32 = kernel32`` would raise
    a ``NameError`` instead of copying the value, which is why the table
    of the broker is built from an explicit namespace and never from the
    body of a class.
    """
    import ctypes

    DWORD = ctypes.c_uint32
    BOOL = ctypes.c_int32
    WORD = ctypes.c_uint16
    UINT = ctypes.c_uint32
    LONG = ctypes.c_int32
    ULONG = ctypes.c_uint32
    HANDLE = ctypes.c_void_p
    SIZE_T = ctypes.c_size_t
    ULONG_PTR = ctypes.c_size_t
    LPCWSTR = ctypes.c_wchar_p
    LPWSTR = ctypes.c_wchar_p

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ('cb', DWORD),
            ('lpReserved', LPWSTR),
            ('lpDesktop', LPWSTR),
            ('lpTitle', LPWSTR),
            ('dwX', DWORD),
            ('dwY', DWORD),
            ('dwXSize', DWORD),
            ('dwYSize', DWORD),
            ('dwXCountChars', DWORD),
            ('dwYCountChars', DWORD),
            ('dwFillAttribute', DWORD),
            ('dwFlags', DWORD),
            ('wShowWindow', WORD),
            ('cbReserved2', WORD),
            ('lpReserved2', ctypes.POINTER(ctypes.c_byte)),
            ('hStdInput', HANDLE),
            ('hStdOutput', HANDLE),
            ('hStdError', HANDLE),
        ]

    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [('StartupInfo', STARTUPINFOW),
                    ('lpAttributeList', ctypes.c_void_p)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [('hProcess', HANDLE),
                    ('hThread', HANDLE),
                    ('dwProcessId', DWORD),
                    ('dwThreadId', DWORD)]

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        """The security attributes of one inheritable handle.

        ``bInheritHandle`` is a ``BOOL`` and it is a 32 bit value: a
        handle that is created with ``NULL`` security attributes can
        never be inherited at all.
        """
        _fields_ = [('nLength', DWORD),
                    ('lpSecurityDescriptor', ctypes.c_void_p),
                    ('bInheritHandle', BOOL)]

    class FILETIME(ctypes.Structure):
        _fields_ = [('dwLowDateTime', DWORD),
                    ('dwHighDateTime', DWORD)]

    class OVERLAPPED(ctypes.Structure):
        """The overlapped structure of one asynchronous operation.

        The structure owns the event of the completion and the offset
        of the operation.  It is released only after the completion of
        the operation was proven.
        """
        _fields_ = [('Internal', SIZE_T),
                    ('InternalHigh', SIZE_T),
                    ('Offset', DWORD),
                    ('OffsetHigh', DWORD),
                    ('hEvent', HANDLE)]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [('ReadOperationCount', ctypes.c_ulonglong),
                    ('WriteOperationCount', ctypes.c_ulonglong),
                    ('OtherOperationCount', ctypes.c_ulonglong),
                    ('ReadTransferCount', ctypes.c_ulonglong),
                    ('WriteTransferCount', ctypes.c_ulonglong),
                    ('OtherTransferCount', ctypes.c_ulonglong)]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong),
                    ('PerJobUserTimeLimit', ctypes.c_longlong),
                    ('LimitFlags', DWORD),
                    ('MinimumWorkingSetSize', SIZE_T),
                    ('MaximumWorkingSetSize', SIZE_T),
                    ('ActiveProcessLimit', DWORD),
                    ('Affinity', SIZE_T),
                    ('PriorityClass', DWORD),
                    ('SchedulingClass', DWORD)]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ('IoInfo', IO_COUNTERS),
                    ('ProcessMemoryLimit', SIZE_T),
                    ('JobMemoryLimit', SIZE_T),
                    ('PeakProcessMemoryUsed', SIZE_T),
                    ('PeakJobMemoryUsed', SIZE_T)]

    class JOBOBJECT_BASIC_PROCESS_ID_LIST(ctypes.Structure):
        """The process id list of a job object.

        The list is an **inline** array of ``ULONG_PTR`` and not a
        pointer: the first process id is written at the offset of the
        array and every other id follows it.  A structure that declared
        a pointer field here would read the first id as an address and
        would dereference it.
        """
        _fields_ = [('NumberOfAssignedProcesses', DWORD),
                    ('NumberOfProcessIdsInList', DWORD),
                    ('ProcessIdList', ULONG_PTR * 1)]

    return {
        'ctypes': ctypes,
        'DWORD': DWORD,
        'BOOL': BOOL,
        'WORD': WORD,
        'UINT': UINT,
        'LONG': LONG,
        'ULONG': ULONG,
        'HANDLE': HANDLE,
        'SIZE_T': SIZE_T,
        'ULONG_PTR': ULONG_PTR,
        'LPCWSTR': LPCWSTR,
        'LPWSTR': LPWSTR,
        'STARTUPINFOW': STARTUPINFOW,
        'STARTUPINFOEXW': STARTUPINFOEXW,
        'PROCESS_INFORMATION': PROCESS_INFORMATION,
        'SECURITY_ATTRIBUTES': SECURITY_ATTRIBUTES,
        'FILETIME': FILETIME,
        'OVERLAPPED': OVERLAPPED,
        'IO_COUNTERS': IO_COUNTERS,
        'JOBOBJECT_BASIC_LIMIT_INFORMATION': JOBOBJECT_BASIC_LIMIT_INFORMATION,
        'JOBOBJECT_EXTENDED_LIMIT_INFORMATION': JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        'JOBOBJECT_BASIC_PROCESS_ID_LIST': JOBOBJECT_BASIC_PROCESS_ID_LIST,
    }


def _declare_windows_primitives(kernel32, types):
    """Declare the prototypes of the Windows primitives of the broker.

    Every prototype is explicit.  A handle is a ``HANDLE``, a pointer is
    an explicit ``ctypes`` pointer, a size is a ``SIZE_T`` and every
    value that Windows defines as a 32 bit number is a ``DWORD`` or a
    ``BOOL``.  A primitive without a declared prototype takes its
    arguments as ``c_int`` and would truncate a 64 bit handle.

    The declaration is applied to the primitive table that is handed in,
    so the very same code declares the table of a real run and the table
    of an offline inspection.
    """
    ctypes = types['ctypes']
    void_p = ctypes.c_void_p
    size_t = types['SIZE_T']
    handle = types['HANDLE']
    boolean = types['BOOL']
    dword = types['DWORD']
    uint = types['UINT']
    ulong = types['ULONG']

    kernel32.CreateJobObjectW.argtypes = [ctypes.POINTER(types['SECURITY_ATTRIBUTES']),
                                          types['LPCWSTR']]
    kernel32.CreateJobObjectW.restype = handle
    kernel32.SetInformationJobObject.argtypes = [handle, ctypes.c_int, void_p, dword]
    kernel32.SetInformationJobObject.restype = boolean
    kernel32.CreateProcessW.argtypes = [types['LPCWSTR'], types['LPWSTR'],
                                        ctypes.POINTER(types['SECURITY_ATTRIBUTES']),
                                        ctypes.POINTER(types['SECURITY_ATTRIBUTES']),
                                        boolean, dword, void_p, types['LPCWSTR'],
                                        ctypes.POINTER(types['STARTUPINFOW']),
                                        ctypes.POINTER(types['PROCESS_INFORMATION'])]
    kernel32.CreateProcessW.restype = boolean
    kernel32.AssignProcessToJobObject.argtypes = [handle, handle]
    kernel32.AssignProcessToJobObject.restype = boolean
    kernel32.ResumeThread.argtypes = [handle]
    kernel32.ResumeThread.restype = dword
    kernel32.TerminateProcess.argtypes = [handle, uint]
    kernel32.TerminateProcess.restype = boolean
    kernel32.TerminateJobObject.argtypes = [handle, uint]
    kernel32.TerminateJobObject.restype = boolean
    kernel32.WaitForSingleObject.argtypes = [handle, dword]
    kernel32.WaitForSingleObject.restype = dword
    kernel32.GetExitCodeProcess.argtypes = [handle, ctypes.POINTER(dword)]
    kernel32.GetExitCodeProcess.restype = boolean
    kernel32.GetProcessTimes.argtypes = [handle,
                                         ctypes.POINTER(types['FILETIME']),
                                         ctypes.POINTER(types['FILETIME']),
                                         ctypes.POINTER(types['FILETIME']),
                                         ctypes.POINTER(types['FILETIME'])]
    kernel32.GetProcessTimes.restype = boolean
    kernel32.QueryInformationJobObject.argtypes = [handle, ctypes.c_int, void_p,
                                                   dword, ctypes.POINTER(dword)]
    kernel32.QueryInformationJobObject.restype = boolean
    kernel32.CloseHandle.argtypes = [handle]
    kernel32.CloseHandle.restype = boolean
    kernel32.CreatePipe.argtypes = [ctypes.POINTER(handle), ctypes.POINTER(handle),
                                    ctypes.POINTER(types['SECURITY_ATTRIBUTES']), dword]
    kernel32.CreatePipe.restype = boolean
    kernel32.ReadFile.argtypes = [handle, void_p, dword,
                                  ctypes.POINTER(dword), void_p]
    kernel32.ReadFile.restype = boolean
    kernel32.WriteFile.argtypes = [handle, void_p, dword,
                                   ctypes.POINTER(dword), void_p]
    kernel32.WriteFile.restype = boolean
    kernel32.SetHandleInformation.argtypes = [handle, dword, dword]
    kernel32.SetHandleInformation.restype = boolean
    kernel32.CreateFileW.argtypes = [types['LPCWSTR'], dword, dword,
                                     ctypes.POINTER(types['SECURITY_ATTRIBUTES']),
                                     dword, dword, handle]
    kernel32.CreateFileW.restype = handle
    kernel32.InitializeProcThreadAttributeList.argtypes = [void_p, dword, dword,
                                                           ctypes.POINTER(size_t)]
    kernel32.InitializeProcThreadAttributeList.restype = boolean
    kernel32.UpdateProcThreadAttribute.argtypes = [void_p, dword, size_t, void_p,
                                                   size_t, void_p, void_p]
    kernel32.UpdateProcThreadAttribute.restype = boolean
    kernel32.DeleteProcThreadAttributeList.argtypes = [void_p]
    kernel32.DeleteProcThreadAttributeList.restype = None
    # The cancellation of the private channel.  ``CancelSynchronousIo``
    # cancels the synchronous operation of one *thread* and it needs the
    # original handle of that thread, never a self reported identifier.
    kernel32.CancelSynchronousIo.argtypes = [handle]
    kernel32.CancelSynchronousIo.restype = boolean
    kernel32.DuplicateHandle.argtypes = [handle, handle, handle, ctypes.POINTER(handle),
                                         dword, boolean, dword]
    kernel32.DuplicateHandle.restype = boolean
    kernel32.GetCurrentThread.argtypes = []
    kernel32.GetCurrentThread.restype = handle
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = handle


class _WindowsApiTable:
    """The namespace of the primitive table of the broker.

    The attributes are assigned explicitly.  A class body resolves a
    name that it assigns itself in the class namespace and in the global
    namespace only, so a class body that copies an enclosing local into
    a name of its own raises a ``NameError`` instead of copying the
    value.
    """

    def __init__(self, *, kernel32, types):
        self.kernel32 = kernel32
        self.types = dict(types)
        for name in ('STARTUPINFOW', 'STARTUPINFOEXW', 'PROCESS_INFORMATION',
                     'SECURITY_ATTRIBUTES', 'IO_COUNTERS',
                     'JOBOBJECT_BASIC_LIMIT_INFORMATION',
                     'JOBOBJECT_EXTENDED_LIMIT_INFORMATION',
                     'JOBOBJECT_BASIC_PROCESS_ID_LIST'):
            setattr(self, name, types[name])

    def __repr__(self):  # pragma: no cover - a diagnostic only
        return '<WindowsApiTable types=%d>' % len(self.types)


def _load_windows_api():
    """Load the Windows primitive table of the broker.

    The load is lazy and it happens only inside the explicit native entry.
    An import of this module on a platform that is not Windows never
    touches ``WinDLL`` and never resolves a symbol, so the module stays
    importable and testable everywhere.  An unsupported platform refuses
    here, before anything is created: it is never degraded into an
    unconstrained process.

    The declaration of the structures and the declaration of the
    prototypes are two separate functions, so that the layout and the
    prototypes can be inspected without loading a native library at all.
    """
    if os.name != 'nt':
        raise BrokerError('BROKER_PLATFORM_UNSUPPORTED')
    import ctypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    types = _windows_api_types()
    _declare_windows_primitives(kernel32, types)
    return _WindowsApiTable(kernel32=kernel32, types=types)


class CreatedProcess:
    """The original handles of one created process."""

    __slots__ = ('process', 'thread', 'pid', 'creation_time', 'failures')

    def __init__(self, process, thread, pid, creation_time, failures=()):
        self.process = process
        self.thread = thread
        self.pid = pid
        self.creation_time = creation_time
        self.failures = tuple(failures)


class WindowsApi:
    """The typed Windows primitive façade of the broker.

    Every method of this class wraps exactly one Windows API call, and the
    broker never calls a Windows function itself.  That keeps the native
    detail - the pointer sizes, the handle ownership and the last error -
    in one place, and it lets the offline validation drive the very same
    broker logic through an in-process façade of the same shape.

    The declarations are pointer size safe: a handle is a
    ``wintypes.HANDLE``, every pointer is an explicit ``ctypes`` pointer
    and every structure declares its fields.  The last error of a failed
    call is read with ``ctypes.get_last_error()``, which is only correct
    because the module was loaded with ``use_last_error=True``.
    """

    CREATE_SUSPENDED = 0x00000004
    EXTENDED_STARTUPINFO_PRESENT = 0x00080000
    STARTF_USESTDHANDLES = 0x00000100
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x01000000
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 0x00000102
    HANDLE_FLAG_INHERIT = 0x00000001
    PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x00000080
    ERROR_MORE_DATA = 234
    ERROR_BROKEN_PIPE = 109
    ERROR_PIPE_NOT_CONNECTED = 233
    ERROR_HANDLE_EOF = 38
    ERROR_OPERATION_ABORTED = 995
    ERROR_NOT_FOUND = 1168
    DUPLICATE_SAME_ACCESS = 0x00000002

    def __init__(self, table=None):
        """The typed façade of the Windows primitives.

        The table is the primitive table of the broker.  A table may be
        handed in for the inspection of the declaration and of the
        layout: the table of a real run is the one that loads the
        native library, and the table of an inspection never loads one.
        The code that uses the façade is the same code in both cases.
        """
        self._api = table if table is not None else _load_windows_api()
        # The invalid value of a handle has the width of a pointer: it is
        # ``-1`` as a 32 bit value and it is ``0xffffffffffffffff`` as a
        # 64 bit one.  A comparison with the Python value ``-1`` would
        # never match the 64 bit value.
        self.invalid_handle_value = self._api.types['ctypes'].c_void_p(-1).value
        # The holding table of the façade.  Every original handle that a
        # successful ``CreateProcess`` produced enters this table in the
        # moment of its creation, before anything else may fail.  A handle
        # that was handed over to its owner leaves the table; a handle
        # that could not be handed over stays in it, with its owner, its
        # pid and the failures of its release.  The table is the recovery
        # entry point of the façade: the core keeps the façade and it can
        # therefore always reach the handles that it never received.
        self._retained = {}
        self._retained_order = []
        # The one lock of the holding table.  Every mutation of the
        # table and every handover of a handle out of it happen under
        # this lock: a handle that is registered by its receiver and
        # that the façade still names would have **two** owners, and a
        # handle that left the façade before its receiver registered it
        # would have none.
        self._table_lock = threading.RLock()
        # The handovers that really happened.  The list is the evidence
        # of the unique owner of a handle: a handle that was handed
        # over is not in the holding table any more and it is never
        # closed by the recovery of the façade.
        self._handovers = []
        # The ONE deadline of the recovery of the façade.  It is
        # published once: a second recovery of the same round reuses
        # the very same value and it never opens a new budget.
        self._recovery_deadline = None
        # The absolute deadline of the round, when the façade is bound to
        # one.  Every wait of the façade is bounded by it: a wait that
        # does not fit into the deadline of the round never starts.
        self._deadline = None
        self._clock = time.monotonic

    def bind_deadline(self, deadline, clock=None):
        """Bind the absolute deadline of the round to this façade.

        The deadline may only shorten the deadline that is already
        bound.  The waits of the façade - the wait of a release and the
        wait of the recovery - are bounded by it and they never start a
        wait with a fresh timeout of their own.
        """
        value = _require_deadline(deadline)
        if value is None:
            return self._deadline
        if clock is not None:
            self._clock = clock
        if self._deadline is None or value < self._deadline:
            self._deadline = value
        return self._deadline

    def _wait_timeout_ms(self):
        """The milliseconds that are left until the bound deadline.

        A façade without a bound deadline keeps the closed wait of the
        package.  A façade with one never waits longer than the deadline
        of the round allows.
        """
        if self._deadline is None:
            return WAIT_MILLISECONDS
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            return 0
        return max(1, min(WAIT_MILLISECONDS, int(remaining * 1000)))

    def _last_error(self):
        """The last error of the last failing primitive of the host.

        The value is read with ``ctypes.get_last_error()``, which is
        only correct because the module was loaded with
        ``use_last_error=True``.  A host that does not have that
        function at all cannot report a last error and reports zero.
        """
        getter = getattr(self._api.types['ctypes'], 'get_last_error', None)
        if getter is None:
            return 0
        return int(getter())

    def _security_attributes(self, inherit):
        """The security attributes of one handle.

        The attributes say that the handle may be inherited.  A handle
        that is created with ``NULL`` security attributes is never
        inheritable, so the handle list of the process attributes would
        name a handle that the child cannot receive.
        """
        ctypes = self._api.types['ctypes']
        attributes = self._api.types['SECURITY_ATTRIBUTES']()
        attributes.nLength = ctypes.sizeof(self._api.types['SECURITY_ATTRIBUTES'])
        attributes.lpSecurityDescriptor = None
        attributes.bInheritHandle = bool(inherit)
        return attributes

    # -- the holding table of the original handles -------------------------
    def _retain(self, handle, kind, pid=None, stage='CREATED'):
        """Take one original handle into the holding table of the façade.

        The table is entered in the moment of the creation of the handle
        and it is left only when the handle was closed with a confirmed
        close or when it was handed over to its owner.  A handle that
        stays in the table is a resource that this round still owns and
        it is named with its kind, its pid and its failures.
        """
        key = id(handle)
        with self._table_lock:
            if key not in self._retained:
                self._retained_order.append(key)
            self._retained[key] = {'handle': handle, 'kind': kind, 'pid': pid,
                                   'stage': stage, 'owner': 'WINDOWS_API',
                                   'failures': []}
            return self._retained[key]

    def _forget(self, handle):
        """Leave the holding table: the handle is closed or handed over."""
        key = id(handle)
        with self._table_lock:
            if key in self._retained:
                del self._retained[key]
                if key in self._retained_order:
                    self._retained_order.remove(key)
                return True
        return False

    def forget_handle(self, handle):
        """Leave the holding table, under the lock of the table.

        The method is the public face of ``_forget``: the receiver of a
        handle uses it when the façade of the primitives does not offer
        the atomic handover.  A façade that offers the handover uses
        that one instead.
        """
        return self._forget(handle)

    def _note(self, handle, failure):
        """Name one failure of one retained handle."""
        key = id(handle)
        with self._table_lock:
            entry = self._retained.get(key)
            if entry is not None:
                entry['failures'].append(failure)
            return entry

    def retained_handles(self):
        """The original handles that this façade still holds.

        The list is a copy: a caller that changes it changes nothing of
        the holding table of the façade.
        """
        with self._table_lock:
            return [dict(self._retained[key]) for key in self._retained_order
                    if key in self._retained]

    def handovers(self):
        """The handovers that really happened, as a copy of the log."""
        with self._table_lock:
            return [dict(item) for item in self._handovers]

    def handover(self, entries, *, owner, register):
        """Hand the named handles over to their new owner, in one step.

        The receiver registers the handles and the façade forgets them
        under **one** lock.  The two facts are one atomic step: a
        handle that the receiver registered and that the façade still
        names would have two independent owners, and the recovery of
        the façade could close a handle that a live reader of the round
        is reading from.  A handle that left the façade before its
        receiver registered it would have no owner at all.

        ``entries`` is the list of ``(handle, kind)`` pairs and
        ``register`` receives it and registers every handle with the
        receiver.  The handover is recorded, so that the evidence of the
        round can name the owner that received the handle.
        """
        items = list(entries)
        with self._table_lock:
            register(items)
            for handle, kind in items:
                self._forget(handle)
                self._handovers.append({'kind': kind, 'owner': owner,
                                        'handle_repr': repr(handle)})
            return True

    def _recovery_timeout_ms(self):
        """The milliseconds that are left until the ONE recovery deadline.

        The deadline of the recovery is published **once**: a second
        recovery of the same round reuses the very same value and it
        never opens a new budget of its own.  A wait of a recovery that
        arrives after the deadline never starts.
        """
        with self._table_lock:
            if self._recovery_deadline is None:
                value = self._deadline
                if value is None:
                    value = self._clock() + (WAIT_MILLISECONDS / 1000.0)
                self._recovery_deadline = min(
                    value, self._clock() + (WAIT_MILLISECONDS / 1000.0))
            remaining = self._recovery_deadline - self._clock()
        if remaining <= 0:
            return 0
        return max(1, min(WAIT_MILLISECONDS, int(remaining * 1000)))

    def _confirm_process_exit(self, handle, failures, cancellations,
                              timeout_ms=None):
        """Try to confirm the exit of one process, once.

        The confirmation of the exit and the confirmation of the close
        of a handle are two different facts.  A wait that timed out is
        **not** an exit: the process may still be alive and it may even
        be a suspended process that never ran.  Its control handle is
        the only handle that may stop it.

        The method returns ``True`` only when the exit was really
        confirmed.  A cancellation of the wait is named and it is handed
        to the caller, which raises it after every safe step was
        executed.
        """
        if timeout_ms is None:
            timeout_ms = self._wait_timeout_ms()
        if timeout_ms <= 0:
            failures.append('WaitForSingleObject:no_budget')
            return False
        try:
            result = self._api.kernel32.WaitForSingleObject(handle, timeout_ms)
        except (KeyboardInterrupt, SystemExit) as error:
            failures.append('WaitForSingleObject:CANCELLED')
            cancellations.append(error)
            return False
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            failures.append('WaitForSingleObject:' + type(error).__name__)
            return False
        if result == self.WAIT_OBJECT_0:
            failures.append('WaitForSingleObject:exited')
            return True
        if result == self.WAIT_TIMEOUT:
            failures.append('WaitForSingleObject:exit_not_confirmed')
            return False
        failures.append('WaitForSingleObject:wait=%d' % int(result))
        return False

    def release_retained(self):
        """Try to release every handle that the façade still holds.

        This is the recovery entry point of the façade.  It is explicit:
        a caller that wants the handles of a failed creation released
        asks for it, and the result is named.  A handle that could not
        be closed stays in the holding table.

        Every handle is released on its own and every step of one handle
        is independent of the others: a cancellation in the middle of the
        recovery never skips the close of the next handle.  The
        cancellation is raised at the end of the recovery, after every
        safe step was executed, and it never replaces an ordinary
        failure of a handle.

        The **control handle of a process** is released only when its
        exit was really confirmed.  A process whose exit was not
        confirmed may still be alive and its control handle is the only
        handle that may stop it.  The handle therefore stays in the
        holding table with its owner and the recovery of the façade can
        reach it again: a later recovery that confirms the exit closes
        it and forgets it.  A close that succeeds is never a proof that
        the process ended.
        """
        report = []
        cancellations = []
        for key in list(self._retained_order):
            entry = self._retained.get(key)
            if entry is None:
                continue
            handle = entry['handle']
            failures = []
            if entry['kind'] == 'process':
                try:
                    if not self._api.kernel32.TerminateProcess(handle, 1):
                        failures.append('TerminateProcess:last_error=%d'
                                        % self._last_error())
                except (KeyboardInterrupt, SystemExit) as error:
                    failures.append('TerminateProcess:CANCELLED')
                    cancellations.append(error)
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    failures.append('TerminateProcess:' + type(error).__name__)
                confirmed = self._confirm_process_exit(
                    handle, failures, cancellations,
                    timeout_ms=self._recovery_timeout_ms())
                if not confirmed:
                    # The process may still be alive: the control handle
                    # stays with the façade and it is never closed under
                    # a process that nobody may stop any more.
                    failures.append('process_control_handle_retained:'
                                    'exit_not_confirmed')
                    self._note(handle, '|'.join(failures))
                    report.append({'kind': entry['kind'], 'pid': entry['pid'],
                                   'released': False,
                                   'failures': list(failures)})
                    continue
            if self._close_quietly(handle, failures, cancellations):
                self._forget(handle)
            else:
                self._note(handle, '|'.join(failures))
            report.append({'kind': entry['kind'], 'pid': entry['pid'],
                           'released': not any(failure.startswith('CloseHandle')
                                               for failure in failures),
                           'failures': list(failures)})
        if cancellations:
            # The cancellation is raised after every safe step of the
            # recovery was executed.  It is never swallowed and it never
            # replaces an ordinary failure that is named in the report.
            raise cancellations[0]
        return report

    # -- the job object ---------------------------------------------------
    def create_job(self):
        handle = self._api.kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise BrokerError('BROKER_JOB_CREATE_FAILED',
                              'last_error=%d' % self._last_error())
        return handle

    def set_job_kill_on_close(self, job):
        """Set the kill-on-close limit of the job and nothing else.

        ``JOB_OBJECT_LIMIT_BREAKAWAY_OK`` is deliberately *not* set: a
        child of the round may not break away from the job.
        """
        ctypes = self._api.types['ctypes']
        limit = self._api.JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limit.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self._api.kernel32.SetInformationJobObject(
                job, self.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limit), ctypes.sizeof(limit)):
            raise BrokerError('BROKER_JOB_LIMIT_FAILED',
                              'last_error=%d' % self._last_error())
        return True

    def terminate_job(self, job, exit_code):
        if not self._api.kernel32.TerminateJobObject(job, exit_code):
            raise BrokerError('BROKER_TERMINATE_FAILED',
                              'last_error=%d' % self._last_error())
        return True

    def job_process_ids(self, job):
        """The bounded list of the process ids of the job.

        The query is bounded by the descendant cap of this package.  A
        job that holds more processes than the cap is *not* reported as an
        empty job: the answer is unknown, and an unknown answer never
        becomes a zero.

        The structure of Windows holds two counts and an **inline** array
        of ``ULONG_PTR``.  The array is read from the buffer at the
        offset of the array and never through a pointer field.

        The answer is only accepted when **every** fact of it agrees:

        * the returned length is at least the size of the header, so that
          the two counts were really written and a legal empty job still
          carries its complete header;
        * the returned length is at most the size of the buffer, so that
          a length that is larger than the buffer was never accepted;
        * the returned length is at least the length that the count of
          the list needs, so that the list was not truncated;
        * the two counts are equal, so that the number of the assigned
          processes and the number of the listed processes agree;
        * the count of the list is within the cap of this package.

        Every other result is **unknown**: an exception, a returned
        length of zero, a reversed pair of counts, a count over the cap
        and a truncated list.  An unknown answer is never an empty job
        and never a success.
        """
        ctypes = self._api.types['ctypes']
        capacity = MAX_DESCENDANTS + 1
        pointer_size = ctypes.sizeof(ctypes.c_size_t)
        header_size = 2 * ctypes.sizeof(self._api.types['DWORD'])
        size = header_size + capacity * pointer_size
        buffer = ctypes.create_string_buffer(size)
        returned = self._api.types['DWORD'](0)
        if not self._api.kernel32.QueryInformationJobObject(
                job, self.JOB_OBJECT_BASIC_PROCESS_ID_LIST, buffer, size,
                ctypes.byref(returned)):
            error = self._last_error()
            if error == self.ERROR_MORE_DATA:
                raise BrokerError('BROKER_DESCENDANT_LIMIT', 'last_error=%d' % error)
            raise BrokerError('BROKER_JOB_QUERY_UNKNOWN', 'last_error=%d' % error)
        header = ctypes.cast(buffer, ctypes.POINTER(
            self._api.JOBOBJECT_BASIC_PROCESS_ID_LIST)).contents
        assigned = int(header.NumberOfAssignedProcesses)
        listed = int(header.NumberOfProcessIdsInList)
        reported = int(returned.value)
        # The returned length has to carry the whole header and it may
        # never be larger than the buffer that was handed to Windows.
        if reported < header_size or reported > size:
            raise BrokerError('BROKER_JOB_QUERY_TRUNCATED',
                              'returned=%d:header=%d:allocated=%d'
                              % (reported, header_size, size))
        if assigned > capacity or listed > capacity:
            raise BrokerError('BROKER_DESCENDANT_LIMIT',
                              'assigned=%d:listed=%d' % (assigned, listed))
        if assigned != listed:
            # The two counts disagree: the answer is unknown and it is
            # never an empty job.
            raise BrokerError('BROKER_JOB_QUERY_TRUNCATED',
                              'assigned=%d:listed=%d' % (assigned, listed))
        if listed > MAX_DESCENDANTS:
            raise BrokerError('BROKER_DESCENDANT_LIMIT',
                              'assigned=%d:listed=%d' % (assigned, listed))
        needed = header_size + listed * pointer_size
        if needed > reported:
            raise BrokerError('BROKER_JOB_QUERY_TRUNCATED',
                              'returned=%d:needed=%d' % (reported, needed))
        if listed == 0:
            # A legal empty job: the header was complete and the two
            # counts were zero.
            return []
        offset = header_size // pointer_size
        identifiers = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_size_t))
        return [int(identifiers[offset + index]) for index in range(listed)]

    # -- the processes -----------------------------------------------------
    def create_process_suspended(self, *, executable, arguments, working_directory,
                                  stdout_handle, stderr_handle, environment=None):
        """Create one suspended process and return its original handles.

        The child inherits exactly three handles: the write end of its
        standard output, the write end of its standard error and the null
        device as its standard input.  The inheritance set is passed
        explicitly as the handle list of the process attributes, so that
        the control channel of the broker, the job handle and every other
        handle of the broker stay in the broker.

        The size of the start up information is the size of the whole
        ``STARTUPINFOEXW``, because the extended flag is set and the
        attribute list follows the start up information inside it.

        The creation has **independent** steps.  The deletion of the
        attribute list, the close of the null device, the birth query of
        the created process and the release of a process that could not
        be adopted do not depend on each other: a failure of one of them
        never skips the others.  The first error of the creation is the
        error that leaves the method and the later errors are named next
        to it; the first error is never replaced by a later one.

        The original handles of a created process enter the holding table
        of this façade in the moment of the creation.  The null device
        of the child enters it in the moment of its creation as well: a
        null device that could not be closed is a resource of this round
        and it stays with its owner.  A handle that was handed over to
        the caller leaves the table; a handle that could not be closed
        stays in it with its owner and its failures, so that the recovery
        of the façade can always reach it.
        """
        ctypes = self._api.types['ctypes']
        kernel32 = self._api.kernel32
        failures = []
        command = ctypes.create_unicode_buffer(_windows_command_line(executable, arguments))
        environment_block = _environment_block(environment)
        attributes = self._security_attributes(True)
        null = kernel32.CreateFileW('NUL', self.GENERIC_READ,
                                    self.FILE_SHARE_READ | self.FILE_SHARE_WRITE,
                                    ctypes.byref(attributes), self.OPEN_EXISTING,
                                    self.FILE_ATTRIBUTE_NORMAL, None)
        if not null or null == self.invalid_handle_value:
            error = self._last_error()
            raise BrokerError('BROKER_NULL_DEVICE_FAILED',
                              'last_error=%d' % error)
        # The moment of the creation of the null device.  The handle of
        # the null device enters the holding table of this façade right
        # here: a null device whose close fails later is a resource of
        # this round and it keeps its original owner and its recovery
        # entry point.
        self._retain(null, 'null_device')
        attribute_list = None
        information = None
        process = None
        thread = None
        pid = None
        primary = None
        cleanup_error = None
        cancellations = []
        try:
            try:
                inherited = (ctypes.c_void_p * 3)(stdout_handle, stderr_handle, null)
                size = ctypes.c_size_t(0)
                kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
                attribute_list = ctypes.create_string_buffer(size.value)
                if not kernel32.InitializeProcThreadAttributeList(
                        attribute_list, 1, 0, ctypes.byref(size)):
                    error = self._last_error()
                    raise BrokerError('BROKER_ATTRIBUTE_LIST_FAILED',
                                      'last_error=%d' % error)
                if not kernel32.UpdateProcThreadAttribute(
                        attribute_list, 0, self.PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                        inherited, ctypes.sizeof(inherited), None, None):
                    error = self._last_error()
                    raise BrokerError('BROKER_ATTRIBUTE_LIST_FAILED',
                                      'last_error=%d' % error)
                startup = self._api.STARTUPINFOEXW()
                # The extended start up information is passed, so the
                # size is the size of the whole structure and not the
                # size of the plain start up information.
                startup.StartupInfo.cb = ctypes.sizeof(self._api.STARTUPINFOEXW)
                startup.StartupInfo.dwFlags = self.STARTF_USESTDHANDLES
                startup.StartupInfo.hStdInput = null
                startup.StartupInfo.hStdOutput = stdout_handle
                startup.StartupInfo.hStdError = stderr_handle
                startup.lpAttributeList = ctypes.cast(attribute_list, ctypes.c_void_p)
                information = self._api.PROCESS_INFORMATION()
                flags = (self.CREATE_SUSPENDED | self.EXTENDED_STARTUPINFO_PRESENT
                         | self.CREATE_UNICODE_ENVIRONMENT)
                environment_pointer = (ctypes.cast(environment_block, ctypes.c_void_p)
                                       if environment_block is not None else None)
                created = kernel32.CreateProcessW(
                    str(executable), command, None, None, True, flags,
                    environment_pointer, str(working_directory),
                    ctypes.byref(startup.StartupInfo), ctypes.byref(information))
                if not created:
                    error = self._last_error()
                    raise BrokerError('BROKER_PROCESS_CREATE_FAILED',
                                      'last_error=%d' % error)
                # The moment of the creation.  The original handles of
                # the process enter the holding table of this façade
                # before anything else may fail: they are never only an
                # integer in a local list or in the detail of an error.
                process = information.hProcess
                thread = information.hThread
                pid = int(information.dwProcessId)
                self._retain(process, 'process', pid)
                self._retain(thread, 'thread', pid)
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                primary = error
            finally:
                # The cleanups of the creation are independent of each
                # other and independent of the failure that is on the way
                # out.  A cleanup that fails never skips the other one and
                # a cancellation in the middle of a cleanup never skips
                # the cleanup that follows it: the cancellation is named
                # and it is raised after every safe step was executed.
                attribute_failures = []
                if attribute_list is not None:
                    try:
                        kernel32.DeleteProcThreadAttributeList(attribute_list)
                    except (KeyboardInterrupt, SystemExit) as error:
                        attribute_failures.append('DeleteProcThreadAttributeList:CANCELLED')
                        cancellations.append(error)
                    except Exception as error:  # noqa: BLE001 - the failure stays visible
                        attribute_failures.append('DeleteProcThreadAttributeList:'
                                                  + type(error).__name__)
                null_failures = []
                if self._close_quietly(null, null_failures, cancellations):
                    # The null device was closed with a confirmed close:
                    # it may be forgotten.
                    self._forget(null)
                failures.extend(attribute_failures)
                failures.extend(null_failures)
                if attribute_failures:
                    cleanup_error = BrokerError('BROKER_ATTRIBUTE_LIST_CLEANUP_FAILED',
                                                '|'.join(attribute_failures))
                elif null_failures:
                    cleanup_error = BrokerError('BROKER_NULL_DEVICE_CLOSE_FAILED',
                                                '|'.join(null_failures))
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            if primary is None:
                primary = error
        if cancellations and primary is None:
            # The cancellation of a cleanup is the primary error of the
            # creation when nothing else failed.  The cleanups that were
            # safe were executed before it was raised and the ordinary
            # failures that were named stay named next to it.
            primary = cancellations[0]
            failures.append('creation_cancelled:' + type(primary).__name__)
        creation = None
        if process is not None:
            # The birth query is the identity of the created process.  It
            # is independent of the cleanups above: it always runs when a
            # process was created.
            try:
                creation = self._process_creation_time(process)
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                if primary is None:
                    primary = error
        if primary is None and cleanup_error is None:
            # The creation was handed over: the original handles are the
            # property of the caller now and they leave the holding table.
            self._forget(process)
            self._forget(thread)
            return CreatedProcess(process, thread, pid, creation, failures)
        # The creation failed.  A process that was created is released
        # through its own original handle and every failure is named.
        release_failures = []
        if process is not None:
            self._release_created(process, thread, release_failures, cancellations)
        failures.extend(release_failures)
        if cancellations and primary is None:
            # The cancellation of the release is the primary error of the
            # creation when nothing else failed.  Every safe step was
            # executed before it is raised.
            primary = cancellations[0]
            failures.append('creation_cancelled:' + type(primary).__name__)
        error = primary if primary is not None else cleanup_error
        detail = getattr(error, 'detail', None)
        if failures:
            error.detail = ((detail or '') + '|cleanup=' + ','.join(failures))
        if cancellations and error is not cancellations[0]:
            # The primary error and the cancellation coexist: the
            # cancellation object stays reachable next to the primary
            # error and it is never replaced by a copy of a message.
            try:
                error.lvw_cancelled = cancellations[0]
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass
        raise error

    def _close_quietly(self, handle, failures, cancellations=None):
        """Close one handle and name a failure of the close.

        A cancellation in the middle of a close never skips the close
        that follows it: it is named in the failures and it is handed to
        the caller, which raises it after every safe step was executed.
        """
        try:
            if not self._api.kernel32.CloseHandle(handle):
                failures.append('CloseHandle:last_error=%d' % self._last_error())
                return False
        except (KeyboardInterrupt, SystemExit) as error:
            failures.append('CloseHandle:CANCELLED')
            if cancellations is not None:
                cancellations.append(error)
            return False
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            failures.append('CloseHandle:' + type(error).__name__)
            return False
        return True

    def _release_created(self, process, thread, failures, cancellations=None):
        """Release a process that was created but never adopted.

        The process is stopped through its own original handle, its exit
        is confirmed and both of its handles are closed.  A failure of
        one of the steps is named and the other steps still run: a handle
        is never left to the garbage collector.  A cancellation in the
        middle of the release never skips the close that follows it: it
        is named and the release continues.

        The confirmation of the exit and the confirmation of the close of
        a handle are two separate facts and they are recorded separately:
        a wait that timed out is not an exit and a close that failed is
        not a close.  A handle that could not be closed stays in the
        holding table of the façade: the original reference is kept and
        the recovery of the façade can reach it.

        The **control handle of the process** is the one exception: it
        is closed only when the exit was really confirmed.  A process
        whose exit was not confirmed may still be alive - it may be a
        suspended process that never ran - and its control handle is the
        only handle that may stop it.  The handle stays in the holding
        table of the façade with its owner, so that the recovery of the
        façade can reach it again.

        The cancellations of the release are collected in the list of
        the caller: they are raised after every safe step was executed
        and they never replace the primary error of the creation.
        """
        if cancellations is None:
            cancellations = []
        try:
            if not self._api.kernel32.TerminateProcess(process, 1):
                failures.append('TerminateProcess:last_error=%d' % self._last_error())
        except (KeyboardInterrupt, SystemExit) as error:
            failures.append('TerminateProcess:CANCELLED')
            cancellations.append(error)
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            failures.append('TerminateProcess:' + type(error).__name__)
        confirmed = self._confirm_process_exit(process, failures, cancellations)
        # The thread handle is independent of the exit of the process: it
        # is closed on its own and it never waits for the process.
        if thread is not None:
            if self._close_quietly(thread, failures, cancellations):
                self._forget(thread)
            else:
                self._note(thread, 'close_not_confirmed')
        if not confirmed:
            # The process may still be alive.  Its control handle stays
            # with the façade: it is never closed and never forgotten.
            failures.append('process_control_handle_retained:exit_not_confirmed')
            self._note(process, 'exit_not_confirmed:control_handle_retained')
            if cancellations:
                failures.append('release_cancelled:'
                                + type(cancellations[0]).__name__)
            return failures
        if self._close_quietly(process, failures, cancellations):
            self._forget(process)
        else:
            self._note(process, 'close_not_confirmed')
        if cancellations:
            failures.append('release_cancelled:' + type(cancellations[0]).__name__)
        return failures

    def _process_creation_time(self, process):
        """The birth time of one process, as the 100 nanosecond tick count.

        The query is the identity of the process: a process whose birth
        time cannot be read has no proven identity and is not used.
        """
        ctypes = self._api.types['ctypes']
        creation = self._api.types['FILETIME']()
        exit_time = self._api.types['FILETIME']()
        kernel = self._api.types['FILETIME']()
        user = self._api.types['FILETIME']()
        if not self._api.kernel32.GetProcessTimes(
                process, ctypes.byref(creation), ctypes.byref(exit_time),
                ctypes.byref(kernel), ctypes.byref(user)):
            error = self._last_error()
            raise BrokerError('BROKER_PROCESS_BIRTH_QUERY_FAILED',
                              'last_error=%d' % error)
        return (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)

    def assign_process_to_job(self, job, process):
        if not self._api.kernel32.AssignProcessToJobObject(job, process):
            raise BrokerError('BROKER_ASSIGN_FAILED',
                              'last_error=%d' % self._last_error())
        return True

    def resume_thread(self, thread):
        result = self._api.kernel32.ResumeThread(thread)
        if result == 0xFFFFFFFF:
            raise BrokerError('BROKER_RESUME_FAILED',
                              'last_error=%d' % self._last_error())
        return int(result)

    def terminate_process(self, process, exit_code):
        if not self._api.kernel32.TerminateProcess(process, exit_code):
            raise BrokerError('BROKER_TERMINATE_FAILED',
                              'last_error=%d' % self._last_error())
        return True

    def wait_process(self, process, timeout_ms):
        result = self._api.kernel32.WaitForSingleObject(process, timeout_ms)
        if result == self.WAIT_OBJECT_0:
            return True
        if result == self.WAIT_TIMEOUT:
            return False
        raise BrokerError('BROKER_WAIT_FAILED', 'wait=%d' % int(result))

    def exit_code(self, process):
        code = self._api.types['DWORD'](0)
        if not self._api.kernel32.GetExitCodeProcess(
                process, self._api.types['ctypes'].byref(code)):
            raise BrokerError('BROKER_EXIT_CODE_FAILED',
                              'last_error=%d' % self._last_error())
        return int(code.value)

    def close_handle(self, handle):
        if not self._api.kernel32.CloseHandle(handle):
            raise BrokerError('BROKER_HANDLE_CLOSE_FAILED',
                              'last_error=%d' % self._last_error())
        # The close was confirmed: the handle leaves the holding table
        # of the façade.  A handle that could not be closed stays in it
        # with its owner and it is reachable by the recovery.
        self._forget(handle)
        return True

    # -- the pipes ---------------------------------------------------------
    def create_pipe(self, name):
        """Create one pipe.  Only the write end is inheritable.

        The security attributes of the pipe say that the ends are
        inheritable and the inherit flag of the *read* end is cleared
        right afterwards.  A pipe that was created with ``NULL``
        security attributes can never be inherited at all.

        Both ends enter the holding table of this façade in the moment
        of their creation.  A pipe whose inherit flag could not be
        cleared therefore keeps its original ends with their owner: the
        core never received the pair and the round never loses the
        ownership of a handle that it created.

        The failure of the inherit flag is cleaned up **independently**
        of the two ends.  A cancellation of the inherit flag and a
        cancellation of the close of one end never skip the close of the
        other end: the safe close of both ends always runs and the
        cancellation is raised afterwards.  The end that could not be
        closed keeps its original reference with the façade and the end
        that was closed with a confirmed close leaves the table.
        """
        ctypes = self._api.types['ctypes']
        read = self._api.types['HANDLE']()
        write = self._api.types['HANDLE']()
        attributes = self._security_attributes(True)
        if not self._api.kernel32.CreatePipe(ctypes.byref(read), ctypes.byref(write),
                                             ctypes.byref(attributes), 0):
            error = self._last_error()
            raise BrokerError('BROKER_PIPE_FAILED', 'last_error=%d' % error)
        # The moment of the creation of the two ends.
        self._retain(read, 'pipe_read')
        self._retain(write, 'pipe_write')
        primary = None
        inherited = False
        try:
            inherited = bool(self._api.kernel32.SetHandleInformation(
                read, self.HANDLE_FLAG_INHERIT, 0))
        except (KeyboardInterrupt, SystemExit) as error:
            # The cancellation of the inherit flag is the primary error
            # of the pipe and it never skips the safe close of the ends.
            primary = error
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            primary = BrokerError('BROKER_PIPE_INHERIT_FAILED',
                                  'last_error=%d:%s' % (self._last_error(),
                                                        type(error).__name__))
        if inherited:
            return read, write
        error = self._last_error()
        failures = []
        cancellations = []
        if self._close_quietly(read, failures, cancellations):
            self._forget(read)
        if self._close_quietly(write, failures, cancellations):
            self._forget(write)
        if primary is None:
            primary = BrokerError(
                'BROKER_PIPE_INHERIT_FAILED',
                'last_error=%d%s' % (error,
                                     ('|cleanup=' + ','.join(failures))
                                     if failures else ''))
        else:
            try:
                primary.detail = ((getattr(primary, 'detail', None) or '')
                                  + '|cleanup=' + ','.join(failures))
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass
        if cancellations:
            # The cancellation of a close is the error that leaves the
            # method and the primary error stays reachable next to it:
            # a cancellation never becomes an ordinary evidence and it
            # never hides the error that caused the pipe.
            cancel = cancellations[0]
            try:
                cancel.lvw_primary = primary
                primary.lvw_cancelled = cancel
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass
            raise cancel
        raise primary

    def read_stream(self, handle, size):
        """Read one block of a child stream.

        The end of a stream is an end and not an error, but only in the
        branches that Windows documents as the end of a pipe: a broken
        pipe, a pipe that is not connected any more, the end of the file
        and an operation that was aborted.  Every other failure of the
        read is a failure of the round and it is named.
        """
        ctypes = self._api.types['ctypes']
        buffer = ctypes.create_string_buffer(size)
        read = self._api.types['DWORD'](0)
        if not self._api.kernel32.ReadFile(handle, buffer, size,
                                           ctypes.byref(read), None):
            error = self._last_error()
            if error in (self.ERROR_BROKEN_PIPE, self.ERROR_PIPE_NOT_CONNECTED,
                         self.ERROR_HANDLE_EOF, self.ERROR_OPERATION_ABORTED):
                return b''
            raise BrokerError('BROKER_STREAM_READ_FAILED', 'last_error=%d' % error)
        return buffer.raw[:read.value]

    def write_stream(self, handle, data):
        ctypes = self._api.types['ctypes']
        buffer = ctypes.create_string_buffer(bytes(data), len(data))
        written = self._api.types['DWORD'](0)
        if not self._api.kernel32.WriteFile(handle, buffer, len(data),
                                            ctypes.byref(written), None):
            raise BrokerError('BROKER_STREAM_WRITE_FAILED',
                              'last_error=%d' % self._last_error())
        return int(written.value)

    # -- the cancellation of a synchronous operation -----------------------
    def duplicate_current_thread_handle(self):
        """The original handle of the calling thread.

        The handle is the handle of the thread itself and never a self
        reported identifier: ``CancelSynchronousIo`` cancels the
        operation of one thread and it needs the real handle of that
        thread.
        """
        ctypes = self._api.types['ctypes']
        thread = self._api.kernel32.GetCurrentThread()
        process = self._api.kernel32.GetCurrentProcess()
        duplicate = self._api.types['HANDLE']()
        if not self._api.kernel32.DuplicateHandle(process, thread, process,
                                                  ctypes.byref(duplicate), 0,
                                                  False, self.DUPLICATE_SAME_ACCESS):
            raise BrokerError('BROKER_THREAD_HANDLE_FAILED',
                              'last_error=%d' % self._last_error())
        return duplicate

    def cancel_synchronous_io(self, thread_handle):
        """Ask for the cancellation of the synchronous operation of a thread.

        The call is a **request** and not a completion.  It may report
        ``ERROR_NOT_FOUND`` because the operation had not started yet or
        because it had just finished: the caller has to read the real
        completion of the thread and to join it.  The return value of
        this method names the state of the request.
        """
        if not self._api.kernel32.CancelSynchronousIo(thread_handle):
            error = self._last_error()
            if error == self.ERROR_NOT_FOUND:
                return 'NOT_FOUND'
            raise BrokerError('BROKER_PIPE_CANCEL_FAILED',
                              'last_error=%d' % error)
        return 'REQUESTED'


# -- the fixed command of a role ------------------------------------------

def _base_environment():
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() not in REMOVED_ENVIRONMENT}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['PYTHONNOUSERSITE'] = '1'
    environment['NO_PROXY'] = '127.0.0.1,localhost'
    return environment


def _comfy_environment(root):
    environment = _base_environment()
    temporary = str(Path(root) / 'temp' / 'service-os')
    environment.update({
        'HF_HUB_OFFLINE': '1',
        'TRANSFORMERS_OFFLINE': '1',
        'HF_DATASETS_OFFLINE': '1',
        'TEMP': temporary,
        'TMP': temporary,
        'TORCH_HOME': str(Path(temporary) / 'torch'),
        'HF_HOME': str(Path(temporary) / 'huggingface'),
        'XDG_CACHE_HOME': str(Path(temporary) / 'cache'),
    })
    return environment


def _ollama_environment():
    environment = _base_environment()
    environment['OLLAMA_HOST'] = '127.0.0.1:11434'
    environment['OLLAMA_NO_CLOUD'] = '1'
    return environment


def role_command(role, run_root, owned_pids):
    """Assemble the fixed command of one role.

    The command form of a role is frozen in this module and it is
    assembled from the tools that the plan closed.  The plan never carries
    an argument vector, a shell, a script or an environment: it carries
    the tools and the closed data of the role, and this function is the
    only place where a command line of this package exists.

    The forms are the ones of the already authorised launch of this pack:
    the ComfyUI launch of ``reports/v0-s1/wp-s1-03-phase-a/live_probe.py``
    and of ``tools/v0_s2_driver.py``, the Ollama launch of the same
    wrapper, and the sampler launch of ``tools/v0_s2_runtime.py``.

    The private process ids of the sampler are passed as *separate*
    arguments: the parser of the sampler is ``type=int, nargs='+'`` and
    one argument that carries a space would not be an integer.
    """
    name = role['role']
    tools = role['tools']
    data = role['data']
    root = str(run_root)
    if name == 'COMFY':
        python = tools[0]['path']
        main = tools[1]['path']
        arguments = ['-s', '-B', main,
                     '--listen', '127.0.0.1', '--port', '8191',
                     '--base-directory', root,
                     '--user-directory', str(Path(root) / data['user_directory']),
                     '--disable-auto-launch', '--disable-api-nodes',
                     '--disable-all-custom-nodes',
                     '--whitelist-custom-nodes', 'lvw_v0_bridge']
        return {'executable': python, 'arguments': arguments,
                'working_directory': root, 'environment': _comfy_environment(root)}
    if name == 'OLLAMA':
        executable = tools[0]['path']
        return {'executable': executable, 'arguments': ['serve'],
                'working_directory': root, 'environment': _ollama_environment()}
    if name == 'SAMPLER':
        python = tools[0]['path']
        script = tools[1]['path']
        directory = str(Path(root) / 'temp' / 'resource-sampler')
        arguments = ['-I', '-B', script, '--execute-sampler',
                     '--run-root', directory,
                     '--nvidia-smi', data['nvidia_exe'],
                     '--binary-sha256', data['nvidia_sha256'],
                     '--private-pids'] + [str(pid) for pid in owned_pids] + \
                    ['--max-seconds', str(data['max_seconds'])]
        return {'executable': python, 'arguments': arguments,
                'working_directory': directory, 'environment': _base_environment()}
    raise BrokerError('BROKER_ROLE_UNKNOWN', name)


# -- the bounded reader of a child stream ----------------------------------

class _BoundedStreamReader(threading.Thread):
    """One bounded background reader of one stream of a child.

    The thread only reads.  It never writes, it never calls the broker and
    it never waits for the broker.  The broker takes the published counts
    out of it at its own checkpoints, so the deadline of the round is never
    held up by a silent child.

    A read that failed for a reason that Windows does not document as the
    end of a pipe is a named error of the round: the reader keeps it and
    the round is not a release.
    """

    def __init__(self, win32, handle, *, limit, name):
        super().__init__(daemon=True, name='lvw-native-custody-stream-' + name)
        self.win32 = win32
        self.handle = handle
        self.limit = limit
        self.observed = 0
        self.kept = 0
        self.overflow = False
        self.error = None
        self.finished = threading.Event()

    def run(self):
        try:
            while True:
                block = self.win32.read_stream(self.handle, 65536)
                if not block:
                    break
                self.observed += len(block)
                if self.observed > self.limit:
                    self.overflow = True
                    break
                self.kept += len(block)
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.error = getattr(error, 'code', None) or type(error).__name__
        finally:
            self.finished.set()


# -- the pending resources of one round ------------------------------------

class _PendingResources:
    """The pending resource table of one round.

    Every handle that this round creates enters this table in the moment
    of its successful creation.  A handle **stays** in the table until it
    is closed with a confirmed close: the handover of a handle to its
    owner changes the owner and nothing else.  The handle is a resource
    that this round owns and it is named until it is really closed.

    A handle that could not be closed stays in the table with its owner:
    it is a resource that this round still owns and it is named in the
    evidence of the round.

    A handle of another owner is never in this table and it is never
    touched.

    The table carries the **owner object** of a handle and not only its
    name: a handle that is owned by a live reader is protected from the
    pending pass by the fact that the reader is alive and not by a
    string that somebody may write.  The owner object is the reader
    itself and the table asks it.
    """

    def __init__(self, win32):
        self._win32 = win32
        self._items = []
        self._lock = threading.RLock()

    def add(self, handle, kind, *, role=None, owner=None):
        item = {'handle': handle, 'kind': kind, 'role': role,
                'owner': owner or 'PENDING', 'owner_ref': None}
        with self._lock:
            self._items.append(item)
        return item

    def take(self, handle):
        """Remove one handle from the table: its owner holds it now."""
        with self._lock:
            for index, item in enumerate(self._items):
                if item['handle'] == handle:
                    del self._items[index]
                    return item
        return None

    def transfer(self, handle, owner, *, owner_ref=None):
        """Hand one pending handle over to its owner.

        The owner of the handle is only changed after the handover
        succeeded.  The handle stays in the table until it is closed: it
        is a resource that this round owns and it is named until then.
        A handle that could not be handed over keeps the owner
        ``PENDING`` and it is closed by the round.

        The ``owner_ref`` is the **object** of the new owner.  It is
        what the pending pass asks before it closes a handle: a read end
        that a live reader still reads from is never closed under it.
        """
        with self._lock:
            for item in self._items:
                if item['handle'] == handle:
                    item['owner'] = owner
                    if owner_ref is not None:
                        item['owner_ref'] = owner_ref
                    return item
        return None

    def pending(self):
        """The handles that this round still owns and has not closed."""
        with self._lock:
            return [dict(item) for item in self._items]

    def close_all(self, failures, on_closed=None, protect=None):
        """Close every handle that is still pending and name the failures.

        A handle that could not be closed stays in the table: it is a
        resource that this round still owns and it is named in the
        evidence of the round.  It is never left to the garbage
        collector and it is never closed twice.

        Every handle is closed on its own: a cancellation in the middle
        of the group never skips the handles that follow it.  The
        cancellation is raised after every handle was coordinated and it
        is never turned into an ordinary evidence.

        A handle that was closed with a **confirmed** close is reported
        to the owner of the table through ``on_closed``: the core has to
        learn that the handle is really closed, so that it never names a
        closed handle any more.  The report happens before the
        cancellation is raised: the bookkeeping of the core is never
        left behind the error that left the cleanup.

        The ``protect`` predicate is the **real** guard of the pass: a
        handle whose owner is still using it is never closed under it,
        whatever the branch that reached the pass did before.  The
        guard is asked about the owner and not about a name of an owner.
        """
        remaining = []
        cancellations = []
        with self._lock:
            items = list(self._items)
        for item in items:
            if protect is not None and protect(item):
                # The handle is in use by a live owner: it is never
                # closed under it and it keeps its owner.
                remaining.append(item)
                failures.append({'stage': 'close_pending', 'kind': item['kind'],
                                 'role': item['role'],
                                 'code': 'BROKER_PENDING_HANDLE_IN_USE'})
                continue
            try:
                self._win32.close_handle(item['handle'])
            except BrokerError as error:
                failures.append({'stage': 'close_pending', 'kind': item['kind'],
                                 'role': item['role'], 'code': error.code})
                remaining.append(item)
            except (KeyboardInterrupt, SystemExit) as error:
                failures.append({'stage': 'close_pending', 'kind': item['kind'],
                                 'role': item['role'],
                                 'error_type': type(error).__name__,
                                 'cancellation': True})
                remaining.append(item)
                cancellations.append(error)
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                failures.append({'stage': 'close_pending', 'kind': item['kind'],
                                 'role': item['role'],
                                 'error_type': type(error).__name__})
                remaining.append(item)
            else:
                item['closed'] = True
                if on_closed is not None:
                    on_closed(item)
        with self._lock:
            self._items = remaining
        if cancellations:
            raise cancellations[0]
        return remaining


# -- the core of the broker ------------------------------------------------

class BrokerCore:
    """The job and the handle custody of one native custody round.

    The core owns exactly one job object and the original handles of the
    processes of the round.  Every process of the round is created
    suspended, it is assigned to the job of the round and only then it is
    resumed.

    A failure never falls back to a weaker behaviour.  There is no retry
    without the job, there is no adoption of a process that was not
    created here and there is no stop of a process that this core does not
    hold a handle of.
    """

    def __init__(self, *, win32, plan, run_root, clock=None, wall=None,
                 context=None):
        self.win32 = win32
        self.plan = plan
        self.run_root = Path(run_root)
        self._clock = clock or time.monotonic
        self._wall = wall or time.time
        # The ONE context of the round.  The core, the loop, the
        # transport of the channel and the endpoints of the channel hold
        # this very object: a layer that only copied the number of a
        # deadline would be a layer with a deadline of its own.
        self.context = context if context is not None else _RoundContext(
            clock=self._clock, wall=self._wall)
        self.state = 'NEW'
        self.job = None
        self.job_kill_on_close = False
        self.job_closed = False
        self.job_terminated = False
        self.job_active = None
        self.job_active_known = False
        self.job_process_ids = []
        self.records = []
        self.failures = []
        self.readers = []
        self.reader_states = []
        self.new_text_bytes = 0
        self.stop_reason = None
        self._stream_failure_reported = False
        self._text_failure_reported = False
        self._pending = _PendingResources(win32)
        # The resources that this core could not release.  A resource
        # that could not be closed keeps its original reference and its
        # owner here: it is named in the evidence of the round and it is
        # never replaced by a copy of an error message.
        self._retained_resources = []
        # The cancellations that were observed during the coordination of
        # the readers.  They are raised after every reader was
        # coordinated and they never replace an ordinary failure.
        self._readers_cancelled = []
        # The cancellations that were observed during the wait of the
        # original processes.  They are raised after every process was
        # coordinated.
        self._processes_cancelled = []
        # The absolute deadline of the round.  It is bound by the loop
        # before the job of the round exists and it is the upper bound of
        # the one cleanup deadline of the round.
        self._absolute_deadline = None
        # The ONE cleanup deadline of the round.  It is generated at the
        # first stop or at the first failure of the cleanup and it is the
        # same value in every step of the cleanup.
        self._cleanup_deadline_value = None
        self._released = False
        self._abort_reported = False
        self.broker_identity = {
            'pid': os.getpid(),
            'executable': sys.executable,
            'reported_by_the_broker': True,
            'identity_source': 'CHILD_CLAIM',
        }

    # -- the deadlines of the round ---------------------------------------
    def bind_clock(self, clock):
        """Bind the clock of the round to this core.

        The core, the loop and the context of the round read the same
        clock: the absolute deadline of the round and the ONE cleanup
        deadline are in one domain and a deadline of one domain is never
        compared with a clock of another one.
        """
        if clock is not None:
            self._clock = clock
            self.context.clock = clock
        return self._clock

    def bind_absolute_deadline(self, deadline):
        """Bind the absolute deadline of the round to this core.

        The deadline may only shorten the deadline that is already
        bound.  It is the upper bound of the one cleanup deadline of the
        round: the cleanup never outlives the round itself.
        """
        value = self.context.bind_absolute_deadline(deadline)
        self._absolute_deadline = value
        # The façade of the primitives is bound to the same deadline: its
        # waits are bounded by the deadline of the round and they never
        # start a wait with a fresh timeout of their own.
        binder = getattr(self.win32, 'bind_deadline', None)
        if callable(binder):
            try:
                binder(value, self._clock)
            except BaseException:  # noqa: BLE001 - the failure stays visible
                pass
        return value

    def cleanup_deadline(self, deadline=None):
        """The ONE absolute deadline of the cleanup of this round.

        The deadline is generated once, at the first stop or at the first
        failure of the cleanup, and it is published **atomically** by the
        context of the round.  Two callers that entered the cleanup at
        the same moment therefore see the very same value and the
        deadline is never generated twice.

        It is the earlier of the absolute deadline of the round and the
        fixed cleanup budget, measured from the moment of the first
        cleanup.  Every later call returns the very same value: no layer
        of the cleanup adds a budget of its own and no layer starts a
        new wait with a fresh timeout.
        """
        value = self.context.cleanup_deadline(deadline)
        self._cleanup_deadline_value = value
        return value

    def remaining_cleanup_seconds(self, deadline=None):
        """The seconds that are left until the cleanup deadline.

        The value is recomputed on every call: a wait that already
        consumed part of the budget never gets the whole budget again.
        """
        return self.context.remaining_cleanup(deadline)

    def check_startup_budget(self, stage):
        """Check the shared budget of the startup **before** a step.

        A step of the startup of the round - the creation of a process,
        the assignment of a process to the job, the resume of its
        thread, the start of a reader and the creation of the next role
        - checks the shared cancel and the shared deadline of the round
        before it happens and after it happened.

        A step that runs after the deadline arrived may only clean up:
        it never resumes a thread and it never creates the next role.
        """
        context = self.context
        if context.cancel.is_set() or context.is_unknown():
            raise BrokerError('BROKER_STARTUP_CANCELLED', stage)
        deadline = context.absolute_deadline
        if deadline is not None and self._clock() >= deadline:
            raise BrokerError('BROKER_STARTUP_DEADLINE_EXCEEDED', stage)
        return True

    def _retain_resource(self, kind, handle, code=None, owner='CORE_RETAINED'):
        """Keep the original reference of a resource that was not released."""
        for item in self._retained_resources:
            if item['kind'] == kind and item['handle'] is handle:
                return item
        item = {'kind': kind, 'handle': handle, 'owner': owner, 'code': code}
        self._retained_resources.append(item)
        return item

    def _release_resource(self, kind, handle):
        """Forget a resource that was released with a confirmed close.

        The **original reference** of a resource is its identity: a
        handle that was really closed is forgotten whatever name it was
        retained under.  A resource that was not closed keeps its owner
        and it stays named: the retained list is never cleared to make a
        check green.
        """
        self._retained_resources = [item for item in self._retained_resources
                                   if item['handle'] is not handle]

    def _adopt_from_api(self, entries, role):
        """Take the named handles over from the façade of the primitives.

        The receiver registers the handles and the façade forgets them
        in **one** atomic step.  A handle that both of them names would
        have two independent owners and the recovery of the façade could
        close a handle that a live reader of the round is reading from.
        A handle that left the façade before its receiver registered it
        would have no owner at all.

        The façade that does not offer the atomic handover is asked to
        forget the handles after the registration: the receiver is
        always registered first, so that a failure in between leaves the
        handle with **two** owners and never with none.
        """
        items = list(entries)

        def register(handles):
            for handle, kind in handles:
                self._pending.add(handle, kind, role=role)

        handover = getattr(self.win32, 'handover', None)
        if callable(handover):
            handover(items, owner='CORE', register=register)
            return
        register(items)
        forget = getattr(self.win32, 'forget_handle', None)
        if callable(forget):
            for handle, _kind in items:
                forget(handle)

    def _api_retained(self):
        """The original handles that the Windows façade still holds.

        The façade is the owner of a handle that it could not hand over
        and it is the owner of the recovery of that handle.  The core
        keeps the façade, so the core can always reach these handles.

        The names of the handles are the printable ones: the evidence of
        a round is a document and it never carries a raw handle value.
        """
        getter = getattr(self.win32, 'retained_handles', None)
        if not callable(getter):
            return []
        try:
            entries = list(getter())
        except BaseException:  # noqa: BLE001 - the failure stays visible
            return []
        return [{'kind': entry.get('kind'), 'pid': entry.get('pid'),
                 'stage': entry.get('stage'), 'owner': entry.get('owner'),
                 'failures': list(entry.get('failures', ())),
                 'handle_repr': repr(entry.get('handle'))}
                for entry in entries]

    # -- the arming of the round ------------------------------------------
    def arm(self):
        """Create the job object of the round.

        The job is created before any process of the round exists, so that
        every process of the round can be assigned to it before it runs.

        The shared budget of the startup is checked **before** the
        creation of the job and **after** it: a job that was created
        after the deadline of the round arrived is only cleaned up and it
        is never armed.
        """
        if self.state != 'NEW':
            raise BrokerError('BROKER_STATE_INVALID', self.state)
        self.state = 'VALIDATED'
        self.check_startup_budget('ARM:JOB')
        try:
            self.job = self.win32.create_job()
        except BrokerError as error:
            self.failures.append({'stage': 'create_job', 'code': error.code})
            self.state = 'UNKNOWN_RETAINED'
            raise
        self._pending.add(self.job, 'job')
        self._pending.transfer(self.job, 'CORE')
        try:
            self.win32.set_job_kill_on_close(self.job)
        except BrokerError as error:
            self.failures.append({'stage': 'set_job_limits', 'code': error.code})
            closed = self._close_handle('job', self.job)
            if closed:
                # The job handle was closed with a confirmed close: it may
                # be forgotten.
                self.job = None
            else:
                # The job handle was not closed.  The original reference
                # stays with its owner and it is named: a handle that may
                # not be closed is never forgotten and it is never
                # replaced by a copy of an error message.
                self._retain_resource('job', self.job, error.code)
            self.state = 'UNKNOWN_RETAINED'
            raise
        self.job_kill_on_close = True
        self.state = 'ARMED'
        # The budget is checked after the creation of the job: a job that
        # was created after the deadline arrived is only cleaned up.
        self.check_startup_budget('ARM:DONE')
        return self.evidence()

    # -- the launch of the roles ------------------------------------------
    def launch(self):
        """Create the roles of the round, one after the other.

        The launch has an independent ``finally``: a failure of a role,
        a refusal of the broker and a cancellation all release the
        resources of the round before the failure leaves this method.
        The cancellation itself is not swallowed: it continues to
        propagate after the cleanup.
        """
        if self.state != 'ARMED':
            raise BrokerError('BROKER_STATE_INVALID', self.state)
        try:
            for role in self.plan.roles:
                # The shared budget of the startup is checked before
                # every role: a role that is created after the deadline
                # of the round arrived is a role that nobody may stop.
                self.check_startup_budget('ROLE:' + role['role'])
                self._launch_role(role)
        except BaseException:
            # Any failure of the launch, a cancellation included, ends
            # the round closed: the job, the pipes and the original
            # handles of this round are released here.
            self._abort_round('LAUNCH_ABORTED')
            raise
        self.state = 'RUNNING'
        return self.evidence()

    def _launch_role(self, role):
        name = role['role']
        owned = [record['pid'] for record in self.records if record['pid']]
        command = role_command(role, self.run_root, owned)
        record = {'role': name,
                  'executable': command['executable'],
                  'executable_sha256': role['tools'][0]['sha256'],
                  'arguments': list(command['arguments']),
                  'working_directory': command['working_directory'],
                  'log': role['log'],
                  'created': False, 'assigned': False, 'resumed': False,
                  'pid': None, 'creation_time': None,
                  'terminated': False, 'exited': False, 'exit_code': None,
                  'process_handle_closed': False, 'thread_handle_closed': False,
                  'stdout_bytes': 0, 'stderr_bytes': 0,
                  'stdout_overflow': False, 'stderr_overflow': False,
                  'failure': None,
                  'pending_handles': []}
        self.records.append(record)
        try:
            self._prepare_directories(role)
        except OSError as error:
            record['failure'] = 'BROKER_ROLE_DIRECTORY_FAILED'
            self.failures.append({'stage': 'role_directory', 'role': name,
                                  'error_type': type(error).__name__})
            self._abort_round('ROLE_DIRECTORY_FAILED')
            raise BrokerError('BROKER_ROLE_DIRECTORY_FAILED', name)
        try:
            # The shared budget of the startup is checked **before** every
            # pipe: a pipe that is created after the deadline of the round
            # arrived is a pipe that nobody may close.
            self.check_startup_budget('PIPE:stdout:' + name)
            stdout_read, stdout_write = self.win32.create_pipe('stdout')
            # The two ends are handed over to the core in one step: the
            # façade forgets them and the core registers them, so that
            # the two tables never name the same handle.
            self._adopt_from_api([(stdout_read, 'pipe_read'),
                                  (stdout_write, 'pipe_write')], name)
            self.check_startup_budget('PIPE:stderr:' + name)
            stderr_read, stderr_write = self.win32.create_pipe('stderr')
            self._adopt_from_api([(stderr_read, 'pipe_read'),
                                  (stderr_write, 'pipe_write')], name)
            self.check_startup_budget('PIPE_DONE:' + name)
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'create_pipe', 'role': name, 'code': error.code})
            self._abort_round('PIPE_FAILED')
            raise
        try:
            # The shared budget of the startup is checked **before** the
            # creation: a role that is created after the deadline of the
            # round arrived would be a role that nobody may stop.
            self.check_startup_budget('CREATE:' + name)
            created = self.win32.create_process_suspended(
                executable=command['executable'], arguments=command['arguments'],
                working_directory=command['working_directory'],
                stdout_handle=stdout_write, stderr_handle=stderr_write,
                environment=command['environment'])
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'create_process', 'role': name,
                                  'code': error.code})
            # The façade keeps the original handles of a process that it
            # could not hand over.  They are named here: the core holds
            # the façade and the recovery of the façade can reach them.
            retained = self._api_retained()
            if retained:
                self.failures.append({'stage': 'create_process_retained',
                                      'role': name, 'retained': retained})
            self._abort_round('CREATE_FAILED')
            raise
        # The original handles of the process enter the pending table of
        # the round in the moment of their creation and the core takes
        # them right away: it is their owner from now on and it closes
        # them when it releases the records.
        #
        # The registration happens **before** the check of the shared
        # budget that follows the creation and before every other step
        # that may raise.  A process that was created after the deadline
        # arrived is only cleaned up and it is never owned by nobody:
        # the lease of the round may end, the ownership of the handles
        # may not.
        self._pending.add(created.process, 'process', role=name)
        self._pending.add(created.thread, 'thread', role=name)
        self._pending.transfer(created.process, 'CORE')
        self._pending.transfer(created.thread, 'CORE')
        record['pending_handles'].append({'kind': 'process', 'owner': 'CORE'})
        record['pending_handles'].append({'kind': 'thread', 'owner': 'CORE'})
        record['created'] = True
        record['pid'] = created.pid
        record['creation_time'] = created.creation_time
        record['process_handle'] = created.process
        record['thread_handle'] = created.thread
        for failure in getattr(created, 'failures', ()):
            self.failures.append({'stage': 'create_process', 'role': name,
                                  'code': failure})
        try:
            # The budget is checked again after the creation: a process
            # that was created after the deadline arrived is only
            # cleaned up, it is never assigned and it is never resumed.
            self.check_startup_budget('CREATED:' + name)
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'create_process', 'role': name,
                                  'code': error.code})
            # The façade keeps the original handles of a process that it
            # could not hand over.  They are named here: the core holds
            # the façade and the recovery of the façade can reach them.
            retained = self._api_retained()
            if retained:
                self.failures.append({'stage': 'create_process_retained',
                                      'role': name, 'retained': retained})
            self._abort_round('CREATE_FAILED')
            raise
        # The write ends belong to the child now; the broker keeps the read
        # ends only.  The copies of the broker are closed and they leave
        # the pending table: they are not pending any more.
        self._release_pending(stdout_write)
        self._release_pending(stderr_write)
        try:
            # The shared budget is checked before the assignment and
            # before the resume: a thread that is resumed after the
            # deadline of the round arrived is a service that runs
            # outside of the round.
            self.check_startup_budget('ASSIGN:' + name)
            self.win32.assign_process_to_job(self.job, created.process)
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'assign', 'role': name, 'code': error.code})
            # The process is still suspended: it never ran.  It is stopped
            # through its own original handle and its exit is confirmed.
            self._terminate_owned(created.process, record, 'ASSIGN_FAILED')
            self._abort_round('ASSIGN_FAILED')
            raise
        record['assigned'] = True
        try:
            self.check_startup_budget('RESUME:' + name)
            self.win32.resume_thread(created.thread)
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'resume', 'role': name, 'code': error.code})
            self._abort_round('RESUME_FAILED')
            raise
        record['resumed'] = True
        try:
            self.check_startup_budget('READER:' + name)
            self._start_reader(record, stdout_read, 'stdout')
            self.check_startup_budget('READER:' + name)
            self._start_reader(record, stderr_read, 'stderr')
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'reader', 'role': name, 'code': error.code})
            self._abort_round('READER_FAILED')
            raise

    def _release_pending(self, handle):
        """Release one pending handle that the child took over."""
        item = self._pending.take(handle)
        if item is None:
            return False
        try:
            self.win32.close_handle(handle)
        except BrokerError as error:
            self.failures.append({'stage': 'close_stream', 'kind': item['kind'],
                                  'role': item['role'], 'code': error.code})
            self._pending.add(handle, item['kind'], role=item['role'])
            return False
        except (KeyboardInterrupt, SystemExit) as error:
            # A cancellation never becomes an ordinary evidence: it is
            # named and it is raised, so that the cleanups that follow
            # it still run.
            self.failures.append({'stage': 'close_stream', 'kind': item['kind'],
                                  'role': item['role'],
                                  'error_type': type(error).__name__,
                                  'cancellation': True})
            self._pending.add(handle, item['kind'], role=item['role'])
            raise
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self.failures.append({'stage': 'close_stream', 'kind': item['kind'],
                                  'role': item['role'],
                                  'error_type': type(error).__name__})
            self._pending.add(handle, item['kind'], role=item['role'])
            return False
        return True

    def _prepare_directories(self, role):
        """Create the fresh directories of a role.

        A directory that already exists is refused: a stale log, a stale
        pid lease or a stale sampler output of an earlier round may never
        be read as the output of this round.

        The user directory of the ComfyUI role is the directory that the
        plan closed and not a fixed name: the round creates the
        directory that the command of the role really uses.
        """
        name = role['role']
        if name == 'COMFY':
            (Path(self.run_root) / 'temp' / 'service-os').mkdir(parents=True,
                                                                exist_ok=True)
            (Path(self.run_root) / role['data']['user_directory']).mkdir(
                parents=True, exist_ok=True)
        elif name == 'SAMPLER':
            (Path(self.run_root) / 'temp' / 'resource-sampler').mkdir(
                parents=True, exist_ok=False)

    def _start_reader(self, record, handle, stream):
        """Hand the read end of a pipe over to its reader.

        The reader is the owner of the read end from now on: the
        handover changes the owner of the handle and nothing else.  The
        handle stays in the pending table of the round until it is
        really closed, and the reader closes it when it is stopped.

        The reader **object** is registered as the owner of the handle
        and not only its name: the pending pass asks the reader whether
        it is still alive before it closes the read end under it.
        """
        reader = _BoundedStreamReader(self.win32, handle, limit=MAX_STREAM_BYTES,
                                      name=record['role'] + '-' + stream)
        self.readers.append(reader)
        self._pending.transfer(handle, 'READER', owner_ref=reader)
        record['pending_handles'].append({'kind': 'pipe_read',
                                          'stream': stream, 'owner': 'READER'})
        reader.start()

    def _close_handle(self, kind, handle):
        """Close one owned handle and name a failure of the close.

        A handle that was closed leaves the pending table of the round
        and it leaves the retained resources of the round: a handle that
        is really closed is never named as a resource any more.  A
        handle that could not be closed stays pending: it is a resource
        that this round still owns and it is named.

        A **cancellation** in the middle of a close is never turned into
        an ordinary evidence: it is named and it is raised, so that the
        finalizer that follows it still runs and the cancellation
        continues to propagate after the cleanup.
        """
        try:
            self.win32.close_handle(handle)
        except BrokerError as error:
            self.failures.append({'stage': 'close_handle', 'kind': kind,
                                  'code': error.code})
            return False
        except (KeyboardInterrupt, SystemExit) as error:
            self.failures.append({'stage': 'close_handle', 'kind': kind,
                                  'error_type': type(error).__name__,
                                  'cancellation': True})
            raise
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self.failures.append({'stage': 'close_handle', 'kind': kind,
                                  'error_type': type(error).__name__})
            return False
        self._pending.take(handle)
        # The handle is really closed: it is not a retained resource of
        # the round any more.
        self._release_resource(kind, handle)
        return True

    def _close_readers(self):
        """Stop the readers of the children and close their read handles.

        The wait of a reader is bounded by the ONE cleanup deadline of the
        round and its state is recorded.  A reader that is still blocked
        when the wait is over is a *fact* of this round and it is
        reported as such: a daemon thread that is still running is not a
        finished thread, and the read end of such a reader is not closed
        under it.

        Every reader is independent of the others: a reader that could
        not be joined never skips the coordination of the readers that
        follow it, and a reader whose thread never started is never
        joined at all.  A read end that was closed with a confirmed
        close is never closed a second time.
        """
        for reader in self.readers:
            try:
                self._close_one_reader(reader)
            except (KeyboardInterrupt, SystemExit) as error:
                # A cancellation never skips the readers that follow it:
                # it is named and it is raised after every reader was
                # coordinated.
                self.failures.append({'stage': 'close_readers',
                                      'name': reader.name,
                                      'error_type': type(error).__name__,
                                      'cancellation': True})
                self._readers_cancelled.append(error)
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                self.failures.append({'stage': 'close_readers',
                                      'name': reader.name,
                                      'error_type': type(error).__name__})
        if self._readers_cancelled:
            raise self._readers_cancelled[0]

    def _close_one_reader(self, reader):
        """Coordinate one reader of the round on its own.

        The read end of a reader is closed **only** when the reader
        really stopped.  Every branch of the coordination asks the
        reader whether it is still alive: a wait that was cancelled and
        a join that failed are not a proof that the reader ended, and
        the read end of a live reader is never closed under it.

        A cancellation in the middle of the coordination never skips the
        readers that follow it and it never skips the protection of the
        read end of the reader that is still alive.
        """
        if reader.handle is None:
            # The read end of this reader was closed with a confirmed
            # close already.
            return
        state = {'name': reader.name,
                 'finished': reader.finished.is_set(),
                 'joined': False,
                 'alive': reader.is_alive(),
                 'error': reader.error}
        if reader.ident is None and not reader.is_alive():
            # The thread of this reader never started.  A thread that
            # never started is never joined: the join of a thread that
            # was not started is an error of the caller and not a fact
            # of the round.  The handle of this reader is closed here,
            # because no thread of the round reads it.
            state['started'] = False
            state['alive'] = False
            state['finished'] = True
            self.reader_states.append(state)
            if self._close_handle('stream', reader.handle):
                reader.handle = None
            else:
                self._retain_resource('pipe_read', reader.handle,
                                      'BROKER_HANDLE_CLOSE_FAILED')
            return
        state['started'] = True
        cancelled = None
        try:
            remaining = self.remaining_cleanup_seconds()
            wait = min(READER_JOIN_SECONDS, remaining)
            if wait > 0:
                reader.finished.wait(wait)
            # The remaining budget is recomputed before the join: a wait
            # that already consumed part of the budget never receives the
            # whole budget again.
            remaining = self.remaining_cleanup_seconds()
            reader.join(min(READER_JOIN_SECONDS, remaining))
        except (KeyboardInterrupt, SystemExit) as error:
            # A cancellation never decides the fate of the read end: the
            # reader is asked again whether it is still alive.
            cancelled = error
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self.failures.append({'stage': 'close_reader',
                                  'name': reader.name,
                                  'error_type': type(error).__name__})
        alive = reader.is_alive()
        state['finished'] = reader.finished.is_set()
        state['joined'] = not alive
        state['alive'] = alive
        self.reader_states.append(state)
        if alive:
            # The reader still holds the read end.  The handle is not
            # closed under a running reader: it leaves the pending
            # table with its owner and the round keeps the fact.
            self._pending.take(reader.handle)
            self.reader_states[-1]['handle_retained'] = True
            self.failures.append({'stage': 'reader_not_stopped',
                                  'name': reader.name,
                                  'code': 'BROKER_READER_NOT_STOPPED'})
            if cancelled is not None:
                raise cancelled
            return
        if self._close_handle('stream', reader.handle):
            reader.handle = None
        else:
            self._retain_resource('pipe_read', reader.handle,
                                  'BROKER_HANDLE_CLOSE_FAILED')
        if cancelled is not None:
            raise cancelled

    def _terminate_owned(self, handle, record, reason):
        """Stop one owned process through its own original handle.

        No pid is used and no name is used: only the handle that this core
        created is passed to the operating system.  The wait is bounded
        by the ONE cleanup deadline of the round: an expired deadline
        never starts a new wait.
        """
        try:
            self.win32.terminate_process(handle, 1)
            record['terminated'] = True
        except BrokerError as error:
            self.failures.append({'stage': 'terminate', 'reason': reason,
                                  'code': error.code})
            return False
        timeout = self._wait_timeout_ms()
        if timeout <= 0:
            self.failures.append({'stage': 'wait', 'reason': reason,
                                  'code': 'BROKER_CLEANUP_DEADLINE_EXCEEDED'})
            return True
        try:
            record['exited'] = bool(self.win32.wait_process(handle, timeout))
        except BrokerError as error:
            self.failures.append({'stage': 'wait', 'reason': reason, 'code': error.code})
        if record['exited']:
            try:
                record['exit_code'] = self.win32.exit_code(handle)
            except BrokerError as error:
                self.failures.append({'stage': 'exit_code', 'reason': reason,
                                      'code': error.code})
        return True

    # -- the stop of the round ---------------------------------------------
    def stop(self, reason='STOP', *, force_unknown=False, deadline=None):
        """Stop the round and release every handle that this core holds.

        The stop is bounded and it is idempotent: a repeated stop does not
        terminate anything twice and it does not change the evidence of
        the round.  Every handle is reported on its own, so a handle that
        could not be closed stays visible and the round becomes unknown
        instead of a silent success.

        The steps of the stop are **independent bounded finalizers**.  The
        termination of the job, the wait for the original processes, the
        stop of the readers, the query of the job, the release of the
        original handles, the release of the job, the release of the
        pending resources and the diagnosis of the round each run in
        their own guard: a failure of one of them never skips the others.
        The first failure of the round is the one that leaves the method
        and the later failures are named next to it.

        A stop that did not release everything does **not** latch the
        round as released: the same owner may try the remaining work
        again, inside the ONE cleanup deadline of the round.  A handle
        that was closed with a confirmed close is never closed a second
        time.
        """
        if self._released:
            return self.evidence()
        if self.state == 'STOPPING' and self._cleanup_deadline_value is not None:
            # A stop that is already running: the owner of the round does
            # not start a second one.
            return self.evidence()
        self.state = 'STOPPING'
        if self.stop_reason is None:
            self.stop_reason = reason
        # The ONE cleanup deadline of the round.  It is generated here,
        # at the first stop, and every step below uses this very value.
        deadline = self.cleanup_deadline(deadline)
        primary = None

        def step(stage, action):
            """Run one bounded finalizer of the stop.

            A finalizer that fails never skips the finalizers that follow
            it.  A cancellation is named as a cancellation and it is
            never turned into an ordinary evidence: it becomes the
            primary failure of the round when nothing else failed, and
            it is raised after every finalizer was executed.
            """
            nonlocal primary
            try:
                action()
            except BaseException as error:  # noqa: BLE001 - the cleanup still runs
                cancelled = isinstance(error, (KeyboardInterrupt, SystemExit))
                if primary is None:
                    primary = error
                self.failures.append({'stage': stage,
                                      'error_type': type(error).__name__,
                                      'cancellation': cancelled})

        step('diagnostic', self._collect_stream_counts)
        step('terminate_job', self._terminate_the_job)
        step('wait_processes', self._wait_the_processes)
        step('close_readers', self._close_readers)
        step('query_job', self._query_job)
        step('release_records', self._release_the_records)
        step('release_job', self._release_the_job)
        step('pending_resources', self._close_pending)

        released = self._is_released()
        # The latch of a completed release is only set when the release
        # was really proven.  An unfinished cleanup never blocks the
        # recovery of the same owner.
        self._released = released
        self.state = 'UNKNOWN_RETAINED' if (force_unknown or not released) else 'RELEASED'
        if primary is not None:
            # The first failure of the round is not swallowed: the caller
            # sees it after the round was cleaned up.
            raise primary
        return self.evidence()

    def _pending_handle_in_use(self, item):
        """Whether the owner of a pending handle is still using it.

        The owner of a handle is an **object** and not a name: the
        reader that owns a read end is asked whether it is still alive.
        A read end that a live reader still reads from is never closed
        under it, whatever the branch that reached the pending pass did
        before.
        """
        owner = item.get('owner_ref')
        if owner is None:
            return False
        alive = getattr(owner, 'is_alive', None)
        if not callable(alive):
            return False
        try:
            return bool(alive())
        except Exception:  # noqa: BLE001 - the failure stays visible
            # A reader that cannot answer is a reader that may still be
            # alive: the handle is protected.
            return True

    def _close_pending(self):
        """Close the handles that are still pending and name the failures.

        The pending pass is the **last** close of the round and it may
        close a handle that the release of the records or the release of
        the job could not close.  Every handle that it really closes is
        reported to the core: the job of the round, the records of the
        round and the retained resources of the round never name a
        handle that is closed.

        The pass never closes a handle whose owner is still using it:
        the guard is the fact of the owner and not the name of an
        owner.
        """
        retained = self._pending.close_all(self.failures,
                                           on_closed=self._note_closed_handle,
                                           protect=self._pending_handle_in_use)
        if retained:
            self.failures.append({'stage': 'pending_resources',
                                  'count': len(retained),
                                  'code': 'BROKER_PENDING_RESOURCES_RETAINED'})

    def _note_closed_handle(self, item):
        """Learn that the pending pass really closed one handle.

        The bookkeeping of the core has to agree with the fact of the
        close: a handle that is closed may never be named by the job of
        the round, by the records of the round or by the retained
        resources of the round.  Only the handle that was really closed
        is forgotten: a handle that could not be closed keeps its owner
        and it stays named.
        """
        handle = item['handle']
        kind = item['kind']
        if self.job is handle:
            self.job = None
            self.job_closed = True
        for record in self.records:
            if record.get('process_handle') is handle:
                record['process_handle_closed'] = True
                record['process_handle'] = None
            if record.get('thread_handle') is handle:
                record['thread_handle_closed'] = True
                record['thread_handle'] = None
        self._release_resource(kind, handle)

    def _terminate_the_job(self):
        """Terminate the job of the round.

        The termination happens once.  A repeated stop does not terminate
        the job of the round a second time.
        """
        if self.job is None or self.job_terminated:
            return
        try:
            self.win32.terminate_job(self.job, 1)
            self.job_terminated = True
        except BrokerError as error:
            self.failures.append({'stage': 'terminate_job', 'code': error.code})

    def _wait_the_processes(self):
        """Wait for the original processes of the round.

        Every process is independent of the others: a process that could
        not be waited for does not skip the wait of the next one, and an
        ordinary failure of the wait of one process does not interrupt
        the group.  The wait is bounded by the ONE cleanup deadline of
        the round and the remaining budget is recomputed before every
        single wait: an expired deadline never starts a new wait.
        """
        for record in self.records:
            try:
                self._wait_one_process(record)
            except (KeyboardInterrupt, SystemExit) as error:
                # A cancellation never skips the processes that follow it:
                # it is named and it is raised after every process was
                # coordinated.
                self.failures.append({'stage': 'wait', 'role': record['role'],
                                      'error_type': type(error).__name__,
                                      'cancellation': True})
                self._processes_cancelled.append(error)
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                self.failures.append({'stage': 'wait', 'role': record['role'],
                                      'error_type': type(error).__name__})
        if self._processes_cancelled:
            raise self._processes_cancelled[0]

    def _wait_one_process(self, record):
        """Wait for one original process of the round, on its own."""
        handle = record.get('process_handle')
        if handle is None or record['exited']:
            return
        if not record['resumed']:
            # The process never ran: it is stopped through its own
            # suspended handle.
            self._terminate_owned(handle, record, 'SUSPENDED_AT_STOP')
            return
        timeout = self._wait_timeout_ms()
        if timeout <= 0:
            self.failures.append({'stage': 'wait', 'role': record['role'],
                                  'code': 'BROKER_CLEANUP_DEADLINE_EXCEEDED'})
            return
        try:
            record['exited'] = bool(self.win32.wait_process(handle, timeout))
        except BrokerError as error:
            self.failures.append({'stage': 'wait', 'role': record['role'],
                                  'code': error.code})
        except (KeyboardInterrupt, SystemExit):
            # A cancellation is never turned into an ordinary evidence:
            # it leaves the wait of this process and it is raised after
            # every other process was coordinated.
            raise
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self.failures.append({'stage': 'wait', 'role': record['role'],
                                  'error_type': type(error).__name__})
            return
        if record['exited']:
            try:
                record['exit_code'] = self.win32.exit_code(handle)
            except BrokerError as error:
                self.failures.append({'stage': 'exit_code', 'role': record['role'],
                                      'code': error.code})
            except (KeyboardInterrupt, SystemExit):
                # The cancellation of the exit code is a cancellation of
                # the round and it is never swallowed by the evidence.
                raise
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                self.failures.append({'stage': 'exit_code', 'role': record['role'],
                                      'error_type': type(error).__name__})

    def _wait_timeout_ms(self):
        """The milliseconds that are left until the cleanup deadline."""
        remaining = self.remaining_cleanup_seconds()
        if remaining <= 0:
            return 0
        return max(1, min(WAIT_MILLISECONDS, int(remaining * 1000)))

    def _release_the_records(self):
        """Close the original handles of the processes of the round.

        A handle that was closed with a confirmed close is forgotten and
        it is never closed a second time.  A handle that could not be
        closed keeps its original reference and its owner.

        Every handle of every record is closed on its own: a failure of
        one of them never skips the handles that follow it, and a
        cancellation is raised after every handle was coordinated.
        """
        cancellations = []
        for record in self.records:
            for key, kind in (('thread_handle', 'thread'),
                              ('process_handle', 'process')):
                handle = record.get(key)
                if handle is None:
                    continue
                try:
                    closed = self._close_handle(kind, handle)
                except (KeyboardInterrupt, SystemExit) as error:
                    # A cancellation never skips the handles that follow
                    # it: it is named and it is raised after every
                    # handle was coordinated.
                    record[kind + '_handle_closed'] = False
                    self.failures.append({'stage': 'close_handle', 'kind': kind,
                                          'role': record.get('role'),
                                          'error_type': type(error).__name__,
                                          'cancellation': True})
                    self._retain_resource(kind, handle, 'BROKER_HANDLE_CLOSE_FAILED')
                    cancellations.append(error)
                    continue
                record[kind + '_handle_closed'] = closed
                if closed:
                    record[key] = None
                else:
                    self._retain_resource(kind, handle, 'BROKER_HANDLE_CLOSE_FAILED')
        if cancellations:
            raise cancellations[0]

    def _release_the_job(self):
        """Close the original handle of the job of the round.

        A job handle that could not be closed is **not** forgotten: the
        core keeps the original reference and the round stays unknown.
        """
        if self.job is None:
            return
        handle = self.job
        closed = self._close_handle('job', handle)
        self.job_closed = closed
        if closed:
            self.job = None
            self._release_resource('job', handle)
        else:
            self._retain_resource('job', handle, 'BROKER_HANDLE_CLOSE_FAILED')

    def _is_released(self):
        """Whether the round is a proven release.

        A release needs every fact and not only the absence of a failure:
        every owned process has to have exited, every handle has to have
        been closed, every reader has to have been joined without a read
        error and the job has to have been queried and found empty.
        """
        if self.failures:
            return False
        if not all(record['exited'] for record in self.records if record['created']):
            return False
        if not all(record['process_handle_closed'] and record['thread_handle_closed']
                   for record in self.records):
            return False
        if not self.job_closed:
            return False
        if not (self.job_active_known and self.job_active == 0):
            return False
        if not self.reader_states:
            return False
        for state in self.reader_states:
            if not state['finished'] or state['alive'] or state['error']:
                return False
        if self._pending.pending():
            return False
        return True

    def _query_job(self):
        """Ask the job how many processes it still holds.

        The answer is bounded.  An unknown answer and an answer that is
        over the cap are both *unknown*: neither of them is a zero.

        The query only runs while the job handle is still open.  A
        handle that was already closed keeps the answer that it produced:
        a second stop never destroys the proof of the first one.
        """
        if self.job is None:
            return
        try:
            identifiers = self.win32.job_process_ids(self.job)
        except BrokerError as error:
            self.failures.append({'stage': 'query_job', 'code': error.code})
            self.job_active_known = False
            self.job_active = None
            return
        if len(identifiers) > MAX_DESCENDANTS:
            self.failures.append({'stage': 'query_job', 'code': 'BROKER_DESCENDANT_LIMIT'})
            self.job_active_known = False
            self.job_active = None
            return
        self.job_active_known = True
        self.job_active = len(identifiers)
        self.job_process_ids = list(identifiers)

    def _collect_stream_counts(self):
        total = 0
        for record in self.records:
            for stream, key in (('stdout', 'stdout_bytes'), ('stderr', 'stderr_bytes')):
                for reader in self.readers:
                    if reader.name.endswith(record['role'] + '-' + stream):
                        record[key] = reader.observed
                        record[stream + '_overflow'] = reader.overflow
                        if reader.overflow and not self._stream_failure_reported:
                            self._stream_failure_reported = True
                            self.failures.append({'stage': 'stream_limit',
                                                  'role': record['role'],
                                                  'stream': stream,
                                                  'code': 'BROKER_STREAM_LIMIT_EXCEEDED'})
        for reader in self.readers:
            total += reader.kept
        self.new_text_bytes = total
        if total > MAX_NEW_TEXT_BYTES and not self._text_failure_reported:
            self._text_failure_reported = True
            self.failures.append({'stage': 'new_text_limit',
                                  'code': 'BROKER_NEW_TEXT_LIMIT_EXCEEDED'})

    def overflowed(self):
        """Whether a bound of the text of the children was exceeded."""
        self._collect_stream_counts()
        if self.new_text_bytes > MAX_NEW_TEXT_BYTES:
            return True
        return any(record['stdout_overflow'] or record['stderr_overflow']
                   for record in self.records)

    def _abort_round(self, reason):
        """Fail the round closed.

        The stop of the round is bounded and it only touches the handles
        and the job of this round.  The state of the round is unknown
        afterwards, whatever the stop itself proved.  The abort is
        idempotent: a failure that already aborted the round does not
        abort it a second time and it does not report it twice.
        """
        if not self._abort_reported:
            self._abort_reported = True
            self.failures.append({'stage': 'round', 'code': reason})
        try:
            self.stop(reason, force_unknown=True)
        except BrokerError as error:
            self.failures.append({'stage': 'abort', 'code': error.code})
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self.failures.append({'stage': 'abort', 'error_type': type(error).__name__})
        self.state = 'UNKNOWN_RETAINED'

    # -- the evidence ------------------------------------------------------
    def summary(self):
        """The bounded summary of the round that fits into one frame."""
        return {'state': self.state,
                'roles': [{'role': record['role'], 'pid': record['pid'],
                           'created': record['created'], 'assigned': record['assigned'],
                           'resumed': record['resumed'], 'exited': record['exited']}
                          for record in self.records],
                'job_active_known': self.job_active_known,
                'job_active': self.job_active,
                'failures': len(self.failures)}

    def evidence(self):
        return {
            'kind': 'lvw.s3-native-broker-evidence/1',
            'state': self.state,
            'run_id': self.plan.run_id,
            'candidate_sha': self.plan.candidate_sha,
            'authorization_sha256': self.plan.authorization_sha256,
            'grant_authority': 'NOT_VERIFIED',
            'stop_reason': self.stop_reason,
            'broker': self.broker_identity,
            'job': {'created': self.job is not None or self.job_closed,
                    'kill_on_job_close': self.job_kill_on_close,
                    'breakaway_allowed': False,
                    'terminated': self.job_terminated,
                    'active_process_count': self.job_active,
                    'active_process_count_known': self.job_active_known,
                    'process_ids': list(self.job_process_ids),
                    'handle_closed': self.job_closed},
            'roles': [{key: value for key, value in record.items()
                       if key not in ('process_handle', 'thread_handle')}
                      for record in self.records],
            'new_text_bytes': self.new_text_bytes,
            'readers': list(self.reader_states),
            'pending_resources': self._pending.pending(),
            # The resources that this round could not release and the
            # original handles that the Windows façade still holds.  They
            # are named with their original references: a resource that
            # was not released is never replaced by a copy of a message.
            'retained_resources': [{'kind': item['kind'], 'owner': item['owner'],
                                    'code': item['code'],
                                    'handle_repr': repr(item['handle'])}
                                   for item in self._retained_resources],
            'api_retained': self._api_retained(),
            'cleanup_deadline': self._cleanup_deadline_value,
            'failures': list(self.failures),
            # The claims that this package does not make.
            'native_execution_proven': False,
            'native_cleanup_proven': False,
            'gpu_released_proven': False,
            'port_released_proven': False,
            'sampler_proven': False,
            'parent_crash_recovery_proven': False,
            'windows_stdin_eof_proven': False,
            'admission_produced': False,
            'stage_pass_claim': False,
            'product_gate0': False,
        }


# -- the bounded private pipe ----------------------------------------------

def _require_deadline(deadline, code='BROKER_DEADLINE_INVALID'):
    """Check one absolute deadline.

    A deadline is a finite number of seconds of the monotonic clock of
    the host.  A boolean, a string, an infinite value and a value that
    is not a number at all are refused: a deadline that was understood
    as something else would silently unbound the round.
    """
    if deadline is None:
        return None
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
        raise BrokerError(code)
    value = float(deadline)
    if not math.isfinite(value):
        raise BrokerError(code)
    return value


class _PosixSyscalls:
    """The POSIX system calls of the private pipe.

    The table is a narrow and explicit interface.  It is the only place
    where the private channel touches the operating system, and it can
    be replaced by a synthetic table in the offline validation: the
    production logic of the channel is then driven by a table that
    records the calls instead of by the kernel.
    """

    def __init__(self):
        self._pollers = {}

    def fileno(self, file_object):
        return file_object.fileno()

    def set_blocking(self, descriptor, blocking):
        os.set_blocking(descriptor, blocking)

    def _poller(self, descriptor):
        poller = self._pollers.get(descriptor)
        if poller is None:
            poller = select.poll()
            poller.register(descriptor,
                            select.POLLIN | select.POLLOUT
                            | select.POLLERR | select.POLLHUP)
            self._pollers[descriptor] = poller
        return poller

    def poll(self, descriptor, mask, timeout):
        """Whether the descriptor is ready for the requested operation."""
        ready = self._poller(descriptor).poll(max(0.0, timeout) * 1000)
        for number, event in ready:
            if event & select.POLLNVAL:
                raise BrokerError('BROKER_PIPE_DESCRIPTOR_INVALID')
            if mask == 'read' and event & (select.POLLIN | select.POLLHUP
                                           | select.POLLERR):
                return True
            if mask == 'write' and event & (select.POLLOUT | select.POLLHUP
                                            | select.POLLERR):
                return True
        return False

    def read(self, descriptor, size):
        return os.read(descriptor, size)

    def write(self, descriptor, data):
        return os.write(descriptor, data)

    def close(self, file_object):
        file_object.close()


class _PosixPipeEndpoint:
    """One end of a private pipe on a POSIX host.

    The endpoint owns the original descriptor of the pipe and it closes
    it itself.  The descriptor is set to non blocking exactly once, by
    the owner that created it, and the read and the write poll it in
    slices of at most 50 milliseconds.  Every slice checks the cancel
    flag and the absolute deadline, so that a peer that never reads can
    never hold the supervisor of the round.

    The endpoint never changes the blocking mode of a descriptor that it
    does not own and it never closes a descriptor that it does not own.
    It never relies on the lock of a buffered object either: the close
    of a buffered object may wait for a reader that holds its lock, and
    the close of this endpoint is the close of the owner of the
    descriptor.
    """

    def __init__(self, file_object, *, name, syscalls=None, clock=None):
        self._file = file_object
        self._name = name
        self._syscalls = syscalls or _PosixSyscalls()
        self._clock = clock or time.monotonic
        self._descriptor = self._syscalls.fileno(file_object)
        self._non_blocking = False
        self._closed = False
        # The absolute deadline that is bound to this endpoint.  It may
        # only shorten the deadline that is already bound and it is read
        # again on every slice: a deadline that was bound after a read
        # started still tightens that read.
        self._deadline = None
        self.facts = {'name': name, 'owner': 'POSIX_ENDPOINT',
                      'descriptor': self._descriptor}

    def bind_deadline(self, deadline):
        """Bind an absolute deadline to this endpoint.

        The deadline may only shorten the deadline that is already
        bound.  It is a property of the endpoint and not a local
        argument of one call: a call that passed ``None`` before the
        binding still observes the bound deadline.
        """
        value = _require_deadline(deadline)
        if value is None:
            return self._deadline
        if self._deadline is not None and value > self._deadline:
            return self._deadline
        self._deadline = value
        return value

    def _effective_deadline(self, deadline=None):
        """The deadline that this call really uses."""
        value = _require_deadline(deadline)
        if self._deadline is None:
            return value
        if value is None:
            return self._deadline
        return min(value, self._deadline)

    def prepare(self):
        """Set the descriptor to non blocking, once, by its owner."""
        if self._non_blocking or self._closed:
            return
        self._syscalls.set_blocking(self._descriptor, False)
        self._non_blocking = True
        self.facts['non_blocking'] = True

    def _check(self, deadline, cancel):
        if cancel is not None and cancel.is_set():
            raise BrokerError('BROKER_PIPE_CANCELLED', self._name)
        if deadline is not None and self._clock() >= deadline:
            raise BrokerError('BROKER_PIPE_TIMEOUT', self._name)

    def read(self, deadline=None, cancel=None):
        """Read one block of the pipe, bounded by the deadline."""
        self.prepare()
        while True:
            self._check(self._effective_deadline(deadline), cancel)
            if not self._syscalls.poll(self._descriptor, 'read',
                                       POLL_SLICE_SECONDS):
                continue
            try:
                data = self._syscalls.read(self._descriptor, PIPE_READ_BYTES)
            except BlockingIOError:
                # The pipe was not ready after all: the slice is repeated.
                continue
            except OSError as error:
                raise BrokerError('BROKER_PIPE_READ_FAILED',
                                  '%s:%s' % (self._name, type(error).__name__))
            if not data:
                return b''
            return data

    def write(self, data, deadline=None, cancel=None):
        """Write the whole block, bounded by the deadline."""
        self.prepare()
        view = memoryview(bytes(data))
        total = 0
        while total < len(view):
            self._check(self._effective_deadline(deadline), cancel)
            if not self._syscalls.poll(self._descriptor, 'write',
                                       POLL_SLICE_SECONDS):
                continue
            try:
                count = self._syscalls.write(self._descriptor, view[total:])
            except BlockingIOError:
                # The pipe was full after all: the slice is repeated.
                continue
            except OSError as error:
                raise BrokerError('BROKER_PIPE_WRITE_FAILED',
                                  '%s:%s' % (self._name, type(error).__name__))
            if count <= 0:
                raise BrokerError('BROKER_PIPE_WRITE_FAILED', self._name)
            total += count
        return total

    def close(self):
        """Close the original descriptor of this endpoint, exactly once.

        The endpoint is closed **only** when the close really happened.
        A close that failed keeps the descriptor and its owner: the
        endpoint may try it again and it is never marked as closed
        irreversibly.

        A close of an endpoint that is already closed keeps the fact
        that it is closed: the second close is idempotent and it never
        turns a proven close into a missing one.
        """
        if self._closed:
            self.facts['closed'] = True
            self.facts['already_closed'] = True
            self.facts['retained_workers'] = 0
            self.facts['worker_thread_handle_released'] = True
            return self.facts
        try:
            self._syscalls.close(self._file)
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.facts['closed'] = False
            self.facts['error_type'] = type(error).__name__
            self.facts['retained_workers'] = 0
            self.facts['worker_thread_handle_released'] = True
            return self.facts
        self._closed = True
        self.facts['closed'] = True
        # This host has no worker thread for an end of the pipe: the
        # blocking calls are made by the reader of the channel itself.
        # There is therefore no original worker handle that could be
        # outstanding, and the fact says so.
        self.facts['retained_workers'] = 0
        self.facts['worker_thread_handle_released'] = True
        return self.facts


class _WindowsPipeWorker(threading.Thread):
    """One worker of one end of a private pipe on a Windows host.

    The worker owns one blocking operation at a time.  It takes the
    request from its queue, it performs the blocking call on the
    original handle of the pipe and it reports the real completion of
    the call.  The thread is created once for the endpoint and it is
    never created for a frame.

    The handle of the thread is the handle of the thread itself and
    never a self reported identifier: ``CancelSynchronousIo`` needs the
    original handle of the thread that performs the operation.

    The lifecycle of the worker is **explicit**.  The states are
    ``IDLE``, ``QUEUED``, ``IN_IO``, ``CANCELLING``, ``DONE`` and
    ``STOPPED``:

    * ``IDLE``      the worker waits for a request;
    * ``QUEUED``    a request waits for the worker;
    * ``IN_IO``     the worker is inside the blocking call;
    * ``CANCELLING`` a cancellation was asked for;
    * ``DONE``      the request of the worker completed;
    * ``STOPPED``   the thread of the worker really ended.

    ``DONE`` is not ``STOPPED``: the completion of a request says
    nothing about the thread of the worker, and the handle of the
    thread may only be closed after the thread really ended.

    The worker is the **only** owner of the handle of its own thread:
    it duplicated that handle and it closes it when its thread really
    ended.  A worker that did not stop keeps its handle and its owner:
    the handle is never closed under a live worker and it is never left
    to the garbage collector.
    """

    STATES = ('IDLE', 'QUEUED', 'IN_IO', 'CANCELLING', 'DONE', 'STOPPED')

    def __init__(self, api, handle, *, kind, action, name, clock=None):
        super().__init__(daemon=True, name=name)
        self.api = api
        self.handle = handle
        self.kind = kind
        self.action = action
        self._clock = clock or time.monotonic
        self._requests = queue.Queue(maxsize=1)
        # The event of the in-flight operation.  It is set while the
        # worker is inside the call and it is cleared again when the
        # call ended: an event that is never cleared would report a
        # permanent in-flight state.
        self.inside = threading.Event()
        self.done = threading.Event()
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.result = None
        self.error = None
        self.thread_handle = None
        self.thread_handle_released = False
        self.joined = False
        self.state = 'IDLE'
        # The number of the requests that were submitted and the number
        # of the requests that completed.  The two numbers are the real
        # completion of a request: the event alone could report the
        # completion of an older request.
        self._condition = threading.Condition()
        self._submitted = 0
        self._completed = 0
        # The flag of the cancellation.  It stops the worker from
        # accepting a new task before the cancellation is requested.
        self._cancelled = False
        # The name of the cancel flag is not ``_stop``: the base class of
        # the thread uses that name for its own method and a shadow of it
        # would break the join of the thread.
        self._stop_event = threading.Event()
        # The pause of the retry of a cancellation.  It is its **own**
        # event and it is never set: the retry of a cancellation may not
        # wait on the stop event of the worker, because the worker set
        # that event itself and the wait would return at once.
        self._pause = threading.Event()

    # -- the lifecycle ----------------------------------------------------
    def run(self):
        try:
            self.thread_handle = self.api.duplicate_current_thread_handle()
        except BrokerError as error:
            self.error = error.code
            self.done.set()
            self.ready.set()
            self.state = 'DONE'
            self.stopped.set()
            return
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.error = type(error).__name__
            self.done.set()
            self.ready.set()
            self.state = 'DONE'
            self.stopped.set()
            return
        self.ready.set()
        try:
            while not self._stop_event.is_set():
                try:
                    request = self._requests.get(timeout=0.1)
                except queue.Empty:
                    continue
                self.error = None
                self.result = None
                # The check of the cancellation and the publication of
                # the intent to enter the operation are **one** atomic
                # step under the lock of the worker.  A cancellation
                # that arrives between the check and the operation would
                # otherwise be answered by a worker that performs the
                # operation anyway: the cancellation and the operation
                # would be two uncoordinated facts.
                with self._condition:
                    cancelled = self._cancelled
                    if not cancelled:
                        self.state = 'IN_IO'
                        self.inside.set()
                if cancelled:
                    # The cancellation reached the worker before the
                    # operation started: the operation is not performed
                    # at all and the request is answered as finished.
                    self._complete()
                    continue
                try:
                    self.result = self.action(request)
                except BrokerError as error:
                    self.error = error.code
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    self.error = type(error).__name__
                finally:
                    self.inside.clear()
                    self._complete()
        finally:
            self.state = 'STOPPED'
            self.stopped.set()
            # The worker is the only owner of the handle of its own
            # thread and it closes it here, when its thread really ended.
            self.release_thread_handle()

    def _complete(self):
        """Report the real completion of the current request."""
        with self._condition:
            self._completed += 1
            self._condition.notify_all()
        self.done.set()
        self.state = 'DONE'

    def wait_ready(self, seconds):
        """Wait for the worker to have acquired the handle of its thread."""
        return self.ready.wait(max(0.0, seconds))

    def submit(self, request):
        """Hand one request to the worker.

        The hand over is bounded: the queue of the worker holds one
        request and a request that does not fit is refused with a named
        error.  A worker that is dead and a worker whose thread handle
        could not be created refuse the request as well.

        The hand over and the cancellation share **one** lock: a
        request that is submitted after the cancellation of the worker
        is refused and it never enters the queue.  The cancellation and
        the submission are therefore coordinated by the same generation
        of the worker and a request of an older generation is never
        taken for the completion of this one.

        The completion of a request is the number of the completed
        requests and not the event alone: the completion of an older
        request is never the completion of this one.
        """
        if not self.is_alive():
            raise BrokerError('BROKER_WORKER_NOT_ALIVE', self.kind)
        if self.thread_handle is None:
            raise BrokerError('BROKER_WORKER_NOT_READY',
                               '%s:%s' % (self.kind, self.error))
        with self._condition:
            if self._cancelled:
                # The cancellation of this worker arrived first: the
                # request is refused and it never enters the queue.
                raise BrokerError('BROKER_WORKER_CANCELLED', self.kind)
            self._submitted += 1
            generation = self._submitted
            try:
                self._requests.put(request, timeout=POLL_SLICE_SECONDS)
            except queue.Full:
                self._submitted -= 1
                self._condition.notify_all()
                raise BrokerError('BROKER_WORKER_QUEUE_FULL', self.kind)
            self.done.clear()
            self.state = 'QUEUED'
            return generation

    def wait_done(self, generation, timeout):
        """Wait for the completion of one request, bounded."""
        with self._condition:
            return self._condition.wait_for(
                lambda: self._completed >= generation, max(0.0, timeout))

    def request_cancel(self, deadline=None):
        """Ask for the cancellation of the operation of this worker.

        The request is not a completion.  The caller has to wait for the
        real completion of the worker and to join it.

        The cancellation stops the worker from accepting a new task
        **first** and it drives the worker to its end: the worker that
        is inside an operation is asked to leave it and the worker that
        waits for a request is asked to stop waiting.  A cancellation
        that reports ``NOT_FOUND`` is repeated, bounded by the shared
        deadline, until the worker reports that **this** generation is
        done or that the thread really stopped: a cancellation that was
        sent once and dropped is not a cancellation.

        The retry never waits on the stop event of the worker: the
        worker set that event itself, a moment before, and a wait that
        returns at once would end the retry after a single
        ``NOT_FOUND``.  The retry waits on its own pause instead, so
        that the request of the operating system is really repeated.

        The completion of an **older** generation never releases the
        retry: the real completion of the request of this generation is
        the number of the completed requests.
        """
        with self._condition:
            self._cancelled = True
            self.state = 'CANCELLING'
            self._condition.notify_all()
        # The worker is driven to its end: it stops waiting for a
        # request and it leaves the operation that it is inside as soon
        # as the cancellation of the operating system arrived.
        self._stop_event.set()
        if self.thread_handle is None:
            return 'NO_HANDLE'
        if deadline is None:
            # The retry of a cancellation is **always** bounded: a
            # worker that never ends may not hold the caller for ever.
            # The bound of the package is used only when the caller did
            # not bring a deadline of the round.
            deadline = self._clock() + CLOSE_JOIN_SECONDS
        while True:
            try:
                state = self.api.cancel_synchronous_io(self.thread_handle)
            except BrokerError as error:
                self.error = error.code
                return 'FAILED'
            except Exception as error:  # noqa: BLE001 - the failure stays visible
                self.error = type(error).__name__
                return 'FAILED'
            if state != 'NOT_FOUND':
                return state
            # The operation was not found: it had not started yet or it
            # had just finished.  The worker is asked again until the
            # request of this generation completed or until the thread
            # of the worker really stopped.
            with self._condition:
                completed = self._completed >= self._submitted
            if completed or self.stopped.is_set():
                return 'NOT_FOUND'
            if deadline is not None and self._clock() >= deadline:
                return 'NOT_FOUND'
            # The pause of the retry is its own event: the stop event of
            # the worker was set by this very method and it may never be
            # used as the sleep of the retry.
            self._pause.wait(POLL_SLICE_SECONDS)

    def stop(self):
        """Ask the worker to end its loop."""
        self._stop_event.set()

    def stop_accepting(self):
        """Stop the worker from accepting a new task.

        The flag is written under the **same** lock that the worker of
        the endpoint reads it under: the cancellation and the intent to
        enter the operation are one atomic step.
        """
        with self._condition:
            self._cancelled = True
        self._stop_event.set()

    def release_thread_handle(self):
        """Close the handle of the thread of this worker.

        The worker is the only owner of that handle.  It is closed here
        and only here, and only after the thread of the worker really
        ended.  A worker that did not stop keeps its handle.
        """
        if self.thread_handle is None:
            return True
        handle = self.thread_handle
        try:
            self.api.close_handle(handle)
        except BrokerError as error:
            self.error = error.code
            return False
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.error = type(error).__name__
            return False
        self.thread_handle = None
        self.thread_handle_released = True
        return True

    def join_bounded(self, seconds):
        """Join the worker and report whether it really stopped.

        A worker whose thread was never started cannot be joined: the
        join of such a thread is an error of the caller and not a fact
        of the round.  The join reports that the worker did not stop
        and it never pretends that the thread ended.
        """
        try:
            self.join(max(0.0, seconds))
        except RuntimeError:
            # The thread was never started: it is not a thread of the
            # round that ended, it is a thread that never came up.
            self.joined = False
            return False
        self.joined = not self.is_alive()
        return self.joined


class _WindowsPipeEndpoint:
    """One end of a private pipe on a Windows host.

    The read and the write of the endpoint each own exactly one worker
    thread and there is never more than one of them: the number of the
    threads of a channel is fixed and it never grows with the number of
    the frames.

    The supervisor never performs the blocking call itself.  It waits
    for the completion of the worker in bounded slices, it checks the
    cancel flag and the deadline on every slice and it cancels the
    worker through the original handle of its thread when the deadline
    arrives.  The worker that is inside the call is the one that may
    block; the supervisor never does.

    The cancellation of a synchronous operation is a request and not a
    completion: ``CancelSynchronousIo`` may report that the operation
    was not found because it had not started yet or because it had just
    finished.  The worker therefore reports the real state of its
    operation, the supervisor joins it with a bounded wait, and a worker
    that did not stop keeps its owner reference and makes the round
    unknown.

    A write is a **complete** write: the endpoint writes the whole
    block, in as many partial writes as Windows needs, and it reports
    the number of the bytes that really went into the pipe.  A partial
    write is never reported as a success.
    """

    #: The bound absolute deadline of this endpoint.  It is a class
    #: attribute so that an endpoint that was built without its
    #: constructor still has a real deadline and never a missing one.
    _deadline = None
    #: The cancel flag and the deadline of the write that is in flight.
    #: They are class attributes for the same reason as the deadline
    #: above: an endpoint that was built without its constructor still
    #: has them and never a missing one.
    _write_cancel = None
    _write_deadline = None
    #: The context of the round.  It is a class attribute for the same
    #: reason: an endpoint that was built without its constructor still
    #: reads the absolute deadline of the round from it and it never
    #: treats a missing context as an unlimited budget.
    _context = None

    def __init__(self, file_object, *, name, api=None, clock=None,
                 handle=None, context=None):
        self._file = file_object
        self._name = name
        self._api = api
        self._clock = clock or time.monotonic
        self._closed = False
        self._reader = None
        self._writer = None
        self._retained = []
        self._deadline = None
        self._write_cancel = None
        self._write_deadline = None
        # The ONE context of the round.  The endpoint reads the absolute
        # deadline of the round from it and it never keeps a budget of
        # its own.
        self._context = context
        if handle is None:
            import msvcrt
            handle = msvcrt.get_osfhandle(file_object.fileno())
        self._handle = handle
        self.facts = {'name': name, 'owner': 'WINDOWS_ENDPOINT'}

    def bind_deadline(self, deadline):
        """Bind an absolute deadline to this endpoint.

        The deadline may only shorten the deadline that is already
        bound and it is read again on every slice.
        """
        value = _require_deadline(deadline)
        if value is None:
            return self._deadline
        if self._deadline is not None and value > self._deadline:
            return self._deadline
        self._deadline = value
        return value

    def bind_context(self, context):
        """Bind the ONE context of the round to this endpoint."""
        if context is not None:
            self._context = context
        return self._context

    def _effective_deadline(self, deadline=None):
        """The deadline that this call really uses.

        The deadline of the call, the deadline that is bound to the
        endpoint and the absolute deadline of the round are **one**
        value: the earliest of the three.  The endpoint never keeps a
        deadline of its own and it never treats a missing context as an
        unlimited budget.
        """
        value = _require_deadline(deadline)
        bound = self._deadline
        if bound is not None and (value is None or bound < value):
            value = bound
        context = self._context
        if context is not None:
            absolute = context.absolute_deadline
            if absolute is not None and (value is None or absolute < value):
                value = absolute
        return value

    def _remaining(self, deadline=None):
        """The seconds that are left until the deadline of this endpoint."""
        value = self._effective_deadline(deadline)
        if value is None:
            return CLOSE_JOIN_SECONDS
        return max(0.0, value - self._clock())

    def _start(self, kind, action, deadline=None):
        """Create and start one worker of this endpoint.

        The worker is registered with the endpoint **before** it is
        started.  An endpoint that owns a worker only after the start
        returned has no owner at all for a worker whose start did not
        return, and the close of the endpoint could close the file
        under a worker that is about to read from it.

        The wait for the handle of the thread of the worker is bounded
        by the **current** remaining budget of the round.  It never
        opens a budget of its own and it never waits a fixed number of
        seconds.
        """
        worker = _WindowsPipeWorker(self._api, self._handle, kind=kind,
                                    action=action, clock=self._clock,
                                    name='lvw-native-custody-pipe-' + kind)
        # The pre-registration: the endpoint is the owner of the worker
        # before the thread of the worker exists.
        if kind == 'read':
            self._reader = worker
        else:
            self._writer = worker
        try:
            worker.start()
        except BaseException:
            # The start of the worker did not return.  The worker keeps
            # its owner and it may still come up: it is never forgotten
            # and it is never closed under.
            self._retained.append(worker)
            self.facts['retained_workers'] = len(self._retained)
            self.facts['worker_alive'] = True
            raise
        # The worker acquires the handle of its own thread before it may
        # be used.  The wait for it is bounded by the remaining budget of
        # the round.
        worker.wait_ready(self._remaining(deadline))
        return worker

    def _await(self, worker, request, deadline, cancel):
        """Wait for the completion of one worker, bounded and cancellable.

        The deadline that this wait really uses is **recomputed on every
        slice**: a deadline that was bound after the wait started still
        tightens the wait that is running.  A wait that carries no
        deadline yet observes the deadline as soon as it is bound, and
        the cancel flag ends it in the meantime.
        """
        generation = worker.submit(request)
        while True:
            effective = self._effective_deadline(deadline)
            if cancel is not None and cancel.is_set():
                self._cancel(worker, effective)
                raise BrokerError('BROKER_PIPE_CANCELLED', self._name)
            if effective is not None and self._clock() >= effective:
                self._cancel(worker, effective)
                raise BrokerError('BROKER_PIPE_TIMEOUT', self._name)
            if worker.wait_done(generation, POLL_SLICE_SECONDS):
                break
        if worker.error:
            raise BrokerError(worker.error, self._name)
        return worker.result

    def _cancel(self, worker, deadline=None):
        """Cancel one worker and prove that it really stopped."""
        state = worker.request_cancel(self._effective_deadline(deadline))
        if not worker.join_bounded(self._remaining(deadline)):
            # The worker did not stop: it keeps its owner reference and
            # the round becomes unknown.  It is never terminated blindly
            # and it is never waited for without a bound.
            self._retained.append(worker)
            self.facts['retained_workers'] = len(self._retained)
            self.facts['worker_alive'] = True
            raise BrokerError('BROKER_PIPE_CANCEL_NOT_CONFIRMED',
                              '%s:%s' % (self._name, state))
        if not worker.joined:
            self._retained.append(worker)
            self.facts['retained_workers'] = len(self._retained)
            raise BrokerError('BROKER_PIPE_CANCEL_NOT_CONFIRMED', self._name)

    def read(self, deadline=None, cancel=None):
        """Read one block of the pipe, bounded by the deadline."""
        if self._reader is None:
            self._start('read', self._read_block, deadline)
        return self._await(self._reader, None, deadline, cancel)

    def write(self, data, deadline=None, cancel=None):
        """Write the whole block, bounded by the deadline."""
        if self._writer is None:
            self._start('write', self._write_block, deadline)
        # The cancel flag and the deadline of this write are published
        # for the partial write: every segment of a partial write checks
        # the cancel flag and the deadline of the round.  They are not
        # cleared when the write ends: a segment that is still in flight
        # inside the worker has to observe the cancel of this write.
        self._write_cancel = cancel
        self._write_deadline = self._effective_deadline(deadline)
        return self._await(self._writer, bytes(data), deadline, cancel)

    def _read_block(self, request):
        return self._api.read_stream(self._handle, PIPE_READ_BYTES)

    def _current_write_deadline(self):
        """The deadline that the next segment of a write really uses.

        The value is read **again** for every segment of a partial
        write.  A copy of the deadline that was taken when the write
        started would let the write continue past a deadline that the
        round published in the meantime, and the shared context of the
        round is the only authority of the deadline.
        """
        value = self._write_deadline
        bound = self._deadline
        if bound is not None and (value is None or bound < value):
            value = bound
        context = self._context
        if context is not None:
            absolute = context.absolute_deadline
            if absolute is not None and (value is None or absolute < value):
                value = absolute
        return value

    def _write_block(self, request):
        """Write the whole block, report the number of the written bytes.

        Windows may write less than the block that it was given.  The
        endpoint repeats the write until the whole block was written or
        until the write fails with a named error.  **Every segment** of
        the partial write checks the cancel flag and the deadline of the
        round: a write that is not bounded is not a write.
        """
        data = bytes(request)
        total = 0
        while total < len(data):
            cancel = self._write_cancel
            if cancel is not None and cancel.is_set():
                raise BrokerError('BROKER_PIPE_CANCELLED', self._name)
            deadline = self._current_write_deadline()
            if deadline is not None and self._clock() >= deadline:
                raise BrokerError('BROKER_PIPE_TIMEOUT', self._name)
            count = self._api.write_stream(self._handle, data[total:])
            if count is None or count <= 0:
                raise BrokerError('BROKER_STREAM_WRITE_FAILED',
                                  '%s:written=%d' % (self._name, total))
            total += count
        return total

    def close(self):
        """Close the original handle of this endpoint, exactly once.

        The close stops the workers from accepting a new task first, it
        asks for the cancellation of the operation that is in flight and
        it joins the workers with a bounded wait.  A worker that did not
        stop keeps its owner reference: the file is never closed under a
        worker that is still inside its operation.

        The close is **committed** only when it really happened.  A
        close that failed keeps the file and its owner: the endpoint
        may try it again inside the deadline of the round and it is
        never marked as closed irreversibly.  A close of an endpoint
        that is already closed keeps the fact that it is closed: the
        second close is idempotent and it never turns a proven close
        into a missing one.

        The state of the workers is **recomputed** on every close: a
        worker that really ended and whose handle of its thread was
        released is not retained any more, and a worker whose handle of
        its thread could not be closed is retained again and it may be
        released by a later close.  A closed file never locks the
        recovery of the handle of a thread.
        """
        deadline = self._effective_deadline()
        alive = False
        retained = []
        for worker in (self._reader, self._writer):
            if worker is None:
                continue
            worker.stop_accepting()
            worker.request_cancel(deadline)
            if not worker.join_bounded(self._remaining(deadline)):
                # The worker did not stop: it keeps its owner and the
                # file is never closed under it.
                alive = True
                retained.append(worker)
                continue
            # The thread of the worker really ended: the original handle
            # of the thread may be released now.  A handle that could
            # not be closed keeps its owner and a later close may try it
            # again.
            if not worker.release_thread_handle():
                retained.append(worker)
        # The state of the workers is **recomputed** on every close: a
        # worker that really ended and whose handle of its thread was
        # released is not retained any more.  A closed file never locks
        # the recovery of the handle of a thread.
        self._retained = retained
        self.facts['retained_workers'] = len(self._retained)
        self.facts['worker_alive'] = alive
        self.facts['worker_thread_handle_released'] = all(
            worker.thread_handle_released
            for worker in (self._reader, self._writer) if worker is not None)
        if alive:
            # A live worker keeps the file: the file is never closed
            # under a worker that is still inside its operation.
            self.facts['closed'] = False
            return self.facts
        if self._closed:
            self.facts['closed'] = True
            self.facts['already_closed'] = True
            return self.facts
        try:
            self._file.close()
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.facts['closed'] = False
            self.facts['error_type'] = type(error).__name__
            return self.facts
        self._closed = True
        self.facts['closed'] = True
        return self.facts


def _make_endpoint(file_object, name, *, api=None, clock=None, context=None):
    """The endpoint of one end of the private pipe of this host.

    The Windows host gets the supervised and cancellable endpoint and
    every other host gets the non blocking endpoint of the original
    descriptor.  The choice is made by the host and never by a string
    that a caller could set: a platform that is not Windows never loads
    the Windows table.

    The Windows endpoint needs the primitive table of the host, because
    the cancellation of a synchronous operation needs the original
    handle of the thread that performs it.  The table is loaded only on
    Windows.

    The ONE context of the round is handed to the endpoint: the
    endpoint reads the absolute deadline of the round from it and it
    never keeps a budget of its own.
    """
    if os.name == 'nt':
        if api is None:
            api = WindowsApi()
        return _WindowsPipeEndpoint(file_object, name=name, api=api, clock=clock,
                                    context=context)
    return _PosixPipeEndpoint(file_object, name=name, clock=clock)


# -- the private control channel -------------------------------------------

class StreamChannel:
    """The private control channel of the broker.

    The channel is the broker's own standard input and output.  It is
    bounded three times: one frame is at most 32 KiB, the channel carries
    at most 1024 frames and the text of the children is bounded by the
    core.

    The read side is drained by one background thread, so the broker never
    blocks on the read.  A parent that stops talking therefore cannot hold
    the deadline of the round: the deadline is checked by the broker
    itself.

    The channel owns the original handles of its two ends.  A read and a
    write are bounded by an absolute deadline and by a cancel flag, so a
    peer that never reads can never hold the supervisor of the round.
    """

    def __init__(self, reader, writer, *, max_frames=MAX_FRAMES,
                 max_frame_bytes=MAX_FRAME_BYTES, name='channel',
                 read_endpoint=None, write_endpoint=None, clock=None, api=None,
                 context=None, custody=None):
        self._reader = read_endpoint or _make_endpoint(reader, name + '-read',
                                                       clock=clock, api=api,
                                                       context=context)
        self._writer = write_endpoint or _make_endpoint(writer, name + '-write',
                                                        clock=clock, api=api,
                                                        context=context)
        self._queue = queue.Queue(maxsize=max_frames)
        self._max_frames = max_frames
        self._max_frame_bytes = max_frame_bytes
        self._count = 0
        self._overflow = False
        self._eof = False
        self._error = None
        self._buffer = b''
        self._deadline = None
        self._clock = clock or time.monotonic
        self._cancel = threading.Event()
        self.reader_alive = None
        self.reader_finished = None
        # The ONE context of the round.  The channel and its endpoints
        # read the absolute deadline of the round from it and they never
        # keep a budget of their own.
        self._context = context
        self._thread = threading.Thread(target=self._drain, daemon=True,
                                        name='lvw-native-custody-channel')
        # The channel registers itself with the custody of the launcher
        # **before** its reader thread starts: a channel whose
        # construction failed half way may not leave an endpoint and a
        # thread without an owner.
        self._custody = custody
        if custody is not None:
            custody.retain('channel', self, 'constructing')
        try:
            self._thread.start()
        except BaseException:
            # The start of the reader of the channel did not return: the
            # channel keeps its owner in the custody of the launcher and
            # it is never forgotten.
            raise
        if custody is not None:
            custody.forget(self)

    def bind_context(self, context):
        """Bind the ONE context of the round to the channel.

        The context is bound to the channel **and** to its two
        endpoints: every layer of the round reads the same absolute
        deadline and none of them keeps a deadline of its own.
        """
        if context is not None:
            self._context = context
            for endpoint in (self._reader, self._writer):
                binder = getattr(endpoint, 'bind_context', None)
                if callable(binder):
                    binder(context)
        return self._context

    def bind_deadline(self, deadline):
        """Bind the absolute deadline of the round to the channel.

        The deadline is bound to the channel **and** to its two
        endpoints.  A binding that happens after a read started still
        tightens that read: the deadline is a property of the endpoint
        and not a local argument of one call.
        """
        value = _require_deadline(deadline)
        if value is None:
            return self._deadline
        if self._deadline is not None and value > self._deadline:
            return self._deadline
        self._deadline = value
        for endpoint in (self._reader, self._writer):
            binder = getattr(endpoint, 'bind_deadline', None)
            if callable(binder):
                try:
                    binder(value)
                except Exception:  # noqa: BLE001 - the failure stays visible
                    pass
        return value

    def _remaining(self, deadline=None):
        """The seconds that are left until the deadline of the channel."""
        value = self._deadline if deadline is None else deadline
        if value is None:
            return None
        return max(0.0, value - (self._clock or time.monotonic)())

    def _drain(self):
        try:
            while True:
                block = self._reader.read(self._deadline, self._cancel)
                if not block:
                    break
                buffer = self._buffer + block
                self._buffer = b''
                while True:
                    index = buffer.find(b'\n')
                    if index < 0:
                        break
                    raw = buffer[:index + 1]
                    buffer = buffer[index + 1:]
                    if len(raw) > self._max_frame_bytes:
                        self._overflow = True
                        return
                    self._count += 1
                    if self._count > self._max_frames:
                        self._overflow = True
                        return
                    while True:
                        self._check_wait()
                        try:
                            self._queue.put(raw, timeout=0.5)
                            break
                        except queue.Full:
                            if self._eof:
                                return
                            continue
                # The remainder of the block has no newline.  The buffer
                # of the channel is bounded: it is checked on **every**
                # append and an oversize buffer is refused at once.  One
                # byte beyond the limit is kept, so that the overflow is
                # detected and not silently trimmed.
                if len(buffer) > self._max_frame_bytes:
                    self._buffer = buffer[:self._max_frame_bytes + 1]
                    self._overflow = True
                    return
                self._buffer = buffer
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self._error = getattr(error, 'code', None) or type(error).__name__
        finally:
            self._eof = True
            if self._buffer and self._error is None:
                # The stream ended in the middle of a frame.  An
                # incomplete frame is a named failure of the channel and
                # it is never dropped silently.
                self._error = 'BROKER_CHANNEL_PARTIAL_FRAME'

    def _check_wait(self):
        """The cancel flag and the deadline of the wait of the reader."""
        if self._cancel.is_set():
            raise BrokerError('BROKER_CHANNEL_CANCELLED')
        remaining = self._remaining()
        if remaining is not None and remaining <= 0:
            raise BrokerError('BROKER_CHANNEL_TIMEOUT')

    def read(self, timeout):
        """One raw frame, ``None`` when nothing arrived, ``b''`` at the end."""
        if self._overflow:
            raise BrokerError('BROKER_CHANNEL_OVERFLOW')
        try:
            return self._queue.get(timeout=max(0.0, timeout))
        except queue.Empty:
            if self._error:
                raise BrokerError(self._error)
            if self._eof:
                return b''
            return None

    def write(self, raw, deadline=None):
        """Write one frame, bounded by the deadline of the round.

        The number of the bytes that really went into the pipe is
        checked: a partial write is never reported as a success.
        """
        if len(raw) > self._max_frame_bytes:
            raise BrokerError('BROKER_CHANNEL_FRAME_TOO_LARGE')
        target = self._deadline if deadline is None else deadline
        written = self._writer.write(raw, target, self._cancel)
        if written is not None and written != len(raw):
            raise BrokerError('BROKER_CHANNEL_WRITE_INCOMPLETE',
                              'written=%s:expected=%d' % (written, len(raw)))
        return written

    def close(self):
        """Close the channel and report whether the reader really stopped.

        The reader thread is joined with a bounded wait.  A reader that
        did not stop is reported as such: a daemon thread is not a
        finished thread, so the fact that the reader is still alive is
        kept visible instead of being hidden behind the close.  The read
        end is closed by its owner only when the reader really stopped.

        The facts of the close carry the error of the reader, the number
        of the workers that the endpoints retained and the fact that the
        original handles of those workers were released: a reader that
        ended with an error is not a successful end.

        The close may be **repeated**: a close that did not confirm its
        ends may try them again, and a close of an endpoint that is
        already closed keeps the fact that it is closed.
        """
        facts = {}
        self._cancel.set()
        try:
            write_facts = self._writer.close()
            facts['write_end_closed'] = bool(write_facts.get('closed'))
            facts['write_retained_workers'] = int(
                write_facts.get('retained_workers') or 0)
            facts['write_worker_thread_handle_released'] = bool(
                write_facts.get('worker_thread_handle_released'))
        except Exception:  # noqa: BLE001 - the failure stays visible
            facts['write_end_closed'] = False
            facts['write_retained_workers'] = 0
            facts['write_worker_thread_handle_released'] = False
        remaining = self._remaining()
        join_seconds = CLOSE_JOIN_SECONDS if remaining is None else remaining
        self._thread.join(join_seconds)
        self.reader_alive = self._thread.is_alive()
        self.reader_finished = not self.reader_alive
        facts['reader_finished'] = self.reader_finished
        facts['reader_error'] = self._error
        if self.reader_alive:
            # The reader is still inside the pipe: the read end is not
            # closed under it.  It stays owned by the channel and the
            # round keeps the fact.  The facts of the reader endpoint are
            # the real ones and they are never replaced by a zero.
            endpoint_facts = getattr(self._reader, 'facts', None)
            endpoint_facts = endpoint_facts if isinstance(endpoint_facts, dict) else {}
            facts['read_end_closed'] = False
            facts['read_retained_workers'] = int(
                endpoint_facts.get('retained_workers') or 0)
            facts['read_worker_thread_handle_released'] = bool(
                endpoint_facts.get('worker_thread_handle_released'))
            facts['worker_thread_handle_released'] = bool(
                facts.get('write_worker_thread_handle_released')
                and facts.get('read_worker_thread_handle_released'))
            facts['channel_retained_workers'] = (int(facts.get('write_retained_workers') or 0)
                                                  + int(facts.get('read_retained_workers') or 0))
            return facts
        try:
            read_facts = self._reader.close()
            facts['read_end_closed'] = bool(read_facts.get('closed'))
            facts['read_retained_workers'] = int(
                read_facts.get('retained_workers') or 0)
            facts['read_worker_thread_handle_released'] = bool(
                read_facts.get('worker_thread_handle_released'))
        except Exception:  # noqa: BLE001 - the failure stays visible
            facts['read_end_closed'] = False
            facts['read_retained_workers'] = 0
            facts['read_worker_thread_handle_released'] = False
        facts['worker_thread_handle_released'] = bool(
            facts.get('write_worker_thread_handle_released')
            and facts.get('read_worker_thread_handle_released'))
        facts['channel_retained_workers'] = (int(facts.get('write_retained_workers') or 0)
                                              + int(facts.get('read_retained_workers') or 0))
        return facts

    @property
    def eof(self):
        return self._eof

    @property
    def overflow(self):
        return self._overflow

    @property
    def frames(self):
        return self._count


# -- the bounded command loop ----------------------------------------------

class _StartupOwner:
    """The bounded owner of one startup step of the round.

    A startup step may block: the creation of a job, the creation of a
    process and the assignment of a process may all block inside the
    operating system.  Such a step may not run unbounded inside the one
    supervision thread of the round.

    The owner therefore runs the step in its own thread and hands the
    result over through a **bounded** channel of one slot.  The
    supervisor waits for the result until the absolute deadline of the
    round.  A step that did not finish in time keeps the round unknown,
    keeps the thread and its owner, and a result that arrives late may
    only clean up: it may never continue the startup of the round.
    """

    def __init__(self, *, name, clock, deadline):
        self.name = name
        self._clock = clock
        self._deadline = deadline
        self._results = queue.Queue(maxsize=STARTUP_INFLIGHT_SLOTS)
        self._thread = None
        self._error = None
        self._value = None
        self._finished = threading.Event()
        self._expired = False

    def start(self, action):
        """Run one startup step in the thread of this owner."""
        self._thread = threading.Thread(
            target=self._run, args=(action,), daemon=True,
            name='lvw-native-custody-startup-' + self.name)
        self._thread.start()
        return self

    def _run(self, action):
        try:
            value = action()
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._error = error
            outcome = ('error', error)
        else:
            self._value = value
            outcome = ('value', value)
        # The **attempt** of the step ended.  The event of the attempt is
        # published here and it is never a proof that the thread of the
        # step ended: the thread still has to publish its result and to
        # leave.
        self._finished.set()
        self._put(outcome)

    def _put(self, item):
        try:
            self._results.put_nowait(item)
        except queue.Full:
            # The bounded channel is full: the result is dropped and the
            # owner keeps the error.  The channel never grows.
            pass

    def await_result(self):
        """Wait for the result of the step, bounded by the deadline."""
        while True:
            if self._clock() >= self._deadline:
                self._expired = True
                raise BrokerError('BROKER_STARTUP_DEADLINE_EXCEEDED', self.name)
            try:
                kind, value = self._results.get(timeout=POLL_SLICE_SECONDS)
            except queue.Empty:
                continue
            if kind == 'error':
                raise value
            return value

    def settle(self, seconds):
        """Wait, bounded, for the **thread** of this owner to end.

        The wait is bounded by the shared cleanup deadline of the round
        and it never adds a settle budget of its own.

        The end of the **attempt** of the step and the end of the
        **thread** that performs it are two different facts.  The event
        of the attempt is published before the result and before the
        thread leaves, and it is therefore never a proof that the
        thread ended.  The settle asks the thread itself: a thread that
        is still running keeps its owner and the round stays unknown.
        """
        if self._thread is None:
            return True
        try:
            self._thread.join(max(0.0, seconds))
        except RuntimeError:
            # The thread was never started: it is not a thread of the
            # round that ended.
            return False
        return not self._thread.is_alive()

    @property
    def expired(self):
        """Whether the step of this owner missed the deadline."""
        return self._expired

    @property
    def in_flight(self):
        """Whether the step of this owner is still running."""
        return self._thread is not None and self._thread.is_alive()


class BrokerLoop:
    """The bounded command loop of the broker.

    The loop owns the absolute deadline of the round.  It is fixed once,
    from the lease of the plan, and it is never moved: neither a status
    request nor a heartbeat may extend it.

    The round is stopped when the parent asks for it, when the channel
    reaches its end, when a bound of the channel or of the text of the
    children is exceeded or when the absolute deadline arrives.  A stop
    that was not requested by the parent keeps the evidence of the round
    unknown: the round did not end in a proven release.

    The startup of the round is supervised.  The arm and the launch are
    **bounded startup steps** with their own owner: a step that blocks
    may not hold the supervision of the round and a step that returns
    after the absolute deadline may only clean up.
    """

    def __init__(self, *, core, transport, plan, nonce, clock=None, wall=None,
                 max_frames=MAX_FRAMES):
        self.core = core
        self.transport = transport
        self.plan = plan
        self.nonce = nonce
        self._clock = clock or time.monotonic
        self._wall = wall or time.time
        self._max_frames = max_frames
        self._sequence = 0
        self._last_sequence = None
        self._frames = 0
        self._sent_frames = 0
        self._deadline_wall = None
        self._deadline_mono = None
        self._last_frame_wall = None
        self._last_alive_wall = None
        self._stopped = False
        # The ONE context of the round.  The loop holds the very same
        # object as the core: the deadlines, the cancel and the unknown
        # of the round are one state and not one number per layer.
        self.context = core.context
        # The owner of the startup step that is in flight.  A step that
        # did not end keeps the round unknown and it keeps its owner.
        self._startup_owner = None
        self._startup_in_flight = None

    # -- the deadline ------------------------------------------------------
    def _fix_deadline(self):
        """Fix the absolute deadline of the round, once, before anything.

        The deadline is fixed before the job of the round is created,
        before the first reply is written and before the first role is
        launched.  It is the earlier of the lease of the plan and the
        runtime of the plan and it is never moved afterwards.
        """
        if self._deadline_mono is not None:
            return self._deadline_mono
        wall_now = self._wall()
        self._deadline_wall = min(self.plan.lease_expires_at,
                                  wall_now + self.plan.max_runtime_seconds)
        self._deadline_mono = self._clock() + max(0.0, self._deadline_wall - wall_now)
        return self._deadline_mono

    def remaining_seconds(self):
        if self._deadline_mono is None:
            return float(self.plan.max_runtime_seconds)
        return max(0.0, self._deadline_mono - self._clock())

    # -- the replies -------------------------------------------------------
    def _check_frame_budget(self, reserved=RESERVED_TERMINAL_FRAMES):
        """The frame budget of the channel, in both directions.

        The budget of the round is shared by the frames that the broker
        sends and by the frames that it receives: the round of six hours
        with its heartbeat stays inside the budget of the channel.  The
        frames of the terminal exchange are reserved and the budget is
        never widened and never renewed.

        The check is the **total** of both directions.  A single
        direction is never a substitute for the total: a channel that
        received a thousand frames and sent none is not inside the
        budget when the budget is a thousand and twenty four frames.
        """
        if self._frames + self._sent_frames + reserved + 1 > MAX_FRAMES:
            raise BrokerError('BROKER_FRAME_BUDGET_EXCEEDED',
                              'sent=%d:received=%d' % (self._sent_frames,
                                                       self._frames))

    def _reply(self, kind, state, detail, *, terminal=False):
        self._check_frame_budget(0 if terminal else RESERVED_TERMINAL_FRAMES)
        self._sent_frames += 1
        self._sequence += 1
        frame = {'schema': CHANNEL_SCHEMA, 'kind': kind, 'run_id': self.plan.run_id,
                 'candidate_sha': self.plan.candidate_sha,
                 'authorization_sha256': self.plan.authorization_sha256,
                 'nonce': self.nonce, 'sequence': self._sequence,
                 'state': state, 'detail': detail}
        raw = json.dumps(frame, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
        if len(raw) > MAX_FRAME_BYTES:
            frame['detail'] = {'truncated': True}
            raw = json.dumps(frame, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        # The deadline of the round is already bound to the transport, so
        # the write of the frame is bounded by it.  The transport is
        # never called with an argument that it does not know.
        self.transport.write(raw + b'\n')

    # -- the supervised startup --------------------------------------------
    def _guarded_startup(self, action, stage):
        """One startup step, guarded by the shared deadline.

        The shared budget is checked **before** the step and **after**
        it returned.  A step that starts after the deadline of the round
        arrived never runs at all, and a step that finished after the
        deadline may only clean up: it may never continue the startup of
        the round and it may never write a successful reply.

        The supervision publishes the cancel of the round when the
        deadline arrived: the core and every later step of the startup
        see it and they stop.
        """
        def guarded():
            self._check_startup_budget(stage)
            action()
            self._check_startup_budget(stage)
            return None
        return guarded

    def _check_startup_budget(self, stage):
        """Check the shared budget of the startup of the round."""
        try:
            self.core.check_startup_budget(stage)
        except BrokerError:
            # The supervision publishes the cancel of the round: the
            # core and every later step of the startup see it.
            self.context.request_cancel()
            self._abort_started_round()
            raise

    def _abort_started_round(self):
        """Release what the round acquired, bounded by the shared budget."""
        try:
            self.core.stop('STARTUP_AFTER_DEADLINE', force_unknown=True)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self.core.failures.append({'stage': 'startup_abort',
                                       'error_type': type(error).__name__})

    def _run_startup(self, stage, action):
        """Run one startup step under the absolute deadline of the round."""
        owner = _StartupOwner(name=stage, clock=self._clock,
                              deadline=self._deadline_mono)
        self._startup_owner = owner
        self.context.register_inflight(owner)
        owner.start(self._guarded_startup(action, stage))
        try:
            value = owner.await_result()
        except BrokerError as error:
            if error.code not in ('BROKER_STARTUP_DEADLINE_EXCEEDED',
                                  'BROKER_STARTUP_CANCELLED'):
                self.context.release_inflight(owner)
                raise
            self.core.failures.append({'stage': stage, 'code': error.code})
            # The step did not finish before the deadline.  The owner
            # keeps its thread: a late result may only clean up.  The
            # wait for the end of the step is bounded by the **shared**
            # cleanup deadline of the round and it never adds a settle
            # budget of its own.
            budget = self.context.remaining_cleanup()
            if not owner.settle(budget):
                self._startup_in_flight = owner
                self.core.failures.append({'stage': stage,
                                           'code': 'BROKER_STARTUP_IN_FLIGHT_RETAINED'})
            else:
                self.context.release_inflight(owner)
            raise
        # The step returned its result.  The **thread** of the step may
        # still be inside the operating system: the result of the step
        # is not the exit of its thread.  The owner is released only
        # after the real exit of the thread, and a thread that did not
        # exit keeps its owner and it is never given a new budget.
        if not owner.settle(self._startup_settle_seconds()):
            self._startup_in_flight = owner
            self.core.failures.append({'stage': stage,
                                       'code': 'BROKER_STARTUP_IN_FLIGHT_RETAINED'})
        else:
            self.context.release_inflight(owner)
        return value

    def _startup_settle_seconds(self):
        """The bounded wait for the real exit of a startup thread.

        The wait is bounded by the **remaining** of the absolute
        deadline of the round and by the settle bound of the package.
        It never publishes the cleanup deadline of the round - the
        cleanup of a round that did not fail keeps its whole budget -
        and it never opens a budget of its own.
        """
        remaining = self.context.remaining_absolute()
        if remaining is None:
            return STARTUP_SETTLE_SECONDS
        return max(POLL_SLICE_SECONDS, min(remaining, STARTUP_SETTLE_SECONDS))

    # -- the run -----------------------------------------------------------
    def run(self):
        """Run the round and always release what the round owns.

        The loop has a ``finally`` that does not depend on the diagnosis
        of the round and not on the success of a write: a round that
        could not write its first reply still releases the job and the
        handles that it created.
        """
        self._fix_deadline()
        # The core and the loop read the same clock: the deadlines of
        # the round and the ONE cleanup deadline are in one domain.
        binder_clock = getattr(self.core, 'bind_clock', None)
        if callable(binder_clock):
            binder_clock(self._clock)
        self.core.bind_absolute_deadline(self._deadline_mono)
        binder = getattr(self.transport, 'bind_deadline', None)
        if callable(binder):
            # The transport of the channel is bound to the deadline of
            # the round before the job of the round exists: a read or a
            # write of the channel can never outlive the round.
            binder(self._deadline_mono)
        try:
            try:
                self._run_startup('ARM', self.core.arm)
            except BrokerError as error:
                self._reply('REFUSED', self.core.state, {'code': error.code},
                            terminal=True)
                self._write_receipt('ARM_FAILED')
                return 3
            self._reply('READY', self.core.state, {'broker': self.core.broker_identity})
            try:
                self._run_startup('LAUNCH', self.core.launch)
            except BrokerError as error:
                self._reply('REFUSED', self.core.state, {'code': error.code},
                            terminal=True)
                self._write_receipt('LAUNCH_FAILED')
                return 3
            self._reply('STATUS', self.core.state, self.core.summary())
            exit_code = self._loop()
            self._write_receipt(self.core.stop_reason)
            return exit_code
        finally:
            self._ensure_stopped()

    def _ensure_stopped(self):
        """Release the resources of the round, whatever happened before.

        The release never raises: a failure of the release is kept by the
        core and it never replaces the first failure of the round.
        """
        if self._stopped:
            return
        self._stopped = True
        if self._startup_in_flight is not None:
            # A startup step is still running: the core belongs to the
            # in-flight owner and the round keeps the fact.  The cleanup
            # of the core would race with the step that is still inside
            # the operating system, so it is not started here.
            self.core.failures.append({'stage': 'loop_stop',
                                       'code': 'BROKER_STARTUP_IN_FLIGHT_RETAINED'})
            self.core.state = 'UNKNOWN_RETAINED'
            return
        try:
            self.core.stop(self.core.stop_reason or 'LOOP_EXIT', force_unknown=True)
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.core.failures.append({'stage': 'loop_stop',
                                        'error_type': type(error).__name__})
            self.core.state = 'UNKNOWN_RETAINED'

    def _loop(self):
        self._last_frame_wall = self._wall()
        while True:
            now = self._clock()
            if now >= self._deadline_mono:
                return self._stop('LEASE_EXPIRED', 4)
            if self.core.overflowed():
                return self._stop('BOUND_EXCEEDED', 4)
            timeout = min(POLL_SECONDS, max(0.01, self._deadline_mono - now))
            try:
                raw = self.transport.read(timeout)
            except BrokerError:
                return self._stop('CHANNEL_ERROR', 4)
            if raw is None:
                # A missing heartbeat is a secondary signal.  The absolute
                # deadline stays the authority of the round.
                if self._wall() - self._last_frame_wall > HEARTBEAT_TIMEOUT_SECONDS:
                    return self._stop('HEARTBEAT_MISSING', 4)
                continue
            if raw == b'':
                return self._stop('CHANNEL_EOF', 4)
            # The hard cap of the channel is checked before the frame is
            # decoded: a frame that does not fit at all is refused
            # without being accepted.
            if self._frames + self._sent_frames + 1 > MAX_FRAMES:
                return self._stop('FRAME_BUDGET_EXCEEDED', 4)
            try:
                frame = decode_command(raw, run_id=self.plan.run_id,
                                       candidate_sha=self.plan.candidate_sha,
                                       authorization_sha256=self.plan.authorization_sha256,
                                       nonce=self.nonce, last_sequence=self._last_sequence)
            except CustodyError as error:
                self.core.failures.append({'stage': 'channel', 'code': error.code})
                return self._stop('CHANNEL_REFUSED', 4)
            # The reservation of the terminal exchange is **consumed** by
            # the terminal frame itself.  A STOP that arrives near the
            # limit of the budget is a legal frame: it is never refused
            # because of the reservation that was kept for it.  A frame
            # that is not terminal never borrows the reservation and it
            # fails closed when the total does not fit.
            terminal = frame['command'] == 'STOP'
            try:
                self._check_frame_budget(0 if terminal else RESERVED_TERMINAL_FRAMES)
            except BrokerError:
                return self._stop('FRAME_BUDGET_EXCEEDED', 4)
            self._frames += 1
            if self._frames > self._max_frames:
                return self._stop('FRAME_COUNT_EXCEEDED', 4)
            # Only a frame that was decoded and that carries the identity
            # of the round refreshes the heartbeat of the round.  A frame
            # that was refused never does.
            self._last_frame_wall = self._wall()
            self._last_alive_wall = self._last_frame_wall
            self._last_sequence = frame['sequence']
            if frame['command'] == 'STATUS':
                self._reply('STATUS', self.core.state, self.core.summary())
                continue
            return self._stop('STOP_COMMAND', 0)

    def _stop(self, reason, exit_code):
        unknown = reason != 'STOP_COMMAND'
        self.core.stop(reason, force_unknown=unknown)
        self._reply('STOPPED', self.core.state, self.core.summary(), terminal=True)
        return exit_code

    def _write_receipt(self, reason):
        """Write the terminal receipt of the round into the run root.

        The receipt is the evidence that survives a parent that died.  It
        is written once, it is bounded and it is never replaced by a
        successful claim.  A failure of the write never replaces the
        first failure of the round.
        """
        evidence = self.core.evidence()
        evidence['reason'] = reason
        evidence['channel'] = {'frames_received': self._frames,
                               'last_sequence_received': self._last_sequence,
                               'frame_limit': self._max_frames}
        evidence['deadline_wall'] = self._deadline_wall
        evidence['deadline_extended'] = False
        raw = json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                         indent=2).encode('utf-8')
        if len(raw) > MAX_RECEIPT_BYTES:
            raw = json.dumps({'kind': 'lvw.s3-native-broker-receipt/1',
                              'reason': reason, 'truncated': True,
                              'stage_pass_claim': False}).encode('utf-8')
        path = Path(self.core.run_root) / 'temp' / 'native' / 'custody-terminal.json'
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        except OSError:
            return False
        return True


# -- the fixed entry of the broker -----------------------------------------

def build_broker_command(*, plan_path, plan_sha256, run_root, nonce, python=None):
    """The fixed command of the broker.

    The command starts exactly this broker with one sealed plan document.
    There is no dynamic import of a caller supplied module and no arbitrary
    argument vector: the only arguments are the plan, its digest, the run
    root of the round and the nonce of the session.
    """
    script = Path(__file__).resolve()
    if not script.is_file():
        raise BrokerError('BROKER_SCRIPT_MISSING')
    if not re.fullmatch(r'[0-9a-f]{64}', str(plan_sha256)):
        raise BrokerError('BROKER_PLAN_DIGEST_INVALID')
    if not re.fullmatch(r'[0-9a-f]{32}', str(nonce)):
        raise BrokerError('BROKER_NONCE_INVALID')
    executable = python or sys.executable
    return [executable, '-I', '-B', str(script),
            '--plan', str(plan_path), '--plan-sha256', str(plan_sha256),
            '--run-root', str(run_root), '--nonce', str(nonce)]


class BrokerProcess:
    """The original handle of the broker process of one round.

    The parent keeps the process handle, the pipes of the private channel
    and the identity of the executable.  The replies of the broker are
    read through one bounded background reader, so the parent never blocks
    on the channel and the deadline of the round is never held up by a
    silent broker.

    The handle is **deadline aware**: it says so with its own marker and
    it takes the absolute deadline of every write.  A handle that is not
    deadline aware is never assumed to be deadline aware by the parent.
    """

    #: The marker of a handle that understands an absolute deadline.
    channel_deadline_aware = True

    def __init__(self, process, executable, executable_sha256, channel,
                 clock=None):
        self._process = process
        self._channel = channel
        self._clock = clock or time.monotonic
        self.pid = process.pid
        self.executable = executable
        self.executable_sha256 = executable_sha256
        # Whether the reader of the channel really stopped when the channel
        # was closed.  It is ``None`` until the close happened and it stays
        # ``False`` when the reader was still alive after the bounded join.
        self.reader_finished = None
        # The absolute deadline of the round, handed over by the parent.
        # The parent may only shorten it.
        self.write_deadline = None
        self.close_facts = None

    def bind_channel_deadline(self, deadline):
        """Bind the absolute deadline of the round to the private channel.

        The deadline is a finite number of seconds of the monotonic clock
        and it may only shorten the deadline that is already bound: a
        later deadline is refused.
        """
        value = _require_deadline(deadline)
        if value is None:
            raise BrokerError('BROKER_DEADLINE_INVALID')
        if self.write_deadline is not None and value > self.write_deadline:
            raise BrokerError('BROKER_DEADLINE_EXTENDED')
        self.write_deadline = value
        binder = getattr(self._channel, 'bind_deadline', None)
        if callable(binder):
            binder(value)
        return value

    def write(self, raw, deadline=None):
        """Write one frame of the parent, bounded by the deadline.

        The deadline is explicit and it is checked: a write that is not
        bounded by an absolute deadline would let a broker that never
        reads hold the supervisor of the round forever.
        """
        value = _require_deadline(deadline)
        if value is None:
            value = self.write_deadline
        if value is None:
            raise BrokerError('BROKER_DEADLINE_MISSING')
        if self.write_deadline is not None and value > self.write_deadline:
            raise BrokerError('BROKER_DEADLINE_EXTENDED')
        return self._channel.write(raw, value)

    def read(self, timeout):
        return self._channel.read(timeout)

    def close(self, deadline=None):
        """Close the original handle of the broker.

        The close happens even when the exchange of the stop failed: the
        resource of this round is released either way.

        The facts of the close are returned and they are named: a handle
        that was not closed, a reader that did not stop and a process that
        did not exit are facts of the round and they are never hidden
        behind a success.  The release of the original process handle is
        explicit and it is never left to the garbage collector.

        The waits of the close are bounded by **one** absolute deadline:
        the deadline that the parent bound before it closed the handle.
        The remaining time is recomputed before every wait, so that a
        wait that already consumed part of the budget never gets the
        whole budget again and no layer of the cleanup adds a budget of
        its own.

        The close may be **repeated** inside the same deadline: an item
        that was confirmed is never closed a second time and an item
        that was not confirmed is coordinated again.  The attempt that
        ended is not a release: only the facts of the close prove it.

        The **endpoint is the only owner** of the files of the channel.
        The broker process therefore never closes the standard input and
        the standard output of the process by itself: it closes the
        channel, and the channel closes the files that it owns.
        """
        value = self._cleanup_deadline(deadline)
        budget = max(0.0, value - self._clock())
        facts = {'channel_closed': False,
                 'channel_reader_finished': None,
                 'channel_reader_error': None,
                 'channel_retained_workers': 0,
                 'write_end_closed': False,
                 'read_end_closed': False,
                 'stdin_closed': False,
                 'stdout_closed': False,
                 'process_exited': False,
                 'exit_code': None,
                 'terminated': False,
                 'process_handle_released': False,
                 'process_handle_release_method': None,
                 'worker_thread_handle_released': False,
                 'cleanup_budget_seconds': budget,
                 'cleanup_deadline': value}
        # The facts of a previous attempt are kept: an item that was
        # confirmed is never closed a second time and its fact stays
        # true.
        previous = self.close_facts if isinstance(self.close_facts, dict) else {}
        for key, confirmed in previous.items():
            if key in ('cleanup_budget_seconds', 'cleanup_deadline'):
                continue
            if (confirmed is True
                    or (key == 'exit_code' and confirmed is not None)
                    or key == 'process_handle_release_method'):
                facts[key] = confirmed
        # The channel and its endpoints use the very same absolute
        # deadline: they never start a wait of their own.
        binder = getattr(self._channel, 'bind_deadline', None)
        if callable(binder):
            try:
                binder(value)
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass
        if not facts['channel_closed']:
            channel_facts = self._close_channel(facts)
        elif not self._channel_complete(facts):
            # A previous attempt already called the close of the
            # channel, but it did not confirm **every** item of it: the
            # read end, the worker of an endpoint and the original
            # handle of its thread may still be open.  The items that
            # were not confirmed are coordinated again, inside the very
            # same deadline.  A close that returned is not a release.
            channel_facts = self._close_channel(facts)
        else:
            channel_facts = None
        if channel_facts is not None:
            facts.update(channel_facts)
        # The files of the channel belong to the endpoints of the
        # channel.  The fact of their close is the fact of the channel.
        facts['stdin_closed'] = facts['write_end_closed']
        facts['stdout_closed'] = facts['read_end_closed']
        if not facts['process_exited']:
            try:
                self._process.wait(timeout=max(0.0, value - self._clock()))
                facts['process_exited'] = True
                facts['exit_code'] = self._process.returncode
            except Exception:  # noqa: BLE001 - the failure stays visible
                # Only the broker that this parent holds is terminated, and
                # its exit is confirmed afterwards with a bounded wait.
                try:
                    self._process.terminate()
                    facts['terminated'] = True
                except Exception:  # noqa: BLE001 - the failure stays visible
                    pass
                try:
                    self._process.wait(timeout=max(0.0, value - self._clock()))
                    facts['process_exited'] = True
                    facts['exit_code'] = self._process.returncode
                except Exception:  # noqa: BLE001 - the failure stays visible
                    pass
        if not facts['process_handle_released']:
            facts.update(self._release_process_handle(facts['process_exited']))
        self.close_facts = facts
        self.reader_finished = facts['channel_reader_finished']
        return facts

    @staticmethod
    def _channel_complete(facts):
        """Whether the close of the channel confirmed every item of it.

        The items are the two ends of the channel, the reader of the
        channel, the workers of the endpoints and the original handles
        of their threads.  A fact that is missing is a missing fact and
        not a success.
        """
        if facts.get('channel_reader_finished') is not True:
            return False
        if facts.get('read_end_closed') is not True:
            return False
        if facts.get('write_end_closed') is not True:
            return False
        if int(facts.get('channel_retained_workers') or 0) != 0:
            return False
        if facts.get('worker_thread_handle_released') is not True:
            return False
        return True

    def _close_channel(self, facts):
        """Close the channel of the round and report its facts.

        The method returns the facts of the close of the channel and it
        never raises: the failure of the close of the channel is a fact
        of the round and it is named in the facts.
        """
        try:
            channel_facts = self._channel.close()
        except Exception:  # noqa: BLE001 - the failure stays visible
            facts['channel_closed'] = False
            return None
        facts['channel_closed'] = True
        facts['channel_reader_finished'] = getattr(self._channel,
                                                    'reader_finished', None)
        if not isinstance(channel_facts, dict):
            return None
        facts['write_end_closed'] = bool(channel_facts.get('write_end_closed'))
        facts['read_end_closed'] = bool(channel_facts.get('read_end_closed'))
        facts['channel_reader_error'] = channel_facts.get('reader_error')
        facts['channel_retained_workers'] = int(
            (channel_facts.get('write_retained_workers') or 0)
            + (channel_facts.get('read_retained_workers') or 0))
        facts['worker_thread_handle_released'] = bool(
            channel_facts.get('worker_thread_handle_released'))
        return channel_facts

    def _cleanup_deadline(self, deadline=None):
        """The ONE absolute deadline of the cleanup of the broker.

        The deadline is the one that the parent bound before it closed
        the handle.  It may only be shortened, never extended, and every
        wait of the cleanup recomputes the time that is left.
        """
        value = _require_deadline(deadline)
        if value is None:
            value = self.write_deadline
        if value is None:
            value = self._clock() + CLEANUP_BUDGET_SECONDS
        elif self.write_deadline is not None and value > self.write_deadline:
            value = self.write_deadline
        return value

    def _release_process_handle(self, exited=False):
        """Release the original process handle, explicitly and by platform.

        The release is recorded and it is never left to the garbage
        collector: on Windows the original handle of the process is closed
        through its own handle object and on POSIX the child process has
        no separate handle that the parent owns.

        The original handle of the process is closed **only** when the
        exit of the process was really confirmed.  A process whose exit
        was not confirmed may still be alive and its original handle is
        the only handle that the parent owns for it: the handle stays
        with its owner and a later close may release it.  A close that
        succeeds is never a proof that the process ended.
        """
        if not exited:
            return {'process_handle_released': False,
                    'process_handle_release_method': 'EXIT_NOT_CONFIRMED'}
        if os.name == 'nt':
            handle = getattr(self._process, '_handle', None)
            close = getattr(handle, 'Close', None)
            if close is None:
                return {'process_handle_released': False,
                        'process_handle_release_method': 'WINDOWS_NO_EXPLICIT_HANDLE'}
            try:
                close()
            except Exception:  # noqa: BLE001 - the failure stays visible
                return {'process_handle_released': False,
                        'process_handle_release_method': 'WINDOWS_HANDLE_CLOSE_FAILED'}
            return {'process_handle_released': True,
                    'process_handle_release_method': 'WINDOWS_HANDLE_CLOSE'}
        return {'process_handle_released': True,
                'process_handle_release_method': 'POSIX_PROCESS_EXIT'}


class _LauncherCustody:
    """The persistent owner of the original resources of a failed launch.

    The launcher owns the original process of the round until the
    channel of the round exists.  A channel that could not be built
    would leave the launcher with a running process and with pipes that
    nobody owns.

    Every original resource of such a launch enters this table **with
    its original reference** and it stays there until a confirmed
    release: the round never loses the ownership of a resource that it
    created, and a pid is never used to find a process again.

    The table is the recovery entry point of the launcher.  It is
    explicit and it is finite: a caller that wants the resources of a
    failed launch released asks for it.
    """

    def __init__(self):
        self._items = []
        self._lock = threading.Lock()

    def retain(self, kind, resource, detail=None):
        """Take one original resource into the table of the launcher.

        The table never names the same resource twice: a resource that
        is already with its owner is not entered a second time and the
        table converges.
        """
        with self._lock:
            for item in self._items:
                if item['kind'] == kind and item['resource'] is resource:
                    return resource
            self._items.append({'kind': kind, 'resource': resource,
                                'detail': detail})
        return resource

    def forget(self, resource):
        """Leave the table: the resource was handed over to its owner."""
        with self._lock:
            remaining = [item for item in self._items
                         if item['resource'] is not resource]
            self._items = remaining

    def items(self):
        """The original resources that the launcher still owns."""
        with self._lock:
            return list(self._items)

    def release(self, deadline=None):
        """Try to release every original resource of the table.

        The release of every resource is independent of the others: a
        resource that could not be released stays in the table with its
        original reference and it is named in the report.

        The wait of every resource uses the **same** absolute deadline.
        A recovery never opens a budget of its own and it never waits a
        fixed number of seconds for a process that may still be alive.
        """
        released = []
        remaining = []
        for item in self.items():
            resource = item['resource']
            try:
                if item['kind'] == 'process':
                    failures = _terminate_and_close_process(resource,
                                                            deadline=deadline)
                    if failures:
                        remaining.append(item)
                        continue
                else:
                    close = getattr(resource, 'close', None)
                    if callable(close):
                        close()
            except BaseException:  # noqa: BLE001 - the failure stays visible
                remaining.append(item)
                continue
            released.append(item['kind'])
        with self._lock:
            self._items = remaining
        return {'released': list(released),
                'retained': [item['kind'] for item in remaining]}


#: The one table of the original resources of the launches of this
#: package.  It is empty after a launch that was handed over and it
#: names the resources of a launch that was not.
_LAUNCHER_CUSTODY = _LauncherCustody()


def release_retained_launches(deadline=None):
    """The recovery entry point of the launcher of this package.

    The caller asks for the original resources of the launches that were
    not handed over to be released, and the report names the resources
    that could not be released.

    The wait of every resource uses the **same** absolute deadline of
    the round: a recovery never opens a budget of its own and it never
    waits a fixed number of seconds for a process that may still be
    alive.
    """
    return _LAUNCHER_CUSTODY.release(deadline=deadline)


def _launcher_custody_items():
    """The original resources that the launcher of this package owns.

    The list is a copy and every entry carries the **original** object:
    a pid is never used to find a process of the round again.
    """
    return _LAUNCHER_CUSTODY.items()


def _terminate_and_close_process(process, *, deadline=None, close_pipes=True):
    """Terminate one process of this round and close its pipes.

    The release is explicit and it is bounded: the process is
    terminated, its exit is confirmed and its pipes are closed.  The
    method never raises: it is the last step of a failure and it never
    replaces the failure that is on the way out.

    The wait uses the **same** absolute deadline of the round: a
    recovery never opens a budget of its own and it never waits a fixed
    number of seconds for a process that may still be alive.

    The original handle of the process is closed **only** when its exit
    was really confirmed.  A process that may still be alive keeps its
    handle and its owner: the handle is the only thing that may stop
    it and it is never closed under it.

    The report names every step that did not succeed, so that the
    caller can keep the original reference of a resource that is still
    open.
    """
    failures = {}
    try:
        process.terminate()
    except Exception as error:  # noqa: BLE001 - the failure stays visible
        failures['terminate'] = type(error).__name__
    budget = CLOSE_JOIN_SECONDS
    if deadline is not None:
        try:
            value = _require_deadline(deadline)
        except BrokerError:
            value = None
        if value is not None:
            budget = max(0.0, value - time.monotonic())
    exited = False
    try:
        process.wait(timeout=budget)
        exited = True
    except Exception as error:  # noqa: BLE001 - the failure stays visible
        failures['wait'] = type(error).__name__
    if exited and os.name == 'nt':
        # The original handle of the process is closed explicitly and it
        # is never left to the garbage collector.  A handle that could
        # not be closed keeps its owner.
        handle = getattr(process, '_handle', None)
        closer = getattr(handle, 'Close', None)
        if callable(closer):
            try:
                closer()
            except Exception as error:  # noqa: BLE001 - the failure stays visible
                failures['handle'] = type(error).__name__
    if close_pipes:
        for name in ('stdin', 'stdout', 'stderr'):
            stream = getattr(process, name, None)
            if stream is None:
                continue
            try:
                stream.close()
            except Exception as error:  # noqa: BLE001 - the failure stays visible
                failures[name] = type(error).__name__
    return failures


def _adopt_broker_process(process, *, channel_factory, executable,
                          executable_sha256, deadline=None):
    """Take the original process of the broker into the custody of a channel.

    The launcher owns the original process of the round until the
    channel of the round exists.  A channel that could not be built
    would leave the launcher with a running process and with pipes that
    nobody owns: the process is terminated, its exit is confirmed and
    its pipes are closed before the failure leaves.

    The **channel** is the only owner of the files of the process.  A
    channel that exists and that could not be handed over is closed by
    the launcher through the channel and never by closing the standard
    input and the standard output of the process by itself: a file that
    is closed under a live worker of the channel is a file that a
    worker is reading from.

    A resource that could not be released keeps its **original**
    reference in the table of the launcher: the session never received
    the process and the round never loses the ownership of it.

    The handover happens exactly once: the process that the channel
    received is the process that the parent owns.
    """
    channel = None
    try:
        channel = channel_factory()
        broker = BrokerProcess(process, executable, executable_sha256, channel)
    except BaseException:
        failures = {}
        if channel is not None:
            # The channel owns the files: it closes them.
            try:
                channel.close()
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                failures['channel'] = type(error).__name__
                _LAUNCHER_CUSTODY.retain('channel', channel,
                                         'close:' + type(error).__name__)
            failures.update(_terminate_and_close_process(
                process, deadline=deadline, close_pipes=False))
        else:
            failures.update(_terminate_and_close_process(process,
                                                         deadline=deadline))
        detail = '|'.join('%s:%s' % item for item in sorted(failures.items()))
        if 'terminate' in failures or 'wait' in failures:
            # The original process that could not be released stays with
            # its owner: the session never received it and the round
            # never loses the ownership of it.
            _LAUNCHER_CUSTODY.retain('process', process, detail)
        if channel is None:
            for name in ('stdin', 'stdout', 'stderr'):
                if name not in failures:
                    continue
                stream = getattr(process, name, None)
                if stream is not None:
                    _LAUNCHER_CUSTODY.retain(name, stream, detail)
        raise
    # The handover happened: the launcher does not own the process of
    # the round any more.
    _LAUNCHER_CUSTODY.forget(process)
    return broker


def launch_broker(plan, run_root, nonce):
    """Start the broker process of one round and keep its original handle.

    The launcher is a Windows only operation.  It refuses on every other
    platform before anything is started: a broker that cannot be started
    on Windows is never replaced by an unconstrained process and never by
    a simulation that pretends to be one.

    The nonce and the plan are checked **before** the first directory and
    the first file of the round exist, so that a refused launch leaves
    nothing behind.
    """
    if os.name != 'nt':
        raise BrokerError('BROKER_PLATFORM_UNSUPPORTED')
    if plan is None:
        raise BrokerError('BROKER_PLAN_INVALID')
    if not re.fullmatch(r'[0-9a-f]{32}', str(nonce)):
        raise BrokerError('BROKER_NONCE_INVALID')
    root = Path(run_root)
    raw = plan.sealed_bytes()
    digest = plan.sealed_sha256()
    directory = root / 'temp' / 'native'
    directory.mkdir(parents=True, exist_ok=True)
    plan_path = directory / 'custody-plan.json'
    with plan_path.open('xb') as stream:
        stream.write(raw)
    command = build_broker_command(plan_path=plan_path, plan_sha256=digest,
                                   run_root=root, nonce=nonce)
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=None, close_fds=True)
    # The original process of the round is with the launcher from the
    # moment of its creation.  The window between the creation of the
    # process and the handover of the channel is not a window without an
    # owner: a cancellation of the reading of the executable leaves the
    # process with its owner and it never disappears.
    _LAUNCHER_CUSTODY.retain('process', process, 'popened')
    executable = Path(command[0])
    try:
        executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
    except OSError:
        executable_sha256 = None
    except (KeyboardInterrupt, SystemExit):
        # The cancellation of the reading of the executable is cleaned
        # up and it continues to propagate.  The process keeps its owner
        # in the table of the launcher and the recovery of the launcher
        # is the entry that releases it.
        raise
    return _adopt_broker_process(
        process,
        channel_factory=lambda: StreamChannel(process.stdout, process.stdin,
                                               custody=_LAUNCHER_CUSTODY),
        executable=str(executable), executable_sha256=executable_sha256)


def read_sealed_plan(path, digest):
    """Read one sealed plan document and check its digest."""
    target = Path(path)
    if not target.is_file():
        raise BrokerError('BROKER_PLAN_MISSING')
    with target.open('rb') as stream:
        raw = stream.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise BrokerError('BROKER_PLAN_TOO_LARGE')
    if hashlib.sha256(raw).hexdigest() != digest:
        raise BrokerError('BROKER_PLAN_DIGEST_DRIFT')
    try:
        document = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as error:
        raise BrokerError('BROKER_PLAN_INVALID') from error
    return document


def main(argv=None):
    """The production entry of the broker.

    The entry is fixed: one sealed plan, its digest, the run root of the
    round and the nonce of the session.  The plan is validated again here,
    because the broker never trusts a document that it did not check.
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--run-root', required=True)
    parser.add_argument('--nonce', required=True)
    arguments = parser.parse_args(argv)
    if not re.fullmatch(r'[0-9a-f]{32}', str(arguments.nonce)):
        sys.stderr.write('BROKER_REFUSED BROKER_NONCE_INVALID\n')
        sys.stderr.flush()
        return 2
    document = read_sealed_plan(arguments.plan, arguments.plan_sha256)
    try:
        plan = validate_launch_plan(document, now=time.time())
    except CustodyError as error:
        sys.stderr.write('BROKER_REFUSED ' + error.code + '\n')
        sys.stderr.flush()
        return 2
    if plan.sealed_sha256() != arguments.plan_sha256:
        # The seal of the plan that the broker validated is not the seal
        # that the parent wrote: the document drifted on its way here.
        sys.stderr.write('BROKER_REFUSED BROKER_PLAN_SEAL_DRIFT\n')
        sys.stderr.flush()
        return 2
    try:
        win32 = WindowsApi()
    except BrokerError as error:
        sys.stderr.write('BROKER_REFUSED ' + error.code + '\n')
        sys.stderr.flush()
        return 2
    core = BrokerCore(win32=win32, plan=plan, run_root=arguments.run_root)
    # The ONE context of the round is handed to the transport of the
    # channel and to its endpoints: the channel, the endpoints and the
    # workers of the endpoints read the same absolute deadline and none
    # of them keeps a budget of its own.
    transport = StreamChannel(sys.stdin.buffer, sys.stdout.buffer, api=win32,
                              context=core.context)
    loop = BrokerLoop(core=core, transport=transport, plan=plan,
                      nonce=arguments.nonce)
    try:
        return loop.run()
    finally:
        # The round releases its own resources in the loop; the entry only
        # closes the channel and never swallows a failure of the round.
        try:
            transport.close()
        except Exception:  # noqa: BLE001 - the failure stays visible
            pass


if __name__ == '__main__':
    sys.exit(main())
