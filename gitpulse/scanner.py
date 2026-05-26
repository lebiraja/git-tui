"""
scanner.py — Recursive Git repository discovery.

Walks a root directory tree and finds all folders containing a .git directory.
Skips common non-project directories for performance.
"""

import os
from pathlib import Path

# Directories to skip during recursive scanning
SKIP_DIRS = {
    # Python / JS build artifacts
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
    # macOS standard home-level directories — system/media data, never git repos
    "Library",
    "Applications",
    "Movies",
    "Music",
    "Pictures",
    "Public",
    # Windows standard home-level directories — system/media data, never git repos
    "AppData",        # like macOS Library: app caches, roaming profiles, local storage
    "Videos",         # standard media folder (macOS equivalent is Movies)
    # Linux common home-level directories — package runtimes, never git repos
    "snap",           # Ubuntu/Debian snap package mounts
}

# Maximum directory depth the walker will descend. Prevents unbounded recursion
# into deep trees (e.g. app containers, VM images, dataset archives).
MAX_DEPTH = 8


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
    _walk(str(root), repos, skip, 0)
    # No alphabetical sort here — the caller (_scan_worker) re-sorts by
    # commit timestamp, making a pre-sort wasted work.
    return repos


def _walk(directory: str, repos: list[Path], skip: set[str], depth: int) -> None:
    """
    Internal recursive walker.

    Uses os.scandir for speed — DirEntry.is_dir() reads the cached d_type
    from the readdir result, avoiding a separate stat() call per entry.

    Skips:
      - directories deeper than MAX_DEPTH
      - hidden directories (name starts with ".")
      - names in `skip`
      - OS-level mount points (detected via os.path.ismount)
      - any path that raises OSError when listed or stat'd
    """
    if depth > MAX_DEPTH:
        return

    try:
        with os.scandir(directory) as it:
            entries = list(it)
    except OSError:
        # Catches PermissionError, TimeoutError (FUSE/network mounts), and any
        # other OS-level failure — skip this branch silently.
        return

    # Check if this directory is a git repo using the cached DirEntry result
    for entry in entries:
        if entry.name == ".git":
            try:
                if entry.is_dir():
                    repos.append(Path(directory))
                    return  # Don't recurse into sub-repos
            except OSError:
                pass
            break

    for entry in sorted(entries, key=lambda e: e.name):
        if entry.name.startswith(".") or entry.name in skip:
            continue
        try:
            is_dir = entry.is_dir()
        except OSError:
            continue
        if not is_dir:
            continue
        if os.path.ismount(entry.path):
            continue
        _walk(entry.path, repos, skip, depth + 1)
