"""
Coverage for the mutating half of git_ops — the operations the TUI can fan out
across an entire fleet at once, and which previously had no direct tests.

Every test runs against a real repository on disk; git_push targets a local
bare repo so the code path is exercised without touching the network.
"""

from __future__ import annotations

import pytest
from git import Repo

from gitpulse.git_ops import (
    RepoStatus,
    commit_changes,
    create_branch,
    delete_branch,
    get_branches,
    get_repo_info,
    get_status,
    git_push,
    is_dirty,
    stage_all,
    stage_files,
    stash_create,
    stash_pop,
    unstage_all,
    unstage_files,
)


class TestStaging:
    def test_stage_files_moves_file_to_staged(self, repo_path):
        # Arrange
        (repo_path / "new.txt").write_text("hello\n")

        # Act
        stage_files(repo_path, ["new.txt"])

        # Assert
        status = get_status(repo_path)
        assert "new.txt" in status.staged
        assert "new.txt" not in status.untracked

    def test_unstage_files_returns_file_to_untracked(self, repo_path):
        # Arrange
        (repo_path / "new.txt").write_text("hello\n")
        stage_files(repo_path, ["new.txt"])

        # Act
        unstage_files(repo_path, ["new.txt"])

        # Assert
        status = get_status(repo_path)
        assert "new.txt" not in status.staged

    def test_stage_all_stages_every_change(self, repo_path):
        # Arrange
        (repo_path / "a.txt").write_text("a\n")
        (repo_path / "b.txt").write_text("b\n")

        # Act
        stage_all(repo_path)

        # Assert
        status = get_status(repo_path)
        assert {"a.txt", "b.txt"} <= set(status.staged)

    def test_unstage_all_clears_the_index(self, repo_path):
        # Arrange
        (repo_path / "a.txt").write_text("a\n")
        stage_all(repo_path)

        # Act
        unstage_all(repo_path)

        # Assert
        assert get_status(repo_path).staged == []


class TestCommit:
    def test_commit_changes_creates_a_commit(self, repo_path, repo):
        # Arrange
        before = len(list(repo.iter_commits()))
        (repo_path / "feature.txt").write_text("work\n")
        stage_all(repo_path)

        # Act
        commit_changes(repo_path, "add feature")

        # Assert
        commits = list(Repo(repo_path).iter_commits())
        assert len(commits) == before + 1
        assert commits[0].message.strip() == "add feature"

    def test_commit_changes_leaves_tree_clean(self, repo_path):
        # Arrange
        (repo_path / "feature.txt").write_text("work\n")
        stage_all(repo_path)

        # Act
        commit_changes(repo_path, "add feature")

        # Assert
        assert get_repo_info(repo_path).status == RepoStatus.CLEAN

    def test_commit_with_nothing_staged_does_not_add_a_commit(self, repo_path, repo):
        # Arrange
        before = len(list(repo.iter_commits()))

        # Act
        commit_changes(repo_path, "empty")

        # Assert
        assert len(list(Repo(repo_path).iter_commits())) == before


class TestBranches:
    def test_create_branch_appears_in_listing(self, repo_path):
        # Act
        create_branch(repo_path, "feature/x", checkout=False)

        # Assert
        assert "feature/x" in {b.name for b in get_branches(repo_path)}

    def test_create_branch_with_checkout_switches_head(self, repo_path):
        # Act
        create_branch(repo_path, "feature/y", checkout=True)

        # Assert
        assert get_repo_info(repo_path).branch == "feature/y"

    def test_delete_branch_removes_it(self, repo_path):
        # Arrange
        create_branch(repo_path, "feature/z", checkout=False)

        # Act
        delete_branch(repo_path, "feature/z", force=True)

        # Assert
        assert "feature/z" not in {b.name for b in get_branches(repo_path)}

    def test_delete_current_branch_is_rejected(self, repo_path):
        # Arrange
        current = get_repo_info(repo_path).branch

        # Act
        delete_branch(repo_path, current, force=True)

        # Assert — git refuses to delete the checked-out branch
        assert current in {b.name for b in get_branches(repo_path)}


class TestStash:
    def test_stash_create_clears_the_working_tree(self, repo_path):
        # Arrange
        (repo_path / "README.md").write_text("# modified\n")

        # Act
        stash_create(repo_path, "wip")

        # Assert
        assert get_repo_info(repo_path).status == RepoStatus.CLEAN

    def test_stash_pop_restores_the_change(self, repo_path):
        # Arrange
        (repo_path / "README.md").write_text("# modified\n")
        stash_create(repo_path, "wip")

        # Act
        stash_pop(repo_path)

        # Assert
        assert (repo_path / "README.md").read_text() == "# modified\n"

    def test_stash_create_increments_stash_count(self, repo_path):
        # Arrange
        (repo_path / "README.md").write_text("# modified\n")

        # Act
        stash_create(repo_path, "wip")

        # Assert
        assert get_repo_info(repo_path).stash_count == 1


class TestPush:
    def test_git_push_updates_the_remote(self, repo_path, remote_repo):
        # Arrange
        repo = Repo(repo_path)
        repo.create_remote("origin", str(remote_repo))
        repo.git.push("--set-upstream", "origin", "main")
        (repo_path / "later.txt").write_text("later\n")
        stage_all(repo_path)
        commit_changes(repo_path, "later work")

        # Act
        git_push(repo_path)

        # Assert — read the pushed branch directly; a bare repo's default HEAD
        # may point at a branch name the working repo never used.
        pushed = Repo(remote_repo).refs["main"].commit
        assert pushed.message.strip() == "later work"

    def test_repo_is_ahead_before_push(self, repo_path, remote_repo):
        # Arrange
        repo = Repo(repo_path)
        repo.create_remote("origin", str(remote_repo))
        repo.git.push("--set-upstream", "origin", "main")
        (repo_path / "later.txt").write_text("later\n")
        stage_all(repo_path)
        commit_changes(repo_path, "later work")

        # Act
        info = get_repo_info(repo_path)

        # Assert
        assert info.ahead == 1

    def test_ahead_returns_to_zero_after_push(self, repo_path, remote_repo):
        # Arrange
        repo = Repo(repo_path)
        repo.create_remote("origin", str(remote_repo))
        repo.git.push("--set-upstream", "origin", "main")
        (repo_path / "later.txt").write_text("later\n")
        stage_all(repo_path)
        commit_changes(repo_path, "later work")

        # Act
        git_push(repo_path)

        # Assert
        assert get_repo_info(repo_path).ahead == 0


class TestIsDirty:
    def test_clean_repo_is_not_dirty(self, repo_path):
        # Act
        dirty, _summary = is_dirty(repo_path)

        # Assert
        assert dirty is False

    def test_modified_file_makes_repo_dirty(self, repo_path):
        # Arrange
        (repo_path / "README.md").write_text("# changed\n")

        # Act
        dirty, summary = is_dirty(repo_path)

        # Assert
        assert dirty is True
        assert summary

    def test_untracked_file_makes_repo_dirty(self, repo_path):
        # Arrange
        (repo_path / "stray.txt").write_text("stray\n")

        # Act
        dirty, _summary = is_dirty(repo_path)

        # Assert
        assert dirty is True


class TestGetRepoInfo:
    def test_reports_branch_and_clean_status(self, repo_path):
        # Act
        info = get_repo_info(repo_path)

        # Assert
        assert info.branch == "main"
        assert info.status == RepoStatus.CLEAN
        assert info.total_commits == 1

    def test_untracked_file_is_counted(self, repo_path):
        # Arrange
        (repo_path / "stray.txt").write_text("stray\n")

        # Act
        info = get_repo_info(repo_path)

        # Assert
        assert info.status == RepoStatus.UNTRACKED
        assert info.modified_count >= 1

    def test_last_commit_message_is_populated(self, repo_path):
        # Act
        info = get_repo_info(repo_path)

        # Assert
        assert info.last_commit_msg == "initial commit"
        assert info.last_commit_ts > 0

    def test_non_repo_directory_yields_placeholder(self, tmp_path):
        # Arrange — a directory that is not a git repo
        plain = tmp_path / "plain"
        plain.mkdir()

        # Act
        info = get_repo_info(plain)

        # Assert — get_repo_info swallows the error and degrades
        assert info.branch == "unknown"
        assert info.last_commit_ts == 0.0
