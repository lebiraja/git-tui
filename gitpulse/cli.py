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

_TIME_SPEC_HELP = "1d, 7d, 30d, yesterday, today, or YYYY-MM-DD"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitpulse",
        description="GitPulse — Git repo fleet dashboard. Run without arguments for the TUI.",
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
    parser.add_argument(
        "--commits", type=int, default=10, metavar="N",
        help="Commits to display per repo in the TUI (default: 10)",
    )
    parser.add_argument(
        "--no-watch", action="store_true", default=False,
        help="Disable live watch mode",
    )

    common = argparse.ArgumentParser(add_help=False)
    add_common(common)

    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser(
        "scan", parents=[common],
        help="Print fleet state as JSON and exit",
        description="Scan the fleet and emit machine-readable state on stdout.",
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
        help="Print fleet state as a Markdown context pack",
        description="Render fleet state as Markdown sized for an LLM context window.",
    )
    p_ctx.add_argument(
        "--max-repos", type=int, default=40, metavar="N",
        help="Cap rows listed per section (default: 40)",
    )

    p_dig = sub.add_parser(
        "digest", parents=[common],
        help="Print an author activity digest as Markdown",
        description="Summarise recent commit activity by author across the fleet.",
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
