"""End-to-end smoke test: actually start the g4f API server and run the
pipeline against a tiny slice of real providers.

This is NOT part of the regular unit-test suite — it requires network
access and can take a couple of minutes. Run manually::

    python tests/smoke_test_real.py
"""

import asyncio, os, sys, time, shutil, tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester import Config, run, start_g4f_api_server, cleanup_browsers
from g4f_tester.fetcher import ProviderModelFetcher
from g4f_tester.tester import ProviderModelTester
from g4f_tester.reporter import TestResultsReporter


def main():
    tmp = tempfile.mkdtemp(prefix="g4f_smoke_")
    print(f"Smoke test workspace: {tmp}")

    cfg = Config(
        base_url="http://localhost:8081",
        api_key="1234",
        port=8081,
        max_concurrent=5,
        timeout=60,
        batch_size=5,
        provider_dir=f"{tmp}/provider",
        working_dir=f"{tmp}/working",
        output_dir=f"{tmp}/output",
        generated_media_dir=f"{tmp}/generated_media",
    )
    cfg.ensure_dirs()

    print("Starting g4f API server...")
    thread = start_g4f_api_server(port=cfg.port, api_key=cfg.api_key, poll_timeout=60)
    if thread is None:
        print("FAIL: server didn't start")
        shutil.rmtree(tmp)
        sys.exit(1)

    print("\n--- STEP 1: Fetch providers ---")
    fetcher = ProviderModelFetcher(cfg.base_url, cfg.api_key, cfg.provider_dir)
    data = fetcher.fetch(with_types=False, sleep_between=0)
    if not data:
        print("FAIL: no providers fetched")
        shutil.rmtree(tmp)
        sys.exit(1)

    print(f"Got {len(data)} providers")
    fetcher.save_to_files(data)
    fetcher.create_test_format(data)

    pairs = fetcher.extract_test_data(data)
    print(f"Total pairs: {len(pairs)}")
    # Test only the first 3 pairs to keep the smoke test fast.
    pairs = pairs[:3]
    print(f"Will test {len(pairs)} pairs: {pairs}")

    print("\n--- STEP 2: Test ---")
    tester = ProviderModelTester(
        base_url=cfg.base_url, api_key=cfg.api_key,
        max_concurrent=cfg.max_concurrent, timeout=cfg.timeout,
        output_dir=cfg.output_dir,
    )
    results = asyncio.run(tester.test_all_models_batched(pairs, batch_size=3,
                                                          cleanup_fn=cleanup_browsers))

    print("\n--- STEP 3: Report ---")
    reporter = TestResultsReporter(working_dir=cfg.working_dir)
    summary = reporter.save_test_results(results)
    print(f"Summary: {summary}")

    print("\nFiles in working dir:")
    for f in sorted(os.listdir(cfg.working_dir)):
        size = os.path.getsize(os.path.join(cfg.working_dir, f))
        print(f"  {f}  ({size} bytes)")

    print("\nFiles in output dir:")
    if os.path.isdir(cfg.output_dir):
        for f in sorted(os.listdir(cfg.output_dir))[:10]:
            size = os.path.getsize(os.path.join(cfg.output_dir, f))
            print(f"  {f}  ({size} bytes)")

    print("\nFiles in provider dir:")
    for f in sorted(os.listdir(cfg.provider_dir)):
        size = os.path.getsize(os.path.join(cfg.provider_dir, f))
        print(f"  {f}  ({size} bytes)")

    print("\nSMOKE TEST COMPLETE")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
