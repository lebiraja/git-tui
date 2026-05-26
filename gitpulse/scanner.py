"""
scanner.py — Recursive Git repository discovery.

Walks a root directory tree and finds all folders containing a .git directory.
Skips common non-project directories for performance.
"""

import os
from pathlib import Path

# Directories to skip during recursive scanning
SKIP_DIRS = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
    "site-packages",
    # Cloud-sync / network-volume directories (belt-and-suspenders for clients
    # that do not expose a real OS mount point, so os.path.ismount() misses them)
    "Google Drive",
    "Dropbox",
    "OneDrive",
    "Box",
    "iCloud Drive",
}


def scan_repos(root: Path, extra_skip: set[str] | None = None) -> list[Path]:
    """
    Recursively scan `root` for directories that contain a .git folder.

    Returns a list of absolute paths to discovered repositories.
    Once a .git directory is found inside a folder, we do NOT recurse deeper
    into that folder (avoids picking up submodules or nested repos).

    Network-mounted paths (detected via os.path.ismount) and directories whose
    names appear in SKIP_DIRS (or extra_skip) are skipped silently. Any OSError
    raised during traversal (including TimeoutError on unresponsive FUSE mounts)
    is caught and treated as a skip.

    Args:
        root: The top-level directory to begin scanning from.
        extra_skip: Optional set of additional directory names to skip,
            merged with SKIP_DIRS. Pass None to use only SKIP_DIRS.

    Returns:
        A list of Path objects pointing to each discovered repo root.
    """
    root = root.expanduser().resolve()
    if not root.is_dir():
        return []

    skip = SKIP_DIRS | extra_skip if extra_skip else SKIP_DIRS
    repos: list[Path] = []
    _walk(root, repos, skip)
    # No alphabetical sort here — the caller (_scan_worker) re-sorts by
    # commit timestamp, making a pre-sort wasted work.
    return repos


def _walk(directory: Path, repos: list[Path], skip: set[str]) -> None:
    """
    Internal recursive walker.

    If `directory` itself contains a .git folder, add it to `repos`
    and stop recursing deeper. Otherwise, iterate children, skipping:
      - hidden directories (name starts with ".")
      - names in `skip`
      - OS-level mount points (detected via os.path.ismount)
      - any path that raises OSError when stat'd or listed
    """
    try:
        children = sorted(directory.iterdir())
    except OSError:
        # Catches PermissionError, TimeoutError (FUSE/network mounts), and any
        # other OS-level failure — skip this branch silently.
        return

    # Check if this directory is a git repo
    if (directory / ".git").is_dir():
        repos.append(directory)
        return  # Don't recurse into sub-repos

    for child in children:
        if child.name.startswith(".") or child.name in skip:
            continue
        try:
            is_dir = child.is_dir()
        except OSError:
            continue
        if not is_dir:
            continue
        if os.path.ismount(str(child)):
            continue
        _walk(child, repos, skip)
