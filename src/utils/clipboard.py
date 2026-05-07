"""System clipboard write utilities.

Shell layer — spawns subprocesses and uses platform-specific APIs.
"""

import os
import subprocess
import sys

__all__ = ["copy_to_clipboard"]


def _run_clipboard_cmd(cmd: list[str], encoded: bytes) -> bool:
    """Write bytes to a clipboard tool via stdin; tolerates daemons that never exit.

    wl-copy and xclip stay alive serving the clipboard until another app reads it.
    We write stdin, close it, then wait up to 1 s. If the process is still running
    after that it has accepted the content — treat as success."""
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.stdin is None:
            proc.kill()
            return False
        proc.stdin.write(encoded)
        proc.stdin.close()
        try:
            proc.wait(timeout=1.0)
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            return True  # still running — serving clipboard
    except (FileNotFoundError, OSError) as _:
        return False


def _copy_to_clipboard_win32(text: str) -> bool:
    """Windows clipboard write via ctypes Win32 API."""
    try:
        import ctypes  # noqa: PLC0415
    except ImportError:
        return False

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    encoded = text.encode("utf-16-le") + b"\x00\x00"

    try:
        handle = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))  # type: ignore[attr-defined]
        if not handle:
            return False
        ptr = ctypes.windll.kernel32.GlobalLock(handle)  # type: ignore[attr-defined]
        if not ptr:
            ctypes.windll.kernel32.GlobalFree(handle)  # type: ignore[attr-defined]
            return False
        ctypes.memmove(ptr, encoded, len(encoded))
        ctypes.windll.kernel32.GlobalUnlock(handle)  # type: ignore[attr-defined]

        if not ctypes.windll.user32.OpenClipboard(0):  # type: ignore[attr-defined]
            ctypes.windll.kernel32.GlobalFree(handle)  # type: ignore[attr-defined]
            return False
        try:
            ctypes.windll.user32.EmptyClipboard()  # type: ignore[attr-defined]
            ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, handle)  # type: ignore[attr-defined]
        finally:
            ctypes.windll.user32.CloseClipboard()  # type: ignore[attr-defined]
        return True
    except (OSError, AttributeError) as _:
        return False


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard; returns False when unavailable.

    Linux: requires DISPLAY or WAYLAND_DISPLAY and wl-copy, xclip, or xsel.
    macOS: uses pbcopy.
    Windows: uses ctypes directly — no external dependency.

    Args:
        text: The text to copy to the clipboard.

    Returns:
        True if the text was successfully copied, False otherwise."""
    if sys.platform == "linux":
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False
        encoded = text.encode()
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            if _run_clipboard_cmd(cmd, encoded):
                return True
        return False

    if sys.platform == "darwin":
        return _run_clipboard_cmd(["pbcopy"], text.encode())

    if sys.platform == "win32":
        return _copy_to_clipboard_win32(text)

    return False
