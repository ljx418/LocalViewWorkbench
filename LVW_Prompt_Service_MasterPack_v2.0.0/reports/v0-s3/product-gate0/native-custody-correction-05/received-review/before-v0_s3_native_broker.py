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
        offset of the array and never through a pointer field.  The
        answer is only complete when the returned length and the two
        counts agree with the number of the ids that were read: a list
        that was truncated by the buffer is unknown and never an empty
        job.
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
        if assigned > capacity or listed > capacity:
            raise BrokerError('BROKER_DESCENDANT_LIMIT',
                              'assigned=%d:listed=%d' % (assigned, listed))
        if assigned > listed:
            # The buffer was too small: the list is incomplete and the
            # answer is unknown.  It is never an empty job.
            raise BrokerError('BROKER_JOB_QUERY_TRUNCATED',
                              'assigned=%d:listed=%d' % (assigned, listed))
        needed = header_size + listed * pointer_size
        reported = int(returned.value)
        if reported and reported < needed:
            raise BrokerError('BROKER_JOB_QUERY_TRUNCATED',
                              'returned=%d:needed=%d' % (reported, needed))
        if listed == 0:
            if assigned != 0:
                raise BrokerError('BROKER_JOB_QUERY_TRUNCATED',
                                  'assigned=%d:listed=0' % assigned)
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
        try:
            inherited = (ctypes.c_void_p * 3)(stdout_handle, stderr_handle, null)
            size = ctypes.c_size_t(0)
            attribute_list = None
            try:
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
            finally:
                # The attribute list and the null handle are released
                # here, and the last error of the failure was already
                # read before this cleanup began.
                if attribute_list is not None:
                    kernel32.DeleteProcThreadAttributeList(attribute_list)
                self._close_quietly(null, failures)
        except BrokerError as error:
            if failures:
                error.detail = ((error.detail or '') + '|cleanup='
                                + ','.join(failures))
            raise
        try:
            creation = self._process_creation_time(information.hProcess)
        except BaseException:
            # The process exists but it was not adopted.  It is stopped
            # through its own original handle and both of its handles
            # are closed here, so that it never survives the method.
            self._release_created(information.hProcess, information.hThread, failures)
            raise
        return CreatedProcess(information.hProcess, information.hThread,
                              int(information.dwProcessId), creation, failures)

    def _close_quietly(self, handle, failures):
        """Close one handle and name a failure of the close."""
        try:
            if not self._api.kernel32.CloseHandle(handle):
                failures.append('CloseHandle:last_error=%d' % self._last_error())
                return False
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            failures.append('CloseHandle:' + type(error).__name__)
            return False
        return True

    def _release_created(self, process, thread, failures):
        """Release a process that was created but never adopted.

        The process is stopped through its own original handle, its exit
        is confirmed and both of its handles are closed.  A failure of
        one of the steps is named and the other steps still run: a handle
        is never left to the garbage collector.
        """
        try:
            if not self._api.kernel32.TerminateProcess(process, 1):
                failures.append('TerminateProcess:last_error=%d' % self._last_error())
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            failures.append('TerminateProcess:' + type(error).__name__)
        try:
            self._api.kernel32.WaitForSingleObject(process, WAIT_MILLISECONDS)
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            failures.append('WaitForSingleObject:' + type(error).__name__)
        self._close_quietly(thread, failures)
        self._close_quietly(process, failures)
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
        return True

    # -- the pipes ---------------------------------------------------------
    def create_pipe(self, name):
        """Create one pipe.  Only the write end is inheritable.

        The security attributes of the pipe say that the ends are
        inheritable and the inherit flag of the *read* end is cleared
        right afterwards.  A pipe that was created with ``NULL``
        security attributes can never be inherited at all.
        """
        ctypes = self._api.types['ctypes']
        read = self._api.types['HANDLE']()
        write = self._api.types['HANDLE']()
        attributes = self._security_attributes(True)
        if not self._api.kernel32.CreatePipe(ctypes.byref(read), ctypes.byref(write),
                                             ctypes.byref(attributes), 0):
            error = self._last_error()
            raise BrokerError('BROKER_PIPE_FAILED', 'last_error=%d' % error)
        if not self._api.kernel32.SetHandleInformation(read, self.HANDLE_FLAG_INHERIT, 0):
            error = self._last_error()
            failures = []
            self._close_quietly(read, failures)
            self._close_quietly(write, failures)
            raise BrokerError('BROKER_PIPE_INHERIT_FAILED',
                              'last_error=%d%s' % (error,
                                                   ('|cleanup=' + ','.join(failures))
                                                   if failures else ''))
        return read, write

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
    of its successful creation.  A handle leaves the table when its owner
    took it: the reader that took a read end, or the core that took the
    original handles of a process.  A handle that is still in the table
    when the round ends is a resource that this round still owns, and it
    is closed and named.

    A handle of another owner is never in this table and it is never
    touched.
    """

    def __init__(self, win32):
        self._win32 = win32
        self._items = []

    def add(self, handle, kind, *, role=None):
        item = {'handle': handle, 'kind': kind, 'role': role,
                'owner': 'PENDING'}
        self._items.append(item)
        return item

    def take(self, handle):
        """Remove one handle from the table: its owner holds it now."""
        for index, item in enumerate(self._items):
            if item['handle'] == handle:
                del self._items[index]
                return item
        return None

    def transfer(self, handle, owner):
        """Hand one pending handle over to its owner.

        The owner of the handle is only changed after the handover
        succeeded.  The handle stays in the table until it is closed: it
        is a resource that this round owns and it is named until then.
        A handle that could not be handed over keeps the owner
        ``PENDING`` and it is closed by the round.
        """
        for item in self._items:
            if item['handle'] == handle:
                item['owner'] = owner
                return item
        return None

    def pending(self):
        """The handles that this round still owns and has not closed."""
        return [dict(item) for item in self._items]

    def close_all(self, failures):
        """Close every handle that is still pending and name the failures.

        A handle that could not be closed stays in the table: it is a
        resource that this round still owns and it is named in the
        evidence of the round.  It is never left to the garbage
        collector and it is never closed twice.
        """
        remaining = []
        for item in self._items:
            try:
                self._win32.close_handle(item['handle'])
            except BrokerError as error:
                failures.append({'stage': 'close_pending', 'kind': item['kind'],
                                 'role': item['role'], 'code': error.code})
                remaining.append(item)
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                failures.append({'stage': 'close_pending', 'kind': item['kind'],
                                 'role': item['role'],
                                 'error_type': type(error).__name__})
                remaining.append(item)
            else:
                item['closed'] = True
        self._items = remaining
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

    def __init__(self, *, win32, plan, run_root, clock=None, wall=None):
        self.win32 = win32
        self.plan = plan
        self.run_root = Path(run_root)
        self._clock = clock or time.monotonic
        self._wall = wall or time.time
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
        self._released = False
        self._abort_reported = False
        self.broker_identity = {
            'pid': os.getpid(),
            'executable': sys.executable,
            'reported_by_the_broker': True,
            'identity_source': 'CHILD_CLAIM',
        }

    # -- the arming of the round ------------------------------------------
    def arm(self):
        """Create the job object of the round.

        The job is created before any process of the round exists, so that
        every process of the round can be assigned to it before it runs.
        """
        if self.state != 'NEW':
            raise BrokerError('BROKER_STATE_INVALID', self.state)
        self.state = 'VALIDATED'
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
            self._close_handle('job', self.job)
            self._pending.take(self.job)
            self.job = None
            self.state = 'UNKNOWN_RETAINED'
            raise
        self.job_kill_on_close = True
        self.state = 'ARMED'
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
            stdout_read, stdout_write = self.win32.create_pipe('stdout')
            self._pending.add(stdout_read, 'pipe_read', role=name)
            self._pending.add(stdout_write, 'pipe_write', role=name)
            stderr_read, stderr_write = self.win32.create_pipe('stderr')
            self._pending.add(stderr_read, 'pipe_read', role=name)
            self._pending.add(stderr_write, 'pipe_write', role=name)
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'create_pipe', 'role': name, 'code': error.code})
            self._abort_round('PIPE_FAILED')
            raise
        try:
            created = self.win32.create_process_suspended(
                executable=command['executable'], arguments=command['arguments'],
                working_directory=command['working_directory'],
                stdout_handle=stdout_write, stderr_handle=stderr_write,
                environment=command['environment'])
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'create_process', 'role': name,
                                  'code': error.code})
            self._abort_round('CREATE_FAILED')
            raise
        # The write ends belong to the child now; the broker keeps the read
        # ends only.  The copies of the broker are closed and they leave
        # the pending table: they are not pending any more.
        self._release_pending(stdout_write)
        self._release_pending(stderr_write)
        record['created'] = True
        record['pid'] = created.pid
        record['creation_time'] = created.creation_time
        record['process_handle'] = created.process
        record['thread_handle'] = created.thread
        # The original handles of the process enter the pending table of
        # the round in the moment of their creation and the core takes
        # them right away: it is their owner from now on and it closes
        # them when it releases the records.
        self._pending.add(created.process, 'process', role=name)
        self._pending.add(created.thread, 'thread', role=name)
        self._pending.transfer(created.process, 'CORE')
        self._pending.transfer(created.thread, 'CORE')
        record['pending_handles'].append({'kind': 'process', 'owner': 'CORE'})
        record['pending_handles'].append({'kind': 'thread', 'owner': 'CORE'})
        for failure in getattr(created, 'failures', ()):
            self.failures.append({'stage': 'create_process', 'role': name,
                                  'code': failure})
        try:
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
            self.win32.resume_thread(created.thread)
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'resume', 'role': name, 'code': error.code})
            self._abort_round('RESUME_FAILED')
            raise
        record['resumed'] = True
        self._start_reader(record, stdout_read, 'stdout')
        self._start_reader(record, stderr_read, 'stderr')

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

        The reader is the owner of the read end from now on: the handle
        leaves the pending table of the round and the reader closes it
        when it is stopped.
        """
        reader = _BoundedStreamReader(self.win32, handle, limit=MAX_STREAM_BYTES,
                                      name=record['role'] + '-' + stream)
        self.readers.append(reader)
        self._pending.transfer(handle, 'READER')
        record['pending_handles'].append({'kind': 'pipe_read',
                                          'stream': stream, 'owner': 'READER'})
        reader.start()

    def _close_handle(self, kind, handle):
        """Close one owned handle and name a failure of the close.

        A handle that was closed leaves the pending table of the round.
        A handle that could not be closed stays pending: it is a
        resource that this round still owns and it is named.
        """
        try:
            self.win32.close_handle(handle)
        except BrokerError as error:
            self.failures.append({'stage': 'close_handle', 'kind': kind,
                                  'code': error.code})
            return False
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self.failures.append({'stage': 'close_handle', 'kind': kind,
                                  'error_type': type(error).__name__})
            return False
        self._pending.take(handle)
        return True

    def _close_readers(self):
        """Stop the readers of the children and close their read handles.

        The wait of a reader is bounded and its state is recorded.  A
        reader that is still blocked when the wait is over is a *fact* of
        this round and it is reported as such: a daemon thread that is
        still running is not a finished thread, and the read end of such
        a reader is not closed under it.
        """
        for reader in self.readers:
            reader.finished.wait(READER_JOIN_SECONDS)
            reader.join(READER_JOIN_SECONDS)
            alive = reader.is_alive()
            self.reader_states.append({'name': reader.name,
                                       'finished': reader.finished.is_set(),
                                       'joined': not alive,
                                       'alive': alive,
                                       'error': reader.error})
            if alive:
                # The reader still holds the read end.  The handle is not
                # closed under a running reader: it leaves the pending
                # table with its owner and the round keeps the fact.
                self._pending.take(reader.handle)
                self.reader_states[-1]['handle_retained'] = True
                self.failures.append({'stage': 'reader_not_stopped',
                                      'name': reader.name,
                                      'code': 'BROKER_READER_NOT_STOPPED'})
                continue
            self._close_handle('stream', reader.handle)

    def _terminate_owned(self, handle, record, reason):
        """Stop one owned process through its own original handle.

        No pid is used and no name is used: only the handle that this core
        created is passed to the operating system.
        """
        try:
            self.win32.terminate_process(handle, 1)
            record['terminated'] = True
        except BrokerError as error:
            self.failures.append({'stage': 'terminate', 'reason': reason,
                                  'code': error.code})
            return False
        try:
            record['exited'] = bool(self.win32.wait_process(handle, WAIT_MILLISECONDS))
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
    def stop(self, reason='STOP', *, force_unknown=False):
        """Stop the round and release every handle that this core holds.

        The stop is bounded and it is idempotent: a repeated stop does not
        terminate anything twice and it does not change the evidence of
        the round.  Every handle is reported on its own, so a handle that
        could not be closed stays visible and the round becomes unknown
        instead of a silent success.

        The stop has its own ``finally``: the termination and the release
        of the handles happen even when the diagnosis of the round failed,
        and the first failure of the round is not replaced by the failure
        of the diagnosis.
        """
        if self.state in ('RELEASED', 'UNKNOWN_RETAINED'):
            return self.evidence()
        if self._released:
            return self.evidence()
        self._released = True
        self.state = 'STOPPING'
        self.stop_reason = reason
        primary = None
        try:
            try:
                self._collect_stream_counts()
            except Exception as error:  # noqa: BLE001 - the diagnosis never blocks
                self.failures.append({'stage': 'diagnostic',
                                      'error_type': type(error).__name__})
                primary = error
            self._terminate_the_round()
            self._query_job()
            self._close_readers()
            self._release_the_records()
            self._release_the_job()
            retained = self._pending.close_all(self.failures)
            if retained:
                self.failures.append({'stage': 'pending_resources',
                                      'count': len(retained),
                                      'code': 'BROKER_PENDING_RESOURCES_RETAINED'})
        except BaseException as error:  # noqa: BLE001 - the cleanup still runs
            primary = error
            self.failures.append({'stage': 'stop', 'error_type': type(error).__name__})
        released = self._is_released()
        self.state = 'UNKNOWN_RETAINED' if (force_unknown or not released) else 'RELEASED'
        if primary is not None:
            # The first failure of the round is not swallowed: the caller
            # sees it after the round was cleaned up.
            raise primary
        return self.evidence()

    def _terminate_the_round(self):
        """Terminate the job of the round and wait for its processes."""
        if self.job is not None:
            try:
                self.win32.terminate_job(self.job, 1)
                self.job_terminated = True
            except BrokerError as error:
                self.failures.append({'stage': 'terminate_job', 'code': error.code})
        for record in self.records:
            handle = record.get('process_handle')
            if handle is None or record['exited']:
                continue
            if not record['resumed']:
                # The process never ran: it is stopped through its own
                # suspended handle.
                self._terminate_owned(handle, record, 'SUSPENDED_AT_STOP')
                continue
            try:
                record['exited'] = bool(self.win32.wait_process(handle, WAIT_MILLISECONDS))
            except BrokerError as error:
                self.failures.append({'stage': 'wait', 'role': record['role'],
                                      'code': error.code})
            if record['exited']:
                try:
                    record['exit_code'] = self.win32.exit_code(handle)
                except BrokerError as error:
                    self.failures.append({'stage': 'exit_code', 'role': record['role'],
                                          'code': error.code})

    def _release_the_records(self):
        """Close the original handles of the processes of the round."""
        for record in self.records:
            thread = record.get('thread_handle')
            if thread is not None:
                record['thread_handle_closed'] = self._close_handle('thread', thread)
                record['thread_handle'] = None
            process = record.get('process_handle')
            if process is not None:
                record['process_handle_closed'] = self._close_handle('process', process)
                record['process_handle'] = None

    def _release_the_job(self):
        """Close the original handle of the job of the round."""
        if self.job is not None:
            self.job_closed = self._close_handle('job', self.job)
            self._pending.take(self.job)
            self.job = None

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
        """
        if self.job is None:
            self.job_active_known = False
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
        self.facts = {'name': name, 'owner': 'POSIX_ENDPOINT',
                      'descriptor': self._descriptor}

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
            self._check(deadline, cancel)
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
            self._check(deadline, cancel)
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
        """Close the original descriptor of this endpoint, exactly once."""
        if self._closed:
            self.facts['closed'] = False
            self.facts['already_closed'] = True
            return self.facts
        self._closed = True
        try:
            self._syscalls.close(self._file)
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.facts['closed'] = False
            self.facts['error_type'] = type(error).__name__
            return self.facts
        self.facts['closed'] = True
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
    """

    def __init__(self, api, handle, *, kind, action, name):
        super().__init__(daemon=True, name=name)
        self.api = api
        self.handle = handle
        self.kind = kind
        self.action = action
        self._requests = queue.Queue(maxsize=1)
        self.inside = threading.Event()
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.thread_handle = None
        self.joined = False
        # The name of the cancel flag is not ``_stop``: the base class of
        # the thread uses that name for its own method and a shadow of it
        # would break the join of the thread.
        self._stop_event = threading.Event()

    def run(self):
        try:
            self.thread_handle = self.api.duplicate_current_thread_handle()
        except BrokerError as error:
            self.error = error.code
            self.done.set()
            return
        while not self._stop_event.is_set():
            try:
                request = self._requests.get(timeout=0.1)
            except queue.Empty:
                continue
            self.error = None
            self.result = None
            try:
                self.inside.set()
                self.result = self.action(request)
            except BrokerError as error:
                self.error = error.code
            except Exception as error:  # noqa: BLE001 - the failure stays visible
                self.error = type(error).__name__
            finally:
                self.done.set()

    def submit(self, request):
        """Hand one request to the worker."""
        self.done.clear()
        self._requests.put(request)

    def request_cancel(self):
        """Ask for the cancellation of the operation of this worker.

        The request is not a completion.  The caller has to wait for the
        real completion of the worker and to join it.
        """
        if self.thread_handle is None:
            return 'NO_HANDLE'
        try:
            return self.api.cancel_synchronous_io(self.thread_handle)
        except BrokerError as error:
            self.error = error.code
            return 'FAILED'

    def stop(self):
        """Ask the worker to end its loop."""
        self._stop_event.set()

    def join_bounded(self, seconds):
        """Join the worker and report whether it really stopped."""
        self.join(seconds)
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
    """

    def __init__(self, file_object, *, name, api=None, clock=None):
        self._file = file_object
        self._name = name
        self._api = api
        self._clock = clock or time.monotonic
        self._closed = False
        self._reader = None
        self._writer = None
        self._retained = []
        import msvcrt
        self._handle = msvcrt.get_osfhandle(file_object.fileno())
        self.facts = {'name': name, 'owner': 'WINDOWS_ENDPOINT'}

    def _start(self, kind, action):
        worker = _WindowsPipeWorker(self._api, self._handle, kind=kind,
                                    action=action,
                                    name='lvw-native-custody-pipe-' + kind)
        worker.start()
        return worker

    def _await(self, worker, request, deadline, cancel):
        """Wait for the completion of one worker, bounded and cancellable."""
        worker.submit(request)
        while True:
            if cancel is not None and cancel.is_set():
                self._cancel(worker)
                raise BrokerError('BROKER_PIPE_CANCELLED', self._name)
            if deadline is not None and self._clock() >= deadline:
                self._cancel(worker)
                raise BrokerError('BROKER_PIPE_TIMEOUT', self._name)
            if worker.done.wait(POLL_SLICE_SECONDS):
                break
        if worker.error:
            raise BrokerError(worker.error, self._name)
        return worker.result

    def _cancel(self, worker):
        """Cancel one worker and prove that it really stopped."""
        state = worker.request_cancel()
        if not worker.done.wait(CLOSE_JOIN_SECONDS):
            # The worker did not stop: it keeps its owner reference and
            # the round becomes unknown.  It is never terminated blindly
            # and it is never waited for without a bound.
            self._retained.append(worker)
            raise BrokerError('BROKER_PIPE_CANCEL_NOT_CONFIRMED',
                              '%s:%s' % (self._name, state))
        worker.join_bounded(CLOSE_JOIN_SECONDS)
        if not worker.joined:
            self._retained.append(worker)
            raise BrokerError('BROKER_PIPE_CANCEL_NOT_CONFIRMED', self._name)

    def read(self, deadline=None, cancel=None):
        """Read one block of the pipe, bounded by the deadline."""
        if self._reader is None:
            self._reader = self._start('read', self._read_block)
        return self._await(self._reader, None, deadline, cancel)

    def write(self, data, deadline=None, cancel=None):
        """Write the whole block, bounded by the deadline."""
        if self._writer is None:
            self._writer = self._start('write', self._write_block)
        return self._await(self._writer, bytes(data), deadline, cancel)

    def _read_block(self, request):
        return self._api.read_stream(self._handle, PIPE_READ_BYTES)

    def _write_block(self, request):
        return self._api.write_stream(self._handle, request)

    def close(self):
        """Close the original handle of this endpoint, exactly once."""
        if self._closed:
            self.facts['closed'] = False
            self.facts['already_closed'] = True
            return self.facts
        self._closed = True
        for worker in (self._reader, self._writer):
            if worker is None:
                continue
            worker.stop()
            if not worker.done.is_set():
                worker.request_cancel()
                worker.join_bounded(CLOSE_JOIN_SECONDS)
            if worker.is_alive():
                self._retained.append(worker)
        try:
            self._file.close()
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.facts['closed'] = False
            self.facts['error_type'] = type(error).__name__
            return self.facts
        self.facts['closed'] = True
        self.facts['retained_workers'] = len(self._retained)
        return self.facts


def _make_endpoint(file_object, name, *, api=None, clock=None):
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
    """
    if os.name == 'nt':
        if api is None:
            api = WindowsApi()
        return _WindowsPipeEndpoint(file_object, name=name, api=api, clock=clock)
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
                 read_endpoint=None, write_endpoint=None, clock=None, api=None):
        self._reader = read_endpoint or _make_endpoint(reader, name + '-read',
                                                       clock=clock, api=api)
        self._writer = write_endpoint or _make_endpoint(writer, name + '-write',
                                                        clock=clock, api=api)
        self._queue = queue.Queue(maxsize=max_frames)
        self._max_frames = max_frames
        self._max_frame_bytes = max_frame_bytes
        self._count = 0
        self._overflow = False
        self._eof = False
        self._error = None
        self._buffer = b''
        self._deadline = None
        self._cancel = threading.Event()
        self.reader_alive = None
        self.reader_finished = None
        self._thread = threading.Thread(target=self._drain, daemon=True,
                                        name='lvw-native-custody-channel')
        self._thread.start()

    def bind_deadline(self, deadline):
        """Bind the absolute deadline of the round to the channel."""
        self._deadline = _require_deadline(deadline)

    def _drain(self):
        try:
            while True:
                block = self._reader.read(self._deadline, self._cancel)
                if not block:
                    break
                self._buffer += block
                while True:
                    index = self._buffer.find(b'\n')
                    if index < 0:
                        break
                    raw = self._buffer[:index + 1]
                    self._buffer = self._buffer[index + 1:]
                    if len(raw) > self._max_frame_bytes:
                        self._overflow = True
                        return
                    self._count += 1
                    if self._count > self._max_frames:
                        self._overflow = True
                        return
                    while True:
                        try:
                            self._queue.put(raw, timeout=0.5)
                            break
                        except queue.Full:
                            if self._eof:
                                return
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self._error = getattr(error, 'code', None) or type(error).__name__
        finally:
            self._eof = True

    def read(self, timeout):
        """One raw frame, ``None`` when nothing arrived, ``b''`` at the end."""
        if self._overflow:
            raise BrokerError('BROKER_CHANNEL_OVERFLOW')
        try:
            return self._queue.get(timeout=max(0.0, timeout))
        except queue.Empty:
            if self._eof:
                return b''
            return None

    def write(self, raw, deadline=None):
        """Write one frame, bounded by the deadline of the round."""
        if len(raw) > self._max_frame_bytes:
            raise BrokerError('BROKER_CHANNEL_FRAME_TOO_LARGE')
        target = self._deadline if deadline is None else deadline
        return self._writer.write(raw, target, self._cancel)

    def close(self):
        """Close the channel and report whether the reader really stopped.

        The reader thread is joined with a bounded wait.  A reader that
        did not stop is reported as such: a daemon thread is not a
        finished thread, so the fact that the reader is still alive is
        kept visible instead of being hidden behind the close.  The read
        end is closed by its owner only when the reader really stopped.
        """
        facts = {}
        self._cancel.set()
        try:
            write_facts = self._writer.close()
            facts['write_end_closed'] = bool(write_facts.get('closed'))
        except Exception:  # noqa: BLE001 - the failure stays visible
            facts['write_end_closed'] = False
        self._thread.join(CLOSE_JOIN_SECONDS)
        self.reader_alive = self._thread.is_alive()
        self.reader_finished = not self.reader_alive
        facts['reader_finished'] = self.reader_finished
        if self.reader_alive:
            # The reader is still inside the pipe: the read end is not
            # closed under it.  It stays owned by the channel and the
            # round keeps the fact.
            facts['read_end_closed'] = False
            return facts
        try:
            read_facts = self._reader.close()
            facts['read_end_closed'] = bool(read_facts.get('closed'))
        except Exception:  # noqa: BLE001 - the failure stays visible
            facts['read_end_closed'] = False
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

    # -- the run -----------------------------------------------------------
    def run(self):
        """Run the round and always release what the round owns.

        The loop has a ``finally`` that does not depend on the diagnosis
        of the round and not on the success of a write: a round that
        could not write its first reply still releases the job and the
        handles that it created.
        """
        self._fix_deadline()
        binder = getattr(self.transport, 'bind_deadline', None)
        if callable(binder):
            # The transport of the channel is bound to the deadline of
            # the round before the job of the round exists: a read or a
            # write of the channel can never outlive the round.
            binder(self._deadline_mono)
        try:
            try:
                self.core.arm()
            except BrokerError as error:
                self._reply('REFUSED', self.core.state, {'code': error.code},
                            terminal=True)
                self._write_receipt('ARM_FAILED')
                return 3
            self._reply('READY', self.core.state, {'broker': self.core.broker_identity})
            try:
                self.core.launch()
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
            self._frames += 1
            if self._frames > self._max_frames:
                return self._stop('FRAME_COUNT_EXCEEDED', 4)
            try:
                frame = decode_command(raw, run_id=self.plan.run_id,
                                       candidate_sha=self.plan.candidate_sha,
                                       authorization_sha256=self.plan.authorization_sha256,
                                       nonce=self.nonce, last_sequence=self._last_sequence)
            except CustodyError as error:
                self.core.failures.append({'stage': 'channel', 'code': error.code})
                return self._stop('CHANNEL_REFUSED', 4)
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

    def __init__(self, process, executable, executable_sha256, channel):
        self._process = process
        self._channel = channel
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

    def close(self):
        """Close the original handle of the broker.

        The close happens exactly once and it happens even when the
        exchange of the stop failed: the resource of this round is
        released either way.

        The facts of the close are returned and they are named: a handle
        that was not closed, a reader that did not stop and a process that
        did not exit are facts of the round and they are never hidden
        behind a success.  The release of the original process handle is
        explicit and it is never left to the garbage collector.

        The waits of the close are bounded by one budget: the budget
        that the parent bound before it closed the handle, and never more
        than the fixed cleanup budget of the round.
        """
        budget = self._cleanup_budget()
        facts = {'channel_closed': False,
                 'channel_reader_finished': None,
                 'write_end_closed': False,
                 'read_end_closed': False,
                 'stdin_closed': False,
                 'stdout_closed': False,
                 'process_exited': False,
                 'exit_code': None,
                 'terminated': False,
                 'process_handle_released': False,
                 'process_handle_release_method': None,
                 'cleanup_budget_seconds': budget}
        try:
            channel_facts = self._channel.close()
            facts['channel_closed'] = True
            facts['channel_reader_finished'] = self._channel.reader_finished
            if isinstance(channel_facts, dict):
                facts['write_end_closed'] = bool(channel_facts.get('write_end_closed'))
                facts['read_end_closed'] = bool(channel_facts.get('read_end_closed'))
        except Exception:  # noqa: BLE001 - the failure stays visible
            facts['channel_closed'] = False
        try:
            self._process.stdin.close()
            facts['stdin_closed'] = True
        except Exception:  # noqa: BLE001 - the failure stays visible
            pass
        try:
            self._process.wait(timeout=budget)
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
                self._process.wait(timeout=budget)
                facts['process_exited'] = True
                facts['exit_code'] = self._process.returncode
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass
        try:
            self._process.stdout.close()
            facts['stdout_closed'] = True
        except Exception:  # noqa: BLE001 - the failure stays visible
            pass
        facts.update(self._release_process_handle())
        self.close_facts = facts
        self.reader_finished = facts['channel_reader_finished']
        return facts

    def _cleanup_budget(self):
        """The one budget of the cleanup of the broker.

        The budget is the smaller of the fixed cleanup budget of the
        round and the time that is left until the deadline that the
        parent bound.  A round without a remaining time cleans up
        immediately and it keeps what it could not prove.
        """
        budget = float(CLOSE_JOIN_SECONDS)
        if self.write_deadline is not None:
            budget = min(budget, max(0.0, self.write_deadline - time.monotonic()))
        return budget

    def _release_process_handle(self):
        """Release the original process handle, explicitly and by platform.

        The release is recorded and it is never left to the garbage
        collector: on Windows the original handle of the process is closed
        through its own handle object and on POSIX the child process has
        no separate handle that the parent owns.
        """
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
    channel = StreamChannel(process.stdout, process.stdin)
    executable = Path(command[0])
    try:
        executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
    except OSError:
        executable_sha256 = None
    return BrokerProcess(process, str(executable), executable_sha256, channel)


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
    transport = StreamChannel(sys.stdin.buffer, sys.stdout.buffer, api=win32)
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
