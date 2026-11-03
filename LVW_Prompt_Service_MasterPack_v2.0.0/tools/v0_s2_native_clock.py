"""Native Python clock only; no environment, process-table or GPU queries."""
import json
import sys
import time


def snapshot():
    if sys.platform!='win32':raise ValueError('NATIVE_WINDOWS_CLOCK_REQUIRED')
    return {'clock_basis':'native_python_monotonic','platform':sys.platform,
            'monotonic_seconds':time.monotonic(),'wall_seconds':time.time()}


if __name__=='__main__':
    try:print(json.dumps(snapshot()))
    except Exception as error:
        print(json.dumps({'error_type':type(error).__name__}));raise SystemExit(2)
