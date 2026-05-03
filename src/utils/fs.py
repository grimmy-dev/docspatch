"""Filesystem utilities."""

import os
from pathlib import Path


def atomic_write(path: Path, content: str) -> None:
    """Write content to path via a temp file; cleans up on any failure.

    Args:
        path: The final destination path.
        content: The string content to write.

    Raises:
        OSError: If any file operation fails."""
    tmp = Path(str(path) + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
