"""Tests for g4f_tester.config."""

import os, sys, shutil, tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester.config import (
    Config,
    DEFAULT_API_KEY,
    DEFAULT_BASE_URL,
    DEFAULT_PORT,
    build_arg_parser,
    parse_args,
)


def test_defaults():
    c = Config()
    assert c.base_url == DEFAULT_BASE_URL
    assert c.api_key == DEFAULT_API_KEY
    assert c.port == DEFAULT_PORT
    assert c.max_concurrent == 50
    assert c.timeout == 120
    assert c.batch_size == 20
    assert c.start_server is True


def test_auth_headers_with_key():
    c = Config(api_key="abc")
    assert c.auth_headers == {"Authorization": "Bearer abc"}


def test_auth_headers_without_key():
    c = Config(api_key=None)
    assert c.auth_headers == {}


def test_is_github_actions():
    c = Config()
    old = os.environ.get("GITHUB_ACTIONS")
    try:
        os.environ["GITHUB_ACTIONS"] = "true"
        assert c.is_github_actions is True
        os.environ["GITHUB_ACTIONS"] = "false"
        assert c.is_github_actions is False
        del os.environ["GITHUB_ACTIONS"]
        assert c.is_github_actions is False
    finally:
        if old is not None:
            os.environ["GITHUB_ACTIONS"] = old


def test_from_env_overrides():
    old = os.environ.copy()
    try:
        os.environ["G4F_PORT"] = "9999"
        os.environ["G4F_API_KEY"] = "envkey"
        os.environ["G4F_TIMEOUT"] = "300"
        c = Config.from_env()
        assert c.port == 9999
        assert c.api_key == "envkey"
        assert c.timeout == 300
    finally:
        os.environ.clear()
        os.environ.update(old)


def test_from_env_bad_int_falls_back():
    old = os.environ.get("G4F_PORT")
    try:
        os.environ["G4F_PORT"] = "not-a-number"
        c = Config.from_env()
        assert c.port == DEFAULT_PORT
    finally:
        if old is None:
            os.environ.pop("G4F_PORT", None)
        else:
            os.environ["G4F_PORT"] = old


def test_from_env_empty_string_treated_as_missing():
    old = os.environ.get("G4F_API_KEY")
    try:
        os.environ["G4F_API_KEY"] = ""
        c = Config.from_env()
        assert c.api_key == DEFAULT_API_KEY
    finally:
        if old is None:
            os.environ.pop("G4F_API_KEY", None)
        else:
            os.environ["G4F_API_KEY"] = old


def test_from_args():
    args = parse_args(["--port", "7000", "--timeout", "99", "--no-server"])
    c = Config.from_args(args)
    assert c.port == 7000
    assert c.timeout == 99
    assert c.start_server is False


def test_ensure_dirs():
    tmp = tempfile.mkdtemp()
    try:
        c = Config(
            provider_dir=f"{tmp}/p",
            working_dir=f"{tmp}/w",
            output_dir=f"{tmp}/o",
            generated_media_dir=f"{tmp}/gm",
        )
        c.ensure_dirs()
        for d in ("p", "w", "o", "gm"):
            assert os.path.isdir(f"{tmp}/{d}")
    finally:
        shutil.rmtree(tmp)


def test_arg_parser_has_help():
    p = build_arg_parser()
    h = p.format_help()
    for flag in ("--port", "--api-key", "--base-url", "--max-concurrent",
                 "--timeout", "--batch-size", "--no-server"):
        assert flag in h


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  ... {name}", end=" ")
            fn()
            print("OK")
    print("All config tests passed.")
