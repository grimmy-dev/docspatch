"""Pure string and badge utilities for README generation.

Core layer — no I/O, no side effects.
"""

import re

__all__ = [
    "MAX_README_CHARS",
    "NOISE_DIRS",
    "compact_readme",
    "detect_badges",
    "git_remote_to_https",
    "preserve_sections",
]

MAX_README_CHARS = 4000

NOISE_DIRS: frozenset[str] = frozenset({".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "dist", "build"})

# Shields.io badge info for known SPDX license IDs
_LICENSE_BADGES: dict[str, tuple[str, str]] = {
    "MIT": ("MIT-yellow", "https://opensource.org/licenses/MIT"),
    "Apache-2.0": ("Apache%202.0-blue", "https://www.apache.org/licenses/LICENSE-2.0"),
    "GPL-3.0": ("GPL%20v3-blue", "https://www.gnu.org/licenses/gpl-3.0"),
    "GPL-3.0-only": ("GPL%20v3-blue", "https://www.gnu.org/licenses/gpl-3.0"),
    "BSD-3-Clause": ("BSD%203--Clause-blue", "https://opensource.org/licenses/BSD-3-Clause"),
    "LGPL-3.0": ("LGPL%20v3-blue", "https://www.gnu.org/licenses/lgpl-3.0"),
}

_GITHUB_SLUG = re.compile(r"https://github\.com/([^/]+/[^/.]+)")
_KEEP_PATTERN = re.compile(r"<!-- dp-keep -->.*?<!-- /dp-keep -->", re.DOTALL)


def compact_readme(content: str, max_chars: int) -> str:
    """Compact README to max_chars by keeping preamble, headings, and first paragraphs of each section.

    Falls back to hard truncation when compacted result still exceeds limit."""
    if len(content) <= max_chars:
        return content

    lines = content.splitlines()
    out: list[str] = []
    chars = 0
    seen_heading = False
    in_first_para = False
    saw_content = False

    for line in lines:
        is_heading = line.startswith("#")
        is_blank = not line.strip()

        if is_heading:
            seen_heading = True
            in_first_para = True
            saw_content = False
            if out and out[-1].strip():
                out.append("")
                chars += 1
            out.append(line)
            chars += len(line) + 1
        elif not seen_heading:
            out.append(line)
            chars += len(line) + 1
        elif in_first_para:
            if is_blank and saw_content:
                in_first_para = False
            elif not is_blank:
                saw_content = True
                out.append(line)
                chars += len(line) + 1

        if chars >= max_chars:
            break

    result = "\n".join(out)
    return result[:max_chars] if len(result) > max_chars else result


def git_remote_to_https(url: str) -> str:
    """Convert a Git remote URL from SSH or `git://` format to HTTPS, or normalize an existing HTTPS URL."""
    # git@github.com:owner/repo.git → https://github.com/owner/repo
    ssh = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", url)
    if ssh:
        return f"https://{ssh.group(1)}/{ssh.group(2)}"
    # git://github.com/owner/repo.git → https://github.com/owner/repo
    git_proto = re.match(r"git://(.+?)(?:\.git)?$", url)
    if git_proto:
        return f"https://{git_proto.group(1)}"
    # https://github.com/owner/repo.git → strip .git suffix
    https = re.match(r"(https://[^/]+/.+?)(?:\.git)?$", url)
    if https:
        return https.group(1)
    return url


def preserve_sections(original: str, updated: str) -> str:
    """Restore <!-- dp-keep -->...<!-- /dp-keep --> sections from original into updated.

    If no such sections exist in the original content, the updated content is returned unmodified."""
    preserved = [m.group(0) for m in _KEEP_PATTERN.finditer(original)]
    if not preserved:
        return updated
    idx = 0

    def _replace(m: re.Match[str]) -> str:
        nonlocal idx
        if idx < len(preserved):
            block = preserved[idx]
            idx += 1
            return block
        return m.group(0)

    return _KEEP_PATTERN.sub(_replace, updated)


def detect_badges(
    remote_url: str | None,
    package_name: str | None,
    version: str | None,
    license_id: str | None,
) -> list[str]:
    """Return badge markdown lines for PyPI and license when URLs will resolve.

    Only emits badges with deterministic, verifiable shield.io URLs. Never invents URLs; missing info produces no badge."""
    if not remote_url or not _GITHUB_SLUG.match(remote_url):
        return []
    badges: list[str] = []
    if package_name and version:
        pkg = package_name
        badges.append(f"[![PyPI version](https://img.shields.io/pypi/v/{pkg}.svg)](https://pypi.org/project/{pkg}/)")
    if license_id and license_id in _LICENSE_BADGES:
        label, url = _LICENSE_BADGES[license_id]
        badges.append(f"[![License: {license_id}](https://img.shields.io/badge/License-{label}.svg)]({url})")
    return badges
