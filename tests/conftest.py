"""Shared fixtures — real git repositories on disk, no mocking."""

from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo


def _init(path: Path) -> Repo:
    """Initialise a repo with a deterministic identity and one commit."""
    repo = Repo.init(path, initial_branch="main")
    with repo.config_writer() as cw:
        cw.set_value("user", "email", "test@example.com")
        cw.set_value("user", "name", "Test User")
        cw.set_value("commit", "gpgsign", "false")
    (path / "README.md").write_text("# test\n")
    repo.index.add(["README.md"])
    repo.index.commit("initial commit")
    return repo


@pytest.fixture
def repo_path(tmp_path) -> Path:
    """A clean git repo containing a single commit."""
    path = tmp_path / "solo"
    path.mkdir()
    _init(path)
    return path


@pytest.fixture
def repo(repo_path) -> Repo:
    """The GitPython handle for :func:`repo_path`."""
    return Repo(repo_path)


@pytest.fixture
def remote_repo(tmp_path) -> Path:
    """A bare repo usable as a push target — no network required."""
    bare = tmp_path / "origin.git"
    Repo.init(bare, bare=True)
    return bare


@pytest.fixture
def fleet(tmp_path) -> Path:
    """A root directory containing three repos in differing states.

    - ``clean``     — nothing outstanding
    - ``dirty``     — one untracked file
    - ``committed`` — one extra commit, staged file removed
    """
    root = tmp_path / "fleet"
    root.mkdir()

    clean = root / "clean"
    clean.mkdir()
    _init(clean)

    dirty = root / "dirty"
    dirty.mkdir()
    _init(dirty)
    (dirty / "scratch.txt").write_text("uncommitted\n")

    committed = root / "committed"
    committed.mkdir()
    r = _init(committed)
    (committed / "second.txt").write_text("more\n")
    r.index.add(["second.txt"])
    r.index.commit("second commit")

    return root
