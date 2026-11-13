"""The pytest entry of the guarded runner of the originals correction 04.

The guard is installed before this module is loaded, so the guard is
already active when pytest imports the candidate and the test modules.
"""
import sys

import pytest

sys.exit(pytest.main(sys.argv[1:]))
