"""Prompt templates for PR generation."""

from __future__ import annotations

from .git import BranchDiff


SYSTEM_PROMPT = """You are an expert software engineer who writes clear, concise pull request descriptions.
Your PR descriptions help reviewers understand what changed, why it changed, and how to test it.
Always be specific and technical. Avoid vague language like "various improvements" or "some fixes"."""


def build_pr_prompt(diff: BranchDiff, style: str = "standard") -> str:
    """Build the prompt for PR generation.

    Args:
        diff: The branch diff to describe
        style: Output style ('standard', 'conventional', 'minimal')

    Returns:
        Formatted prompt string
    """
    commits_section = ""
    if diff.commits:
        commits_section = "## Commit Messages\n" + "\n".join(f"- {c}" for c in diff.commits)

    files_section = "## Changed Files\n"
    status_labels = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}
    for f in diff.files:
        status = status_labels.get(f.status, "changed")
        files_section += f"- `{f.path}` ({status}, +{f.additions}/-{f.deletions})\n"

    diff_section = ""
    if diff.raw_diff:
        diff_section = f"## Diff\n```diff\n{diff.raw_diff}\n```"

    format_instructions = _get_format_instructions(style)

    return f"""Analyze the following git changes and write a pull request description.

Branch: `{diff.current_branch}` → `{diff.base_branch}`
Changes: {diff.summary}

{commits_section}

{files_section}

{diff_section}

{format_instructions}"""


def _get_format_instructions(style: str) -> str:
    if style == "minimal":
        return """Write a brief PR description with:
1. A one-line title (max 72 chars, imperative mood)
2. 2-3 bullet points explaining what changed

Format:
**Title:** <title>

**Description:**
- <change 1>
- <change 2>
- <change 3>"""

    elif style == "conventional":
        return """Write a PR description following Conventional Commits style:

**Title:** <type>(<scope>): <description>
Types: feat, fix, refactor, docs, test, chore, perf

**What changed:**
<specific technical changes>

**Why:**
<motivation and context>

**Breaking changes:** (if any, otherwise omit)
<breaking changes>

**Test plan:**
- [ ] <test step 1>
- [ ] <test step 2>"""

    else:  # standard
        return """Write a comprehensive PR description with this exact format:

**Title:** <concise title in imperative mood, max 72 chars>

## Summary
<2-3 sentences explaining what this PR does and why>

## Changes
<bullet points of specific changes, be technical and precise>

## Test Plan
- [ ] <how to test change 1>
- [ ] <how to test change 2>

## Notes (optional)
<any reviewer notes, migration steps, or caveats>"""
