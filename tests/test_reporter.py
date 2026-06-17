"""Tests for g4f_tester.reporter."""

import json, os, sys, tempfile, shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester.models import TestResultWithTypes
from g4f_tester.reporter import TestResultsReporter


def _make_results():
    return [
        TestResultWithTypes("ProvA", "gpt-4", True, 1.2,
                            response_content="hello", media_type="text",
                            response_types=["text"]),
        TestResultWithTypes("ProvA", "dall-e-3", True, 2.5,
                            response_content="img url",
                            media_type="image", response_types=["text", "image"]),
        TestResultWithTypes("ProvB", "tts-1", True, 0.8,
                            response_content="audio ok",
                            media_type="audio", response_types=["text", "audio"]),
        TestResultWithTypes("ProvB", "broken", False, 0.1,
                            error="HTTP 500", response_types=["text"]),
    ]


def test_save_test_results_writes_all_files():
    tmp = tempfile.mkdtemp()
    try:
        r = TestResultsReporter(working_dir=tmp)
        summary = r.save_test_results(_make_results())
        for name in ("test_results.json", "test_results.txt",
                     "working_results.txt", "models.txt"):
            assert os.path.exists(os.path.join(tmp, name)), name
        assert summary["total_tested"] == 4
        assert summary["working_count"] == 3
        assert summary["non_working_count"] == 1
        assert 0 < summary["success_rate"] <= 100
        assert summary["response_type_breakdown"]["text"] == 1
        assert summary["response_type_breakdown"]["image"] == 1
        assert summary["response_type_breakdown"]["audio"] == 1
    finally:
        shutil.rmtree(tmp)


def test_test_results_json_shape():
    tmp = tempfile.mkdtemp()
    try:
        r = TestResultsReporter(working_dir=tmp)
        r.save_test_results(_make_results())
        with open(os.path.join(tmp, "test_results.json")) as f:
            data = json.load(f)
        assert "summary" in data
        assert "working_models" in data
        assert "non_working_models" in data
        assert len(data["working_models"]) == 3
        assert len(data["non_working_models"]) == 1
        # Each working entry should have the expected fields.
        w = data["working_models"][0]
        for k in ("provider", "model", "response_time",
                  "response_preview", "media_type", "response_types"):
            assert k in w
    finally:
        shutil.rmtree(tmp)


def test_working_results_txt_format():
    tmp = tempfile.mkdtemp()
    try:
        r = TestResultsReporter(working_dir=tmp)
        r.save_test_results(_make_results())
        with open(os.path.join(tmp, "working_results.txt")) as f:
            txt = f.read()
        assert "ProvA|gpt-4|text" in txt
        assert "ProvA|dall-e-3|image" in txt
        assert "ProvB|tts-1|audio" in txt
        # Non-working entries should NOT appear in working_results.txt.
        assert "broken" not in txt
    finally:
        shutil.rmtree(tmp)


def test_models_txt_deduplicates():
    tmp = tempfile.mkdtemp()
    try:
        r = TestResultsReporter(working_dir=tmp)
        results = [
            TestResultWithTypes("P", "gpt-4", True, 1.0, media_type="text"),
            TestResultWithTypes("P2", "gpt-4", True, 1.0, media_type="text"),
            TestResultWithTypes("P3", "gpt-4", True, 1.0, media_type="text"),
        ]
        r.save_test_results(results)
        with open(os.path.join(tmp, "models.txt")) as f:
            lines = [ln for ln in f.read().splitlines() if ln]
        # Should appear exactly once even though 3 providers serve it.
        assert lines.count("gpt-4 (text)") == 1
    finally:
        shutil.rmtree(tmp)


def test_empty_results_do_not_crash():
    tmp = tempfile.mkdtemp()
    try:
        r = TestResultsReporter(working_dir=tmp)
        summary = r.save_test_results([])
        assert summary["total_tested"] == 0
        assert summary["working_count"] == 0
        assert summary["success_rate"] == 0
        assert summary["average_response_time"] == 0
    finally:
        shutil.rmtree(tmp)


def test_test_results_txt_contains_sections():
    tmp = tempfile.mkdtemp()
    try:
        r = TestResultsReporter(working_dir=tmp)
        r.save_test_results(_make_results())
        with open(os.path.join(tmp, "test_results.txt")) as f:
            txt = f.read()
        assert "SUMMARY:" in txt
        assert "RESPONSE TYPE BREAKDOWN:" in txt
        assert "WORKING MODELS BY RESPONSE TYPE:" in txt
        assert "NON-WORKING MODELS:" in txt
        assert "TEXT MODELS:" in txt
        assert "IMAGE MODELS:" in txt
        assert "AUDIO MODELS:" in txt
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  ... {name}", end=" ")
            fn()
            print("OK")
    print("All reporter tests passed.")
