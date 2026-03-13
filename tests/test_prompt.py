"""Tests for prompt generation."""

import pytest

from gpr.git import BranchDiff, FileDiff
from gpr.prompt import SYSTEM_PROMPT, build_pr_prompt, _get_format_instructions


def _make_diff(files=None, commits=None, raw_diff=""):
    files = files or [
        FileDiff(path="src/main.py", status="M", additions=10, deletions=3, diff_content=""),
    ]
    commits = commits or ["abc123 feat: add feature"]
    return BranchDiff(
        base_branch="main",
        current_branch="feature/test",
        commits=commits,
        files=files,
        total_additions=sum(f.additions for f in files),
        total_deletions=sum(f.deletions for f in files),
        raw_diff=raw_diff,
    )


class TestSystemPrompt:
    def test_system_prompt_exists(self):
        assert SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 50

    def test_system_prompt_mentions_pr(self):
        assert "pull request" in SYSTEM_PROMPT.lower()


class TestBuildPrPrompt:
    def test_includes_branch_info(self):
        diff = _make_diff()
        prompt = build_pr_prompt(diff)
        assert "feature/test" in prompt
        assert "main" in prompt

    def test_includes_commit_messages(self):
        diff = _make_diff(commits=["abc feat: my feature", "def fix: my fix"])
        prompt = build_pr_prompt(diff)
        assert "abc feat: my feature" in prompt
        assert "def fix: my fix" in prompt

    def test_includes_file_changes(self):
        diff = _make_diff()
        prompt = build_pr_prompt(diff)
        assert "src/main.py" in prompt

    def test_includes_summary(self):
        diff = _make_diff()
        prompt = build_pr_prompt(diff)
        assert "commit" in prompt.lower()

    def test_includes_raw_diff(self):
        diff = _make_diff(raw_diff="diff --git a/foo.py b/foo.py\n+new line")
        prompt = build_pr_prompt(diff)
        assert "diff --git" in prompt

    def test_no_diff_section_when_empty(self):
        diff = _make_diff(raw_diff="")
        prompt = build_pr_prompt(diff)
        # Should not have diff section header when empty
        assert "```diff" not in prompt

    def test_standard_style(self):
        diff = _make_diff()
        prompt = build_pr_prompt(diff, style="standard")
        assert "Summary" in prompt or "Title" in prompt

    def test_conventional_style(self):
        diff = _make_diff()
        prompt = build_pr_prompt(diff, style="conventional")
        assert "Conventional" in prompt or "feat" in prompt

    def test_minimal_style(self):
        diff = _make_diff()
        prompt = build_pr_prompt(diff, style="minimal")
        assert "brief" in prompt.lower()

    def test_file_status_labels(self):
        files = [
            FileDiff(path="new.py", status="A", additions=50, deletions=0, diff_content=""),
            FileDiff(path="old.py", status="D", additions=0, deletions=30, diff_content=""),
            FileDiff(path="changed.py", status="M", additions=5, deletions=2, diff_content=""),
        ]
        diff = _make_diff(files=files)
        prompt = build_pr_prompt(diff)
        assert "added" in prompt
        assert "deleted" in prompt
        assert "modified" in prompt


class TestGetFormatInstructions:
    def test_standard_instructions(self):
        instructions = _get_format_instructions("standard")
        assert "Title" in instructions
        assert "Summary" in instructions
        assert "Test Plan" in instructions

    def test_conventional_instructions(self):
        instructions = _get_format_instructions("conventional")
        assert "feat" in instructions or "Conventional" in instructions

    def test_minimal_instructions(self):
        instructions = _get_format_instructions("minimal")
        assert "brief" in instructions.lower()

    def test_unknown_style_defaults(self):
        # Unknown style should return something (standard)
        instructions = _get_format_instructions("unknown")
        assert instructions  # Non-empty
