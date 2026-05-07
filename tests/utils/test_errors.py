"""Tests for classify_llm_error — covers all branches including chained causes."""

import pytest

from src.utils.errors import NetworkError, RateLimitError, classify_llm_error


def exc(msg: str) -> Exception:
    return Exception(msg)


def chained(outer: str, inner: str) -> Exception:
    e = Exception(outer)
    e.__cause__ = Exception(inner)
    return e


@pytest.mark.parametrize(
    "error, expected_type, fragment",
    [
        (exc("401 unauthorized"), RuntimeError, "Authentication"),
        (exc("authentication failed"), RuntimeError, "Authentication"),
        (exc("api_key invalid"), RuntimeError, "Authentication"),
        (exc("429 rate_limit exceeded"), RateLimitError, "Rate limit"),
        (exc("quota exceeded"), RateLimitError, "Rate limit"),
        (exc("resource_exhausted"), RateLimitError, "Rate limit"),
        (exc("connection refused"), NetworkError, "not responding"),
        (exc("network error"), NetworkError, "not responding"),
        (exc("502 bad gateway"), NetworkError, "not responding"),
        (exc("503 service unavailable"), NetworkError, "not responding"),
        (exc("timeout after 30s"), NetworkError, "not responding"),
        (exc("model_not_found gpt-5"), RuntimeError, "Model not found"),
        (exc("model not found"), RuntimeError, "Model not found"),
        (exc("context_length exceeded"), RuntimeError, "too long"),
        (exc("context window full"), RuntimeError, "too long"),
        (exc("input too long"), RuntimeError, "too long"),
    ],
)
def test_classify_direct(error: Exception, expected_type: type, fragment: str) -> None:
    result = classify_llm_error(error)
    assert isinstance(result, expected_type)
    assert fragment.lower() in str(result).lower()


def test_classify_chained_cause_rate_limit() -> None:
    """LangGraph wraps node exceptions — classifier must search chained cause."""
    outer = Exception("GraphExecutionError")
    outer.__cause__ = Exception("429 resource_exhausted")
    result = classify_llm_error(outer)
    assert isinstance(result, RateLimitError)


def test_classify_chained_cause_network() -> None:
    outer = Exception("TaskFailed")
    outer.__cause__ = Exception("connection refused")
    result = classify_llm_error(outer)
    assert isinstance(result, NetworkError)


def test_classify_fallback_first_line_only() -> None:
    """Fallback must not bleed JSON or multi-line traces."""
    raw = '{"error": {"code": 500, "message": "boom", "details": [1,2,3]}}\nmore stuff'
    result = classify_llm_error(exc(raw))
    assert "\n" not in str(result)
    assert len(str(result)) <= 310


def test_classify_fallback_empty_message() -> None:
    result = classify_llm_error(exc(""))
    assert "debug" in str(result).lower()
