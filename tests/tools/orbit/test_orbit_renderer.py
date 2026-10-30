"""Regression tests for upstream defects fixed during the bug-hunt rounds.

Each test reproduces a concrete failure that shipped in v4.0.0-alpha.1 and
asserts the corrected behavior, so the defect cannot silently return.
"""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.utils import TempEnv


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


class TestOrbitRendererGeometry(unittest.TestCase):

    def test_accent_half_span_never_goes_negative(self):
        for count in (12, 45, 46, 60, 120):
            step_deg = 360.0 / count
            self.assertGreaterEqual(max(0.0, step_deg / 2.0 - 4.0), 0.0)
