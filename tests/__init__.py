"""Test suite for the g4f_tester package.

Run with::

    python -m pytest tests/ -v
    # or, without pytest:
    python tests/run_tests.py
"""

import os
import sys

# Make the package importable when running tests directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
