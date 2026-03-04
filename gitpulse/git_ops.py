"""
git_ops.py — Git operations for GitPulse.

Provides data classes and helper functions to query repository status,
recent commits, diffs, branches, and to switch branches.
Uses GitPython for interfacing with local git repositories.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
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


@dataclass
class BranchInfo:
    """Information about a local branch."""
    name: str
    is_current: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_repo(path: Path) -> Repo:
    """Open a git.Repo, raising on failure."""
    return Repo(str(path))


def _determine_status(repo: Repo) -> RepoStatus:
    """Determine the high-level status of a repository."""
    if repo.is_dirty(untracked_files=True):
        # Check if there are only untracked files (no modifications)
        if not repo.is_dirty(untracked_files=False):
            return RepoStatus.UNTRACKED
        return RepoStatus.MODIFIED
    return RepoStatus.CLEAN


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_repo_info(path: Path) -> RepoInfo:
    """
    Return a RepoInfo summary for the repository at `path`.

    Args:
        path: Absolute path to the repository root.

    Returns:
        A RepoInfo dataclass instance.
    """
    try:
        repo = _open_repo(path)
        branch = repo.active_branch.name if not repo.head.is_detached else "(detached)"
        status = _determine_status(repo)
    except (InvalidGitRepositoryError, Exception):
        branch = "unknown"
        status = RepoStatus.CLEAN

    return RepoInfo(
        name=path.name,
        path=path,
        branch=branch,
        status=status,
    )


def get_status(path: Path) -> FileStatus:
    """
    Return categorised file lists (staged, unstaged, untracked) for a repo.

    Args:
        path: Absolute path to the repository root.

    Returns:
        A FileStatus dataclass instance.
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
    Return the last `n` commits from the current branch.

    Args:
        path: Absolute path to the repository root.
        n:    Number of commits to retrieve.

    Returns:
        A list of CommitInfo dataclass instances (most recent first).
    """
    repo = _open_repo(path)
    commits: list[CommitInfo] = []

    try:
        for commit in repo.iter_commits(max_count=n):
            commits.append(
                CommitInfo(
                    short_hash=commit.hexsha[:7],
                    author=str(commit.author),
                    date=datetime.fromtimestamp(commit.committed_date).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    message=commit.message.strip().split("\n")[0],
                )
            )
    except Exception:
        pass

    return commits


def get_diff(path: Path) -> str:
    """
    Return the uncommitted diff (working tree vs index) as a string.

    Args:
        path: Absolute path to the repository root.

    Returns:
        The diff text, or an informational message if there is no diff.
    """
    repo = _open_repo(path)

    try:
        diff_text = repo.git.diff()
        if not diff_text:
            # Also check staged diff
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

    Args:
        path: Absolute path to the repository root.

    Returns:
        A list of BranchInfo dataclass instances.
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

    Args:
        path:        Absolute path to the repository root.
        branch_name: Name of the branch to switch to.

    Returns:
        A status message indicating success or failure.
    """
    repo = _open_repo(path)
    try:
        repo.git.checkout(branch_name)
        return f"Switched to branch '{branch_name}'"
    except GitCommandError as exc:
        return f"Error switching branch: {exc}"
