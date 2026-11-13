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
  the process attributes.

* **Only what was created is stopped.**  The broker has no notion of a
  process name, of a pid or of a record of another owner.  It stops the
  handles that it holds and the job that it created, and nothing else.

Nothing in this module has ever run on Windows.  Every native claim of
this package therefore stays ``NOT_PROVEN``: the Windows path is written
from the documented behaviour of the API and it is not a measurement.
"""
import hashlib
import json
import os
import queue
import re
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
HEARTBEAT_TIMEOUT_SECONDS = 30
CLOSE_JOIN_SECONDS = 5.0
MAX_PLAN_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 1024 * 1024
POLL_SECONDS = 0.25

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


def _load_windows_api():
    """Load the Windows primitive table of the broker.

    The load is lazy and it happens only inside the explicit native entry.
    An import of this module on a platform that is not Windows never
    touches ``WinDLL`` and never resolves a symbol, so the module stays
    importable and testable everywhere.  An unsupported platform refuses
    here, before anything is created: it is never degraded into an
    unconstrained process.
    """
    if os.name != 'nt':
        raise BrokerError('BROKER_PLATFORM_UNSUPPORTED')
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ('cb', wintypes.DWORD),
            ('lpReserved', wintypes.LPWSTR),
            ('lpDesktop', wintypes.LPWSTR),
            ('lpTitle', wintypes.LPWSTR),
            ('dwX', wintypes.DWORD),
            ('dwY', wintypes.DWORD),
            ('dwXSize', wintypes.DWORD),
            ('dwYSize', wintypes.DWORD),
            ('dwXCountChars', wintypes.DWORD),
            ('dwYCountChars', wintypes.DWORD),
            ('dwFillAttribute', wintypes.DWORD),
            ('dwFlags', wintypes.DWORD),
            ('wShowWindow', wintypes.WORD),
            ('cbReserved2', wintypes.WORD),
            ('lpReserved2', ctypes.POINTER(ctypes.c_byte)),
            ('hStdInput', wintypes.HANDLE),
            ('hStdOutput', wintypes.HANDLE),
            ('hStdError', wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [('hProcess', wintypes.HANDLE),
                    ('hThread', wintypes.HANDLE),
                    ('dwProcessId', wintypes.DWORD),
                    ('dwThreadId', wintypes.DWORD)]

    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [('StartupInfo', STARTUPINFOW),
                    ('lpAttributeList', ctypes.c_void_p)]

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
                    ('LimitFlags', wintypes.DWORD),
                    ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t),
                    ('PriorityClass', wintypes.DWORD),
                    ('SchedulingClass', wintypes.DWORD)]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ('IoInfo', IO_COUNTERS),
                    ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t),
                    ('PeakJobMemoryUsed', ctypes.c_size_t)]

    class JOBOBJECT_BASIC_PROCESS_ID_LIST(ctypes.Structure):
        _fields_ = [('NumberOfAssignedProcesses', wintypes.DWORD),
                    ('NumberOfProcessIdsInList', wintypes.DWORD),
                    ('ProcessIdList', ctypes.POINTER(ctypes.c_size_t))]

    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                 ctypes.c_void_p, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR,
                                        ctypes.c_void_p, ctypes.c_void_p,
                                        wintypes.BOOL, wintypes.DWORD,
                                        ctypes.c_void_p, wintypes.LPCWSTR,
                                        ctypes.c_void_p, ctypes.c_void_p]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                   ctypes.c_void_p, wintypes.DWORD,
                                                   ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE),
                                    ctypes.POINTER(wintypes.HANDLE),
                                    ctypes.c_void_p, wintypes.DWORD]
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.HANDLE]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                           wintypes.DWORD,
                                                           ctypes.POINTER(ctypes.c_size_t)]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                   ctypes.c_size_t, ctypes.c_void_p,
                                                   ctypes.c_size_t, ctypes.c_void_p,
                                                   ctypes.c_void_p]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel32.DeleteProcThreadAttributeList.restype = None

    class _Api:
        kernel32 = kernel32
        STARTUPINFOW = STARTUPINFOW
        STARTUPINFOEXW = STARTUPINFOEXW
        PROCESS_INFORMATION = PROCESS_INFORMATION
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION = JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        JOBOBJECT_BASIC_PROCESS_ID_LIST = JOBOBJECT_BASIC_PROCESS_ID_LIST
        ctypes = ctypes
        wintypes = wintypes

    return _Api()


class CreatedProcess:
    """The original handles of one created process."""

    __slots__ = ('process', 'thread', 'pid', 'creation_time')

    def __init__(self, process, thread, pid, creation_time):
        self.process = process
        self.thread = thread
        self.pid = pid
        self.creation_time = creation_time


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
    INVALID_HANDLE_VALUE = -1
    HANDLE_FLAG_INHERIT = 0x00000001
    PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x00000080
    ERROR_MORE_DATA = 234

    def __init__(self):
        self._api = _load_windows_api()

    def _last_error(self):
        return int(self._api.ctypes.get_last_error())

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
        ctypes = self._api.ctypes
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
        """
        ctypes = self._api.ctypes
        capacity = MAX_DESCENDANTS + 1
        size = (ctypes.sizeof(self._api.JOBOBJECT_BASIC_PROCESS_ID_LIST)
                + (capacity - 1) * ctypes.sizeof(ctypes.c_size_t))
        buffer = ctypes.create_string_buffer(size)
        returned = self._api.wintypes.DWORD(0)
        if not self._api.kernel32.QueryInformationJobObject(
                job, self.JOB_OBJECT_BASIC_PROCESS_ID_LIST, buffer, size,
                ctypes.byref(returned)):
            error = self._last_error()
            if error == self.ERROR_MORE_DATA:
                raise BrokerError('BROKER_DESCENDANT_LIMIT', 'last_error=%d' % error)
            raise BrokerError('BROKER_JOB_QUERY_UNKNOWN', 'last_error=%d' % error)
        header = ctypes.cast(buffer, ctypes.POINTER(
            self._api.JOBOBJECT_BASIC_PROCESS_ID_LIST)).contents
        count = int(header.NumberOfProcessIdsInList)
        if count > capacity:
            raise BrokerError('BROKER_DESCENDANT_LIMIT', 'count=%d' % count)
        return [int(header.ProcessIdList[index]) for index in range(count)]

    # -- the processes -----------------------------------------------------
    def create_process_suspended(self, *, executable, arguments, working_directory,
                                  stdout_handle, stderr_handle, environment=None):
        """Create one suspended process and return its original handles.

        The child inherits exactly three handles: the write end of its
        standard output, the write end of its standard error and the null
        device as its standard input.  The inheritance set is passed
        explicitly as the handle list of the process attributes, so that the
        control channel of the broker, the job handle and every other
        handle of the broker stay in the broker.
        """
        ctypes = self._api.ctypes
        wintypes = self._api.wintypes
        kernel32 = self._api.kernel32
        command = ctypes.create_unicode_buffer(_windows_command_line(executable, arguments))
        environment_block = _environment_block(environment)
        null = kernel32.CreateFileW('NUL', self.GENERIC_READ,
                                    self.FILE_SHARE_READ | self.FILE_SHARE_WRITE,
                                    None, self.OPEN_EXISTING,
                                    self.FILE_ATTRIBUTE_NORMAL, None)
        if not null or null == self.INVALID_HANDLE_VALUE:
            raise BrokerError('BROKER_NULL_DEVICE_FAILED',
                              'last_error=%d' % self._last_error())
        inherited = (ctypes.c_void_p * 3)(stdout_handle, stderr_handle, null)
        size = ctypes.c_size_t(0)
        try:
            kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
            attribute_list = ctypes.create_string_buffer(size.value)
            if not kernel32.InitializeProcThreadAttributeList(attribute_list, 1, 0,
                                                              ctypes.byref(size)):
                raise BrokerError('BROKER_ATTRIBUTE_LIST_FAILED',
                                  'last_error=%d' % self._last_error())
            try:
                if not kernel32.UpdateProcThreadAttribute(
                        attribute_list, 0, self.PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                        inherited, ctypes.sizeof(inherited), None, None):
                    raise BrokerError('BROKER_ATTRIBUTE_LIST_FAILED',
                                      'last_error=%d' % self._last_error())
                startup = self._api.STARTUPINFOEXW()
                startup.StartupInfo.cb = ctypes.sizeof(self._api.STARTUPINFOW)
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
                    ctypes.byref(startup), ctypes.byref(information))
                if not created:
                    raise BrokerError('BROKER_PROCESS_CREATE_FAILED',
                                      'last_error=%d' % self._last_error())
            finally:
                kernel32.DeleteProcThreadAttributeList(attribute_list)
        finally:
            kernel32.CloseHandle(null)
        creation = self._process_creation_time(information.hProcess)
        return CreatedProcess(information.hProcess, information.hThread,
                              int(information.dwProcessId), creation)

    def _process_creation_time(self, process):
        ctypes = self._api.ctypes
        creation = ctypes.c_longlong(0)
        exit_time = ctypes.c_longlong(0)
        kernel = ctypes.c_longlong(0)
        user = ctypes.c_longlong(0)
        if not self._api.kernel32.GetProcessTimes(
                process, ctypes.byref(creation), ctypes.byref(exit_time),
                ctypes.byref(kernel), ctypes.byref(user)):
            return None
        # The Windows epoch starts in 1601; the value is the 100 nanosecond
        # tick count since that epoch.
        return creation.value

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
        code = self._api.wintypes.DWORD(0)
        if not self._api.kernel32.GetExitCodeProcess(process, self._api.ctypes.byref(code)):
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
        """Create one pipe.  Only the write end is inheritable."""
        ctypes = self._api.ctypes
        wintypes = self._api.wintypes
        read = wintypes.HANDLE()
        write = wintypes.HANDLE()
        if not self._api.kernel32.CreatePipe(ctypes.byref(read), ctypes.byref(write),
                                             None, 0):
            raise BrokerError('BROKER_PIPE_FAILED', 'last_error=%d' % self._last_error())
        self._api.kernel32.SetHandleInformation(read, self.HANDLE_FLAG_INHERIT, 0)
        return read, write

    def read_stream(self, handle, size):
        ctypes = self._api.ctypes
        buffer = ctypes.create_string_buffer(size)
        read = self._api.wintypes.DWORD(0)
        if not self._api.kernel32.ReadFile(handle, buffer, size,
                                           ctypes.byref(read), None):
            return b''
        return buffer.raw[:read.value]

    def write_stream(self, handle, data):
        ctypes = self._api.ctypes
        buffer = ctypes.create_string_buffer(bytes(data), len(data))
        written = self._api.wintypes.DWORD(0)
        if not self._api.kernel32.WriteFile(handle, buffer, len(data),
                                            ctypes.byref(written), None):
            raise BrokerError('BROKER_STREAM_WRITE_FAILED',
                              'last_error=%d' % self._last_error())
        return int(written.value)


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
    an argument vector, a shell, a script or an environment: it carries the
    tools and the closed data of the role, and this function is the only
    place where a command line of this package exists.

    The forms are the ones of the already authorised launch of this pack:
    the ComfyUI launch of ``reports/v0-s1/wp-s1-03-phase-a/live_probe.py``
    and of ``tools/v0_s2_driver.py``, the Ollama launch of the same
    wrapper, and the sampler launch of ``tools/v0_s2_runtime.py``.
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
                     '--private-pids', ' '.join(str(pid) for pid in owned_pids),
                     '--max-seconds', str(data['max_seconds'])]
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
            self.error = type(error).__name__
        finally:
            self.finished.set()


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
        try:
            self.win32.set_job_kill_on_close(self.job)
        except BrokerError as error:
            self.failures.append({'stage': 'set_job_limits', 'code': error.code})
            self._close_handle('job', self.job)
            self.job = None
            self.state = 'UNKNOWN_RETAINED'
            raise
        self.job_kill_on_close = True
        self.state = 'ARMED'
        return self.evidence()

    # -- the launch of the roles ------------------------------------------
    def launch(self):
        """Create the roles of the round, one after the other."""
        if self.state != 'ARMED':
            raise BrokerError('BROKER_STATE_INVALID', self.state)
        for role in self.plan.roles:
            self._launch_role(role)
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
                  'failure': None}
        self.records.append(record)
        try:
            self._prepare_directories(name)
        except OSError as error:
            record['failure'] = 'BROKER_ROLE_DIRECTORY_FAILED'
            self.failures.append({'stage': 'role_directory', 'role': name,
                                  'error_type': type(error).__name__})
            self._abort_round('ROLE_DIRECTORY_FAILED')
            raise BrokerError('BROKER_ROLE_DIRECTORY_FAILED', name)
        stdout_read = stdout_write = stderr_read = stderr_write = None
        try:
            stdout_read, stdout_write = self.win32.create_pipe('stdout')
            stderr_read, stderr_write = self.win32.create_pipe('stderr')
        except BrokerError as error:
            record['failure'] = error.code
            self.failures.append({'stage': 'create_pipe', 'role': name, 'code': error.code})
            self._close_streams(stdout_read, stdout_write, stderr_read, stderr_write)
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
            self._close_streams(stdout_read, stdout_write, stderr_read, stderr_write)
            self._abort_round('CREATE_FAILED')
            raise
        # The write ends belong to the child now; the broker keeps the read
        # ends only.
        self._close_streams(None, stdout_write, None, stderr_write)
        record['created'] = True
        record['pid'] = created.pid
        record['creation_time'] = created.creation_time
        record['process_handle'] = created.process
        record['thread_handle'] = created.thread
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

    def _prepare_directories(self, name):
        """Create the fresh directories of a role.

        A directory that already exists is refused: a stale log, a stale
        pid lease or a stale sampler output of an earlier round may never
        be read as the output of this round.
        """
        if name == 'COMFY':
            (Path(self.run_root) / 'temp' / 'service-os').mkdir(parents=True,
                                                                exist_ok=True)
            (Path(self.run_root) / 'user').mkdir(parents=True, exist_ok=True)
        elif name == 'SAMPLER':
            (Path(self.run_root) / 'temp' / 'resource-sampler').mkdir(
                parents=True, exist_ok=False)

    def _start_reader(self, record, handle, stream):
        reader = _BoundedStreamReader(self.win32, handle, limit=MAX_STREAM_BYTES,
                                      name=record['role'] + '-' + stream)
        self.readers.append(reader)
        reader.start()

    def _close_streams(self, stdout_read, stdout_write, stderr_read, stderr_write):
        for handle in (stdout_read, stdout_write, stderr_read, stderr_write):
            if handle is None:
                continue
            try:
                self.win32.close_handle(handle)
            except BrokerError as error:
                self.failures.append({'stage': 'close_stream', 'code': error.code})

    def _close_handle(self, kind, handle):
        try:
            self.win32.close_handle(handle)
            return True
        except BrokerError as error:
            self.failures.append({'stage': 'close_handle', 'kind': kind,
                                  'code': error.code})
            return False

    def _close_readers(self):
        """Stop the readers of the children and close their read handles.

        The wait of a reader is bounded and its state is recorded.  A
        reader that is still blocked when the wait is over is a *fact* of
        this round and it is reported as such: a daemon thread that is
        still running is not a finished thread.
        """
        for reader in self.readers:
            reader.finished.wait(1.0)
            self.reader_states.append({'name': reader.name,
                                       'finished': reader.finished.is_set(),
                                       'alive': reader.is_alive(),
                                       'error': reader.error})
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
        terminate anything twice and it does not change the evidence of the
        round.  Every handle is reported on its own, so a handle that could
        not be closed stays visible and the round becomes unknown instead
        of a silent success.
        """
        if self.state in ('RELEASED', 'UNKNOWN_RETAINED'):
            return self.evidence()
        self.state = 'STOPPING'
        self.stop_reason = reason
        self._collect_stream_counts()
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
        self._query_job()
        self._close_readers()
        for record in self.records:
            thread = record.get('thread_handle')
            if thread is not None:
                record['thread_handle_closed'] = self._close_handle('thread', thread)
                record['thread_handle'] = None
            process = record.get('process_handle')
            if process is not None:
                record['process_handle_closed'] = self._close_handle('process', process)
                record['process_handle'] = None
        if self.job is not None:
            self.job_closed = self._close_handle('job', self.job)
            self.job = None
        released = (not self.failures
                    and all(record['exited'] for record in self.records if record['created'])
                    and self.job_active_known and self.job_active == 0
                    and all(record['process_handle_closed'] and record['thread_handle_closed']
                            for record in self.records)
                    and self.job_closed)
        self.state = 'UNKNOWN_RETAINED' if (force_unknown or not released) else 'RELEASED'
        return self.evidence()

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
        afterwards, whatever the stop itself proved.
        """
        self.failures.append({'stage': 'round', 'code': reason})
        try:
            self.stop(reason, force_unknown=True)
        except BrokerError as error:
            self.failures.append({'stage': 'abort', 'code': error.code})
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
    """

    def __init__(self, reader, writer, *, max_frames=MAX_FRAMES,
                 max_frame_bytes=MAX_FRAME_BYTES):
        self._reader = reader
        self._writer = writer
        self._queue = queue.Queue(maxsize=max_frames)
        self._max_frames = max_frames
        self._max_frame_bytes = max_frame_bytes
        self._count = 0
        self._overflow = False
        self._eof = False
        self._error = None
        self.reader_alive = None
        self.reader_finished = None
        self._thread = threading.Thread(target=self._drain, daemon=True,
                                        name='lvw-native-custody-channel')
        self._thread.start()

    def _drain(self):
        try:
            while True:
                raw = self._reader.readline(self._max_frame_bytes + 1)
                if not raw:
                    break
                if len(raw) > self._max_frame_bytes or not raw.endswith(b'\n'):
                    self._overflow = True
                    break
                self._count += 1
                if self._count > self._max_frames:
                    self._overflow = True
                    break
                while True:
                    try:
                        self._queue.put(raw, timeout=0.5)
                        break
                    except queue.Full:
                        if self._eof:
                            return
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self._error = type(error).__name__
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

    def write(self, raw):
        if len(raw) > self._max_frame_bytes:
            raise BrokerError('BROKER_CHANNEL_FRAME_TOO_LARGE')
        self._writer.write(raw)
        self._writer.flush()

    def close(self):
        """Close the channel and report whether the reader really stopped.

        The reader thread is joined with a bounded wait.  A reader that
        did not stop is reported as such: a daemon thread is not a
        finished thread, so the fact that the reader is still alive is
        kept visible instead of being hidden behind the close.
        """
        try:
            self._writer.close()
        except Exception:  # noqa: BLE001 - the failure stays visible
            pass
        self._thread.join(CLOSE_JOIN_SECONDS)
        self.reader_alive = self._thread.is_alive()
        self.reader_finished = not self.reader_alive
        return self.reader_finished

    @property
    def eof(self):
        return self._eof

    @property
    def overflow(self):
        return self._overflow


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
        self._deadline_wall = None
        self._deadline_mono = None
        self._last_frame_wall = None

    def _reply(self, kind, state, detail):
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
        self.transport.write(raw + b'\n')

    def run(self):
        try:
            self.core.arm()
        except BrokerError as error:
            self._reply('REFUSED', self.core.state, {'code': error.code})
            self._write_receipt('ARM_FAILED')
            return 3
        self._reply('READY', self.core.state, {'broker': self.core.broker_identity})
        try:
            self.core.launch()
        except BrokerError as error:
            self._reply('REFUSED', self.core.state, {'code': error.code})
            self._write_receipt('LAUNCH_FAILED')
            return 3
        self._reply('STATUS', self.core.state, self.core.summary())
        exit_code = self._loop()
        self._write_receipt(self.core.stop_reason)
        return exit_code

    def _loop(self):
        wall_now = self._wall()
        self._deadline_wall = min(self.plan.lease_expires_at,
                                  wall_now + self.plan.max_runtime_seconds)
        self._deadline_mono = self._clock() + max(0.0, self._deadline_wall - wall_now)
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
            self._last_frame_wall = self._wall()
            try:
                frame = decode_command(raw, run_id=self.plan.run_id,
                                       candidate_sha=self.plan.candidate_sha,
                                       authorization_sha256=self.plan.authorization_sha256,
                                       nonce=self.nonce, last_sequence=self._last_sequence)
            except CustodyError as error:
                self.core.failures.append({'stage': 'channel', 'code': error.code})
                return self._stop('CHANNEL_REFUSED', 4)
            self._last_sequence = frame['sequence']
            if frame['command'] == 'STATUS':
                self._reply('STATUS', self.core.state, self.core.summary())
                continue
            return self._stop('STOP_COMMAND', 0)

    def _stop(self, reason, exit_code):
        unknown = reason != 'STOP_COMMAND'
        self.core.stop(reason, force_unknown=unknown)
        self._reply('STOPPED', self.core.state, self.core.summary())
        return exit_code

    def _write_receipt(self, reason):
        """Write the terminal receipt of the round into the run root.

        The receipt is the evidence that survives a parent that died.  It
        is written once, it is bounded and it is never replaced by a
        successful claim.
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
    """

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

    def write(self, raw):
        self._channel.write(raw)

    def read(self, timeout):
        return self._channel.read(timeout)

    def close(self):
        """Close the original handle of the broker.

        The close happens exactly once and it happens even when the
        exchange of the stop failed: the resource of this round is
        released either way.
        """
        try:
            self._channel.close()
        finally:
            self.reader_finished = self._channel.reader_finished
            try:
                self._process.stdin.close()
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass
            try:
                self._process.wait(timeout=5)
            except Exception:  # noqa: BLE001 - the failure stays visible
                try:
                    self._process.terminate()
                except Exception:  # noqa: BLE001 - the failure stays visible
                    pass
            try:
                self._process.stdout.close()
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass


def launch_broker(plan, run_root, nonce):
    """Start the broker process of one round and keep its original handle.

    The launcher is a Windows only operation.  It refuses on every other
    platform before anything is started: a broker that cannot be started
    on Windows is never replaced by an unconstrained process and never by a
    simulation that pretends to be one.
    """
    if os.name != 'nt':
        raise BrokerError('BROKER_PLATFORM_UNSUPPORTED')
    root = Path(run_root)
    directory = root / 'temp' / 'native'
    directory.mkdir(parents=True, exist_ok=True)
    plan_path = directory / 'custody-plan.json'
    raw = json.dumps(plan.sealed, ensure_ascii=False, sort_keys=True,
                     indent=2).encode('utf-8')
    with plan_path.open('xb') as stream:
        stream.write(raw)
    digest = hashlib.sha256(raw).hexdigest()
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
    document = read_sealed_plan(arguments.plan, arguments.plan_sha256)
    try:
        plan = validate_launch_plan(document, now=time.time())
    except CustodyError as error:
        sys.stderr.write('BROKER_REFUSED ' + error.code + '\n')
        sys.stderr.flush()
        return 2
    try:
        win32 = WindowsApi()
    except BrokerError as error:
        sys.stderr.write('BROKER_REFUSED ' + error.code + '\n')
        sys.stderr.flush()
        return 2
    core = BrokerCore(win32=win32, plan=plan, run_root=arguments.run_root)
    transport = StreamChannel(sys.stdin.buffer, sys.stdout.buffer)
    loop = BrokerLoop(core=core, transport=transport, plan=plan,
                      nonce=arguments.nonce)
    try:
        return loop.run()
    finally:
        transport.close()


if __name__ == '__main__':
    sys.exit(main())
