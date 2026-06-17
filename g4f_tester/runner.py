"""High-level orchestration: wire fetcher → tester → reporter together.

Provides three things:

* :func:`run` — async entry point that takes a :class:`Config` and runs
  the full pipeline. Reusable from notebooks, tests, or other modules.

* :func:`main` — sync entry point used by ``provider_tester.py``. Parses
  CLI args, builds a :class:`Config`, and calls :func:`run`.

* :class:`ProviderModelFetcherAndTester` — a thin facade over the modular
  pipeline that exposes the *exact same* public surface as the legacy
  single-file class. Existing user scripts that did ``from provider_tester
  import ProviderModelFetcherAndTester`` keep working unchanged.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .config import (
    Config,
    DEFAULT_API_KEY,
    DEFAULT_BASE_URL,
    DEFAULT_MAX_CONCURRENT,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    parse_args,
)
from .fetcher import ProviderModelFetcher
from .reporter import TestResultsReporter
from .server import cleanup_browsers, start_g4f_api_server, start_server_from_config
from .tester import ProviderModelTester

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async pipeline
# ---------------------------------------------------------------------------
async def run(cfg: Config) -> Dict[str, Any]:
    """Execute the full fetch → test → report pipeline.

    Returns the summary dict so callers can introspect results.
    """
    cfg.ensure_dirs()

    if cfg.start_server:
        start_server_from_config(cfg)
    else:
        log.info("Skipping embedded server (start_server=False). "
                 "Make sure %s is reachable.", cfg.base_url)

    print("=== STEP 1: Fetching providers and models ===")
    fetcher = ProviderModelFetcher(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        provider_dir=cfg.provider_dir,
    )
    provider_models = fetcher.fetch(with_types=False)
    if not provider_models:
        print("No data retrieved. Exiting.")
        return {"total_providers": 0, "total_models": 0, "summary": {}}

    fetcher.save_to_files(provider_models)
    fetcher.create_test_format(provider_models)

    total_models = sum(d.get("model_count", 0) for d in provider_models.values())
    print(f"\nFetch Summary:")
    print(f"Total providers: {len(provider_models)}")
    print(f"Total models: {total_models}")

    test_data = fetcher.extract_test_data(provider_models)
    if cfg.skip_providers:
        test_data = [(p, m) for (p, m) in test_data if p not in set(cfg.skip_providers)]
    if not test_data:
        print("No test data available. Exiting.")
        return {"total_providers": len(provider_models), "total_models": 0, "summary": {}}

    print("\n=== STEP 2: Testing all capabilities for provider-model combinations ===")
    print(f"Testing {len(test_data)} provider-model combinations for all "
          f"capabilities (text, image, audio, video)")

    tester = ProviderModelTester(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        max_concurrent=cfg.max_concurrent,
        timeout=cfg.timeout,
        output_dir=cfg.output_dir,
        test_messages=[{"role": "user", "content": cfg.test_message}],
        image_prompt=cfg.image_prompt,
        video_prompt=cfg.video_prompt,
        audio_prompt=cfg.audio_prompt,
    )

    start = time.time()
    results = await tester.test_all_models_batched(
        test_data,
        batch_size=cfg.batch_size,
        cleanup_fn=cleanup_browsers,
        cleanup_every_n_batches=cfg.cleanup_browser_every_n_batches,
        inter_batch_sleep=cfg.inter_batch_sleep,
    )
    total_time = time.time() - start

    reporter = TestResultsReporter(working_dir=cfg.working_dir)
    summary = reporter.save_test_results(results)

    print(f"\nTesting completed in {total_time:.2f} seconds")
    print(f"Results: {summary['working_count']}/{summary['total_tested']} working "
          f"({summary['success_rate']:.2f}%)")
    print(f"Response Type Breakdown: {summary['response_type_breakdown']}")
    return {
        "total_providers": len(provider_models),
        "total_models": total_models,
        "summary": summary,
        "results": results,
        "elapsed_seconds": total_time,
    }


def main(argv: Optional[List[str]] = None) -> None:
    """Sync entry point — parse args, configure logging, run."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg = Config.from_args(args)
    asyncio.run(run(cfg))


# ---------------------------------------------------------------------------
# Backwards-compatible facade
# ---------------------------------------------------------------------------
class ProviderModelFetcherAndTester:
    """Facade preserving the legacy single-class API.

    Every method delegates to the appropriate modular component, so user
    code that does::

        from provider_tester import ProviderModelFetcherAndTester
        t = ProviderModelFetcherAndTester(BASE_URL, API_KEY, max_concurrent=50, timeout=120)
        data = t.fetch_providers_and_models()
        t.save_to_files(data)
        ...

    keeps working byte-for-byte.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        timeout: int = DEFAULT_TIMEOUT,
        *,
        provider_dir: str = "provider",
        working_dir: str = "working",
        output_dir: str = "output",
        test_messages: Optional[List[dict]] = None,
        image_prompt: str = "a simple test image of a red apple",
        video_prompt: str = "a simple test video of a cat walking",
        audio_prompt: str = "Hello, this is a test audio generation",
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.provider_dir = provider_dir
        self.working_dir = working_dir
        self.output_dir = output_dir
        self.test_messages = test_messages or [
            {"role": "user",
             "content": "Hello, are you working? Reply with 'Yes' if you can respond."}
        ]
        self.image_prompt = image_prompt
        self.video_prompt = video_prompt
        self.audio_prompt = audio_prompt

        for d in (provider_dir, working_dir, output_dir):
            os.makedirs(d, exist_ok=True)

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Compose the modular pieces.
        self._fetcher = ProviderModelFetcher(base_url, api_key, provider_dir)
        self._tester = ProviderModelTester(
            base_url=base_url,
            api_key=api_key,
            max_concurrent=max_concurrent,
            timeout=timeout,
            output_dir=output_dir,
            test_messages=self.test_messages,
            image_prompt=image_prompt,
            video_prompt=video_prompt,
            audio_prompt=audio_prompt,
        )
        self._reporter = TestResultsReporter(working_dir)

    # ----- direct delegation -----------------------------------------
    def fetch_providers_and_models(self) -> Dict[str, Any]:
        return self._fetcher.fetch(with_types=False)

    def fetch_providers_and_models_with_types(self) -> Dict[str, Any]:
        return self._fetcher.fetch(with_types=True)

    def save_to_files(self, data: Dict[str, Any], base_filename: str = "providers_models") -> None:
        self._fetcher.save_to_files(data, base_filename)

    def create_test_format(self, data: Dict[str, Any], filename: str = "models_for_testing.txt") -> None:
        self._fetcher.create_test_format(data, filename)

    def save_provider_models_with_types(self, data: Dict[str, Any]) -> None:
        self._fetcher.save_with_types(data)

    @staticmethod
    def determine_response_types(model_info: dict) -> List[str]:
        return ProviderModelFetcher.determine_response_types(model_info)

    @staticmethod
    def extract_test_data_from_fetched(data: Dict[str, Any]) -> List[Tuple[str, str]]:
        return ProviderModelFetcher.extract_test_data(data)

    async def test_all_models(self, test_data: List[Tuple[str, str]]):
        return await self._tester.test_all_models(test_data)

    async def test_all_models_batched(
        self, test_data: List[Tuple[str, str]], batch_size: int = 20,
    ):
        return await self._tester.test_all_models_batched(
            test_data,
            batch_size=batch_size,
            cleanup_fn=cleanup_browsers,
        )

    def save_test_results(self, results, base_filename: str = "test_results") -> dict:
        return self._reporter.save_test_results(results, base_filename)

    def save_simple_working_results(self, results) -> None:
        self._reporter.save_simple_working_results(results)

    # ----- direct passthroughs for the methods callers may rely on ---
    async def get_model_capabilities(self, session, provider: str, model: str) -> dict:
        return await self._tester.get_model_capabilities(session, provider, model)

    async def test_provider_model_combination(self, session, provider: str, model: str):
        return await self._tester.test_provider_model_combination(session, provider, model)

    async def test_single_model(self, session, provider, model, response_types):
        return await self._tester.test_single_model(session, provider, model, response_types)

    async def test_image_generation(self, session, provider, model, response_types):
        return await self._tester.test_image_generation(session, provider, model, response_types)

    async def test_video_generation(self, session, provider, model, response_types):
        return await self._tester.test_video_generation(session, provider, model, response_types)

    async def test_audio_generation(self, session, provider, model, response_types):
        return await self._tester.test_audio_generation(session, provider, model, response_types)


# ---------------------------------------------------------------------------
# Re-export for the legacy entry point in provider_tester.py
# ---------------------------------------------------------------------------
__all__ = [
    "Config",
    "ProviderModelFetcher",
    "ProviderModelTester",
    "TestResultsReporter",
    "ProviderModelFetcherAndTester",
    "start_g4f_api_server",
    "cleanup_browsers",
    "main",
    "run",
    "DEFAULT_BASE_URL",
    "DEFAULT_API_KEY",
    "DEFAULT_PORT",
]
