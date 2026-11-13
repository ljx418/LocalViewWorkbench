"""The pytest entry of the S3-P4 originals correction 05.

The entry is a thin shim: the guard has installed its audit hook before
this file is run, so the pytest startup, every plugin and the import of
the candidate already run inside the guard.
"""
import sys

import pytest

if __name__ == '__main__':
    raise SystemExit(pytest.main(sys.argv[1:]))
