"""Bounded direct-child runner for the trusted local decoder adapter."""
from dataclasses import dataclass
import subprocess
import threading
import time

from .core import BridgeError


@dataclass(frozen=True)
class ProcessResult:
    stdout: bytes
    stderr: bytes
    returncode: int


def run_bounded(argv, *, timeout_seconds, output_limit=1024 * 1024, cancel=None):
    """Run trusted argv without shell; cap total captured stdout plus stderr.

    This is an internal adapter utility, not an API accepting arbitrary commands.
    Only the process handle created here may be terminated. Decoder executables
    must not spawn detached children; target-platform ownership is checked live.
    """
    if (not isinstance(argv, (list, tuple)) or not argv
            or any(not isinstance(a, str) or "\x00" in a for a in argv)):
        raise ValueError("invalid decoder argument vector")
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not 0 < timeout_seconds <= 120):
        raise ValueError("invalid decoder timeout")
    if (isinstance(output_limit, bool) or not isinstance(output_limit, int)
            or not 0 < output_limit <= 16 * 1024 * 1024):
        raise ValueError("invalid decoder output cap")
    if cancel is not None and cancel.is_set():
        raise BridgeError("JOB_CANCELLED", "video preparation cancelled", subcode="VIDEO_PROCESS_CANCELLED")
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=False)
    except OSError as exc:
        raise BridgeError("MEDIA_INVALID", "decoder could not start", subcode="VIDEO_PROCESS_START_FAILED") from exc
    chunks = [bytearray(), bytearray()]
    lock = threading.Lock()
    exceeded = threading.Event()
    read_failed = threading.Event()
    total = 0

    def drain(stream, index):
        nonlocal total
        try:
            while True:
                data = stream.read1(4096)
                if not data:
                    return
                with lock:
                    remaining = max(0, output_limit - total)
                    chunks[index].extend(data[:remaining])
                    total += min(len(data), remaining)
                    if len(data) > remaining:
                        exceeded.set()
        except (OSError, ValueError):
            read_failed.set()

    readers = [threading.Thread(target=drain, args=(stream, i), daemon=True)
               for i, stream in enumerate((process.stdout, process.stderr))]
    deadline = time.monotonic() + timeout_seconds
    reason = None
    try:
        for thread in readers:
            thread.start()
        while True:
            if cancel is not None and cancel.is_set():
                reason = "cancel"
            elif exceeded.is_set():
                reason = "output"
            elif time.monotonic() >= deadline:
                reason = "timeout"
            if reason or process.poll() is not None:
                break
            time.sleep(.01)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        else:
            process.wait()
        for thread in readers:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in readers):
            raise BridgeError("RESOURCE_RELEASE_PENDING", "decoder pipe cleanup incomplete",
                              subcode="VIDEO_PROCESS_PIPE_PENDING")
        process.stdout.close()
        process.stderr.close()
    if reason == "cancel":
        raise BridgeError("JOB_CANCELLED", "video preparation cancelled", subcode="VIDEO_PROCESS_CANCELLED")
    # A short-lived child can exit before the monitor observes the reader flag.
    if reason == "output" or exceeded.is_set():
        raise BridgeError("MEDIA_LIMIT_EXCEEDED", "decoder output cap exceeded", subcode="VIDEO_PROCESS_OUTPUT_LIMIT")
    if reason == "timeout":
        raise BridgeError("MODEL_TIMEOUT", "video preparation timed out", subcode="VIDEO_PROCESS_TIMEOUT")
    if read_failed.is_set() or process.returncode != 0:
        raise BridgeError("MEDIA_INVALID", "decoder failed", subcode="VIDEO_PROCESS_FAILED")
    return ProcessResult(bytes(chunks[0]), bytes(chunks[1]), process.returncode)
