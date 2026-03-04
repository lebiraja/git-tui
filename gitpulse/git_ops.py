"""
git_ops.py — Git operations for GitPulse.

Provides data classes and helper functions to query repository status,
recent commits, diffs, branches, stashes, remotes, tags, and to switch
branches. Uses GitPython for interfacing with local git repositories.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from git import Repo, InvalidGitRepositoryError, GitCommandError


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class RepoStatus(enum.Enum):
    """High-level status of a repository's working tree."""
    CLEAN = "CLEAN"
    MODIFIED = "MODIFIED"
    UNTRACKED = "UNTRACKED"


@dataclass
class RepoInfo:
    """Summary information for a single git repository."""
    name: str
    path: Path
    branch: str
    status: RepoStatus
    last_commit_ts: float = 0.0        # Unix timestamp of most recent commit
    last_commit_msg: str = ""           # First line of most recent commit message
    modified_count: int = 0             # Number of modified + staged + untracked files
    total_commits: int = 0              # Total commit count on current branch
    contributor_count: int = 0          # Unique author count


@dataclass
class FileStatus:
    """Categorised lists of files returned by `git status`."""
    staged: list[str] = field(default_factory=list)
    unstaged: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)


@dataclass
class CommitInfo:
    """A single commit entry."""
    short_hash: str
    author: str
    date: str
    message: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


@dataclass
class BranchInfo:
    """Information about a local branch."""
    name: str
    is_current: bool


@dataclass
class StashEntry:
    """A single stash entry."""
    index: int
    message: str


@dataclass
class RemoteInfo:
    """Information about a git remote."""
    name: str
    url: str
    ahead: int = 0
    behind: int = 0


@dataclass
class TagInfo:
    """Information about a git tag."""
    name: str
    date: str
    message: str
    tagger: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_repo(path: Path) -> Repo:
    """Open a git.Repo, raising on failure."""
    return Repo(str(path))


def _determine_status(repo: Repo) -> tuple[RepoStatus, int]:
    """Determine the high-level status of a repository and file count."""
    try:
        staged = list(repo.index.diff("HEAD"))
    except Exception:
        staged = []
    unstaged = list(repo.index.diff(None))
    untracked = repo.untracked_files
    count = len(staged) + len(unstaged) + len(untracked)

    if staged or unstaged:
        return RepoStatus.MODIFIED, count
    elif untracked:
        return RepoStatus.UNTRACKED, count
    return RepoStatus.CLEAN, 0


def relative_time(ts: float) -> str:
    """Convert a Unix timestamp to a human-readable relative time string."""
    if ts == 0:
        return "never"
    now = datetime.now(timezone.utc).timestamp()
    diff = now - ts
    if diff < 60:
        return "just now"
    elif diff < 3600:
        m = int(diff // 60)
        return f"{m}m ago"
    elif diff < 86400:
        h = int(diff // 3600)
        return f"{h}h ago"
    elif diff < 604800:
        d = int(diff // 86400)
        return f"{d}d ago"
    elif diff < 2592000:
        w = int(diff // 604800)
        return f"{w}w ago"
    elif diff < 31536000:
        mo = int(diff // 2592000)
        return f"{mo}mo ago"
    else:
        y = int(diff // 31536000)
        return f"{y}y ago"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_repo_info(path: Path) -> RepoInfo:
    """
    Return a RepoInfo summary for the repository at `path`.

    Includes last commit timestamp for sorting, file counts, and summary stats.
    """
    try:
        repo = _open_repo(path)
        branch = repo.active_branch.name if not repo.head.is_detached else "(detached)"
        status, mod_count = _determine_status(repo)

        # Last commit info
        last_ts = 0.0
        last_msg = ""
        total = 0
        contributors = set()
        try:
            head_commit = repo.head.commit
            last_ts = float(head_commit.committed_date)
            last_msg = head_commit.message.strip().split("\n")[0]

            # Count total commits and contributors (capped for speed)
            for i, c in enumerate(repo.iter_commits()):
                total += 1
                contributors.add(str(c.author))
                if i >= 500:  # Cap traversal for perf
                    break
        except Exception:
            pass

    except (InvalidGitRepositoryError, Exception):
        branch = "unknown"
        status = RepoStatus.CLEAN
        mod_count = 0
        last_ts = 0.0
        last_msg = ""
        total = 0
        contributors = set()

    return RepoInfo(
        name=path.name,
        path=path,
        branch=branch,
        status=status,
        last_commit_ts=last_ts,
        last_commit_msg=last_msg,
        modified_count=mod_count,
        total_commits=total,
        contributor_count=len(contributors),
    )


def get_status(path: Path) -> FileStatus:
    """
    Return categorised file lists (staged, unstaged, untracked) for a repo.
    """
    repo = _open_repo(path)
    fs = FileStatus()

    # Staged (index vs HEAD)
    try:
        diffs_staged = repo.index.diff("HEAD")
        fs.staged = [d.a_path or d.b_path for d in diffs_staged]
    except Exception:
        fs.staged = []

    # Unstaged (working tree vs index)
    diffs_unstaged = repo.index.diff(None)
    fs.unstaged = [d.a_path or d.b_path for d in diffs_unstaged]

    # Untracked
    fs.untracked = repo.untracked_files

    return fs


def get_commits(path: Path, n: int = 10) -> list[CommitInfo]:
    """
    Return the last `n` commits from the current branch, including diff stats.
    """
    repo = _open_repo(path)
    commits: list[CommitInfo] = []

    try:
        for commit in repo.iter_commits(max_count=n):
            # Get diffstat for each commit
            files_changed = 0
            insertions = 0
            deletions = 0
            try:
                stats = commit.stats.total
                files_changed = stats.get("files", 0)
                insertions = stats.get("insertions", 0)
                deletions = stats.get("deletions", 0)
            except Exception:
                pass

            commits.append(
                CommitInfo(
                    short_hash=commit.hexsha[:7],
                    author=str(commit.author),
                    date=datetime.fromtimestamp(commit.committed_date).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    message=commit.message.strip().split("\n")[0],
                    files_changed=files_changed,
                    insertions=insertions,
                    deletions=deletions,
                )
            )
    except Exception:
        pass

    return commits


def get_diff(path: Path) -> str:
    """
    Return the uncommitted diff (working tree vs index) as a string.
    """
    repo = _open_repo(path)

    try:
        diff_text = repo.git.diff()
        if not diff_text:
            staged_diff = repo.git.diff("--cached")
            if staged_diff:
                return staged_diff
            return "No uncommitted changes."
        return diff_text
    except Exception as exc:
        return f"Error getting diff: {exc}"


def get_branches(path: Path) -> list[BranchInfo]:
    """
    Return a list of all local branches, indicating which is current.
    """
    repo = _open_repo(path)
    branches: list[BranchInfo] = []

    try:
        current = repo.active_branch.name if not repo.head.is_detached else None
    except Exception:
        current = None

    for branch in repo.branches:
        branches.append(
            BranchInfo(name=branch.name, is_current=(branch.name == current))
        )

    return branches


def switch_branch(path: Path, branch_name: str) -> str:
    """
    Checkout a different branch.
    """
    repo = _open_repo(path)
    try:
        repo.git.checkout(branch_name)
        return f"Switched to branch '{branch_name}'"
    except GitCommandError as exc:
        return f"Error switching branch: {exc}"


def get_stashes(path: Path) -> list[StashEntry]:
    """
    Return a list of stash entries for the repo.
    """
    repo = _open_repo(path)
    stashes: list[StashEntry] = []
    try:
        stash_output = repo.git.stash("list")
        if stash_output.strip():
            for line in stash_output.strip().split("\n"):
                # Format: stash@{0}: WIP on main: abc1234 commit message
                parts = line.split(":", 1)
                idx_str = parts[0].strip()
                msg = parts[1].strip() if len(parts) > 1 else ""
                # Extract index number
                try:
                    idx = int(idx_str.split("{")[1].rstrip("}"))
                except (IndexError, ValueError):
                    idx = 0
                stashes.append(StashEntry(index=idx, message=msg))
    except Exception:
        pass
    return stashes


def get_remotes(path: Path) -> list[RemoteInfo]:
    """
    Return remote info including ahead/behind counts relative to tracking branch.
    """
    repo = _open_repo(path)
    remotes: list[RemoteInfo] = []

    for remote in repo.remotes:
        url = ""
        try:
            url = remote.url
        except Exception:
            pass

        ahead = 0
        behind = 0
        try:
            # Get ahead/behind for current branch vs remote tracking branch
            branch = repo.active_branch
            tracking = branch.tracking_branch()
            if tracking:
                rev_range_ahead = f"{tracking.name}..{branch.name}"
                rev_range_behind = f"{branch.name}..{tracking.name}"
                ahead = len(list(repo.iter_commits(rev_range_ahead)))
                behind = len(list(repo.iter_commits(rev_range_behind)))
        except Exception:
            pass

        remotes.append(RemoteInfo(
            name=remote.name,
            url=url,
            ahead=ahead,
            behind=behind,
        ))

    return remotes


def get_tags(path: Path, n: int = 15) -> list[TagInfo]:
    """
    Return the most recent `n` tags, sorted by date descending.
    """
    repo = _open_repo(path)
    tags: list[TagInfo] = []

    try:
        for tag_ref in repo.tags:
            try:
                # Annotated tag
                tag_obj = tag_ref.tag
                if tag_obj:
                    ts = tag_obj.tagged_date
                    date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    message = (tag_obj.message or "").strip().split("\n")[0]
                    tagger = str(tag_obj.tagger) if tag_obj.tagger else ""
                else:
                    # Lightweight tag — use commit date
                    commit = tag_ref.commit
                    ts = commit.committed_date
                    date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    message = commit.message.strip().split("\n")[0]
                    tagger = str(commit.author)

                tags.append(TagInfo(
                    name=tag_ref.name,
                    date=date_str,
                    message=message,
                    tagger=tagger,
                ))
            except Exception:
                tags.append(TagInfo(name=tag_ref.name, date="", message="", tagger=""))
    except Exception:
        pass

    # Sort by date descending, take first n
    tags.sort(key=lambda t: t.date, reverse=True)
    return tags[:n]
