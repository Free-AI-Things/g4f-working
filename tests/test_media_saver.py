"""Tests for g4f_tester.media_saver."""

import asyncio, os, sys, tempfile, shutil, base64
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester.media_saver import MediaSaver, _safe_name, _join_url


def test_safe_name_replaces_slashes():
    assert _safe_name("foo/bar") == "foo_bar"
    assert _safe_name("foo\\bar") == "foo_bar"
    assert _safe_name("plain") == "plain"


def test_join_url_relative():
    assert _join_url("http://localhost:8081", "/media/abc.mp3") == "http://localhost:8081/media/abc.mp3"
    assert _join_url("http://localhost:8081/", "/media/abc.mp3") == "http://localhost:8081/media/abc.mp3"
    assert _join_url("http://localhost:8081", "http://other/x.mp3") == "http://other/x.mp3"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_save_text():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        ok = _run(s.save_text("Prov", "gpt-4", "Hello, world!"))
        assert ok is True
        path = os.path.join(tmp, "Prov_gpt-4_response.txt")
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "Hello, world!"
    finally:
        shutil.rmtree(tmp)


def test_save_audio_bytes():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        ok = _run(s.save_audio_bytes("P", "M", b"\x00\x01\x02ID3"))
        assert ok is True
        path = os.path.join(tmp, "P_M_audio.mp3")
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == b"\x00\x01\x02ID3"
    finally:
        shutil.rmtree(tmp)


def test_save_image_data_url():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        data_url = "data:image/png;base64," + base64.b64encode(raw).decode()
        ok = _run(s.save_image_data_url("P", "M", data_url, 0))
        assert ok is True
        path = os.path.join(tmp, "P_M_image_0.jpg")
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == raw
    finally:
        shutil.rmtree(tmp)


def test_save_audio_response_with_data_url():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        raw = b"FAKE_MP3_DATA"
        data_url = "data:audio/mp3;base64," + base64.b64encode(raw).decode()
        ok = _run(s.save_audio_response("P", "M", {"data": data_url}))
        assert ok is True
        path = os.path.join(tmp, "P_M_audio.mp3")
        assert os.path.exists(path)
    finally:
        shutil.rmtree(tmp)


def test_save_audio_response_with_bytes():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        ok = _run(s.save_audio_response("P", "M", b"\x00\x00"))
        assert ok is True
        assert os.path.exists(os.path.join(tmp, "P_M_audio.mp3"))
    finally:
        shutil.rmtree(tmp)


def test_save_audio_response_unrecognised_returns_false():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        ok = _run(s.save_audio_response("P", "M", 12345))
        assert ok is False
    finally:
        shutil.rmtree(tmp)


def test_save_image_responses_mixed():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        raw = b"\x89PNG" + b"\x00" * 10
        data_url = "data:image/png;base64," + base64.b64encode(raw).decode()
        # Mix: one data URL (saves) + one unsupported string (skipped) + one http URL (will fail to download)
        n = _run(s.save_image_responses("P", "M", [data_url, "ftp://nope", "http://example.com/x.jpg"]))
        assert n == 1
        assert os.path.exists(os.path.join(tmp, "P_M_image_0.jpg"))
    finally:
        shutil.rmtree(tmp)


def test_save_video_response_with_dict():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        # Will attempt download but fail; should not raise.
        ok = _run(s.save_video_response("P", "M", {"url": "http://example.com/v.mp4"}))
        assert ok is False
    finally:
        shutil.rmtree(tmp)


def test_save_video_response_unrecognised():
    tmp = tempfile.mkdtemp()
    try:
        s = MediaSaver(tmp, base_url="http://x")
        ok = _run(s.save_video_response("P", "M", {"no_url": "here"}))
        assert ok is False
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  ... {name}", end=" ")
            fn()
            print("OK")
    print("All media_saver tests passed.")
