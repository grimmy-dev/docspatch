"""Tests for `docspatch cache clear` command."""

from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from src.utils.persistent_cache import get_scope_dir

runner = CliRunner()


def _app() -> typer.Typer:
    from src.cli.commands.cache import cache_app

    app = typer.Typer()
    app.add_typer(cache_app, name="cache")
    return app


# ---------------------------------------------------------------------------
# Clear all
# ---------------------------------------------------------------------------


def test_clear_deletes_cache_dir_when_present(tmp_path: Path) -> None:
    cache_root = tmp_path / ".docspatch" / "cache"
    cache_root.mkdir(parents=True)
    (cache_root / "somescope").mkdir()

    with patch("src.cli.commands.cache.get_root", return_value=tmp_path):
        result = runner.invoke(_app(), ["cache", "clear"])

    assert result.exit_code == 0
    assert not cache_root.exists()


def test_clear_prints_target_path_before_deleting(tmp_path: Path) -> None:
    cache_root = tmp_path / ".docspatch" / "cache"
    cache_root.mkdir(parents=True)

    with patch("src.cli.commands.cache.get_root", return_value=tmp_path):
        result = runner.invoke(_app(), ["cache", "clear"])

    assert str(cache_root) in result.output


def test_clear_no_op_when_cache_absent(tmp_path: Path) -> None:
    with patch("src.cli.commands.cache.get_root", return_value=tmp_path):
        result = runner.invoke(_app(), ["cache", "clear"])

    assert result.exit_code == 0
    assert "no cache" in result.output.lower()


def test_clear_exit_zero_on_success(tmp_path: Path) -> None:
    cache_root = tmp_path / ".docspatch" / "cache"
    cache_root.mkdir(parents=True)

    with patch("src.cli.commands.cache.get_root", return_value=tmp_path):
        result = runner.invoke(_app(), ["cache", "clear"])

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Clear scope
# ---------------------------------------------------------------------------


def test_clear_scope_deletes_only_targeted_scope(tmp_path: Path) -> None:
    target_a = tmp_path / "src"
    target_b = tmp_path / "lib"
    target_a.mkdir()
    target_b.mkdir()
    cache_root = tmp_path / ".docspatch" / "cache"

    scope_a = get_scope_dir(cache_root, target_a, tmp_path)
    scope_b = get_scope_dir(cache_root, target_b, tmp_path)
    scope_a.mkdir(parents=True)
    scope_b.mkdir(parents=True)

    with patch("src.cli.commands.cache.get_root", return_value=tmp_path):
        result = runner.invoke(_app(), ["cache", "clear", "--scope", str(target_a)])

    assert result.exit_code == 0
    assert not scope_a.exists()
    assert scope_b.exists()


def test_clear_scope_no_op_when_scope_absent(tmp_path: Path) -> None:
    target = tmp_path / "src"
    target.mkdir()

    with patch("src.cli.commands.cache.get_root", return_value=tmp_path):
        result = runner.invoke(_app(), ["cache", "clear", "--scope", str(target)])

    assert result.exit_code == 0
    assert "no cache" in result.output.lower()


def test_clear_scope_prints_target_before_deleting(tmp_path: Path) -> None:
    target = tmp_path / "src"
    target.mkdir()
    cache_root = tmp_path / ".docspatch" / "cache"
    scope_dir = get_scope_dir(cache_root, target, tmp_path)
    scope_dir.mkdir(parents=True)

    with patch("src.cli.commands.cache.get_root", return_value=tmp_path):
        result = runner.invoke(_app(), ["cache", "clear", "--scope", str(target)])

    assert str(scope_dir) in result.output
