"""Tests for CLI interface."""

import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

from gpr.cli import main
from gpr.git import BranchDiff, FileDiff, GitError
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
        assert "0.1.0" in result.output

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
