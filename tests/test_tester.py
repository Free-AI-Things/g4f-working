"""Tests for g4f_tester.tester.

These use a fake aiohttp session so we don't need a real g4f API server.
"""

import asyncio, json, os, sys, tempfile, shutil
from unittest.mock import AsyncMock, MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester.models import TestResultWithTypes
from g4f_tester.tester import ProviderModelTester


def _run(coro):
    return asyncio.run(coro)


def _make_tester(tmp):
    return ProviderModelTester(
        base_url="http://localhost:8081",
        api_key="key",
        max_concurrent=5,
        timeout=10,
        output_dir=tmp,
    )


class FakeResponse:
    """Minimal stand-in for an aiohttp response."""
    def __init__(self, status=200, json_data=None, chunks=None, headers=None):
        self.status = status
        self._json = json_data
        self._chunks = chunks or []
        self.headers = headers or {}
        self._chunk_iter = iter(self._chunks)

    async def json(self):
        return self._json

    async def text(self):
        return json.dumps(self._json) if self._json is not None else ""

    async def read(self):
        return b"\x00\x01\x02"  # tiny fake audio

    @property
    def content(self):
        async def _aiter():
            for c in self._chunks:
                if c is None:
                    yield b""
                else:
                    yield c.encode("utf-8") if isinstance(c, str) else c
        return _aiter()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    def __init__(self):
        self.posts = []
        self.gets = []
        self._post_responses = {}
        self._get_responses = {}

    def stub_post(self, url_substring, response):
        self._post_responses[url_substring] = response

    def stub_get(self, url_substring, response):
        self._get_responses[url_substring] = response

    def post(self, url, headers=None, json=None, timeout=None):
        self.posts.append((url, json))
        for k, v in self._post_responses.items():
            if k in url:
                return v
        return FakeResponse(status=404, json_data={"error": {"message": "no stub"}})

    def get(self, url, headers=None, timeout=None):
        self.gets.append(url)
        for k, v in self._get_responses.items():
            if k in url:
                return v
        return FakeResponse(status=404, json_data={})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def test_guess_response_types_text_only():
    t = _make_tester(tempfile.mkdtemp())
    assert t._guess_response_types("gpt-4", {}) == ["text"]


def test_guess_response_types_image_keyword():
    t = _make_tester(tempfile.mkdtemp())
    types = t._guess_response_types("dall-e-3", {})
    assert "image" in types


def test_guess_response_types_audio_keyword():
    t = _make_tester(tempfile.mkdtemp())
    types = t._guess_response_types("tts-1", {})
    assert "audio" in types


def test_guess_response_types_video_keyword():
    t = _make_tester(tempfile.mkdtemp())
    types = t._guess_response_types("sora", {})
    assert "video" in types


def test_guess_response_types_with_api_caps():
    t = _make_tester(tempfile.mkdtemp())
    types = t._guess_response_types("custom", {"image": True, "audio": True})
    assert "image" in types and "audio" in types


def test_test_single_model_success_streaming():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        chunks = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: [DONE]',
        ]
        sess.stub_post("/v1/chat/completions", FakeResponse(status=200, chunks=chunks))
        result = _run(t.test_single_model(sess, "ProvA", "gpt-4", ["text"]))
        assert result.working is True
        assert result.provider == "ProvA"
        assert result.model == "gpt-4"
        assert "Hello" in result.response_content
        # File should have been written.
        assert os.path.exists(os.path.join(tmp, "ProvA_gpt-4_response.txt"))
    finally:
        shutil.rmtree(tmp)


def test_test_single_model_http_error():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        sess.stub_post("/v1/chat/completions", FakeResponse(status=500, json_data={"error": "boom"}))
        result = _run(t.test_single_model(sess, "ProvA", "gpt-4", ["text"]))
        assert result.working is False
        assert "HTTP 500" in result.error
    finally:
        shutil.rmtree(tmp)


def test_test_single_model_api_error_in_stream():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        chunks = [
            'data: {"error":{"message":"rate limited"}}',
        ]
        sess.stub_post("/v1/chat/completions", FakeResponse(status=200, chunks=chunks))
        result = _run(t.test_single_model(sess, "ProvA", "gpt-4", ["text"]))
        assert result.working is False
        assert "API Error" in result.error
        assert "rate limited" in result.error
    finally:
        shutil.rmtree(tmp)


def test_test_image_generation_success():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        sess.stub_post("/v1/images/generate", FakeResponse(
            status=200, json_data={"data": [{"url": "http://example.com/img.jpg"}]}
        ))
        # The image download will fail (no stub), but the test should still report success.
        result = _run(t.test_image_generation(sess, "ProvA", "dall-e-3", ["text", "image"]))
        assert result.working is True
        assert result.media_type == "image"
        assert "Image generated" in result.response_content
    finally:
        shutil.rmtree(tmp)


def test_test_image_generation_no_data():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        sess.stub_post("/v1/images/generate", FakeResponse(status=200, json_data={"data": []}))
        result = _run(t.test_image_generation(sess, "ProvA", "dall-e-3", ["text", "image"]))
        assert result.working is False
        assert "No valid image data" in result.error
    finally:
        shutil.rmtree(tmp)


def test_test_video_generation_falls_back_to_chat():
    """First endpoint returns 404 → should try chat/completions."""
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        # First call: video/generate returns 404.
        # Second call: chat/completions returns 200 with a chunk mentioning "video".
        # FakeSession dispatches by URL substring — we need separate responses.
        # Trick: stub_post matches by substring; "video/generate" won't match "/v1/chat/completions"
        # so we register both.

        def post(url, headers=None, json=None, timeout=None):
            if "video/generate" in url:
                return FakeResponse(status=404, json_data={"error": "not found"})
            if "chat/completions" in url:
                chunks = ['data: {"choices":[{"delta":{"content":"Here is your video: <video url>"}}]}', 'data: [DONE]']
                return FakeResponse(status=200, chunks=chunks)
            return FakeResponse(status=404)
        sess.post = post
        result = _run(t.test_video_generation(sess, "ProvA", "sora", ["text", "video"]))
        assert result.working is True
        assert result.media_type == "video"
    finally:
        shutil.rmtree(tmp)


def test_test_video_generation_payload_not_mutated():
    """Critical regression: the legacy code mutated the payload dict."""
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        captured_payloads = []

        def post(url, headers=None, json=None, timeout=None):
            captured_payloads.append(json)
            if "video/generate" in url:
                return FakeResponse(status=200, json_data={"data": [{"url": "http://x/v.mp4"}]})
            return FakeResponse(status=404)
        sess = FakeSession()
        sess.post = post
        result = _run(t.test_video_generation(sess, "ProvA", "sora", ["text", "video"]))
        assert result.working is True
        # The first payload must have "prompt" (video/generate), not "messages".
        assert "prompt" in captured_payloads[0]
        assert "messages" not in captured_payloads[0]
    finally:
        shutil.rmtree(tmp)


def test_test_audio_generation_raw_bytes():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        # audio/speech endpoint returns raw bytes (not JSON).
        sess.stub_post("/v1/audio/speech", FakeResponse(
            status=200, json_data=None, headers={"Content-Type": "audio/mpeg"}
        ))
        result = _run(t.test_audio_generation(sess, "ProvA", "tts-1", ["text", "audio"]))
        assert result.working is True
        assert result.media_type == "audio"
        assert os.path.exists(os.path.join(tmp, "ProvA_tts-1_audio.mp3"))
    finally:
        shutil.rmtree(tmp)


def test_test_audio_generation_payload_not_mutated():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        captured = []

        def post(url, headers=None, json=None, timeout=None):
            captured.append(json)
            if "audio/speech" in url:
                # Return raw bytes.
                return FakeResponse(status=200, json_data=None,
                                    headers={"Content-Type": "audio/mpeg"})
            return FakeResponse(status=404)
        sess = FakeSession()
        sess.post = post
        result = _run(t.test_audio_generation(sess, "ProvA", "tts-1", ["text", "audio"]))
        assert result.working is True
        # First payload is for audio/speech and must have "input" + "voice", not "messages".
        assert "input" in captured[0]
        assert "voice" in captured[0]
        assert "messages" not in captured[0]
    finally:
        shutil.rmtree(tmp)


def test_test_audio_generation_falls_back_to_chat():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)

        def post(url, headers=None, json=None, timeout=None):
            if "audio/speech" in url:
                return FakeResponse(status=404, json_data={"error": "no"})
            if "chat/completions" in url:
                chunks = ['data: {"choices":[{"message":{"audio":{"data": "data:audio/mp3;base64,AAAA"}}}]}', 'data: [DONE]']
                return FakeResponse(status=200, chunks=chunks)
            return FakeResponse(status=404)
        sess = FakeSession()
        sess.post = post
        result = _run(t.test_audio_generation(sess, "ProvA", "tts-1", ["text", "audio"]))
        assert result.working is True
        assert os.path.exists(os.path.join(tmp, "ProvA_tts-1_audio.mp3"))
    finally:
        shutil.rmtree(tmp)


def test_get_model_capabilities_uses_session():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        sess.stub_get("/api/ProvA/models", FakeResponse(
            status=200, json_data={"data": [{"id": "m1", "image": True}]}
        ))
        caps = _run(t.get_model_capabilities(sess, "ProvA", "m1"))
        assert caps == {"image": True, "video": False, "audio": False, "vision": False}
    finally:
        shutil.rmtree(tmp)


def test_get_model_capabilities_missing_model_returns_empty():
    tmp = tempfile.mkdtemp()
    try:
        t = _make_tester(tmp)
        sess = FakeSession()
        sess.stub_get("/api/ProvA/models", FakeResponse(
            status=200, json_data={"data": [{"id": "other"}]}
        ))
        caps = _run(t.get_model_capabilities(sess, "ProvA", "m1"))
        assert caps == {}
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  ... {name}", end=" ")
            fn()
            print("OK")
    print("All tester tests passed.")
