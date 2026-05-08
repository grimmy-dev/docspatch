"""Tests for readme_context node — mocks shell layer, verifies context fields."""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.schemas.readme_io import ProjectContext
from src.schemas.readme_state import ReadmeState
from src.utils.git.reader import GitSignals


def _state(**kwargs: object) -> ReadmeState:
    return ReadmeState(repo_path=Path("/repo"), target_path=Path("/repo"), **kwargs)  # type: ignore[arg-type]


def _mock_reader(remote_url: str | None = "git@github.com:user/repo.git", root: Path = Path("/repo")) -> MagicMock:
    reader: MagicMock = MagicMock()
    reader.root = root
    reader.resolve_target.return_value = root
    reader.get_remote_url.return_value = remote_url
    reader.get_activity_signals.return_value = GitSignals(commit_count=10, first_commit="2024-01", last_commit="2026-04", is_dormant=False)
    return reader


_FAKE_CTX = ProjectContext(
    name="myproject",
    version="1.2.3",
    description="A test project.",
    dependencies=["langgraph", "rich"],
    cli_scripts={"dp": "src.cli.main:app"},
    license_id="MIT",
)

_FAKE_PUBLIC_API: dict[str, list[str]] = {"src/cli/main.py": ["app", "main"]}
_FAKE_TEST_COVERAGE = "Test coverage: 12 test files, 45 functions covered"


def _patches(reader: MagicMock, readme_return: tuple[str | None, bool] = ("# Existing", False)) -> list[object]:
    return [
        patch("src.graph.nodes.readme.context.GitReader", return_value=reader),
        patch("src.graph.nodes.readme.context.parse_pyproject", return_value=_FAKE_CTX),
        patch("src.graph.nodes.readme.context.build_dir_tree", return_value="src/\n  cli/"),
        patch("src.graph.nodes.readme.context.find_init_docstring", return_value="Top-level package."),
        patch("src.graph.nodes.readme.context.load_existing_readme", return_value=readme_return),
        patch("src.graph.nodes.readme.context.git_remote_to_https", return_value="https://github.com/user/repo"),
        patch("src.graph.nodes.readme.context.scan_public_api", return_value=_FAKE_PUBLIC_API),
        patch("src.graph.nodes.readme.context.get_test_coverage_summary", return_value=_FAKE_TEST_COVERAGE),
        patch("src.graph.nodes.readme.context.extract_usage_examples", return_value=[]),
    ]


def _run(state: ReadmeState, patches: list[object]) -> object:
    from src.graph.nodes.readme.context import readme_context

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)  # type: ignore[arg-type]
        return readme_context(state)


def test_all_context_fields_populated() -> None:
    reader = _mock_reader()
    result = _run(_state(), _patches(reader))

    pc = result["project_context"]  # type: ignore[index]
    assert pc.name == "myproject"
    assert pc.version == "1.2.3"
    assert pc.description == "A test project."
    assert pc.dependencies == ["langgraph", "rich"]
    assert pc.cli_scripts == {"dp": "src.cli.main:app"}
    assert pc.license_id == "MIT"
    assert result["remote_url"] == "https://github.com/user/repo"  # type: ignore[index]
    assert result["dir_tree"] == "src/\n  cli/"  # type: ignore[index]
    assert result["init_docstring"] == "Top-level package."  # type: ignore[index]
    assert result["public_api"] == _FAKE_PUBLIC_API  # type: ignore[index]
    assert result["test_coverage"] == _FAKE_TEST_COVERAGE  # type: ignore[index]
    assert result["usage_examples"] == []  # type: ignore[index]
    assert isinstance(result["git_signals"], GitSignals)  # type: ignore[index]


def test_existing_readme_preserved_when_not_rewrite() -> None:
    reader = _mock_reader()
    result = _run(_state(rewrite=False), _patches(reader))
    assert result["existing_readme"] == "# Existing"  # type: ignore[index]


def test_existing_readme_cleared_on_rewrite() -> None:
    reader = _mock_reader()
    result = _run(_state(rewrite=True), _patches(reader))
    assert result["existing_readme"] is None  # type: ignore[index]


def test_no_remotes_gives_none_url() -> None:
    reader = _mock_reader(remote_url=None)
    result = _run(_state(), _patches(reader))
    assert result["remote_url"] is None  # type: ignore[index]


def test_compacted_readme_sets_flag() -> None:
    reader = _mock_reader()
    result = _run(_state(rewrite=False), _patches(reader, readme_return=("# Long README", True)))
    assert result["readme_was_truncated"] is True  # type: ignore[index]
    assert len(result.get("warnings", [])) == 0  # type: ignore[index]


def _subpackage_state() -> ReadmeState:
    return ReadmeState(repo_path=Path("/repo"), target_path=Path("/repo/subpkg"))  # type: ignore[arg-type]


def _subpackage_reader() -> MagicMock:
    reader = _mock_reader()
    reader.root = Path("/repo")
    reader.resolve_target.return_value = Path("/repo/subpkg")
    return reader


def test_subpackage_strips_repo_level_fields() -> None:
    reader = _subpackage_reader()
    result = _run(_subpackage_state(), _patches(reader))

    pc = result["project_context"]  # type: ignore[index]
    assert pc.dependencies == []
    assert pc.cli_scripts == {}
    assert pc.license_id is None
    assert result["remote_url"] is None  # type: ignore[index]


def test_subpackage_preserves_name_version_description() -> None:
    reader = _subpackage_reader()
    result = _run(_subpackage_state(), _patches(reader))

    pc = result["project_context"]  # type: ignore[index]
    assert pc.name == "myproject"
    assert pc.version == "1.2.3"
    assert pc.description == "A test project."


def test_root_level_preserves_all_fields() -> None:
    reader = _mock_reader()
    result = _run(_state(), _patches(reader))

    pc = result["project_context"]  # type: ignore[index]
    assert pc.dependencies == ["langgraph", "rich"]
    assert pc.cli_scripts == {"dp": "src.cli.main:app"}
    assert pc.license_id == "MIT"
    assert result["remote_url"] == "https://github.com/user/repo"  # type: ignore[index]
