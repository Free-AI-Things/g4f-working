"""Tests for g4f_tester.models."""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester.models import TestResult, TestResultWithTypes


def test_test_result_defaults():
    r = TestResult(provider="P", model="M", working=True, response_time=1.2)
    assert r.provider == "P"
    assert r.model == "M"
    assert r.working is True
    assert r.response_time == 1.2
    assert r.error is None
    assert r.response_content is None
    assert r.media_type is None


def test_test_result_with_types_default_response_types():
    r = TestResultWithTypes(provider="P", model="M", working=True, response_time=1.0)
    assert r.response_types == ["text"]


def test_test_result_with_types_explicit_response_types():
    r = TestResultWithTypes(
        provider="P", model="M", working=True, response_time=1.0,
        response_types=["text", "image"],
    )
    assert r.response_types == ["text", "image"]


def test_test_result_with_types_none_response_types_is_replaced():
    r = TestResultWithTypes(
        provider="P", model="M", working=True, response_time=1.0,
        response_types=None,
    )
    assert r.response_types == ["text"]


def test_test_result_with_types_text_is_always_present():
    r = TestResultWithTypes(
        provider="P", model="M", working=True, response_time=1.0,
        response_types=["image"],
    )
    assert r.response_types == ["text", "image"]


def test_to_dict_round_trip():
    r = TestResultWithTypes(
        provider="P", model="M", working=True, response_time=1.0,
        response_content="hello", media_type="text",
        response_types=["text"],
    )
    d = r.to_dict()
    assert d["provider"] == "P"
    assert d["model"] == "M"
    assert d["working"] is True
    assert d["response_content"] == "hello"
    assert d["media_type"] == "text"
    assert d["response_types"] == ["text"]
    # to_dict should not share state with the source object.
    d["response_types"].append("image")
    assert r.response_types == ["text"]


def test_instances_do_not_share_response_types():
    a = TestResultWithTypes(provider="P", model="A", working=True, response_time=1.0)
    b = TestResultWithTypes(provider="P", model="B", working=True, response_time=1.0)
    a.response_types.append("image")
    assert b.response_types == ["text"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  ... {name}", end=" ")
            fn()
            print("OK")
    print("All model tests passed.")
