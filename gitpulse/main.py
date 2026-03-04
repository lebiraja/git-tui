"""
main.py — GitPulse entry point.

Launches the Textual TUI application. Accepts an optional --root CLI
argument to set the directory to scan for git repositories.
Repos are sorted by most recent commit date.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer
from textual.containers import Horizontal

# Support both installed-package imports (gitpulse.scanner) and
# direct execution (python main.py) by trying relative first.
try:
    from gitpulse.scanner import scan_repos
    from gitpulse.git_ops import get_repo_info, switch_branch, RepoInfo
    from gitpulse.ui.sidebar import RepoSidebar
    from gitpulse.ui.tabs import MainPanel
except ImportError:
    # Running directly: python main.py
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
    Repos are sorted by most recent commit (most active first).
    """

    CSS_PATH = str(Path(__file__).parent / "ui" / "styles.tcss")

    TITLE = "GitPulse"
    SUB_TITLE = "Git Repo Dashboard"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("slash", "search", "Search", show=True),
        Binding("escape", "clear_search", "Clear", show=False),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Prev", show=False),
    ]

    def __init__(self, root_dir: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.root_dir = root_dir
        self.repos: list[RepoInfo] = []
        self._all_repos: list[RepoInfo] = []  # Unfiltered master list
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

    def action_search(self) -> None:
        """Focus the search input (bound to '/')."""
        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.focus_search()

    def action_clear_search(self) -> None:
        """Clear search and refocus repo list."""
        from textual.widgets import Input
        inp = self.query_one("#search-input", Input)
        inp.value = ""
        self.query_one("#repo-list").focus()

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _scan_and_populate(self) -> None:
        """Discover repos, build info objects, sort by date, and populate sidebar."""
        paths = scan_repos(self.root_dir)
        self._all_repos = [get_repo_info(p) for p in paths]

        # Sort by most recent commit date (descending)
        self._all_repos.sort(key=lambda r: r.last_commit_ts, reverse=True)
        self.repos = list(self._all_repos)

        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.populate(self.repos)

        # Load first repo into main panel if available
        if self.repos:
            self._select_repo(self.repos[0])

    def _select_repo(self, repo_info: RepoInfo) -> None:
        """Load a repo's data into the main panel."""
        self._selected_repo = repo_info
        main: MainPanel = self.query_one("#main-panel", MainPanel)
        main.load_repo(repo_info.path, repo_info)

    def _apply_filter(self, query: str) -> None:
        """Filter the repo list by name, re-populate sidebar."""
        q = query.strip().lower()
        if q:
            self.repos = [r for r in self._all_repos if q in r.name.lower()]
        else:
            self.repos = list(self._all_repos)

        sidebar: RepoSidebar = self.query_one("#sidebar-container", RepoSidebar)
        sidebar.populate(self.repos)

        if self.repos:
            self._select_repo(self.repos[0])

    # -----------------------------------------------------------------
    # Message handlers
    # -----------------------------------------------------------------

    def on_repo_sidebar_repo_selected(self, message: RepoSidebar.RepoSelected) -> None:
        """User navigated to a different repo in the sidebar."""
        self._select_repo(message.repo_info)

    def on_repo_sidebar_search_changed(self, message: RepoSidebar.SearchChanged) -> None:
        """User typed in the search bar."""
        self._apply_filter(message.query)

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
        main.load_repo(updated_info.path, updated_info)

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
    """Entry point — called by both `python main.py` and the `gitpulse` command."""
    args = parse_args()
    root = Path(args.root).expanduser().resolve()

    if not root.is_dir():
        print(f"Error: '{root}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    app = GitPulseApp(root_dir=root)
    app.run()


if __name__ == "__main__":
    main()
