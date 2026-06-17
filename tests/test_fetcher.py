"""Tests for g4f_tester.fetcher."""

import json, os, sys, tempfile, shutil
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester.fetcher import ProviderModelFetcher


def _make_fetcher(tmp):
    return ProviderModelFetcher("http://localhost:8081", "key", provider_dir=tmp)


def test_determine_response_types_text_only():
    info = {"id": "gpt-4", "image": False, "video": False, "audio": False}
    assert ProviderModelFetcher.determine_response_types(info) == ["text"]


def test_determine_response_types_with_image_flag():
    info = {"id": "dall-e-3", "image": True, "video": False, "audio": False}
    types = ProviderModelFetcher.determine_response_types(info)
    assert "image" in types
    assert "text" in types


def test_determine_response_types_with_keyword_only():
    info = {"id": "some-flux-model", "image": False, "video": False, "audio": False}
    types = ProviderModelFetcher.determine_response_types(info)
    assert "image" in types


def test_determine_response_types_audio_keyword():
    info = {"id": "tts-1", "image": False, "video": False, "audio": False}
    types = ProviderModelFetcher.determine_response_types(info)
    assert "audio" in types


def test_determine_response_types_video_keyword():
    info = {"id": "sora-2", "image": False, "video": False, "audio": False}
    types = ProviderModelFetcher.determine_response_types(info)
    assert "video" in types


def test_extract_test_data_with_string_models():
    data = {
        "ProvA": {"models": ["m1", "m2"], "model_count": 2},
        "ProvB": {"models": ["m3"], "model_count": 1},
    }
    pairs = ProviderModelFetcher.extract_test_data(data)
    assert pairs == [("ProvA", "m1"), ("ProvA", "m2"), ("ProvB", "m3")]


def test_extract_test_data_with_dict_models():
    data = {
        "ProvA": {"models": [{"id": "m1"}, {"id": "m2"}], "model_count": 2},
    }
    pairs = ProviderModelFetcher.extract_test_data(data)
    assert pairs == [("ProvA", "m1"), ("ProvA", "m2")]


def test_extract_test_data_skips_missing_id():
    data = {"P": {"models": [{"id": "m1"}, {"no_id": True}, "m3"]}}
    pairs = ProviderModelFetcher.extract_test_data(data)
    assert pairs == [("P", "m1"), ("P", "m3")]


def test_save_to_files_writes_both_formats():
    tmp = tempfile.mkdtemp()
    try:
        f = _make_fetcher(tmp)
        data = {
            "ProvA": {
                "provider_info": {"url": "http://a", "label": "A"},
                "models": ["m1", "m2"],
                "model_count": 2,
            },
            "ProvB": {
                "provider_info": {"url": "http://b", "label": "B"},
                "models": [],
                "model_count": 0,
                "error": "boom",
            },
        }
        f.save_to_files(data, "providers_models")
        j = os.path.join(tmp, "providers_models.json")
        t = os.path.join(tmp, "providers_models.txt")
        assert os.path.exists(j)
        assert os.path.exists(t)
        with open(j) as fh:
            loaded = json.load(fh)
        assert loaded == data
        with open(t) as fh:
            txt = fh.read()
        assert "ProvA" in txt
        assert "ProvB" in txt
        assert "boom" in txt
        assert "m1" in txt
    finally:
        shutil.rmtree(tmp)


def test_create_test_format():
    tmp = tempfile.mkdtemp()
    try:
        f = _make_fetcher(tmp)
        data = {
            "ProvA": {"models": ["m1", "m2"], "model_count": 2},
            "ProvB": {"models": ["m3"], "model_count": 1},
        }
        f.create_test_format(data, "models_for_testing.txt")
        path = os.path.join(tmp, "models_for_testing.txt")
        assert os.path.exists(path)
        with open(path) as fh:
            txt = fh.read()
        assert "ProvA|m1" in txt
        assert "ProvA|m2" in txt
        assert "ProvB|m3" in txt
        assert txt.startswith("# Format:")
    finally:
        shutil.rmtree(tmp)


def test_save_with_types():
    tmp = tempfile.mkdtemp()
    try:
        f = _make_fetcher(tmp)
        data = {
            "ProvA": {
                "provider_info": {"url": "http://a", "label": "A"},
                "models": [
                    {"id": "m1", "image": True, "video": False, "audio": False, "vision": False,
                     "response_types": ["text", "image"]},
                ],
                "model_count": 1,
            },
        }
        f.save_with_types(data)
        assert os.path.exists(os.path.join(tmp, "provider_models_type.json"))
        assert os.path.exists(os.path.join(tmp, "provider_models_type.txt"))
    finally:
        shutil.rmtree(tmp)


def test_fetch_with_mocked_http():
    tmp = tempfile.mkdtemp()
    try:
        f = _make_fetcher(tmp)
        providers_payload = [{"id": "ProvA", "url": "u", "label": "A"}]
        models_payload = {"data": [{"id": "m1"}, {"id": "m2"}]}

        def fake_get(url, headers=None, timeout=None):
            r = MagicMock()
            r.raise_for_status = MagicMock()
            if url.endswith("/v1/providers"):
                r.json = MagicMock(return_value=providers_payload)
            elif "/api/ProvA/models" in url:
                r.json = MagicMock(return_value=models_payload)
            else:
                r.json = MagicMock(return_value={})
            return r

        with patch("g4f_tester.fetcher.requests.get", side_effect=fake_get):
            data = f.fetch(with_types=False, sleep_between=0)

        assert "ProvA" in data
        assert data["ProvA"]["models"] == ["m1", "m2"]
        assert data["ProvA"]["model_count"] == 2
    finally:
        shutil.rmtree(tmp)


def test_fetch_with_types_with_mocked_http():
    tmp = tempfile.mkdtemp()
    try:
        f = _make_fetcher(tmp)
        providers_payload = [{"id": "ProvA", "url": "u", "label": "A"}]
        models_payload = {"data": [{"id": "m1", "image": True}, {"id": "m2"}]}

        def fake_get(url, headers=None, timeout=None):
            r = MagicMock()
            r.raise_for_status = MagicMock()
            if url.endswith("/v1/providers"):
                r.json = MagicMock(return_value=providers_payload)
            elif "/api/ProvA/models" in url:
                r.json = MagicMock(return_value=models_payload)
            else:
                r.json = MagicMock(return_value={})
            return r

        with patch("g4f_tester.fetcher.requests.get", side_effect=fake_get):
            data = f.fetch(with_types=True, sleep_between=0)

        models = data["ProvA"]["models"]
        assert models[0]["id"] == "m1"
        assert models[0]["image"] is True
        assert "image" in models[0]["response_types"]
        assert models[1]["id"] == "m2"
        assert models[1]["image"] is False
    finally:
        shutil.rmtree(tmp)


def test_fetch_handles_provider_error():
    tmp = tempfile.mkdtemp()
    try:
        f = _make_fetcher(tmp)
        providers_payload = [{"id": "ProvA"}, {"id": "ProvB"}]

        def fake_get(url, headers=None, timeout=None):
            r = MagicMock()
            r.raise_for_status = MagicMock()
            if url.endswith("/v1/providers"):
                r.json = MagicMock(return_value=providers_payload)
                return r
            if "/api/ProvA/models" in url:
                r.json = MagicMock(return_value={"data": [{"id": "m1"}]})
                return r
            if "/api/ProvB/models" in url:
                import requests as _r
                raise _r.RequestException("network bad")
            r.json = MagicMock(return_value={})
            return r

        with patch("g4f_tester.fetcher.requests.get", side_effect=fake_get):
            data = f.fetch(with_types=False, sleep_between=0)

        assert data["ProvA"]["models"] == ["m1"]
        assert data["ProvB"]["models"] == []
        assert "error" in data["ProvB"]
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  ... {name}", end=" ")
            fn()
            print("OK")
    print("All fetcher tests passed.")
