"""gpr CLI - AI-powered PR description generator."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax

from . import __version__
from .git import GitError, analyze_diff
from .prompt import SYSTEM_PROMPT, build_pr_prompt
from .providers import ProviderError, get_provider

console = Console()
err_console = Console(stderr=True)


def _print_error(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {msg}")


@click.command()
@click.version_option(version=__version__, prog_name="gpr")
@click.option(
    "--provider",
    "-p",
    default="claude",
    type=click.Choice(["claude", "openai", "ollama"]),
    show_default=True,
    help="AI provider to use.",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Model name (provider-specific). Defaults: claude=claude-haiku-4-5-20251001, openai=gpt-4o-mini, ollama=llama3.2",
)
@click.option(
    "--base",
    "-b",
    default=None,
    help="Base branch to diff against (auto-detected if not set).",
)
@click.option(
    "--style",
    "-s",
    default="standard",
    type=click.Choice(["standard", "conventional", "minimal"]),
    show_default=True,
    help="PR description style.",
)
@click.option(
    "--copy",
    "-c",
    is_flag=True,
    default=False,
    help="Copy output to clipboard.",
)
@click.option(
    "--gh",
    is_flag=True,
    default=False,
    help="Open 'gh pr create' with generated title and body.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Save output to file.",
)
@click.option(
    "--raw",
    is_flag=True,
    default=False,
    help="Print raw markdown without rich formatting.",
)
@click.option(
    "--diff-only",
    is_flag=True,
    default=False,
    help="Print the diff that would be sent to AI (for debugging).",
)
@click.option(
    "--ollama-host",
    default="http://localhost:11434",
    show_default=True,
    help="Ollama server URL (only for --provider ollama).",
)
@click.option(
    "--repo",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to git repository (defaults to current directory).",
)
def main(
    provider: str,
    model: Optional[str],
    base: Optional[str],
    style: str,
    copy: bool,
    gh: bool,
    output: Optional[Path],
    raw: bool,
    diff_only: bool,
    ollama_host: str,
    repo: Optional[Path],
) -> None:
    """Generate AI-powered pull request descriptions from your git diff.

    \b
    Examples:
      gpr                          # Generate PR description (Claude)
      gpr --provider ollama        # Use local Ollama (no API key)
      gpr --provider openai        # Use OpenAI GPT-4o-mini
      gpr --style conventional     # Use conventional commits format
      gpr --copy                   # Copy to clipboard
      gpr --gh                     # Open gh pr create
      gpr --base develop           # Diff against develop branch
    """
    # Analyze git diff
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[dim]Analyzing git diff...[/dim]"),
            console=err_console,
            transient=True,
        ) as progress:
            progress.add_task("", total=None)
            diff = analyze_diff(repo_path=repo, base_branch=base)
    except GitError as e:
        _print_error(str(e))
        sys.exit(1)

    if diff.is_empty:
        err_console.print("[yellow]No changes detected between current branch and base.[/yellow]")
        sys.exit(0)

    # Show diff summary
    err_console.print(
        f"[dim]Branch:[/dim] [bold]{diff.current_branch}[/bold] → "
        f"[dim]{diff.base_branch}[/dim]  "
        f"[dim]{diff.summary}[/dim]"
    )

    # Debug mode: print diff
    if diff_only:
        syntax = Syntax(diff.raw_diff, "diff", theme="monokai", line_numbers=False)
        console.print(syntax)
        return

    # Build prompt
    user_prompt = build_pr_prompt(diff, style=style)

    # Initialize provider
    try:
        provider_kwargs = {}
        if model:
            provider_kwargs["model"] = model
        if provider == "ollama":
            provider_kwargs["host"] = ollama_host
        ai = get_provider(provider, **provider_kwargs)
    except ProviderError as e:
        _print_error(str(e))
        sys.exit(1)

    # Generate PR description
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[dim]Generating with {ai.name}...[/dim]"),
            console=err_console,
            transient=True,
        ) as progress:
            progress.add_task("", total=None)
            result = ai.generate(SYSTEM_PROMPT, user_prompt)
    except ProviderError as e:
        _print_error(str(e))
        sys.exit(1)

    # Output
    if raw or not sys.stdout.isatty():
        click.echo(result)
    else:
        console.print()
        console.print(Panel(Markdown(result), title="[bold green]PR Description[/bold green]", border_style="green"))
        console.print()

    # Save to file
    if output:
        output.write_text(result, encoding="utf-8")
        err_console.print(f"[green]✓[/green] Saved to [bold]{output}[/bold]")

    # Copy to clipboard
    if copy:
        try:
            import pyperclip
            pyperclip.copy(result)
            err_console.print("[green]✓[/green] Copied to clipboard")
        except Exception as e:
            err_console.print(f"[yellow]Warning:[/yellow] Could not copy to clipboard: {e}")

    # Open gh pr create
    if gh:
        _open_gh_pr_create(result)


def _open_gh_pr_create(description: str) -> None:
    """Parse title from description and open gh pr create."""
    import subprocess

    # Extract title from markdown
    title = ""
    for line in description.splitlines():
        if line.startswith("**Title:**"):
            title = line.replace("**Title:**", "").strip()
            break

    if not title:
        # Fallback: use first non-empty line
        for line in description.splitlines():
            line = line.strip("#• -*").strip()
            if line:
                title = line[:72]
                break

    # Remove title line from body
    body_lines = []
    skip_next = False
    for line in description.splitlines():
        if line.startswith("**Title:**"):
            skip_next = True
            continue
        if skip_next and not line.strip():
            skip_next = False
            continue
        skip_next = False
        body_lines.append(line)
    body = "\n".join(body_lines).strip()

    err_console = Console(stderr=True)
    err_console.print(f"\n[dim]Running:[/dim] gh pr create --title [bold]\"{title}\"[/bold] --body ...")

    try:
        subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", body],
            check=False,
        )
    except FileNotFoundError:
        err_console.print(
            "[yellow]Warning:[/yellow] 'gh' CLI not found. "
            "Install it from https://cli.github.com/"
        )
