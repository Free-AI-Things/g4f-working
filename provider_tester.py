#!/usr/bin/env python3
"""
provider_tester.py — entry point for the g4f-working daily test pipeline.

This file is intentionally tiny: all real logic lives in the
:mod:`g4f_tester` package. Keeping the entry point thin means the GitHub
Actions workflow (which calls ``python provider_tester.py``) needs no
changes, while users get a properly modular codebase to extend.

Usage
-----
::

    python provider_tester.py                       # all defaults
    python provider_tester.py --port 9000           # custom port
    python provider_tester.py --no-server --base-url http://localhost:8081
    python provider_tester.py --timeout 180 --batch-size 50

Environment variables (override defaults; CLI flags win if both set)
-------------------------------------------------------------------
``G4F_BASE_URL``, ``G4F_API_KEY``, ``G4F_PORT``,
``G4F_MAX_CONCURRENT``, ``G4F_TIMEOUT``, ``G4F_BATCH_SIZE``,
``G4F_TEST_MESSAGE``, ``G4F_IMAGE_PROMPT``, ``G4F_VIDEO_PROMPT``,
``G4F_AUDIO_PROMPT``, ``G4F_NO_SERVER``

Backwards compatibility
-----------------------
Code that did ``from provider_tester import ProviderModelFetcherAndTester``
keeps working — the class is re-exported below.
"""

from __future__ import annotations

# Re-export the legacy class so existing user scripts keep working.
from g4f_tester import (
    ProviderModelFetcherAndTester,
    cleanup_browsers,
    main,
    run,
    start_g4f_api_server,
)

# Also re-export the dataclasses since the legacy file exposed them at
# module level (some users may have imported them).
from g4f_tester.models import TestResult, TestResultWithTypes

__all__ = [
    "ProviderModelFetcherAndTester",
    "TestResult",
    "TestResultWithTypes",
    "start_g4f_api_server",
    "cleanup_browsers",
    "main",
    "run",
]


if __name__ == "__main__":
    main()
