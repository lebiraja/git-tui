"""
cli.py — Command-line entry point for GitPulse.

Bare ``gitpulse`` launches the TUI. Subcommands provide non-interactive,
machine-readable surfaces:

    gitpulse scan --json        fleet state as a JSON document
    gitpulse scan --ndjson      one repo object per line
    gitpulse context            fleet state as a Markdown context pack
    gitpulse digest --since 7d  author activity digest

Textual is imported lazily, only when the TUI is actually launched, so the
non-interactive subcommands stay fast and importable in headless environments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as _config
from .utils import __version__

_TIME_SPEC_HELP = "1d, 7d, 2w, 4h, yesterday, today, or YYYY-MM-DD"

_MAIN_EPILOG = """\
examples:
  gitpulse                            launch the dashboard for the configured root
  gitpulse --root ~/Projects          launch the dashboard for a specific directory

  gitpulse scan --json                fleet state as JSON (for scripts and agents)
  gitpulse scan --json --ahead        only repos with unpushed commits
  gitpulse context                    fleet state as Markdown, for an LLM prompt
  gitpulse digest --since 7d          what you committed in the last week

dashboard keys:
  /  filter repos          j / k or arrows  move            [ ]  switch tab
  r  rescan                Space / *        select / all    :    bulk actions
  w  toggle watch mode     d  digest        b  stale branches
  e  error log             ?  help          q  quit

configuration:
  ~/.config/gitpulse/config.toml  — scan roots, excluded dirs, author emails,
  watch interval, stale threshold, worker count. CLI flags always win.
  An annotated example is written to config.toml.example on first run.

Full documentation: https://github.com/lebiraja/gitpulse
"""

_SCAN_EPILOG = """\
examples:
  gitpulse scan --json                       every repo, indented JSON
  gitpulse scan --json --indent 0            compact — fewer tokens for an agent
  gitpulse scan --json --dirty               only repos with uncommitted changes
  gitpulse scan --json --ahead               only repos with unpushed commits
  gitpulse scan --ndjson                     one JSON object per line
  gitpulse scan --root ~/work --json | jq '.repos[] | select(.behind > 0) | .name'

output:
  A JSON envelope with schema_version, scanned_at (ISO-8601 UTC), root,
  repo_count, repos[], and errors[]. Each repo carries name, path, branch,
  status, readable, modified_count, ahead, behind, stash_count,
  has_stale_branches, last_commit{ts,iso,message}, total_commits,
  contributor_count, and commit_activity[] (commits per week, 7 weeks).

  status is one of: clean, modified, untracked, unreadable.

  A repo with "readable": false could not be inspected — its state is unknown,
  NOT clean. Check the errors[] array too; if it is non-empty the picture is
  incomplete.

  Only JSON goes to stdout, so it is safe to pipe directly into a parser.
  Exit status is 0 even when repos are dirty; 1 means the scan itself failed.
"""

_CONTEXT_EPILOG = """\
examples:
  gitpulse context                     full fleet summary
  gitpulse context --max-repos 15      cap each section on a large fleet
  gitpulse context > /tmp/fleet.md     save it to paste into a prompt

output:
  Markdown ordered by what needs action: repos needing attention first, an
  unpushed-work table, stale branches, then clean repos collapsed to a single
  name list. Repos that could not be read are listed separately and explicitly
  marked as unknown rather than clean.

  Use this when a human will read the summary. Use `scan --json` when a program
  will parse it.
"""

_DIGEST_EPILOG = """\
examples:
  gitpulse digest --since 7d                     your commits this week
  gitpulse digest --since yesterday              since yesterday midnight
  gitpulse digest --since 2026-01-01             since a specific date
  gitpulse digest --author you@example.com       filter to one author
  gitpulse digest --author a@x.com --author b@x.com   several authors

output:
  Markdown grouped by repository, with per-commit insertion/deletion counts and
  a fleet-wide total. Answers "what did I do", where `context` answers "what is
  the state right now".

  With no --author, the digest uses author.emails from config.toml, falling back
  to each repository's own git config user.email.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitpulse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "GitPulse — a dashboard for every git repository on your machine.\n\n"
            "Scans a directory tree for local git repos and shows which have "
            "uncommitted\nchanges, unpushed commits, stashes, or stale branches. "
            "Run with no arguments\nfor the interactive dashboard, or use a "
            "subcommand for scriptable output."
        ),
        epilog=_MAIN_EPILOG,
    )
    parser.add_argument(
        "--version", action="version", version=f"gitpulse {__version__}"
    )

    def add_common(target: argparse.ArgumentParser) -> None:
        """Options every mode accepts, including the bare TUI invocation."""
        target.add_argument(
            "--root",
            type=str,
            default=None,
            help="Root directory to scan (default: config scan.roots, else cwd)",
        )
        target.add_argument(
            "--config",
            type=str,
            default=None,
            metavar="PATH",
            help="Path to config.toml (default: ~/.config/gitpulse/config.toml)",
        )
        target.add_argument(
            "--max-workers",
            type=int,
            default=None,
            metavar="N",
            help="Thread-pool ceiling for the scan (default: config bulk.max_workers)",
        )

    # Bare `gitpulse` accepts the common options plus the TUI-only ones.
    add_common(parser)
    tui_group = parser.add_argument_group(
        "dashboard options", "Only apply when launching the interactive TUI"
    )
    tui_group.add_argument(
        "--commits", type=int, default=10, metavar="N",
        help="Commits to show per repo in the Commits tab (default: 10)",
    )
    tui_group.add_argument(
        "--no-watch", action="store_true", default=False,
        help="Disable live auto-refresh when repos change on disk",
    )

    common = argparse.ArgumentParser(add_help=False)
    add_common(common)

    sub = parser.add_subparsers(
        dest="command",
        title="subcommands",
        metavar="{scan,context,digest}",
        description=(
            "Non-interactive output for scripts, pipelines, and coding agents.\n"
            "Run `gitpulse <subcommand> --help` for details and examples."
        ),
    )

    p_scan = sub.add_parser(
        "scan", parents=[common],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Print fleet state as JSON and exit",
        description=(
            "Scan the fleet and emit machine-readable state on stdout.\n\n"
            "This is the command for scripts and coding agents: it answers\n"
            "\"which of my repos have unpushed work?\" in a single call."
        ),
        epilog=_SCAN_EPILOG,
    )
    fmt = p_scan.add_mutually_exclusive_group()
    fmt.add_argument(
        "--json", action="store_true", default=False,
        help="Emit a single JSON document (default)",
    )
    fmt.add_argument(
        "--ndjson", action="store_true", default=False,
        help="Emit one JSON object per line",
    )
    p_scan.add_argument(
        "--dirty", action="store_true", default=False,
        help="Only repos with uncommitted changes",
    )
    p_scan.add_argument(
        "--ahead", action="store_true", default=False,
        help="Only repos with unpushed commits",
    )
    p_scan.add_argument(
        "--indent", type=int, default=2, metavar="N",
        help="JSON indentation; 0 for compact (default: 2)",
    )

    p_ctx = sub.add_parser(
        "context", parents=[common],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Print fleet state as a Markdown context pack",
        description=(
            "Render fleet state as Markdown sized for an LLM context window.\n\n"
            "State-first and ordered by what needs action, so it stays useful\n"
            "when pasted straight into a prompt or a standup note."
        ),
        epilog=_CONTEXT_EPILOG,
    )
    p_ctx.add_argument(
        "--max-repos", type=int, default=40, metavar="N",
        help="Cap rows listed per section (default: 40)",
    )

    p_dig = sub.add_parser(
        "digest", parents=[common],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Print an author activity digest as Markdown",
        description=(
            "Summarise recent commit activity by author across the fleet.\n\n"
            "Answers \"what did I do\"; use `context` for \"what is the state now\"."
        ),
        epilog=_DIGEST_EPILOG,
    )
    p_dig.add_argument(
        "--since", type=str, default=None, metavar="SPEC",
        help=f"Time window: {_TIME_SPEC_HELP} (default: config digest.default_window)",
    )
    p_dig.add_argument(
        "--author", action="append", dest="authors", metavar="EMAIL", default=None,
        help="Author email filter (repeatable; default: git config user.email)",
    )

    return parser


def _cmd_scan(args) -> int:
    from .api import fleet_to_dict, repo_to_dict, scan_fleet_detailed

    result = scan_fleet_detailed(root=args.root, max_workers=args.max_workers)

    repos = result.repos
    if args.dirty:
        repos = [r for r in repos if r.modified_count > 0]
    if args.ahead:
        repos = [r for r in repos if r.ahead > 0]
    result.repos = repos

    if args.ndjson:
        for repo in repos:
            sys.stdout.write(json.dumps(repo_to_dict(repo)) + "\n")
    else:
        indent = args.indent if args.indent > 0 else None
        sys.stdout.write(json.dumps(fleet_to_dict(result), indent=indent) + "\n")
    return 0


def _cmd_context(args) -> int:
    from .api import scan_fleet_detailed
    from .context import render_context

    result = scan_fleet_detailed(root=args.root, max_workers=args.max_workers)
    sys.stdout.write(render_context(result, max_repos=args.max_repos))
    return 0


def _cmd_digest(args) -> int:
    from .api import fleet_digest, scan_fleet
    from .digest import render_markdown

    cfg = _config.get()
    since = args.since or cfg.digest.default_window
    repos = scan_fleet(root=args.root, max_workers=args.max_workers)
    digest = fleet_digest(
        repos, since=since, authors=args.authors, max_workers=args.max_workers
    )
    sys.stdout.write(render_markdown(digest) + "\n")
    return 0


def _run_tui(args) -> int:
    # Imported here so the non-interactive subcommands never load Textual.
    from .main import GitPulseApp

    cfg = _config.get()
    if args.root is not None:
        root = Path(args.root).expanduser().resolve()
    elif cfg.scan.roots:
        root = Path(cfg.scan.roots[0]).expanduser().resolve()
    else:
        root = Path(".").resolve()

    if not root.is_dir():
        print(f"Error: '{root}' is not a valid directory.", file=sys.stderr)
        return 1

    watch_enabled = cfg.watch.enabled and not args.no_watch
    GitPulseApp(root_dir=root, commits=args.commits, watch=watch_enabled).run()
    return 0


def main() -> None:
    """Console-script entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    # Load config before anything reads scan roots or worker counts.
    if getattr(args, "config", None):
        _config.load(Path(args.config))

    handlers = {
        "scan": _cmd_scan,
        "context": _cmd_context,
        "digest": _cmd_digest,
    }
    handler = handlers.get(args.command)

    try:
        if handler is None:
            sys.exit(_run_tui(args))
        sys.exit(handler(args))
    except NotADirectoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        # Raised by parse_since on an unrecognised --since spec.
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        # Downstream closed the pipe (e.g. `gitpulse scan --json | head`).
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
