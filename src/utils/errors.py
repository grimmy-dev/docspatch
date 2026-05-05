"""Domain exceptions and LLM error classifier."""

__all__ = ["NetworkError", "RateLimitError", "classify_llm_error"]


class RateLimitError(RuntimeError):
    """Raised when an LLM provider returns a rate-limit or quota response."""


class NetworkError(RuntimeError):
    """Raised on transient network/server errors (timeout, 502, 503, connection)."""


def classify_llm_error(exc: Exception) -> RuntimeError:
    """Map a raw LLM exception to a typed, user-friendly RuntimeError.

    Searches both the exception and its chained cause so LangGraph-wrapped
    errors are classified correctly. Fallback truncates to the first line to
    prevent raw JSON or stack traces leaking into user-facing messages.

    Args:
        exc: The raw exception raised by the LLM.

    Returns:
        A user-friendly RuntimeError that captures the essence of the original
        exception."""
    parts = [str(exc)]
    cause = exc.__cause__ or exc.__context__
    if cause:
        parts.append(str(cause))
    msg = " ".join(parts).lower()

    if any(s in msg for s in ("401", "unauthorized", "authentication", "api_key")):
        return RuntimeError("Authentication failed — check your API key.")
    if any(s in msg for s in ("429", "rate_limit", "quota", "resource_exhausted")):
        return RateLimitError("Rate limit hit — wait and retry.")
    if "model_not_found" in msg or "model not found" in msg:
        return RuntimeError("Model not found — check your model setting.")
    if "context_length" in msg or "context window" in msg or "too long" in msg:
        return RuntimeError("Input too long — reduce the amount of code being processed.")
    if "timeout" in msg or any(s in msg for s in ("connection", "network", "502", "503")):
        return NetworkError("Server not responding — retrying.")

    lines = str(exc).splitlines()
    first_line = lines[0][:300].strip() if lines else ""
    return RuntimeError(first_line or "Unexpected LLM error — run with --debug for details.")
