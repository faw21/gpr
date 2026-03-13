"""Tests for CLI interface."""

import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

from gpr.cli import main
from gpr.git import BranchDiff, FileDiff, GitError, StagedDiff
from gpr.providers.base import ProviderError


def _make_diff():
    files = [
        FileDiff(path="src/main.py", status="M", additions=10, deletions=3, diff_content=""),
    ]
    return BranchDiff(
        base_branch="main",
        current_branch="feature/test",
        commits=["abc123 feat: add feature"],
        files=files,
        total_additions=10,
        total_deletions=3,
        raw_diff="diff --git a/src/main.py b/src/main.py\n+new line",
    )


class TestCLIBasic:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "provider" in result.output
        assert "style" in result.output

    @patch("gpr.cli.analyze_diff")
    def test_git_error_exits_with_1(self, mock_analyze):
        mock_analyze.side_effect = GitError("Not a git repo")
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 1

    @patch("gpr.cli.analyze_diff")
    def test_empty_diff_exits_0(self, mock_analyze):
        empty_diff = BranchDiff(
            base_branch="main",
            current_branch="feature/test",
            commits=[],
            files=[],
            total_additions=0,
            total_deletions=0,
            raw_diff="",
        )
        mock_analyze.return_value = empty_diff
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_provider_error_exits_1(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_diff()
        mock_get_provider.side_effect = ProviderError("No API key")
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 1

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_generate_error_exits_1(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_diff()
        mock_provider = MagicMock()
        mock_provider.name = "claude"
        mock_provider.generate.side_effect = ProviderError("API error")
        mock_get_provider.return_value = mock_provider
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 1


class TestCLIOutput:
    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_raw_output(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_diff()
        mock_provider = MagicMock()
        mock_provider.name = "claude"
        mock_provider.generate.return_value = "**Title:** Add feature\n## Summary\nTest"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["--raw"])
        assert result.exit_code == 0
        assert "Add feature" in result.output

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_output_to_file(self, mock_analyze, mock_get_provider, tmp_path):
        mock_analyze.return_value = _make_diff()
        mock_provider = MagicMock()
        mock_provider.name = "claude"
        mock_provider.generate.return_value = "PR description content"
        mock_get_provider.return_value = mock_provider

        output_file = tmp_path / "pr.md"
        runner = CliRunner()
        result = runner.invoke(main, ["--raw", "--output", str(output_file)])
        assert result.exit_code == 0
        assert output_file.read_text() == "PR description content"

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_diff_only_mode(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_diff()

        runner = CliRunner()
        result = runner.invoke(main, ["--diff-only"])
        # Should print diff without calling provider
        mock_get_provider.assert_not_called()
        assert result.exit_code == 0

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_provider_selection(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_diff()
        mock_provider = MagicMock()
        mock_provider.name = "openai"
        mock_provider.generate.return_value = "PR desc"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        runner.invoke(main, ["--provider", "openai", "--raw"])
        mock_get_provider.assert_called_once_with("openai")

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_ollama_provider_with_host(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_diff()
        mock_provider = MagicMock()
        mock_provider.name = "ollama"
        mock_provider.generate.return_value = "PR desc"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        runner.invoke(main, ["--provider", "ollama", "--ollama-host", "http://custom:11434", "--raw"])
        mock_get_provider.assert_called_once_with("ollama", host="http://custom:11434")

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_model_passed_to_provider(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_diff()
        mock_provider = MagicMock()
        mock_provider.name = "claude"
        mock_provider.generate.return_value = "PR desc"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        runner.invoke(main, ["--model", "claude-opus-4-6", "--raw"])
        mock_get_provider.assert_called_once_with("claude", model="claude-opus-4-6")


def _make_staged():
    files = [
        FileDiff(path="src/auth.py", status="M", additions=15, deletions=5, diff_content=""),
    ]
    return StagedDiff(
        files=files,
        total_additions=15,
        total_deletions=5,
        raw_diff="diff --git a/src/auth.py b/src/auth.py\n+new line",
    )


class TestCLICommitMode:
    def test_help_shows_commit_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "commit" in result.output.lower()

    @patch("gpr.cli.analyze_staged")
    def test_commit_git_error_exits_1(self, mock_analyze):
        mock_analyze.side_effect = GitError("Not a git repo")
        runner = CliRunner()
        result = runner.invoke(main, ["--commit"])
        assert result.exit_code == 1

    @patch("gpr.cli.analyze_staged")
    def test_commit_empty_staged_exits_0(self, mock_analyze):
        mock_analyze.return_value = StagedDiff(
            files=[], total_additions=0, total_deletions=0, raw_diff=""
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--commit"])
        assert result.exit_code == 0

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_staged")
    def test_commit_raw_output(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_staged()
        mock_provider = MagicMock()
        mock_provider.name = "claude"
        mock_provider.generate.return_value = "feat(auth): add token refresh logic"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["--commit", "--raw"])
        assert result.exit_code == 0
        assert "feat(auth)" in result.output

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_staged")
    def test_commit_provider_error_exits_1(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_staged()
        mock_get_provider.side_effect = ProviderError("No API key")
        runner = CliRunner()
        result = runner.invoke(main, ["--commit"])
        assert result.exit_code == 1

    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_staged")
    def test_commit_diff_only_mode(self, mock_analyze, mock_get_provider):
        mock_analyze.return_value = _make_staged()
        runner = CliRunner()
        result = runner.invoke(main, ["--commit", "--diff-only"])
        mock_get_provider.assert_not_called()
        assert result.exit_code == 0

    @patch("subprocess.run")
    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_staged")
    def test_commit_run_calls_git_commit(self, mock_analyze, mock_get_provider, mock_run):
        mock_analyze.return_value = _make_staged()
        mock_provider = MagicMock()
        mock_provider.name = "claude"
        mock_provider.generate.return_value = "feat(auth): add token refresh"
        mock_get_provider.return_value = mock_provider

        mock_run_result = MagicMock()
        mock_run_result.stdout = "1 file changed"
        mock_run.return_value = mock_run_result

        runner = CliRunner()
        result = runner.invoke(main, ["--commit-run", "--raw"])
        assert result.exit_code == 0
        # Verify git commit was called
        call_args = mock_run.call_args
        assert "git" in call_args[0][0]
        assert "commit" in call_args[0][0]

    @patch("pyperclip.copy")
    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_staged")
    def test_commit_copy_to_clipboard(self, mock_analyze, mock_get_provider, mock_copy):
        mock_analyze.return_value = _make_staged()
        mock_provider = MagicMock()
        mock_provider.name = "claude"
        mock_provider.generate.return_value = "fix(api): handle null response"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["--commit", "--copy", "--raw"])
        assert result.exit_code == 0
        mock_copy.assert_called_once_with("fix(api): handle null response")


class TestCLIClipboard:
    @patch("pyperclip.copy")
    @patch("gpr.cli.get_provider")
    @patch("gpr.cli.analyze_diff")
    def test_copy_to_clipboard(self, mock_analyze, mock_get_provider, mock_copy):
        mock_analyze.return_value = _make_diff()
        mock_provider = MagicMock()
        mock_provider.name = "claude"
        mock_provider.generate.return_value = "PR content"
        mock_get_provider.return_value = mock_provider

        runner = CliRunner()
        result = runner.invoke(main, ["--copy", "--raw"])
        assert result.exit_code == 0
        mock_copy.assert_called_once_with("PR content")
