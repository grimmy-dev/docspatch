"""Shared runner utilities — thread ID generation and interrupt typing."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils.git import get_root

__all__ = ["make_thread", "thread_id"]


def thread_id(command: str, target_path: Path) -> str:
    """Return a 16-char hex hash of repo_root + command + path; stable across resumes."""
    root = get_root()
    key = f"{root}{command}{target_path}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def make_thread(command: str, target_path: Path, resume: bool) -> str:
    """Return base thread ID when resuming, or base_id_timestamp for new runs."""
    base = thread_id(command, target_path)
    if resume:
        return base
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{base}_{ts}"


def iv_type(iv: Any) -> str | None:
    """Extract the 'type' field from an interrupt value dict."""
    return iv.get("type") if isinstance(iv, dict) else None
