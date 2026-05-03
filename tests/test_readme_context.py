"""Tests for readme_context node — mocks shell layer, verifies context fields."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.schemas.readme_io import ProjectContext
from src.schemas.readme_state import ReadmeState


def _state(**kwargs: object) -> ReadmeState:
    return ReadmeState(repo_path=Path("/repo"), target_path=Path("/repo"), **kwargs)  # type: ignore[arg-type]


def _mock_repo(remote_url: str | None = "git@github.com:user/repo.git") -> MagicMock:
    repo: MagicMock = MagicMock()
    if remote_url:
        remote = MagicMock()
        remote.url = remote_url
        repo.remotes = [remote]
    else:
        repo.remotes = []
    return repo


_FAKE_CTX = ProjectContext(
    name="myproject",
    version="1.2.3",
    description="A test project.",
    dependencies=["langgraph", "rich"],
    cli_scripts={"dp": "src.cli.main:app"},
    license_id="MIT",
)


def _patch_shell(repo: MagicMock, root: Path = Path("/repo")) -> list[object]:
    return [
        patch("src.graph.nodes.readme.context.get_repo", return_value=repo),
        patch("src.graph.nodes.readme.context.get_root", return_value=root),
        patch("src.graph.nodes.readme.context.parse_pyproject", return_value=_FAKE_CTX),
        patch("src.graph.nodes.readme.context.build_dir_tree", return_value="src/\n  cli/"),
        patch("src.graph.nodes.readme.context.find_init_docstring", return_value="Top-level package."),
        patch("src.graph.nodes.readme.context.load_existing_readme", return_value=("# Existing", False)),
        patch("src.graph.nodes.readme.context.git_remote_to_https", return_value="https://github.com/user/repo"),
    ]


def test_all_context_fields_populated() -> None:
    from src.graph.nodes.readme.context import readme_context

    repo = _mock_repo()
    patches = _patch_shell(repo)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        result = readme_context(_state())

    assert result["project_name"] == "myproject"
    assert result["project_version"] == "1.2.3"
    assert result["project_description"] == "A test project."
    assert result["dependencies"] == ["langgraph", "rich"]
    assert result["cli_scripts"] == {"dp": "src.cli.main:app"}
    assert result["remote_url"] == "https://github.com/user/repo"
    assert result["dir_tree"] == "src/\n  cli/"
    assert result["init_docstring"] == "Top-level package."
    assert result["license_id"] == "MIT"


def test_existing_readme_preserved_when_not_rewrite() -> None:
    from src.graph.nodes.readme.context import readme_context

    repo = _mock_repo()
    patches = _patch_shell(repo)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        result = readme_context(_state(rewrite=False))

    assert result["existing_readme"] == "# Existing"


def test_existing_readme_cleared_on_rewrite() -> None:
    from src.graph.nodes.readme.context import readme_context

    repo = _mock_repo()
    patches = _patch_shell(repo)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        result = readme_context(_state(rewrite=True))

    assert result["existing_readme"] is None


def test_no_remotes_gives_none_url() -> None:
    from src.graph.nodes.readme.context import readme_context

    repo = _mock_repo(remote_url=None)
    patches = _patch_shell(repo)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        result = readme_context(_state())

    assert result["remote_url"] is None


def test_compacted_readme_sets_flag() -> None:
    from src.graph.nodes.readme.context import readme_context

    repo = _mock_repo()
    patches = _patch_shell(repo)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[6]:
        with patch("src.graph.nodes.readme.context.load_existing_readme", return_value=("# Long README", True)):
            result = readme_context(_state(rewrite=False))

    assert result["readme_was_truncated"] is True
    assert len(result.get("warnings", [])) == 0
