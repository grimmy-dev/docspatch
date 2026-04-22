import re


def normalize(source: str) -> str:
    """Strip whitespace and comments so cosmetic changes don't trigger LLM."""
    source = re.sub(r"#.*", "", source)  # inline comments
    source = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)  # docstrings
    source = re.sub(r"'''.*?'''", "", source, flags=re.DOTALL)
    source = re.sub(r"\s+", " ", source)  # collapse all whitespace
    return source.strip()


def is_significant(old_body: str, new_body: str) -> bool:
    """Return True if the change is meaningful (not just whitespace/comments)."""
    return normalize(old_body) != normalize(new_body)


def has_meaningful_changes(functions: list[dict]) -> bool:
    """Return True if any function in the list is marked significant."""
    return any(f.get("is_significant", False) for f in functions)
