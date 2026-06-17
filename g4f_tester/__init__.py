"""
g4f_tester — a modular toolkit for testing which gpt4free providers/models
work *without* any API key, token, or cookies.

Public API
----------
``ProviderModelFetcherAndTester``
    High-level orchestrator that mirrors the legacy single-file class so
    existing scripts keep working unchanged.

``TestResultWithTypes``
    Dataclass returned by every test routine.

``run()``, ``main()``
    Convenience entry-points used by ``provider_tester.py``.
"""

from .models import TestResult, TestResultWithTypes
from .config import Config
from .server import cleanup_browsers, install_signal_hooks, start_g4f_api_server
from .fetcher import ProviderModelFetcher
from .tester import ProviderModelTester
from .reporter import TestResultsReporter
from .media_saver import MediaSaver
from .runner import ProviderModelFetcherAndTester, main, run

__all__ = [
    "TestResult",
    "TestResultWithTypes",
    "Config",
    "ProviderModelFetcher",
    "ProviderModelTester",
    "TestResultsReporter",
    "MediaSaver",
    "ProviderModelFetcherAndTester",
    "start_g4f_api_server",
    "cleanup_browsers",
    "install_signal_hooks",
    "main",
    "run",
]

__version__ = "2.0.0"
