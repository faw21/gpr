"""Git repository analysis for PR generation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import git as gitpython
from git.exc import InvalidGitRepositoryError


class GitError(Exception):
    """Raised when git operations fail."""


@dataclass(frozen=True)
class FileDiff:
    """Represents changes to a single file."""

    path: str
    status: str  # A=added, M=modified, D=deleted, R=renamed
    additions: int
    deletions: int
    diff_content: str


@dataclass(frozen=True)
class BranchDiff:
    """Complete diff of a branch against its base."""

    base_branch: str
    current_branch: str
    commits: list[str]
    files: list[FileDiff]
    total_additions: int
    total_deletions: int
    raw_diff: str

    @property
    def is_empty(self) -> bool:
        return not self.files and not self.commits

    @property
    def summary(self) -> str:
        n_files = len(self.files)
        n_commits = len(self.commits)
        return (
            f"{n_commits} commit(s), {n_files} file(s) changed, "
            f"+{self.total_additions}/-{self.total_deletions} lines"
        )


def _find_repo(path: Optional[Path] = None) -> gitpython.Repo:
    """Find git repository starting from path."""
    search_path = path or Path.cwd()
    try:
        return gitpython.Repo(search_path, search_parent_directories=True)
    except InvalidGitRepositoryError:
        raise GitError(f"Not a git repository: {search_path}")


def _detect_base_branch(repo: gitpython.Repo) -> str:
    """Detect the base branch (main/master/develop)."""
    candidates = ["main", "master", "develop", "dev"]
    remote_refs = {ref.remote_head for ref in repo.remotes[0].refs} if repo.remotes else set()

    for candidate in candidates:
        # Check local branch
        if candidate in [b.name for b in repo.branches]:
            return candidate
        # Check remote branch
        if candidate in remote_refs:
            return f"origin/{candidate}"

    # Fallback: use HEAD~1 if only one branch
    return "HEAD~1"


def _parse_numstat(numstat_output: str, diff_map: dict[str, str]) -> list[FileDiff]:
    """Parse git diff --numstat output into FileDiff objects."""
    files = []
    for line in numstat_output.strip().splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        additions_str, deletions_str, path = parts
        # Binary files show '-'
        additions = int(additions_str) if additions_str != "-" else 0
        deletions = int(deletions_str) if deletions_str != "-" else 0

        # Determine status from path
        if " => " in path:
            status = "R"
            path = path.split(" => ")[-1].strip("{}")
        elif path in diff_map:
            status = diff_map[path]
        else:
            status = "M"

        files.append(
            FileDiff(
                path=path,
                status=status,
                additions=additions,
                deletions=deletions,
                diff_content=diff_map.get(path, ""),
            )
        )
    return files


def _get_file_statuses(repo: gitpython.Repo, base: str, head: str) -> dict[str, str]:
    """Get file status map (path -> status letter) between two refs."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", base, head],
            capture_output=True,
            text=True,
            cwd=repo.working_dir,
            check=True,
        )
        status_map = {}
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status_letter = parts[0][0]  # First char: A/M/D/R
                path = parts[1].split("\t")[-1]  # Handle renames
                status_map[path] = status_letter
        return status_map
    except subprocess.CalledProcessError:
        return {}


def _truncate_diff(diff_content: str, max_chars: int = 8000) -> str:
    """Truncate diff content to avoid overwhelming LLMs."""
    if len(diff_content) <= max_chars:
        return diff_content
    lines = diff_content.splitlines()
    result_lines = []
    total = 0
    for line in lines:
        if total + len(line) + 1 > max_chars:
            result_lines.append(f"\n... (truncated, {len(diff_content) - total} chars omitted)")
            break
        result_lines.append(line)
        total += len(line) + 1
    return "\n".join(result_lines)


def analyze_diff(
    repo_path: Optional[Path] = None,
    base_branch: Optional[str] = None,
    max_diff_chars: int = 12000,
) -> BranchDiff:
    """Analyze the diff between current branch and base branch.

    Args:
        repo_path: Path to git repo (defaults to cwd)
        base_branch: Base branch to diff against (auto-detected if None)
        max_diff_chars: Maximum characters for diff content

    Returns:
        BranchDiff with complete analysis
    """
    repo = _find_repo(repo_path)

    current_branch = repo.active_branch.name
    base = base_branch or _detect_base_branch(repo)

    # Get commit messages
    try:
        log_result = subprocess.run(
            ["git", "log", "--oneline", f"{base}..HEAD"],
            capture_output=True,
            text=True,
            cwd=repo.working_dir,
            check=True,
        )
        commits = [line.strip() for line in log_result.stdout.strip().splitlines() if line.strip()]
    except subprocess.CalledProcessError:
        commits = []

    # Get raw diff (truncated)
    try:
        raw_diff_result = subprocess.run(
            ["git", "diff", base, "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo.working_dir,
            check=True,
        )
        raw_diff = _truncate_diff(raw_diff_result.stdout, max_diff_chars)
    except subprocess.CalledProcessError:
        raw_diff = ""

    # Get numstat for additions/deletions per file
    try:
        numstat_result = subprocess.run(
            ["git", "diff", "--numstat", base, "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo.working_dir,
            check=True,
        )
        numstat_output = numstat_result.stdout
    except subprocess.CalledProcessError:
        numstat_output = ""

    # Get per-file diffs for context
    diff_map: dict[str, str] = {}
    if raw_diff:
        current_file = None
        current_lines: list[str] = []
        for line in raw_diff.splitlines():
            if line.startswith("diff --git"):
                if current_file and current_lines:
                    diff_map[current_file] = "\n".join(current_lines)
                # Extract filename: "diff --git a/foo b/foo"
                parts = line.split(" b/", 1)
                current_file = parts[1] if len(parts) > 1 else None
                current_lines = [line]
            elif current_file is not None:
                current_lines.append(line)
        if current_file and current_lines:
            diff_map[current_file] = "\n".join(current_lines)

    # Get file statuses
    status_map = _get_file_statuses(repo, base, "HEAD")
    # Merge status into diff_map keys
    full_diff_map = {**diff_map}
    for path, status in status_map.items():
        if path not in full_diff_map:
            full_diff_map[path] = ""

    files = _parse_numstat(numstat_output, {**status_map, **{k: status_map.get(k, "M") for k in diff_map}})

    # Update diff content in files
    files_with_diff = []
    for f in files:
        files_with_diff.append(
            FileDiff(
                path=f.path,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                diff_content=diff_map.get(f.path, ""),
            )
        )

    total_additions = sum(f.additions for f in files_with_diff)
    total_deletions = sum(f.deletions for f in files_with_diff)

    return BranchDiff(
        base_branch=base,
        current_branch=current_branch,
        commits=commits,
        files=files_with_diff,
        total_additions=total_additions,
        total_deletions=total_deletions,
        raw_diff=raw_diff,
    )
