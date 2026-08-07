"""
api.py — Public, UI-free library surface for GitPulse.

This module is the supported entry point for programmatic consumers (agent
frameworks, scripts, an MCP server). It deliberately imports nothing from
``gitpulse.ui`` and never pulls in Textual, so it can be imported into a
non-TUI process cheaply.

    from gitpulse.api import scan_fleet, fleet_to_dict

    fleet = scan_fleet("~/Projects")
    unpushed = [r for r in fleet if r.ahead > 0]

Everything here is read-only. Mutating operations stay in ``git_ops`` and are
not re-exported: fanning a write across an entire fleet from a script is a
different risk profile than doing it behind a confirmation modal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import config as _config
from .digest import Digest, build_digest
from .git_ops import RepoInfo, RepoStatus, classify_error, get_repo_info
from .parallel import run_parallel
from .scanner import scan_repos
from .utils import parse_since

# Bump when the emitted dict shape changes incompatibly. Consumers parse this.
SCHEMA_VERSION = 1

__all__ = [
    "SCHEMA_VERSION",
    "ScanResult",
    "is_unreadable",
    "scan_fleet",
    "scan_fleet_detailed",
    "repo_state",
    "fleet_to_dict",
    "repo_to_dict",
    "fleet_digest",
]


class ScanResult:
    """Outcome of a fleet scan: the repos that resolved, plus per-path errors.

    Errors are carried alongside the results rather than raised, so a single
    unreadable directory cannot mask an otherwise complete scan.
    """

    def __init__(
        self,
        root: Path,
        repos: list[RepoInfo],
        errors: list[tuple[Path, str]],
    ) -> None:
        self.root = root
        self.repos = repos
        self.errors = errors
        self.scanned_at = datetime.now(timezone.utc)

    def __iter__(self):
        return iter(self.repos)

    def __len__(self) -> int:
        return len(self.repos)


def _resolve_root(root: str | Path | None) -> Path:
    """Expand *root*, falling back to configured scan roots then the cwd."""
    if root is not None:
        return Path(root).expanduser().resolve()
    cfg = _config.get()
    if cfg.scan.roots:
        return Path(cfg.scan.roots[0]).expanduser().resolve()
    return Path(".").resolve()


def scan_fleet_detailed(
    root: str | Path | None = None,
    max_workers: int | None = None,
) -> ScanResult:
    """Discover and enrich every git repo under *root*.

    Args:
        root: Directory to scan. Defaults to the first configured scan root,
            then the current directory.
        max_workers: Thread-pool ceiling. Defaults to the configured
            ``bulk.max_workers``.

    Returns:
        A :class:`ScanResult` with the resolved repos and any per-path errors.
    """
    resolved = _resolve_root(root)
    if not resolved.is_dir():
        raise NotADirectoryError(f"{resolved} is not a directory")

    cfg = _config.get()
    workers = max_workers if max_workers is not None else cfg.bulk.max_workers
    extra_skip = set(cfg.scan.exclude_dirs) if cfg.scan.exclude_dirs else None

    paths = scan_repos(resolved, extra_skip=extra_skip)
    results = run_parallel(get_repo_info, paths, max_workers=workers)

    repos: list[RepoInfo] = []
    errors: list[tuple[Path, str]] = []
    for path, result in results:
        if isinstance(result, Exception):
            _, detail = classify_error(result)
            errors.append((path, detail))
        else:
            repos.append(result)

    repos.sort(key=lambda r: r.last_commit_ts, reverse=True)
    return ScanResult(root=resolved, repos=repos, errors=errors)


def scan_fleet(
    root: str | Path | None = None,
    max_workers: int | None = None,
) -> list[RepoInfo]:
    """Return every git repo under *root*, most recently active first."""
    return scan_fleet_detailed(root=root, max_workers=max_workers).repos


def repo_state(path: str | Path) -> RepoInfo:
    """Return the current :class:`RepoInfo` for a single repository."""
    return get_repo_info(Path(path).expanduser().resolve())


def _iso(ts: float) -> str | None:
    """Format a Unix timestamp as ISO-8601 UTC, or None if unset."""
    if not ts:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def is_unreadable(info: RepoInfo) -> bool:
    """True if ``get_repo_info`` fell back to placeholder values.

    ``get_repo_info`` catches its own errors and returns a default RepoInfo
    with ``branch="unknown"`` and no history rather than raising. Left
    unflagged that shape is indistinguishable from a genuinely clean repo,
    which would tell a consumer there is nothing to do.
    """
    return info.branch == "unknown" and info.last_commit_ts == 0.0


def repo_to_dict(info: RepoInfo) -> dict:
    """Serialize a :class:`RepoInfo` into a JSON-safe dict.

    ``status`` is emitted as a stable lowercase string ("clean", "modified",
    "untracked") rather than the enum repr — those strings are part of the
    documented schema. Repos that could not be read are marked
    ``"status": "unreadable"`` so they are never mistaken for clean.
    """
    unreadable = is_unreadable(info)
    return {
        "name": info.name,
        "path": str(info.path),
        "branch": info.branch,
        "status": "unreadable" if unreadable else info.status.value.lower(),
        "readable": not unreadable,
        "modified_count": info.modified_count,
        "ahead": info.ahead,
        "behind": info.behind,
        "stash_count": info.stash_count,
        "has_stale_branches": info.has_stale_branches,
        "last_commit": {
            "ts": info.last_commit_ts,
            "iso": _iso(info.last_commit_ts),
            "message": info.last_commit_msg,
        },
        "total_commits": info.total_commits,
        "contributor_count": info.contributor_count,
        "commit_activity": list(info.commit_activity),
    }


def fleet_to_dict(result: ScanResult) -> dict:
    """Serialize a :class:`ScanResult` into the documented JSON envelope."""
    return {
        "schema_version": SCHEMA_VERSION,
        "scanned_at": result.scanned_at.isoformat(),
        "root": str(result.root),
        "repo_count": len(result.repos),
        "repos": [repo_to_dict(r) for r in result.repos],
        "errors": [{"path": str(p), "error": e} for p, e in result.errors],
    }


def fleet_digest(
    repos: Iterable[RepoInfo],
    since: str = "1d",
    authors: list[str] | None = None,
    max_workers: int | None = None,
) -> Digest:
    """Build an author-activity digest across *repos*.

    Args:
        repos: Repositories to include, e.g. the output of :func:`scan_fleet`.
        since: Time window spec ("1d", "7d", "yesterday", "YYYY-MM-DD").
        authors: Author email patterns. Defaults to the configured authors,
            then the repo's own ``user.email``.
        max_workers: Thread-pool ceiling.
    """
    cfg = _config.get()
    workers = max_workers if max_workers is not None else cfg.bulk.max_workers
    patterns = authors if authors is not None else (cfg.author.emails or [])
    return build_digest(
        list(repos), parse_since(since), patterns, max_workers=workers
    )


# Kept importable for consumers that want the status vocabulary without
# reaching into git_ops directly.
STATUS_VALUES = tuple(s.value.lower() for s in RepoStatus) + ("unreadable",)
