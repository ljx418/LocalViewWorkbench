"""Pytest configuration for the reviewer-owned process-correction tests.

The tests import the corrected helper module directly so that the source
adapter can be replaced by a spy.  No test in this directory touches real
media: every fixture is created inside the pytest basetemp, which the runner
places inside an owned TemporaryDirectory parent.
"""
from __future__ import annotations

import sys
from pathlib import Path

HELPER_DIR = Path(__file__).resolve().parents[1] / "helper"
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))
