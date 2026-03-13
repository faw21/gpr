"""Tests for git analysis module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gpr.git import (
    BranchDiff,
    FileDiff,
    GitError,
    _detect_base_branch,
    _parse_numstat,
    _truncate_diff,
    analyze_diff,
)


class TestFileDiff:
    def test_immutable(self):
        fd = FileDiff(path="foo.py", status="M", additions=5, deletions=2, diff_content="...")
        with pytest.raises(Exception):
            fd.path = "bar.py"

    def test_basic_fields(self):
        fd = FileDiff(path="src/main.py", status="A", additions=100, deletions=0, diff_content="")
        assert fd.path == "src/main.py"
        assert fd.status == "A"
        assert fd.additions == 100
        assert fd.deletions == 0


class TestBranchDiff:
    def _make_diff(self, files=None, commits=None):
        files = files or []
        commits = commits or []
        return BranchDiff(
            base_branch="main",
            current_branch="feature/test",
            commits=commits,
            files=files,
            total_additions=sum(f.additions for f in files),
            total_deletions=sum(f.deletions for f in files),
            raw_diff="",
        )

    def test_is_empty_when_no_files_or_commits(self):
        diff = self._make_diff()
        assert diff.is_empty

    def test_not_empty_with_files(self):
        fd = FileDiff(path="foo.py", status="M", additions=1, deletions=0, diff_content="")
        diff = self._make_diff(files=[fd])
        assert not diff.is_empty

    def test_not_empty_with_commits(self):
        diff = self._make_diff(commits=["abc123 fix: something"])
        assert not diff.is_empty

    def test_summary_format(self):
        fd = FileDiff(path="a.py", status="M", additions=10, deletions=3, diff_content="")
        diff = self._make_diff(files=[fd], commits=["abc fix"])
        assert "1 commit(s)" in diff.summary
        assert "1 file(s)" in diff.summary
        assert "+10" in diff.summary
        assert "-3" in diff.summary

    def test_immutable(self):
        diff = self._make_diff()
        with pytest.raises(Exception):
            diff.base_branch = "develop"


class TestTruncateDiff:
    def test_no_truncation_when_short(self):
        content = "line1\nline2\nline3"
        assert _truncate_diff(content, max_chars=1000) == content

    def test_truncates_when_long(self):
        content = "a" * 100 + "\n" + "b" * 100
        result = _truncate_diff(content, max_chars=50)
        assert "truncated" in result
        assert len(result) < len(content)

    def test_truncation_preserves_start(self):
        content = "important line\n" + "x" * 1000
        result = _truncate_diff(content, max_chars=50)
        assert "important line" in result


class TestParseNumstat:
    def test_parses_modified_file(self):
        numstat = "5\t3\tfoo.py"
        files = _parse_numstat(numstat, {"foo.py": "M"})
        assert len(files) == 1
        assert files[0].path == "foo.py"
        assert files[0].additions == 5
        assert files[0].deletions == 3

    def test_parses_added_file(self):
        numstat = "100\t0\tsrc/new.py"
        files = _parse_numstat(numstat, {"src/new.py": "A"})
        assert files[0].status == "A"
        assert files[0].additions == 100
        assert files[0].deletions == 0

    def test_handles_binary_file(self):
        numstat = "-\t-\timage.png"
        files = _parse_numstat(numstat, {})
        assert files[0].additions == 0
        assert files[0].deletions == 0

    def test_handles_empty_numstat(self):
        files = _parse_numstat("", {})
        assert files == []

    def test_handles_multiple_files(self):
        numstat = "5\t3\ta.py\n10\t0\tb.py\n0\t20\tc.py"
        files = _parse_numstat(numstat, {})
        assert len(files) == 3


class TestDetectBaseBranch:
    def test_detects_main(self):
        repo = MagicMock()
        repo.remotes = []
        main_branch = MagicMock()
        main_branch.name = "main"
        repo.branches = [main_branch]
        assert _detect_base_branch(repo) == "main"

    def test_detects_master_when_no_main(self):
        repo = MagicMock()
        repo.remotes = []
        master_branch = MagicMock()
        master_branch.name = "master"
        repo.branches = [master_branch]
        assert _detect_base_branch(repo) == "master"

    def test_fallback_to_head(self):
        repo = MagicMock()
        repo.remotes = []
        feature_branch = MagicMock()
        feature_branch.name = "feature/xyz"
        repo.branches = [feature_branch]
        assert _detect_base_branch(repo) == "HEAD~1"


class TestAnalyzeDiff:
    @patch("gpr.git._find_repo")
    @patch("subprocess.run")
    def test_analyze_diff_basic(self, mock_run, mock_find_repo):
        # Setup mock repo
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "feature/test"
        mock_repo.working_dir = "/fake/repo"
        main_branch = MagicMock()
        main_branch.name = "main"
        mock_repo.branches = [main_branch]
        mock_repo.remotes = []
        mock_find_repo.return_value = mock_repo

        # Mock subprocess calls
        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if "--oneline" in cmd:
                result.stdout = "abc123 feat: add feature\ndef456 fix: fix bug\n"
            elif "--numstat" in cmd:
                result.stdout = "10\t2\tsrc/main.py\n5\t0\tsrc/new.py\n"
            elif "--name-status" in cmd:
                result.stdout = "M\tsrc/main.py\nA\tsrc/new.py\n"
            else:
                result.stdout = "diff --git a/src/main.py b/src/main.py\n+new line\n"
            return result

        mock_run.side_effect = fake_run

        diff = analyze_diff()
        assert diff.current_branch == "feature/test"
        assert diff.base_branch == "main"
        assert len(diff.commits) == 2
        assert not diff.is_empty

    @patch("gpr.git._find_repo")
    def test_git_error_propagates(self, mock_find_repo):
        mock_find_repo.side_effect = GitError("Not a git repo")
        with pytest.raises(GitError):
            analyze_diff()
