def classify_llm_error(e: Exception) -> RuntimeError:
    """Map provider exceptions to user-friendly messages."""
    msg = str(e).lower()

    if any(k in msg for k in ("401", "unauthorized", "authentication", "api key", "invalid_api_key")):
        return RuntimeError(
            "API key rejected. Verify your key in ~/.docspatch/config.toml"
        )
    if any(k in msg for k in ("429", "rate limit", "quota", "resource_exhausted")):
        return RuntimeError(
            "Rate limit hit. Wait a moment and retry, or switch to a different model."
        )
    if any(k in msg for k in ("model not found", "does not exist", "invalid model", "model_not_found")):
        return RuntimeError(
            "Model not found. Check model name in ~/.docspatch/config.toml"
        )
    if any(k in msg for k in ("context length", "maximum context", "token limit", "too long")):
        return RuntimeError(
            "Input exceeds model context window. Use --style compact or narrow the path scope."
        )
    if any(k in msg for k in ("timeout", "timed out", "deadline")):
        return RuntimeError(
            "Request timed out. Check your connection and retry."
        )
    if any(k in msg for k in ("connection", "network", "unavailable", "503", "502")):
        return RuntimeError(
            "Network error reaching the API. Check your connection and retry."
        )

    return RuntimeError(f"LLM call failed: {e}")
