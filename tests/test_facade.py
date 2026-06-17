"""Tests for the backwards-compatible facade class."""

import asyncio, os, sys, tempfile, shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from provider_tester import (
    ProviderModelFetcherAndTester,
    TestResult,
    TestResultWithTypes,
    cleanup_browsers,
    start_g4f_api_server,
)


def test_facade_constructs_with_legacy_args():
    t = ProviderModelFetcherAndTester(
        "http://localhost:8081", "1234",
        max_concurrent=50, timeout=120,
    )
    assert t.base_url == "http://localhost:8081"
    assert t.api_key == "1234"
    assert t.max_concurrent == 50
    assert t.timeout == 120


def test_facade_creates_default_dirs():
    tmp = tempfile.mkdtemp()
    try:
        cwd = os.getcwd()
        os.chdir(tmp)
        t = ProviderModelFetcherAndTester("http://x", "k")
        for d in ("provider", "working", "output"):
            assert os.path.isdir(d)
        os.chdir(cwd)
    finally:
        os.chdir(sys.path[0] if not os.getcwd().startswith(tmp) else os.path.expanduser("~"))
        shutil.rmtree(tmp)


def test_facade_exposes_legacy_methods():
    t = ProviderModelFetcherAndTester("http://x", "k")
    legacy = [
        "fetch_providers_and_models",
        "fetch_providers_and_models_with_types",
        "save_to_files",
        "create_test_format",
        "save_provider_models_with_types",
        "determine_response_types",
        "extract_test_data_from_fetched",
        "test_all_models",
        "test_all_models_batched",
        "save_test_results",
        "save_simple_working_results",
        "get_model_capabilities",
        "test_provider_model_combination",
        "test_single_model",
        "test_image_generation",
        "test_video_generation",
        "test_audio_generation",
    ]
    for name in legacy:
        assert hasattr(t, name), f"Missing legacy method: {name}"


def test_facade_determine_response_types_is_static():
    info = {"id": "dall-e-3", "image": True, "video": False, "audio": False}
    # Both as instance call and static call should work.
    t = ProviderModelFetcherAndTester("http://x", "k")
    assert "image" in t.determine_response_types(info)
    assert "image" in ProviderModelFetcherAndTester.determine_response_types(info)


def test_facade_save_test_results_writes_files():
    tmp = tempfile.mkdtemp()
    try:
        t = ProviderModelFetcherAndTester(
            "http://x", "k",
            working_dir=tmp, output_dir=tmp, provider_dir=tmp,
        )
        results = [
            TestResultWithTypes("P", "m1", True, 1.0, media_type="text"),
            TestResultWithTypes("P", "m2", False, 0.5, error="boom"),
        ]
        summary = t.save_test_results(results)
        assert summary["total_tested"] == 2
        assert summary["working_count"] == 1
        assert os.path.exists(os.path.join(tmp, "test_results.json"))
        assert os.path.exists(os.path.join(tmp, "test_results.txt"))
        assert os.path.exists(os.path.join(tmp, "working_results.txt"))
        assert os.path.exists(os.path.join(tmp, "models.txt"))
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  ... {name}", end=" ")
            fn()
            print("OK")
    print("All facade tests passed.")
