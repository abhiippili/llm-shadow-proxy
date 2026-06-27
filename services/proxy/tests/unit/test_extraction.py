import pytest
from app.core.extraction import extract_response, extract_model, extract_tokens
from app.core.exceptions import ExtractionError


def test_extract_response_returns_string():
    raw = {"model": "primary-v1", "response": "Paris is the capital.", "tokens": 5}
    assert extract_response(raw) == "Paris is the capital."


def test_extract_response_raises_on_missing_field():
    raw = {"model": "primary-v1", "tokens": 5}
    with pytest.raises(ExtractionError):
        extract_response(raw)


def test_extract_response_raises_on_non_string():
    raw = {"response": 42}
    with pytest.raises(ExtractionError):
        extract_response(raw)


def test_extract_model_returns_unknown_on_missing():
    raw = {"response": "hello"}
    assert extract_model(raw) == "unknown"


def test_extract_model_returns_value_when_present():
    raw = {"response": "hello", "model": "gpt-4"}
    assert extract_model(raw) == "gpt-4"


def test_extract_tokens_returns_zero_on_missing():
    raw = {"response": "hello"}
    assert extract_tokens(raw) == 0


def test_extract_tokens_returns_value_when_present():
    raw = {"response": "hello", "tokens": 99}
    assert extract_tokens(raw) == 99


def test_extract_response_raises_with_none_value():
    raw = {"response": None}
    with pytest.raises(ExtractionError):
        extract_response(raw)
