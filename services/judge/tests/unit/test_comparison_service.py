import pytest
from app.services.comparison_service import normalise, compare


def test_normalise_lowercases():
    assert normalise("Hello World") == "hello world"


def test_normalise_strips_trailing_punctuation():
    assert normalise("hello.") == "hello"
    assert normalise("hello!") == "hello"
    assert normalise("hello?") == "hello"


def test_normalise_strips_whitespace():
    assert normalise("  hello  ") == "hello"


def test_normalise_collapses_spaces():
    assert normalise("hello   world") == "hello world"


def test_compare_returns_match_for_identical():
    result = compare("The answer is 42.", "The answer is 42.")
    assert result["match"] is True
    assert result["score"] == 1.0


def test_compare_returns_match_after_normalisation():
    result = compare("The answer is 42.", "the answer is 42")
    assert result["match"] is True


def test_compare_returns_mismatch_for_different():
    result = compare("The answer is 42.", "The answer is 43.")
    assert result["match"] is False
    assert result["score"] == 0.0


def test_compare_includes_reason():
    result = compare("hello", "world")
    assert "reason" in result
    assert len(result["reason"]) > 0


def test_compare_match_reason_text():
    result = compare("same text", "same text")
    assert result["reason"] == "normalised strings match"


def test_compare_mismatch_reason_text():
    result = compare("hello", "world")
    assert result["reason"] == "responses differ after normalisation"


def test_compare_includes_normalised_forms():
    result = compare("Hello World!", "hello world")
    assert "normalised_primary" in result
    assert "normalised_candidate" in result
    assert result["normalised_primary"] == "hello world"
    assert result["normalised_candidate"] == "hello world"
