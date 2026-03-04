"""
main.py — GitPulse entry point.

Launches the Textual TUI application. Accepts an optional --root CLI
argument to set the directory to scan for git repositories.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static
from textual.containers import Horizontal

# Ensure the gitpulse package root is on sys.path so local imports work
# when running `python main.py` directly from the gitpulse/ directory.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from scanner import scan_repos
from git_ops import get_repo_info, switch_branch, RepoInfo
from ui.sidebar import RepoSidebar
from ui.tabs import MainPanel


class GitPulseApp(App):
    """
    GitPulse — A developer-focused Git repository dashboard TUI.

    Scans a root directory for all local git repos and displays live
    status, recent commits, diffs, and branch management.
    """

    CSS_PATH = "ui/styles.tcss"

    TITLE = "GitPulse"
    SUB_TITLE = "Git Repo Dashboard"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("tab", "focus_next", "Next Tab", show=False),
        Binding("shift+tab", "focus_previous", "Prev Tab", show=False),
    ]

    def __init__(self, root_dir: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.root_dir = root_dir
        self.repos: list[RepoInfo] = []
        self._selected_repo: RepoInfo | None = None

    # -----------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="app-grid"):
            yield RepoSidebar(id="sidebar-container")
            yield MainPanel(id="main-panel")
        yield Footer()

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def on_mount(self) -> None:
        """Initial scan on startup — delayed to ensure DOM is ready."""
        self.call_later(self._scan_and_populate)

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------

    def action_refresh(self) -> None:
        """Rescan all repositories (bound to 'r')."""
        self._scan_and_populate()
        self.notify("Repositories refreshed ⚡", timeout=2)

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _scan_and_populate(self) -> None:
        """Discover repos, build info objects, and populate sidebar."""
        paths = scan_repos(self.root_dir)
        self.repos = [get_repo_info(p) for p in paths]

        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.populate(self.repos)

        # Load first repo into main panel if available
        if self.repos:
            self._select_repo(self.repos[0])

    def _select_repo(self, repo_info: RepoInfo) -> None:
        """Load a repo's data into the main panel."""
        self._selected_repo = repo_info
        main: MainPanel = self.query_one("#main-panel", MainPanel)
        main.load_repo(repo_info.path)

    # -----------------------------------------------------------------
    # Message handlers
    # -----------------------------------------------------------------

    def on_repo_sidebar_repo_selected(self, message: RepoSidebar.RepoSelected) -> None:
        """User navigated to a different repo in the sidebar."""
        self._select_repo(message.repo_info)

    def on_main_panel_branch_switch_requested(
        self, message: MainPanel.BranchSwitchRequested
    ) -> None:
        """User pressed Enter on a branch in the Branches tab."""
        if self._selected_repo is None:
            return

        result = switch_branch(self._selected_repo.path, message.branch_name)
        self.notify(result, timeout=3)

        # Refresh the selected repo's data
        updated_info = get_repo_info(self._selected_repo.path)
        self._selected_repo = updated_info
        main: MainPanel = self.query_one("#main-panel", MainPanel)
        main.load_repo(updated_info.path)

        # Also refresh sidebar to reflect branch change
        self._scan_and_populate()


# -----------------------------------------------------------------------
# CLI entry point
# -----------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="gitpulse",
        description="GitPulse — Git Repo Dashboard TUI",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(Path.home() / "projects"),
        help="Root directory to scan for git repos (default: ~/projects)",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()
    root = Path(args.root).expanduser().resolve()

    if not root.is_dir():
        print(f"Error: '{root}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    app = GitPulseApp(root_dir=root)
    app.run()


if __name__ == "__main__":
    main()
